"""
Sums the sold quantity per article number across all paid invoices
(Lexware Office), grouped by year (of the invoice's voucherDate), for e.g. a
GQ-Kontrolle.

Only invoices with voucherStatus == "paid" are counted (drafts, open,
overdue, voided invoices are ignored). Line items of type "material" or
"service" are attributed to their article's articleNumber (resolved via
LexwareClient.get_article_number()); line items of type "custom" (free-text
position with a quantity but no article reference) are grouped under their
own name instead; type "text" (section headers, no quantity) is skipped.

Grouping/summing is done with polars; the result is printed to stdout as
JSON: {"<year>": [{"artikelnummer", "bezeichnung", "gtin", "menge", "einheit"}, ...]}.
gtin is empty for line items without a resolvable article (custom positions,
or an article deleted from Lexware without a recoverable articleNumber, see
LexwareClient.get_article_number()).

Required environment variable: LEXWARE_API_KEY

Usage:
  lexware-sales-by-article
  lexware-sales-by-article --from 2026-01-01 --to 2026-12-31
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import polars as pl

from bstools.env import require_env_var
from bstools.lexware import LexwareClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="only invoices on/after this date")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="only invoices on/before this date")
    args = parser.parse_args()

    client = LexwareClient(require_env_var("LEXWARE_API_KEY"))
    rows: list[dict[str, Any]] = []

    # Always send an explicit voucherDateFrom, even when the user didn't ask
    # for one -- rules out any undocumented default date window /voucherlist
    # might otherwise apply when no date filter is given at all. 2000-01-01
    # predates any plausible Lexware account. voucherDateTo is only sent
    # when the user actually asked for an upper bound.
    api_date_params: dict[str, str] = {"voucherDateFrom": args.date_from or "2000-01-01"}
    if args.date_to:
        api_date_params["voucherDateTo"] = args.date_to
    print(f"Querying /voucherlist with {api_date_params} ...", file=sys.stderr)

    paid = [
        entry
        for entry in client.paginate_voucherlist("invoice", **api_date_params)
        if entry.get("voucherStatus") == "paid"
        and (not args.date_from or (entry.get("voucherDate") or "") >= args.date_from)
        and (not args.date_to or (entry.get("voucherDate") or "") <= args.date_to)
    ]
    print(f"Found {len(paid)} paid invoice(s), fetching line items ...", file=sys.stderr)

    # Down-payment invoices (Abschlagsrechnungen) are a separate voucherType
    # in Lexware, not included in the "invoice" query above -- a common
    # source of "why is my count lower than what I see in Lexware" surprises.
    # Just a heads-up for now: their line items aren't verified to have the
    # same shape as regular invoices, so they're not folded into the report
    # yet, only counted here.
    dpi_count = sum(1 for _ in client.paginate_voucherlist("downpaymentinvoice"))
    if dpi_count:
        print(
            f"NOTE: {dpi_count} Abschlagsrechnung(en) (down-payment invoices) exist "
            f"in Lexware but are NOT included in this report -- they're a separate "
            f"voucherType. Say the word if these should count too.",
            file=sys.stderr,
        )

    for entry in paid:
        year = (entry.get("voucherDate") or "")[:4] or "unbekannt"
        invoice = client.get_voucher_detail("invoice", entry["id"])
        for item in invoice.get("lineItems", []):
            item_type = item.get("type")
            quantity = item.get("quantity")
            if item_type not in ("material", "service", "custom") or quantity is None:
                continue
            item_name = item.get("name", "?")
            if item_type == "custom" or not item.get("id"):
                key, gtin = f"(ohne Artikelnummer) {item_name}", ""
            else:
                key, gtin = client.get_article_number(item)

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
