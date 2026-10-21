"""
Checks the honey records in Grist for nonsense: missing links, duplicate
numbers, formula errors, impossible dates and quantities, GQ conflicts and
gaps the reports (abfuellungen, eigenkontrolle) would trip over. The output
is in German, like the records.

Every check is a class below with a code: a letter for the table and a
number, 1xx for an error ("Fehler": wrong or contradictory, to be fixed),
2xx for a warning ("Hinweis": incomplete, unusual or left as TODO).

  G  all tables        O  Standorte        V  Völker
  S  Schleuderungen    E  Eimer            L  Lose
  N  Analysen          F  Abfüllungen      K  Artikel/Verkaufdetails
  R  Reinigungsprotokoll                   B  Bestandsbuch

`bscli lint --list` lists them all. The exit status is 1 when there is at
least one error (0 otherwise), so the check can stop a script.

A new check: a subclass of Lint (or of RowLint, for one row at a time)
with code, title and table, decorated with @register.

Settings (environment variable, or config file -- see bscli.example.toml):
  GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli lint                       # everything
  bscli lint --year 2026           # only records of 2026 (and those without date)
  bscli lint --errors-only         # without the warnings
  bscli lint --select E F104       # only the bucket checks and F104
  bscli lint --ignore N203 G201    # all but these
  bscli lint --statistics          # how often each check hit
  bscli lint --list                # the checks with their codes
"""

import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Any, ClassVar

from bstools import tracing
from bstools.cli.eigenkontrolle import Year
from bstools.env import require_env
from bstools.grist import GristClient
from bstools.logging_setup import setup_logging
from bstools.pdf import count, number

ERROR = "Fehler"
WARNING = "Hinweis"

# Honigverordnung: at most 20 % water (heather honey 23 %); GQ goes lower
# (Year.water_max).
WATER_MAX_HONIGV = 0.20
WATER_MAX_HONIGV_HEATHER = 0.23

# The tables checked, in the order of the output, with their German name.
TABLES = {
    "Standorte": "Standorte",
    "Volker": "Völker",
    "Tracing_Schleuderungen": "Schleuderungen",
    "Tracing_Eimer": "Eimer",
    "Tracing_Lose": "Lose",
    "Tracing_Analysen": "Analysen",
    "Abfullungen": "Abfüllungen",
    "Artikel": "Artikel",
    "Verkaufdetails": "Verkaufdetails",
    "Reinigungsprotokoll": "Reinigungsprotokoll",
    "Bestandsbuch": "Bestandsbuch",
}

# The column holding the number a record is known by, per table.
NUMBER_COLUMN = {
    "Standorte": "location_id",
    "Volker": "VN",
    "Tracing_Schleuderungen": "centrifugation_id",
    "Tracing_Eimer": "bucket_id",
    "Tracing_Lose": "batch_id",
    "Abfullungen": "filling_id",
    "Artikel": "sku",
}

Row = dict[str, Any]


def fmt_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "–"


def percent(value: float) -> str:
    return f"{count(round(value * 100, 1))} %"


def year_of_number(text: str) -> int | None:
    """The year in a number like E-2026-16."""
    m = re.search(r"(?<!\d)(20\d\d)(?!\d)", text)
    return int(m.group(1)) if m else None


# -- the data -------------------------------------------------------------


