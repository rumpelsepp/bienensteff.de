"""Small HTTP client on top of pycurl (libcurl), shared by the Grist,
Lexware, DWD and Trachtnet code -- replaces niquests, which pulled in a
pile of less well-known dependencies just for a handful of plain REST calls.

Deliberately covers only what those callers need: a reusable client with
base URL, default headers and timeouts, query params (list values repeat
the key, like requests does), a JSON request body, redirects, transparent
decompression, a few retries on connection failures, and a Response with
status_code/ok/content/text/json()/raise_for_status().

All settings live in one ClientConfig (frozen dataclass), so callers
describe a client declaratively and can derive variants with
dataclasses.replace() -- e.g. a CLI flag overriding the concurrency.

Two flavors sharing all request setup:
- Client: blocking. Keeps one curl handle, so connections are reused
  across requests (curl_easy_reset() keeps the connection cache). Not
  thread-safe -- use one Client per thread.
- AsyncClient: asyncio, via pycurl's own AsyncCurlMulti (libcurl's
  multi-socket API driven by the event loop -- no threads, no polling).
  Concurrent requests share the multi handle's connection pool, and
  HTTP/2 requests to the same host get multiplexed over one connection.

Politeness: ClientConfig.min_interval spaces out request *starts* across
the whole client (both flavors, incl. retries), independent of how many
run concurrently -- max_concurrency alone would let a fast server be hit
as often as it can answer.

URLs are built with libcurl's own URL API (pycurl.CurlUrl, i.e.
curl_url()) rather than string concatenation and urllib.parse: libcurl
parses, normalizes and percent-encodes, and the handle is passed to
the transfer as-is (CURLOPT_CURLU), so the URL curl sends is exactly
the one built here.

Logging (logger "bstools.httpclient"): one DEBUG line per request with
status, HTTP version, size and a timing breakdown (DNS/connect/TLS/first
byte/total, and whether a pooled connection was reused) -- shows up with
any CLI's --debug. ClientConfig.trace (default: BSTOOLS_HTTP_TRACE=1 in
the environment) additionally enables
curl's verbose trace (like `curl -v`: connection info, request and
response headers, Authorization/Cookie redacted) on
"bstools.httpclient.trace", independent of --debug.

Response bodies are buffered in memory -- fine for JSON APIs and the few
MB of a DWD zip. libcurl itself already handles chunked transfer
encoding, Content-Encoding (gzip/brotli/zstd) and HTTP/2 streams below
this layer, so a body always arrives here complete and decoded.
"""

from __future__ import annotations

import asyncio
import io
import json as jsonlib
import logging
import math
import os
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Self

import pycurl

logger = logging.getLogger(__name__)
trace_logger = logging.getLogger(f"{__name__}.trace")

TRACE = os.environ.get("BSTOOLS_HTTP_TRACE", "") not in ("", "0")
if TRACE:
    # Propagation to the root handlers doesn't check the root's level, so
    # this makes the trace visible even without a CLI's --debug.
    trace_logger.setLevel(logging.DEBUG)

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

_HTTP_VERSIONS = {
    pycurl.CURL_HTTP_VERSION_1_0: "HTTP/1.0",
    pycurl.CURL_HTTP_VERSION_1_1: "HTTP/1.1",
    pycurl.CURL_HTTP_VERSION_2_0: "HTTP/2",
    pycurl.CURL_HTTP_VERSION_3: "HTTP/3",
}

# Matches the header both as a real header line ("Authorization: ...")
# and inside curl's HTTP/2 stream info text ("[authorization: ...]").
_HTTP_VERSION_OPTS = {
    "1.1": pycurl.CURL_HTTP_VERSION_1_1,
    "2": pycurl.CURL_HTTP_VERSION_2TLS,  # h2 over TLS, HTTP/1.1 for plain http
    "3": pycurl.CURL_HTTP_VERSION_3,  # try h3, fall back to h2/h1.1
}

_REDACT_RE = re.compile(r"(?i)\b((?:proxy-)?authorization|(?:set-)?cookie)(:\s*)[^\]\r\n]*")


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
    """Connect timed out, no data arrived for `timeout` seconds, or the
    whole request exceeded `total_timeout`."""


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
    http_version: str
    elapsed: float  # seconds, whole transfer incl. redirects

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


