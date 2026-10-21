// Eigenkontrolle "Geprüfte Qualität – Bayern", honey, one year: criteria
// A1-H2 of the GQ check with the evidence from Grist, boxes to tick, defects
// and measures, signature, then the records as annexes -- rendered by
// `bscli eigenkontrolle` (see bstools.cli.eigenkontrolle.report for the data).

#import "@local/imkerei:0.1.0": *
#let d = json(bytes(sys.inputs.at("data", default: "{}")))
#show: imkerei.with(data: d, title: "Eigenkontrolle GQ-Bayern Honig " + d.jahr, flipped: true)

#let num = right + horizon
#let txt = left + horizon
#let box-leer = box(width: 0.75em, height: 0.75em, stroke: 0.6pt + ink, baseline: 0.1em)
#let ankreuzen(beschriftung) = [#box-leer #h(0.2em) #beschriftung]
#let linie(breite) = box(width: breite, stroke: (bottom: 0.5pt + line-color), height: 1em)

#doc-title(
  [Eigenkontrolle #d.jahr],
  subtitle: [„Geprüfte Qualität – Bayern“ · Honig · Erzeugung, Lagerung, Vermarktung],
)

#v(0.3cm)
#grid(
  columns: (auto, 1fr, auto, 1fr),
  column-gutter: 0.3cm,
  row-gutter: 0.45cm,
  align: (x, y) => if y == 2 { left + top } else { left + bottom },
  label[Betrieb], [#d.firma],
  label[Bienenvölker], [#d.voelker_anzahl am #d.stichtag],
  label[Datum der Kontrolle], linie(100%),
  label[durchgeführt von], linie(100%),
  label[Bereiche],
  grid.cell(colspan: 3, stack(
    spacing: 0.3cm,
    ankreuzen[Honiggewinnung und -lagerung],
    ankreuzen[Vermarktung an Endverbraucher],
    ankreuzen[Vermarktung an Wiederverkäufer],
  )),
)

#small[
  Kriterien nach dem Prüfbericht „Geprüfte Qualität – Bayern“ Honig (GQ-Version 01/25). k.o. = Ausschlusskriterium.
  Der Nachweis nennt, was in Grist erfasst ist; ob ein Kriterium erfüllt ist, wird beim Ankreuzen entschieden.
  Fett gedruckte Hinweise bitte prüfen.
]

// An unreliable result (analysis before homogenisation): grey, italic.
#let vorlaeufig(body) = text(fill: muted, style: "italic", body)

#let nachweis(k) = {
  set par(leading: 0.4em, spacing: 0.35em)
  for n in k.nachweis {
    if n.warn { strong(n.text) } else if n.at("vorlaeufig", default: false) { vorlaeufig(n.text) } else { n.text }
    parbreak()
  }
  if k.nachweis.len() == 0 { linie(100%) }
}

#for g in d.gruppen {
  heading-bar[#g.gruppe #h(0.3em) #g.titel]
  data-table(
    columns: (1.1cm, 8cm, 1fr, 1cm, 1cm),
    align: (left + top, left + top, left + top, center + top, center + top),
    header: ([Nr.], [Kriterium], [Nachweis], [ja], [nein]),
    size: 8.5pt,
    ..g
      .kriterien
      .map(k => (
        [*#k.nr*#if k.ko [ \ #text(size: 7pt, fill: muted)[k.o.]]],
        k.text,
        nachweis(k),
        box-leer,
        box-leer,
      ))
      .flatten(),
  )
}

#block(breakable: false)[
  #heading-bar[Mängel und Maßnahmen]
  #data-table(
    columns: (1.2cm, 1fr, 1fr, 2.2cm, 2.2cm),
    header: ([Krit.], [Abweichung], [Maßnahme], [Frist], [erledigt am]),
    size: 9pt,
    ..range(6).map(_ => ([#v(0.5cm)], [], [], [], [])).flatten(),
  )
  #v(1.2cm)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 1.5cm,
    [#line(length: 100%, stroke: 0.5pt + line-color) #small[Ort, Datum]],
    [#line(length: 100%, stroke: 0.5pt + line-color) #small[Unterschrift]],
  )
]

// -- annexes ---------------------------------------------------------------

#let a = d.anlagen
#let anlage(nr, titel) = heading-bar[Anlage #nr: #titel]
#let leer(liste, body) = if liste.len() == 0 [Keine Einträge #d.jahr.] else { body }

#pagebreak()
#anlage(1, [Völkerverzeichnis: Völker am #d.stichtag])
#leer(a.voelker, data-table(
  columns: (1.2cm, 1.8cm, 4cm, 1fr, 2.6cm),
  header: ([VN], [Boden-Nr.], [Typ], [Standort], [seit]),
  size: 8.5pt,
  ..a.voelker.map(v => (v.vn, v.bn, v.typ, v.standort, v.von)).flatten(),
))

#anlage(2, [Standorte])
#leer(a.standorte, data-table(
  columns: (2cm, 1fr, 6cm),
  header: ([Kürzel], [Name], [Koordinaten (WGS84)]),
  size: 8.5pt,
  ..a
    .standorte
    .map(s => (
      s.kuerzel,
      s.name,
      if s.koordinaten == "" [–] else if s.karte == "" { s.koordinaten } else { link(s.karte, s.koordinaten) },
    ))
    .flatten(),
))
#small[Breite, Länge in Grad; der Link führt zum Flugkreis im BayernAtlas.]