class Data:
    """The records, what the checks share (the day of each record, its
    name, the buckets of a batch) and the --year filter."""

    def __init__(
        self,
        r: tracing.Records,
        sales_details: dict[int, Row],
        years: set[int] | None = None,
        today: date | None = None,
    ) -> None:
        self.r = r
        self.sales_details = sales_details
        self.years = years
        self.today = today or date.fromisoformat(time.strftime("%Y-%m-%d"))
        self.tables: dict[str, dict[int, Row]] = {
            "Standorte": r.standorte,
            "Volker": r.voelker,
            "Tracing_Schleuderungen": r.schleuderungen,
            "Tracing_Eimer": r.eimer,
            "Tracing_Lose": r.lose,
            "Tracing_Analysen": r.analysen,
            "Abfullungen": r.abfuellungen,
            "Artikel": r.artikel,
            "Verkaufdetails": sales_details,
            "Reinigungsprotokoll": r.reinigung,
            "Bestandsbuch": r.bestandsbuch,
        }
        self.buckets_of_batch: dict[int, list[Row]] = defaultdict(list)
        for bucket in r.eimer.values():
            if batch_id := tracing.ref(bucket.get("batch_id")):
                self.buckets_of_batch[batch_id].append(bucket)
        # A batch dates from its first centrifugation, an analysis from its
        # batches.
        self.batch_day = {
            i: min((b["date"] for b in self.buckets_of_batch[i] if b["date"]), default=None)
            for i in r.lose
        }

    def day(self, table: str, row_id: int, row: Row) -> date | None:
        if table == "Tracing_Lose":
            return self.batch_day.get(row_id)
        if table == "Tracing_Analysen":
            days = [d for i in tracing.refs(row.get("batch_id")) if (d := self.batch_day.get(i))]
            return min(days, default=None)
        if table == "Volker":
            return row.get("von")
        day = row.get("date")
        return day if isinstance(day, date) else None

    def dissolved(self, colony: Row) -> date | None:
        """The day a colony was dissolved; None while it lives (a planned
        dissolution after today counts as alive)."""
        until = colony.get("bis")
        return until if until and until <= self.today else None

    def relevant(self, table: str, row_id: int, row: Row) -> bool:
        """Whether a record is checked: always without --year and when it
        has no date (a missing date is a finding itself); a colony when it
        lived at some time in those years."""
        if self.years is None:
            return True
        if table == "Volker":
            since, until = row.get("von"), row.get("bis")
            return not since or (
                since.year <= max(self.years) and (not until or until.year >= min(self.years))
            )
        day = self.day(table, row_id, row)
        return day is None or day.year in self.years

    def rows(self, table: str) -> Iterator[tuple[int, Row]]:
        """The rows of a table the --year filter lets through."""
        for row_id, row in self.tables[table].items():
            if self.relevant(table, row_id, row):
                yield row_id, row

    def name(self, table: str, row_id: int, row: Row) -> str:
        """How a record is called in the output: its number, else the date
        or the row id."""
        if (col := NUMBER_COLUMN.get(table)) and (v := row.get(col)) not in (None, ""):
            return f"VN {v}" if table == "Volker" else str(v).strip()
        if table == "Tracing_Analysen" and (report := tracing.text(row.get("report_number"))):
            return report
        if table == "Verkaufdetails" and (
            sku := self.r.artikel_nummer(tracing.ref(row.get("sku")))
        ):
            return sku
        if table == "Bestandsbuch":
            return f"{fmt_date(row.get('date'))} BN {row.get('BN') or '–'}"
        if table == "Reinigungsprotokoll" and row.get("date"):
            return fmt_date(row["date"])
        return f"Zeile {row_id}"


# -- the checks -----------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    lint: type[Lint]
    table: str
    record: str
    detail: str = ""

    @property
    def text(self) -> str:
        return self.lint.title + (f": {self.detail}" if self.detail else "")


class Lint:
    """A check. `code` is unique; 1xx is an error, 2xx a warning. `title`
    is the German text of the output; `table` the Grist table it checks
    (empty for checks across all tables)."""

    code: ClassVar[str]
    title: ClassVar[str]
    table: ClassVar[str] = ""

    @classmethod
    def level(cls) -> str:
        return ERROR if cls.code[1] == "1" else WARNING

    def check(self, data: Data) -> Iterator[Finding]:
        raise NotImplementedError

    def finding(self, record: str, detail: str = "", table: str = "") -> Finding:
        return Finding(type(self), table or self.table, record, detail)


class RowLint(Lint):
    """A check of one row at a time: check_row() returns True or a detail
    text for a finding, False/None/"" for none."""

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str | None:
        raise NotImplementedError

    def check(self, data: Data) -> Iterator[Finding]:
        for row_id, row in data.rows(self.table):
            if result := self.check_row(data, row_id, row):
                detail = result if isinstance(result, str) else ""
                yield self.finding(data.name(self.table, row_id, row), detail)


LINTS: list[type[Lint]] = []


