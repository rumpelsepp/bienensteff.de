// Sales per article (e.g. for the GQ check), income and box vouchers, per
// year -- rendered by `bscli verkaufszahlen` (see
// bstools.cli.verkaufszahlen.pdf_data for the data). Landscape: the article
// table has nine columns.

#import "@local/imkerei:0.1.0": *
#let d = json(bytes(sys.inputs.at("data", default: "{}")))
#show: imkerei.with(data: d, title: "Verkaufszahlen", flipped: true)

#let num = right + horizon
#let txt = left + horizon

#doc-title(
  [Verkaufszahlen],
  subtitle: [Zeitraum: #d.zeitraum#if d.filter != "" [ · #d.filter]],
)

#if d.jahre.len() == 0 [
  #v(0.5cm)
  Keine Verkäufe im Zeitraum.
]

#for (i, y) in d.jahre.enumerate() {
  if i > 0 { pagebreak() }
  block(below: 0.2cm, text(size: 16pt, weight: "bold", fill: dark, y.jahr))
  if y.hinweis != "" { small(y.hinweis) }

  if y.gruppen.len() == 0 {
    heading-bar[Verkaufte Mengen je Artikel]
    [Keine Verkäufe.]
  }
  for g in y.gruppen {
    heading-bar[#g.titel]
    data-table(
      columns: (1fr, 2.6cm, 3.2cm, 1.5cm, 1.2cm, 2cm, 2cm, 2cm, 2cm),
      align: (txt, txt, txt, txt, num, num, num, num, num),
      header: ([Artikel], [Art.-Nr.], [GTIN], [Einheit], [VPE], [Rechnung], [Box], [Gesamt], [Gläser]),
      totals: g.summen.map(s => (table.cell(colspan: 8, align: right)[#s.label], s.wert)),
      ..g
        .artikel
        .map(a => (
          a.bezeichnung,
          db-artikel(a.nr),
          a.gtin,
          a.einheit,
          a.vpe,
          a.rechnung,
          a.box,
          a.gesamt,
          strong(a.glaeser),
        ))
        .flatten(),
    )
  }
  if y.gruppen.len() > 0 {
    small[
      Rechnung = bezahlte Lexware-Rechnungen · Box = ohne Rechnung über eine Verkaufsbox (alle Gläser, die
      nicht mehr da sind, auch geklaute) · VPE = Gläser je Verkaufseinheit (z. B. 12er-Karton) · Gläser =
      Gesamt × VPE, nur für Stückware · Pauschal berechnet = Positionen mit einem Pauschalpreis statt
      einer Stückzahl, z. B. „Honig (pauschal)“; sie zählen nicht als Gläser
    ]
  }

  // Income and vouchers stay together, on the next page if need be.
  if d.mit_geld {
    block(breakable: false, grid(
      columns: (7.5cm, 1fr),
      column-gutter: 1cm,
      [
        #heading-bar[Einnahmen]
        #data-table(
          columns: (1fr, 3cm),
          align: (txt, num),
          header: ([Quelle], [Betrag]),
          totals: (([Gesamt], y.einnahmen_gesamt),),
          ..y.einnahmen.map(e => (e.quelle, e.betrag)).flatten(),
        )
      ],
      if y.barbelege.len() > 0 [
        #heading-bar[Kassenberichte der Boxen]
        #data-table(
          columns: (1.6cm, 1.9cm, 1fr, 1.7cm, 1.7cm, 1.8cm, 1.7cm, 2cm),
          align: (txt, txt, txt, num, num, num, num, num),
          header: ([Beleg], [Datum], [Box], [bar], [unbar], [Beleg], [Soll], [Fehlbetrag]),
          size: 9pt,
          ..y
            .barbelege
            .map(b => (b.beleg, b.datum, b.box, b.bar, b.unbar, strong(b.beleg_betrag), b.soll, b.fehlbetrag))
            .flatten(),
        )
      ],
    ))
  }
}
