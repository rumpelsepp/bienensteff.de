#!/usr/bin/env -S uv run -s

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "polars>=1.39.3",
#     "requests>=2.33.1",
# ]
# ///

import json
import subprocess

import polars as pl
import requests


document_id = "suQKVJDfFYQF"
api_key = (
    subprocess.run(["gopass", "show", "grist-api-key"], check=True, capture_output=True)
    .stdout.decode()
    .strip()
)


def fetch_table(table_id: str) -> pl.DataFrame:
    url = f"https://docs.getgrist.com/api/docs/{document_id}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {api_key}"}

    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()
    return (
        pl.DataFrame(data["records"])
        .unnest("fields")
        .select(pl.all().exclude(["created_at", "updated_at"]))
    )


def main() -> None:
    articles_df = fetch_table("Artikel").filter(~pl.col("sku").str.starts_with("_"))
    article_details_df = fetch_table("Verkaufdetails")
    article_brands_df = fetch_table("Marken")
    article_vkes_df = fetch_table("VKEs")

    skus_df = (
        article_details_df.join(articles_df, left_on="sku", right_on="id", how="inner")
        .drop(["id", "sku", "label_right"])
        .rename({"sku_right": "sku"})
        .join(article_brands_df, left_on="brand_id", right_on="id", how="inner")
        .drop(["brand_id"])
        .with_columns(
            [
                pl.struct(
                    [
                        pl.col("name_short"),
                        pl.col("name_right").alias("name"),
                        pl.col("corporate_claim"),
                        pl.col("hint"),
                        pl.col("owner"),
                    ]
                ).alias("brand")
            ]
        )
        .drop("name_short", "name_right", "corporate_claim", "hint", "owner")
        .join(article_vkes_df, left_on="sales_unit", right_on="id", how="inner")
        .drop(["auto_description_enabled"])
        .rename(
            {
                "name_right": "packaging_unit_label",
                "packaging_unit_right": "packaging_unit_name",
            }
        )
        .with_columns(
            [
                pl.struct(
                    [
                        pl.col("packaging_unit_label").alias("label"),
                        pl.col("filling_unit"),
                        pl.col("net_weight"),
                        pl.col("packaging_unit_name").alias("name"),
                        pl.col("packaging_type"),
                        pl.col("packaging_unit"),
                    ]
                ).alias("packaging")
            ]
        )
        .drop(
            [
                "sales_unit",
                "packaging_unit_label",
                "filling_unit",
                "net_weight",
                "packaging_unit_name",
                "packaging_type",
                "packaging_unit",
            ]
        )
    )

    locations_df = fetch_table("Standorte")
    centrifugations_df = fetch_table("Tracing_Schleuderungen").with_columns([
        pl.from_epoch(pl.col("date"), time_unit="s").dt.strftime("%Y-%m-%d").alias("date"),
    ])
    batches_df = fetch_table("Tracing_Lose")
    buckets_df = (
        fetch_table("Tracing_Eimer")
        .join(
            batches_df.select(["id", "batch_id"]),
            left_on="batch_id",
            right_on="id",
            how="left",
        )
        .join(
            centrifugations_df.select(["id", "centrifugation_id"]),
            left_on="centrifugation_id",
            right_on="id",
            how="left",
        )
        .drop(["id", "batch_id", "centrifugation_id"])
        .rename(
            {
                "batch_id_right": "batch_id",
                "centrifugation_id_right": "centrifugation_id",
            }
        )
        .join(
            locations_df.select(["id", "location_id"]),
            left_on="location",
            right_on="id",
            how="left",
        )
        .drop(["location"])
        .with_columns(
            pl.col("bucket_id").alias("id")
        )
    )

    fillings_df = (
        fetch_table("Abfullungen")
        .with_columns(
            [
                pl.from_epoch(pl.col("date"), time_unit="s").dt.strftime("%Y-%m-%d"),
                pl.from_epoch(pl.col("best_before_date"), time_unit="s").dt.strftime("%Y-%m-%d"),
            ]
        )
        .join(
            batches_df.select(["id", "batch_id"]),
            left_on="batch_id",
            right_on="id",
            how="left",
        )
        .drop(["batch_id", "id"])
        .rename({"batch_id_right": "batch_id"})
        .join(
            articles_df.select(["id", "sku"]),
            left_on="sku",
            right_on="id",
            how="left",
        )
        .drop(["sku"])
        .rename({"sku_right": "sku"})
        .with_columns(
            pl.col("filling_id").alias("id")
        )
    )

    fillings_grouped = fillings_df.group_by("sku").agg(
        pl.struct(pl.all().exclude("sku")).alias("fillings")
    )
    skus_df = skus_df.join(fillings_grouped, on="sku", how="left").with_columns((pl.lit("SKU-") + pl.col("sku")).alias("id")).filter(pl.col("fillings").is_not_null())
    
    buckets_agg = (
        buckets_df
        .group_by("batch_id")
        .agg(pl.struct(pl.all()).alias("buckets"))
    )

    fillings_agg = (
        fillings_df
        .group_by("batch_id")
        .agg(pl.struct(pl.all()).alias("fillings"))
    )

    batches_grouped_df = (
        batches_df.join(fillings_agg, on="batch_id", how="left")
        .join(buckets_agg, on="batch_id", how="left")
        .drop("id")
        .with_columns(pl.col("batch_id").alias("id"))
    )

    print(
        json.dumps(
            {
                "articles": skus_df.to_dicts(),
                "fillings": fillings_df.to_dicts(),
                "buckets": buckets_df.to_dicts(),
                "batches": batches_grouped_df.to_dicts(),
                "centrifugations": centrifugations_df.drop("id").with_columns(pl.col("centrifugation_id").alias("id")).to_dicts(),
            },
        )
    )


if __name__ == "__main__":
    main()