def register[L: type[Lint]](cls: L) -> L:
    """Registers a check."""
    if cls.code in {c.code for c in LINTS}:
        raise ValueError(f"lint code {cls.code} twice")
    LINTS.append(cls)
    return cls


def missing_ref(ref: int | None, target: dict[int, Row]) -> bool | str:
    """For a Ref cell: True when empty, a detail when it points at a row
    that does not exist, "" when fine."""
    if ref is None:
        return True
    return "" if ref in target else f"Zeile {ref} gibt es nicht"


# G -- all tables


@register
class FormulaError(Lint):
    code, title = "G101", "Formelfehler"

    def check(self, data: Data) -> Iterator[Finding]:
        for table in TABLES:
            for row_id, row in data.rows(table):
                for col, value in row.items():
                    if isinstance(value, list) and value[:1] == ["E"]:
                        kind = value[1] if len(value) > 1 else "Fehler"
                        name = data.name(table, row_id, row)
                        yield self.finding(name, f"Spalte {col}, {kind}", table)


@register
class MissingNumber(Lint):
    code, title = "G102", "ohne Nummer"

    def check(self, data: Data) -> Iterator[Finding]:
        for table, col in NUMBER_COLUMN.items():
            for row_id, row in data.rows(table):
                if row.get(col) in (None, ""):
                    yield self.finding(f"Zeile {row_id}", f"Spalte {col}", table)


@register
class DuplicateNumber(Lint):
    code, title = "G103", "Nummer mehrfach vergeben"

    def check(self, data: Data) -> Iterator[Finding]:
        for table, col in NUMBER_COLUMN.items():
            counts = Counter(
                str(v).strip()
                for row in data.tables[table].values()
                if (v := row.get(col)) not in (None, "")
            )
            # With --year: only numbers with a record in those years.
            in_years = {str(row.get(col)).strip() for _, row in data.rows(table)}
            for nr, n in sorted(counts.items()):
                if n > 1 and nr in in_years:
                    name = f"VN {nr}" if table == "Volker" else nr
                    yield self.finding(name, f"{n}×", table)


@register
class OpenTodo(Lint):
    code, title = "G201", "offener Punkt im Kommentar"

    def check(self, data: Data) -> Iterator[Finding]:
        for table in TABLES:
            for row_id, row in data.rows(table):
                for col in ("comment", "Kommentar"):
                    comment = tracing.text(row.get(col))
                    if re.search(r"\bTODO\b|\?\?", comment):
                        yield self.finding(data.name(table, row_id, row), f"„{comment}“", table)


@register
class NumberYearMismatch(Lint):
    code, title = "G202", "Jahr der Nummer passt nicht zum Datum"

    def check(self, data: Data) -> Iterator[Finding]:
        for table in ("Tracing_Schleuderungen", "Tracing_Eimer", "Tracing_Lose", "Abfullungen"):
            for row_id, row in data.rows(table):
                name = data.name(table, row_id, row)
                day = data.day(table, row_id, row)
                if day and (year := year_of_number(name)) and year != day.year:
                    yield self.finding(name, fmt_date(day), table)


# O -- Standorte (locations)


@register
class LocationWithoutMapLink(RowLint):
    code, title, table = "O201", "ohne BayernAtlas-Link, keine Koordinaten", "Standorte"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        r = data.r
        used = any(tracing.ref(v.get("Standort")) == row_id for v in r.voelker.values()) or any(
            tracing.ref(b.get("location")) == row_id for b in r.eimer.values()
        )
        return (
            used
            and tracing.text(row.get("location_id")) not in tracing.GENERIC_LOCATIONS
            and not tracing.text(row.get("position"))
            and not tracing.text(row.get("circle"))
        )


@register
class LocationWithoutName(RowLint):
    code, title, table = "O202", "ohne Namen", "Standorte"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("name"))


# V -- Völker (colonies)


@register
class ColonyWithoutCreationDate(RowLint):
    code, title, table = "V101", "ohne Erstellungsdatum", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("von") is None


@register
class ColonyDissolvedBeforeCreated(RowLint):
    code, title, table = "V102", "aufgelöst vor dem Erstellungsdatum", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        since, until = row.get("von"), row.get("bis")
        if since and until and until < since:
            return f"erstellt {fmt_date(since)}, aufgelöst {fmt_date(until)}"
        return None


