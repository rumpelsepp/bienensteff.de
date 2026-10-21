"""
The command line tools of bienensteff.de, as subcommands.

API keys, URLs and the Grist document come from the environment or the
config file bscli.toml, see bscli.example.toml.
"""

import argparse
import os
from types import ModuleType

from bstools.cli import (
    abfuellungen,
    beleg_pdf,
    bestellungen,
    dump_db,
    dump_dwd,
    dump_trachtnet,
    eigenkontrolle,
    kassenbericht,
    lint,
    summarize_trachtnet,
    typst_build,
    verkaufszahlen,
)

# Each module provides add_arguments(parser) and run(args); argparse builds
# usage, help and errors from that. The text after the name is the
# one-line summary in `bscli --help`; the full help is the module's own.
COMMANDS: dict[str, tuple[ModuleType, str]] = {
    "kassenbericht": (
        kassenbericht,
        "Kassenbericht of a box emptying as PDF, optionally to Lexware",
    ),
    "verkaufszahlen": (verkaufszahlen, "sales per article, GQB and income per year as PDF"),
    "abfuellungen": (abfuellungen, "fillings per year with their batches as PDF"),
    "eigenkontrolle": (eigenkontrolle, "GQ-Bayern Eigenkontrolle of a year as PDF, from Grist"),
    "bestellungen": (bestellungen, "Lexware order confirmations and their vouchers to Grist"),
    "beleg-pdf": (beleg_pdf, "PDF of a Lexware voucher by number (RE-, AG-, AB-, LS-)"),
    "typst": (typst_build, "build any typst file in the design of the business"),
    "lint": (lint, "check the honey records in Grist for errors and gaps"),
}
DUMPS: dict[str, tuple[ModuleType, str]] = {
    "db": (dump_db, "product/tracing database from Grist as JSON"),
    "trachtnet": (dump_trachtnet, "TrachtNet hive scale data"),
    "trachtnet-summary": (summarize_trachtnet, "summary of the TrachtNet dump for the map"),
    "dwd": (dump_dwd, "weather data of a DWD station"),
}


def _add_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    commands: dict[str, tuple[ModuleType, str]],
) -> None:
    for name, (module, summary) in commands.items():
        parser = subparsers.add_parser(
            name,
            help=summary,
            description=getattr(module, "CLI_HELP", None) or module.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            suggest_on_error=True,
        )
        module.add_arguments(parser)
        parser.set_defaults(run=module.run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bscli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        suggest_on_error=True,
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="config file to use instead of looking for bscli.toml",
    )
    commands = parser.add_subparsers(title="commands", metavar="COMMAND", required=True)
    _add_commands(commands, COMMANDS)
    dump = commands.add_parser(
        "dump",
        help="data for the website (db, trachtnet, dwd, ...)",
        description="Data dumps for the website.",
        suggest_on_error=True,
    )
    _add_commands(
        dump.add_subparsers(title="dumps", metavar="DUMP", required=True),
        DUMPS,
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.config:
        os.environ["BSCLI_CONFIG"] = args.config
    args.run(args)


if __name__ == "__main__":
    main()
