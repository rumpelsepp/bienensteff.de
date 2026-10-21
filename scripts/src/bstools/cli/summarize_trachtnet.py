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
  trustworthy the average over them is;
- days, season_days: the days of the season with data, and how many
  there were to have -- for the year still running only up to the
  latest day in the dump. Where many are missing, gain falls short of
  what the colonies brought in; the map marks such regions.

Output: <outdir>/landkreis-summary.json, one region per line, oldest
first: {"kind", "years", "regions": {<ags>: {"name", "slug", "years":
{"<year>": {"gain", "peak", "scales", "days", "season_days"}}}}}. Regions without a single
season record in a year are left out of it.

Usage:
  bscli dump trachtnet-summary --outdir static/trachtnet-dump
"""

import argparse
import datetime
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
    days: int
    season_days: int


class RegionSummary(TypedDict):
    name: str
    slug: str
    years: dict[str, YearSummary]


def season_days(year: int, latest: str) -> int:
    """The days of the season of `year` up to `latest` (an ISO date, the
    latest day the dump has for that year)."""
    first = datetime.date(year, SEASON_FIRST, 1)
    end = datetime.date(year, SEASON_LAST + 1, 1) - datetime.timedelta(days=1)
    end = min(end, datetime.date.fromisoformat(latest))
    return max((end - first).days + 1, 0)


def summarize_year(records: list[Record], expected: int) -> YearSummary | None:
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
        "days": len(in_season),
        "season_days": expected,
    }


def read_records(path: Path) -> list[Record]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def summarize(outdir: Path) -> None:
    index = json.loads((outdir / "index.json").read_text())
    landkreise = [r for r in index["regions"] if r["kind"] == "landkreis"]
    logger.info("Summarising %s Landkreise", len(landkreise))

    # Region id -> year -> its records.
    records = {
        region["id"]: {
            path.stem.rsplit("-", 1)[1]: read_records(path)
            for path in sorted((outdir / "landkreis").glob(f"{region['id']}-*.ndjson"))
        }
        for region in landkreise
    }
    # The latest day of each year in the dump, for how many days of a
    # season still running there are to have.
    latest: dict[str, str] = {}
    for per_year in records.values():
        for year, rs in per_year.items():
            if rs:
                latest[year] = max(latest.get(year, ""), rs[-1]["date"])

    regions: dict[str, RegionSummary] = {}
    years: set[int] = set()
    for region in landkreise:
        summaries: dict[str, YearSummary] = {}
        for year, rs in records[region["id"]].items():
            summary = summarize_year(rs, season_days(int(year), latest[year]))
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


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("./trachtnet-dump"),
        help="output directory of `bscli dump trachtnet` (default: %(default)s)",
    )


def run(args: argparse.Namespace) -> None:
    setup_logging()
    summarize(args.outdir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