@register
class LiveColonyWithoutLocation(RowLint):
    code, title, table = "V103", "lebt, aber ohne Standort", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not data.dissolved(row) and not tracing.ref(row.get("Standort"))


@register
class TwoColoniesOnOneFloor(Lint):
    code, title, table = "V104", "zwei Völker gleichzeitig auf einer Boden-Nr.", "Volker"

    def check(self, data: Data) -> Iterator[Finding]:
        by_floor: dict[Any, list[tuple[int, Row]]] = defaultdict(list)
        for row_id, colony in data.rows(self.table):
            if colony.get("BN") and colony.get("von"):
                by_floor[colony["BN"]].append((row_id, colony))
        for floor, colonies in sorted(by_floor.items()):
            colonies.sort(key=lambda x: x[1]["von"])
            for (ia, a), (ib, b) in pairwise(colonies):
                if a["bis"] is None or b["von"] < a["bis"]:
                    until = f" bis {fmt_date(a['bis'])}" if a["bis"] else ""
                    yield self.finding(
                        f"BN {floor}",
                        f"{data.name(self.table, ia, a)} ab {fmt_date(a['von'])}{until}, "
                        f"{data.name(self.table, ib, b)} ab {fmt_date(b['von'])}",
                    )


@register
class LiveColonyWithoutFloorNumber(RowLint):
    code, title, table = "V201", "lebt, aber ohne Boden-Nr.", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not data.dissolved(row) and not row.get("BN")


@register
class DissolvedWithoutReason(RowLint):
    code, title, table = "V202", "aufgelöst ohne Auflösungsgrund", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        until = data.dissolved(row)
        return fmt_date(until) if until and not tracing.text(row.get("Auflosungsgrund")) else None


@register
class ColonyWithoutType(RowLint):
    code, title, table = "V203", "ohne Typ", "Volker"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("Typ"))


# S -- Schleuderungen (centrifugations)


@register
class CentrifugationWithoutDate(RowLint):
    code, title, table = "S101", "ohne Datum", "Tracing_Schleuderungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("date") is None


@register
class CentrifugationWithoutBuckets(RowLint):
    code, title, table = "S201", "ohne Eimer", "Tracing_Schleuderungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not any(
            tracing.ref(b.get("centrifugation_id")) == row_id for b in data.r.eimer.values()
        )


@register
class CentrifugationWithoutHiveCount(RowLint):
    code, title, table = "S202", "ohne Anzahl Völker", "Tracing_Schleuderungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not number(row.get("number_of_hives"))


# E -- Eimer (buckets)


@register
class BucketWithoutCentrifugation(RowLint):
    code, title, table = "E101", "ohne Schleuderung", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("centrifugation_id")), data.r.schleuderungen)


@register
class BucketWithoutBatch(RowLint):
    code, title, table = "E102", "ohne Los", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("batch_id")), data.r.lose)


@register
class BucketWithoutLocation(RowLint):
    code, title, table = "E103", "ohne Standort", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("location")), data.r.standorte)


@register
class BucketWithoutWeight(RowLint):
    code, title, table = "E104", "ohne Gewicht", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not (number(row.get("weight")) or 0) > 0


@register
class BucketMoistureNotFraction(RowLint):
    code, title, table = "E105", "Wassergehalt nicht als Anteil (0,17 = 17 %)", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        moisture = number(row.get("moisture"))
        return count(moisture) if moisture and moisture > 1 else None


@register
class BucketMoistureAboveHonigV(RowLint):
    code, title, table = "E106", "Wassergehalt über der Honigverordnung", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        moisture = number(row.get("moisture"))
        batch = data.r.lose.get(tracing.ref(row.get("batch_id")) or 0, {})
        heather = "heide" in tracing.text(batch.get("honey_type")).lower()
        limit = WATER_MAX_HONIGV_HEATHER if heather else WATER_MAX_HONIGV
        if moisture and limit < moisture <= 1:
            return f"{percent(moisture)} > {percent(limit)}"
        return None


