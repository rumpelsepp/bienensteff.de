"""
Fillings per year as PDF (templates/abfuellungen.typ), from the Grist
table Abfullungen: each filling with its batch, honey type, article, jars,
kg, best-before date and DIB numbers, and per batch how much was harvested
(the buckets of the batch) and how much of it has been filled so far -- the
Abfüllplan and the plausibility of what came in and went out for the GQ
check (criteria A6, A8, A10).

The GQ column of a filling is the article's GQB certification
(Verkaufdetails.gqb_certified of the article), and --gqb filters by it; the
batch table shows whether the batch itself is GQB-compliant. A filling of a
GQB-certified article from a batch that is not GQB-compliant is listed as a
conflict: GQ and non-GQ goods have to stay apart.

Settings (environment variable, or config file -- see bscli.example.toml):
  GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli abfuellungen                          # the current year
  bscli abfuellungen --year 2025              # Abfuellungen_2025.pdf
  bscli abfuellungen --year 2024 2026         # 2024 to 2026, one section per year
  bscli abfuellungen --gqb only               # only GQ articles
  bscli abfuellungen --from 2026-05-01 --to 2026-08-31 -o sommer.pdf
"""

import argparse
import time
from datetime import date
from pathlib import Path
from typing import Any

from bstools import tracing
from bstools.cli.periode import add_period_arguments, period, period_label, period_name
from bstools.env import require_env
from bstools.grist import GristClient
from bstools.logging_setup import setup_logging
from bstools.pdf import add_print_arguments, count, letterhead, render

GQB_FILTERS = {
    "only": "nur GQ-Artikel",
    "exclude": "nur Artikel ohne GQ",
}


def kg(value: float | None) -> str:
    return "–" if value is None else f"{count(round(value, 2))} kg"


def report(r: tracing.Records, start: date, end: date, gqb: str | None) -> dict[str, Any]:
    """The data for templates/abfuellungen.typ: per year (newest first) the
    fillings, their totals, the batches they came from and the conflicts."""
    fillings = []
    for f in r.abfuellungen.values():
        if not tracing.in_window(f["date"], start, end):
            continue
        los_id = tracing.ref(f.get("batch_id"))
        los = r.lose.get(los_id or 0, {})
        los_gq = bool(los.get("gqb_compliant"))
        artikel_gq = r.artikel_gqb.get(tracing.ref(f.get("sku")) or 0, False)
        if (gqb == "only" and not artikel_gq) or (gqb == "exclude" and artikel_gq):
            continue
        fillings.append((f, los_id, los, los_gq, artikel_gq))
    fillings.sort(key=lambda x: (x[0]["date"], tracing.text(x[0].get("filling_id"))))

    years: dict[int, list[Any]] = {}
    for item in fillings:
        years.setdefault(item[0]["date"].year, []).append(item)

    jahre = []
    for year in sorted(years, reverse=True):
        items = years[year]
        y_start = max(start, date(year, 1, 1))
        konflikte = []
        rows = []
        for f, los_id, los, los_gq, artikel_gq in items:
            nummer = tracing.text(f.get("filling_id"))
            if artikel_gq and not los_gq:
                konflikte.append(
                    f"{nummer}: GQ-Artikel „{tracing.text(f.get('label'))}“ aus Los "
                    f"{r.los_nummer(los_id) or '(ohne Los)'}, das nicht GQ ist."
                )
            if los_id is None:
                konflikte.append(f"{nummer}: ohne Los – nicht rückverfolgbar.")
            rows.append(
                {
                    "nr": nummer,
                    "datum": f["date"].strftime("%d.%m.%Y"),
                    "los": r.los_nummer(los_id),
                    "sorte": tracing.text(los.get("honey_type")),
                    "gq": "ja" if artikel_gq else "",
                    "artikel": tracing.text(f.get("label")),
                    "sku": r.artikel_nummer(tracing.ref(f.get("sku"))),
                    "stueck": count(f["stueck"]),
                    "kg": count(round(f["kg"], 2)) if f["kg"] is not None else "–",
                    "mhd": f["mhd"].strftime("%d.%m.%Y") if f["mhd"] else "",
                    "dib": tracing.text(f.get("dib_field")),
                }
            )

        lose = []
        for los_id in dict.fromkeys(i[1] for i in items if i[1] is not None):
            los = r.lose[los_id]
            geerntet = sum(
                tracing.number_or_zero(e.get("weight"))
                for e in r.eimer.values()
                if tracing.ref(e.get("batch_id")) == los_id
            )
            # Filled from the batch before this year (a batch can be filled
            # over two years): harvested - before - this year = what is left
            # in the buckets, or lost.
            vorher = sum(
                f["kg"] or 0
                for f in r.abfuellungen.values()
                if tracing.ref(f.get("batch_id")) == los_id and f["date"] and f["date"] < y_start
            )
            im_jahr = sum(i[0]["kg"] or 0 for i in items if i[1] == los_id)
            lose.append(
                {
                    "los": r.los_nummer(los_id),
                    "sorte": tracing.text(los.get("honey_type")),
                    "gq": "ja" if los.get("gqb_compliant") else "",
                    "geerntet": kg(geerntet),
                    "vorher": kg(vorher) if vorher else "",
                    "im_jahr": kg(im_jahr),
                    "rest": kg(geerntet - vorher - im_jahr),
                }
            )

        jahre.append(
            {
                "jahr": str(year),
                "abfuellungen": rows,
                "summe_stueck": count(sum(i[0]["stueck"] or 0 for i in items)),
                "summe_kg": count(round(sum(i[0]["kg"] or 0 for i in items), 2)),
                "lose": lose,
                "konflikte": konflikte,
            }
        )
    return {"filter": GQB_FILTERS.get(gqb or "", ""), "jahre": jahre}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    add_period_arguments(parser)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="PATH",
        help="PDF path (default: Abfuellungen_<period>.pdf)",
    )
    parser.add_argument(
        "--gqb", choices=list(GQB_FILTERS), help="only GQ articles, or exclude them"
    )
    add_print_arguments(parser)


def run(args: argparse.Namespace) -> None:
    setup_logging()
    today = date.fromisoformat(time.strftime("%Y-%m-%d"))
    start, end = period(args, "abfuellungen", today)
    cfg = require_env("GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID")
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    data = {
        **letterhead(grist),
        **report(tracing.load(grist), start, end, args.gqb),
        "zeitraum": period_label(start, end),
    }
    output: Path = args.output or Path(f"Abfuellungen_{period_name(args, start, end)}.pdf")
    output.write_bytes(render("abfuellungen.typ", data, bw=args.bw))
    print(f"{output} written.")
