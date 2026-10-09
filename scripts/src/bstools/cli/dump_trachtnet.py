"""
Dumps Trachtnet (dlr-web-daten1.aspdienste.de) beehive scale data per year
and region -- Bundesland, Regierungsbezirk, Landkreis and individual scale
(Waage) -- as one NDJSON file per region/year, plus an index.json listing
every region with its name, slug and the years a file exists for.

Where the data comes from:
- The list of regions and scales isn't hardcoded: it's read from the four
  select boxes on Trachtnet's own page (tdsa_client.pl without params), one
  request per run -- new scales show up and retired ones disappear
  automatically.
- Chart data comes from tdsa_client.pl?type=load_chart, the endpoint the
  page's own chart uses. It takes comma-separated ids and a from/to year
  range (the page allows at most 4 years) and returns one series per
  region and year, so regions are fetched in batches (--batch-size) rather
  than one request each. A series carries the region's display name, not
  its id; names are unique per region kind, which is how series map back
  to regions. If a batch fails with a 500 (seen for some retired scales),
  it's split in half and retried down to single regions.

Output: <outdir>/<kind>/<id>-<year>.ndjson, one record per line, oldest
first: {"date", "weight", "delta", "scales"} -- weight is the cumulative
weight change since Jan 1 in kg (averaged over the scales of a region),
delta the day's change in kg as Trachtnet computes it, scales the number
of scales that reported that day. <outdir>/index.json maps kind/id to name
and slug (for the website's shortcodes, see bundle_src/js/charts/
trachtnet.ts) and lists the years with a file per region.

What's dropped instead of stored (see clean_records()):
- days without data (weight null, or no scales) -- Trachtnet pads every
  series to a full year, so these are most of the raw records;
- runs of exactly 0.0 kg (>= 2 days, or at the start of a series): scales
  that report 0 while offline or before they were set up -- an isolated
  0.0 between real values is kept, as it can be a genuinely flat day;
- today and yesterday: Trachtnet still revises these as more scales report
  in (a new day often starts with a handful of scales and 0.0 kg).
Trachtnet also recomputes whole past years every now and then, so the
current year is always fetched in full; in the first days of January the
previous year is fetched too, to catch its final revisions.

Load on the (public) server: see TrachtnetConfig.

Usage:
  dump-trachtnet --outdir static/trachtnet-dump            # current year
  dump-trachtnet --year 2011 2012 2013 --outdir static/trachtnet-dump
  dump-trachtnet --concurrency 2 --min-interval 0.5 --debug
"""

import argparse
import asyncio
import dataclasses
import datetime
import html
import json
import logging
import re
import unicodedata
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Self, TypedDict

from bstools import httpclient
from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

CLIENT_PATH = "cgi-bin/tdsa/tdsa_client.pl"

# Query parameter -> output folder, in the order regions are listed in
# index.json and resolved by name on the website (a Bundesland wins over a
# Regierungsbezirk of the same name, e.g. "Berlin").
KINDS = frozendict(
    {
        "blid": "bundesland",
        "rbzid": "regierungsbezirk",
        "lkid": "landkreis",
        "wid": "waage",
    }
)

# See TrachtnetConfig for where these numbers come from.
DEFAULT_HTTP_CONFIG = httpclient.ClientConfig(
    base_url="https://dlr-web-daten1.aspdienste.de",
    # The server answers 403 to non-browser user agents.
    user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
    connect_timeout=5.0,
    timeout=45.0,
    total_timeout=120.0,
    retries=3,
    max_concurrency=4,
    min_interval=0.25,
)


@dataclasses.dataclass(frozen=True, kw_only=True)
class TrachtnetConfig:
    """Tunables for a dump run; main() applies the CLI overrides via
    dataclasses.replace().

    Server cost is roughly per series (region x year): measured (Sept 2026)
    ~0.3 s for a single series and ~1.6 s for 10 in one request. A batch
    of 20 regions x 4 years is ~80 series, i.e. ~10-15 s before the first
    byte -- hence the generous stall timeout (45 s) and total cap (120 s);
    a Timeout is retried up to `max_attempts` times, `retry_delay` seconds
    apart.

    Load: at most `max_concurrency` requests in flight and at least
    `min_interval` seconds between two request starts. A daily run (~1,650
    regions, current year) is ~85 requests instead of the ~1,500 single
    ones the old dump made.
    """

    http: httpclient.ClientConfig = DEFAULT_HTTP_CONFIG
    batch_size: int = 20
    years_per_request: int = 4  # Trachtnet's own limit
    max_attempts: int = 5
    retry_delay: float = 2.0
    # Today and yesterday are still being revised by Trachtnet, see the
    # module docstring.
    provisional_days: int = 2
    # Also fetch the previous year during the first days of January.
    previous_year_days: int = 14