@register
class BucketUnusuallyHeavy(RowLint):
    code, title, table = "E201", "Gewicht ungewöhnlich hoch", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        weight = number(row.get("weight"))
        return f"{count(weight)} kg" if weight and weight > 40 else None


@register
class BucketMoistureAboveGQ(RowLint):
    code, title, table = "E202", "Wassergehalt über der GQ-Grenze, Los ist GQ", "Tracing_Eimer"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        moisture = number(row.get("moisture"))
        batch_id = tracing.ref(row.get("batch_id")) or 0
        batch = data.r.lose.get(batch_id, {})
        if not moisture or moisture > WATER_MAX_HONIGV or not batch.get("gqb_compliant"):
            return None
        limit = Year.water_max(batch)
        if moisture <= limit:
            return None
        return f"{percent(moisture)} > {percent(limit)}, {data.r.los_nummer(batch_id)}"


# L -- Lose (batches)


def fillings_of(data: Data, batch_id: int) -> list[Row]:
    return [f for f in data.r.abfuellungen.values() if tracing.ref(f.get("batch_id")) == batch_id]


@register
class BatchFilledWithoutBuckets(RowLint):
    code, title, table = "L101", "ohne Eimer, aber mit Abfüllungen", "Tracing_Lose"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not data.buckets_of_batch[row_id] and bool(fillings_of(data, row_id))


@register
class BatchOverfilled(RowLint):
    code, title, table = "L102", "mehr abgefüllt als geerntet", "Tracing_Lose"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        buckets = data.buckets_of_batch[row_id]
        harvested = sum(tracing.number_or_zero(b.get("weight")) for b in buckets)
        filled = sum(f["kg"] or 0 for f in fillings_of(data, row_id))
        if buckets and filled > harvested + 0.5:
            return (
                f"{count(round(filled, 2))} kg abgefüllt, {count(round(harvested, 2))} kg geerntet"
            )
        return None


@register
class BatchWithoutBuckets(RowLint):
    code, title, table = "L201", "ohne Eimer", "Tracing_Lose"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not data.buckets_of_batch[row_id] and not fillings_of(data, row_id)


@register
class BatchWithoutHoneyType(RowLint):
    code, title, table = "L202", "ohne Sorte", "Tracing_Lose"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("honey_type"))


@register
class GQBatchWithoutAnalysis(RowLint):
    code, title, table = "L203", "GQ-Los ohne Analyse nach Homogenisierung", "Tracing_Lose"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return bool(row.get("gqb_compliant")) and not any(
            row_id in tracing.refs(a.get("batch_id")) and not a.get("before_homogenisation")
            for a in data.r.analysen.values()
        )


# N -- Analysen (laboratory analyses)


def gq_results(data: Data, row: Row) -> Iterator[tuple[str, str]]:
    """(batch number, finding) of an analysis after homogenisation against
    the GQ limits, for each of its GQ batches."""
    if row.get("before_homogenisation"):
        return
    for batch_id in tracing.refs(row.get("batch_id")):
        batch = data.r.lose.get(batch_id, {})
        if batch.get("gqb_compliant"):
            for result in Year.pruefung(batch, row)["befunde"]:
                yield data.r.los_nummer(batch_id), result


@register
class AnalysisWithoutBatch(RowLint):
    code, title, table = "N101", "ohne Los", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        batch_ids = tracing.refs(row.get("batch_id"))
        if not batch_ids:
            return True
        unknown = [str(i) for i in batch_ids if i not in data.r.lose]
        return f"Zeile {', '.join(unknown)} gibt es nicht" if unknown else ""


@register
class AnalysisWaterNotFraction(RowLint):
    code, title, table = "N102", "Wassergehalt nicht als Anteil (0,17 = 17 %)", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        water = number(row.get("water"))
        return count(water) if water and water > 1 else None


@register
class DuplicateReport(Lint):
    code, title, table = "N103", "Bericht mehrfach erfasst", "Tracing_Analysen"

    def check(self, data: Data) -> Iterator[Finding]:
        counts = Counter(
            report
            for _, a in data.rows(self.table)
            if (report := tracing.text(a.get("report_number")))
        )
        for report, n in sorted(counts.items()):
            if n > 1:
                yield self.finding(report, f"{n}×, eine Zeile mit allen Losen genügt")


