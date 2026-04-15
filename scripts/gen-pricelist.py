#!/usr/bin/env -S uv run -s

# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///

import json
import datetime
import json
from typing import TypedDict
from pathlib import Path


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


def main() -> None:
    articles = json.loads(Path("./assets/db/db.json").read_text())["articles"]
    articles = sorted(articles, key=lambda x: x["sku"])
    articles_out: list[Article] = []

    for article in articles:
        if not article["for_sale"]:
            continue

        item: Article = {
            "sku": article["sku"],
            "label": article["label"],
            "brand": article["brand"]["name"],
            "product_name": article["name"],
            "price": article["price"],
            "price_per_kg": article["base_price"],
            "vke": article["packaging"]["label"],
            "vpe": article["packaging"]["packaging_unit"],
            "in_stock": article["in_stock"],
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