def _trace(infotype: int, data: bytes) -> None:
    """CURLOPT_DEBUGFUNCTION callback -- the same information `curl -v`
    prints, minus body bytes."""
    match infotype:
        case pycurl.INFOTYPE_TEXT:
            prefix = "*"
        case pycurl.INFOTYPE_HEADER_OUT:
            prefix = ">"
        case pycurl.INFOTYPE_HEADER_IN:
            prefix = "<"
        case _:
            return
    for line in data.decode("utf-8", errors="replace").splitlines():
        if not line:
            continue
        line = _REDACT_RE.sub(r"\1\2[redacted]", line)
        trace_logger.debug("%s %s", prefix, line)


@dataclass(frozen=True, kw_only=True)
class ClientConfig:
    """Everything a Client/AsyncClient can be tuned with.

    Timeouts (seconds): `timeout` is how long a transfer may stall
    without receiving any data (like requests' read timeout) -- it covers
    a server that takes long to start answering as well as one that stops
    mid-body. `connect_timeout` bounds DNS + TCP + TLS setup.
    `total_timeout`, if set, is a hard cap on the whole request incl.
    redirects.

    `retries`/`retry_backoff`: retries only happen for connection
    failures (see _RETRY_ANY/_RETRY_GET), never for HTTP error statuses or
    timeouts -- callers handle those themselves. Retry n waits
    retry_backoff * 2**n seconds.

    `max_concurrency` (AsyncClient only) caps in-flight requests;
    `min_interval` is the minimum time between two request starts across
    the whole client -- together they bound the load on the server.

    `http_version`: None lets libcurl negotiate (HTTP/2 over TLS where
    the server offers it); "3" tries HTTP/3 first. `ca_bundle`: None
    autodetects the system bundle (see _find_ca_bundle). `trace`: curl's
    verbose trace, see the module docstring.
    """

    base_url: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)
    user_agent: str = pycurl.version.split()[0]
    connect_timeout: float = 10.0
    timeout: float = 60.0
    total_timeout: float | None = None
    retries: int = 2
    retry_backoff: float = 0.5
    max_redirects: int = 10
    max_concurrency: int = 4
    min_interval: float = 0.0
    http_version: Literal["1.1", "2", "3"] | None = None
    ca_bundle: str | None = None
    trace: bool = TRACE