@dataclasses.dataclass(frozen=True)
class Region:
    kind: str  # output folder, see KINDS
    param: str  # query parameter
    id: str  # as Trachtnet has it, incl. leading zeros
    name: str  # display name, also the series name in chart responses
    slug: str  # for looking regions up by name on the website


@dataclasses.dataclass(frozen=True)
class Catalog:
    regions: list[Region]
    years: list[int]


class Record(TypedDict):
    date: str
    weight: float
    delta: float | None
    scales: int


_SELECT_RE = r'<select[^>]*\bid="{}"[^>]*>(.*?)</select>'
_OPTION_RE = re.compile(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)')
# " (BY - LK)" etc. at the end of Regierungsbezirk/Landkreis names.
_STATE_CODE_RE = re.compile(r"\s*\(([A-Z]{2}) - ([A-Z]+)\)$")
_NAME_PREFIXES = ("früher: ", "Reg.-Bez. ", "Statistische Region ", "Direktionsbezirk ")


def _slugify(text: str) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _base_slug(name: str) -> str:
    """ "Reg.-Bez. Köln (NW - R)" -> "koeln", "Oberbayern (BY - R)" ->
    "oberbayern", "Baden-Württemberg" -> "baden_wuerttemberg" -- matches
    the names the old hardcoded enums used, which the site's content still
    refers to (e.g. region="Oberbayern")."""
    name = _STATE_CODE_RE.sub("", name)
    for prefix in _NAME_PREFIXES:
        name = name.removeprefix(prefix)
    return _slugify(name)


def parse_catalog(page: str) -> Catalog:
    regions: list[Region] = []
    for param, kind in KINDS.items():
        m = re.search(_SELECT_RE.format(param), page, re.DOTALL)
        if m is None:
            raise ValueError(f"no <select id={param!r}> on the Trachtnet page")
        options = []
        for value, label in _OPTION_RE.findall(m.group(1)):
            label = " ".join(html.unescape(label).split())
            suffix = f" ({value})"
            if not label.endswith(suffix):
                continue  # the "... wählen" placeholder
            options.append((value, label.removesuffix(suffix)))

        slugs = {value: _base_slug(name) for value, name in options}
        counts: dict[str, int] = {}
        for s in slugs.values():
            counts[s] = counts.get(s, 0) + 1
        for value, name in options:
            slug = slugs[value]
            if counts[slug] > 1:
                # e.g. a Landkreis and the kreisfreie Stadt of the same name
                code = _STATE_CODE_RE.search(name)
                slug = f"{slug}_{code.group(2).lower()}" if code else f"{slug}_{value}"
            regions.append(Region(kind, param, value, name, slug))

    m = re.search(_SELECT_RE.format("from"), page, re.DOTALL)
    years = sorted(int(v) for v, _ in _OPTION_RE.findall(m.group(1))) if m else []
    return Catalog(regions, years)


