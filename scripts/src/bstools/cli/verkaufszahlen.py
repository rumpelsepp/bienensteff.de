"""
Sales report per year as PDF (templates/verkaufszahlen.typ; with --json
also as JSON on stdout): paid Lexware invoices plus the honesty boxes
recorded in Grist. Per year:

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
only; set up by hand in Grist, nothing written there): cash sold
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

A year that the --from/--to window does not cover completely is marked as
such in the PDF -- its numbers are then only a part of the year.

Settings (environment variable, or config file -- see bscli.example.toml):
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli verkaufszahlen                                   # the current year
  bscli verkaufszahlen --year 2025                      # Verkaufszahlen_2025.pdf
  bscli verkaufszahlen --year 2024 2026                 # 2024 to 2026
  bscli verkaufszahlen --year 2026 --gqb only -o gq-kontrolle-2026.pdf
  bscli verkaufszahlen --from 2026-04-01 --to 2026-09-30
  bscli verkaufszahlen --from 2026-01-01 --json > verkaufszahlen.json
"""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

lazy import polars as pl

from bstools.env import require_env
from bstools.grist import GristClient
from bstools.lexware import LexwareClient
from bstools.logging_setup import setup_logging
from bstools.pdf import add_print_arguments, count, eur, german_date, letterhead, render

logger = logging.getLogger(__name__)

# Entered by hand in Grist, only read here -- see the module docstring.
BOX_TABLE_ID = "Box_Leerungen"
BOX_ITEMS_TABLE_ID = "Box_Bestand"

GRIST_ENV = ["GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID"]
REQUIRED_ENV = ["LEXWARE_API_KEY"] + GRIST_ENV

# Short version of the module docstring above, for --help -- the full one is
# too long to dump on a terminal usefully. Keep in sync by hand; it's meant
# to stay a stable summary, not track every detail of the long version.
CLI_HELP = """Sales report per year as PDF -- paid Lexware invoices plus the honesty
boxes from the Grist tables "Box_Leerungen"/"Box_Bestand": sold quantity per
article, split into invoices and boxes (e.g. for the GQ-Kontrolle), income
(invoices, boxes cash and non-cash) and the Kassenberichte of the boxes.
A plain income overview, not a profit calculation; see the module docstring
in the source for what is deliberately left out.

Settings (environment variable, or config file -- see bscli.example.toml):
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli verkaufszahlen                                   # the current year
  bscli verkaufszahlen --year 2025                      # Verkaufszahlen_2025.pdf
  bscli verkaufszahlen --year 2024 2026                 # 2024 to 2026
  bscli verkaufszahlen --year 2026 --gqb only -o gq-kontrolle-2026.pdf
  bscli verkaufszahlen --from 2026-04-01 --to 2026-09-30
  bscli verkaufszahlen --from 2026-01-01 --json > verkaufszahlen.json"""