class _BaseClient:
    def __init__(self, config: ClientConfig | None = None) -> None:
        self.config = config or ClientConfig()
        self.base_url = (
            pycurl.CurlUrl(self.config.base_url.encode()) if self.config.base_url else None
        )
        self.headers = dict(self.config.headers)
        self._ca_bundle = self.config.ca_bundle or _find_ca_bundle()
        self._next_start = 0.0

    def _reserve_start(self) -> float:
        """Books the next request start slot per config.min_interval and
        returns how long to wait for it (0 if it's now). Reservation
        rather than sleep-under-lock, so concurrent async requests queue
        up in order without holding anything while they wait."""
        interval = self.config.min_interval
        if interval <= 0:
            return 0.0
        now = time.monotonic()
        start = max(now, self._next_start)
        self._next_start = start + interval
        return start - now

    def _build_url(self, url: str, params: Mapping[str, Any] | None) -> pycurl.CurlUrl:
        """Relative `url`s are appended to the base URL's path (not
        RFC 3986-resolved against it: "/articles" on ".../v1" must give
        ".../v1/articles", not "/articles"). Params are appended one by
        one, percent-encoded by libcurl; list values repeat the key, None
        values are skipped. Everything goes to libcurl as UTF-8 bytes --
        pycurl encodes str arguments as ASCII and would choke on "süß".
        """
        if self.base_url is None or url.startswith(("http://", "https://")):
            u = pycurl.CurlUrl(url.encode())
        else:
            path, _, query = url.partition("?")
            u = pycurl.CurlUrl(self.base_url.url)
            base_path = (u.path or "").rstrip("/")
            u.path = f"{base_path}/{path.lstrip('/')}".encode()
            if query:
                u.setpart(pycurl.UPART_QUERY, query.encode(), pycurl.U_APPENDQUERY)
        for key, value in (params or {}).items():
            values = value if isinstance(value, (list, tuple)) else [value]
            for v in values:
                if v is None:
                    continue
                u.setpart(
                    pycurl.UPART_QUERY,
                    f"{key}={v}".encode(),
                    pycurl.U_APPENDQUERY | pycurl.U_URLENCODE,
                )
        return u

    def _header_lines(self, headers: Mapping[str, str] | None, has_json: bool) -> list[str]:
        # Case-insensitive merge: per-request headers override the defaults.
        merged = {k.lower(): (k, v) for k, v in self.headers.items()}
        merged.update({k.lower(): (k, v) for k, v in (headers or {}).items()})
        if has_json:
            merged.setdefault("content-type", ("Content-Type", "application/json"))
        # No "Expect: 100-continue" round trip before larger bodies.
        merged.setdefault("expect", ("Expect", ""))
        return [f"{k}: {v}" for k, v in merged.values()]

    def _setup(
        self,
        c: pycurl.Curl,
        method: str,
        url: pycurl.CurlUrl,
        header_lines: list[str],
        body: bytes | None,
    ) -> io.BytesIO:
        cfg = self.config
        c.reset()
        buf = io.BytesIO()
        c.setopt(pycurl.CURLU, url)
        c.setopt(pycurl.HTTPHEADER, header_lines)
        c.setopt(pycurl.WRITEDATA, buf)
        c.setopt(pycurl.FOLLOWLOCATION, True)
        c.setopt(pycurl.MAXREDIRS, cfg.max_redirects)
        c.setopt(pycurl.ACCEPT_ENCODING, "")  # everything libcurl can decode
        c.setopt(pycurl.USERAGENT, cfg.user_agent)
        c.setopt(pycurl.NOSIGNAL, True)
        c.setopt(pycurl.CONNECTTIMEOUT_MS, int(cfg.connect_timeout * 1000))
        c.setopt(pycurl.LOW_SPEED_LIMIT, 1)
        c.setopt(pycurl.LOW_SPEED_TIME, max(1, math.ceil(cfg.timeout)))
        if cfg.total_timeout is not None:
            c.setopt(pycurl.TIMEOUT_MS, int(cfg.total_timeout * 1000))
        if cfg.http_version is not None:
            c.setopt(pycurl.HTTP_VERSION, _HTTP_VERSION_OPTS[cfg.http_version])
        if self._ca_bundle:
            c.setopt(pycurl.CAINFO, self._ca_bundle)
        if cfg.trace:
            c.setopt(pycurl.VERBOSE, True)
            c.setopt(pycurl.DEBUGFUNCTION, _trace)

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
        return buf

    @staticmethod
    def _transport_error(exc: pycurl.error, method: str, url: str) -> TransportError:
        # (CURLcode, message) -- types-pycurl doesn't type the args.
        args: tuple[Any, ...] = exc.args
        code, message = int(args[0]), str(args[1])
        cls = Timeout if code == pycurl.E_OPERATION_TIMEDOUT else TransportError
        return cls(code, message, method, url)

    @staticmethod
    def _response(c: pycurl.Curl, method: str, buf: io.BytesIO) -> Response:
        resp = Response(
            method=method,
            url=c.getinfo(pycurl.EFFECTIVE_URL),
            status_code=c.getinfo(pycurl.RESPONSE_CODE),
            content=buf.getvalue(),
            http_version=_HTTP_VERSIONS.get(c.getinfo(pycurl.INFO_HTTP_VERSION), "HTTP/?"),
            elapsed=c.getinfo(pycurl.TOTAL_TIME_T) / 1e6,
        )
        if logger.isEnabledFor(logging.DEBUG):
            ms = {
                name: c.getinfo(info) / 1000
                for name, info in (
                    ("dns", pycurl.NAMELOOKUP_TIME_T),
                    ("connect", pycurl.CONNECT_TIME_T),
                    ("tls", pycurl.APPCONNECT_TIME_T),
                    ("ttfb", pycurl.STARTTRANSFER_TIME_T),
                )
            }
            reused = c.getinfo(pycurl.NUM_CONNECTS) == 0
            logger.debug(
                "%s %s -> %s %s, %d bytes, %.0f ms "
                "(dns %.0f, connect %.0f, tls %.0f, ttfb %.0f ms%s)",
                method,
                resp.url,
                resp.http_version,
                resp.status_code,
                c.getinfo(pycurl.SIZE_DOWNLOAD_T),
                resp.elapsed * 1000,
                ms["dns"],
                ms["connect"],
                ms["tls"],
                ms["ttfb"],
                ", reused connection" if reused else "",
            )
        return resp

    def _prepare(
        self,
        method: str,
        url: str,
        params: Mapping[str, Any] | None,
        json: Any,
        headers: Mapping[str, str] | None,
    ) -> tuple[str, pycurl.CurlUrl, list[str], bytes | None]:
        body = None if json is None else jsonlib.dumps(json).encode()
        return (
            str(method).upper(),
            self._build_url(url, params),
            self._header_lines(headers, has_json=body is not None),
            body,
        )

    def _retry_delay(self, exc: TransportError, method: str, attempt: int) -> float | None:
        """Seconds to wait before retry number `attempt` (1-based), or
        None if `exc` shouldn't be retried."""
        retryable = exc.curl_code in _RETRY_ANY or (method == "GET" and exc.curl_code in _RETRY_GET)
        retries = self.config.retries
        if isinstance(exc, Timeout) or not retryable or attempt > retries:
            return None
        delay = self.config.retry_backoff * 2.0**attempt
        logger.warning("%s, retrying in %.1fs (%s/%s)", exc, delay, attempt, retries)
        return delay


