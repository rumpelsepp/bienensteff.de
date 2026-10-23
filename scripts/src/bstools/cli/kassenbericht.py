"""
Kassenbericht of one emptying of an honesty box ("Verkaufsbox") as a PDF,
from the Grist tables Box_Leerungen and Box_Bestand -- and with --upload
booked in Lexware as a bookkeeping voucher with the PDF attached.

The PDF is rendered by the system's typst (templates/kassenbericht.typ in
this package; the data goes in as JSON via `--input data=...`) as PDF/A-2b,
the archival flavour. Header and footer take the business data from the
Grist table Betriebsdaten.

--upload creates a bookkeeping voucher of type salesinvoice in Lexware:
voucher number = the Belegnummer (BV-...), date = the date of the emptying,
amount = Bargeld + unbar, posting category "Einnahmen als Kleinunternehmer",
0 % tax, collective contact. Then the PDF is attached to it. Assigning the
payments -- the cash register for the Bargeld, the bank transactions for
unbar -- is not possible via the API (payments are read-only there) and
stays a step in Lexware. The upload is refused if the emptying is already
ticked "festgeschrieben" in Grist, if a voucher with that number already
exists, or if the amount is 0 (e.g. BV-000, the initial filling). After a
successful upload the emptying is ticked "festgeschrieben" in Grist, which
locks it and its article rows there (access rules on that column).

Settings (environment variable, or config file -- see bscli.example.toml):
  GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID; LEXWARE_API_KEY for --upload

Usage:
  bscli kassenbericht BV-001                 # writes Kassenbericht_BV-001.pdf
  bscli kassenbericht BV-001 -o /tmp/x.pdf
  bscli kassenbericht BV-001 --upload --dry-run
  bscli kassenbericht BV-001 --upload
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bstools.env import require_env
from bstools.grist import GristClient
from bstools.lexware import CATEGORY_SMALL_BUSINESS_INCOME, LexwareClient
from bstools.logging_setup import setup_logging
from bstools.pdf import add_print_arguments, count, eur, german_date, letterhead, number, render

logger = logging.getLogger(__name__)

BOX_TABLE_ID = "Box_Leerungen"
BOX_ITEMS_TABLE_ID = "Box_Bestand"
GRIST_ENV = ["GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID"]


def epoch_to_date(value: Any) -> str | None:
    """Grist Date cell (Unix seconds, UTC midnight) -> "YYYY-MM-DD"."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d")


def fetch_report(grist: GristClient, voucher_number: str) -> dict[str, Any]:
    """The emptying with this Belegnummer, its article rows and the business
    data, as plain values for the template and the voucher. Exits on a
    number that does not exist (or exists twice) or a missing date/amount.
    """
    emptyings = [
        r
        for r in grist.get_records(BOX_TABLE_ID)
        if r["fields"].get("Belegnummer") == voucher_number
    ]
    if len(emptyings) != 1:
        known = sorted(
            r["fields"].get("Belegnummer") or "" for r in grist.get_records(BOX_TABLE_ID)
        )
        logger.error(
            "%s: %s emptying(s) with this Belegnummer in Grist '%s' (known: %s).",
            voucher_number,
            len(emptyings),
            BOX_TABLE_ID,
            ", ".join(n for n in known if n) or "none",
        )
        sys.exit(1)
    rec = emptyings[0]
    f = rec["fields"]

    date = epoch_to_date(f.get("Datum"))
    cash = number(f.get("Betrag"))
    if date is None or cash is None:
        logger.error("%s: Datum or Bargeld is missing in Grist.", voucher_number)
        sys.exit(1)
    non_cash = number(f.get("Unbar")) or 0.0
    total = round(cash + non_cash, 2)
    if hint := (f.get("Hinweis") or "").strip():
        logger.warning("%s: Grist says: %s", voucher_number, hint)

    items = [
        r["fields"]
        for r in sorted(grist.get_records(BOX_ITEMS_TABLE_ID), key=lambda r: r["id"])
        if r["fields"].get("Leerung") == rec["id"]
    ]
    if not items:
        logger.warning("%s: no article rows in Grist '%s'.", voucher_number, BOX_ITEMS_TABLE_ID)

    return {
        "grist_id": rec["id"],
        "festgeschrieben": bool(f.get("Festgeschrieben")),
        "nummer": voucher_number,
        "datum_iso": date,
        "datum": german_date(date),
        "box": f.get("Quelle") or "",
        "bargeld_wert": cash,
        "unbar_wert": non_cash,
        "beleg_betrag_wert": total,
        "bargeld": eur(cash),
        "unbar": eur(non_cash),
        "beleg_betrag": eur(total),
        "bemerkung": (f.get("Notiz") or "").strip(),
        "positionen": [
            {
                "bezeichnung": i.get("Bezeichnung") or "",
                "sku": i.get("Article_Number") or "",
                "gezaehlt": count(i.get("Gezaehlt")),
                "aufgefuellt": count(i.get("Aufgefuellt_auf")),
            }
            for i in items
        ],
        **letterhead(grist),
    }


