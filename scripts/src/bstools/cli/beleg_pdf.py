"""
Downloads a Lexware voucher PDF by its human-readable document number (e.g.
RE-1044, AG-0012, AB-0042, LS-0007) via the Lexware Office API.

Required environment variable: LEXWARE_API_KEY

Usage:
  bscli beleg-pdf RE-1044
"""

import argparse
import logging
import sys
from pathlib import Path

from bstools.env import require_env_var
from bstools.lexware import LexwareClient
from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# Voucher number prefix -> voucherType (Lexware API filter value / RESOURCE_INFO key).
PREFIX_TO_VOUCHER_TYPE = frozendict(
    {
        "RE": "invoice",
        "AG": "quotation",
        "AB": "orderconfirmation",
        "LS": "deliverynote",
    }
)


def get_voucher_type(voucher_number: str) -> str:
    prefix = voucher_number.split("-")[0]
    try:
        return PREFIX_TO_VOUCHER_TYPE[prefix]
    except KeyError:
        raise ValueError(
            f"prefix {prefix} is not supported [voucher_number: {voucher_number}]"
        ) from None


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("DOCUMENT_NUMBER")


def run(args: argparse.Namespace) -> None:
    setup_logging()

    client = LexwareClient(require_env_var("LEXWARE_API_KEY"))
    try:
        voucher_type = get_voucher_type(args.DOCUMENT_NUMBER)
        data = client.download_voucher_pdf(voucher_type, args.DOCUMENT_NUMBER)
    except (KeyError, ValueError) as e:
        logger.error(str(e))
        sys.exit(1)

    Path(args.DOCUMENT_NUMBER).with_suffix(".pdf").write_bytes(data)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
