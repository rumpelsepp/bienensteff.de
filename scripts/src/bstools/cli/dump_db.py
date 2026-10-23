"""
Dumps the Bienensteff product/tracing database from its Grist SaaS document
(articles, fillings, buckets, batches with their laboratory analyses,
centrifugations) as JSON to stdout, for the page of the database
(bundle_src/js/db/, which joins the tables in the browser).

Five flat tables, one row per record, each with its `id` (SKU-…, A-…, E-…,
L-…, S-…) once; a record points to another by that one's id (`article_id`,
`batch_id`, `centrifugation_id`). Only the laboratory analyses are nested,
in their batch.

What is no longer public is left out, by drop_expired() -- the page applies
the same rule on the day it is read, so a dump that has aged a while does
no harm.

The dump is committed to a public repository and holds only what the page
of the database shows: what a record is and what it is connected to. Quantities (weights, numbers of jars and hives), locations,
the water content measured per bucket, stock and sales flags and the
comments say how the business runs and stay in Grist; what is to be said
about a batch in public is its `public_note`. So do the reports of
the laboratory analyses themselves (Tracing_Analysen.document): the dump
names them, by number, issuer and file.

Settings (environment variable, or config file -- see bscli.example.toml):
  GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli dump db > assets/db/db.json
"""

import argparse
import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from bstools import tracing
from bstools.env import require_env
from bstools.grist import GristClient
from bstools.logging_setup import setup_logging

# One flat query per top-level output section -- no nested subqueries; the
# "fillings"/"buckets" arrays nested under articles/batches are grouped
# client-side afterwards, from these same flat results (see _group_by()).
#
# `a.sku`/`'SKU-' || a.sku` etc.: Artikel rows for internal materials/
# packaging (not sellable products) are prefixed "_" by convention and
# excluded from the products this dump is about.

SKUS_SQL = """
SELECT
  'SKU-' || a.sku AS id,
  a.sku AS sku,
  vd.gtin AS gtin,
  vd.label AS label,
  a.name AS name,
  a.description AS description,
  vd.auto_description AS auto_description,
  vd.gqb_certified AS gqb_certified,
  m.name AS brand_name,
  m.hint AS brand_hint,
  m.corporate_claim AS brand_corporate_claim,
  k.name AS packaging_label,
  k.net_weight AS packaging_net_weight,
  k.filling_unit AS packaging_filling_unit,
  vd.packaging_type AS packaging_type,
  vd.packaging_unit AS packaging_unit
FROM Verkaufdetails vd
JOIN Artikel a ON vd.sku = a.id
JOIN Marken m ON vd.brand_id = m.id
JOIN VKEs k ON vd.sales_unit = k.id
WHERE substr(a.sku, 1, 1) != '_'
"""

FILLINGS_SQL = """
SELECT
  f.filling_id AS id,
  'SKU-' || a.sku AS article_id,
  f.label AS label,
  l.batch_id AS batch_id,
  date(f.date, 'unixepoch') AS date,
  date(f.best_before_date, 'unixepoch') AS best_before_date,
  f.dib_field AS dib_field
FROM Abfullungen f
LEFT JOIN Tracing_Lose l ON f.batch_id = l.id
LEFT JOIN Artikel a ON f.sku = a.id AND substr(a.sku, 1, 1) != '_'
"""

BUCKETS_SQL = """
SELECT
  e.bucket_id AS id,
  l.batch_id AS batch_id,
  s.centrifugation_id AS centrifugation_id
FROM Tracing_Eimer e
LEFT JOIN Tracing_Lose l ON e.batch_id = l.id
LEFT JOIN Tracing_Schleuderungen s ON e.centrifugation_id = s.id
"""

BATCHES_SQL = """
SELECT
  l.batch_id AS id,
  l.honey_type AS honey_type,
  l.gqb_compliant AS gqb_compliant,
  l.public_note AS public_note
FROM Tracing_Lose l
"""

CENTRIFUGATIONS_SQL = """
SELECT
  s.centrifugation_id AS id,
  date(s.date, 'unixepoch') AS date
FROM Tracing_Schleuderungen s
"""

# A batch can have several analyses, and one analysis can belong to several
# batches: Tracing_Analysen.batch_id is a RefList. Read through the records
# API rather than /sql -- SQLite holds a RefList cell as JSON text, or as a
# marshalled blob for cells converted from the former Ref column, which SQL
# cannot take apart; the API decodes both (["L", 9, 10]). One row per analysis
# and batch, in the order of the analyses. `water` is a fraction
# (0.165 = 16.5 %). A sample taken before the batch was homogenised
# (before_homogenisation) did not measure the honey as it is sold: its report
# is named, its result is not.


