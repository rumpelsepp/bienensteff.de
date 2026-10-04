"""
Dumps the Bienensteff product/tracing database from its Grist SaaS document
(articles, fillings, buckets, batches with their laboratory analyses,
centrifugations) as one joined JSON blob to stdout.

The joining itself happens server-side, via Grist's /sql endpoint (SQLite
dialect -- see GristClient.query_sql()), not client-side in Python. The
nested "fillings"/"buckets"/"analyses" arrays (per article/batch) are built
client-side though, in _group_by() -- see there for why.

The dump is committed to a public repository and holds only what the pages
of the database show (layouts/db/): what a record is and what it is
connected to. Quantities (weights, numbers of jars and hives), locations,
the water content measured per bucket, stock and sales flags and the
comments say how the business runs and stay in Grist; what is to be said
about a batch in public is its `public_note`. So do the reports of
the laboratory analyses themselves (Tracing_Analysen.document): the dump
names them, by number, issuer and file.

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
  vd.label AS label,
  vd.auto_description AS auto_description,
  a.sku AS sku,
  a.name AS name,
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
  f.dib_field AS dib_field,
  f.label AS label,
  l.batch_id AS batch_id,
  f.filling_id AS id
FROM Abfullungen f
LEFT JOIN Tracing_Lose l ON f.batch_id = l.id
LEFT JOIN Artikel a ON f.sku = a.id AND substr(a.sku, 1, 1) != '_'
"""

BUCKETS_SQL = """
SELECT
  e.bucket_id AS bucket_id,
  l.batch_id AS batch_id,
  s.centrifugation_id AS centrifugation_id,
  e.bucket_id AS id
FROM Tracing_Eimer e
LEFT JOIN Tracing_Lose l ON e.batch_id = l.id
LEFT JOIN Tracing_Schleuderungen s ON e.centrifugation_id = s.id
"""

BATCHES_SQL = """
SELECT
  l.batch_id AS batch_id,
  l.honey_type AS honey_type,
  l.gqb_compliant AS gqb_compliant,
  l.public_note AS public_note,
  l.batch_id AS id
FROM Tracing_Lose l
"""

CENTRIFUGATIONS_SQL = """
SELECT
  s.centrifugation_id AS centrifugation_id,
  date(s.date, 'unixepoch') AS date,
  s.centrifugation_id AS id
FROM Tracing_Schleuderungen s
"""

# A batch can have several analyses. `water` is a fraction (0.165 = 16.5 %).
# A sample taken before the batch was homogenised (before_homogenisation)
# did not measure the honey as it is sold: its report is named, its result
# is not, see main().
ANALYSES_SQL = """
SELECT
  l.batch_id AS batch_id,
  an.water AS water,
  an.report_number AS report_number,
  an.issuer AS issuer,
  an.file_name AS file_name,
  an.before_homogenisation AS before_homogenisation
FROM Tracing_Analysen an
JOIN Tracing_Lose l ON an.batch_id = l.id
ORDER BY an.id
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
    _coerce_bools(skus, ("gqb_certified",))
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

    buckets = grist.query_sql(BUCKETS_SQL)

    batches = grist.query_sql(BATCHES_SQL)
    _coerce_bools(batches, ("gqb_compliant",))

    centrifugations = grist.query_sql(CENTRIFUGATIONS_SQL)

    analyses = grist.query_sql(ANALYSES_SQL)
    _coerce_bools(analyses, ("before_homogenisation",))
    for row in analyses:
        if row["before_homogenisation"]:
            row["water"] = None
    analyses_by_batch = _group_by(analyses, "batch_id")

    fillings_by_sku = _group_by(fillings, "sku")
    fillings_by_batch = _group_by(fillings, "batch_id")
    buckets_by_batch = _group_by(buckets, "batch_id")
    for row in skus:
        row["fillings"] = fillings_by_sku.get(row["sku"], [])
    for row in batches:
        row["fillings"] = fillings_by_batch.get(row["batch_id"], [])
        row["buckets"] = buckets_by_batch.get(row["batch_id"], [])
        row["analyses"] = analyses_by_batch.get(row["batch_id"], [])

    # Pretty-printed and UTF-8 rather than \u-escaped, so commits of
    # assets/db/db.json give readable diffs -- byte-identical to the `jq`
    # pass the justfile used to pipe this through.
    print(
        json.dumps(
            {
                "articles": skus,
                "fillings": fillings,
                "buckets": buckets,
                "batches": batches,
                "centrifugations": centrifugations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
