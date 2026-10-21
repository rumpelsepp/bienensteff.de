"""The honey records in Grist -- colonies, locations, centrifugations,
buckets, batches, analyses, fillings, cleaning log and treatment book -- read
whole and joined in Python, for the reports `bscli abfuellungen` and
`bscli eigenkontrolle`.

The tables are small, so they come in with get_records() and are joined
here: no SQL joins on Ref columns, which can drop rows for legacy cells (see
GristClient.query_sql()). Dates become datetime.date, Ref cells stay row
ids, a formula error or an empty cell becomes None.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from bstools import geo
from bstools.grist import GristClient
from bstools.pdf import number

Row = dict[str, Any]

# Locations that stand for no place of their own, e.g. "ALLE" (all
# locations together) on buckets that were extracted from several.
GENERIC_LOCATIONS = {"ALLE"}


def to_date(value: Any) -> date | None:
    """A Grist Date cell (Unix seconds, UTC midnight) as a date."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return datetime.fromtimestamp(value, UTC).date()


def ref(value: Any) -> int | None:
    """A Ref cell as row id; None when empty (0) or not a number."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value else None


def refs(value: Any) -> list[int]:
    """A RefList cell (["L", 1, 2] in the API) as row ids; a plain Ref
    cell gives a list of one, an empty cell an empty list."""
    if isinstance(value, list) and value[:1] == ["L"]:
        return [v for v in value[1:] if ref(v)]
    return [r] if (r := ref(value)) else []


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def choices(value: Any) -> list[str]:
    """A ChoiceList cell (["L", "a", "b"] in the API) as its choices."""
    if isinstance(value, list) and value[:1] == ["L"]:
        return [text(v) for v in value[1:] if text(v)]
    return []


def ids(values: list[int | None]) -> list[int]:
    """The row ids among `values`, each once, sorted."""
    return sorted({v for v in values if v is not None})


def number_or_zero(value: Any) -> float:
    return number(value) or 0.0


@dataclass
class Records:
    """All tables, each as {row id: fields}, plus `date` filled in where
    the table has one."""

    standorte: dict[int, Row] = field(default_factory=dict)
    voelker: dict[int, Row] = field(default_factory=dict)
    schleuderungen: dict[int, Row] = field(default_factory=dict)
    eimer: dict[int, Row] = field(default_factory=dict)
    lose: dict[int, Row] = field(default_factory=dict)
    analysen: dict[int, Row] = field(default_factory=dict)
    abfuellungen: dict[int, Row] = field(default_factory=dict)
    artikel: dict[int, Row] = field(default_factory=dict)
    # Artikel row id -> GQB certified, from Verkaufdetails.
    artikel_gqb: dict[int, bool] = field(default_factory=dict)
    reinigung: dict[int, Row] = field(default_factory=dict)
    bestandsbuch: dict[int, Row] = field(default_factory=dict)
    # Location row id -> its position, resolved on first use (see lage()).
    lagen: dict[int, geo.Lage | None] = field(default_factory=dict)

    def standort(self, row_id: int | None) -> int | None:
        """The location as row id; None when empty or generic ("ALLE")."""
        s = self.standorte.get(row_id or 0)
        if not s or text(s.get("location_id")) in GENERIC_LOCATIONS:
            return None
        return row_id

    def lage(self, row_id: int) -> geo.Lage | None:
        """Position of a location from its BayernAtlas link (`position`,
        else the centre of `circle`); looked up once per run."""
        if row_id not in self.lagen:
            s = self.standorte.get(row_id, {})
            link = text(s.get("position")) or text(s.get("circle"))
            self.lagen[row_id] = geo.lage(link) if link else None
        return self.lagen[row_id]

    def volk_am(self, bn: Any, day: date | None) -> Row | None:
        """The colony living on floor number `bn` that day (from its
        creation up to, not including, its dissolution); None if none."""
        if not bn or day is None:
            return None
        for v in self.voelker.values():
            if (
                v.get("BN") == bn
                and v["von"]
                and v["von"] <= day
                and (not v["bis"] or day < v["bis"])
            ):
                return v
        return None

    def standort_name(self, row_id: int | None) -> str:
        s = self.standorte.get(row_id or 0)
        return text(s.get("name")) or text(s.get("location_id")) if s else ""

    def artikel_nummer(self, row_id: int | None) -> str:
        """Artikel.sku, the Lexware article number."""
        a = self.artikel.get(row_id or 0)
        return text(a.get("sku")) if a else ""

    def los_nummer(self, row_id: int | None) -> str:
        los = self.lose.get(row_id or 0)
        return text(los.get("batch_id")) if los else ""


def _table(grist: GristClient, table_id: str, date_column: str | None = None) -> dict[int, Row]:
    rows: dict[int, Row] = {}
    for rec in grist.get_records(table_id):
        fields = dict(rec.get("fields", {}))
        if date_column:
            fields["date"] = to_date(fields.get(date_column))
        rows[rec["id"]] = fields
    return rows


def load(grist: GristClient) -> Records:
    r = Records(
        standorte=_table(grist, "Standorte"),
        voelker=_table(grist, "Volker"),
        schleuderungen=_table(grist, "Tracing_Schleuderungen", "date"),
        eimer=_table(grist, "Tracing_Eimer"),
        lose=_table(grist, "Tracing_Lose"),
        analysen=_table(grist, "Tracing_Analysen"),
        abfuellungen=_table(grist, "Abfullungen", "date"),
        artikel=_table(grist, "Artikel"),
        reinigung=_table(grist, "Reinigungsprotokoll", "Datum"),
        bestandsbuch=_table(grist, "Bestandsbuch", "Datum"),
    )
    for v in grist.get_records("Verkaufdetails"):
        fields = v.get("fields", {})
        if sku := ref(fields.get("sku")):
            r.artikel_gqb[sku] = bool(fields.get("gqb_certified"))
    for e in r.eimer.values():
        s = r.schleuderungen.get(ref(e.get("centrifugation_id")) or 0)
        e["date"] = s["date"] if s else None
    for v in r.voelker.values():
        v["von"] = to_date(v.get("erstellt_am"))
        v["bis"] = to_date(v.get("aufgelost_am"))
    for a in r.abfuellungen.values():
        a["mhd"] = to_date(a.get("best_before_date"))
        a["kg"] = number(a.get("weight_total"))
        a["stueck"] = number(a.get("pieces"))
    return r


def in_window(d: date | None, start: date, end: date) -> bool:
    return d is not None and start <= d <= end
