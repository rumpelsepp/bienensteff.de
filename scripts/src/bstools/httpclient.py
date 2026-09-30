"""Small HTTP client on top of pycurl (libcurl), shared by the Grist,
Lexware, DWD and Trachtnet code -- replaces niquests, which pulled in a
pile of less well-known dependencies just for a handful of plain REST calls.

Deliberately covers only what those callers need: a reusable client with
base URL, default headers and timeout, query params (list values repeat
the key, like requests does), a JSON request body, redirects, transparent
decompression, a few retries on connection failures, and a Response with
status_code/ok/content/text/json()/raise_for_status().

One Client keeps one curl handle, so connections are reused across
requests (curl_easy_reset() keeps the connection cache). Not thread-safe
-- use one Client per thread.
"""

from __future__ import annotations

import io
import json as jsonlib
import logging
import math
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlencode

import pycurl

logger = logging.getLogger(__name__)

# The pycurl wheels bundle their own libcurl/OpenSSL, whose compiled-in CA
# bundle path is that of the wheel build system and may not exist on the
# machine actually running this (e.g. Ubuntu CI vs. a RHEL-based build
# image). So point libcurl at the system's CA bundle explicitly -- first
# one that exists wins, after the usual env var overrides.
_CA_BUNDLE_ENV = ("CURL_CA_BUNDLE", "SSL_CERT_FILE")
_CA_BUNDLE_PATHS = (
    "/etc/pki/tls/certs/ca-bundle.crt",  # Fedora/RHEL
    "/etc/ssl/certs/ca-certificates.crt",  # Debian/Ubuntu/Alpine/Arch
    "/etc/ssl/ca-bundle.pem",  # openSUSE
    "/etc/ssl/cert.pem",  # macOS/BSD
)

# Connection-level failures worth retrying for any method -- the request
# never reached the server, so a retry can't duplicate a write.
_RETRY_ANY = {pycurl.E_COULDNT_RESOLVE_HOST, pycurl.E_COULDNT_CONNECT}
# Failures mid-exchange: only retried for GET, since a POST/PATCH may
# already have been applied server-side.
_RETRY_GET = {pycurl.E_GOT_NOTHING, pycurl.E_SEND_ERROR, pycurl.E_RECV_ERROR}


def _find_ca_bundle() -> str | None:
    for var in _CA_BUNDLE_ENV:
        if path := os.environ.get(var):
            return path
    for path in _CA_BUNDLE_PATHS:
        if Path(path).is_file():
            return path
    return None


class TransportError(Exception):
    """The request didn't produce an HTTP response at all (DNS, connect,
    TLS, connection reset, ...). `curl_code` is libcurl's CURLcode."""

    def __init__(self, curl_code: int, message: str, method: str, url: str) -> None:
        super().__init__(f"{method} {url}: curl error {curl_code}: {message}")
        self.curl_code = curl_code


class Timeout(TransportError):
    """Connect timed out, or no data arrived for `timeout` seconds."""


class HTTPError(Exception):
    """Raised by Response.raise_for_status() for 4xx/5xx responses."""

    def __init__(self, response: Response) -> None:
        super().__init__(f"HTTP {response.status_code} for {response.method} {response.url}")
        self.response = response


@dataclass(frozen=True)
class Response:
    method: str
    url: str
    status_code: int
    content: bytes

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return jsonlib.loads(self.content)

    def raise_for_status(self) -> None:
        if not self.ok:
            raise HTTPError(self)


class Client:
    def __init__(
        self,
        base_url: str = "",
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
        retries: int = 2,
    ) -> None:
        """`timeout` is both the connect timeout and how long a transfer
        may stall without receiving any data (like requests' read timeout),
        not a cap on the total transfer time. `retries` only applies to
        connection failures (see _RETRY_ANY/_RETRY_GET), never to HTTP
        error statuses -- callers handle those themselves.
        """
        self.base_url = base_url.rstrip("/")
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.retries = retries
        self._ca_bundle = _find_ca_bundle()
        self._curl = pycurl.Curl()

    def close(self) -> None:
        self._curl.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _build_url(self, url: str, params: Mapping[str, Any] | None) -> str:
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"
        if params:
            query = urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
            if query:
                url += ("&" if "?" in url else "?") + query
        return url

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        method = str(method).upper()
        full_url = self._build_url(url, params)

        # Case-insensitive merge: per-request headers override the defaults.
        merged = {k.lower(): (k, v) for k, v in self.headers.items()}
        merged.update({k.lower(): (k, v) for k, v in (headers or {}).items()})
        body: bytes | None = None
        if json is not None:
            body = jsonlib.dumps(json).encode()
            merged.setdefault("content-type", ("Content-Type", "application/json"))
        # No "Expect: 100-continue" round trip before larger bodies.
        merged.setdefault("expect", ("Expect", ""))
        header_lines = [f"{k}: {v}" for k, v in merged.values()]

        attempt = 0
        while True:
            try:
                return self._perform(method, full_url, header_lines, body)
            except TransportError as exc:
                retryable = exc.curl_code in _RETRY_ANY or (
                    method == "GET" and exc.curl_code in _RETRY_GET
                )
                if isinstance(exc, Timeout) or not retryable or attempt >= self.retries:
                    raise
                attempt += 1
                delay = 0.5 * 2**attempt
                logger.warning("%s, retrying in %.1fs (%s/%s)", exc, delay, attempt, self.retries)
                time.sleep(delay)

    def _perform(
        self, method: str, url: str, header_lines: list[str], body: bytes | None
    ) -> Response:
        c = self._curl
        c.reset()
        buf = io.BytesIO()
        c.setopt(pycurl.URL, url)
        c.setopt(pycurl.HTTPHEADER, header_lines)
        c.setopt(pycurl.WRITEDATA, buf)
        c.setopt(pycurl.FOLLOWLOCATION, True)
        c.setopt(pycurl.MAXREDIRS, 10)
        c.setopt(pycurl.ACCEPT_ENCODING, "")  # everything libcurl can decode
        c.setopt(pycurl.USERAGENT, pycurl.version.split()[0])
        c.setopt(pycurl.NOSIGNAL, True)
        c.setopt(pycurl.CONNECTTIMEOUT_MS, int(self.timeout * 1000))
        c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
        c.setopt(pycurl.LOW_SPEED_TIME, max(1, math.ceil(self.timeout)))
        if self._ca_bundle:
            c.setopt(pycurl.CAINFO, self._ca_bundle)

        if body is not None:
            c.setopt(pycurl.POSTFIELDS, body)
            if method != "POST":
                c.setopt(pycurl.CUSTOMREQUEST, method)
        elif method == "GET":
            c.setopt(pycurl.HTTPGET, True)
        elif method == "HEAD":
            c.setopt(pycurl.NOBODY, True)
        else:
            c.setopt(pycurl.CUSTOMREQUEST, method)

        try:
            c.perform()
        except pycurl.error as exc:
            # (CURLcode, message) -- types-pycurl doesn't type the args.
            args: tuple[Any, ...] = exc.args
            code, message = int(args[0]), str(args[1])
            cls = Timeout if code == pycurl.E_OPERATION_TIMEDOUT else TransportError
            raise cls(code, message, method, url) from exc

        return Response(
            method=method,
            url=c.getinfo(pycurl.EFFECTIVE_URL),
            status_code=c.getinfo(pycurl.RESPONSE_CODE),
            content=buf.getvalue(),
        )

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Response:
        return self.request("PATCH", url, **kwargs)