#anlage(3, [Ernte: Schleuderungen #d.jahr])
#leer(a.ernte, data-table(
  columns: (2.2cm, 2cm, 1.4cm, 1fr, 1.2cm, 3cm, 1.8cm),
  align: (txt, txt, num, txt, num, txt, num),
  header: ([Nr.], [Datum], [Völker], [Standort], [Eimer], [Lose], [Menge]),
  size: 8.5pt,
  ..a
    .ernte
    .map(e => (db-link(e.nr), e.datum, e.voelker, e.standorte, e.eimer, e.lose.map(db-link).join([, ]), e.kg))
    .flatten(),
))

#anlage(4, [Lose und Analysen])
#leer(a.lose, data-table(
  columns: (2.2cm, 3.2cm, 1cm, 1.8cm, 1fr, 1.6cm, 2.6cm, 2.2cm),
  align: (txt, txt, txt, num, txt, num, num, num),
  header: ([Los], [Sorte], [GQ], [Menge], [Analyse], [Wasser], [Invertase (U/kg)], [HMF (mg/kg)]),
  size: 8.5pt,
  ..a
    .lose
    .map(l => (
      db-link(l.los),
      l.sorte,
      l.gq,
      l.kg,
      if l.analysen.len() == 0 [–] else {
        for an in l.analysen [
          #if an.vorher {
            vorlaeufig[#an.bericht#if an.aussteller != "" [, #an.aussteller] (vor Homogenisierung)\*]
          } else [#an.bericht#if an.aussteller != "" [, #an.aussteller]] \
        ]
      },
      // Before homogenisation: grey with an asterisk, never bold -- the
      // value does not stand for the batch, so it is not judged.
      ..("wasser", "invertase", "hmf").map(k => for an in l.analysen [
        #if an.vorher { vorlaeufig[#an.at(k)\*] } else if an.at(k + "_warn") { strong(an.at(k)) } else { an.at(k) } \
      ]),
    ))
    .flatten(),
))
#if a.lose.any(l => l.analysen.any(an => an.vorher)) [#small[
  \* Vor Homogenisierung: Probe aus einzelnen Eimern, nicht aus dem fertigen Los -- nicht
  verlässlich, nur zur Orientierung; nicht gegen die Grenzwerte bewertet. Maßgeblich ist die
  Analyse nach der Homogenisierung.
]]

#anlage(5, [Abfüllungen #d.jahr])
#leer(a.abfuellungen, data-table(
  columns: (2cm, 2.2cm, 2.2cm, 1cm, 1fr, 1.4cm, 1.6cm, 2.2cm, 3cm),
  align: (txt, txt, txt, txt, txt, num, num, txt, txt),
  header: ([Nr.], [Datum], [Los], [GQ], [Artikel], [Stück], [kg], [MHD], [DIB-Nr.]),
  size: 8.5pt,
  ..a.abfuellungen.map(f => (db-link(f.nr), f.datum, db-link(f.los), f.gq, db-artikel(f.sku, body: f.artikel), f.stueck, f.kg, f.mhd, f.dib)).flatten(),
))
#if a.abfuellungen.len() > 0 [#small[GQ = Artikel GQ-Bayern-zertifiziert (Verkaufdetails des Artikels)]]

#anlage(6, [Reinigungsprotokoll #d.jahr])
#leer(a.reinigung, data-table(
  columns: (2.2cm, 1fr, 5.5cm, 2.4cm, 1fr),
  header: ([Datum], [Objekt], [Mittel], [Schädlinge], [Kommentar]),
  size: 8.5pt,
  ..a
    .reinigung
    .map(c => (c.datum, c.objekt, c.mittel, if c.schaedlinge == "Befall" { strong(c.schaedlinge) } else { c.schaedlinge }, c.kommentar))
    .flatten(),
))

#anlage(7, [Bestandsbuch #d.jahr])
#leer(a.bestandsbuch, data-table(
  columns: (2cm, 1.2cm, 1.8cm, 2.4cm, 1fr, 1.6cm, 2.2cm),
  header: ([Datum], [VN], [Boden-Nr.], [Gabe], [Arzneimittel], [Menge], [Wartezeit bis]),
  size: 8.5pt,
  ..a.bestandsbuch.map(b => (b.datum, b.vn, b.bn, b.gabe, b.mittel, b.menge, b.wartezeit)).flatten(),
))

#anlage(8, [Fortbildungen bis #d.jahr])
#if a.fortbildungen.len() == 0 [Keine Fortbildungen eingetragen.] else {
  data-table(
    columns: (2.2cm, 1fr, 1fr),
    header: ([Datum], [Fortbildung], [Veranstalter]),
    size: 8.5pt,
    ..a
      .fortbildungen
      .map(f => (f.datum, if f.url == "" { f.titel } else { link(f.url, f.titel) }, f.veranstalter))
      .flatten(),
  )
  small[Nachweise auf bienensteff.de, Über uns: Fachkundenachweise.]
}