@register
class AnalysisAboveGQLimits(RowLint):
    code, title, table = "N104", "GQ-Grenzwert nicht eingehalten", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str:
        return "; ".join(
            f"{batch}: {result}"
            for batch, result in gq_results(data, row)
            if "nicht erfasst" not in result
        )


@register
class AnalysisWithoutReportNumber(RowLint):
    code, title, table = "N201", "ohne Berichtsnummer", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("report_number"))


@register
class AnalysisWithoutWater(RowLint):
    code, title, table = "N202", "ohne Wassergehalt", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not number(row.get("water"))


@register
class AnalysisWithoutDocument(RowLint):
    code, title, table = "N203", "ohne angehängten Bericht", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not row.get("document")


@register
class AnalysisGQValuesMissing(RowLint):
    code, title, table = "N204", "GQ-Werte nicht erfasst", "Tracing_Analysen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str:
        missing = {
            result.removesuffix(" nicht erfasst")
            for _, result in gq_results(data, row)
            if "nicht erfasst" in result
        }
        return ", ".join(sorted(missing))


# F -- Abfüllungen (fillings)


@register
class FillingWithoutDate(RowLint):
    code, title, table = "F101", "ohne Datum", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("date") is None


@register
class FillingWithoutBatch(RowLint):
    code, title, table = "F102", "ohne Los, nicht rückverfolgbar", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("batch_id")), data.r.lose)


@register
class FillingWithoutArticle(RowLint):
    code, title, table = "F103", "ohne Artikel", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("sku")), data.r.artikel)


@register
class FillingArticleWithoutSalesDetails(RowLint):
    code, title, table = (
        "F104",
        "Artikel ohne Verkaufdetails (kein Gewicht, kein GQ)",
        "Abfullungen",
    )

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        sku = tracing.ref(row.get("sku"))
        with_details = {tracing.ref(v.get("sku")) for v in data.sales_details.values()}
        if sku in data.r.artikel and sku not in with_details:
            return data.r.artikel_nummer(sku)
        return None


@register
class FillingPiecesInvalid(RowLint):
    code, title, table = "F105", "Stückzahl fehlt oder ist nicht ganz", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        pieces = row.get("stueck")
        if not pieces or pieces <= 0:
            return True
        return count(pieces) if pieces != int(pieces) else ""


@register
class FillingWithoutBestBefore(RowLint):
    code, title, table = "F106", "ohne MHD", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("mhd") is None


@register
class FillingBestBeforeNotAfter(RowLint):
    code, title, table = "F107", "MHD nicht nach der Abfüllung", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        best_before, day = row.get("mhd"), row.get("date")
        if best_before and day and best_before <= day:
            return f"MHD {fmt_date(best_before)}, abgefüllt {fmt_date(day)}"
        return None


@register
class GQArticleFromNonGQBatch(RowLint):
    code, title, table = "F108", "GQ-Artikel aus einem Los, das nicht GQ ist", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        batch_id = tracing.ref(row.get("batch_id"))
        sku = tracing.ref(row.get("sku")) or 0
        batch = data.r.lose.get(batch_id or 0)
        if batch is not None and data.r.artikel_gqb.get(sku) and not batch.get("gqb_compliant"):
            return data.r.los_nummer(batch_id)
        return None


@register
class FillingBeforeCentrifugation(RowLint):
    code, title, table = "F109", "abgefüllt vor der Schleuderung des Loses", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        batch_id = tracing.ref(row.get("batch_id")) or 0
        first, day = data.batch_day.get(batch_id), row.get("date")
        if first and day and day < first:
            return (
                f"abgefüllt {fmt_date(day)}, "
                f"{data.r.los_nummer(batch_id)} geschleudert {fmt_date(first)}"
            )
        return None


@register
class FillingBestBeforeTooLate(RowLint):
    code, title, table = "F201", "MHD mehr als 3 Jahre nach der Abfüllung", "Abfullungen"

    def check_row(self, data: Data, row_id: int, row: Row) -> str | None:
        best_before, day = row.get("mhd"), row.get("date")
        if best_before and day and (best_before - day).days > 3 * 366:
            return f"MHD {fmt_date(best_before)}, abgefüllt {fmt_date(day)}"
        return None


