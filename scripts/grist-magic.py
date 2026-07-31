#!/usr/bin/env -S uv run --script

# /// script
# requires-python = ">=3.14"
# dependencies = ["httpx>=0.27"]
# ///

"""
Lexware Office -> Grist sync for order confirmations (Bienensteff).

Grist column names, content, code comments, and console output are all
English now to avoid mixing languages within the tool.

Status logic (German display strings, see the STATUS_*/SUB_STATUS_* constants):
  "Status" is entirely manual. The script only ever sets it to STATUS_OPEN
  ("Offen") once, when a row is first created, and never touches it again --
  closing an OC (or reopening it) is entirely up to the human, on their own
  schedule.
  "Sub_Status" is entirely automatic, the mirror image of Status. Every run
  it's overwritten unconditionally with the OC's current billing progress,
  one of AUTO_SUB_STATUSES: "Nicht fakturiert" (no invoice, no delivery note
  either), "Zu fakturieren" (no invoice yet, but a delivery note exists --
  NOT a claim the goods were actually delivered, Lexware has no such
  confirmation, just a hint that billing is likely due), "Fakturiert"
  (invoice(s) linked, at least one still open), "Überfällig" (invoice open
  AND a dunning is linked), "Bezahlt" (all linked invoices settled --
  voucherStatus in SETTLED_INVOICE_STATUSES, "paid" or "voided" -- and at
  least one was actually paid), or "Storniert" (all linked invoices settled
  but every one of them is "voided" -- nothing was ever actually paid).
  There is no manual override for Sub_Status: whatever a human puts there is
  replaced on the next run. This is deliberate -- it keeps the
  billing-progress signal visible even after a human closes Status, instead
  of being overwritten by a one-way "done" marker.

Amount:
  Sum of the open amounts (openAmount) of all invoices linked to the OC,
  excluding drafts (see IGNORED_INVOICE_STATUSES -- a draft invoice is
  editable/deletable, not sent to the customer, so it's treated as if it
  doesn't exist here; it still shows up as a normal row in the Docs table,
  just doesn't count for Amount/Sub_Status). If the OC has no counted
  invoice (not billed, or only draft invoices), falls back to the OC's own
  total amount instead of showing 0.

Documents: live in a separate table named "{GRIST_TABLE_ID}_Docs" (e.g.
"Bestellungen_Docs"), not a column on the main table -- meant to be shown via
a Grist widget instead of one crowded cell. Columns:
  - Order_Confirmation_Number: a genuine Grist Reference (Ref:{GRIST_TABLE_ID})
    to the main table's row, not text -- so a widget can actually link/filter
    on it. The cell value written there is the OC's Grist row id (see
    sync_to_grist's return value), and column creation tries to set
    visibleCol so it displays as the OC number rather than a raw row id
    (best-effort against Grist's internal metadata tables -- if that lookup
    fails, fix "Show column" by hand once in Grist).
  - Document: the deeplink, as Markdown (rendered via widgetOptions.widget
    = "Markdown" -- confirmed against a working manually-configured column;
    the API docs/source pointed at "MarkdownTextBox" instead, which is
    wrong/misleading, don't trust that name again).
  - Document_Type: the voucherType, translated to German via
    DOCUMENT_TYPE_LABELS ("Rechnung", "Lieferschein", "Auftragsbestätigung",
    "Angebot", "Gutschrift", "Mahnung") -- technically always recoverable
    from the deeplink's URL, but a plain column is easier to filter/group on
    than parsing it back out.
  - Document_Status: the voucher's voucherStatus, translated to German via
    DOCUMENT_STATUS_LABELS -- falls back to the raw API value for anything
    not in that mapping (Lexware doesn't publish one shared status enum
    across voucher types, so this list is just what's been seen in
    practice), rather than hiding an unmapped status.
  - Document_Date, Document_Amount: the voucher's own voucherDate/
    totalAmount, straight from the API with no translation. Populated for
    every type except dunnings ("dun"), since those can't be listed via
    /voucherlist at all (see build_records) -- getting this data for
    dunnings would need a detail GET per dunning, deliberately skipped to
    avoid the extra API calls.
One row per document link (the OC itself, plus every voucher Lexware or a
manual entry links to it -- invoices, delivery notes, credit notes,
quotations, whatever). This table is fully derived: every run, all its rows
are deleted and reinserted from scratch (see sync_docs_table) -- don't put
anything manual in it, it will not survive the next run. Skipped entirely
when --only is used, since a full wipe would otherwise delete every other
OC's links too.
  1. Automatic, via the OC's own "relatedVouchers" list (returned by the
     Lexware API on every sales voucher), which enumerates every voucher
     created from it, regardless of type.
  2. Manual, via the Grist column "Manual_Document_Numbers" on the main
     table: enter comma-separated document numbers there (e.g. "RE-1044,
     LI-0022") for cases where the automatic chain comes up empty because a
     document wasn't created "from" the OC in Lexware. The script resolves
     every number against an index of all document numbers (invoices,
     delivery notes, quotations, credit notes -- NOT dunnings, see
     build_records) and appends a deeplink for whatever it finds. Numbers
     that can't be resolved are printed as warnings rather than silently
     dropped. Manual_Document_Numbers itself is read-only from the script's
     perspective -- it never writes to it after row creation.

Document access uses Lexware's deeplink feature (permalinks into the
Lexware web app, where you're already logged in) instead of file
uploads/attachments. The {appbaseurl}/permalink/{resource}/view/{id}
scheme is documented verbatim for contacts and cash boxes; for the other
voucher types it's taken by analogy -- verify against a live link once.

Before running for real: run with `--debug --dry-run` first and check the
raw payloads.

Required environment variables:
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID, GRIST_TABLE_ID

Usage:
  uv run lexware_grist_sync.py --init [--dry-run]   # create/update the Grist table
  uv run lexware_grist_sync.py --debug --dry-run
  uv run lexware_grist_sync.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

LEXWARE_BASE = "https://api.lexware.io/v1"
APP_BASE_URL = "https://app.lexware.de"
LEXWARE_MIN_INTERVAL = 0.6  # Lexware caps at 2 req/s; margin built in.

# Invoice voucherStatus values (raw Lexware API values, not user-facing --
# German display strings are a separate concern, see DOCUMENT_STATUS_LABELS)
# that count as "nothing more to collect": either it was paid, or it was
# cancelled (storniert) and therefore never needs to be paid. Confirmed
# against a live --debug payload: the API actually returns "paid" (the docs
# say "paidoff", which is wrong/outdated).
SETTLED_INVOICE_STATUSES = {"paid", "voided"}

# Invoice voucherStatus values that don't count as a real invoice yet for the
# Amount/Sub_Status logic -- a draft is editable/deletable, not sent to the
# customer, so an OC with only a draft invoice linked is treated exactly as
# if it had no invoice at all (still Unbilled/ToInvoice). The draft still
# shows up as a normal row in the Docs table, this only affects the main
# table's computed columns.
IGNORED_INVOICE_STATUSES = {"draft"}

# Status (main table, manual) choices.
STATUS_OPEN = "Offen"
STATUS_CLOSED = "Geschlossen"

# Sub_Status (main table, automatic) values this script sets, in rough
# workflow order. Unconditionally overwritten every run -- see docstring
# above.
SUB_STATUS_UNBILLED = "Nicht fakturiert"
SUB_STATUS_TO_INVOICE = "Zu fakturieren"
SUB_STATUS_INVOICED = "Fakturiert"
SUB_STATUS_OVERDUE = "Überfällig"
SUB_STATUS_PAID = "Bezahlt"
SUB_STATUS_CANCELLED = "Storniert"
AUTO_SUB_STATUSES = [
    SUB_STATUS_UNBILLED,
    SUB_STATUS_TO_INVOICE,
    SUB_STATUS_INVOICED,
    SUB_STATUS_OVERDUE,
    SUB_STATUS_PAID,
    SUB_STATUS_CANCELLED,
]

# The document links live in their own table (for a Grist widget view),
# named after the main table with this suffix, e.g. "Bestellungen_Docs".
DOCS_TABLE_SUFFIX = "_Docs"

GRIST_ENV = [
    "GRIST_API_KEY",
    "GRIST_BASE_URL",
    "GRIST_DOC_ID",
    "GRIST_TABLE_ID",
]
REQUIRED_ENV = ["LEXWARE_API_KEY"] + GRIST_ENV

# voucherType (API filter value) -> URL path segment, used both for the
# detail GET and for the deeplink.
RESOURCE_INFO: dict[str, str] = {
    "invoice": "invoices",
    "deliverynote": "delivery-notes",
    "orderconfirmation": "order-confirmations",
    "quotation": "quotations",  # path unverified, best guess
    "creditnote": "credit-notes",
    "dun": "dunnings",
}

# voucherType -> German label, for the Docs table's Document_Type column.
DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "invoice": "Rechnung",
    "deliverynote": "Lieferschein",
    "orderconfirmation": "Auftragsbestätigung",
    "quotation": "Angebot",
    "creditnote": "Gutschrift",
    "dun": "Mahnung",
}


def document_type_label(voucher_type: str) -> str:
    return DOCUMENT_TYPE_LABELS.get(voucher_type, voucher_type)


# voucherStatus (raw Lexware API value, varies by voucher type) -> German
# label, for the Docs table's Document_Status column. Not exhaustive --
# Lexware doesn't publish one shared enum across voucher types, this is
# just every value seen in practice (invoices: draft/open/paid/overdue/
# voided; quotations: rejected/accepted; delivery notes/OCs: open). Falls
# back to the raw API value for anything not in here, see
# document_status_label(), rather than silently hiding an unmapped status.
DOCUMENT_STATUS_LABELS: dict[str, str] = {
    "draft": "Entwurf",
    "open": "Offen",
    "paid": "Bezahlt",
    "paidoff": "Bezahlt",
    "overdue": "Überfällig",
    "voided": "Storniert",
    "rejected": "Abgelehnt",
    "accepted": "Angenommen",
}


def document_status_label(voucher_status: str | None) -> str | None:
    if not voucher_status:
        return None
    return DOCUMENT_STATUS_LABELS.get(voucher_status, voucher_status)


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_config(required: list[str] = REQUIRED_ENV) -> dict[str, str]:
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        die(
            "Missing environment variables: "
            + ", ".join(missing)
            + "\nSee the docstring at the top of this script."
        )
    return {k: os.environ[k] for k in required}


class LexwareClient:
    def __init__(self, api_key: str, debug: bool = False) -> None:
        self._client = httpx.Client(
            base_url=LEXWARE_BASE,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=30.0,
        )
        self._last_call = 0.0
        self.debug = debug

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_call
        if elapsed < LEXWARE_MIN_INTERVAL:
            time.sleep(LEXWARE_MIN_INTERVAL - elapsed)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._throttle()
        resp = self._client.get(path, params=params)
        self._last_call = time.monotonic()
        if resp.status_code == 429:
            # Hit the rate limit anyway -- back off briefly and retry once.
            time.sleep(2.0)
            resp = self._client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if self.debug:
            print(f"--- DEBUG GET {path} params={params} ---", file=sys.stderr)
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000], file=sys.stderr)
        return data

    def paginate_voucherlist(
        self, voucher_type: str, voucher_status: str = "any", page_size: int = 100
    ) -> Iterator[dict[str, Any]]:
        page = 0
        while True:
            data = self.get(
                "/voucherlist",
                params={
                    "voucherType": voucher_type,
                    "voucherStatus": voucher_status,
                    "page": page,
                    "size": page_size,
                },
            )
            content = data.get("content", [])
            if not content:
                return
            yield from content
            total_pages = data.get("totalPages", 1)
            page += 1
            if page >= total_pages:
                return

    def get_voucher_detail(self, voucher_type: str, voucher_id: str) -> dict[str, Any]:
        path_segment = RESOURCE_INFO[voucher_type]
        return self.get(f"/{path_segment}/{voucher_id}")

    def get_contact(self, contact_id: str) -> dict[str, Any]:
        return self.get(f"/contacts/{contact_id}")


def build_deeplink(voucher_type: str, voucher_id: str) -> str:
    path_segment = RESOURCE_INFO[voucher_type]
    return f"{APP_BASE_URL}/permalink/{path_segment}/view/{voucher_id}"


def build_contact_deeplink(contact_id: str) -> str:
    return f"{APP_BASE_URL}/permalink/contacts/view/{contact_id}"


@dataclass
class DocLink:
    markdown: str
    doc_type: str
    status: str | None = None
    date: str | None = None  # "YYYY-MM-DD"
    amount: float | None = None


@dataclass
class OrderRecord:
    ab_id: str
    ab_number: str
    date: str
    customer: str
    customer_id: str
    amount: float | None
    auto_sub_status: str = ""
    doc_links: list[DocLink] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def extract_contact_id(voucher_detail: dict[str, Any]) -> str | None:
    return (voucher_detail.get("address", {}) or {}).get("contactId")


def extract_one_time_name(voucher_detail: dict[str, Any]) -> str:
    """Display name for one-time addresses (Einmalkunde), which have no
    contactId -- the name is entered directly on the voucher's address block.
    """
    return (voucher_detail.get("address", {}) or {}).get("name") or "Unknown"


def build_voucher_index(
    client: LexwareClient, voucher_type: str, number_index: dict[str, tuple[str, str]]
) -> dict[str, dict[str, Any]]:
    """Mapping voucher id -> {voucherNumber, voucherStatus, voucherDate,
    totalAmount, openAmount}, from the /voucherlist view only -- no
    per-voucher detail GET. Also populates number_index (voucherNumber ->
    (type, id)), for resolving Manual_Document_Numbers.

    Deliberately not a per-voucher detail GET (e.g. GET /invoices/{id}):
    that response has no "openAmount" field at all -- only totalPrice.* for
    the voucher's own total, nothing about what's still open. openAmount
    (and, conveniently, everything else needed for the Docs table's
    Document_Status/Document_Date/Document_Amount columns) only exists on
    the /voucherlist summary, so that's the only source for any of it --
    and it's already being fetched for the number index anyway, so this
    doesn't cost any extra API calls.
    """
    index: dict[str, dict[str, Any]] = {}
    for entry in client.paginate_voucherlist(voucher_type, "any"):
        voucher_id = entry.get("id")
        number = entry.get("voucherNumber")
        if not voucher_id:
            continue
        if number:
            number_index[number.strip()] = (voucher_type, voucher_id)
        index[voucher_id] = {
            "voucherNumber": number,
            "voucherStatus": entry.get("voucherStatus"),
            "voucherDate": (entry.get("voucherDate") or "")[:10] or None,
            "totalAmount": entry.get("totalAmount"),
            "openAmount": entry.get("openAmount"),
        }
    return index


def extract_related(voucher_detail: dict[str, Any]) -> list[dict[str, str]]:
    """All related vouchers (any type) from a voucher's own relatedVouchers
    list -- this is how Lexware links an order confirmation to the invoices/
    delivery notes/etc. created from it (there is no "precedingSalesVoucherId"
    field on the other side).
    """
    related = voucher_detail.get("relatedVouchers") or []
    return [r for r in related if r.get("id") and r.get("voucherType")]


def get_contact_name(
    client: LexwareClient, contact_id: str, cache: dict[str, str]
) -> str:
    if contact_id in cache:
        return cache[contact_id]
    contact = client.get_contact(contact_id)
    company = contact.get("company") or {}
    person = contact.get("person") or {}
    if company.get("name"):
        name = company["name"]
    elif person:
        name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
    else:
        name = "Unknown"
    cache[contact_id] = name
    return name


def resolve_manual_links(
    manual_field_value: str,
    number_index: dict[str, tuple[str, str]],
    voucher_indexes: dict[str, dict[str, dict[str, Any]]],
    already_linked_ids: set[str],
    ab_number: str,
) -> tuple[list[DocLink], list[str], list[dict[str, Any]]]:
    """Resolves the comma-separated numbers from Manual_Document_Numbers.

    Returns (doc links, warnings, invoice info among them -- used for the
    Amount/Sub_Status logic). No detail GET needed for any type:
    number_index already has the canonical voucherNumber for the link text,
    and voucher_indexes already has voucherStatus/voucherDate/*Amount for
    every listable type (not dunnings, see build_records).
    """
    links: list[DocLink] = []
    warnings: list[str] = []
    manual_invoices: list[dict[str, Any]] = []

    if not manual_field_value:
        return links, warnings, manual_invoices

    for raw_number in manual_field_value.split(","):
        number = raw_number.strip()
        if not number:
            continue
        match = number_index.get(number)
        if not match:
            warnings.append(
                f"OC {ab_number}: manual document number '{number}' not found in Lexware."
            )
            continue
        voucher_type, voucher_id = match
        if voucher_id in already_linked_ids:
            continue  # already linked automatically, avoid duplicate entry
        already_linked_ids.add(voucher_id)
        info = voucher_indexes.get(voucher_type, {}).get(voucher_id)
        if voucher_type == "invoice":
            if info and info.get("voucherStatus") in IGNORED_INVOICE_STATUSES:
                pass  # draft -- still linked as a doc below, just not counted
            elif info:
                manual_invoices.append(info)
            else:
                warnings.append(
                    f"OC {ab_number}: manual invoice '{number}' not found in the "
                    f"invoice list, amount/status for it may be wrong."
                )
        links.append(
            DocLink(
                markdown=f"[{number} (manual)]({build_deeplink(voucher_type, voucher_id)})",
                doc_type=document_type_label(voucher_type),
                status=document_status_label(info.get("voucherStatus")) if info else None,
                date=info.get("voucherDate") if info else None,
                amount=info.get("totalAmount") if info else None,
            )
        )

    return links, warnings, manual_invoices


def build_records(
    client: LexwareClient,
    existing: dict[str, dict[str, Any]],
    only_ab_number: str | None = None,
) -> list[OrderRecord]:
    number_index: dict[str, tuple[str, str]] = {}
    # "dun" (dunnings) is deliberately excluded: /voucherlist rejects it with
    # a 400, so it can't be listed this way. Automatic linking via
    # relatedVouchers still picks up dunnings fine, since that comes from the
    # OC's own detail response, not from /voucherlist -- just without
    # Document_Status/Document_Date/Document_Amount, since those need the
    # /voucherlist summary.
    voucher_indexes = {
        voucher_type: build_voucher_index(client, voucher_type, number_index)
        for voucher_type in ("invoice", "deliverynote", "quotation", "creditnote")
    }

    contact_cache: dict[str, str] = {}
    records: list[OrderRecord] = []

    for entry in client.paginate_voucherlist("orderconfirmation", "any"):
        ab_id = entry.get("id")
        if not ab_id:
            continue
        ab_number = entry.get("voucherNumber", ab_id)
        if only_ab_number and ab_number != only_ab_number:
            continue
        existing_row = existing.get(ab_id, {})

        detail = client.get_voucher_detail("orderconfirmation", ab_id)
        if entry.get("voucherNumber"):
            number_index[entry["voucherNumber"].strip()] = ("orderconfirmation", ab_id)

        contact_id = extract_contact_id(detail) or ""
        customer_name = (
            get_contact_name(client, contact_id, contact_cache)
            if contact_id
            else extract_one_time_name(detail)
        )
        # Only real contacts get a deeplink -- one-time addresses (Einmalkunde)
        # have no contact_id and thus nothing to link to.
        customer_display = (
            f"[{customer_name}]({build_contact_deeplink(contact_id)})"
            if contact_id
            else customer_name
        )

        # One doc link per related voucher, whatever type it is (invoice,
        # delivery note, credit note, quotation, ...). No detail GET needed
        # for any of them -- invoices/deliverynotes/quotations/creditnotes
        # come from voucher_indexes (voucherStatus/voucherDate/*Amount),
        # dunnings just get id + voucherNumber, both already included in
        # relatedVouchers.
        doc_links: list[DocLink] = [
            DocLink(
                markdown=f"[{ab_number}]({build_deeplink('orderconfirmation', ab_id)})",
                doc_type=document_type_label("orderconfirmation"),
                status=document_status_label(entry.get("voucherStatus")),
                date=(entry.get("voucherDate") or "")[:10] or None,
                amount=entry.get("totalAmount"),
            )
        ]
        invoice_details: list[dict[str, Any]] = []
        already_linked_ids = {ab_id}
        warnings: list[str] = []
        has_dunning = False
        has_delivery_note = False

        for rel in extract_related(detail):
            rel_id, rel_type = rel["id"], rel["voucherType"]
            rel_number = rel.get("voucherNumber", rel_id)
            path_segment = RESOURCE_INFO.get(rel_type)
            if not path_segment:
                warnings.append(
                    f"OC {ab_number}: related voucher '{rel_number}' has unknown "
                    f"type '{rel_type}', skipped."
                )
                continue
            already_linked_ids.add(rel_id)
            info = voucher_indexes.get(rel_type, {}).get(rel_id)
            if rel_type == "invoice":
                if info and info.get("voucherStatus") in IGNORED_INVOICE_STATUSES:
                    pass  # draft -- still linked as a doc below, just not counted
                elif info:
                    invoice_details.append(info)
                else:
                    warnings.append(
                        f"OC {ab_number}: linked invoice '{rel_number}' not found "
                        f"in the invoice list, amount/status for it may be wrong."
                    )
            elif rel_type == "dun":
                has_dunning = True
            elif rel_type == "deliverynote":
                has_delivery_note = True
            doc_links.append(
                DocLink(
                    markdown=f"[{rel_number}]({build_deeplink(rel_type, rel_id)})",
                    doc_type=document_type_label(rel_type),
                    status=document_status_label(info.get("voucherStatus")) if info else None,
                    date=info.get("voucherDate") if info else None,
                    amount=info.get("totalAmount") if info else None,
                )
            )

        manual_links, manual_warnings, manual_invoices = resolve_manual_links(
            existing_row.get("manual_document_numbers", ""),
            number_index,
            voucher_indexes,
            already_linked_ids,
            ab_number,
        )
        doc_links.extend(manual_links)
        warnings.extend(manual_warnings)

        all_invoices = invoice_details + manual_invoices
        if all_invoices:
            amount = sum(d.get("openAmount") or 0 for d in all_invoices)
            billing_settled = all(
                d.get("voucherStatus") in SETTLED_INVOICE_STATUSES for d in all_invoices
            )
            if billing_settled:
                # All voided (never actually paid) is distinct from Paid --
                # a mix of voided + paid still counts as Paid, since some
                # money did in fact change hands.
                all_voided = all(d.get("voucherStatus") == "voided" for d in all_invoices)
                auto_sub_status = SUB_STATUS_CANCELLED if all_voided else SUB_STATUS_PAID
            else:
                auto_sub_status = SUB_STATUS_OVERDUE if has_dunning else SUB_STATUS_INVOICED
        else:
            # Not billed yet -- show the OC's own total instead of 0. A
            # delivery note existing doesn't mean the goods were actually
            # delivered (Lexware has no such confirmation), just that the
            # document was created -- but it's a strong hint billing is due.
            amount = entry.get("totalAmount")
            auto_sub_status = SUB_STATUS_TO_INVOICE if has_delivery_note else SUB_STATUS_UNBILLED

        records.append(
            OrderRecord(
                ab_id=ab_id,
                ab_number=ab_number,
                date=(entry.get("voucherDate") or "")[:10],
                customer=customer_display,
                customer_id=contact_id,
                amount=amount,
                auto_sub_status=auto_sub_status,
                doc_links=doc_links,
                warnings=warnings,
            )
        )
    return records


def _choice_options(choices: list[str]) -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"choices": choices})}


def _date_options(date_format: str) -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"dateFormat": date_format})}


def _markdown_options() -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"widget": "Markdown"})}


# Columns this script needs, in creation order: (colId, Grist type, extra
# column fields for creation only, e.g. widgetOptions for Choice/Date -- used
# when the column doesn't exist yet; never applied to an existing column, see
# run_init_table). Must stay in sync with to_grist_fields() below.
#
# "Date" and "Status"/"Sub_Status" are real Grist Date/Choice columns, not
# Text -- see date_to_epoch() and AUTO_SUB_STATUSES for what's written there.
GRIST_SCHEMA: list[tuple[str, str, dict[str, Any] | None]] = [
    ("Lexware_Order_Confirmation_Id", "Text", None),
    ("Order_Confirmation_Number", "Text", None),
    ("Date", "Date", _date_options("DD.MM.YYYY")),
    ("Customer", "Text", None),
    ("Customer_Id", "Text", None),
    ("Amount", "Numeric", None),
    ("Status", "Choice", _choice_options([STATUS_OPEN, STATUS_CLOSED])),
    ("Last_Synced", "Text", None),
    ("Sub_Status", "Choice", _choice_options(AUTO_SUB_STATUSES)),
    ("Manual_Document_Numbers", "Text", None),
]

def build_docs_schema(
    grist: GristClient, main_table_id: str
) -> list[tuple[str, str, dict[str, Any] | None]]:
    """Docs table schema: one row per document link, shown via a Grist widget
    linked/filtered on Order_Confirmation_Number, instead of cramming all
    links into one cell on the main table.

    Order_Confirmation_Number is a Ref to the main table -- its Grist row id
    is what gets written there (see sync_docs_table), not the AB number text
    -- so a widget can actually link/filter on it. visibleCol is looked up
    so the reference displays the main table's own Order_Confirmation_Number
    text instead of a raw row id; this is best-effort against Grist's
    internal metadata tables, so if the lookup fails for any reason the
    column is still created as a working reference, just without a nice
    display column (fix once by hand in Grist via "Show column" then).
    """
    ref_fields: dict[str, Any] = {}
    visible_col_ref = grist.get_column_ref(main_table_id, "Order_Confirmation_Number")
    if visible_col_ref is not None:
        ref_fields["visibleCol"] = visible_col_ref
    else:
        print(
            f"WARNING: could not look up the colRef for "
            f"{main_table_id}.Order_Confirmation_Number -- the reference "
            f"column will show raw row ids until 'Show column' is set by "
            f"hand in Grist.",
            file=sys.stderr,
        )
    return [
        ("Order_Confirmation_Number", f"Ref:{main_table_id}", ref_fields or None),
        ("Document", "Text", _markdown_options()),
        ("Document_Type", "Text", None),
        ("Document_Status", "Text", None),
        ("Document_Date", "Date", _date_options("DD.MM.YYYY")),
        ("Document_Amount", "Numeric", None),
    ]


class GristClient:
    def __init__(self, base_url: str, api_key: str, doc_id: str, table_id: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        self.doc_id = doc_id
        self.table_id = table_id

    def fetch_existing(self) -> dict[str, dict[str, Any]]:
        """Mapping Lexware_Order_Confirmation_Id -> {row_id,
        manual_document_numbers}."""
        resp = self._client.get(
            f"/api/docs/{self.doc_id}/tables/{self.table_id}/records"
        )
        self._check(resp)
        records = resp.json().get("records", [])
        result: dict[str, dict[str, Any]] = {}
        for rec in records:
            fields = rec.get("fields", {})
            ab_id = fields.get("Lexware_Order_Confirmation_Id")
            if ab_id:
                result[ab_id] = {
                    "row_id": rec["id"],
                    "manual_document_numbers": fields.get("Manual_Document_Numbers", "") or "",
                }
        return result

    def add_records(self, table_id: str, records: list[dict[str, Any]]) -> list[int]:
        """Returns the newly assigned row ids, in the same order as `records`."""
        if not records:
            return []
        payload = {"records": [{"fields": r} for r in records]}
        resp = self._client.post(
            f"/api/docs/{self.doc_id}/tables/{table_id}/records", json=payload
        )
        self._check(resp)
        return [rec["id"] for rec in resp.json().get("records", [])]

    def update_records(self, table_id: str, updates: list[tuple[int, dict[str, Any]]]) -> None:
        if not updates:
            return
        payload = {"records": [{"id": row_id, "fields": fields} for row_id, fields in updates]}
        resp = self._client.patch(
            f"/api/docs/{self.doc_id}/tables/{table_id}/records", json=payload
        )
        self._check(resp)

    def list_row_ids(self, table_id: str) -> list[int]:
        resp = self._client.get(f"/api/docs/{self.doc_id}/tables/{table_id}/records")
        self._check(resp)
        return [rec["id"] for rec in resp.json().get("records", [])]

    def delete_records(self, table_id: str, row_ids: list[int]) -> None:
        if not row_ids:
            return
        resp = self._client.post(
            f"/api/docs/{self.doc_id}/tables/{table_id}/records/delete", json=row_ids
        )
        self._check(resp)

    @staticmethod
    def _check(resp: httpx.Response) -> None:
        if resp.is_error:
            print(f"Grist API error {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()

    def list_tables(self) -> list[str]:
        resp = self._client.get(f"/api/docs/{self.doc_id}/tables")
        self._check(resp)
        return [t["id"] for t in resp.json().get("tables", [])]

    def get_columns(self, table_id: str) -> dict[str, dict[str, Any]]:
        """Mapping colId -> {"type": ..., "widgetOptions": <raw string or None>}."""
        resp = self._client.get(f"/api/docs/{self.doc_id}/tables/{table_id}/columns")
        self._check(resp)
        return {
            col["id"]: {
                "type": col.get("fields", {}).get("type", ""),
                "widgetOptions": col.get("fields", {}).get("widgetOptions"),
            }
            for col in resp.json().get("columns", [])
        }

    def get_table_ref(self, table_id: str) -> int | None:
        """Internal row id of a table in the _grist_Tables metadata table --
        needed to look up a column's colRef for visibleCol on Ref columns.
        """
        resp = self._client.get(f"/api/docs/{self.doc_id}/tables/_grist_Tables/records")
        self._check(resp)
        for rec in resp.json().get("records", []):
            if rec.get("fields", {}).get("tableId") == table_id:
                return rec["id"]
        return None

    def get_column_ref(self, table_id: str, col_id: str) -> int | None:
        """Internal row id (colRef) of a column in the _grist_Tables_column
        metadata table -- what a Ref column's visibleCol field points to.
        """
        table_ref = self.get_table_ref(table_id)
        if table_ref is None:
            return None
        resp = self._client.get(
            f"/api/docs/{self.doc_id}/tables/_grist_Tables_column/records"
        )
        self._check(resp)
        for rec in resp.json().get("records", []):
            fields = rec.get("fields", {})
            if fields.get("parentId") == table_ref and fields.get("colId") == col_id:
                return rec["id"]
        return None

    def create_table(
        self, table_id: str, columns: list[tuple[str, str, dict[str, Any] | None]]
    ) -> None:
        payload = {
            "tables": [
                {
                    "id": table_id,
                    "columns": [
                        {
                            "id": col_id,
                            "fields": {"label": col_id, "type": col_type, **(extra or {})},
                        }
                        for col_id, col_type, extra in columns
                    ],
                }
            ]
        }
        resp = self._client.post(f"/api/docs/{self.doc_id}/tables", json=payload)
        self._check(resp)

    def add_columns(
        self, table_id: str, columns: list[tuple[str, str, dict[str, Any] | None]]
    ) -> None:
        payload = {
            "columns": [
                {
                    "id": col_id,
                    "fields": {"label": col_id, "type": col_type, **(extra or {})},
                }
                for col_id, col_type, extra in columns
            ]
        }
        resp = self._client.post(
            f"/api/docs/{self.doc_id}/tables/{table_id}/columns", json=payload
        )
        self._check(resp)

    def update_column_fields(self, table_id: str, col_id: str, fields: dict[str, Any]) -> None:
        payload = {"columns": [{"id": col_id, "fields": fields}]}
        resp = self._client.patch(
            f"/api/docs/{self.doc_id}/tables/{table_id}/columns", json=payload
        )
        self._check(resp)


# Status and Manual_Document_Numbers are exclusively manually maintained;
# this script never overwrites them on update (only pre-fills a default when
# a row is created). Sub_Status is the opposite: fully automatic, overwritten
# unconditionally every run -- see the module docstring.
MANUAL_ONLY_COLUMNS = {"Status", "Manual_Document_Numbers"}


def date_to_epoch(date_str: str | None) -> int | None:
    """"YYYY-MM-DD" -> Unix timestamp (seconds, UTC midnight), the value
    format Grist's Date columns actually store/expect via the API -- an ISO
    string is not accepted.
    """
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def to_grist_fields(rec: OrderRecord, now_iso: str, is_new: bool) -> dict[str, Any]:
    fields = {
        "Lexware_Order_Confirmation_Id": rec.ab_id,
        "Order_Confirmation_Number": rec.ab_number,
        "Date": date_to_epoch(rec.date),
        "Customer": rec.customer,
        "Customer_Id": rec.customer_id,
        "Amount": rec.amount,
        "Sub_Status": rec.auto_sub_status,
        "Last_Synced": now_iso,
    }
    if is_new:
        fields["Status"] = STATUS_OPEN
        fields["Manual_Document_Numbers"] = ""
    return fields


def sync_to_grist(
    grist: GristClient,
    records: list[OrderRecord],
    existing: dict[str, dict[str, Any]],
    dry_run: bool,
) -> dict[str, int]:
    """Returns ab_id -> main-table row id, for every row that exists after
    this call (both previously-existing and newly-created) -- the Docs table
    needs these to write proper Ref cell values, not just the AB number text.
    """
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    to_add: list[dict[str, Any]] = []
    to_add_ab_ids: list[str] = []
    to_update: list[tuple[int, dict[str, Any]]] = []
    row_ids: dict[str, int] = {ab_id: data["row_id"] for ab_id, data in existing.items()}

    for rec in records:
        is_new = rec.ab_id not in existing
        fields = to_grist_fields(rec, now_iso, is_new)
        if is_new:
            to_add.append(fields)
            to_add_ab_ids.append(rec.ab_id)
        else:
            to_update.append((existing[rec.ab_id]["row_id"], fields))

    print(f"New: {len(to_add)}, updated: {len(to_update)}")
    if dry_run:
        print("--dry-run is set, nothing will be written to Grist.")
        return row_ids

    new_ids = grist.add_records(grist.table_id, to_add)
    row_ids.update(zip(to_add_ab_ids, new_ids))
    grist.update_records(grist.table_id, to_update)
    return row_ids


def sync_docs_table(
    grist: GristClient,
    table_id: str,
    records: list[OrderRecord],
    row_ids: dict[str, int],
    dry_run: bool,
) -> None:
    """The docs table is fully derived (no manual columns), so the simplest
    correct sync is: wipe it and reinsert -- one row per document link.

    Order_Confirmation_Number is a Ref to the main table, so it needs the
    OC's actual Grist row id (from row_ids, as returned by sync_to_grist),
    not the AB number text.
    """
    total_links = sum(len(rec.doc_links) for rec in records)
    print(f"Docs table '{table_id}': {total_links} document link(s).")
    if dry_run:
        print("--dry-run is set, the Docs table will not be touched.")
        return

    rows: list[dict[str, Any]] = []
    for rec in records:
        row_id = row_ids.get(rec.ab_id)
        if row_id is None:
            print(
                f"WARNING: no Grist row id for OC {rec.ab_number}, skipping "
                f"its Docs table rows.",
                file=sys.stderr,
            )
            continue
        for link in rec.doc_links:
            rows.append(
                {
                    "Order_Confirmation_Number": row_id,
                    "Document": link.markdown,
                    "Document_Type": link.doc_type,
                    "Document_Status": link.status,
                    "Document_Date": date_to_epoch(link.date),
                    "Document_Amount": link.amount,
                }
            )

    existing_ids = grist.list_row_ids(table_id)
    if existing_ids:
        grist.delete_records(table_id, existing_ids)
    grist.add_records(table_id, rows)


# widgetOptions keys that get synced onto an already-existing column without
# asking (unlike a type change, these never touch stored cell values, only
# UI behavior: the choice list for Choice columns, Markdown rendering for
# Text columns). Deliberately excludes "dateFormat" -- since a user may well
# have picked a different date format on purpose, that one's left alone once
# the column already exists.
AUTO_SYNCED_OPTION_KEYS = {"choices", "widget"}


def _parse_widget_options(widget_options_raw: Any) -> dict[str, Any]:
    if not widget_options_raw:
        return {}
    try:
        return json.loads(widget_options_raw)
    except (TypeError, ValueError):
        return {}


def run_init_table(
    grist: GristClient,
    table_id: str,
    schema: list[tuple[str, str, dict[str, Any] | None]],
    dry_run: bool,
) -> None:
    """Creates or updates one Grist table so it has all columns in `schema`.

    Only ever creates the table or adds missing columns on its own. Existing
    columns whose type doesn't match are never changed without asking first,
    since a type change can reformat or discard the values already in them.
    A few widgetOptions keys (AUTO_SYNCED_OPTION_KEYS) are the one exception
    that's synced on existing columns too, without asking: e.g. a Choice
    column's declared choice list, or a Text column's Markdown-rendering
    widget. Only ever the keys in AUTO_SYNCED_OPTION_KEYS, since those only
    affect UI behavior, never a stored cell value.
    """
    print(f"Checking Grist table '{table_id}' in doc {grist.doc_id} ...")
    tables = grist.list_tables()

    if table_id not in tables:
        print(f"Table '{table_id}' does not exist, creating with {len(schema)} columns ...")
        if dry_run:
            print("--dry-run is set, nothing will be created.")
            return
        grist.create_table(table_id, schema)
        print("Table created.")
        return

    print(f"Table '{table_id}' already exists, checking columns ...")
    existing_cols = grist.get_columns(table_id)

    missing = [
        (col_id, col_type, extra)
        for col_id, col_type, extra in schema
        if col_id not in existing_cols
    ]
    mismatched = [
        (col_id, existing_cols[col_id]["type"], col_type)
        for col_id, col_type, _ in schema
        if col_id in existing_cols and existing_cols[col_id]["type"] != col_type
    ]
    options_to_sync = []
    for col_id, col_type, extra in schema:
        if col_id not in existing_cols or not extra or "widgetOptions" not in extra:
            continue
        desired_wo = json.loads(extra["widgetOptions"])
        relevant_keys = [k for k in desired_wo if k in AUTO_SYNCED_OPTION_KEYS]
        if not relevant_keys:
            continue
        current_wo = _parse_widget_options(existing_cols[col_id]["widgetOptions"])
        if any(current_wo.get(k) != desired_wo.get(k) for k in relevant_keys):
            options_to_sync.append((col_id, extra))

    if not missing and not mismatched and not options_to_sync:
        print("Nothing to do, the table already matches the expected schema.")
        return

    if missing:
        print("Missing columns: " + ", ".join(col_id for col_id, _, _ in missing))
    if mismatched:
        print("Columns with a different type than expected:")
        for col_id, have, want in mismatched:
            print(f"  {col_id}: have {have!r}, expected {want!r}")
    if options_to_sync:
        print("Columns whose choices/widget will be (re-)set: " + ", ".join(c for c, _ in options_to_sync))

    if dry_run:
        print("--dry-run is set, nothing will be changed.")
        return

    if missing:
        grist.add_columns(table_id, missing)
        print(f"Added {len(missing)} column(s).")

    if mismatched:
        print(
            "\nChanging a column's type can reformat or discard the values "
            "already stored in it, so confirm each one:"
        )
        for col_id, have, want in mismatched:
            answer = input(f"  Change '{col_id}' from {have!r} to {want!r}? [y/N] ").strip().lower()
            if answer == "y":
                grist.update_column_fields(table_id, col_id, {"type": want})
                print(f"  Updated {col_id}.")
            else:
                print(f"  Skipped {col_id} -- writes to it may fail until fixed manually.")

    for col_id, extra in options_to_sync:
        grist.update_column_fields(table_id, col_id, extra)
        print(f"Updated options for {col_id}.")


def run_init(grist: GristClient, dry_run: bool) -> None:
    run_init_table(grist, grist.table_id, GRIST_SCHEMA, dry_run)
    print()
    docs_table_id = f"{grist.table_id}{DOCS_TABLE_SUFFIX}"
    docs_schema = build_docs_schema(grist, grist.table_id)
    run_init_table(grist, docs_table_id, docs_schema, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")
    parser.add_argument("--dry-run", action="store_true", help="don't write anything to Grist")
    parser.add_argument(
        "--init", action="store_true", help="create/update the Grist table, then exit"
    )
    parser.add_argument(
        "--only",
        metavar="AB_NUMBER",
        help="only process this one order confirmation number, for debugging "
        "(e.g. --only AB-0042)",
    )
    args = parser.parse_args()

    if args.init:
        cfg = load_config(GRIST_ENV)
        grist = GristClient(
            cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"], cfg["GRIST_TABLE_ID"]
        )
        run_init(grist, dry_run=args.dry_run)
        return

    cfg = load_config()
    lexware = LexwareClient(cfg["LEXWARE_API_KEY"], debug=args.debug)
    grist = GristClient(
        cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"], cfg["GRIST_TABLE_ID"]
    )

    print("Reading existing Grist rows (incl. manual document links) ...")
    existing = grist.fetch_existing()

    print("Fetching order confirmations and related documents from Lexware ...")
    records = build_records(lexware, existing, only_ab_number=args.only)
    print(f"Found {len(records)} order confirmations.\n")

    print(f"{'OC-Nr':<12} {'Date':<11} {'Customer':<25} {'Sub_Status':<10} {'Amount'}")
    for r in records:
        print(f"{r.ab_number:<12} {r.date:<11} {r.customer:<25} {r.auto_sub_status:<10} {r.amount}")
        for w in r.warnings:
            print(f"  WARNING: {w}")

    row_ids = sync_to_grist(grist, records, existing, dry_run=args.dry_run)

    if args.only:
        print("--only is set, skipping the Docs table (it's a full wipe-and-reinsert, "
              "which would delete every other OC's document links).")
    else:
        docs_table_id = f"{cfg['GRIST_TABLE_ID']}{DOCS_TABLE_SUFFIX}"
        sync_docs_table(grist, docs_table_id, records, row_ids, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