def _analyses(grist: GristClient) -> list[dict[str, Any]]:
    lose = {r["id"]: r.get("fields", {}).get("batch_id") for r in grist.get_records("Tracing_Lose")}
    rows = []
    for an in sorted(grist.get_records("Tracing_Analysen"), key=lambda r: r["id"]):
        f = an.get("fields", {})
        before = bool(f.get("before_homogenisation"))
        for los_id in sorted(tracing.refs(f.get("batch_id"))):
            if los_id not in lose:
                continue
            rows.append(
                {
                    "batch_id": lose[los_id],
                    "water": None if before else f.get("water"),
                    "report_number": f.get("report_number"),
                    "issuer": f.get("issuer"),
                    "file_name": f.get("file_name"),
                    "before_homogenisation": before,
                }
            )
    return rows


def _coerce_bools(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> None:
    """query_sql() returns Grist Bool columns as SQLite's own 0/1 integers,
    not JSON booleans like get_records() does -- coerces the given columns
    of every row, in place, back to real booleans.
    """
    for row in rows:
        for key in keys:
            row[key] = bool(row[key])


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    """Groups `rows` by `row[key]`, dropping `key` itself from each nested
    copy (redundant once it's the dict key) -- the plain-Python equivalent
    of the old polars version's `group_by(key).agg(pl.struct(...))`. Rows
    whose `key` is None (unresolvable/unset reference) are left out, same
    as a SQL join would leave them out.
    """
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        group_key = row[key]
        if group_key is None:
            continue
        groups.setdefault(group_key, []).append({k: v for k, v in row.items() if k != key})
    return groups


def drop_expired(
    db: dict[str, list[dict[str, Any]]], today: date
) -> dict[str, list[dict[str, Any]]]:
    """The tables without what is no longer public on `today`.

    Public is what there may still be a jar of on somebody's shelf: a
    filling past its best-before date is left out, and with it what led to
    nothing but such fillings -- a batch all of whose fillings have
    expired, the buckets of such a batch (or of none) and a centrifugation
    none of whose buckets is left. A batch that has not been filled yet
    stays; articles all stay. bundle_src/js/db/data.ts applies the same
    rule in the browser.
    """
    iso = today.isoformat()
    expired = {f["id"] for f in db["fillings"] if (f["best_before_date"] or "") < iso}
    fillings = [f for f in db["fillings"] if f["id"] not in expired]
    filled = {f["batch_id"] for f in db["fillings"]}
    current = {f["batch_id"] for f in fillings}
    batches = [b for b in db["batches"] if b["id"] in current or b["id"] not in filled]
    batch_ids = {b["id"] for b in batches}
    buckets = [e for e in db["buckets"] if e["batch_id"] in batch_ids]
    centrifugation_ids = {e["centrifugation_id"] for e in buckets}
    centrifugations = [s for s in db["centrifugations"] if s["id"] in centrifugation_ids]
    return {
        "articles": db["articles"],
        "fillings": fillings,
        "buckets": buckets,
        "batches": batches,
        "centrifugations": centrifugations,
    }


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """No options of its own: the output goes to stdout."""


def run(args: argparse.Namespace) -> None:
    setup_logging()
    cfg = require_env("GRIST_BASE_URL", "GRIST_API_KEY", "GRIST_DOC_ID")
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])

    articles = grist.query_sql(SKUS_SQL)
    _coerce_bools(articles, ("gqb_certified",))
    for row in articles:
        row["brand"] = {
            "name": row.pop("brand_name"),
            "hint": row.pop("brand_hint"),
            "corporate_claim": row.pop("brand_corporate_claim"),
        }
        row["packaging"] = {
            "label": row.pop("packaging_label"),
            "net_weight": row.pop("packaging_net_weight"),
            "filling_unit": row.pop("packaging_filling_unit"),
            "type": row.pop("packaging_type"),
            "unit": row.pop("packaging_unit"),
        }

    batches = grist.query_sql(BATCHES_SQL)
    _coerce_bools(batches, ("gqb_compliant",))
    analyses_by_batch = _group_by(_analyses(grist), "batch_id")
    for row in batches:
        row["analyses"] = analyses_by_batch.get(row["id"], [])

    db = drop_expired(
        {
            "articles": articles,
            "fillings": grist.query_sql(FILLINGS_SQL),
            "buckets": grist.query_sql(BUCKETS_SQL),
            "batches": batches,
            "centrifugations": grist.query_sql(CENTRIFUGATIONS_SQL),
        },
        datetime.now(ZoneInfo("Europe/Berlin")).date(),
    )
    for rows in db.values():
        rows.sort(key=lambda row: row["id"])

    # Pretty-printed and UTF-8 rather than \u-escaped, so commits of
    # assets/db/db.json give readable diffs.
    print(json.dumps(db, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_arguments(parser)
    run(parser.parse_args(argv))


if __name__ == "__main__":
    main()