def _hash_lookup(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Trachtnet's per-point extras come as a list of one-key dicts keyed by
    the point's x value (as a string)."""
    return {**entry for entry in entries}


def parse_series(series: dict[str, Any]) -> list[Record]:
    """Raw chart series -> records, incl. the empty days (see
    clean_records()). x values are millisecond timestamps normalized to
    2012 (a leap year, so every month/day fits); the real year is
    `yearId`."""
    year = int(series["yearId"])
    deltas = _hash_lookup(series.get("yDayDataHash", []))
    scales = _hash_lookup(series.get("yAmountWaageHash", []))
    records: list[Record] = []
    for x, weight in series["data"]:
        day = datetime.datetime.fromtimestamp(x / 1000, datetime.UTC).date()
        try:
            date = day.replace(year=year)
        except ValueError:
            continue  # Feb 29 in a non-leap year
        key = str(x)
        records.append(
            {
                "date": date.isoformat(),
                "weight": weight,
                "delta": deltas.get(key),
                "scales": scales.get(key) or 0,
            }
        )
    records.sort(key=lambda r: r["date"])
    return records


def clean_records(records: list[Record], cutoff: datetime.date) -> list[Record]:
    """Drops what isn't data, see the module docstring: empty days, runs of
    exactly 0.0 kg (>= 2 days, or at the start), and days from `cutoff` on.
    """
    records = [
        r
        for r in records
        if r["weight"] is not None and r["scales"] and r["date"] < cutoff.isoformat()
    ]
    drop: set[int] = set()
    i = 0
    while i < len(records):
        if records[i]["weight"] != 0:
            i += 1
            continue
        j = i
        while j < len(records) and records[j]["weight"] == 0:
            j += 1
        if j - i >= 2 or i == 0:
            drop.update(range(i, j))
        i = j
    return [r for k, r in enumerate(records) if k not in drop]


def _chunks[T](items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _year_ranges(years: Sequence[int], size: int) -> Iterator[tuple[int, int]]:
    """Consecutive runs of `years`, at most `size` long, as (from, to)."""
    run: list[int] = []
    for y in sorted(set(years)):
        if run and (y != run[-1] + 1 or len(run) == size):
            yield run[0], run[-1]
            run = []
        run.append(y)
    if run:
        yield run[0], run[-1]


class TrachtnetClient:
    def __init__(self, config: TrachtnetConfig | None = None) -> None:
        self.config = config or TrachtnetConfig()
        self.client = httpclient.AsyncClient(self.config.http)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def fetch_catalog(self) -> Catalog:
        resp = await self.client.get(CLIENT_PATH)
        resp.raise_for_status()
        return parse_catalog(resp.text)

    async def _load_chart(
        self, param: str, ids: Sequence[str], from_year: int, to_year: int
    ) -> list[dict[str, Any]]:
        # The id list goes into the URL as-is, not via params: the server
        # 301-redirects percent-encoded commas (%2C, which libcurl's param
        # encoding produces) to literal ones -- apparently one per redirect,
        # so a batch of 20 ids ran into curl's redirect limit. Ids are only
        # digits anyway.
        url = f"{CLIENT_PATH}?{param}={','.join(ids)}"
        params = {p: "" for p in KINDS if p != param}
        params |= {"type": "load_chart", "from": str(from_year), "to": str(to_year)}
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                resp = await self.client.get(url, params=params)
                resp.raise_for_status()
                break
            except httpclient.Timeout as e:
                if attempt == self.config.max_attempts:
                    raise
                logger.warning("%s, trying again…", e)
                await asyncio.sleep(self.config.retry_delay)
        data = resp.json()
        if data.get("msg") != "chart_data_ok":
            # e.g. no data at all for this selection
            logger.debug(
                "load_chart %s=%s %s-%s: %s", param, ids, from_year, to_year, data.get("msg")
            )
            return []
        series: list[dict[str, Any]] = data.get("chart_data", {}).get("Series") or []
        return series

    async def fetch(
        self, regions: Sequence[Region], from_year: int, to_year: int
    ) -> dict[tuple[Region, int], list[Record]]:
        """Raw records per (region, year) for one batch of same-kind
        regions. A 500 splits the batch, see the module docstring."""
        try:
            series = await self._load_chart(
                regions[0].param, [r.id for r in regions], from_year, to_year
            )
        except httpclient.HTTPError as e:
            if e.response.status_code != 500:
                raise
            if len(regions) == 1:
                logger.warning(
                    "Server error for %s %s (%s), %s-%s, skipping",
                    regions[0].kind,
                    regions[0].id,
                    regions[0].name,
                    from_year,
                    to_year,
                )
                return {}
            half = len(regions) // 2
            first = await self.fetch(regions[:half], from_year, to_year)
            return first | await self.fetch(regions[half:], from_year, to_year)

        by_name = {r.name: r for r in regions}
        out: dict[tuple[Region, int], list[Record]] = {}
        for s in series:
            region = by_name.get(s.get("name", ""))
            if region is None:
                logger.warning("Unexpected series %r in response, skipping", s.get("name"))
                continue
            out[(region, int(s["yearId"]))] = parse_series(s)
        return out


def write_ndjson(path: Path, records: list[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records)
    )


def write_index(outdir: Path, catalog: Catalog) -> None:
    """One region per line, so a new scale or year is a one-line diff."""
    lines = []
    for r in catalog.regions:
        years = sorted(
            int(p.stem.rsplit("-", 1)[1]) for p in (outdir / r.kind).glob(f"{r.id}-*.ndjson")
        )
        entry = {"kind": r.kind, "id": r.id, "name": r.name, "slug": r.slug, "years": years}
        lines.append("    " + json.dumps(entry, ensure_ascii=False))
    (outdir / "index.json").write_text(
        '{\n  "years": '
        + json.dumps(catalog.years)
        + ',\n  "regions": [\n'
        + ",\n".join(lines)
        + "\n  ]\n}\n"
    )


def default_years(config: TrachtnetConfig, today: datetime.date) -> list[int]:
    years = [today.year]
    if today.timetuple().tm_yday <= config.previous_year_days:
        years.insert(0, today.year - 1)
    return years


async def dump_all(config: TrachtnetConfig, years: list[int] | None, outdir: Path) -> None:
    today = datetime.datetime.now(datetime.UTC).date()
    cutoff = today - datetime.timedelta(days=config.provisional_days - 1)

    async with TrachtnetClient(config) as client:
        catalog = await client.fetch_catalog()
        counts = {kind: sum(r.kind == kind for r in catalog.regions) for kind in KINDS.values()}
        logger.info("Trachtnet lists %s, years %s", counts, catalog.years)

        years = years or default_years(config, today)
        unknown = sorted(set(years) - set(catalog.years))
        if unknown:
            logger.warning("Years %s aren't offered by Trachtnet, skipping them", unknown)
            years = [y for y in years if y in catalog.years]

        jobs = [
            (batch, from_year, to_year)
            for kind in KINDS.values()
            for batch in _chunks([r for r in catalog.regions if r.kind == kind], config.batch_size)
            for from_year, to_year in _year_ranges(years, config.years_per_request)
        ]
        done = written = 0

        async def run(batch: Sequence[Region], from_year: int, to_year: int) -> None:
            nonlocal done, written
            result = await client.fetch(batch, from_year, to_year)
            for (region, year), raw in result.items():
                records = clean_records(raw, cutoff)
                if records:
                    write_ndjson(outdir / region.kind / f"{region.id}-{year}.ndjson", records)
                    written += 1
            done += 1
            logger.info(
                "%s %s-%s: %s regions, %s with data (%s/%s requests)",
                batch[0].kind,
                from_year,
                to_year,
                len(batch),
                len({r for r, _ in result} & set(batch)),
                done,
                len(jobs),
            )

        # All requests are queued at once; the client's concurrency limit
        # and min_interval decide how fast they actually hit the server. Any
        # unexpected error cancels the rest.
        async with asyncio.TaskGroup() as tg:
            for job in jobs:
                tg.create_task(run(*job))

    write_index(outdir, catalog)
    logger.info("Wrote %s files and index.json to %s", written, outdir)


def main() -> None:
    defaults = TrachtnetConfig()
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--year",
        type=int,
        nargs="+",
        help="years to dump (default: the current one, plus the previous one in early January)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("./trachtnet-dump"),
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=defaults.http.max_concurrency,
        help="max requests in flight (default: %(default)s)",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=defaults.http.min_interval,
        metavar="SECONDS",
        help="min time between two request starts (default: %(default)s)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=defaults.batch_size,
        help="regions per request (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=defaults.http.total_timeout,
        metavar="SECONDS",
        help="hard cap per request (default: %(default)s)",
    )
    parser.add_argument("--debug", action="store_true", help="log every request with timings")
    args = parser.parse_args()
    setup_logging(debug=args.debug)
    if args.concurrency < 1 or args.batch_size < 1:
        parser.error("--concurrency and --batch-size must be at least 1")

    config = dataclasses.replace(
        defaults,
        batch_size=args.batch_size,
        http=dataclasses.replace(
            defaults.http,
            max_concurrency=args.concurrency,
            min_interval=args.min_interval,
            total_timeout=args.timeout,
        ),
    )
    asyncio.run(dump_all(config, args.year, args.outdir))


if __name__ == "__main__":
    main()
