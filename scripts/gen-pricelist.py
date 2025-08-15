#!/usr/bin/env -S uv run -qs

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
# ]
# ///

import csv
from typing import Any

import httpx

ARTICLE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=287358663&single=true&output=csv"


def fetch_sheet(url: str) -> list[dict[str, Any]]:
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return list(csv.DictReader(r.text.splitlines(), delimiter=",", quotechar='"'))
    

def main() -> None:
    articles = fetch_sheet(ARTICLE_URL)
    
    print("""
| Artikelnummer | Produkt | Marke | <acronym title="Verkaufseinheit">VKE</acronym> | <acronym title="Verpackungseinheit">VPE</acronym> | Preis | Preis / kg |
|----------|-------------|----------------| -- | -- | -- | -- |
    """.strip())
    for article in sorted(articles, key=lambda x: x["SKU"]):
        if article["Preis"] == "":
            continue
        print(f"| {article['SKU']} | {article['Produktname']} | {article['Marke']} | {article['Nettofüllmenge']} {article['Einheit']} | {article['VPE']} | {article['Preis']} | {article['Preis / kg']} |")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
