// Design of the Imkerei Stefan Tatschner for all its documents: header
// with logo and address over a yellow line, footer with page numbers,
// bold headings, tables, boxes and fields to fill in.
//
//   #import "@local/imkerei:0.1.0": *
//   #show: imkerei.with(title: "…")
//
// Built with `bscli typst FILE`, which hands typst this package. Header and
// footer show `betrieb` below; `data:` overrides firma, adresse and kontakt
// and can add erstellt (shown in the footer) -- generated reports pass the
// business data from Grist there, see bstools.pdf.letterhead.
//
// Black and white, for printers without colour: `--input bw=1` -- grey
// instead of colours, and logo-bw.svg instead of logo.svg (the file can be
// overridden with `--input logo=…`).

#import "@preview/zebra:0.1.0": qrcode

#let bw = sys.inputs.at("bw", default: "") in ("1", "true", "yes")
#let logo = sys.inputs.at("logo", default: if bw { "logo-bw.svg" } else { "logo.svg" })

#let ink = if bw { luma(10%) } else { rgb("#263238") }
#let dark = if bw { luma(15%) } else { rgb("#37474f") }
#let muted = if bw { luma(40%) } else { rgb("#607d8b") }
#let accent = if bw { luma(30%) } else { rgb("#fec108") }
#let tint = if bw { luma(93%) } else { rgb("#fff8e1") }
#let line-color = if bw { luma(55%) } else { rgb("#90a4ae") }
#let sep = if bw { luma(80%) } else { rgb("#cfd8dc") }

// The house font, for all documents of the business.
#let schrift = "Noto Sans"

// Links: a thin underline in the line colour, so they show without
// shouting. `imkerei` and `aushang` apply it unless
// `links-unterstreichen: false`.
#let link-stil(an, body) = {
  show link: it => if an { underline(stroke: 0.4pt + line-color, offset: 1.6pt, evade: true, it) } else { it }
  body
}

// A record of the honey database (Schleuderung S-…, Eimer E-…, Los L-…,
// Abfüllung A-…) as a link to its page, e.g. #db-link("L-2026-01").
#let db-link(id) = if id == "" or id == none { [] } else {
  link("https://db.bienensteff.de/?q=" + lower(id), id)
}

// An article of the database by its number (Artikel.sku, the Lexware
// article number), shown as `body` or the number itself. No link for an
// empty number, internal articles ("_…") and free-text positions ("–").
#let db-artikel(nr, body: none) = {
  let text-or-nr = if body == none { nr } else { body }
  if nr == "" or nr == none or nr.starts-with("_") or nr == "–" { text-or-nr } else {
    link("https://db.bienensteff.de/?q=sku-" + lower(nr), text-or-nr)
  }
}

// The business, for the letterhead and for use in documents (#betrieb.email):
// the [betrieb] section of bscli.toml, which `bscli typst` and the reports
// hand over as `--input betrieb=<JSON>` -- the bank details stay out of this
// package and the repository. Keys not given are empty.
#let betrieb = (
  firma: "",
  inhaber: "",
  strasse: "",
  ort: "",
  email: "",
  telefon: "",
  webseite: "",
  kontoinhaber: "",
  iban: "",
  bic: "",
  wero: "",
) + json(bytes(sys.inputs.at("betrieb", default: "{}")))

#let imkerei(data: (:), title: "", flipped: false, links-unterstreichen: true, body) = {
  let d = (
    firma: betrieb.firma,
    adresse: betrieb.strasse + " · " + betrieb.ort,
    kontakt: betrieb.email + " · " + betrieb.telefon,
  ) + data
  let firma = d.firma
  set document(title: title, author: firma)
  set text(font: schrift, size: 10pt, fill: ink, lang: "de", region: "DE")
  set par(justify: false, leading: 0.55em)
  show: link-stil.with(links-unterstreichen)
  set page(
    paper: "a4",
    flipped: flipped,
    margin: (top: 3.6cm, bottom: 2.2cm, x: 2.2cm),
    header: block(width: 100%, inset: (bottom: 0.2cm), stroke: (bottom: 1.5pt + accent))[
      #grid(
        columns: (auto, 1fr),
        align: (left + horizon, right + horizon),
        image(logo, height: 1.6cm),
        [
          #text(size: 12pt, weight: "bold", fill: dark, firma) \
          #text(size: 9pt, fill: muted, d.at("adresse", default: "")) \
          #text(size: 9pt, fill: muted, d.at("kontakt", default: ""))
        ],
      )
    ],
    footer: context block(width: 100%, inset: (top: 0.15cm), stroke: (top: 0.5pt + sep))[
      #set align(center)
      #set text(size: 8pt, fill: muted)
      // "erstellt am" only for generated reports; a static document has none.
      #let erstellt = d.at("erstellt", default: "")
      #firma#if erstellt != "" [ · erstellt am #erstellt] · Seite #counter(page).display() von #counter(page).final().first()
    ],
  )
  body
}

// Title and an optional line below it.
#let doc-title(title, subtitle: none) = {
  text(size: 22pt, weight: "bold", fill: dark, tracking: -0.02em, title)
  if subtitle != none {
    v(-0.5cm)
    text(size: 9.5pt, style: "italic", fill: muted, subtitle)
  }
}

// Section heading: bold, in the dark colour.
#let heading-bar(body) = block(
  above: 0.7cm,
  below: 0.25cm,
  text(size: 12.5pt, weight: "bold", fill: dark, body),
)

