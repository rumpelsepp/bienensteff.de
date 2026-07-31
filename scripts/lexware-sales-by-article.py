#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.14"
# dependencies = ["httpx>=0.27", "polars>=1.0"]
# ///

"""
Sums the sold quantity per article number across all paid invoices
(Lexware Office), grouped by year (of the invoice's voucherDate), for e.g. a
GQ-Kontrolle.

Only invoices with voucherStatus == "paid" are counted (drafts, open,
overdue, voided invoices are ignored). Line items of type "material" or
"service" are attributed to their article's articleNumber (resolved via a
cached GET /articles/{id}); line items of type "custom" (free-text position
with a quantity but no article reference) are grouped under their own name
instead; type "text" (section headers, no quantity) is skipped.

If an article was since deleted in Lexware (GET /articles/{id} -> 404), the
line item itself is checked for an "articleNumber" field first (undocumented,
but seen on some responses) before falling back to grouping by the line
item's own name.

Grouping/summing is done with polars; the result is printed to stdout as
JSON: {"<year>": [{"artikelnummer", "bezeichnung", "gtin", "menge", "einheit"}, ...]}.
gtin is empty for line items without a resolvable article (custom positions,
or an article deleted from Lexware without a recoverable articleNumber).

Required environment variable: LEXWARE_API_KEY

Usage:
  uv run lexware-sales-by-article.py
  uv run lexware-sales-by-article.py --from 2026-01-01 --to 2026-12-31
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Iterator

import httpx
import polars as pl

LEXWARE_BASE = "https://api.lexware.io/v1"
MIN_INTERVAL = 0.6  # Lexware caps at 2 req/s; margin built in.


class LexwareClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.Client(
            base_url=LEXWARE_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=30.0,
        )
        self._last_call = 0.0

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        elapsed = time.monotonic() - self._last_call
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        resp = self._client.get(path, params=params)
        self._last_call = time.monotonic()
        if resp.status_code == 429:
            time.sleep(2.0)
            resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def paginate_voucherlist(self, voucher_type: str, page_size: int = 100) -> Iterator[dict[str, Any]]:
        """Paginates by requested vs. received page size rather than trusting
        a "totalPages"-style field in the response -- Lexware's pagination
        metadata has been seen to live under different/nested field names
        across API versions, which silently truncated results to just the
        first page when that field didn't match. A short page is the only
        reliable "this was the last page" signal.
        """
        page = 0
        while True:
            data = self.get(
                "/voucherlist",
                params={"voucherType": voucher_type, "voucherStatus": "any", "page": page, "size": page_size},
            )
            content = data.get("content", [])
            print(
                f"  page {page}: {len(content)} entries "
                f"(totalElements={data.get('totalElements')}, totalPages={data.get('totalPages')})",
                file=sys.stderr,
            )
            if not content:
                return
            yield from content
            if len(content) < page_size:
                return
            page += 1


def article_info(client: LexwareClient, item: dict[str, Any], cache: dict[str, tuple[str, str]]) -> tuple[str, str]:
    """Resolves a lineItem's article id to (articleNumber, gtin). If the
    article no longer exists (404 -- happens for old invoices whose article
    was since deleted in Lexware), tries the line item's own "articleNumber"
    field (undocumented, not always present) before falling back to grouping
    by the line item's own name; gtin is empty in that case, since it's not
    carried on the line item at all.
    """
    article_id = item["id"]
    if article_id not in cache:
        try:
            article = client.get(f"/articles/{article_id}")
            number = article.get("articleNumber") or article_id
            cache[article_id] = (number, article.get("gtin") or "")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            fallback_number = item.get("articleNumber")
            name = item.get("name", "?")
            number = fallback_number if fallback_number else f"(Artikel gelöscht) {name}"
            cache[article_id] = (number, "")
    return cache[article_id]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="only invoices on/after this date")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="only invoices on/before this date")
    args = parser.parse_args()

    api_key = os.environ.get("LEXWARE_API_KEY")
    if not api_key:
        print("ERROR: LEXWARE_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    client = LexwareClient(api_key)
    article_cache: dict[str, tuple[str, str]] = {}
    rows: list[dict[str, Any]] = []

    paid = [
        entry
        for entry in client.paginate_voucherlist("invoice")
        if entry.get("voucherStatus") == "paid"
        and (not args.date_from or (entry.get("voucherDate") or "") >= args.date_from)
        and (not args.date_to or (entry.get("voucherDate") or "") <= args.date_to)
    ]
    print(f"Found {len(paid)} paid invoice(s), fetching line items ...", file=sys.stderr)

    for entry in paid:
        year = (entry.get("voucherDate") or "")[:4] or "unbekannt"
        invoice = client.get(f"/invoices/{entry['id']}")
        for item in invoice.get("lineItems", []):
            item_type = item.get("type")
            quantity = item.get("quantity")
            if item_type not in ("material", "service", "custom") or quantity is None:
                continue
            item_name = item.get("name", "?")
            if item_type == "custom" or not item.get("id"):
                key, gtin = f"(ohne Artikelnummer) {item_name}", ""
            else:
                key, gtin = article_info(client, item, article_cache)

            rows.append(
                {
                    "jahr": year,
                    "artikelnummer": key,
                    "bezeichnung": item_name,
                    "gtin": gtin,
                    "menge": quantity,
                    "einheit": item.get("unitName") or "",
                }
            )

    if not rows:
        print(json.dumps({}))
        return

    grouped = (
        pl.DataFrame(rows)
        .group_by(["jahr", "artikelnummer"], maintain_order=True)
        .agg(
            pl.col("bezeichnung").first(),
            pl.col("gtin").first(),
            pl.col("einheit").first(),
            pl.col("menge").sum(),
        )
        .sort(["jahr", "artikelnummer"])
    )

    result: dict[str, list[dict[str, Any]]] = {}
    for year, group in grouped.group_by(["jahr"], maintain_order=True):
        result[year[0]] = group.drop("jahr").to_dicts()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
