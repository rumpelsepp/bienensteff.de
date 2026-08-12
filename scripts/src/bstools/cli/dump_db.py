"""
Dumps the Bienensteff product/tracing database from its Grist SaaS document
(articles, fillings, buckets, batches, centrifugations) as one joined JSON
blob to stdout.

The joining itself happens server-side, via Grist's /sql endpoint (SQLite
dialect -- see GristClient.query_sql()), not client-side in Python. The
nested "fillings"/"buckets" arrays (per article/batch) are built
client-side though, in _group_by() -- see there for why.

A batch/article with no matching fillings/buckets gets `[]`, not `null`,
for that key -- fine for consumers (see layouts/_partials/db/*.html):
Hugo's `{{ with }}` treats a zero-length slice the same as nil.

Requires a working `gopass show grist-api-key`.

Usage:
  dump-db > assets/db/db.json
"""

import json
import subprocess
from typing import Any

from bstools.grist import GristClient
from bstools.logging_setup import setup_logging

GRIST_BASE_URL = "https://docs.getgrist.com"
DOCUMENT_ID = "suQKVJDfFYQF"

# One flat query per top-level output section -- no nested subqueries; the
# "fillings"/"buckets" arrays nested under articles/batches are grouped
# client-side afterwards, from these same flat results (see _group_by()).
#
# `a.sku`/`'SKU-' || a.sku` etc.: Artikel rows for internal materials/
# packaging (not sellable products) are prefixed "_" by convention and
# excluded from the products this dump is about.

SKUS_SQL = """
SELECT
  vd.gtin AS gtin,
  vd.color AS color,
  vd.flavor AS flavor,
  vd.gqb_certified AS gqb_certified,
  vd.for_sale AS for_sale,
  vd.in_stock AS in_stock,
  vd.label AS label,
  vd.auto_description AS auto_description,
  p.price AS price,
  p.base_price AS base_price,
  a.sku AS sku,
  a.name AS name,
  a.comment AS comment,
  a.description AS description,
  m.name_short AS brand_name_short,
  m.name AS brand_name,
  m.corporate_claim AS brand_corporate_claim,
  m.hint AS brand_hint,
  m.owner AS brand_owner,
  k.name AS packaging_label,
  k.filling_unit AS packaging_filling_unit,
  k.net_weight AS packaging_net_weight,
  k.packaging_unit AS packaging_name,
  vd.packaging_type AS packaging_type,
  vd.packaging_unit AS packaging_unit,
  'SKU-' || a.sku AS id
FROM Verkaufdetails vd
JOIN Artikel a ON vd.sku = a.id
LEFT JOIN Preise p ON p.sku_id = a.id
JOIN Marken m ON vd.brand_id = m.id
JOIN VKEs k ON vd.sales_unit = k.id
WHERE substr(a.sku, 1, 1) != '_'
"""

FILLINGS_SQL = """
SELECT
  a.sku AS sku,
  f.filling_id AS filling_id,
  date(f.date, 'unixepoch') AS date,
  date(f.best_before_date, 'unixepoch') AS best_before_date,
  f.pieces AS pieces,
  f.comment AS comment,
  f.dib_field AS dib_field,
  f.label AS label,
  f.weight_total AS weight_total,
  l.batch_id AS batch_id,
  f.filling_id AS id
FROM Abfullungen f
LEFT JOIN Tracing_Lose l ON f.batch_id = l.id
LEFT JOIN Artikel a ON f.sku = a.id AND substr(a.sku, 1, 1) != '_'
"""

BUCKETS_SQL = """
SELECT
  e.bucket_id AS bucket_id,
  e.weight AS weight,
  e.moisture AS moisture,
  e.comment AS comment,
  e.done AS done,
  e.date AS date,
  l.batch_id AS batch_id,
  s.centrifugation_id AS centrifugation_id,
  st.location_id AS location_id,
  e.bucket_id AS id
FROM Tracing_Eimer e
LEFT JOIN Tracing_Lose l ON e.batch_id = l.id
LEFT JOIN Tracing_Schleuderungen s ON e.centrifugation_id = s.id
LEFT JOIN Standorte st ON e.location = st.id
"""

BATCHES_SQL = """
SELECT
  l.batch_id AS batch_id,
  l.honey_type AS honey_type,
  l.gqb_compliant AS gqb_compliant,
  l.comment AS comment,
  l.weight AS weight,
  l.avail AS avail,
  l.batch_id AS id
FROM Tracing_Lose l
"""

