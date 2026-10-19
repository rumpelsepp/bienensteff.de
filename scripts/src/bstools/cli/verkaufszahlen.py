"""
Lexware Office reports, plus the cash sales recorded in Grist, in one JSON,
grouped by year:

1. "artikel": sold quantity per article number across all paid invoices
   and all cash sales (for e.g. a GQ-Kontrolle), split into
   "menge_rechnung" and "menge_bar" next to the total "menge". Only invoices with voucherStatus == "paid"
   are counted (drafts, open, overdue, voided invoices are ignored). Line
   items of type "material" or "service" are attributed to their article's
   articleNumber (resolved via LexwareClient.get_article_number()); line
   items of type "custom" (free-text position with a quantity but no
   article reference) are grouped under their own name instead; type
   "text" (section headers, no quantity) is skipped. gtin is null for
   line items without a resolvable article (custom positions, or an
   article deleted from Lexware without a recoverable articleNumber).

2. "einnahmen_ausgaben": per-year totalAmount of the same paid invoices as
   the "artikel" report (already fetched, no extra API calls), the cash
   and the non-cash (Wero/SEPA) takings of the box from Grist, and their
   sum -- a plain income overview (e.g. for
   the Kleinunternehmer limits), NOT a profit calculation.

   Manually recorded bookkeeping vouchers ("Belege", GET /v1/vouchers) were
   meant to be folded in here too (income AND expenses), but that endpoint
   turned out to be a dead end: it 400s with "voucherNumber parameter is
   required" when called without one, i.e. it can only look up one already-
   known voucher by number, not list/enumerate all of them -- there is no
   way to discover and sum "all Belege" via the public API. Left out until
   Lexware offers an actual list endpoint for this.

   Depreciation (Abschreibungen) is deliberately out of scope regardless --
   it isn't a dated voucher amount you can sum, but a periodic accounting
   figure (AfA tables, useful life, acquisition cost) that belongs to a
   real BWA or your Steuerberater.

3. "barbelege": per year, one entry per cash receipt number from Grist,
   with its date, source, counted cash (betrag), non-cash payments (unbar),
   their sum (beleg_betrag -- the amount of the voucher with that number in
   Lexware, to check against), expected amount (soll), shortfall
   (fehlbetrag) and number of items.

Cash sales (Grist tables "Box_Leerungen" and "Box_Bestand", hardcoded, read
only; set up by hand in Grist, --init only checks their columns): cash sold
without an invoice, e.g. from the honesty box in the woods, is booked in
Lexware as a plain voucher without line items, so Lexware cannot say
which articles left. Both tables follow the paper Kassenbericht:
  - Box_Leerungen, one row per emptying (= one Kassenbericht = one voucher
    in Lexware, over cash plus Wero/SEPA; the cash is assigned to it via
    the cash register, the Wero/SEPA payments from the bank account):
    Belegnummer ("BV-014", BV = Barverkauf: one running number across all
    boxes, the same as on the voucher in Lexware -- this is what ties the
    two together), Datum, Quelle (formula: the name of the box, from the
    reference Box to the table Boxen), Betrag (labelled "Bargeld in der
    Box": counted cash), Unbar (labelled "unbar": sum of the Wero/SEPA payments
    with the box's reference since its previous emptying, as written on the
    Kassenbericht), Soll and
    Fehlbetrag (formulas: Soll from the article rows, Fehlbetrag = Soll -
    Betrag - Unbar; the shortfall is not income and is only reported,
    never added up as such).
  - Box_Bestand, one row per emptying and article: Leerung (reference to
    the emptying), Artikel (reference to Artikel), Gezaehlt and
    Aufgefuellt_auf (entered), Weg (formula: what the previous emptying
    filled the box up to, minus what was counted now -- stolen jars
    included, since for the GQ check every jar that left counts, paid or
    not) and Article_Number (formula, Artikel.sku = Lexware articleNumber;
    GTIN, description and unit are looked up in Lexware by it).
The date window applies to the emptying's date; article rows follow their
emptying.
Invoices made out for cash payments (receipts for customers who want one)
are regular Lexware invoices with line items, so they are counted from
Lexware and must not be entered here as well.

Grist sync (table "Verkaufszahlen", hardcoded -- this script feeds exactly
one table, unlike bestellungen's generic GRIST_TABLE_ID): every normal run
also upserts the "artikel" rows into Grist, keyed on (Year, Article_Number),
with Quantity_Invoices and Quantity_Cash next to the total Quantity.
The upserted Quantity is the FULL sum for that year recomputed from this
run's fetch, not a delta -- so only years that this run's --from/--to window
covers completely (from on/before Jan 1 through on/after Dec 31, or through
"today" for the still-running current year) are synced. A narrower window
(e.g. a single month) would only see a fraction of the year's invoices and
would silently overwrite a previous full-year total with that fraction, so
such incomplete years are computed for the JSON report but skipped for
Grist. Cash sales are cut to the same --from/--to window as the invoices (see is_year_complete()/build_grist_rows()). Rows whose voucherDate
was missing (year bucket "unbekannt") are likewise never synced, since that
bucket can silently merge quantities from otherwise-unrelated invoices --
it only ever shows up in the JSON report. Only articles with a resolvable
GTIN are uploaded -- rows without one (custom/free-text positions, or an
article deleted from Lexware without a recoverable GTIN) are left out of
Grist entirely, though they still show up in the JSON report on stdout as
before. "einnahmen_ausgaben" is not synced -- it isn't per-article data, so
it doesn't fit this table.

Required environment variables:
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli verkaufszahlen --init [--dry-run]   # create/update the Grist tables
  bscli verkaufszahlen
  bscli verkaufszahlen --from 2026-01-01 --to 2026-12-31
  bscli verkaufszahlen --dry-run
"""

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

