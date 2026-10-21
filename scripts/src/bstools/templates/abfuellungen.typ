// Fillings per year with the batches they came from -- rendered by
// `bscli abfuellungen` (see bstools.cli.abfuellungen.report for the data).
// Landscape: the filling table has ten columns.

#import "@local/imkerei:0.1.0": *
#let d = json(bytes(sys.inputs.at("data", default: "{}")))
#show: imkerei.with(data: d, title: "Abfüllungen", flipped: true)

#let num = right + horizon
#let txt = left + horizon

#doc-title([Abfüllungen], subtitle: [Zeitraum: #d.zeitraum#if d.filter != "" [ · #d.filter]])

#if d.jahre.len() == 0 [
  #v(0.5cm)
  Keine Abfüllungen im Zeitraum.
]

#for (i, y) in d.jahre.enumerate() {
  if i > 0 { pagebreak() }
  block(below: 0.2cm, text(size: 16pt, weight: "bold", fill: dark, y.jahr))

  heading-bar[Abfüllungen]
  data-table(
    columns: (1.9cm, 2cm, 2cm, 1fr, 1cm, 1fr, 1.3cm, 1.6cm, 2cm, 2.6cm),
    align: (txt, txt, txt, txt, txt, txt, num, num, txt, txt),
    header: ([Nr.], [Datum], [Los], [Sorte], [GQ], [Artikel], [Stück], [kg], [MHD], [DIB-Nr.]),
    size: 9pt,
    totals: ((table.cell(colspan: 6, align: right)[Summe], y.summe_stueck, y.summe_kg, [], []),),
    ..y
      .abfuellungen
      .map(a => (db-link(a.nr), a.datum, db-link(a.los), a.sorte, a.gq, db-artikel(a.sku, body: a.artikel), a.stueck, a.kg, a.mhd, a.dib))
      .flatten(),
  )
  small[GQ = Artikel GQ-Bayern-zertifiziert (Verkaufdetails des Artikels); in der Tabelle Lose: Los GQ-konform]

  // "vorher abgefüllt" only when a batch was already filled from before
  // this year; otherwise the column would stay empty.
  let vorher = y.lose.any(l => l.vorher != "")
  block(breakable: false)[
    #heading-bar[Lose]
    #data-table(
      columns: (2.2cm, 1fr, 1cm, 2.6cm, ..if vorher { (3cm,) }, 3cm, 2.8cm),
      align: (txt, txt, txt, num, ..if vorher { (num,) }, num, num),
      header: ([Los], [Sorte], [GQ], [geerntet], ..if vorher { ([vorher abgefüllt],) }, [abgefüllt #y.jahr], [Rest]),
      size: 9pt,
      ..y
        .lose
        .map(l => (db-link(l.los), l.sorte, l.gq, l.geerntet, ..if vorher { (l.vorher,) }, l.im_jahr, strong(l.rest)))
        .flatten(),
    )
    #small[
      geerntet = Summe der Eimer des Loses ·
      #if vorher [vorher abgefüllt = aus dem Los schon vor #y.jahr abgefüllt ·]
      Rest = geerntet − #if vorher [vorher −] abgefüllt #y.jahr: noch im Eimer oder Schwund
    ]
  ]

  if y.konflikte.len() > 0 {
    kasten[Zu prüfen][
      #for k in y.konflikte [- #k]
    ]
  }
}