class Client(_BaseClient):
    def __init__(self, config: ClientConfig | None = None) -> None:
        super().__init__(config)
        self._curl = pycurl.Curl()

    def close(self) -> None:
        self._curl.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        method, curl_url, header_lines, body = self._prepare(method, url, params, json, headers)
        attempt = 0
        while True:
            if wait := self._reserve_start():
                time.sleep(wait)
            buf = self._setup(self._curl, method, curl_url, header_lines, body)
            try:
                self._curl.perform()
            except pycurl.error as exc:
                err = self._transport_error(exc, method, str(curl_url.url))
                attempt += 1
                delay = self._retry_delay(err, method, attempt)
                if delay is None:
                    raise err from exc
                time.sleep(delay)
                continue
            return self._response(self._curl, method, buf)

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Response:
        return self.request("PATCH", url, **kwargs)


class AsyncClient(_BaseClient):
    def __init__(self, config: ClientConfig | None = None) -> None:
        super().__init__(config)
        self._multi = pycurl.AsyncCurlMulti()
        self._sem = asyncio.Semaphore(self.config.max_concurrency)
        # Idle easy handles, reused across requests (one per concurrent
        # request at most); connections live in the multi handle's pool.
        self._idle: list[pycurl.Curl] = []

    async def aclose(self) -> None:
        await self._multi.aclose()
        for c in self._idle:
            c.close()
        self._idle.clear()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        method, curl_url, header_lines, body = self._prepare(method, url, params, json, headers)
        attempt = 0
        while True:
            async with self._sem:
                if wait := self._reserve_start():
                    await asyncio.sleep(wait)
                c = self._idle.pop() if self._idle else pycurl.Curl()
                try:
                    buf = self._setup(c, method, curl_url, header_lines, body)
                    try:
                        await self._multi.perform(c)
                    except pycurl.error as exc:
                        err = self._transport_error(exc, method, str(curl_url.url))
                        attempt += 1
                        delay = self._retry_delay(err, method, attempt)
                        if delay is None:
                            raise err from exc
                    else:
                        return self._response(c, method, buf)
                finally:
                    self._idle.append(c)
            # Sleep outside the semaphore, so a backing-off request doesn't
            # block a concurrency slot.
            await asyncio.sleep(delay)

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self.request("POST", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Response:
        return await self.request("PATCH", url, **kwargs)