lazy import polars as pl

from bstools.env import require_env
from bstools.grist import GristClient, changed_fields
from bstools.lexware import LexwareClient
from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# This script feeds exactly one Grist table, unlike bestellungen's generic
# GRIST_TABLE_ID -- so the table name is a constant here, not an env var.
GRIST_TABLE_ID = "Verkaufszahlen"
# Entered by hand, only read here -- see the module docstring. Both are set
# up in Grist (references, formulas), so --init only checks that the columns
# read below exist.
BOX_TABLE_ID = "Box_Leerungen"
BOX_COLUMNS = ["Belegnummer", "Datum", "Quelle", "Betrag", "Unbar", "Soll", "Fehlbetrag"]
BOX_ITEMS_TABLE_ID = "Box_Bestand"
BOX_ITEMS_COLUMNS = ["Leerung", "Article_Number", "Weg"]

GRIST_ENV = ["GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID"]
REQUIRED_ENV = ["LEXWARE_API_KEY"] + GRIST_ENV

# Columns this script needs, in creation order -- see bestellungen.py's
# GRIST_SCHEMA for the general shape. Year is Text, not Numeric/Date: rows
# with an unresolvable voucherDate fall back to "unbekannt" (see main()),
# which wouldn't fit either of those types. GTIN is Text too, to preserve it
# verbatim rather than risk it being read back as a mangled number.
GRIST_SCHEMA: list[tuple[str, str, dict[str, Any] | None]] = [
    ("Year", "Text", None),
    ("Article_Number", "Text", None),
    ("Description", "Text", None),
    ("GTIN", "Text", None),
    ("Unit", "Text", None),
    ("Quantity", "Numeric", None),
    ("Quantity_Invoices", "Numeric", None),
    ("Quantity_Cash", "Numeric", None),
    ("Last_Synced", "Text", None),
]

# Short version of the module docstring above, for --help -- the full one is
# too long to dump on a terminal usefully. Keep in sync by hand; it's meant
# to stay a stable summary, not track every detail of the long version.
CLI_HELP = """Lexware Office reports plus the cash sales from the Grist tables
"Box_Leerungen"/"Box_Bestand", in one JSON, grouped by year: "artikel" (sold quantity per
article number across paid invoices and cash sales, e.g. for a
GQ-Kontrolle), "einnahmen_ausgaben" (per-year paid-invoice revenue and cash
takings -- a plain income overview, not a profit calculation; manual
bookkeeping vouchers and depreciation are deliberately not included, see
the module docstring in the source for why) and "barbelege" (cash takings
per receipt number, to check against Lexware).

Also upserts the "artikel" rows (GTIN required) into the Grist table
"Verkaufszahlen"; see the module docstring for the sync/key details.

Required environment variables:
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli verkaufszahlen --init [--dry-run]   # create/update the Grist tables
  bscli verkaufszahlen
  bscli verkaufszahlen --from 2026-01-01 --to 2026-12-31
  bscli verkaufszahlen --dry-run"""


