"""
Downloads a Lexware voucher PDF by its human-readable document number (e.g.
RE-1044, AG-0012, AB-0042, LS-0007) via the Lexware Office API.

Required environment variable: LEXWARE_API_KEY

Usage:
  lexware-download RE-1044
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bstools.env import require_env_var
from bstools.lexware import LexwareClient

# Voucher number prefix -> voucherType (Lexware API filter value / RESOURCE_INFO key).
PREFIX_TO_VOUCHER_TYPE = {
    "RE": "invoice",
    "AG": "quotation",
    "AB": "orderconfirmation",
    "LS": "deliverynote",
}


def get_voucher_type(voucher_number: str) -> str:
    prefix = voucher_number.split("-")[0]
    try:
        return PREFIX_TO_VOUCHER_TYPE[prefix]
    except KeyError:
        raise ValueError(
            f"prefix {prefix} is not supported [voucher_number: {voucher_number}]"
        ) from None


def download_voucher(client: LexwareClient, voucher_number: str) -> bytes:
    voucher_type = get_voucher_type(voucher_number)
    voucher_id = client.find_voucher_id(voucher_type, voucher_number)
    if voucher_id is None:
        raise KeyError(f"{voucher_number} not found")
    return client.get_voucher_file(voucher_type, voucher_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("DOCUMENT_NUMBER")
    args = parser.parse_args()

    client = LexwareClient(require_env_var("LEXWARE_API_KEY"))
    try:
        data = download_voucher(client, args.DOCUMENT_NUMBER)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    Path(args.DOCUMENT_NUMBER).with_suffix(".pdf").write_bytes(data)


if __name__ == "__main__":
    main()
