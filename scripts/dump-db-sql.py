#!/usr/bin/env python3

import csv
import json
from datetime import datetime
from urllib.request import urlopen
from typing import Any


LOSE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=319545385&single=true&output=csv"
ABF_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=1094250359&single=true&output=csv"
EIMER_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=614306566&single=true&output=csv"


def fetch_sheet(url: str) -> dict[str, Any]:
    with urlopen(url) as f:
        raw_data = f.read().decode()
        return csv.DictReader(raw_data.splitlines(), delimiter=",", quotechar='"')


def fetch_abf() -> dict[str, Any]:
    raw_data = fetch_sheet(ABF_URL)
    data = []

    for raw_row in raw_data:
        if raw_row["Nummer"].startswith("A-1970"):
            continue

        row = {}
        for k, v in raw_row.items():
            match k:
                case "Abfülldatum" | "Schleuderdatum" | "MHD":
                    dt = datetime.strptime(v, "%d.%m.%Y")
                    row[k] = dt.isoformat()
                case _:
                    row[k.replace(" ", "_")] = v

        data.append(row)

    data.sort(key=lambda x: datetime.fromisoformat(x["MHD"]), reverse=True)
    return data


def fetch_lose() -> dict[str, Any]:
    raw_data = fetch_sheet(LOSE_URL)
    data = []

    for raw_row in raw_data:
        row = {}
        for k, v in raw_row.items():
            match k:
                case "Schleuderdatum":
                    dt = datetime.strptime(v, "%d.%m.%Y")
                    row[k] = dt.isoformat()
                case _:
                    row[k.replace(" ", "_")] = v
        data.append(row)
    return data


def fetch_eimer() -> dict[str, Any]:
    raw_data = fetch_sheet(EIMER_URL)
    data = []

    for raw_row in raw_data:
        row = {}
        for k, v in raw_row.items():
            match k:
                case "Datum":
                    dt = datetime.strptime(v, "%d.%m.%Y")
                    row[k] = dt.isoformat()
                case _:
                    row[k.replace(" ", "_")] = v
        data.append(row)
    return data


def lookup_object_index(l: list[dict[str, Any]], key: str, val: Any) -> int:
    for i, obj in enumerate(l):
        if obj[key] == val:
            return i
    raise ValueError


def main():
    data = {
        "lose": fetch_lose(),
        "abf": fetch_abf(),
        "eimer": fetch_eimer(),
    }

    # Add mapping Lose -> Abfüllungen
    mapping = {
        "abf": {},
        "eimer": {},
    }
    for abf in data["abf"]:
        los_id = abf["Los"]
        abf_id = abf["Nummer"]

        if los_id not in mapping["abf"]:
            mapping["abf"][los_id] = []
        if abf_id not in mapping["abf"][los_id]:
            mapping["abf"][los_id].append(abf_id)

    for eimer in data["eimer"]:
        eimer_id = eimer["Nummer"]
        los_id = eimer["Los"]

        if los_id not in mapping["eimer"]:
            mapping["eimer"][los_id] = []
        if eimer_id not in mapping["eimer"][los_id]:
            mapping["eimer"][los_id].append(eimer_id)

    for los in data["lose"]:
        los_id = los["Nummer"]

        if los_id in mapping["abf"] and len(mapping["abf"][los_id]) > 0:
            index = lookup_object_index(data["lose"], "Nummer", los_id)
            data["lose"][index]["Abfüllungen"] = sorted(mapping["abf"][los_id])
        if los_id in mapping["eimer"] and len(mapping["eimer"][los_id]) > 0:
            index = lookup_object_index(data["lose"], "Nummer", los_id)
            data["lose"][index]["Eimer"] = sorted(mapping["eimer"][los_id])

    print(json.dumps(data, indent=4))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
