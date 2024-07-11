#!/usr/bin/env python3

import csv
import json
import sqlite3
import sys
from datetime import date, datetime
from typing import Any

import httpx

L_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=319545385&single=true&output=csv"
A_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=1094250359&single=true&output=csv"
E_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=614306566&single=true&output=csv"
Z_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=424473037&single=true&output=csv"


def fetch_sheet(url: str) -> list[dict[str, Any]]:
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return list(csv.DictReader(r.text.splitlines(), delimiter=",", quotechar='"'))


def init_db(cur: sqlite3.Cursor) -> None:
    cur.executescript("""
        CREATE TABLE buckets (
            id TEXT PRIMARY KEY,
            extraction_id TEXT,
            batch_id TEXT,
            location TEXT,
            weight REAL,
            moisture REAL,
            finished INTEGER,
            comment TEXT
        ) STRICT;

        CREATE TABLE extractions (
            id TEXT PRIMARY KEY,
            date TEXT,
            weight REAL,
            comment TEXT
        ) STRICT;

        CREATE TABLE batches (
            id TEXT PRIMARY KEY,
            closed INTEGER,
            weight REAL,
            sort TEXT,
            comment TEXT
        ) STRICT;

        CREATE TABLE fillings (
            id TEXT PRIMARY KEY,
            batch_id TEXT,
            date TEXT,
            bbd TEXT,
            description TEXT,
            weight REAL,
            container REAL,
            price REAL,
            glass_info JSON ,
            comment TEXT
        );
    """)


def import_buckets(cur: sqlite3.Cursor) -> None:
    for bucket in fetch_sheet(E_URL):
        cur.execute(
            """
            INSERT INTO buckets(
                id,
                extraction_id,
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
                float(bucket["Gewicht"].replace(" kg", "").replace(",", ".")),
                float(bucket["Wassergehalt"].replace("%", "").replace(",", ".")) / 100,
                bucket["abgefüllt"] == "x",
                bucket["Kommentar"],
            ),
        )


def import_extractions(cur: sqlite3.Cursor) -> None:
    for extraction in fetch_sheet(Z_URL):
        cur.execute(
            """
            INSERT INTO extractions(
                id,
                date,
                weight,
                comment
            ) VALUES (?, ?, ?, ?);
        """,
            (
                extraction["Nummer"],
                datetime.strptime(extraction["Schleuderdatum"], "%d.%m.%Y"),
                float(extraction["Gewicht"].replace(" kg", "").replace(",", ".")),
                extraction["Kommentar"],
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
                float(batch["Gewicht"].replace(" kg", "").replace(",", ".")),
                batch["Honigsorte"],
                batch["Kommentar"],
            ),
        )


def import_fillings(cur: sqlite3.Cursor) -> None:
    for filling in fetch_sheet(A_URL):
        if "1970" in filling["Nummer"]:
            continue

        glass_info = {"type": filling["Glastyp"]}
        if glass_info["type"] == "DIB":
            glass_info["id_prefix"] = filling["KN Präfix"]
            glass_info["id_start"] = int(filling["KN Start"])
            glass_info["id_end"] = int(filling["KN End"])

        cur.execute(
            """
            INSERT INTO fillings(
                id,
                batch_id,
                date,
                bbd,
                description,
                weight,
                container,
                price,
                glass_info,
                comment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
            (
                filling["Nummer"],
                filling["Los"],
                datetime.strptime(filling["Abfülldatum"], "%d.%m.%Y"),
                datetime.strptime(filling["MHD"], "%d.%m.%Y"),
                filling["Bezeichnung"],
                float(filling["Gewicht"].replace(" kg", "").replace(",", ".")),
                float(filling["Gebinde"].replace(" kg", "").replace(",", ".")),
                float(filling["Preis / kg"].replace(" €", "").replace(",", ".")),
                json.dumps(glass_info),
                filling["Kommentar"],
            ),
        )


def gen_json(cur: sqlite3.Cursor) -> str:
    output: dict[str, Any] = {}

    cur.execute("SELECT * FROM buckets")
    output["buckets"] = [dict(row) for row in cur.fetchall()]

    cur.execute("SELECT * FROM extractions")
    output["extractions"] = [dict(row) for row in cur.fetchall()]
    for extraction in output["extractions"]:
        cur.execute(f"SELECT id FROM buckets WHERE buckets.extraction_id = '{extraction['id']}'")
        extraction["buckets"] = [row["id"] for row in cur.fetchall()]
        cur.execute(
            f"SELECT batch_id FROM buckets WHERE buckets.extraction_id = '{extraction['id']}'"
        )
        extraction["batches"] = list(
            {row["batch_id"] for row in cur.fetchall() if row["batch_id"] != ""}
        )

    cur.execute("SELECT * FROM batches")
    output["batches"] = [dict(row) for row in cur.fetchall()]
    for batch in output["batches"]:
        cur.execute(f"SELECT id FROM fillings WHERE fillings.batch_id = '{batch['id']}'")
        batch["fillings"] = [row["id"] for row in cur.fetchall()]
        batch["closed"] = batch["closed"] == 1
        cur.execute(
            f"SELECT id FROM buckets WHERE buckets.batch_id = '{batch['id']}'"
        )
        batch["buckets"] = [row["id"] for row in cur.fetchall()]
        batch["extractions"] = []
        for bucket_id in batch["buckets"]:
            cur.execute(
                f"SELECT extraction_id FROM buckets WHERE buckets.id = '{bucket_id}'"
            )
            if (row := cur.fetchone()) is not None:
                row = dict(row)
                if "extraction_id" in row and row["extraction_id"]:
                    batch["extractions"].append(row["extraction_id"])
        batch["extractions"] = list(set(batch["extractions"]))
        if not batch["extractions"]:
            del batch["extractions"]
            

    cur.execute("SELECT * FROM fillings")
    output["fillings"] = [dict(row) for row in cur.fetchall()]
    for filling in output["fillings"]:
        cur.execute(f"SELECT sort FROM batches WHERE batches.id = '{filling['batch_id']}'")
        filling["sort"] = cur.fetchone()["sort"]
        if info := filling["glass_info"]:
            filling["glass_info"] = json.loads(info)

    return json.dumps(output, indent=4)


def main() -> None:
    sqlite3.register_adapter(date, lambda val: val.isoformat())
    sqlite3.register_adapter(datetime, lambda val: val.isoformat())
    sqlite3.register_converter("date", lambda val: date.fromisoformat(val.decode()))
    sqlite3.register_converter("datetime", lambda val: datetime.fromisoformat(val.decode()))

    with sqlite3.connect(
        ":memory:",
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    ) as db:
        db.row_factory = sqlite3.Row
        cur = db.cursor()
        init_db(cur)
        import_buckets(cur)
        import_extractions(cur)
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