#let label(body) = text(size: 8.5pt, weight: "bold", fill: dark, body)
#let small(body) = text(size: 7.5pt, fill: muted, body)

// Yellow box with a small caps title, e.g. an address to send something to.
#let kasten(titel, body) = block(
  width: 100%,
  above: 0.3cm,
  below: 0.5cm,
  fill: tint,
  stroke: (left: 0.12cm + accent),
  inset: (left: 0.4cm, right: 0.4cm, top: 0.3cm, bottom: 0.3cm),
  {
    set par(leading: 0.7em, spacing: 0.7em)
    text(size: 8.5pt, fill: muted, tracking: 0.03cm, upper(titel))
    linebreak()
    text(size: 10.5pt, body)
  },
)

// A field to fill in by hand: bold label, then `zeilen` writing lines.
#let feld(beschriftung, zeilen: 1) = block(above: 0.55cm, breakable: false)[
  #text(weight: "bold", fill: dark, beschriftung)
  #for _ in range(zeilen) {
    block(above: 0pt, below: 0pt, width: 100%, height: 0.95cm, stroke: (bottom: 0.5pt + line-color))
  }
]

// A table in the house style: tinted header row with a yellow line, grey
// lines between rows and columns, figures of equal width. `totals` are rows
// below the body, bold under a yellow line -- each an array of cells, which
// may span columns (table.cell(colspan: …)); the body cells may not.
#let data-table(columns: (), align: auto, header: (), totals: (), size: 10pt, ..cells) = {
  let body-rows = calc.ceil(cells.pos().len() / columns.len())
  set text(size: size, number-width: "tabular")
  show table.cell: it => if it.y > body-rows { strong(it) } else { it }
  table(
    columns: columns,
    align: align,
    inset: (x: 0.12cm, y: 0.14cm),
    stroke: (x, y) => (
      // The line above the totals is the bottom of the last body row: two
      // strokes on one edge would hide each other.
      bottom: if y == 0 { 1pt + accent } else if totals.len() > 0 and y == body-rows {
        1.5pt + accent
      } else { 0.5pt + line-color },
      right: if x < columns.len() - 1 { 0.5pt + sep } else { none },
    ),
    fill: (x, y) => if y == 0 { tint },
    table.header(..header.map(label)),
    ..cells.pos(),
    ..totals.flatten(),
  )
}

// The logo as an image, e.g. `#logo-bild(height: 3cm)` -- colour or
// black and white like the letterhead.
#let logo-bild(..args) = image(logo, ..args)

// A notice or sign: no letterhead, any paper, the house font and colours.
// Pages are centred; `margin` as in `set page`.
#let aushang(title: "", paper: "a4", flipped: false, margin: 1.2cm, links-unterstreichen: true, body) = {
  set document(title: title, author: betrieb.firma)
  set text(font: schrift, size: 12pt, fill: ink, lang: "de", region: "DE")
  set par(justify: false, leading: 0.5em)
  set page(paper: paper, flipped: flipped, margin: margin)
  show: link-stil.with(links-unterstreichen)
  body
}

// Logo beside a large title and a line below it, the head of a notice.
#let aushang-kopf(titel, untertitel: none, logo-hoehe: 2.5cm, groesse: 34pt) = grid(
  columns: (auto, 1fr),
  column-gutter: 0.5cm,
  align: horizon,
  logo-bild(height: logo-hoehe),
  {
    text(size: groesse, weight: "bold", fill: dark, titel)
    if untertitel != none {
      linebreak()
      text(size: groesse * 0.42, weight: "bold", fill: muted, untertitel)
    }
  },
)

// A framed block that catches the eye: thick yellow border, light fill.
#let rahmen(body, inset: 0.4cm, width: 100%) = block(
  width: width,
  inset: inset,
  fill: tint,
  stroke: 3pt + accent,
  radius: 4pt,
  body,
)

// A QR code, black on white with the quiet zone around it, so it scans on
// tinted boxes too; `width` or `height` as for zebra.qrcode. On white paper
// `quiet-zone: false` lines it up with the text beside it -- then leave the
// white space around it free.
#let qr(data, quiet-zone: true, background-fill: white, ..args) = qrcode(
  data,
  quiet-zone: quiet-zone,
  background-fill: background-fill,
  ..args,
)

// IBAN in groups of four: "DE12 3456 7890 …".
#let iban-lesbar(iban) = iban.clusters().chunks(4).map(c => c.join()).join(" ")

// GiroCode (EPC QR) for a transfer to the business, read by banking apps.
// `betrag` in euros (a number, none = to be entered); `zweck` is the
// reference, at most 140 characters.
#let girocode(betrag: none, zweck: "", ..args) = {
  let summe = if betrag == none { "" } else {
    let cent = int(calc.round(betrag * 100))
    "EUR" + str(calc.quo(cent, 100)) + "." + str(calc.rem(cent, 100) + 100).slice(1)
  }
  assert(
    betrieb.iban != "" and betrieb.kontoinhaber != "",
    message: "girocode: iban und kontoinhaber fehlen -- [betrieb] in bscli.toml",
  )
  let zeilen = ("BCD", "002", "1", "SCT", betrieb.bic, betrieb.kontoinhaber, betrieb.iban, summe, "", "", zweck)
  qr(zeilen.join("\n"), options: (ec-level: "m"), ..args)
}