# K -- Artikel / Verkaufdetails (articles, sales details)


@register
class DuplicateSalesDetails(Lint):
    code, title, table = "K101", "mehrere Verkaufdetails für einen Artikel", "Verkaufdetails"

    def check(self, data: Data) -> Iterator[Finding]:
        counts = Counter(tracing.ref(v.get("sku")) for v in data.sales_details.values())
        for sku, n in sorted(counts.items(), key=lambda x: x[0] or 0):
            if sku and n > 1:
                yield self.finding(data.r.artikel_nummer(sku) or f"Zeile {sku}", f"{n}×")


@register
class SalesDetailsWithoutArticle(RowLint):
    code, title, table = "K102", "ohne Artikel", "Verkaufdetails"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool | str:
        return missing_ref(tracing.ref(row.get("sku")), data.r.artikel)


# R -- Reinigungsprotokoll (cleaning log)


@register
class CleaningWithoutDate(RowLint):
    code, title, table = "R101", "ohne Datum", "Reinigungsprotokoll"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("date") is None


@register
class InfestationWithoutMeasure(RowLint):
    code, title, table = "R102", "Befall ohne Maßnahme im Kommentar", "Reinigungsprotokoll"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        infested = tracing.text(row.get("Schaedlinge")) == "Befall"
        return infested and not tracing.text(row.get("Kommentar"))


@register
class CleaningWithoutObject(RowLint):
    code, title, table = "R201", "ohne Objekt", "Reinigungsprotokoll"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("Objekt"))


@register
class CleaningWithoutAgents(RowLint):
    code, title, table = "R202", "ohne Mittel (GQ D4)", "Reinigungsprotokoll"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.choices(row.get("Mittel"))


@register
class CleaningWithoutPestCheck(RowLint):
    code, title, table = "R203", "ohne Schädlingsbefund (GQ D5)", "Reinigungsprotokoll"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("Schaedlinge"))


# B -- Bestandsbuch (treatment book)


@register
class TreatmentWithoutDate(RowLint):
    code, title, table = "B101", "ohne Datum", "Bestandsbuch"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return row.get("date") is None


@register
class TreatmentWithoutFloorNumber(RowLint):
    code, title, table = "B102", "ohne Boden-Nr.", "Bestandsbuch"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not row.get("BN")


@register
class TreatmentWithoutColony(RowLint):
    code, title, table = "B103", "kein Volk mit dieser Boden-Nr. an dem Tag", "Bestandsbuch"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        floor, day = row.get("BN"), row.get("date")
        return bool(floor and day) and data.r.volk_am(floor, day) is None


@register
class TreatmentWithoutMedicine(RowLint):
    code, title, table = "B104", "ohne Arzneimittel", "Bestandsbuch"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("Arzneimittel"))


@register
class TreatmentWithoutAmount(RowLint):
    code, title, table = "B201", "ohne Menge", "Bestandsbuch"

    def check_row(self, data: Data, row_id: int, row: Row) -> bool:
        return not tracing.text(row.get("Arzneimenge"))


# -- running and output ---------------------------------------------------


def select_lints(select: list[str] | None, ignore: list[str] | None) -> list[type[Lint]]:
    """The checks to run: codes or code prefixes (E, F1, N203), case
    insensitive."""

    def matches(code: str, patterns: list[str]) -> bool:
        return any(code.startswith(p.upper()) for p in patterns)

    return [
        c
        for c in LINTS
        if (not select or matches(c.code, select)) and not (ignore and matches(c.code, ignore))
    ]


def run_lints(data: Data, lints: list[type[Lint]]) -> list[Finding]:
    return [f for c in lints for f in c().check(data)]


