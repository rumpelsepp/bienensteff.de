// Kassenbericht of one emptying of an honesty box, rendered by
// `bscli kassenbericht`. All data comes in as JSON via `--input data=...`;
// numbers and dates are already formatted, so this file only does layout.
// Design follows Widerrufsbelehrung.odt (header with logo, yellow accents).

#let d = json(bytes(sys.inputs.at("data", default: "{}")))

#let ink = rgb("#263238")
#let dark = rgb("#37474f")
#let muted = rgb("#607d8b")
#let accent = rgb("#fec108")
#let tint = rgb("#fff8e1")
#let line-color = rgb("#90a4ae")
#let sep = rgb("#cfd8dc")

#set document(title: "Kassenbericht " + d.at("nummer", default: ""), author: d.at("firma", default: ""))
#set text(font: "Liberation Sans", size: 10pt, fill: ink, lang: "de", region: "DE")
#set par(justify: false, leading: 0.55em)

#set page(
  paper: "a4",
  margin: (top: 3.6cm, bottom: 2.2cm, x: 2.2cm),
  header: block(width: 100%, inset: (bottom: 0.2cm), stroke: (bottom: 1.5pt + accent))[
    #grid(
      columns: (auto, 1fr),
      align: (left + horizon, right + horizon),
      image("logo.svg", height: 1.6cm),
      [
        #text(size: 12pt, weight: "bold", fill: dark, d.at("firma", default: "")) \
        #text(size: 9pt, fill: muted, d.at("adresse", default: "")) \
        #text(size: 9pt, fill: muted, d.at("kontakt", default: ""))
      ],
    )
  ],
  footer: context block(width: 100%, inset: (top: 0.15cm), stroke: (top: 0.5pt + sep))[
    #set align(center)
    #set text(size: 8pt, fill: muted)
    #d.at("firma", default: "") · Seite #counter(page).display() von #counter(page).final().first()
  ],
)

#let heading-bar(body) = block(
  above: 0.7cm,
  below: 0.25cm,
  inset: (left: 0.25cm),
  stroke: (left: 0.12cm + accent),
  text(size: 12.5pt, weight: "bold", fill: dark, body),
)

#let label(body) = text(size: 8.5pt, weight: "bold", fill: dark, body)

// Title
#text(size: 22pt, weight: "bold", fill: dark, tracking: -0.02em)[Kassenbericht Verkaufsbox]
#v(-0.5cm)
#text(size: 9.5pt, style: "italic", fill: muted)[Zählung und Leerung der Box, erstellt aus Grist am #d.at("erstellt", default: "")]

// Header fields
#v(0.3cm)
#grid(
  columns: (1fr, 1fr, 2fr),
  column-gutter: 0.6cm,
  row-gutter: 0.15cm,
  label[Nummer], label[Datum], label[Box],
  ..(d.nummer, d.datum, d.box).map(v => block(
    width: 100%,
    inset: (bottom: 0.1cm),
    stroke: (bottom: 0.5pt + line-color),
    text(size: 11pt, weight: "bold", v),
  )),
)

// Jars
#heading-bar[1. Gläser]
#table(
  columns: (1fr, 2.8cm, 2.8cm),
  align: (left + horizon, right + horizon, right + horizon),
  inset: (x: 0.12cm, y: 0.14cm),
  stroke: (x, y) => (
    bottom: if y == 0 { 1pt + accent } else { 0.5pt + line-color },
    right: if x < 2 { 0.5pt + sep } else { none },
  ),
  fill: (x, y) => if y == 0 { tint },
  table.header(label[Artikel], label[gezählt], label[aufgefüllt auf]),
  ..d.positionen
    .map(p => (
      [#text(size: 10pt, p.bezeichnung) \ #text(size: 7.5pt, fill: muted, p.sku)],
      text(size: 11pt, p.gezaehlt),
      text(size: 11pt, p.aufgefuellt),
    ))
    .flatten(),
)

// Money
#heading-bar[2. Geld]
#let money-row(title, hint, value, total: false) = (
  table.cell(stroke: if total { (top: 1.5pt + accent) } else { none })[
    #text(size: 11pt, weight: "bold", title) \ #text(size: 7.5pt, fill: muted, hint)
  ],
  table.cell(stroke: if total { (top: 1.5pt + accent) } else { none }, align: right + horizon)[
    #text(size: 11pt, weight: if total { "bold" } else { "regular" }, value)
  ],
)
#block(fill: tint, stroke: (left: 0.12cm + accent), width: 100%)[
  #table(
    columns: (1fr, 4.5cm),
    inset: (x: 0.4cm, y: 0.2cm),
    stroke: none,
    ..money-row([Bargeld in der Box], [gezählt bei der Leerung], d.bargeld),
    ..money-row([\+ unbar seit der letzten Leerung], [Wero/SEPA-Eingänge mit dem Verwendungszweck der Box], d.unbar),
    ..money-row([\= Betrag für den Beleg in Lexware], [Bargeld + unbar], d.beleg_betrag, total: true),
  )
]

#if d.at("bemerkung", default: "") != "" [
  #heading-bar[Bemerkung]
  #d.bemerkung
]
