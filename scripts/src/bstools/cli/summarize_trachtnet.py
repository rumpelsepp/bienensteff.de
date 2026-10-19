"""
Summarises the TrachtNet dump (dump_trachtnet.py) for the map chart of the
website: per Landkreis and year the season's total gain, its peak weight
and the number of scales behind them -- everything the map needs, in one
small file instead of the ~15 MB of NDJSON a year would take to load.

Metrics, all over the season only (March through August, like the
website's isInSeason()):
- gain: the sum of the days' positive deltas [kg] -- what the colonies
  brought in;
- peak: the highest cumulative weight of the season [kg];
- scales: the median number of scales that reported on a day -- how
  trustworthy the average over them is.

Output: <outdir>/landkreis-summary.json, one region per line, oldest
first: {"kind", "years", "regions": {<ags>: {"name", "slug", "years":
{"<year>": {"gain", "peak", "scales"}}}}}. Regions without a single
season record in a year are left out of it.

Usage:
  bscli dump trachtnet-summary --outdir static/trachtnet-dump
"""

import argparse
import json
import logging
import statistics
from pathlib import Path
from typing import Any, TypedDict

from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# The season the metrics are over, in months (inclusive), like the
# website's isInSeason().
SEASON_FIRST = 3
SEASON_LAST = 8


class Record(TypedDict):
    date: str
    weight: float
    delta: float | None
    scales: int


class YearSummary(TypedDict):
    gain: float
    peak: float
    scales: int


class RegionSummary(TypedDict):
    name: str
    slug: str
    years: dict[str, YearSummary]


def summarize_year(records: list[Record]) -> YearSummary | None:
    in_season = [
        r
        for r in records
        if SEASON_FIRST <= int(r["date"][5:7]) <= SEASON_LAST and r["weight"] is not None
    ]
    if not in_season:
        return None
    gains = [r["delta"] for r in in_season if r["delta"] is not None and r["delta"] > 0]
    return {
        "gain": round(sum(gains), 1),
        "peak": round(max(r["weight"] for r in in_season), 1),
        "scales": round(statistics.median(r["scales"] for r in in_season)),
    }


def read_records(path: Path) -> list[Record]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(outdir: Path) -> None:
    index = json.loads((outdir / "index.json").read_text())
    landkreise = [r for r in index["regions"] if r["kind"] == "landkreis"]
    logger.info("Summarising %s Landkreise", len(landkreise))

    regions: dict[str, RegionSummary] = {}
    years: set[int] = set()
    for region in landkreise:
        summaries: dict[str, YearSummary] = {}
        for path in sorted((outdir / "landkreis").glob(f"{region['id']}-*.ndjson")):
            year = path.stem.rsplit("-", 1)[1]
            summary = summarize_year(read_records(path))
            if summary is not None:
                summaries[year] = summary
                years.add(int(year))
        if summaries:
            regions[region["id"]] = {
                "name": region["name"],
                "slug": region["slug"],
                "years": dict(sorted(summaries.items())),
            }

    output: dict[str, Any] = {
        "kind": "landkreis",
        "years": sorted(years),
        # One region per line, so a new one is a one-line diff.
        "regions": {id: regions[id] for id in sorted(regions)},
    }
    path = outdir / "landkreis-summary.json"
    path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    logger.info("Wrote %s regions, %s years, to %s", len(regions), len(years), path)


def main(argv: list[str] | None = None, prog: str | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog=prog, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("./trachtnet-dump"),
        help="output directory of `bscli dump trachtnet` (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    setup_logging()
    summarize(args.outdir)


if __name__ == "__main__":
    main()
