#!/usr/bin/env -S uv run -q

# /// script
# dependencies = [
#     "httpx",
# ]
# ///

import csv
import json
import sqlite3
import sys
from datetime import date, datetime
from typing import Any

import httpx

L_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=319545385&single=true&output=csv"
A_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=321365816&single=true&output=csv"
E_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=614306566&single=true&output=csv"
Z_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=424473037&single=true&output=csv"
STOCK_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=1660941194&single=true&output=csv"


def fetch_sheet(url: str) -> list[dict[str, Any]]:
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return list(csv.DictReader(r.text.splitlines(), delimiter=",", quotechar='"'))


def init_db(cur: sqlite3.Cursor) -> None:
    cur.executescript("""
        CREATE TABLE articles (
            gtin TEXT,
            description TEXT,
            long_description TEXT,
            msrp REAL,
            pu REAL,
            comment TEXT
        ) STRICT;

        CREATE TABLE batches (
            id TEXT PRIMARY KEY,
            closed INTEGER,
            weight REAL,
            sort TEXT,
            comment TEXT
        ) STRICT;

        CREATE TABLE buckets (
            id TEXT PRIMARY KEY,
            centrifugation_id TEXT,
            batch_id TEXT,
            location TEXT,
            weight REAL,
            moisture REAL,
            finished INTEGER,
            comment TEXT
        ) STRICT;

        CREATE TABLE centrifugations (
            id TEXT PRIMARY KEY,
            date TEXT,
            weight REAL,
            comment TEXT
        ) STRICT;

        CREATE TABLE stock_transactions (
            date TEXT,
            best_before TEXT,
            batch_id TEXT,
            gtin TEXT,
            weight REAL,
            quantity REAL,
            comment TEXT,
            dib_field TEXT
        ) STRICT;
    """)


def convert_to_float(raw: str, remove: str) -> float:
    return float(raw.replace(remove, "").replace(",", "."))


def import_articles(cur: sqlite3.Cursor) -> None:
    for article in fetch_sheet(A_URL):
        if article["GTIN"].startswith("0000000"):
            continue
        cur.execute(
            """
            INSERT INTO articles(
                gtin,
                description,
                long_description,
                msrp,
                pu,
                comment
            ) VALUES (?, ?, ?, ?, ?, ?);
        """,
            (
                f"GTIN-{article['GTIN']}",
                article["Bezeichnung"],
                article["Artikelbeschreibung"],
                convert_to_float(article["UVP"], " €"),
                convert_to_float(article["VPE"], " kg"),
                article["Kommentar"],
            ),
        )


