"""PDFs in the design of the business, built with the system's typst.

The design is the typst package @local/imkerei in typst-packages/ next to
this module; typst_command() hands typst that package path (unless
$TYPST_PACKAGE_PATH is set), the business from the [betrieb] section of
the config file (`--input betrieb=...`, see the package's lib.typ), PDF/A-2b
and, for printers without colour, black and white. render() builds the reports of the CLI from templates/:
the data goes in as JSON via `--input data=...`, the PDF comes back on
stdout. Templates only do layout -- numbers and dates arrive formatted, with
the helpers below.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from bstools.env import config_path, config_section
from bstools.grist import GristClient

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
PACKAGE_PATH = Path(__file__).resolve().parent / "typst-packages"


def add_print_arguments(parser: argparse.ArgumentParser) -> None:
    """Options of every command that renders a PDF."""
    parser.add_argument(
        "--bw",
        action="store_true",
        help="black and white (grey instead of colours, b/w logo), for printers without colour",
    )


def typst_command(
    subcommand: str = "compile", bw: bool = False, pdf_standard: str | None = "a-2b"
) -> list[str]:
    """`typst <subcommand>` with the package path of @local/imkerei, the
    business of the config file, the PDF standard and black and white if
    asked -- input and output still to add. Exits if typst is not installed.
    """
    typst = shutil.which("typst")
    if typst is None:
        logger.error("typst not found in PATH.")
        sys.exit(1)
    cmd = [typst, subcommand]
    if not os.environ.get("TYPST_PACKAGE_PATH"):
        cmd += ["--package-path", str(PACKAGE_PATH)]
    if betrieb := config_section("betrieb"):
        cmd += ["--input", "betrieb=" + json.dumps(betrieb, ensure_ascii=False)]
    else:
        logger.warning(
            "No [betrieb] in the config file (%s): letterhead and GiroCode stay empty, "
            "see bscli.example.toml.",
            config_path(),
        )
    if pdf_standard:
        cmd += ["--pdf-standard", pdf_standard]
    if bw:
        cmd += ["--input", "bw=1"]
    return cmd


def render(template: str, data: dict[str, Any], bw: bool = False) -> bytes:
    """Renders templates/<template> with `data`, in black and white if
    asked; exits on a typst error."""
    result = subprocess.run(
        [
            *typst_command(bw=bw),
            "--root",
            str(TEMPLATE_DIR),
            "--format",
            "pdf",
            "--input",
            "data=" + json.dumps(data, ensure_ascii=False),
            str(TEMPLATE_DIR / template),
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("typst failed:\n%s", result.stderr.decode(errors="replace"))
        sys.exit(1)
    return result.stdout


def letterhead(grist: GristClient) -> dict[str, str]:
    """Header/footer data (firma, adresse, kontakt, erstellt) from the Grist
    table Betriebsdaten, plus the time of creation in the system's time zone.
    """
    business = {
        r["fields"].get("Key"): r["fields"].get("Value") or ""
        for r in grist.get_records("Betriebsdaten")
    }
    return {
        "firma": business.get("Unternehmensbezeichnung", ""),
        "adresse": " · ".join(v for v in (business.get("Adresse"), business.get("PLZ/Ort")) if v),
        "kontakt": " · ".join(v for v in (business.get("E-Mail"), business.get("Webseite")) if v),
        "erstellt": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M"),
    }


def number(value: Any) -> float | None:
    """A Numeric/Int cell; None when empty or a formula error (["E", ...])."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return float(value)


def _german(s: str) -> str:
    return s.replace(",", " ").replace(".", ",").replace(" ", ".")


def eur(value: float | None) -> str:
    """12.5 -> "12,50 €"; None as an en dash."""
    return "–" if value is None else f"{_german(f'{value:,.2f}')} €"


def count(value: Any) -> str:
    """3.0 -> "3", 2.5 -> "2,5", 1234 -> "1.234"; empty as an en dash."""
    v = number(value)
    if v is None:
        return "–"
    return _german(f"{v:,.0f}" if v.is_integer() else f"{v:,.3f}".rstrip("0"))


def german_date(iso: str) -> str:
    """ "2026-10-16" (or a longer ISO timestamp) -> "16.10.2026"."""
    y, m, d = iso[:10].split("-")
    return f"{d}.{m}.{y}"
