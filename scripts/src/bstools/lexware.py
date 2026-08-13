"""Shared Lexware Office API client, used by grist_magic, lexware_download and
lexware_sales_by_article -- previously each of those reimplemented parts of
this (throttled HTTP, pagination, deeplinks, article/contact lookups) on
their own.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any

import niquests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lexware.io/v1"
APP_BASE_URL = "https://app.lexware.de"
MIN_INTERVAL = 0.6  # Lexware caps at 2 req/s; margin built in.
# /voucherlist's own default page size is 25; 250 is the documented maximum.
# Doesn't affect correctness (pagination stops on an empty page regardless
# of page_size, see paginate_voucherlist), just fewer round-trips.
MAX_VOUCHERLIST_PAGE_SIZE = 250

# voucherType (API filter value) -> URL path segment, used for detail GETs,
# file downloads, and deeplinks alike.
RESOURCE_INFO: dict[str, str] = {
    "invoice": "invoices",
    "deliverynote": "delivery-notes",
    "orderconfirmation": "order-confirmations",
    "quotation": "quotations",  # path unverified, best guess
    "creditnote": "credit-notes",
    # Down-payment invoices (Abschlagsrechnungen) are their own voucherType,
    # NOT included when filtering voucherType=invoice -- easy to miss a
    # chunk of "Rechnungen" this way if the account uses them. Read-only via
    # the API (no POST /v1/down-payment-invoices).
    "downpaymentinvoice": "down-payment-invoices",
    "dun": "dunnings",
}


class LexwareClient:
    def __init__(self, api_key: str) -> None:
        self._client = niquests.Session(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=30.0,
        )
        self._last_call = 0.0
        # Per-instance caches -- both keyed by Lexware id, populated lazily by
        # get_article_number()/get_contact_name() so repeated lookups across
        # many vouchers cost one API call each instead of one per voucher.
        self._article_cache: dict[str, tuple[str, str | None]] = {}
        self._contact_name_cache: dict[str, str] = {}

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)

    def _send(self, method: str, path: str, **kwargs: Any) -> niquests.Response:
        self._throttle()
        resp = self._client.request(method, path, **kwargs)
        self._last_call = time.monotonic()
        if resp.status_code == 429:
            time.sleep(2.0)
            resp = self._client.request(method, path, **kwargs)
            self._last_call = time.monotonic()
        if not resp.ok and resp.status_code != 404:
            # 404 is deliberately quiet -- callers like get_article_number()
            # already expect and handle it (e.g. an article deleted since
            # the invoice was created). Anything else is unexpected enough
            # to want the full response body, not just the status code.
            logger.error(
                "Lexware API error %s for %s %s: %s", resp.status_code, method, path, resp.text
            )
        resp.raise_for_status()
        return resp

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = self._send("GET", path, params=params).json()
        # Guarded by isEnabledFor rather than left to logger.debug()'s own
        # lazy %-formatting: the json.dumps() itself (and the [:3000] slice
        # of a potentially large payload) shouldn't run at all unless DEBUG
        # is actually enabled (see setup_logging(debug=...) in each CLI's
        # main()).
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "GET %s params=%s\n%s",
                path,
                params,
                json.dumps(data, indent=2, ensure_ascii=False)[:3000],
            )
        return data

    def get_file(self, path: str) -> bytes:
        """GET a binary document (PDF/XML), not JSON -- overrides the
        session's default `Accept: application/json` header. Lexware's own
        docs warn that binary-download endpoints can return metadata
        instead of the actual file bytes when the Accept header doesn't
        ask for a binary type.
        """
        content = self._send(
            "GET", path, headers={"Accept": "application/pdf, application/xml, */*"}
        ).content
        return content or b""

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Generic pager for Lexware's {content, last, ...} paged list
        responses, used by paginate_voucherlist(). Factored out as its own
        method since it's not voucherlist-specific -- ready to reuse for any
        other Lexware list endpoint that follows the same paging shape.

        Stops as soon as the response's own "last" field says so; falls
        back to requesting pages until one comes back empty if that field is
        ever missing (deliberately NOT stopping just because a page is
        shorter than the requested `size` -- that heuristic, used here
        previously, breaks silently whenever the server enforces its own,
        smaller effective page size: a genuinely full server-page then still
        looks "short" relative to what we asked for, so pagination would
        stop after page 1 -- seen in practice, always cut off at exactly 60
        results regardless of the true total, no matter how large `size`
        was set to).
        """
        page = 0
        fetched = 0
        while True:
            data = self.get(path, params={**params, "page": page})
            content = data.get("content", [])
            is_last = data.get("last")
            fetched += len(content)
            logger.debug(
                "%s page %s: %s entries (total so far: %s)%s%s",
                path,
                page,
                len(content),
                fetched,
                "" if content else " -- empty page, done",
                " -- last page" if is_last and content else "",
            )
            if not content:
                return
            yield from content
            if is_last is True:
                return
            page += 1

    def paginate_voucherlist(
        self,
        voucher_type: str,
        voucher_status: str = "any",
        page_size: int = MAX_VOUCHERLIST_PAGE_SIZE,
        extra_params: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """See _paginate() for the pagination behavior.

        `extra_params` is merged into the request as-is, e.g.
        {"voucherDateFrom": ..., "voucherDateTo": ..., "contactId": ...,
        "voucherNumber": ...} -- see
        https://developers.lexware.io/docs/#voucherlist-endpoint. A plain
        dict rather than **kwargs, so callers can build it dynamically
        (e.g. an optional date range) without mypy treating the unpacked
        dict as having to match every other keyword parameter's type too.
        """
        yield from self._paginate(
            "/voucherlist",
            {
                "voucherType": voucher_type,
                "voucherStatus": voucher_status,
                "size": page_size,
                **(extra_params or {}),
            },
        )

    # Note: GET /v1/vouchers ("Belege" -- manually recorded bookkeeping
    # income/expense entries) looked like a natural fit for a
    # paginate_bookkeeping_vouchers() alongside paginate_voucherlist(), but
    # it 400s with "voucherNumber parameter is required" when called
    # without one -- it's a single-voucher lookup by number, not a list-all
    # endpoint. There is no way to discover/enumerate all Belege via the
    # public API, so this was removed again rather than kept as dead code.

    def index_vouchers(
        self, voucher_type: str, voucher_status: str = "any"
    ) -> dict[str, dict[str, Any]]:
        """Mapping voucher id -> {voucherNumber, voucherStatus, voucherDate,
        totalAmount, openAmount}, from the /voucherlist view only -- no
        per-voucher detail GET.

        Deliberately not a per-voucher detail GET (e.g. GET /invoices/{id}):
        that response has no "openAmount" field at all, only totalPrice.*
        for the voucher's own total. openAmount only exists on the
        /voucherlist summary, so that's the only source for it.
        """
        index: dict[str, dict[str, Any]] = {}
        for entry in self.paginate_voucherlist(voucher_type, voucher_status):
            voucher_id = entry.get("id")
            if not voucher_id:
                continue
            index[voucher_id] = {
                "voucherNumber": entry.get("voucherNumber"),
                "voucherStatus": entry.get("voucherStatus"),
                "voucherDate": (entry.get("voucherDate") or "")[:10] or None,
                "totalAmount": entry.get("totalAmount"),
                "openAmount": entry.get("openAmount"),
            }
        return index

    def find_voucher_id(self, voucher_type: str, voucher_number: str) -> str | None:
        data = self.get(
            "/voucherlist",
            params={
                "voucherType": voucher_type,
                "voucherStatus": "any",
                "voucherNumber": voucher_number,
            },
        )
        content = data.get("content", [])
        return content[0]["id"] if content else None

    def get_voucher_detail(self, voucher_type: str, voucher_id: str) -> dict[str, Any]:
        return self.get(f"/{RESOURCE_INFO[voucher_type]}/{voucher_id}")

    def get_voucher_file(self, voucher_type: str, voucher_id: str) -> bytes:
        return self.get_file(f"/{RESOURCE_INFO[voucher_type]}/{voucher_id}/file")

    def download_voucher_pdf(self, voucher_type: str, voucher_number: str) -> bytes:
        """Resolves a human-readable voucher number (e.g. "RE-1044") to its
        PDF bytes: find_voucher_id() then get_voucher_file(), with a magic-
        byte sanity check (Lexware's file endpoints have been known to hand
        back something other than the actual PDF, e.g. metadata or an error
        page, without a non-2xx status to signal it).

        Raises KeyError if no voucher with that number exists, ValueError if
        the response doesn't look like a PDF.
        """
        voucher_id = self.find_voucher_id(voucher_type, voucher_number)
        if voucher_id is None:
            raise KeyError(f"{voucher_number} not found")
        data = self.get_voucher_file(voucher_type, voucher_id)
        if not data.startswith(b"%PDF-"):
            raise ValueError(
                f"{voucher_number}: response doesn't look like a PDF "
                f"(starts with {data[:16]!r}, {len(data)} bytes total) -- "
                f"not writing it out."
            )
        return data

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        return self.get(f"/contacts/{contact_id}")

    def get_contact_name(self, contact_id: str) -> str:
        """Display name for a contact, cached per client instance. A
        contact is either a company (has a "company" block) or a person
        (has a "person" block, first/last name) -- falls back to "Unknown"
        for anything else rather than raising.
        """
        if contact_id not in self._contact_name_cache:
            contact = self.get_contact(contact_id)
            company = contact.get("company") or {}
            person = contact.get("person") or {}
            if company.get("name"):
                name = company["name"]
            elif person:
                name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
            else:
                name = "Unknown"
            self._contact_name_cache[contact_id] = name
        return self._contact_name_cache[contact_id]

    def get_article_number(self, item: dict[str, Any]) -> tuple[str, str | None]:
        """Resolves a sales-voucher lineItem's article id to (articleNumber,
        gtin), cached per client instance. If the article no longer exists
        (404 -- happens for old invoices whose article was since deleted in
        Lexware), tries the line item's own "articleNumber" field
        (undocumented, not always present) before falling back to a
        "(Artikel gelöscht) <name>" placeholder; gtin is None in that case,
        since it's not carried on the line item at all.
        """
        article_id = item["id"]
        if article_id not in self._article_cache:
            try:
                article = self.get(f"/articles/{article_id}")
                number = article.get("articleNumber") or article_id
                self._article_cache[article_id] = (number, article.get("gtin") or None)
            except niquests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 404:
                    raise
                fallback_number = item.get("articleNumber")
                name = item.get("name", "?")
                number = fallback_number if fallback_number else f"(Artikel gelöscht) {name}"
                self._article_cache[article_id] = (number, None)
        return self._article_cache[article_id]

    def deeplink(self, voucher_type: str, voucher_id: str) -> str:
        return f"{APP_BASE_URL}/permalink/{RESOURCE_INFO[voucher_type]}/view/{voucher_id}"

    def contact_deeplink(self, contact_id: str) -> str:
        return f"{APP_BASE_URL}/permalink/contacts/view/{contact_id}"


def extract_contact_id(voucher_detail: dict[str, Any]) -> str | None:
    return (voucher_detail.get("address", {}) or {}).get("contactId")


def extract_one_time_name(voucher_detail: dict[str, Any]) -> str:
    """Display name for one-time addresses (Einmalkunde), which have no
    contactId -- the name is entered directly on the voucher's address block.
    """
    return (voucher_detail.get("address", {}) or {}).get("name") or "Unknown"


def extract_related(voucher_detail: dict[str, Any]) -> list[dict[str, str]]:
    """All related vouchers (any type) from a voucher's own relatedVouchers
    list -- this is how Lexware links e.g. an order confirmation to the
    invoices/delivery notes/etc. created from it (there is no
    "precedingSalesVoucherId" field on the other side).
    """
    related = voucher_detail.get("relatedVouchers") or []
    return [r for r in related if r.get("id") and r.get("voucherType")]