def import_buckets(cur: sqlite3.Cursor) -> None:
    for bucket in fetch_sheet(E_URL):
        cur.execute(
            """
            INSERT INTO buckets(
                id,
                centrifugation_id,
                batch_id,
                location,
                weight,
                moisture,
                finished,
                comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
            (
                bucket["Nummer"],
                bucket["Schleuderung"],
                bucket["Los"],
                bucket["Standort"],
                convert_to_float(bucket["Gewicht"], " kg"),
                convert_to_float(bucket["Wassergehalt"], "%") / 100,
                bucket["abgefüllt"] == "x",
                bucket["Kommentar"],
            ),
        )


def import_centrifugations(cur: sqlite3.Cursor) -> None:
    for centrifugation in fetch_sheet(Z_URL):
        cur.execute(
            """
            INSERT INTO centrifugations(
                id,
                date,
                weight,
                comment
            ) VALUES (?, ?, ?, ?);
        """,
            (
                centrifugation["Nummer"],
                datetime.strptime(centrifugation["Schleuderdatum"], "%d.%m.%Y"),
                convert_to_float(centrifugation["Gewicht"], " kg"),
                centrifugation["Kommentar"],
            ),
        )


def import_batches(cur: sqlite3.Cursor) -> None:
    for batch in fetch_sheet(L_URL):
        cur.execute(
            """
            INSERT INTO batches(
                id,
                closed,
                weight,
                sort,
                comment
            ) VALUES (?, ?, ?, ?, ?);
        """,
            (
                batch["Nummer"],
                batch["Closed"] == "x",
                convert_to_float(batch["Gewicht"], " kg"),
                batch["Honigsorte"],
                batch["Kommentar"],
            ),
        )


def import_stock(cur: sqlite3.Cursor) -> None:
    for transaction in fetch_sheet(STOCK_URL):
        cur.execute(
            """
            INSERT INTO stock_transactions(
                date,
                best_before,
                batch_id,
                gtin,
                weight,
                quantity,
                comment,
                dib_field
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
            (
                datetime.strptime(transaction["Datum"], "%d.%m.%Y"),
                datetime.strptime(transaction["MHD"], "%d.%m.%Y"),
                transaction["Los"],
                f"GTIN-{transaction['GTIN']}",
                convert_to_float(transaction["Gesamt"], " kg"),
                int(transaction["Stück"]),
                transaction["Kommentar"],
                transaction["DIB"],
            ),
        )


def gen_json(cur: sqlite3.Cursor) -> str:
    output: dict[str, Any] = {}

    cur.execute("SELECT * FROM articles")
    output["articles"] = [dict(row) for row in cur.fetchall()]
    for article in output["articles"]:
        article["id"] = article["gtin"]
        cur.execute(f"SELECT * from stock_transactions WHERE stock_transactions.gtin = '{article['gtin']}'")
        if (rows := cur.fetchall()) is not None:
            batches = set()
            for row_raw in rows:
                row = dict(row_raw)
                batches.add(row["batch_id"])
            article["batches"] = list(batches)

    cur.execute("SELECT * FROM buckets")
    output["buckets"] = [dict(row) for row in cur.fetchall()]

    cur.execute("SELECT * FROM centrifugations")
    output["centrifugations"] = [dict(row) for row in cur.fetchall()]
    for centrifugation in output["centrifugations"]:
        cur.execute(
            f"SELECT id FROM buckets WHERE buckets.centrifugation_id = '{centrifugation['id']}'"
        )
        centrifugation["buckets"] = [row["id"] for row in cur.fetchall()]
        cur.execute(
            f"SELECT batch_id FROM buckets WHERE buckets.centrifugation_id = '{centrifugation['id']}'"
        )
        centrifugation["batches"] = list(
            {row["batch_id"] for row in cur.fetchall() if row["batch_id"] != ""}
        )

    cur.execute("SELECT * FROM batches")
    output["batches"] = [dict(row) for row in cur.fetchall()]
    for batch in output["batches"]:
        batch["closed"] = batch["closed"] == 1
        cur.execute(f"SELECT id FROM buckets WHERE buckets.batch_id = '{batch['id']}'")
        batch["buckets"] = [row["id"] for row in cur.fetchall()]
        batch["centrifugations"] = []
        for bucket_id in batch["buckets"]:
            cur.execute(
                f"SELECT centrifugation_id FROM buckets WHERE buckets.id = '{bucket_id}'"
            )
            if (row := cur.fetchone()) is not None:
                row = dict(row)
                if "centrifugation_id" in row and row["centrifugation_id"]:
                    batch["centrifugations"].append(row["centrifugation_id"])
        batch["centrifugations"] = list(set(batch["centrifugations"]))
        if not batch["centrifugations"]:
            del batch["centrifugations"]

        cur.execute(f"SELECT gtin FROM stock_transactions WHERE stock_transactions.batch_id = '{batch['id']}'")
        batch["articles"] = list(set([dict(row)["gtin"] for row in cur.fetchall()]))

    return json.dumps(output, indent=4)


def main() -> None:
    sqlite3.register_adapter(date, lambda val: val.isoformat())
    sqlite3.register_adapter(datetime, lambda val: val.isoformat())
    sqlite3.register_converter("date", lambda val: date.fromisoformat(val.decode()))
    sqlite3.register_converter(
        "datetime", lambda val: datetime.fromisoformat(val.decode())
    )

    with sqlite3.connect(
        ":memory:",
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    ) as db:
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        init_db(cur)
        import_articles(cur)
        import_buckets(cur)
        import_centrifugations(cur)
        import_batches(cur)
        import_stock(cur)

        db.commit()

        print(gen_json(cur))
        cur.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
