"""
Eigenkontrolle "Geprüfte Qualität – Bayern" for honey, one year, as PDF
(templates/eigenkontrolle.typ): the criteria A1-H2 of the GQ check
(Prüfbericht Honig, GQ-Version 01/25, qualifood.de) with what Grist holds
as evidence for each, boxes to tick, a table for defects and measures and
the signature -- followed by the records themselves as annexes: the
colonies on 31 December (today while the year is running),
locations, harvest, batches with their analyses, fillings, cleaning log,
treatment book and the training certificates (G1, from the website's page
"Über uns", see bstools.website).

What Grist cannot know (hygiene at the hive, labelling, ...) is
left as a line to fill in by hand. The evidence only states what is
recorded; whether a criterion is met is decided when ticking. Notes that
need a look -- a GQ batch without an analysis, water above 18 %, a GQ
article filled from a non-GQ batch -- are printed in bold.

The quantities sold (criterion A9) come from Lexware and are a report of
their own: bscli verkaufszahlen --year YYYY --gqb only.

Settings (environment variable, or config file -- see bscli.example.toml):
  GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID

Usage:
  bscli eigenkontrolle                        # the current year
  bscli eigenkontrolle --year 2025            # Eigenkontrolle_2025.pdf
  bscli eigenkontrolle --year 2024 2025       # one PDF per year
  bscli eigenkontrolle -o ek.pdf --bw
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

from bstools import tracing, website
from bstools.env import require_env
from bstools.grist import GristClient
from bstools.logging_setup import setup_logging
from bstools.pdf import add_print_arguments, count, letterhead, number, render

# GQ Honig: maximum water content, except heather honey (21.4 %).
WATER_MAX = 0.18
WATER_MAX_HEIDE = 0.214
# Invertase (U/kg) and HMF (mg/kg): at least 64 U/kg and at most 15 mg/kg;
# honey naturally low in enzymes (Robinie, Gamander, early flow) passes
# with at least 45 U/kg if HMF is at most 5 mg/kg.
INVERTASE_MIN = 64.0
INVERTASE_MIN_ENZYMSCHWACH = 45.0
HMF_MAX = 15.0
HMF_MAX_ENZYMSCHWACH = 5.0


def d(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def kg(value: float) -> str:
    return f"{count(round(value, 2))} kg"


def percent(value: float) -> str:
    return f"{count(round(value * 100, 1))} %"


def entries(n: int) -> str:
    return f"{n} Eintrag" if n == 1 else f"{n} Einträge"


def note(text: str, warn: bool = False, vorlaeufig: bool = False) -> dict[str, Any]:
    """A line of evidence; `warn` prints it bold, `vorlaeufig` grey and
    italic (an unreliable result, e.g. an analysis before homogenisation)."""
    return {"text": text, "warn": warn, "vorlaeufig": vorlaeufig}


def werte(p: dict[str, Any]) -> str:
    """The values of an analysis (see Year.pruefung) in one line."""
    return f"Wasser {p['wasser']}, Invertase {p['invertase']} U/kg, HMF {p['hmf']} mg/kg"


class Year:
    """The records of one year and what the criteria say about them."""

    def __init__(
        self,
        r: tracing.Records,
        year: int,
        today: date,
        nachweise: list[dict[str, Any]] | None = None,
    ) -> None:
        self.r = r
        self.year = year
        # Training certificates up to the end of the year, newest first.
        self.nachweise = [n for n in nachweise or [] if n["date"].year <= year]
        start, end = date(year, 1, 1), date(year, 12, 31)
        # The colonies on the reference date, 31 December (today, while the
        # year is still running): nuclei are often united late in the year,
        # so a count during the year would include colonies that end up
        # merged. Every type counts -- Typ in Grist says how a colony came
        # about (Flugling, Brutvolk, ...), it is not updated once a colony
        # becomes a production colony.
        self.stichtag = min(end, today)
        end_voelker = self.stichtag
        self.voelker = sorted(
            (
                v
                for v in r.voelker.values()
                if v["von"]
                and v["von"] <= end_voelker
                and (v["bis"] is None or v["bis"] > end_voelker)
            ),
            key=lambda v: (v["von"], v.get("VN") or 0),
        )
        self.schleuderungen = {
            i: s for i, s in r.schleuderungen.items() if tracing.in_window(s["date"], start, end)
        }
        self.eimer = [
            e
            for e in r.eimer.values()
            if tracing.ref(e.get("centrifugation_id")) in self.schleuderungen
        ]
        self.abfuellungen = sorted(
            (f for f in r.abfuellungen.values() if tracing.in_window(f["date"], start, end)),
            key=lambda f: (f["date"], tracing.text(f.get("filling_id"))),
        )
        lose_ids = {tracing.ref(e.get("batch_id")) for e in self.eimer} | {
            tracing.ref(f.get("batch_id")) for f in self.abfuellungen
        }
        self.lose = {i: r.lose[i] for i in sorted(x for x in lose_ids if x in r.lose)}
        self.reinigung = sorted(
            (c for c in r.reinigung.values() if tracing.in_window(c["date"], start, end)),
            key=lambda c: c["date"],
        )
        self.bestandsbuch = sorted(
            (b for b in r.bestandsbuch.values() if tracing.in_window(b["date"], start, end)),
            key=lambda b: (b["date"], b.get("BN") or 0),
        )
        # Locations of each centrifugation: those of its buckets; buckets
        # marked with a generic location ("ALLE") come from all colonies
        # standing somewhere on that day.
        self.ernte_standorte: dict[int, list[int]] = {}
        for i, s in self.schleuderungen.items():
            eimer = [e for e in self.eimer if tracing.ref(e.get("centrifugation_id")) == i]
            own = tracing.ids([r.standort(tracing.ref(e.get("location"))) for e in eimer])
            self.ernte_standorte[i] = own or self.standorte_am(s["date"])
        # All locations of the year: colonies on the reference date and harvest.
        self.standort_ids = tracing.ids(
            [r.standort(tracing.ref(v.get("Standort"))) for v in self.voelker]
            + [x for ids in self.ernte_standorte.values() for x in ids]
        )

    def standorte_am(self, day: date | None) -> list[int]:
        """Locations of the colonies (any type) that stood on `day`."""
        if day is None:
            return []
        return tracing.ids(
            [
                self.r.standort(tracing.ref(v.get("Standort")))
                for v in self.r.voelker.values()
                if v["von"] and v["von"] <= day and (v["bis"] is None or v["bis"] > day)
            ]
        )

    # -- per batch --------------------------------------------------------

    def analysen(self, los_id: int) -> list[dict[str, Any]]:
        """The analyses of a batch, those after homogenisation first. An
        analysis before homogenisation is a sample of single buckets, not of
        the batch: unreliable, shown only for orientation."""
        return sorted(
            (a for a in self.r.analysen.values() if los_id in tracing.refs(a.get("batch_id"))),
            key=lambda a: bool(a.get("before_homogenisation")),
        )

    @staticmethod
    def water_max(los: dict[str, Any]) -> float:
        return (
            WATER_MAX_HEIDE if "heide" in tracing.text(los.get("honey_type")).lower() else WATER_MAX
        )

    @staticmethod
    def pruefung(los: dict[str, Any], a: dict[str, Any]) -> dict[str, Any]:
        """Water, invertase and HMF of an analysis against the GQ limits:
        the values formatted, each with `warn` when outside, and the
        findings as text. A missing value is a finding too; Grist gives an
        empty Numeric cell as 0, and none of the three can be 0."""
        water, inv, hmf = (number(a.get(k)) or None for k in ("water", "invertase", "hmf"))
        befunde = []
        if water is None:
            befunde.append("Wasser nicht erfasst")
        elif water > Year.water_max(los):
            befunde.append(f"Wasser über {percent(Year.water_max(los))}")
        if inv is None or hmf is None:
            befunde.append(
                ", ".join(n for n, v in (("Invertase", inv), ("HMF", hmf)) if v is None)
                + " nicht erfasst"
            )
        if hmf is not None and hmf > HMF_MAX:
            befunde.append(f"HMF über {count(HMF_MAX)} mg/kg")
        if inv is not None and inv < INVERTASE_MIN:
            if inv < INVERTASE_MIN_ENZYMSCHWACH:
                befunde.append(f"Invertase unter {count(INVERTASE_MIN_ENZYMSCHWACH)} U/kg")
            elif hmf is None or hmf > HMF_MAX_ENZYMSCHWACH:
                befunde.append(
                    f"Invertase unter {count(INVERTASE_MIN)} U/kg; als enzymschwacher Honig "
                    f"nur mit HMF bis {count(HMF_MAX_ENZYMSCHWACH)} mg/kg zulässig"
                )
        return {
            "wasser": percent(water) if water is not None else "–",
            "wasser_warn": water is not None and water > Year.water_max(los),
            "invertase": count(inv) if inv is not None else "–",
            "invertase_warn": any("Invertase unter" in b for b in befunde),
            "hmf": count(hmf) if hmf is not None else "–",
            "hmf_warn": any("HMF über" in b for b in befunde),
            "befunde": befunde,
        }

    def konflikte(self) -> list[str]:
        """Fillings of a GQ article from a batch that is not GQ."""
        out = []
        for f in self.abfuellungen:
            los = self.r.lose.get(tracing.ref(f.get("batch_id")) or 0, {})
            if self.r.artikel_gqb.get(tracing.ref(f.get("sku")) or 0) and not los.get(
                "gqb_compliant"
            ):
                out.append(
                    f"{tracing.text(f.get('filling_id'))} ({tracing.text(f.get('label'))}) "
                    f"aus Los {tracing.text(los.get('batch_id')) or '–'}"
                )
        return out

    # -- the criteria -------------------------------------------------------

    def kriterien(self) -> list[dict[str, Any]]:
        r, y = self.r, self.year
        gq_lose = {i: los for i, los in self.lose.items() if los.get("gqb_compliant")}
        ohne_los = [f for f in self.abfuellungen if not tracing.ref(f.get("batch_id"))]
        eimer_ohne = [
            e
            for e in self.eimer
            if not tracing.ref(e.get("batch_id")) or not tracing.ref(e.get("location"))
        ]
        geerntet = sum(tracing.number_or_zero(e.get("weight")) for e in self.eimer)
        abgefuellt = sum(f["kg"] or 0 for f in self.abfuellungen)
        standorte = self.standort_ids
        ohne_lage = [r.standort_name(s) for s in standorte if r.lage(s) is None]
        konflikte = self.konflikte()
        ohne_volk = [b for b in self.bestandsbuch if not r.volk_am(b.get("BN"), b["date"])]

        h2: list[dict[str, Any]] = []
        for i, los in gq_lose.items():
            nummer = tracing.text(los.get("batch_id"))
            alle = self.analysen(i)
            analysen = [a for a in alle if not a.get("before_homogenisation")]
            vorher = [a for a in alle if a.get("before_homogenisation")]
            if not analysen:
                h2.append(
                    note(
                        f"{nummer}: keine Analyse nach Homogenisierung erfasst"
                        + (" (nur vor Homogenisierung)." if vorher else "."),
                        warn=True,
                    )
                )
            for a in analysen:
                p = self.pruefung(los, a)
                h2.append(
                    note(
                        f"{nummer}: {tracing.text(a.get('report_number'))}: {werte(p)}"
                        + (f" – {'; '.join(p['befunde'])}!" if p["befunde"] else ""),
                        warn=bool(p["befunde"]),
                    )
                )
            # Only when nothing reliable is there: the values before
            # homogenisation for orientation, without judging them.
            if not analysen:
                for a in vorher:
                    p = self.pruefung(los, a)
                    h2.append(
                        note(
                            f"{nummer}: {tracing.text(a.get('report_number'))} "
                            f"vor Homogenisierung, nicht verlässlich: {werte(p)}",
                            vorlaeufig=True,
                        )
                    )
        if not gq_lose:
            h2.append(note(f"Keine GQ-Lose {y}."))

        def k(nr: str, text: str, ko: bool = False, *notes: dict[str, Any]) -> dict[str, Any]:
            return {"nr": nr, "text": text, "ko": ko, "nachweis": list(notes)}

        return [
            {
                "gruppe": "A",
                "titel": "Allgemeine Dokumentation / Herkunftssicherung",
                "kriterien": [
                    k(
                        "A1",
                        "Dokumentation der durchgeführten Eigenkontrolle",
                        False,
                        note("Dieses Dokument."),
                    ),
                    k(
                        "A2",
                        "Dokumentation der eingeleiteten Maßnahmen",
                        False,
                        note("Tabelle „Mängel und Maßnahmen“."),
                    ),
                    k(
                        "A3",
                        "Umsetzung der eingeleiteten Maßnahmen",
                        False,
                        note("Spalte „erledigt am“ der Tabelle „Mängel und Maßnahmen“."),
                    ),
                    k(
                        "A4",
                        "Rückverfolgbarkeit / Beleg der regionalen Herkunft",
                        True,
                        note(
                            f"{len(self.eimer)} Eimer mit Schleuderung, Standort und Los; "
                            f"{len(self.abfuellungen) - len(ohne_los)} von {len(self.abfuellungen)} "
                            "Abfüllungen mit Los (Anlagen 3–5)."
                        ),
                        *(
                            [note(f"{len(eimer_ohne)} Eimer ohne Los oder Standort.", warn=True)]
                            if eimer_ohne
                            else []
                        ),
                        *(
                            [note(f"{len(ohne_los)} Abfüllungen ohne Los.", warn=True)]
                            if ohne_los
                            else []
                        ),
                    ),
                    k("A5", "Konformitätsbescheinigung wird an nächste Stufe weitergegeben", True),
                    k(
                        "A6",
                        "Wareneingänge und -ausgänge sind dokumentiert, nachvollziehbar, plausibel",
                        True,
                        note(
                            f"Geerntet {kg(geerntet)} in {len(self.schleuderungen)} Schleuderungen, "
                            f"abgefüllt {kg(abgefuellt)} (Anlagen 3–5); verkauft: "
                            f"bscli verkaufszahlen --year {y} --gqb only."
                        ),
                    ),
                    k(
                        "A7",
                        "Produktion, Völkerstandplatz, Abfüllung und Lagerung ausschließlich in Bayern",
                        True,
                        note(
                            f"Standorte: {', '.join(r.standort_name(s) for s in standorte) or '–'} (Anlage 2)."
                        ),
                        *(
                            [note(f"Ohne Koordinaten: {', '.join(ohne_lage)}.", warn=True)]
                            if ohne_lage
                            else []
                        ),
                    ),
                    k(
                        "A8",
                        "Abfüllplan vorhanden",
                        True,
                        note(
                            f"{len(self.abfuellungen)} Abfüllungen (Anlage 5; bscli abfuellungen --year {y})."
                        ),
                    ),
                    k(
                        "A9",
                        "Dokumentation der verkauften Produktmenge",
                        False,
                        note(f"bscli verkaufszahlen --year {y} --gqb only."),
                    ),
                    k(
                        "A10",
                        "Trennung von GQ-/Nicht-GQ-Ware eingehalten",
                        True,
                        *(
                            [
                                note(
                                    "GQ-Artikel aus Nicht-GQ-Los: " + "; ".join(konflikte),
                                    warn=True,
                                )
                            ]
                            if konflikte
                            else [note("Kein GQ-Artikel aus einem Nicht-GQ-Los abgefüllt.")]
                        ),
                    ),
                ],
            },
            {
                "gruppe": "B",
                "titel": "Honigerzeugung am Volk",
                "kriterien": [
                    k(
                        "B1",
                        "Völkerverzeichnis liegt vor",
                        False,
                        note(f"{len(self.voelker)} Völker am {d(self.stichtag)} (Anlage 1)."),
                    ),
                    k(
                        "B2",
                        "Standortwahl unbedenklich",
                        True,
                        note("Standorte mit Flugkreis (Anlage 2)."),
                    ),
                    k(
                        "B3",
                        "Hygieneanforderungen am Volk eingehalten (gute fachliche Praxis)",
                        True,
                    ),
                ],
            },
            {
                "gruppe": "C",
                "titel": "Honiggewinnung und -lagerung",
                "kriterien": [
                    k(
                        "C1",
                        "Getrennte Erfassung/Lagerung von GQ- und Nicht-GQ-Rohware (Identifizierung von Partien)",
                        True,
                        note(
                            f"{len(gq_lose)} GQ-Lose, {len(self.lose) - len(gq_lose)} andere; "
                            "jeder Eimer trägt seine Nummer und sein Los (Anlagen 3–4)."
                        ),
                    ),
                    k("C2", "Kennzeichnung der GQ-Bayern-Ware eindeutig und nachvollziehbar", True),
                ],
            },
            {
                "gruppe": "D",
                "titel": "Hygiene",
                "kriterien": [
                    k("D1", "Personalhygiene eingehalten", False, note("Merkblatt Hygiene.")),
                    k(
                        "D2",
                        "Geräte und Honiggefäße entsprechen der Lebensmittelhygiene, dokumentierter Reinigungsplan",
                        False,
                        note(
                            f"Reinigung nach Bedarf; Reinigungsprotokoll: "
                            f"{entries(len(self.reinigung))} {y} (Anlage 6).",
                            warn=not self.reinigung,
                        ),
                    ),
                    k("D3", "Aufbereitungs- und Lagerräume erfüllen die Anforderungen"),
                    k(
                        "D4",
                        "Geeignete Reinigungs- und Desinfektionsmittel für Beuten, Rähmchen und Geräte",
                        False,
                        *self.d4(),
                    ),
                    k(
                        "D5",
                        "Schädlingsbekämpfung im Aufbereitungs- und Lagerraum durchgeführt und dokumentiert",
                        False,
                        *self.d5(),
                    ),
                ],
            },
            {
                "gruppe": "E",
                "titel": "Arzneimittel / Varroabehandlung",
                "kriterien": [
                    k(
                        "E1",
                        "Eingesetzte Arzneimittel/Varroabehandlungsmittel sind dokumentiert",
                        False,
                        note(f"Bestandsbuch: {entries(len(self.bestandsbuch))} {y} (Anlage 7)."),
                        *(
                            [
                                note(
                                    "Boden-Nr. ohne Volk an dem Tag: "
                                    + ", ".join(
                                        f"{d(b['date'])} BN {b.get('BN') or '–'}" for b in ohne_volk
                                    ),
                                    warn=True,
                                )
                            ]
                            if ohne_volk
                            else []
                        ),
                    ),
                ],
            },
            {
                "gruppe": "F",
                "titel": "Etikettierung / Handel",
                "kriterien": [
                    k("F1", "Etikettierung gemäß Lebensmittel-Kennzeichnungsverordnung"),
                ],
            },
            {
                "gruppe": "G",
                "titel": "Schulung",
                "kriterien": [
                    k(
                        "G1",
                        "Fortbildung beim Verband und anerkannten Einrichtungen",
                        False,
                        *self.g1(),
                    ),
                ],
            },
            {
                "gruppe": "H",
                "titel": "Qualitätsanforderung / Analytik",
                "kriterien": [
                    k("H1", "Rückstandsuntersuchungen liegen vor"),
                    k(
                        "H2",
                        "Analyseergebnisse Invertaseaktivität / HMF-Gehalt / Wassergehalt liegen vor",
                        True,
                        *h2,
                    ),
                ],
            },
        ]

    # -- the annexes --------------------------------------------------------

    def anlagen(self) -> dict[str, Any]:
        r = self.r
        voelker = []
        for v in self.voelker:
            sid = r.standort(tracing.ref(v.get("Standort")))
            voelker.append(
                {
                    "vn": str(v.get("VN") or ""),
                    "bn": str(v.get("BN") or ""),
                    "typ": tracing.text(v.get("Typ")),
                    "standort": r.standort_name(sid),
                    "von": d(v["von"]),
                }
            )
        standorte = [
            {
                "kuerzel": tracing.text(r.standorte[s].get("location_id")),
                "name": tracing.text(r.standorte[s].get("name")),
                **self.lage_daten(s),
            }
            for s in self.standort_ids
        ]
        ernte = []
        for i, s in sorted(self.schleuderungen.items(), key=lambda x: x[1]["date"]):
            eimer = [e for e in self.eimer if tracing.ref(e.get("centrifugation_id")) == i]
            ernte.append(
                {
                    "nr": tracing.text(s.get("centrifugation_id")),
                    "datum": d(s["date"]),
                    "voelker": count(s.get("number_of_hives")),
                    "standorte": ", ".join(r.standort_name(x) for x in self.ernte_standorte[i]),
                    "eimer": str(len(eimer)),
                    "lose": list(
                        dict.fromkeys(r.los_nummer(tracing.ref(e.get("batch_id"))) for e in eimer)
                    ),
                    "kg": kg(sum(tracing.number_or_zero(e.get("weight")) for e in eimer)),
                }
            )
        lose = []
        for i, los in self.lose.items():
            analysen = self.analysen(i)
            lose.append(
                {
                    "los": tracing.text(los.get("batch_id")),
                    "sorte": tracing.text(los.get("honey_type")),
                    "gq": "ja" if los.get("gqb_compliant") else "",
                    "kg": kg(tracing.number_or_zero(los.get("weight"))),
                    "analysen": [
                        {
                            "bericht": tracing.text(a.get("report_number")),
                            "aussteller": tracing.text(a.get("issuer")),
                            **self.pruefung(los, a),
                            "vorher": bool(a.get("before_homogenisation")),
                        }
                        for a in analysen
                    ],
                }
            )
        abfuellungen = [
            {
                "nr": tracing.text(f.get("filling_id")),
                "datum": d(f["date"]),
                "los": r.los_nummer(tracing.ref(f.get("batch_id"))),
                "gq": "ja" if r.artikel_gqb.get(tracing.ref(f.get("sku")) or 0) else "",
                "artikel": tracing.text(f.get("label")),
                "sku": r.artikel_nummer(tracing.ref(f.get("sku"))),
                "stueck": count(f["stueck"]),
                "kg": count(round(f["kg"], 2)) if f["kg"] is not None else "–",
                "mhd": d(f["mhd"]),
                "dib": tracing.text(f.get("dib_field")),
            }
            for f in self.abfuellungen
        ]
        reinigung = [
            {
                "datum": d(c["date"]),
                "objekt": tracing.text(c.get("Objekt")),
                "mittel": ", ".join(tracing.choices(c.get("Mittel"))),
                "schaedlinge": tracing.text(c.get("Schaedlinge")),
                "kommentar": tracing.text(c.get("Kommentar")),
            }
            for c in self.reinigung
        ]
        bestandsbuch = [
            {
                "datum": d(b["date"]),
                **self.volk_nummern(b.get("BN"), b["date"]),
                "gabe": tracing.text(b.get("Arzneigabe")),
                "mittel": tracing.text(b.get("Arzneimittel")),
                "menge": tracing.text(b.get("Arzneimenge")),
                "wartezeit": d(tracing.to_date(b.get("Wartezeit_bis"))),
            }
            for b in self.bestandsbuch
        ]
        return {
            "voelker": voelker,
            "standorte": standorte,
            "ernte": ernte,
            "lose": lose,
            "abfuellungen": abfuellungen,
            "reinigung": reinigung,
            "bestandsbuch": bestandsbuch,
            "fortbildungen": [
                {
                    "datum": d(n["date"]),
                    "titel": n["title"],
                    "veranstalter": n["issuer"],
                    "url": n["url"],
                }
                for n in self.nachweise
            ],
        }

    def d4(self) -> list[dict[str, Any]]:
        """The cleaning agents used in the year; entries without one in bold."""
        mittel = list(
            dict.fromkeys(m for c in self.reinigung for m in tracing.choices(c.get("Mittel")))
        )
        ohne = [d(c["date"]) for c in self.reinigung if not tracing.choices(c.get("Mittel"))]
        out = [note(f"Mittel: {', '.join(mittel)} (Anlage 6).")] if mittel else []
        if ohne:
            out.append(note(f"Ohne Angabe der Mittel: {', '.join(ohne)}.", warn=True))
        return out or [note(f"Keine Reinigung {self.year} eingetragen.", warn=True)]

    def d5(self) -> list[dict[str, Any]]:
        """Pest checks with the cleaning: how many, and any infestation in bold."""
        befunde = [(c, tracing.text(c.get("Schaedlinge"))) for c in self.reinigung]
        kontrollen = [b for b in befunde if b[1]]
        befall = [c for c, b in kontrollen if b == "Befall"]
        out = []
        if kontrollen:
            out.append(
                note(
                    f"Sichtkontrolle bei der Reinigung: {len(kontrollen)}× {self.year}"
                    + (", alle ohne Befund" if not befall else "")
                    + " (Anlage 6)."
                )
            )
        for c in befall:
            out.append(
                note(f"Befall {d(c['date'])}: {tracing.text(c.get('Kommentar')) or '–'}", warn=True)
            )
        if not kontrollen:
            out.append(note(f"Keine Schädlingskontrolle {self.year} eingetragen.", warn=True))
        return out

    def g1(self) -> list[dict[str, Any]]:
        """Evidence of training: the certificates of the year, else the
        latest one, in bold."""
        im_jahr = [n for n in self.nachweise if n["date"].year == self.year]
        if im_jahr:
            return [
                note(f"{len(im_jahr)} Fortbildungen {self.year} (Anlage 8):"),
                *(note(f"{d(n['date'])} {n['title']}") for n in reversed(im_jahr)),
            ]
        if self.nachweise:
            n = self.nachweise[0]
            return [
                note(
                    f"Keine Fortbildung {self.year} eingetragen; zuletzt {d(n['date'])}: "
                    f"{n['title']} (Anlage 8).",
                    warn=True,
                )
            ]
        return [note("Keine Fortbildung eingetragen (Website, Über uns).", warn=True)]

    def volk_nummern(self, bn: Any, day: date | None) -> dict[str, str]:
        """VN and floor number (Boden-Nr.) of a Bestandsbuch entry. The floor
        number is what is entered; the colony is the one on that floor that
        day -- looked up here, not taken from Bestandsbuch.HR_Hive_ID, whose
        formula returns the VN where Grist expects a row id."""
        v = self.r.volk_am(bn, day) or {}
        return {"vn": str(v.get("VN") or ""), "bn": str(bn or "")}

    def lage_daten(self, standort_id: int) -> dict[str, str]:
        """Coordinates of a location and the link they lead to: the flight
        circle in the BayernAtlas, else the position. Empty without a
        position."""
        lage = self.r.lage(standort_id)
        s = self.r.standorte[standort_id]
        return {
            "koordinaten": lage.koordinaten if lage else "",
            "karte": tracing.text(s.get("circle")) or tracing.text(s.get("position")),
        }


def report(
    r: tracing.Records, year: int, today: date, nachweise: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    y = Year(r, year, today, nachweise)
    return {
        "jahr": str(year),
        "stichtag": d(y.stichtag),
        "voelker_anzahl": str(len(y.voelker)),
        "gruppen": y.kriterien(),
        "anlagen": y.anlagen(),
    }


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        nargs="+",
        metavar="YYYY",
        help="the year(s) to check instead of the current one; one PDF per year",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="PATH",
        help="PDF path (default: Eigenkontrolle_<year>.pdf; only for a single year)",
    )
    add_print_arguments(parser)


def run(args: argparse.Namespace) -> None:
    setup_logging()
    today = date.fromisoformat(time.strftime("%Y-%m-%d"))
    years = sorted(set(args.year or [today.year]))
    if args.output and len(years) > 1:
        print("bscli eigenkontrolle: error: -o only works for a single year", file=sys.stderr)
        sys.exit(2)
    cfg = require_env("GRIST_API_KEY", "GRIST_BASE_URL", "GRIST_DOC_ID")
    grist = GristClient(cfg["GRIST_BASE_URL"], cfg["GRIST_API_KEY"], cfg["GRIST_DOC_ID"])
    head = letterhead(grist)
    records = tracing.load(grist)
    fortbildungen = website.nachweise()
    for year in years:
        output: Path = args.output or Path(f"Eigenkontrolle_{year}.pdf")
        data = {**head, **report(records, year, today, fortbildungen)}
        output.write_bytes(render("eigenkontrolle.typ", data, bw=args.bw))
        print(f"{output} written.")
