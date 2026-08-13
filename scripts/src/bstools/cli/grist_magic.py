"""
Lexware Office -> Grist sync for order confirmations (Bienensteff).

Grist column names, content, code comments, and console output are all
English now to avoid mixing languages within the tool.

Status logic (German display strings, see the STATUS_*/BILLING_STATUS_*/
SHIPPING_STATUS_* constants):
  "Status" is entirely manual. The script only ever sets it to STATUS_OPEN
  ("Offen") once, when a row is first created, and never touches it again --
  closing an OC (or reopening it) is entirely up to the human, on their own
  schedule.
  "Abrechnungsstatus" is entirely automatic, the mirror image of Status.
  Every run it's overwritten unconditionally with the OC's current billing
  progress, one of AUTO_BILLING_STATUSES: "Nicht fakturiert" (no invoice, no
  delivery note either), "Zu fakturieren" (no invoice yet, but a delivery
  note exists -- NOT a claim the goods were actually delivered, Lexware has
  no such confirmation, just a hint that billing is likely due),
  "Fakturiert" (invoice(s) linked, at least one still open), "Überfällig"
  (invoice open AND a dunning is linked), "Bezahlt" (all linked invoices
  settled -- voucherStatus in SETTLED_INVOICE_STATUSES, "paid" or "voided"
  -- and at least one was actually paid), or "Storniert" (all linked
  invoices settled but every one of them is "voided" -- nothing was ever
  actually paid). There is no manual override for Abrechnungsstatus:
  whatever a human puts there is replaced on the next run. This is
  deliberate -- it keeps the billing-progress signal visible even after a
  human closes Status, instead of being overwritten by a one-way "done"
  marker.
  "Versandstatus" is entirely manual, like Status: the script only ever
  sets it to SHIPPING_STATUS_WAITING ("Wartet") once, when a row is first
  created, and never touches it again. Purely for the human to track
  fulfillment (Wartet -> Bereit -> Erledigt) -- there's no Lexware signal
  for "picked up" or "handed over in person", so this can't be automated.

Amount:
  Sum of the open amounts (openAmount) of all invoices linked to the OC,
  excluding drafts (see IGNORED_INVOICE_STATUSES -- a draft invoice is
  editable/deletable, not sent to the customer, so it's treated as if it
  doesn't exist here; it still shows up as a normal row in the Docs table,
  just doesn't count for Amount/Abrechnungsstatus). If the OC has no counted
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
    /voucherlist at all (see build_records). Populated for
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
  grist-magic --init [--dry-run]   # create/update the Grist table
  grist-magic --debug --dry-run
  grist-magic
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from bstools.env import require_env
from bstools.grist import (
    GristClient,
    choice_options,
    date_options,
    date_to_epoch,
    markdown_options,
)
from bstools.lexware import (
    RESOURCE_INFO,
    LexwareClient,
    extract_contact_id,
    extract_one_time_name,
    extract_related,
)
from bstools.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# Short version of the module docstring above, for --help -- the full one is
# too long to dump on a terminal usefully. Keep in sync by hand; it's meant
# to stay a stable summary, not track every detail of the long version.
CLI_HELP = """Lexware Office -> Grist sync for order confirmations (Bienensteff).

Syncs order confirmations from Lexware into a Grist table: one row per OC
(Status + Versandstatus manual, Abrechnungsstatus automatic billing
progress), plus a derived "_Docs" table linking every related voucher. See
the module docstring in the source for the full column semantics, Amount
calculation, and Docs-table derivation rules.

Required environment variables:
  LEXWARE_API_KEY, GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID, GRIST_TABLE_ID

