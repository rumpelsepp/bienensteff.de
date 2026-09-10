# Konzept: Varroaampel unter /werkzeuge

Stand: 2026-09-09 (Rev. 8 – Matrix Tage × Verfahren, aus der Umsetzung von
Rev. 7 gelernt)

## 1. Ziel

Eine **Wetterampel als Matrix**: Für eine wählbare DWD-Station in
Ober-/Niederbayern zeigt die Seite für die nächsten ~10 Tage, ob der
jeweilige Tag als **Behandlungsstart** für ein Ameisensäure-Verfahren
wetterbedingt günstig (grün), eingeschränkt (gelb) oder ungünstig (rot) ist.

- **Jede Spalte ist ein Vorhersagetag.** So sieht man das Vorhersageband auf
  einen Blick.
- **Jede Zeile ist ein Verfahren** (Präparat × Applikator): Liebig-Dispenser,
  Nassenheider Professional, Formic Pro. Dazu eine **graue Zeile** für
  Ameisensäure 85 %, die in Deutschland nicht zugelassen ist und nur als
  akademische Information dient.
- **Jede Zelle** ist eingefärbt, und **jede Zeile bekommt eine
  Gesamtbewertung** („frühester günstiger Start: Fr, 12.09.").

Die Ein-Zeilen-Fassung aus Rev. 7 (nur Liebig, Tage als Zeilen) hat sich in
der Umsetzung als zu schmal erwiesen: Sie beantwortet nur eine Frage und
lässt keinen Platz, die 60/85-Komplementarität oder Formic Pro sauber
darzustellen. Die Matrix ist die natürliche Form dafür, ohne den
Arzneimittelkatalog von Rev. 6 wiederzubeleben.

Vorbild ist varroawetter.de (DLR Mayen). Unser Werkzeug heißt **Varroaampel**
(`/werkzeuge/varroaampel/`), nutzt ausschließlich DWD Open Data und fügt sich
in die vorhandene Pipeline ein (Hugo + `scripts/`-CLI + Data-Workflow +
TypeScript-Widget), analog zu Trachtnet und Klimadaten.

### Bewusst nicht enthalten

- **Kein Arzneimittelkatalog** mit Zulassungsnummern, Ablaufdaten, Prüf-CLI
  oder YAML-Regel-Engine. Die Verfahren stehen als kommentierte
  Konstantenliste im TypeScript-Modul; vier Einträge rechtfertigen keine
  Datei.
- **Keine brutfreien Verfahren** (Oxalsäure, Milchsäure): Ob ein Volk
  brutfrei ist, weiß das Wetter nicht, und die Schwellen (≥ 3 bzw. ≥ 4 °C)
  sind im Herbst fast immer erfüllt. Eine Zeile wäre fast immer grün und
  damit wertlos. Kandidat für einen Ausbau (Abschnitt 6).
- **Kein Thymol, Flumethrin, Amitraz:** Dauer länger als der
  Vorhersagehorizont oder gar nicht wetterabhängig.
- **Keine Dosier-/Dochttabellen, kein Beutentyp, kein
  Brutstatus-Umschalter, kein Warnbanner.** Einziges Bedienelement ist die
  Stationsauswahl.
- **Keine Luftfeuchte, kein Wind** in der Bewertung. Der Nassenheider nennt
  einen windigen Standort als ungünstig; das ist eine Standortfrage, keine
  Tagesfrage.

---

## 2. Ampel-Logik

### 2.1 Steuergröße

Die **Tageshöchsttemperatur** `t_max` je lokalem Kalendertag, aggregiert aus
den stündlichen `TTT`-Werten (3.2). Beide Dispenser-Hersteller beziehen sich
ausdrücklich auf die „zu erwartenden maximalen Temperaturen gemäß
Wetterprognosen" (Liebig-Anleitung), Formic Pro auf die Außentemperatur
während der Behandlung.

### 2.2 Die Zeilen

Alle Angaben am 2026-09-09 aus den Herstellerunterlagen gelesen (Quellen in
Abschnitt 7). Was der Hersteller nicht vorgibt, ist als **eigene Festlegung**
markiert und im Code entsprechend kommentiert.

| Zeile | Fenster | Temperaturband `t_max` | Gelb-Band | Besonderheit | Status |
|---|---|---|---|---|---|
| **Ameisensäure 60 %, Liebig-Dispenser** | 7 d (1. Behandlung; 2. Behandlung 10 d) | **15–30 °C** – die Dochttabelle hat außerhalb keinen Eintrag | **15–20 °C** – Tabelle: „Verwendung von FORMIVAR 85 % wird empfohlen" | > 25 °C: „am Morgen starten"; kein Start vor Gewitter/Starkregen | `ampel` |
| **Ameisensäure 60 %, Nassenheider Professional** | 10 d (Mindestdauer 10–14 d) | Hersteller nennt **kein Band** (selbstregulierender Docht, Verdunstung witterungsbedingt +50 % „nicht schädlich"). **Eigene Festlegung:** 15–30 °C wie Liebig, als konservative Näherung | keins | Gewitter/Starkregen-Regel übernommen (eigene Festlegung) | `ampel` |
| **Formic Pro** (Ameisensäure-Gelstreifen) | 7 d | **10–29,5 °C** Außentemperatur „bei der Behandlung", also über das ganze Fenster | keins | > 25 °C: Schieber am Boden teilweise offen (Hinweistext); Gewitter/Starkregen-Regel übernommen (eigene Festlegung) | `ampel` |
| **Ameisensäure 85 %, Liebig-Dispenser** (FORMIVAR 85) | 7 d | **15–30 °C** (Dochttabelle FORMIVAR 85) | **25–30 °C** – Tabelle: „Verwendung von FORMIVAR 60 % wird empfohlen" | **In DE nicht zugelassen** (CH: FORMIVAR 85, AT: AMO Varroxal 85 %). Nassenheider nennt 85 % nur für die Oktober-Restentmilbung bei `t_max` > 10 °C, „in bestimmten Bundesländern bei Gefahr im Verzug" | `akademisch` |

Die 85-%-Zeile ist der Grund, warum die Matrix Sinn ergibt: Wo die 60-%-Zeile
gelb ist (15–20 °C), ist die 85-%-Zeile passend, und umgekehrt. Man sieht die
Komplementarität der Herstellertabellen, ohne dass die Seite etwas
empfiehlt, was in Deutschland nicht zugelassen ist.

### 2.3 Bewertung einer Zelle

Zelle = Tag `d` als **Starttag** für Zeile `p`. Betrachtet wird das Fenster
`d … d + dauer − 1`; die Folgetage gehen nur über die Temperatur ein.

| Farbe | Bedingung |
|---|---|
| **Rot** | `t_max` an `d` oder einem Folgetag im Fenster außerhalb des Temperaturbands der Zeile |
| **Rot** | Gewitter an `d` (`ww` 95–99 in irgendeiner Stunde) |
| **Rot** | Niederschlag an `d` ≥ 10 mm (Schwelle: eigene Festlegung) |
| **Gelb** | `t_max` an `d` im Gelb-Band der Zeile |
| **Gelb** | Regenwahrscheinlichkeit `R101` an `d` ≥ 70 % (eigene Festlegung) |
| **Grün** | sonst |

Die Reihenfolge ist die Prüfreihenfolge; die erste zutreffende Regel liefert
Farbe und Kurzbegründung („zu heiß: 32 °C am Do", „Gewitter", „Hersteller
empfiehlt hier 85 %").

Zusätze, die die Farbe nicht ändern:

- Zeilenspezifischer Hinweis (z. B. „am Morgen starten" bei > 25 °C).
- Fenster reicht über den Vorhersagehorizont hinaus: „Vorhersage endet vor
  Behandlungsende" – bewertet wird, was vorliegt. Beim Nassenheider (10 d)
  betrifft das den Großteil der Spalten; das wird ehrlich so angezeigt.
- Spalten ab Tag 8 (+168 h) blasser: „Vorhersage ab hier unsicher".

**Graue Zeile (`akademisch`):** dieselbe Rechnung, aber statt Grün/Gelb/Rot
zwei Graustufen (hell = im Band, dunkel = außerhalb) mit derselben
Kurzbegründung. Feste Beschriftung in der Zeilenüberschrift: „Nur zur
Information. In Deutschland nicht als Tierarzneimittel zugelassen
(zugelassen in CH und AT); eine Anwendung wäre eine Umwidmung und dem
Tierarzt vorbehalten." Kein Link auf eine Anleitung, keine Gesamtbewertung.

Nichts davon ist Saison- oder Trachtlogik: dass Ameisensäure erst **nach der
letzten Honigernte** und **nicht während der Tracht** angewendet wird
(Standardzulassung 2469.99.99, Nassenheider-Gegenanzeige, Formic Pro:
Honig aus aufgesetzten Zargen nicht verzehren), steht als Text auf der
Seite, nicht in der Ampel.

### 2.4 Gesamtbewertung je Zeile

Letzte Spalte der Matrix, pro `ampel`-Zeile:

1. Gibt es eine grüne Zelle: „**frühester günstiger Start: Fr, 12.09.**"
2. Sonst eine gelbe: „frühester eingeschränkter Start: …"
3. Sonst: „im Vorhersagezeitraum kein günstiger Start"

Dazu in Klammern die Anzahl grüner Tage („3 von 10"). Die graue Zeile zeigt
hier nur „nicht zugelassen".

### 2.5 Anzeige

Eine Tabelle, `table-responsive`, erste Spalte sticky:

```
Verfahren            | Mi 10. | Do 11. | Fr 12. | … | Fr 19. | Gesamt
                     | 18/11° | 20/10° | 24/12° |   | 27/15° |
                     | 0 mm 9%| 2 mm 40%| …    |   |        |
---------------------+--------+--------+--------+---+--------+-----------------
AS 60 % Liebig  7 d  | gelb   | gelb   | grün   | … | grün ▒ | Start Fr 12.09. (5/10)
AS 60 % Nassenh. 10 d| gelb   | grün   | grün   | … | grün ▒ | Start Do 11.09. (6/10)
Formic Pro      7 d  | grün   | grün   | grün   | … | grün ▒ | Start Mi 10.09. (8/10)
AS 85 % Liebig  7 d  | hell   | hell   | hell   | … | dunkel | nicht zugelassen
```

- Der Spaltenkopf trägt Datum, `t_max`/`t_min`, Niederschlag und
  Regenwahrscheinlichkeit; die Zellen tragen nur Farbe und ein kurzes Kürzel.
  Die Kurzbegründung steht im `title`-Attribut und wird beim Tippen/Klicken in
  einer Zeile unter der Tabelle angezeigt (Mobile hat keinen Hover).
- Farben über Bootstrap-Klassen (`table-success`, `table-warning`,
  `table-danger`, `table-secondary`/`table-dark` für die graue Zeile) plus ein
  Textkürzel, damit die Ampel auch ohne Farbsehen lesbar ist.
- Die Zeilenüberschrift verlinkt die Herstelleranleitung und nennt die
  Fensterlänge.
- Kein ECharts.

---

## 3. Wetterdaten: DWD MOSMIX_L

Alle Angaben am 2026-09-09 gegen den Lauf `2026-09-09T03:00Z`, Station 10865,
geprüft.

### 3.1 Quelle

- Pro Station eine Datei
  `https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/<ID>/kml/MOSMIX_L_LATEST_<ID>.kmz`,
  4 Läufe/Tag (03/09/15/21 UTC).
- KMZ = gezipptes KML. Parsen mit Python-stdlib (`zipfile`,
  `xml.etree.ElementTree`). Zeitachse in `<dwd:ForecastTimeSteps>`, Werte in
  `<dwd:Forecast dwd:elementName="…">`, Lauf in `<dwd:IssueTime>`, Stationsname
  und Koordinaten (lon, lat, Höhe in Dezimalgrad) in `<name>`,
  `<description>`, `<coordinates>`.
- 114 Elemente, 247 Zeitschritte stündlich (+240 h). Fehlwert `-`.
- Lizenz **CC BY 4.0**, Quellenangabe „Deutscher Wetterdienst" ist Pflicht.

### 3.2 Verwendete Elemente

| Element | Bedeutung | Einheit | Verwendung |
|---|---|---|---|
| `TTT` | Temperatur 2 m | K | `t_max`, `t_min` je Tag |
| `RR1c` | Niederschlag letzte Stunde | mm | Tagessumme |
| `R101` | Wahrscheinlichkeit Niederschlag > 0,1 mm | % | Tagesmaximum |
| `ww` | signifikantes Wetter (WMO-Code) | Code | **Gewitter = 95–99** |

**Korrektur gegenüber Rev. 6:** dort war `wwM` als Gewitter-Flag vorgesehen.
`wwM` ist laut DWD-Elementbeschreibung die **Nebelwahrscheinlichkeit**. Die
Gewitter-Wahrscheinlichkeiten `wwT`/`wwTh`/`wwTd` existieren, waren im
geprüften Lauf aber **komplett unbelegt** (0/247). `ww` ist belegt (246/247)
und wird deshalb verwendet.

`TX`/`TN` (12-h-Extreme) sind nur an 21 von 247 Zeitschritten belegt und
werden nicht verwendet.

### 3.3 Zeitzone

MOSMIX-Zeitstempel sind UTC, die Seite läuft auf `Europe/Berlin`. Tageswerte
werden auf **lokalen Kalendertagen** gebildet: Zeitstempel als aware-UTC
parsen, mit `zoneinfo.ZoneInfo("Europe/Berlin")` konvertieren, dann nach Datum
gruppieren. Erster und letzter Tag des Laufs sind unvollständig; ein Tag wird
nur ausgegeben, wenn **≥ 20 Stundenwerte** vorliegen.

### 3.4 Stationen

Dropdown mit festen Stationen, gruppiert nach Region. Keine PLZ-Eingabe. Alle
IDs am 2026-09-09 im MOSMIX_L-Verzeichnis geprüft.

| ID | Station | Höhe | Region |
|---|---|---|---|
| `10865` | München-Stadt *(Vorauswahl)* | 515 m | Oberbayern |
| `10870` | München-Flughafen | 453 m | Oberbayern |
| `10863` | Weihenstephan (Freising) | 470 m | Oberbayern |
| `10858` | Fürstenfeldbruck | 519 m | Oberbayern |
| `10875` | Mühldorf a. Inn | 406 m | Oberbayern |
| `10982` | Chieming | 549 m | Oberbayern |
| `10963` | Garmisch-Partenkirchen | 719 m | Oberbayern |
| `10962` | Hohenpeißenberg | 977 m | Oberbayern |
| `10788` | Straubing | 350 m | Niederbayern |
| `10872` | Gottfrieding | 350 m | Niederbayern |
| `K4503` | Landshut | 391 m | Niederbayern |
| `10893` | Passau | 409 m | Niederbayern |
| `10895` | Fürstenzell | 476 m | Niederbayern |
| `10796` | Zwiesel | 612 m | Niederbayern |

Datei `data/varroa_stationen.json` (JSON statt YAML, damit das CLI ohne
`pyyaml` auskommt):

```json
[
  {"id": "10865", "label": "München-Stadt", "region": "Oberbayern", "default": true},
  {"id": "10788", "label": "Straubing", "region": "Niederbayern"}
]
```

Name, Höhe und Koordinaten kommen aus dem KMZ, nicht von Hand (der
DWD-Stationskatalog notiert Grad.Minuten, das hat in einer frühen Fassung zu
falschen Koordinaten geführt).

---

## 4. Umsetzung

### 4.1 CLI `dump-mosmix` (`scripts/`)

- `scripts/src/bstools/cli/dump_mosmix.py`, Eintrag in `[project.scripts]`.
  Abhängigkeiten: `niquests` + stdlib. **Kein polars, kein pyyaml.**
- Liest `data/varroa_stationen.json`, holt je Station das KMZ, aggregiert
  `TTT`/`RR1c`/`R101`/`ww` auf lokale Tage (3.3) und schreibt **eine** Datei
  `static/varroaampel/forecast.json` (~20 kB). Das Frontend lädt einmal,
  Stationswechsel ist rein clientseitig.
- Die Ampel wird **nicht** im CLI berechnet. Das CLI ist ein reiner Daten-Dump
  wie `dump-dwd`; die Regeln liegen im Frontend neben der Darstellung.
- JSON statt NDJSON, weil die Struktur verschachtelt ist (Stationen → Tage).

```json
{
  "lauf": "2026-09-09T03:00:00Z",
  "quelle": "Deutscher Wetterdienst, MOSMIX_L (CC BY 4.0)",
  "stationen": [
    {
      "id": "10865", "label": "München-Stadt", "region": "Oberbayern",
      "default": true, "hoehe_m": 515,
      "tage": [
        {"datum": "2026-09-09", "t_max": 24.1, "t_min": 12.0,
         "niederschlag_mm": 0.0, "regen_wahrsch": 15, "gewitter": false,
         "stunden": 18}
      ]
    }
  ]
}
```

- **Defensiv:** Ergebnis erst vollständig im Speicher aufbauen, dann atomar
  schreiben. Schlägt eine Station fehl, wird sie ausgelassen und geloggt; die
  übrigen laufen weiter. Schlägt alles fehl, bleibt die alte Datei stehen.
- `justfile`:

  ```
  update-varroaampel:
      uv run --project scripts dump-mosmix \
          --stations data/varroa_stationen.json \
          --out static/varroaampel/forecast.json
  ```

### 4.2 Cron: `.github/workflows/data.yml`

- Neuer Step `just update-varroaampel` **nach** dem Commit-Step, **vor** dem
  Deploy.
- **Vorhersagen werden nicht committet.** `/static/varroaampel/` kommt in
  `.gitignore` (wie die Build-Artefakte). Der Deploy baut aus dem Working
  Tree, ein Commit ist dafür nicht nötig.
- Der Deploy-Step hängt derzeit an `if: steps.commit.outputs.changed == 'true'`.
  Diese Bedingung **entfernen**, sonst wird an Tagen ohne Trachtnet-/
  Klima-Änderung keine frische Vorhersage ausgeliefert.
- Ein Lauf pro Tag (`0 2 * * *`, nutzt den 21-UTC-Lauf) reicht für eine
  10-Tage-Ampel.

### 4.3 Frontend: `bundle_src/js/varroa/`

- `ampel.ts`: Typen, Konstantenliste `VERFAHREN` (2.2) mit Kommentar je
  Schwelle, Konstantenblock für die verfahrensunabhängigen Wetterregeln
  (Starkregen, Regenwahrscheinlichkeit, Unsicherheit), reine Funktionen
  `bewerteZelle(tage, index, verfahren)`, `bewerteMatrix(tage)` und
  `gesamtbewertung(zeile)`. Ohne DOM, damit sie testbar bleiben.

  ```ts
  interface Verfahren {
      id: string;
      label: string;             // "Ameisensäure 60 %, Liebig-Dispenser"
      kurz: string;              // "AS 60 % Liebig"
      status: "ampel" | "akademisch";
      dauerTage: number;         // Fensterlänge
      band: [number, number];    // t_max außerhalb → rot
      gelbBand?: [number, number];
      gelbText?: string;         // "Hersteller empfiehlt hier 85 %"
      morgenstartAb?: number;    // Hinweis, keine Farbänderung
      anleitung?: string;        // URL; fehlt bei "akademisch"
      hinweis?: string;          // feste Zeilenbeschriftung
  }
  ```

- `render.ts`: lädt `/varroaampel/forecast.json`, baut das `<select>` mit
  `<optgroup>` je Region, rendert Matrix (2.5) und Begründungszeile, merkt die
  gewählte Station in `localStorage`.
- `main.ts`: `initAllVarroaWidgets()` im vorhandenen try/catch-Muster
  (bereits umgesetzt).

### 4.4 Shortcode und Seite

- `layouts/shortcodes/varroa-widget.html`: Container-`div` mit `data-id`, wie
  `klima-widget.html`. Keine Hugo-Datenlogik nötig, alles kommt aus
  `forecast.json`.
- `content/werkzeuge/varroaampel.md`:

  ```
  ---
  title: "Varroaampel"
  description: "Wann ein Behandlungsstart mit Ameisensäure wetterbedingt günstig ist – aus der DWD-Vorhersage"
  ---
  Kurztext: Spalten = Tage, Zeilen = Verfahren, Zelle = Tag als Starttag.
  {.lead}

  {{< varroa-widget >}}

  Erklärung der Farben (2.3), Hinweise (Abschnitt 5), Quellen, Stand.
  ```

- Querverweise auf `/werkzeuge/infos/#varroose`, den Anti-Varroa-Fahrplan und
  `flowchart-as.pdf`. `/werkzeuge` listet Unterseiten automatisch.

---

## 5. Hinweise auf der Seite

Kurz, aber vollständig; Formulierung durchgehend **zustandsbeschreibend**
(„Bedingungen günstig"), nie anweisend („jetzt behandeln").

- Die Ampel bewertet nur das **Wetterfenster** nach den Temperaturangaben
  der jeweiligen Herstelleranleitung. Ob und wann behandelt wird, entscheidet
  der Befall (Milbenfall, siehe Infos).
- Maßgeblich ist die aktuelle Gebrauchsinformation des Präparats und die
  Anleitung des Applikators (je Zeile verlinkt). Dosierung, Dochtfläche und
  Streifenzahl stehen dort, nicht hier.
- Ameisensäure 60 % ad us. vet. und Formic Pro: nur nach der letzten
  Honigernte bzw. ohne Honigzargen, nicht während der Tracht, nicht
  gleichzeitig füttern; **Bestandsbuchpflicht** für alle Zeilen.
- Ameisensäure 85 %: in Deutschland nicht zugelassen. Die graue Zeile ist
  reine Information zur Temperaturabhängigkeit; eine Anwendung wäre eine
  Umwidmung und dem Tierarzt vorbehalten.
- Nassenheider: Hersteller nennt kein Temperaturband; das gezeigte Band ist
  eine konservative Näherung nach der Liebig-Tabelle.
- „Wettervorhersage: Deutscher Wetterdienst (MOSMIX_L), Lauf vom …" mit
  gewählter Station und Höhe.
- „Stand der fachlichen Angaben: <Monat Jahr>" – von Hand gepflegt, einmal
  jährlich vor der Sommerbehandlung prüfen.
- Datenschutz: der DWD-Abruf passiert im Build, der Browser lädt nur
  statisches JSON von bienensteff.de. Keine Drittanbieter-Requests.

---

## 6. Stand und Ausbau

| Schritt | Inhalt | Stand |
|---|---|---|
| Daten | `varroa_stationen.json`, `dump-mosmix`, `.gitignore`, Workflow, `justfile` | umgesetzt (Rev. 7) |
| Widget | `ampel.ts` mit `VERFAHREN`-Liste und Zellenbewertung, `render.ts` mit Matrix, Seite anpassen | **offen** – Rev. 7 hat eine Ein-Zeilen-Tabelle (nur Liebig) |
| optional | Zeile „brutfrei" (Oxalsäure träufeln ≥ 3 °C, Milchsäure sprühen ≥ 4 °C; offen: obere Grenze/Flugwetter), weitere Regionen, Milbenfall-Rechner aus `infos.md` | |

Vor Veröffentlichung zu prüfen (kleiner Aufwand):

- Formic Pro: Temperaturband 10–29,5 °C und 7 Tage stammen aus der
  Händler-FAQ, die aus der Gebrauchsinformation zitiert. Gegen die
  Gebrauchsinformation in der EU Union Product Database gegenlesen
  (Abschnitt 7).
- Ob `ww` an weiteren Stationen und Läufen zuverlässig belegt ist; falls
  `wwT*` in Gewitterlagen befüllt wird, kann es als Zusatzsignal dienen.

---

## 7. Quellen

- DWD MOSMIX: <https://www.dwd.de/DE/leistungen/met_verfahren_mosmix/met_verfahren_mosmix.html>
- MOSMIX_L Einzelstationen: <https://opendata.dwd.de/weather/local_forecasts/mos/MOSMIX_L/single_stations/>
- MOSMIX-Elementübersicht (Community): <https://www.hackitu.de/dwd_mosmix/>
- DWD Datenpolitik / CC BY 4.0: <https://www.dwd.de/DE/derdwd/datenpolitik.html>
- Andermatt BioVet, Gebrauchsanleitung Liebig-Dispenser:
  <https://shop.garten-bienen.at/files/pdf/pdf_Gebrauchsanweisung/Gebrauchsanweisung_Liebig-Dispenser_Web.pdf>
- LAB Hohenheim, Varroa-Bekämpfung mit Ameisensäure und Liebig-Dispenser:
  <https://bienenkunde.uni-hohenheim.de/fileadmin/einrichtungen/bienenkunde/Varroa/LD_Beschreibung.pdf>
- Gebrauchsanweisung NASSENHEIDER Verdunster professional (2017), U-Docht
  nach Beutentyp, Mindestdauer 10–14 d, Behandlungskonzept:
  <https://imkerverein-radolfzell.de/wp-content/uploads/2018/08/NASSENHEIDER-Verdunster-professional-2017.pdf>
- Formic Pro, Gebrauchsinformation (EU Union Product Database):
  <https://medicines.health.europa.eu/veterinary/pl/documents/download/4844ca4b-7664-4d71-97a3-2766f5437fd1>;
  Zusammenfassung in der Händler-FAQ: <https://imkado.de/pages/formic-pro-faq>
- BVL, Standardzulassung Ameisensäure 60 % ad us. vet. (2469.99.99):
  <https://www.bvl.bund.de/SharedDocs/Downloads/05_Tierarzneimittel/Zulassung/Standardzulassung/2469_99_99.html>
- LWG, Zugelassene Varroamittel (Stand Juni 2025):
  <https://www.lwg.bayern.de/mam/cms06/bienen/dateien/varroabehandlungsmittel_mit_zulassung.pdf>
- Bayerisches Varroabehandlungskonzept: <https://www.lwg.bayern.de/varroa>
- Vorbild varroawetter.de, Erläuterung bei bienen&natur:
  <https://www.bienenundnatur.de/bienenkrankheiten/varroabehandlung/varroawetter-nutzen-so-findest-idealen-behandlungszeitpunkt-1257>
