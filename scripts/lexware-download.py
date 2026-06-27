#!/usr/bin/env -S uv run -s

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "requests>=2.33.1",
# ]
# ///

import argparse
import enum
import os
import sys
from pathlib import Path

import requests


API_KEY = os.getenv("LEXWARE_API_KEY")


class VoucherType(enum.Enum):
    INVOICE = "invoice"
    QUOTATION = "quotation"
    ORDERCONFIRMATION = "orderconfirmation"
    DELIVERYNOTE = "deliverynote"


def get_voucher_type(voucher_number: str) -> VoucherType:
    prefix = voucher_number.split("-")[0]
    match prefix:
        case "RE":
            return VoucherType.INVOICE
        case "AG":
            return VoucherType.QUOTATION
        case "AB":
            return VoucherType.ORDERCONFIRMATION
        case "LS":
            return VoucherType.DELIVERYNOTE
    raise ValueError(
        f"prefix {prefix} is not supported [voucher_number: {voucher_number}]"
    )


def get_uuid(voucher_number: str) -> str:
    voucher_type = get_voucher_type(voucher_number)
    url = f"https://api.lexware.io/v1/voucherlist?voucherType={voucher_type.value}&voucherStatus=any&voucherNumber={voucher_number}"

    headers = {"Authorization": f"Bearer {API_KEY}"}

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    # TODO: Error handling
    if len(data["content"]) == 0:
        raise KeyError(f"{voucher_number} not found")
    return data["content"][0]["id"]


def download_voucher(voucher_number: str) -> bytes:
    voucher_type = get_voucher_type(voucher_number)
    uuid = get_uuid(voucher_number)

    match voucher_type:
        case VoucherType.INVOICE:
            url = f"https://api.lexware.io/v1/invoices/{uuid}/file"
        case VoucherType.QUOTATION:
            url = f"https://api.lexware.io/v1/quotations/{uuid}/file"
        case VoucherType.ORDERCONFIRMATION:
            url = f"https://api.lexware.io/v1/order-confirmations/{uuid}/file"
        case VoucherType.DELIVERYNOTE:
            url = f"https://api.lexware.io/v1/delivery-notes/{uuid}/file"

    headers = {"Authorization": f"Bearer {API_KEY}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()

    return r.content


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("DOCUMENT_NUMBER")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        data = download_voucher(args.DOCUMENT_NUMBER)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    Path(args.DOCUMENT_NUMBER).with_suffix(".pdf").write_bytes(data)


if __name__ == "__main__":
    main()