CENTRIFUGATIONS_SQL = """
SELECT
  s.centrifugation_id AS centrifugation_id,
  date(s.date, 'unixepoch') AS date,
  s.number_of_hives AS number_of_hives,
  s.comment AS comment,
  s.weight AS weight,
  s.weight_per_hive AS weight_per_hive,
  s.centrifugation_id AS id
FROM Tracing_Schleuderungen s
"""


def get_api_key() -> str:
    return (
        subprocess.run(["gopass", "show", "grist-api-key"], check=True, capture_output=True)
        .stdout.decode()
        .strip()
    )


def _coerce_bools(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> None:
    """query_sql() returns Grist Bool columns as SQLite's own 0/1 integers,
    not JSON booleans like get_records() does -- coerces the given columns
    of every row, in place, back to real booleans.
    """
    for row in rows:
        for key in keys:
            row[key] = bool(row[key])


def _coerce_floats(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> None:
    """A whole-number value in a Grist Numeric column comes back from
    query_sql() as a Python int, not a float -- SQLite's dynamic typing
    stores a whole REAL/NUMERIC value using its INTEGER storage class (9.0
    comes back as 9; 9.5 stays 9.5 either way), and query_sql() passes that
    through as-is. Coerces the given columns of every row, in place, to
    float, so a given key's JSON type stays stable across rows instead of
    flipping between int and float depending on whether that particular
    row's value happens to be a whole number. None (an unset cell, or no
    match on the LEFT JOIN that produced it) is left as None.

    Only applied to columns that are consistently float in practice (a
    physical weight essentially never lands on a whole kg for long) --
    *not* blanket-applied to every Grist "Numeric" column, since several of
    those (price, pieces, ...) are just as consistently whole numbers, and
    forcing e.g. `"price": 12.0` where every consumer and this script's own
    history has always emitted `12` would be a regression in the other
    direction.
    """
    for row in rows:
        for key in keys:
            if row[key] is not None:
                row[key] = float(row[key])


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


def main() -> None:
    setup_logging()
    grist = GristClient(GRIST_BASE_URL, get_api_key(), DOCUMENT_ID)

    skus = grist.query_sql(SKUS_SQL)
    _coerce_bools(skus, ("gqb_certified", "for_sale", "in_stock"))
    for row in skus:
        row["brand"] = {
            "name_short": row.pop("brand_name_short"),
            "name": row.pop("brand_name"),
            "corporate_claim": row.pop("brand_corporate_claim"),
            "hint": row.pop("brand_hint"),
            "owner": row.pop("brand_owner"),
        }
        row["packaging"] = {
            "label": row.pop("packaging_label"),
            "filling_unit": row.pop("packaging_filling_unit"),
            "net_weight": row.pop("packaging_net_weight"),
            "name": row.pop("packaging_name"),
            "packaging_type": row.pop("packaging_type"),
            "packaging_unit": row.pop("packaging_unit"),
        }

    fillings = grist.query_sql(FILLINGS_SQL)
    _coerce_floats(fillings, ("weight_total",))

    buckets = grist.query_sql(BUCKETS_SQL)
    _coerce_bools(buckets, ("done",))
    _coerce_floats(buckets, ("weight",))

    batches = grist.query_sql(BATCHES_SQL)
    _coerce_bools(batches, ("gqb_compliant",))
    _coerce_floats(batches, ("weight", "avail"))

    centrifugations = grist.query_sql(CENTRIFUGATIONS_SQL)
    _coerce_floats(centrifugations, ("weight",))

    fillings_by_sku = _group_by(fillings, "sku")
    fillings_by_batch = _group_by(fillings, "batch_id")
    buckets_by_batch = _group_by(buckets, "batch_id")
    for row in skus:
        row["fillings"] = fillings_by_sku.get(row["sku"], [])
    for row in batches:
        row["fillings"] = fillings_by_batch.get(row["batch_id"], [])
        row["buckets"] = buckets_by_batch.get(row["batch_id"], [])

    print(
        json.dumps(
            {
                "articles": skus,
                "fillings": fillings,
                "buckets": buckets,
                "batches": batches,
                "centrifugations": centrifugations,
            }
        )
    )


if __name__ == "__main__":
    main()
