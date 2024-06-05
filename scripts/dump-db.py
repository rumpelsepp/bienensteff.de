#!/usr/bin/env python3

import csv
import json
from urllib.request import urlopen
from typing import Any


def fetch_sheet(url: str) -> dict[str, Any]:
    with urlopen(url) as f:
        raw_data = f.read().decode()
        data = csv.DictReader(raw_data.splitlines(), delimiter=',', quotechar='"')

        return [row for row in data if not row["Nummer"].startswith("A-1970")]



def main():
    data = fetch_sheet("https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=1094250359&single=true&output=csv")
    print(json.dumps(data))



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
