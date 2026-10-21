// Kassenbericht of one emptying of an honesty box, rendered by
// `bscli kassenbericht` (see bstools.cli.kassenbericht for the data).

#import "@local/imkerei:0.1.0": *
#let d = json(bytes(sys.inputs.at("data", default: "{}")))
#show: imkerei.with(data: d, title: "Kassenbericht " + d.at("nummer", default: ""))

#doc-title([Kassenbericht Verkaufsbox], subtitle: [Zählung und Leerung der Box])

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

#heading-bar[1. Gläser]
#data-table(
  columns: (1fr, 2.8cm, 2.8cm),
  align: (left + horizon, right + horizon, right + horizon),
  header: ([Artikel], [gezählt], [aufgefüllt auf]),
  ..d.positionen
    .map(p => (
      [#p.bezeichnung \ #small(db-artikel(p.sku))],
      text(size: 11pt, p.gezaehlt),
      text(size: 11pt, p.aufgefuellt),
    ))
    .flatten(),
)

#heading-bar[2. Geld]
#let money-row(title, hint, value, total: false) = (
  table.cell(stroke: if total { (top: 1.5pt + accent) } else { none })[
    #text(size: 11pt, weight: "bold", title) \ #small(hint)
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
