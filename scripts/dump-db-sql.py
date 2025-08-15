#!/usr/bin/env -S uv run -qs

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
# ]
# ///

import csv
import json
import sqlite3
from datetime import date, datetime
from typing import Any

import httpx

LOS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=319545385&single=true&output=csv"
ARTICLE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=287358663&single=true&output=csv"
EIMER_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=614306566&single=true&output=csv"
SCHLEUDERUNG_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=424473037&single=true&output=csv"
ABFUELLUNG_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=137162969&single=true&output=csv"


def fetch_sheet(url: str) -> list[dict[str, Any]]:
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return list(csv.DictReader(r.text.splitlines(), delimiter=",", quotechar='"'))


def init_db(cur: sqlite3.Cursor) -> None:
    cur.executescript("""
        CREATE TABLE articles (
            sku TEXT PRIMARY KEY,
            gtin TEXT,
            name TEXT,
            label TEXT,
            brand TEXT,
            brand_short TEXT,
            description TEXT,
            hint TEXT,
            marketing_note TEXT,
            brand_owner TEXT,
            comment TEXT,
            filling_quantity TEXT,
            filling_unit TEXT
        ) STRICT;

        CREATE TABLE batches (
            id TEXT PRIMARY KEY,
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

        CREATE TABLE fillings (
            id TEXT PRIMARY KEY,
            date TEXT,
            best_before TEXT,
            batch_id TEXT,
            sku TEXT,
            weight REAL,
            quantity REAL,
            comment TEXT,
            dib_field TEXT
        ) STRICT;
    """)


def convert_to_float(raw: str, remove: str) -> float:
    return float(raw.replace(remove, "").replace(",", "."))


def import_articles(cur: sqlite3.Cursor) -> None:
    for article in fetch_sheet(ARTICLE_URL):
        cur.execute(
            """
            INSERT INTO articles(
                sku,
                gtin,
                name,
                label,
                brand,
                brand_short,
                description,
                hint,
                marketing_note,
                brand_owner,
                comment,
                filling_quantity,
                filling_unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
            (
                article["SKU"],
                article["GTIN"],
                article["Produktname"],
                article["Label"],
                article["Marke"],
                article["Marke (kurz)"],
                article["Beschreibung"],
                article["Produkthinweis"],
                article["Marketingbotschaft"],
                article["Markeninhaber"],
                article["Kommentar"],
                article["Nettofüllmenge"],
                article["Einheit"],
            ),
        )


def import_buckets(cur: sqlite3.Cursor) -> None:
    for bucket in fetch_sheet(EIMER_URL):
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
                bucket["verwertet"] == "x",
                bucket["Kommentar"],
            ),
        )


def import_centrifugations(cur: sqlite3.Cursor) -> None:
    for centrifugation in fetch_sheet(SCHLEUDERUNG_URL):
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
    for batch in fetch_sheet(LOS_URL):
        cur.execute(
            """
            INSERT INTO batches(
                id,
                weight,
                sort,
                comment
            ) VALUES (?, ?, ?, ?);
        """,
            (
                batch["Nummer"],
                convert_to_float(batch["Gewicht"], " kg"),
                batch["Honigsorte"],
                batch["Kommentar"],
            ),
        )


def import_fillings(cur: sqlite3.Cursor) -> None:
    for filling in fetch_sheet(ABFUELLUNG_URL):
        cur.execute(
            """
            INSERT INTO fillings(
                id,
                date,
                best_before,
                batch_id,
                sku,
                weight,
                quantity,
                comment,
                dib_field
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
            (
                filling["Nummer"],
                datetime.strptime(filling["Datum"], "%d.%m.%Y"),
                datetime.strptime(filling["MHD"], "%d.%m.%Y"),
                filling["Los"],
                filling["SKU"],
                convert_to_float(filling["Gesamt"], " kg"),
                int(filling["Stück"]),
                filling["Kommentar"],
                filling["DIB"],
            ),
        )


def gen_json(cur: sqlite3.Cursor) -> str:
    output: dict[str, Any] = {}

    cur.execute("SELECT * FROM articles")

    res = []
    for article in [dict(row) for row in cur.fetchall()]:
        article["id"] = f"SKU-{article['sku']}"

        cur.execute(f"SELECT * from fillings WHERE fillings.sku = '{article['sku']}'")
        if (rows := cur.fetchall()) is not None:
            fillings = []
            for row_raw in rows:
                fillings.append(dict(row_raw))
            article["fillings"] = fillings
        res.append(article)
    
    res = list(filter(lambda a: ("fillings" in a and a["fillings"]), res))
    output["articles"] = res
    
    cur.execute("SELECT * FROM buckets")
    res = []
    for bucket in [dict(row) for row in cur.fetchall()]:
        cur.execute(f"SELECT * FROM centrifugations WHERE centrifugations.id = '{bucket['centrifugation_id']}'")
        if centrifugations := [dict(row) for row in cur.fetchall()]:
            bucket["centrifugation"] = centrifugations[0]
        cur.execute(f"SELECT * FROM batches WHERE batches.id = '{bucket['batch_id']}'")
        if batches := [dict(row) for row in cur.fetchall()]:
            bucket["batch"] = batches[0]
        res.append(bucket)
    output["buckets"] = res

    cur.execute("SELECT * FROM centrifugations")
    res = []
    for centrifugation in [dict(row) for row in cur.fetchall()]:
        cur.execute(
            f"SELECT DISTINCT * FROM buckets WHERE buckets.centrifugation_id = '{centrifugation['id']}'"
        )
        centrifugation["buckets"] = [dict(row) for row in cur.fetchall()]
        res.append(centrifugation)

    output["centrifugations"] = res

    cur.execute("SELECT * FROM batches")
    res = []
    for batch in [dict(row) for row in cur.fetchall()]:
        cur.execute(
            f"SELECT DISTINCT * FROM buckets WHERE buckets.batch_id = '{batch['id']}'"
        )
        batch["buckets"] = [dict(row) for row in cur.fetchall()]

        cur.execute(
            f"SELECT DISTINCT * FROM fillings WHERE fillings.batch_id = '{batch['id']}'"
        )
        batch["fillings"] = [dict(row) for row in cur.fetchall()]
        res.append(batch)
    
    output["batches"] = res

    cur.execute("SELECT * FROM fillings")
    res = []
    for filling in [dict(row) for row in cur.fetchall()]:
        res.append(filling)

    output["fillings"] = res

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
        import_fillings(cur)

        db.commit()

        print(gen_json(cur))
        cur.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
