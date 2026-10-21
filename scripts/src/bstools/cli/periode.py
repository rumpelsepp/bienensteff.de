"""The period of a report: --year, or --from/--to, as two dates."""

import argparse
import sys
from datetime import date


def add_period_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="from this date on")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="up to this date")
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        nargs="+",
        metavar="YYYY",
        help="whole years instead of the current one: --year 2025 is --from 2025-01-01 "
        "--to 2025-12-31; several years span from the first to the last",
    )


def period(args: argparse.Namespace, prog: str, today: date) -> tuple[date, date]:
    """(start, end) of --year or --from/--to; without any of them the
    current year (and args.year set to it, for period_name()). Exits on a
    bad date or on --year with --from/--to."""

    def fail(msg: str) -> None:
        print(f"bscli {prog}: error: {msg}", file=sys.stderr)
        sys.exit(2)

    if args.year and (args.date_from or args.date_to):
        fail("--year cannot be combined with --from/--to")
    if not (args.year or args.date_from or args.date_to):
        args.year = [today.year]
    if args.year:
        return date(min(args.year), 1, 1), date(max(args.year), 12, 31)
    try:
        start = date.fromisoformat(args.date_from) if args.date_from else date(2000, 1, 1)
        end = date.fromisoformat(args.date_to) if args.date_to else today
    except ValueError as e:
        fail(str(e))
        raise
    return start, end


def period_label(start: date, end: date) -> str:
    """ "01.01.2026 – 31.12.2026", or "Beginn – …" without a start."""
    first = "Beginn" if start == date(2000, 1, 1) else start.strftime("%d.%m.%Y")
    return f"{first} – {end.strftime('%d.%m.%Y')}"


def period_name(args: argparse.Namespace, start: date, end: date) -> str:
    """For file names: "2026", "2025-2026" or "<from>_bis_<to>"."""
    if args.year:
        lo, hi = min(args.year), max(args.year)
        return str(lo) if lo == hi else f"{lo}-{hi}"
    first = "Beginn" if start == date(2000, 1, 1) else start.isoformat()
    return f"{first}_bis_{end.isoformat()}"