def voucher_payload(report: dict[str, Any]) -> dict[str, Any]:
    """Bookkeeping voucher for POST /v1/vouchers -- see the module docstring."""
    total = report["beleg_betrag_wert"]
    return {
        "type": "salesinvoice",
        "voucherStatus": "open",
        "voucherNumber": report["nummer"],
        "voucherDate": report["datum_iso"],
        "totalGrossAmount": total,
        "totalTaxAmount": 0,
        "taxType": "gross",
        "useCollectiveContact": True,
        "contactName": f"Verkaufsbox {report['box']}".strip(),
        "remark": (
            f"Kassenbericht {report['nummer']}, Verkaufsbox {report['box']}: "
            f"Bargeld {report['bargeld']}, unbar {report['unbar']}"
        ),
        "voucherItems": [
            {
                "amount": total,
                "taxAmount": 0,
                "taxRatePercent": 0,
                "categoryId": CATEGORY_SMALL_BUSINESS_INCOME,
            }
        ],
    }


def upload(
    grist: GristClient, report: dict[str, Any], pdf: bytes, filename: str, dry_run: bool
) -> None:
    payload = voucher_payload(report)
    if report["festgeschrieben"]:
        logger.error(
            "%s is already festgeschrieben in Grist (uploaded before), not uploaded again.",
            report["nummer"],
        )
        sys.exit(1)
    if report["beleg_betrag_wert"] <= 0:
        logger.error(
            "%s: amount is %s -- nothing to book (initial filling?), not uploaded.",
            report["nummer"],
            report["beleg_betrag"],
        )
        sys.exit(1)
    if dry_run:
        print("--dry-run: would create this voucher in Lexware and attach", filename)
        print("and then tick it festgeschrieben in Grist")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    client = LexwareClient(require_env("LEXWARE_API_KEY")["LEXWARE_API_KEY"])
    if existing := client.find_voucher_id("salesinvoice", report["nummer"]):
        logger.error(
            "%s already exists in Lexware (%s), not uploaded again -- tick it "
            "festgeschrieben in Grist if that is the right one.",
            report["nummer"],
            client.voucher_deeplink(existing),
        )
        sys.exit(1)
    voucher_id = client.create_voucher(payload)
    client.upload_voucher_file(voucher_id, filename, pdf)
    print(
        f"Lexware: voucher {report['nummer']} created, PDF attached: {client.voucher_deeplink(voucher_id)}"
    )
    grist.update_records(BOX_TABLE_ID, [(report["grist_id"], {"Festgeschrieben": True})])
    print(f"Grist: {report['nummer']} festgeschrieben.")
    print("Still to do in Lexware: assign the Bargeld (Kasse) and the unbar bank payments.")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("voucher_number", metavar="VOUCHER_NUMBER", help="Belegnummer, e.g. BV-001")
    parser.add_argument(
        "-o", "--output", type=Path, help="PDF path (default: Kassenbericht_<nr>.pdf)"
    )
    parser.add_argument(
        "--upload", action="store_true", help="book it in Lexware with the PDF attached"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="with --upload: only show the voucher"
    )
    add_print_arguments(parser)
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")


def run(args: argparse.Namespace) -> None:
    setup_logging(debug=args.debug)

    cfg = require_env(*GRIST_ENV)
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    report = fetch_report(grist, args.voucher_number)
    pdf = render("kassenbericht.typ", report, bw=args.bw)

    output: Path = args.output or Path(f"Kassenbericht_{args.voucher_number}.pdf")
    output.write_bytes(pdf)
    print(f"{output} written ({len(pdf) // 1024} KiB).")
    if args.upload:
        upload(grist, report, pdf, output.name, args.dry_run)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
