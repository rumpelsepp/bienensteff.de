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
stays a step in Lexware. The upload is refused if a voucher with that number
already exists, or if the amount is 0 (e.g. BV-000, the initial filling).

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
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bstools.env import require_env
from bstools.grist import GristClient
from bstools.lexware import CATEGORY_SMALL_BUSINESS_INCOME, LexwareClient
from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE = TEMPLATE_DIR / "kassenbericht.typ"
BOX_TABLE_ID = "Box_Leerungen"
BOX_ITEMS_TABLE_ID = "Box_Bestand"
GRIST_ENV = ["GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID"]


def epoch_to_date(value: Any) -> str | None:
    """Grist Date cell (Unix seconds, UTC midnight) -> "YYYY-MM-DD"."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value, UTC).strftime("%Y-%m-%d")


def number(value: Any) -> float | None:
    """A Numeric/Int cell; None when empty or a formula error (["E", ...])."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return float(value)


def eur(value: float | None) -> str:
    """12.5 -> "12,50 €", German style; empty cells as an en dash."""
    if value is None:
        return "–"
    s = f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{s} €"


def count(value: Any) -> str:
    v = number(value)
    return "–" if v is None else f"{v:g}"


def german_date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


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

    business = {
        r["fields"].get("Key"): r["fields"].get("Value") or ""
        for r in grist.get_records("Betriebsdaten")
    }
    return {
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
        "firma": business.get("Unternehmensbezeichnung", ""),
        "adresse": " · ".join(v for v in (business.get("Adresse"), business.get("PLZ/Ort")) if v),
        "kontakt": " · ".join(v for v in (business.get("E-Mail"), business.get("Webseite")) if v),
        # Local time, in the system's time zone.
        "erstellt": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
    }


def render_pdf(report: dict[str, Any]) -> bytes:
    """Runs the system's typst on the template; the PDF comes back on stdout."""
    typst = shutil.which("typst")
    if typst is None:
        logger.error("typst not found in PATH.")
        sys.exit(1)
    result = subprocess.run(
        [
            typst,
            "compile",
            "--root",
            str(TEMPLATE_DIR),
            "--pdf-standard",
            "a-2b",
            "--format",
            "pdf",
            "--input",
            "data=" + json.dumps(report, ensure_ascii=False),
            str(TEMPLATE),
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("typst failed:\n%s", result.stderr.decode(errors="replace"))
        sys.exit(1)
    return result.stdout


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


def upload(report: dict[str, Any], pdf: bytes, filename: str, dry_run: bool) -> None:
    payload = voucher_payload(report)
    if report["beleg_betrag_wert"] <= 0:
        logger.error(
            "%s: amount is %s -- nothing to book (initial filling?), not uploaded.",
            report["nummer"],
            report["beleg_betrag"],
        )
        sys.exit(1)
    if dry_run:
        print("--dry-run: would create this voucher in Lexware and attach", filename)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    client = LexwareClient(require_env("LEXWARE_API_KEY")["LEXWARE_API_KEY"])
    if existing := client.find_voucher_id("salesinvoice", report["nummer"]):
        logger.error(
            "%s already exists in Lexware (%s), not uploaded again.",
            report["nummer"],
            client.voucher_deeplink(existing),
        )
        sys.exit(1)
    voucher_id = client.create_voucher(payload)
    client.upload_voucher_file(voucher_id, filename, pdf)
    print(
        f"Lexware: voucher {report['nummer']} created, PDF attached: {client.voucher_deeplink(voucher_id)}"
    )
    print("Still to do in Lexware: assign the Bargeld (Kasse) and the unbar bank payments.")


def main(argv: list[str] | None = None, prog: str | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("belegnummer", metavar="BELEGNUMMER", help="e.g. BV-001")
    parser.add_argument(
        "-o", "--output", type=Path, help="PDF path (default: Kassenbericht_<nr>.pdf)"
    )
    parser.add_argument(
        "--upload", action="store_true", help="book it in Lexware with the PDF attached"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="with --upload: only show the voucher"
    )
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")
    args = parser.parse_args(argv)
    setup_logging(debug=args.debug)

    cfg = require_env(*GRIST_ENV)
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    report = fetch_report(grist, args.belegnummer)
    pdf = render_pdf(report)

    output: Path = args.output or Path(f"Kassenbericht_{args.belegnummer}.pdf")
    output.write_bytes(pdf)
    print(f"{output} written ({len(pdf) // 1024} KiB).")
    if args.upload:
        upload(report, pdf, output.name, args.dry_run)


if __name__ == "__main__":
    main()