def build_grouped_df(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """One row per (jahr, artikelnummer): bezeichnung/gtin/einheit (first
    seen), menge (summed) and its split by quelle ("rechnung"/"bar") into
    menge_rechnung/menge_bar -- the shared aggregation behind both
    build_article_report() (JSON, grouped by year) and build_grist_rows()
    (flat, GTIN-filtered).
    """
    if not rows:
        return pl.DataFrame(
            schema={
                "jahr": pl.Utf8,
                "artikelnummer": pl.Utf8,
                "bezeichnung": pl.Utf8,
                "gtin": pl.Utf8,
                "einheit": pl.Utf8,
                "menge": pl.Float64,
                "menge_rechnung": pl.Float64,
                "menge_bar": pl.Float64,
            }
        )
    return (
        pl.DataFrame(rows)
        .group_by(["jahr", "artikelnummer"], maintain_order=True)
        .agg(
            pl.col("bezeichnung").first(),
            pl.col("gtin").first(),
            pl.col("einheit").first(),
            pl.col("menge").sum(),
            pl.col("menge").filter(pl.col("quelle") == "rechnung").sum().alias("menge_rechnung"),
            pl.col("menge").filter(pl.col("quelle") == "bar").sum().alias("menge_bar"),
        )
        .sort(["jahr", "artikelnummer"])
    )


def build_article_report(df: pl.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if df.is_empty():
        return {}

    result: dict[str, list[dict[str, Any]]] = {}
    for year, group in df.group_by(["jahr"], maintain_order=True):
        result[year[0]] = group.drop("jahr").to_dicts()
    return result


def is_year_complete(year: str, date_from: str | None, date_to: str | None, today: str) -> bool:
    """Whether this run's --from/--to window covers ALL of `year`, i.e.
    whether it's safe to upsert that year's summed Quantity into Grist
    without silently shrinking a previously-synced full-year total (see the
    module docstring's Grist sync section). `year` is the "jahr" bucket, so
    the literal "unbekannt" fallback is always incomplete -- there is no
    real year to compare against, and lumping unrelated invoices under one
    key is exactly what must never reach Grist.
    """
    if not year.isdigit():
        return False
    effective_from = date_from or "2000-01-01"
    effective_to = date_to or today
    year_start, year_end = f"{year}-01-01", f"{year}-12-31"
    if effective_from > year_start:
        return False
    # A year still in progress (year_end is in the future) can only be
    # "complete" up through today -- there's no Dec-31 data to require yet.
    return effective_to >= (min(year_end, today))


def build_grist_rows(
    df: pl.DataFrame, date_from: str | None, date_to: str | None, today: str
) -> list[dict[str, Any]]:
    """Flat (jahr, artikelnummer, bezeichnung, gtin, einheit, menge) rows for
    the Grist sync -- only articles with a resolvable GTIN, per user request,
    and only for years this run's date window covers completely (see
    is_year_complete()). Rows filtered out here still show up in the JSON
    report on stdout as before.
    """
    if df.is_empty():
        return []
    return (
        df.filter(pl.col("gtin").is_not_null())
        .filter(
            pl.col("jahr").map_elements(
                lambda year: is_year_complete(year, date_from, date_to, today),
                return_dtype=pl.Boolean,
            )
        )
        .to_dicts()
    )


def run_init(grist: GristClient, dry_run: bool) -> None:
    grist.ensure_table_schema(GRIST_TABLE_ID, GRIST_SCHEMA, dry_run)
    tables = grist.list_tables()
    for table_id, columns in (
        (BOX_TABLE_ID, BOX_COLUMNS),
        (BOX_ITEMS_TABLE_ID, BOX_ITEMS_COLUMNS),
    ):
        if table_id not in tables:
            logger.warning("Grist table '%s' does not exist -- set it up in Grist.", table_id)
            continue
        missing = [c for c in columns if c not in grist.get_columns(table_id)]
        if missing:
            logger.warning("Grist table '%s' lacks column(s) %s.", table_id, ", ".join(missing))
        else:
            print(f"Grist '{table_id}': all columns this script reads are there.")


def epoch_to_date(value: Any) -> str | None:
    """Grist Date cell (Unix seconds, UTC midnight) -> "YYYY-MM-DD"."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d")


def cell_number(value: Any) -> float | None:
    """A Numeric/Int cell as a number; None for empty cells and for formula
    errors, which the API sends as a list like ["E", "TypeError"].
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return value


def fetch_cash_sales(
    grist: GristClient,
    client: LexwareClient,
    date_from: str | None,
    date_to: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Reads Box_Leerungen and Box_Bestand (see the module docstring), the
    emptyings within --from/--to and their article rows. Returns (article
    rows in the same shape as the invoice line items, with quelle "bar";
    one entry per emptying with its date/year/source/receipt/amount/
    non-cash amount/expected amount/shortfall/quantity, for the income and per-receipt
    reports).

    A missing table is only a warning (nothing recorded yet); rows that
    cannot be placed -- an emptying without a date, an article row without
    an article, a formula error or a negative Weg -- are skipped with a
    warning, since guessing would put them into the wrong year or nowhere
    visible.
    """
    tables = grist.list_tables()
    missing = [t for t in (BOX_TABLE_ID, BOX_ITEMS_TABLE_ID) if t not in tables]
    if missing:
        logger.warning("Grist table(s) %s do not exist, no cash sales counted.", ", ".join(missing))
        return [], []

    # Grist row id of the emptying -> its entry, for the article rows below.
    emptyings: dict[int, dict[str, Any]] = {}
    for rec in grist.get_records(BOX_TABLE_ID):
        fields = rec.get("fields", {})
        date = epoch_to_date(fields.get("Datum"))
        amount = cell_number(fields.get("Betrag")) or 0
        non_cash = cell_number(fields.get("Unbar")) or 0
        if not date:
            if amount or non_cash:
                logger.warning("%s row %s has no date, skipped.", BOX_TABLE_ID, rec["id"])
            continue
        if (date_from and date < date_from) or (date_to and date > date_to):
            continue
        receipt = (fields.get("Belegnummer") or "").strip()
        if not receipt:
            receipt = f"(ohne Belegnummer) {date}"
            logger.warning(
                "%s row %s has no Belegnummer -- it can't be matched with Lexware.",
                BOX_TABLE_ID,
                rec["id"],
            )
        emptyings[rec["id"]] = {
            "jahr": date[:4],
            "datum": date,
            "quelle": fields.get("Quelle") or "",
            "beleg": receipt,
            "betrag": amount,
            "unbar": non_cash,
            "soll": cell_number(fields.get("Soll")) or 0,
            "fehlbetrag": cell_number(fields.get("Fehlbetrag")) or 0,
            "menge": 0,
        }

    articles: dict[str, dict[str, Any]] | None = None
    article_rows: list[dict[str, Any]] = []
    for rec in grist.get_records(BOX_ITEMS_TABLE_ID):
        fields = rec.get("fields", {})
        # Outside the date window, or an emptying without a date (warned above).
        emptying = emptyings.get(fields.get("Leerung") or 0)
        if emptying is None:
            continue
        quantity = cell_number(fields.get("Weg"))
        number = (fields.get("Article_Number") or "").strip()
        if quantity is None or quantity < 0:
            logger.warning(
                "%s row %s (%s): Weg is %r -- check the counts, row skipped.",
                BOX_ITEMS_TABLE_ID,
                rec["id"],
                emptying["beleg"],
                fields.get("Weg"),
            )
            continue
        if not quantity:
            continue
        if not number:
            logger.warning(
                "%s row %s (%s) has no article, quantity skipped.",
                BOX_ITEMS_TABLE_ID,
                rec["id"],
                emptying["beleg"],
            )
            continue
        emptying["menge"] += quantity

        if articles is None:
            articles = client.index_articles_by_number()
        article = articles.get(number)
        if article is None:
            logger.warning(
                "%s row %s: article number %r not found in Lexware -- counted in the "
                "JSON report, but without a GTIN, so not synced to '%s'.",
                BOX_ITEMS_TABLE_ID,
                rec["id"],
                number,
                GRIST_TABLE_ID,
            )
        year = emptying["jahr"]
        article_rows.append(
            {
                "jahr": year,
                "artikelnummer": number,
                "bezeichnung": (article or {}).get("title") or number,
                "gtin": (article or {}).get("gtin") or None,
                "menge": quantity,
                "einheit": (article or {}).get("unitName") or "",
                "quelle": "bar",
            }
        )
    return article_rows, list(emptyings.values())


def build_receipt_report(cash_entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per year, one entry per receipt number: date (earliest), source,
    summed cash, non-cash and voucher amount, expected amount, shortfall
    and quantity -- to check against Lexware's vouchers. Normally one emptying per receipt
    number; a number used twice shows up summed, under one entry.
    """
    if not cash_entries:
        return {}
    df = (
        pl.DataFrame(cash_entries)
        .group_by(["jahr", "beleg"], maintain_order=True)
        .agg(
            pl.col("datum").min(),
            pl.col("quelle").first(),
            pl.col("betrag").sum().round(2),
            pl.col("unbar").sum().round(2),
            (pl.col("betrag") + pl.col("unbar")).sum().round(2).alias("beleg_betrag"),
            pl.col("soll").sum().round(2),
            pl.col("fehlbetrag").sum().round(2),
            pl.col("menge").sum(),
        )
        .sort(["jahr", "datum", "beleg"])
    )
    result: dict[str, list[dict[str, Any]]] = {}
    for year, group in df.group_by(["jahr"], maintain_order=True):
        result[year[0]] = group.drop("jahr").to_dicts()
    return result


def fetch_existing_grist(
    grist: GristClient,
) -> dict[tuple[str, str], tuple[int, dict[str, Any]]]:
    """(Year, Article_Number) -> (Grist row id, row fields), for upserting
    only rows that actually changed, instead of a
    full wipe-and-reinsert -- a partial --from/--to run must only ever touch
    the years it actually fetched, never delete other years' rows a previous
    full run already put there (unlike bestellungen's fully-derived _Docs
    table, which has no such partial-run concern).
    """
    existing: dict[tuple[str, str], tuple[int, dict[str, Any]]] = {}
    for rec in grist.get_records(GRIST_TABLE_ID):
        fields = rec.get("fields", {})
        year, number = fields.get("Year"), fields.get("Article_Number")
        if year and number:
            existing[(year, number)] = (rec["id"], fields)
    return existing


def sync_sales_to_grist(
    grist: GristClient, grist_rows: list[dict[str, Any]], dry_run: bool
) -> None:
    existing = fetch_existing_grist(grist)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    to_add: list[dict[str, Any]] = []
    to_update: list[tuple[int, dict[str, Any]]] = []

    for row in grist_rows:
        fields = {
            "Year": row["jahr"],
            "Article_Number": row["artikelnummer"],
            "Description": row["bezeichnung"],
            "GTIN": row["gtin"],
            "Unit": row["einheit"],
            "Quantity": row["menge"],
            "Quantity_Invoices": row["menge_rechnung"],
            "Quantity_Cash": row["menge_bar"],
        }
        key = (row["jahr"], row["artikelnummer"])
        if key not in existing:
            to_add.append({**fields, "Last_Synced": now_iso})
            continue
        row_id, old_fields = existing[key]
        # Last_Synced only on rows that actually changed, so an unchanged
        # run doesn't rewrite every row just for a fresh timestamp.
        changed = changed_fields(fields, old_fields)
        if changed:
            to_update.append((row_id, {**changed, "Last_Synced": now_iso}))

    unchanged = len(grist_rows) - len(to_add) - len(to_update)
    print(
        f"Grist '{GRIST_TABLE_ID}': new {len(to_add)}, updated {len(to_update)}, "
        f"unchanged {unchanged} "
        f"(articles without a GTIN are not synced, see module docstring)."
    )
    if dry_run:
        print("--dry-run is set, nothing will be written to Grist.")
        return
    grist.add_records(GRIST_TABLE_ID, to_add)
    grist.update_records(GRIST_TABLE_ID, to_update)


def main(argv: list[str] | None = None, prog: str | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog=prog, description=CLI_HELP, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        metavar="YYYY-MM-DD",
        help="only invoices/cash sales on/after this date",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        metavar="YYYY-MM-DD",
        help="only invoices/cash sales on/before this date",
    )
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")
    parser.add_argument("--dry-run", action="store_true", help="don't write anything to Grist")
    parser.add_argument(
        "--init", action="store_true", help="create/update the Grist table, then exit"
    )
    args = parser.parse_args(argv)
    setup_logging(debug=args.debug)

    if args.init:
        cfg = require_env(*GRIST_ENV)
        grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
        run_init(grist, dry_run=args.dry_run)
        return

    cfg = require_env(*REQUIRED_ENV)
    client = LexwareClient(cfg["LEXWARE_API_KEY"])
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    rows: list[dict[str, Any]] = []
    invoice_revenue_by_year: dict[str, float] = {}

    # Always send an explicit voucherDateFrom, even when the user didn't ask
    # for one -- rules out any undocumented default date window /voucherlist
    # might otherwise apply when no date filter is given at all. 2000-01-01
    # predates any plausible Lexware account. voucherDateTo is only sent
    # when the user actually asked for an upper bound.
    api_date_params: dict[str, str] = {"voucherDateFrom": args.date_from or "2000-01-01"}
    if args.date_to:
        api_date_params["voucherDateTo"] = args.date_to
    logger.info("Querying /voucherlist with %s ...", api_date_params)

    paid = [
        entry
        for entry in client.paginate_voucherlist("invoice", extra_params=api_date_params)
        if entry.get("voucherStatus") == "paid"
        and (not args.date_from or (entry.get("voucherDate") or "") >= args.date_from)
        and (not args.date_to or (entry.get("voucherDate") or "") <= args.date_to)
    ]
    logger.info("Found %s paid invoice(s), fetching line items ...", len(paid))

    # Down-payment invoices (Abschlagsrechnungen) are a separate voucherType
    # in Lexware, not included in the "invoice" query above -- a common
    # source of "why is my count lower than what I see in Lexware" surprises.
    # Just a heads-up for now: their line items aren't verified to have the
    # same shape as regular invoices, so they're not folded into the report
    # yet, only counted here.
    dpi_count = sum(1 for _ in client.paginate_voucherlist("downpaymentinvoice"))
    if dpi_count:
        logger.warning(
            "%s Abschlagsrechnung(en) (down-payment invoices) exist in Lexware but are "
            "NOT included in this report -- they're a separate voucherType. Say the word "
            "if these should count too.",
            dpi_count,
        )

    for entry in paid:
        year = (entry.get("voucherDate") or "")[:4] or "unbekannt"
        invoice_revenue_by_year[year] = invoice_revenue_by_year.get(year, 0.0) + (
            entry.get("totalAmount") or 0
        )

        invoice = client.get_voucher_detail("invoice", entry["id"])
        for item in invoice.get("lineItems", []):
            item_type = item.get("type")
            quantity = item.get("quantity")
            if item_type not in ("material", "service", "custom") or quantity is None:
                continue
            item_name = item.get("name", "?")
            if item_type == "custom" or not item.get("id"):
                key, gtin = f"(ohne Artikelnummer) {item_name}", None
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
                    "quelle": "rechnung",
                }
            )

    cash_rows, cash_entries = fetch_cash_sales(grist, client, args.date_from, args.date_to)
    rows.extend(cash_rows)
    logger.info(
        "Found %s emptying(s) in Grist '%s' in the date window.",
        len(cash_entries),
        BOX_TABLE_ID,
    )
    cash_by_year: dict[str, float] = {}
    non_cash_by_year: dict[str, float] = {}
    for entry in cash_entries:
        year = entry["jahr"]
        cash_by_year[year] = cash_by_year.get(year, 0.0) + entry["betrag"]
        non_cash_by_year[year] = non_cash_by_year.get(year, 0.0) + entry["unbar"]

    einnahmen_ausgaben: dict[str, dict[str, float]] = {}
    for year in sorted(invoice_revenue_by_year.keys() | cash_by_year.keys()):
        from_invoices = invoice_revenue_by_year.get(year, 0.0)
        cash = cash_by_year.get(year, 0.0)
        non_cash = non_cash_by_year.get(year, 0.0)
        einnahmen_ausgaben[year] = {
            "einnahmen_rechnungen": round(from_invoices, 2),
            "einnahmen_bar": round(cash, 2),
            "einnahmen_box_unbar": round(non_cash, 2),
            "einnahmen_gesamt": round(from_invoices + cash + non_cash, 2),
        }

    df = build_grouped_df(rows)
    result = {
        "artikel": build_article_report(df),
        "einnahmen_ausgaben": einnahmen_ausgaben,
        "barbelege": build_receipt_report(cash_entries),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    today = time.strftime("%Y-%m-%d")
    incomplete_years = sorted(
        year
        for year in df["jahr"].unique().to_list()
        if not is_year_complete(year, args.date_from, args.date_to, today)
    )
    if incomplete_years:
        logger.warning(
            "year(s) %s are not fully covered by --from/--to (or have an unresolvable "
            "voucherDate) and are therefore NOT synced to Grist this run, to avoid "
            "overwriting a full-year total with a partial one -- see the module docstring.",
            ", ".join(incomplete_years),
        )

    sync_sales_to_grist(
        grist, build_grist_rows(df, args.date_from, args.date_to, today), dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
