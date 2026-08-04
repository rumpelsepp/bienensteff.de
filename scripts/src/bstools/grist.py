"""Shared Grist API client, used by grist_magic (self-hosted-or-SaaS doc sync)
and dump_db (simple table reads from a Grist SaaS document) -- previously
grist_magic had its own copy and dump_db reimplemented a one-off GET via
requests.

One client instance is scoped to one document (doc_id); table_id is passed
per call, since a document has several tables.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from typing import Any

import niquests

# widgetOptions keys that ensure_table_schema() syncs onto an already-existing
# column without asking (unlike a type change, these never touch stored cell
# values, only UI behavior: the choice list for Choice columns, Markdown
# rendering for Text columns). Deliberately excludes "dateFormat" -- a user
# may well have picked a different date format on purpose, so that one's left
# alone once the column already exists.
AUTO_SYNCED_OPTION_KEYS = {"choices", "widget"}


def date_to_epoch(date_str: str | None) -> int | None:
    """ "YYYY-MM-DD" -> Unix timestamp (seconds, UTC midnight), the value
    format Grist's Date columns actually store/expect via the API -- an ISO
    string is not accepted.
    """
    if not date_str:
        return None
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(dt.timestamp())


def choice_options(choices: list[str]) -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"choices": choices})}


def date_options(date_format: str) -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"dateFormat": date_format})}


def markdown_options() -> dict[str, Any]:
    return {"widgetOptions": json.dumps({"widget": "Markdown"})}


def _parse_widget_options(widget_options_raw: Any) -> dict[str, Any]:
    if not widget_options_raw:
        return {}
    try:
        parsed: dict[str, Any] = json.loads(widget_options_raw)
        return parsed
    except TypeError, ValueError:
        return {}


class GristClient:
    def __init__(self, base_url: str, api_key: str, doc_id: str) -> None:
        self._client = niquests.Session(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30.0,
        )
        self.doc_id = doc_id

    @staticmethod
    def _check(resp: niquests.Response) -> None:
        if not resp.ok:
            print(f"Grist API error {resp.status_code}: {resp.text}", file=sys.stderr)
        resp.raise_for_status()

    def get_records(self, table_id: str) -> list[dict[str, Any]]:
        resp = self._client.get(f"/api/docs/{self.doc_id}/tables/{table_id}/records")
        self._check(resp)
        data: dict[str, Any] = resp.json()
        records: list[dict[str, Any]] = data.get("records", [])
        return records

    def add_records(self, table_id: str, records: list[dict[str, Any]]) -> list[int]:
        """Returns the newly assigned row ids, in the same order as `records`."""
        if not records:
            return []
        payload = {"records": [{"fields": r} for r in records]}
        resp = self._client.post(f"/api/docs/{self.doc_id}/tables/{table_id}/records", json=payload)
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
        return [rec["id"] for rec in self.get_records(table_id)]

    def delete_records(self, table_id: str, row_ids: list[int]) -> None:
        if not row_ids:
            return
        resp = self._client.post(
            f"/api/docs/{self.doc_id}/tables/{table_id}/records/delete", json=row_ids
        )
        self._check(resp)

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
        for rec in self.get_records("_grist_Tables"):
            if rec.get("fields", {}).get("tableId") == table_id:
                row_id: int = rec["id"]
                return row_id
        return None

    def get_column_ref(self, table_id: str, col_id: str) -> int | None:
        """Internal row id (colRef) of a column in the _grist_Tables_column
        metadata table -- what a Ref column's visibleCol field points to.
        """
        table_ref = self.get_table_ref(table_id)
        if table_ref is None:
            return None
        for rec in self.get_records("_grist_Tables_column"):
            fields = rec.get("fields", {})
            if fields.get("parentId") == table_ref and fields.get("colId") == col_id:
                row_id: int = rec["id"]
                return row_id
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
        resp = self._client.post(f"/api/docs/{self.doc_id}/tables/{table_id}/columns", json=payload)
        self._check(resp)

    def update_column_fields(self, table_id: str, col_id: str, fields: dict[str, Any]) -> None:
        payload = {"columns": [{"id": col_id, "fields": fields}]}
        resp = self._client.patch(
            f"/api/docs/{self.doc_id}/tables/{table_id}/columns", json=payload
        )
        self._check(resp)

    def ensure_table_schema(
        self,
        table_id: str,
        schema: list[tuple[str, str, dict[str, Any] | None]],
        dry_run: bool = False,
    ) -> None:
        """Creates the table if it doesn't exist yet, or adds whatever
        columns from `schema` are missing on an existing one.

        Existing columns whose type doesn't match are never changed without
        asking first, since a type change can reformat or discard the values
        already in them. A few widgetOptions keys (AUTO_SYNCED_OPTION_KEYS)
        are the one exception that's synced on existing columns too, without
        asking: e.g. a Choice column's declared choice list, or a Text
        column's Markdown-rendering widget -- those only affect UI behavior,
        never a stored cell value.
        """
        print(f"Checking Grist table '{table_id}' in doc {self.doc_id} ...")
        tables = self.list_tables()

        if table_id not in tables:
            print(f"Table '{table_id}' does not exist, creating with {len(schema)} columns ...")
            if dry_run:
                print("--dry-run is set, nothing will be created.")
                return
            self.create_table(table_id, schema)
            print("Table created.")
            return

        print(f"Table '{table_id}' already exists, checking columns ...")
        existing_cols = self.get_columns(table_id)

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
            print(
                "Columns whose choices/widget will be (re-)set: "
                + ", ".join(c for c, _ in options_to_sync)
            )

        if dry_run:
            print("--dry-run is set, nothing will be changed.")
            return

        if missing:
            self.add_columns(table_id, missing)
            print(f"Added {len(missing)} column(s).")

        if mismatched:
            print(
                "\nChanging a column's type can reformat or discard the values "
                "already stored in it, so confirm each one:"
            )
            for col_id, have, want in mismatched:
                answer = (
                    input(f"  Change '{col_id}' from {have!r} to {want!r}? [y/N] ").strip().lower()
                )
                if answer == "y":
                    self.update_column_fields(table_id, col_id, {"type": want})
                    print(f"  Updated {col_id}.")
                else:
                    print(f"  Skipped {col_id} -- writes to it may fail until fixed manually.")

        for col_id, extra in options_to_sync:
            self.update_column_fields(table_id, col_id, extra)
            print(f"Updated options for {col_id}.")
