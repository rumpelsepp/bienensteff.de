"""
bscli -- the command line tools of bienensteff.de, as subcommands.

Every command has its own options: `bscli <command> --help`. API keys, URLs
and the Grist document come from the environment or the config file, see
bstools.env and bscli.example.toml.
"""

import importlib
import os
import sys

type Command = tuple[str, str]  # (module with main(argv, prog), one-line summary)

COMMANDS: dict[str, Command | dict[str, Command]] = {
    "kassenbericht": (
        "bstools.cli.kassenbericht",
        "Kassenbericht einer Box-Leerung aus Grist als PDF, optional als Beleg nach Lexware",
    ),
    "verkaufszahlen": (
        "bstools.cli.verkaufszahlen",
        "verkaufte Stückzahlen je Artikel (Rechnungen + Boxen), Sync nach Grist",
    ),
    "bestellungen": (
        "bstools.cli.bestellungen",
        "Lexware-Auftragsbestätigungen und ihre Belege nach Grist",
    ),
    "beleg-pdf": (
        "bstools.cli.beleg_pdf",
        "PDF eines Lexware-Belegs per Nummer herunterladen (RE-, AG-, AB-, LS-)",
    ),
    "dump": {
        "db": (
            "bstools.cli.dump_db",
            "Produkt-/Tracing-Datenbank aus Grist als JSON (assets/db/db.json)",
        ),
        "trachtnet": (
            "bstools.cli.dump_trachtnet",
            "TrachtNet-Stockwaagen-Daten (static/trachtnet-dump)",
        ),
        "trachtnet-summary": (
            "bstools.cli.summarize_trachtnet",
            "Zusammenfassung des TrachtNet-Dumps für die Karte",
        ),
        "dwd": (
            "bstools.cli.dump_dwd",
            "Wetterdaten einer DWD-Station (static/klima)",
        ),
    },
}


def usage() -> str:
    rows: list[tuple[str, str]] = []
    for name, entry in COMMANDS.items():
        if isinstance(entry, dict):
            rows += [(f"{name} {sub}", summary) for sub, (_, summary) in entry.items()]
        else:
            rows.append((name, entry[1]))
    width = max(len(name) for name, _ in rows)
    lines = "\n".join(f"  {name:<{width}}  {summary}" for name, summary in rows)
    return (
        "usage: bscli [--config PATH] <command> [options]\n\n"
        f"commands:\n{lines}\n\n"
        "`bscli <command> --help` for the options of a command."
    )


def fail(message: str) -> None:
    print(f"bscli: {message}\n\n{usage()}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    argv = sys.argv[1:]
    # Global option, before the command: which config file to use.
    if argv[:1] == ["--config"]:
        if len(argv) < 2:
            fail("--config needs a path")
        os.environ["BSCLI_CONFIG"] = argv[1]
        argv = argv[2:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(usage())
        sys.exit(0 if argv else 2)

    name, rest = argv[0], argv[1:]
    entry = COMMANDS.get(name)
    if entry is None:
        fail(f"unknown command {name!r}")
        return
    if isinstance(entry, dict):
        if not rest or rest[0] not in entry:
            fail(f"{name} needs one of: {', '.join(entry)}")
            return
        name, entry, rest = f"{name} {rest[0]}", entry[rest[0]], rest[1:]
    module = importlib.import_module(entry[0])
    module.main(rest, prog=f"bscli {name}")


if __name__ == "__main__":
    main()