Usage:
  grist-magic --init [--dry-run]   # create/update the Grist table
  grist-magic --debug --dry-run
  grist-magic"""

# Invoice voucherStatus values (raw Lexware API values, not user-facing --
# German display strings are a separate concern, see DOCUMENT_STATUS_LABELS)
# that count as "nothing more to collect": either it was paid, or it was
# cancelled (storniert) and therefore never needs to be paid. Confirmed
# against a live --debug payload: the API actually returns "paid" (the docs
# say "paidoff", which is wrong/outdated).
SETTLED_INVOICE_STATUSES = {"paid", "voided"}

# Invoice voucherStatus values that don't count as a real invoice yet for the
# Amount/Abrechnungsstatus logic -- a draft is editable/deletable, not sent
# to the customer, so an OC with only a draft invoice linked is treated
# exactly as if it had no invoice at all (still Unbilled/ToInvoice). The
# draft still shows up as a normal row in the Docs table, this only affects
# the main table's computed columns.
IGNORED_INVOICE_STATUSES = {"draft"}

# Status (main table, manual) choices.
STATUS_OPEN = "Offen"
STATUS_CLOSED = "Geschlossen"

# Abrechnungsstatus (main table, automatic) values this script sets, in
# rough workflow order. Unconditionally overwritten every run -- see
# docstring above.
BILLING_STATUS_UNBILLED = "Nicht fakturiert"
BILLING_STATUS_TO_INVOICE = "Zu fakturieren"
BILLING_STATUS_INVOICED = "Fakturiert"
BILLING_STATUS_OVERDUE = "Überfällig"
BILLING_STATUS_PAID = "Bezahlt"
BILLING_STATUS_CANCELLED = "Storniert"
AUTO_BILLING_STATUSES = [
    BILLING_STATUS_UNBILLED,
    BILLING_STATUS_TO_INVOICE,
    BILLING_STATUS_INVOICED,
    BILLING_STATUS_OVERDUE,
    BILLING_STATUS_PAID,
    BILLING_STATUS_CANCELLED,
]

# Versandstatus (main table, manual, like Status) choices -- workflow order.
SHIPPING_STATUS_WAITING = "Wartet"
SHIPPING_STATUS_READY = "Bereit"
SHIPPING_STATUS_DONE = "Erledigt"
SHIPPING_STATUSES = [
    SHIPPING_STATUS_WAITING,
    SHIPPING_STATUS_READY,
    SHIPPING_STATUS_DONE,
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
    billing_status: str = ""
    doc_links: list[DocLink] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_voucher_index(
    client: LexwareClient, voucher_type: str, number_index: dict[str, tuple[str, str]]
) -> dict[str, dict[str, Any]]:
    """client.index_vouchers(), plus populating number_index (voucherNumber
    -> (type, id)) for resolving Manual_Document_Numbers -- a pure in-memory
    pass over the index client.index_vouchers() already fetched, no extra
    API calls.
    """
    index = client.index_vouchers(voucher_type)
    for voucher_id, info in index.items():
        if info["voucherNumber"]:
            number_index[info["voucherNumber"].strip()] = (voucher_type, voucher_id)
    return index


def resolve_manual_links(
    client: LexwareClient,
    manual_field_value: str,
    number_index: dict[str, tuple[str, str]],
    voucher_indexes: dict[str, dict[str, dict[str, Any]]],
    already_linked_ids: set[str],
    ab_number: str,
) -> tuple[list[DocLink], list[str], list[dict[str, Any]]]:
    """Resolves the comma-separated numbers from Manual_Document_Numbers.

    Returns (doc links, warnings, invoice info among them -- used for the
    Amount/Abrechnungsstatus logic). No detail GET needed for any type:
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
                markdown=f"[{number} (manual)]({client.deeplink(voucher_type, voucher_id)})",
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
            client.get_contact_name(contact_id) if contact_id else extract_one_time_name(detail)
        )
        # Only real contacts get a deeplink -- one-time addresses (Einmalkunde)
        # have no contact_id and thus nothing to link to.
        customer_display = (
            f"[{customer_name}]({client.contact_deeplink(contact_id)})"
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
                markdown=f"[{ab_number}]({client.deeplink('orderconfirmation', ab_id)})",
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
            if rel_type not in RESOURCE_INFO:
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
                    markdown=f"[{rel_number}]({client.deeplink(rel_type, rel_id)})",
                    doc_type=document_type_label(rel_type),
                    status=document_status_label(info.get("voucherStatus")) if info else None,
                    date=info.get("voucherDate") if info else None,
                    amount=info.get("totalAmount") if info else None,
                )
            )

        manual_links, manual_warnings, manual_invoices = resolve_manual_links(
            client,
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
                billing_status = BILLING_STATUS_CANCELLED if all_voided else BILLING_STATUS_PAID
            else:
                billing_status = BILLING_STATUS_OVERDUE if has_dunning else BILLING_STATUS_INVOICED
        else:
            # Not billed yet -- show the OC's own total instead of 0. A
            # delivery note existing doesn't mean the goods were actually
            # delivered (Lexware has no such confirmation), just that the
            # document was created -- but it's a strong hint billing is due.
            amount = entry.get("totalAmount")
            billing_status = (
                BILLING_STATUS_TO_INVOICE if has_delivery_note else BILLING_STATUS_UNBILLED
            )

        records.append(
            OrderRecord(
                ab_id=ab_id,
                ab_number=ab_number,
                date=(entry.get("voucherDate") or "")[:10],
                customer=customer_display,
                customer_id=contact_id,
                amount=amount,
                billing_status=billing_status,
                doc_links=doc_links,
                warnings=warnings,
            )
        )
    return records


# Columns this script needs, in creation order: (colId, Grist type, extra
# column fields for creation only, e.g. widgetOptions for Choice/Date -- used
# when the column doesn't exist yet; never applied to an existing column, see
# GristClient.ensure_table_schema). Must stay in sync with to_grist_fields()
# below.
#
# "Date" and "Status"/"Versandstatus"/"Abrechnungsstatus" are real Grist
# Date/Choice columns, not Text -- see date_to_epoch() and
# AUTO_BILLING_STATUSES/SHIPPING_STATUSES for what's written there.
GRIST_SCHEMA: list[tuple[str, str, dict[str, Any] | None]] = [
    ("Lexware_Order_Confirmation_Id", "Text", None),
    ("Order_Confirmation_Number", "Text", None),
    ("Date", "Date", date_options("DD.MM.YYYY")),
    ("Customer", "Text", None),
    ("Customer_Id", "Text", None),
    ("Amount", "Numeric", None),
    ("Status", "Choice", choice_options([STATUS_OPEN, STATUS_CLOSED])),
    ("Versandstatus", "Choice", choice_options(SHIPPING_STATUSES)),
    ("Last_Synced", "Text", None),
    ("Abrechnungsstatus", "Choice", choice_options(AUTO_BILLING_STATUSES)),
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
        logger.warning(
            "could not look up the colRef for %s.Order_Confirmation_Number -- the "
            "reference column will show raw row ids until 'Show column' is set by hand "
            "in Grist.",
            main_table_id,
        )
    return [
        ("Order_Confirmation_Number", f"Ref:{main_table_id}", ref_fields or None),
        ("Document", "Text", markdown_options()),
        ("Document_Type", "Text", None),
        ("Document_Status", "Text", None),
        ("Document_Date", "Date", date_options("DD.MM.YYYY")),
        ("Document_Amount", "Numeric", None),
    ]


def fetch_existing(grist: GristClient, table_id: str) -> dict[str, dict[str, Any]]:
    """Mapping Lexware_Order_Confirmation_Id -> {row_id,
    manual_document_numbers}."""
    result: dict[str, dict[str, Any]] = {}
    for rec in grist.get_records(table_id):
        fields = rec.get("fields", {})
        ab_id = fields.get("Lexware_Order_Confirmation_Id")
        if ab_id:
            result[ab_id] = {
                "row_id": rec["id"],
                "manual_document_numbers": fields.get("Manual_Document_Numbers", "") or "",
            }
    return result


def to_grist_fields(rec: OrderRecord, now_iso: str, is_new: bool) -> dict[str, Any]:
    fields = {
        "Lexware_Order_Confirmation_Id": rec.ab_id,
        "Order_Confirmation_Number": rec.ab_number,
        "Date": date_to_epoch(rec.date),
        "Customer": rec.customer,
        "Customer_Id": rec.customer_id,
        "Amount": rec.amount,
        "Abrechnungsstatus": rec.billing_status,
        "Last_Synced": now_iso,
    }
    if is_new:
        fields["Status"] = STATUS_OPEN
        fields["Versandstatus"] = SHIPPING_STATUS_WAITING
        fields["Manual_Document_Numbers"] = ""
    return fields


def sync_to_grist(
    grist: GristClient,
    table_id: str,
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

    new_ids = grist.add_records(table_id, to_add)
    row_ids.update(zip(to_add_ab_ids, new_ids))
    grist.update_records(table_id, to_update)
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
            logger.warning(
                "no Grist row id for OC %s, skipping its Docs table rows.", rec.ab_number
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


def run_init(grist: GristClient, table_id: str, dry_run: bool) -> None:
    grist.ensure_table_schema(table_id, GRIST_SCHEMA, dry_run)
    print()
    docs_table_id = f"{table_id}{DOCS_TABLE_SUFFIX}"
    docs_schema = build_docs_schema(grist, table_id)
    grist.ensure_table_schema(docs_table_id, docs_schema, dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=CLI_HELP, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--debug", action="store_true", help="print raw API payloads to stderr")
    parser.add_argument("--dry-run", action="store_true", help="don't write anything to Grist")
    parser.add_argument(
        "--init", action="store_true", help="create/update the Grist table, then exit"
    )
    parser.add_argument(
        "--only",
        metavar="AB_NUMBER",
        help="only process this one order confirmation number, for debugging (e.g. --only AB-0042)",
    )
    args = parser.parse_args()
    setup_logging(debug=args.debug)

    if args.init:
        cfg = require_env(*GRIST_ENV)
        grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
        run_init(grist, cfg["GRIST_TABLE_ID"], dry_run=args.dry_run)
        return

    cfg = require_env(*REQUIRED_ENV)
    lexware = LexwareClient(cfg["LEXWARE_API_KEY"])
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    table_id = cfg["GRIST_TABLE_ID"]

    print("Reading existing Grist rows (incl. manual document links) ...")
    existing = fetch_existing(grist, table_id)

    print("Fetching order confirmations and related documents from Lexware ...")
    records = build_records(lexware, existing, only_ab_number=args.only)
    print(f"Found {len(records)} order confirmations.\n")

    for r in records:
        for w in r.warnings:
            print(f"  WARNING: {w}")

    row_ids = sync_to_grist(grist, table_id, records, existing, dry_run=args.dry_run)

    if args.only:
        print(
            "--only is set, skipping the Docs table (it's a full wipe-and-reinsert, "
            "which would delete every other OC's document links)."
        )
    else:
        docs_table_id = f"{table_id}{DOCS_TABLE_SUFFIX}"
        sync_docs_table(grist, docs_table_id, records, row_ids, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
