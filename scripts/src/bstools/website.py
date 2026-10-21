"""Data the website keeps in the front matter of its pages, read straight
from the Hugo sources of this repository. The front matter is TOML (between
`+++` lines), so the standard library reads it.

The training certificates ("Fachkundenachweise") are `params.nachweise` of
content/über-uns/index.md -- the list the `nachweise` shortcode shows on
the page "Über uns". Each entry: date (YYYY-MM-DD), title, issuer, url
(a path on the website, made absolute here).
"""

import tomllib
from datetime import date
from pathlib import Path
from typing import Any

# scripts/src/bstools/website.py -> the root of the repository.
REPO = Path(__file__).resolve().parents[3]
UEBER_UNS = REPO / "content" / "über-uns" / "index.md"


def base_url() -> str:
    """baseURL of hugo.toml, without a trailing slash."""
    with (REPO / "hugo.toml").open("rb") as f:
        return str(tomllib.load(f).get("baseURL", "")).rstrip("/")


def front_matter(path: Path) -> dict[str, Any]:
    """The TOML front matter (between the two `+++` lines) of a page;
    empty for a page without one."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++"):
        return {}
    return tomllib.loads(text.split("+++", 2)[1])


def nachweise() -> list[dict[str, Any]]:
    """The training certificates, newest first: date (a date), title,
    issuer and url (absolute)."""
    base = base_url()
    entries = front_matter(UEBER_UNS).get("params", {}).get("nachweise") or []
    out = []
    for e in entries:
        try:
            day = date.fromisoformat(str(e.get("date")))
        except ValueError:
            continue
        url = str(e.get("url") or "")
        out.append(
            {
                "date": day,
                "title": str(e.get("title") or ""),
                "issuer": str(e.get("issuer") or ""),
                "url": base + url if url.startswith("/") else url,
            }
        )
    return sorted(out, key=lambda e: e["date"], reverse=True)
