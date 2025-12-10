#!/usr/bin/env -S uv run -qs

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
# ]
# ///

import csv
import datetime
import json
from typing import Any, TypedDict

import httpx

ARTICLE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRf8WK6ia2ziMOZPu6bQes8lMp95AMb0hnK5uzHo9OhhGkHdnQCN4lGkCByWSnzgyaIOM2rad8Dv0R2/pub?gid=287358663&single=true&output=csv"


class Article(TypedDict):
    sku: str
    label: str
    brand: str
    product_name: str
    price: float
    price_per_kg: float
    vke: str
    vpe: str
    in_stock: bool
    

class ArticleList(TypedDict):
    timestamp: str
    articles: list[Article]


def to_bool(s: str) -> bool:
    match s.strip().lower():
        case "true":
            return True
        case "false":
            return False
        case _:
            raise ValueError(f"invalid boolstring {s}")


def fetch_sheet(url: str) -> list[dict[str, Any]]:
    with httpx.Client(follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return list(csv.DictReader(r.text.splitlines(), delimiter=",", quotechar='"'))
    

def main() -> None:
    articles = fetch_sheet(ARTICLE_URL)
    articles = sorted(articles, key=lambda x: x["SKU"])
    articles_out: list[Article] = []
    
    for article in articles:
        if not article["public"].strip().lower() == "true":
            continue

        item: Article = {
            "sku": article["SKU"],
            "label": article["Label"],
            "brand": article["Marke"],
            "product_name": article["Produktname"],
            "price": article["Preis"],
            "price_per_kg": article["Preis / kg"],
            "vke": article["VKE"],
            "vpe": article["VPE"],
            "in_stock": True if article["in stock"] == "TRUE" else False,
        }
        articles_out.append(item)

    out: ArticleList = {
        "articles": articles_out,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
