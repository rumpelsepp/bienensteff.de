"""
Builds any typst file in the design of the business: the package
@local/imkerei is available (`#import "@local/imkerei:0.1.0": *`), the PDF
is PDF/A-2b, and --bw makes it black and white for printers without colour.
The file can live anywhere, inside this repository or not.

Usage:
  bscli typst brief.typ                      # → brief.pdf next to it
  bscli typst brief.typ -o ~/Ausdruck.pdf --bw
  bscli typst brief.typ --watch              # rebuild on every change
  bscli typst brief.typ -- --font-path fonts # further typst options after --
"""

import argparse
import os
import sys
from pathlib import Path

from bstools.logging_setup import setup_logging
from bstools.pdf import add_print_arguments, typst_command


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file", type=Path, metavar="FILE", help="the .typ file to build")
    parser.add_argument(
        "-o", "--output", type=Path, metavar="PATH", help="PDF path (default: FILE with .pdf)"
    )
    parser.add_argument(
        "--root",
        type=Path,
        metavar="DIR",
        help="directory the document may read files from (default: the one of FILE)",
    )
    parser.add_argument("--watch", action="store_true", help="rebuild whenever a file changes")
    parser.add_argument(
        "--pdf-standard",
        default="a-2b",
        metavar="STANDARD",
        help="PDF standard, '' for none (default: %(default)s, for archiving)",
    )
    add_print_arguments(parser)
    parser.add_argument(
        "typst_args", nargs="*", metavar="-- TYPST_OPTION", help="passed on to typst as they are"
    )


def run(args: argparse.Namespace) -> None:
    setup_logging()
    if not args.file.is_file():
        print(f"bscli typst: error: {args.file} does not exist", file=sys.stderr)
        sys.exit(2)
    cmd = typst_command(
        "watch" if args.watch else "compile", bw=args.bw, pdf_standard=args.pdf_standard or None
    )
    if args.root:
        cmd += ["--root", str(args.root)]
    cmd += [*args.typst_args, str(args.file)]
    if args.output:
        cmd.append(str(args.output))
    # typst takes over this process: its output, Ctrl-C for --watch and its
    # exit code are those of the command.
    os.execv(cmd[0], cmd)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