class Style:
    """ANSI colours for the terminal, like ruff: the location bold, the code
    red for an error and yellow for a warning. Off when not wanted."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _sgr(self, codes: str, text: str) -> str:
        return f"\033[{codes}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._sgr("1", text)

    def dim(self, text: str) -> str:
        return self._sgr("2", text)

    def cyan(self, text: str) -> str:
        return self._sgr("36", text)

    def error(self, text: str) -> str:
        return self._sgr("1;31", text)

    def warning(self, text: str) -> str:
        return self._sgr("1;33", text)

    def code(self, lint: type[Lint]) -> str:
        return self.error(lint.code) if lint.level() == ERROR else self.warning(lint.code)


def use_color(choice: str) -> bool:
    """--color auto: on for a terminal, unless NO_COLOR is set; FORCE_COLOR
    turns it on (https://no-color.org, https://force-color.org)."""
    if choice != "auto":
        return choice == "always"
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


def count_label(n: int, level: str) -> str:
    if level == ERROR:
        return f"{n} Fehler"
    return f"{n} {'Hinweis' if n == 1 else 'Hinweise'}"


def render(
    findings: list[Finding], style: Style, errors_only: bool = False, statistics: bool = False
) -> str:
    """One line per finding in the manner of ruff's concise output,

        Eimer:E-2026-03: E102 ohne Los

    sorted by table, record and code; with `statistics` instead how often
    each check hit. Then the totals."""
    errors = sum(f.lint.level() == ERROR for f in findings)
    warnings = len(findings) - errors
    shown = [f for f in findings if not errors_only or f.lint.level() == ERROR]
    order = list(TABLES)
    lines: list[str] = []
    if statistics:
        per_lint = Counter(f.lint for f in shown)
        width = max((len(str(n)) for n in per_lint.values()), default=1)
        lines += [
            f"{per_lint[c]:>{width}}  {style.code(c)}  {c.title}"
            for c in sorted(per_lint, key=lambda c: c.code)
        ]
    else:
        for f in sorted(shown, key=lambda f: (order.index(f.table), f.record, f.lint.code)):
            where = style.bold(TABLES[f.table]) + style.cyan(":") + style.bold(f.record)
            lines.append(f"{where}{style.cyan(':')} {style.code(f.lint)} {f.text}")
    if not findings:
        return "Keine Befunde."
    if lines:
        lines.append("")
    tables = len({f.table for f in findings})
    total = (
        f"{count_label(errors, ERROR)}, {count_label(warnings, WARNING)} "
        f"in {tables} {'Tabelle' if tables == 1 else 'Tabellen'}"
    )
    if errors_only and warnings:
        total += style.dim(" (Hinweise ausgeblendet)")
    lines.append(f"Gefunden: {total}.")
    return "\n".join(lines)


def list_lints(style: Style) -> str:
    """All checks: code, table, title."""
    lines = [
        f"{style.code(c)}  {TABLES.get(c.table, 'alle Tabellen'):<19}  {c.title}"
        for c in sorted(LINTS, key=lambda c: c.code)
    ]
    legend = f"{style.error('1xx')} Fehler, {style.warning('2xx')} Hinweis"
    return "\n".join(lines) + "\n\n" + legend


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--year",
        type=int,
        nargs="+",
        metavar="YYYY",
        help="only records of these years (and those without a date)",
    )
    parser.add_argument("--errors-only", action="store_true", help="hide the warnings")
    parser.add_argument(
        "--select", nargs="+", metavar="CODE", help="only these checks (codes or prefixes: E, F1)"
    )
    parser.add_argument("--ignore", nargs="+", metavar="CODE", help="skip these checks")
    parser.add_argument(
        "--statistics", action="store_true", help="count the findings per check instead"
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="coloured output (default: auto, for a terminal)",
    )
    parser.add_argument("--list", action="store_true", help="list the checks and exit")


def load(grist: GristClient, years: set[int] | None = None) -> Data:
    r = tracing.load(grist)
    sales_details = {
        rec["id"]: dict(rec.get("fields", {})) for rec in grist.get_records("Verkaufdetails")
    }
    return Data(r, sales_details, years)


def run(args: argparse.Namespace) -> None:
    style = Style(use_color(args.color))
    if args.list:
        print(list_lints(style))
        return
    setup_logging()
    cfg = require_env("GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID")
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    data = load(grist, set(args.year) if args.year else None)
    findings = run_lints(data, select_lints(args.select, args.ignore))
    print(render(findings, style, args.errors_only, args.statistics))
    sys.exit(1 if any(f.lint.level() == ERROR for f in findings) else 0)