def build_grouped_df(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """One row per (jahr, artikelnummer): bezeichnung/gtin/einheit (first
    seen), menge (summed) and its split by quelle ("rechnung"/"bar") into
    menge_rechnung/menge_bar -- the aggregation behind build_article_report().
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
    """Whether this run's --from/--to window covers ALL of `year` -- if not,
    the PDF marks that year's numbers as a part of it. `year` is the "jahr"
    bucket, so the literal "unbekannt" fallback (invoices without a date) is
    never complete.
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
                "%s row %s: article number %r not found in Lexware -- counted, "
                "but without GTIN, description and unit.",
                BOX_ITEMS_TABLE_ID,
                rec["id"],
                number,
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


GQB_FILTERS = {
    "only": "nur GQB-zertifizierte Artikel",
    "exclude": "nur Artikel ohne GQB-Zertifizierung",
}


def article_details(grist: GristClient) -> dict[str, tuple[bool, int]]:
    """Article number (Artikel.sku = Lexware articleNumber) -> (GQB
    certified, packaging unit), from the Grist table Verkaufdetails. The
    packaging unit is the number of jars per sold unit, e.g. 12 for a box of
    12 -- what the GQ check counts are jars.
    """
    rows = grist.query_sql(
        "SELECT a.sku AS sku, v.gqb_certified AS gqb, v.packaging_unit AS vpe "
        "FROM Verkaufdetails v JOIN Artikel a ON v.sku = a.id"
    )
    return {r["sku"]: (bool(r["gqb"]), int(r["vpe"]) if r["vpe"] else 1) for r in rows if r["sku"]}


def add_gqb(
    articles: dict[str, list[dict[str, Any]]],
    details: dict[str, tuple[bool, int]],
    gqb_filter: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Adds gqb, vpe and glaeser (jars: quantity x packaging unit, for units
    counted in pieces) to every article row, and keeps only GQB-certified
    ("only") or only uncertified ("exclude") articles if asked. An article
    missing from Verkaufdetails (e.g. a free-text invoice position) counts
    as not certified.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for year, rows in articles.items():
        kept = []
        for a in rows:
            gqb, vpe = details.get(a["artikelnummer"], (False, 1))
            if (gqb_filter == "only" and not gqb) or (gqb_filter == "exclude" and gqb):
                continue
            pieces = (a["einheit"] or "").lower().startswith("st")
            kept.append(
                {**a, "gqb": gqb, "vpe": vpe, "glaeser": a["menge"] * vpe if pieces else None}
            )
        out[year] = kept
    return out


def loose_label(unit: str) -> str:
    """Label of the total of articles not counted in jars: a weight is
    summed as such; "pauschal" (a lump sum, e.g. "Honig (pauschal)") has no
    quantity of its own, only the number of such invoice positions."""
    if unit.lower() == "pauschal":
        return "Pauschal berechnet (Anzahl Positionen, keine Gläser)"
    return f"Summe in {unit}" if unit else "Summe ohne Einheit"


def article_group(title: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """One table of the PDF: its rows and the totals below it (jars; kg of
    loose honey separately, since those are no jars)."""
    jars = sum(a["glaeser"] for a in rows if a["glaeser"] is not None)
    loose = [a for a in rows if a["glaeser"] is None]
    summen = [{"label": "Summe Gläser", "wert": count(jars)}]
    for unit in sorted({a["einheit"] for a in loose}):
        total = sum(a["menge"] for a in loose if a["einheit"] == unit)
        summen.append({"label": loose_label(unit), "wert": count(total)})
    return {
        "titel": title,
        "artikel": [
            {
                # Free-text invoice positions carry their name as key, see run().
                "nr": "–" if a["artikelnummer"].startswith("(") else a["artikelnummer"],
                "bezeichnung": a["bezeichnung"],
                "gtin": a["gtin"] or "",
                "einheit": a["einheit"],
                "vpe": count(a["vpe"]) if a["vpe"] != 1 else "",
                "rechnung": count(a["menge_rechnung"]),
                "box": count(a["menge_bar"]),
                "gesamt": count(a["menge"]),
                "glaeser": count(a["glaeser"]),
            }
            for a in rows
        ],
        "summen": summen,
    }


def pdf_data(
    result: dict[str, Any],
    date_from: str | None,
    date_to: str | None,
    today: str,
    gqb_filter: str | None = None,
) -> dict[str, Any]:
    """The report, formatted for templates/verkaufszahlen.typ: one entry per
    year, newest first, with a note when the --from/--to window does not
    cover the whole year (the numbers are then a part of it). Articles come
    in two tables, GQB-certified and not; with a GQB filter only the
    matching one, and without income and box vouchers -- those are not per
    article, so a filter cannot apply to them.
    """
    start = german_date(date_from) if date_from else "Beginn"
    zeitraum = f"{start} – {german_date(date_to or today)}"
    years = sorted(
        result["artikel"].keys() | result["einnahmen_ausgaben"].keys() | result["barbelege"].keys(),
        reverse=True,
    )
    jahre = []
    for year in years:
        if not year.isdigit():
            hinweis = "Rechnungen ohne Datum, keinem Jahr zuzuordnen."
        elif not is_year_complete(year, date_from, date_to, today):
            hinweis = f"Nur ein Teil des Jahres: Zeitraum {zeitraum}."
        elif year == today[:4]:
            hinweis = f"Laufendes Jahr, Stand {german_date(today)}."
        else:
            hinweis = ""
        income = result["einnahmen_ausgaben"].get(year, {})
        articles = result["artikel"].get(year, [])
        jahre.append(
            {
                "jahr": year,
                "hinweis": hinweis,
                "gruppen": [
                    article_group(title, rows)
                    for title, rows in (
                        ("GQB-zertifiziert", [a for a in articles if a["gqb"]]),
                        ("Nicht GQB-zertifiziert", [a for a in articles if not a["gqb"]]),
                    )
                    if rows
                ],
                # Sources without income that year are left out; the total stays.
                "einnahmen": [
                    {"quelle": label, "betrag": eur(income[key])}
                    for key, label in (
                        ("einnahmen_rechnungen", "Rechnungen (bezahlt)"),
                        ("einnahmen_bar", "Boxen, bar"),
                        ("einnahmen_box_unbar", "Boxen, unbar"),
                    )
                    if income.get(key)
                ],
                "einnahmen_gesamt": eur(income.get("einnahmen_gesamt", 0.0)),
                "barbelege": [
                    {
                        "beleg": b["beleg"],
                        "datum": german_date(b["datum"]),
                        "box": b["quelle"],
                        "bar": eur(b["betrag"]),
                        "unbar": eur(b["unbar"]),
                        "beleg_betrag": eur(b["beleg_betrag"]),
                        "soll": eur(b["soll"]),
                        "fehlbetrag": eur(b["fehlbetrag"]),
                    }
                    for b in result["barbelege"].get(year, [])
                ],
            }
        )
    return {
        "zeitraum": zeitraum,
        "filter": GQB_FILTERS.get(gqb_filter or "", ""),
        "mit_geld": gqb_filter is None,
        "jahre": jahre,
    }


def add_arguments(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        nargs="+",
        metavar="YYYY",
        help="whole years instead of the current one: --year 2025 is --from 2025-01-01 "
        "--to 2025-12-31; "
        "several years span from the first to the last",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="PATH",
        help="PDF path (default: Verkaufszahlen_<year>.pdf or Verkaufszahlen_<from>_bis_<to>.pdf)",
    )
    parser.add_argument(
        "--gqb",
        choices=list(GQB_FILTERS),
        help="only GQB-certified articles, or exclude them -- e.g. for the GQ check",
    )
    parser.add_argument("--json", action="store_true", help="also print the report as JSON")
    add_print_arguments(parser)
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")


def apply_years(args: argparse.Namespace) -> None:
    """--year as --from/--to of whole years (the two cannot be combined);
    without --year, --from and --to the current year."""
    if not args.year and not (args.date_from or args.date_to):
        args.year = [int(time.strftime("%Y"))]
    if not args.year:
        return
    if args.date_from or args.date_to:
        print(
            "bscli verkaufszahlen: error: --year cannot be combined with --from/--to",
            file=sys.stderr,
        )
        sys.exit(2)
    args.date_from = f"{min(args.year):04d}-01-01"
    args.date_to = f"{max(args.year):04d}-12-31"


def run(args: argparse.Namespace) -> None:
    setup_logging(debug=args.debug)
    apply_years(args)

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
        "artikel": add_gqb(build_article_report(df), article_details(grist), args.gqb),
        "einnahmen_ausgaben": einnahmen_ausgaben,
        "barbelege": build_receipt_report(cash_entries),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    today = time.strftime("%Y-%m-%d")
    if args.year:
        span = f"{min(args.year)}" + (f"-{max(args.year)}" if len(set(args.year)) > 1 else "")
        default_name = f"Verkaufszahlen_{span}.pdf"
    else:
        default_name = (
            f"Verkaufszahlen_{args.date_from or 'Beginn'}_bis_{args.date_to or today}.pdf"
        )
    output: Path = args.output or Path(default_name)
    data = {**letterhead(grist), **pdf_data(result, args.date_from, args.date_to, today, args.gqb)}
    output.write_bytes(render("verkaufszahlen.typ", data, bw=args.bw))
    print(f"{output} written.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=CLI_HELP, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
