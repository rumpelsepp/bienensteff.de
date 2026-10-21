# imkerei – Typst-Design der Imkerei Stefan Tatschner

Briefkopf mit Logo, Farben, Überschriften, Tabellen, Kästen und Felder zum
Ausfüllen – für alle Dokumente der Imkerei, als lokales Typst-Paket.

```typst
#import "@local/imkerei:0.1.0": *
#show: imkerei.with(
  (firma: "Imkerei Stefan Tatschner", adresse: "…", kontakt: "…"),
  title: "Titel",
)

#doc-title([Titel], subtitle: [Untertitel])
#heading-bar[Überschrift]
Text …
#kasten[An][Anschrift]
#feld([Name], zeilen: 2)
#data-table(columns: (1fr, 3cm), header: ([Artikel], [Menge]), [Honig], [3])
```

Aushänge und Schilder ohne Briefkopf, in beliebigem Format:

```typst
#show: aushang.with(title: "Honigkiste", paper: "a5")
#aushang-kopf([Honigkiste], untertitel: [Selbstbedienung])
#rahmen[Bitte öffnen!]
#qr("https://bienensteff.de", width: 3cm)
#girocode(betrag: 9, zweck: "Honigkiste", width: 3.5cm)   // Überweisung
```

Bank- und Kontaktdaten stehen in `betrieb` (`betrieb.iban`, `betrieb.wero`, …).
Sie kommen nicht aus dem Paket, sondern aus dem Abschnitt `[betrieb]` der
`bscli.toml` (siehe `bscli.example.toml`); `bscli typst` reicht sie als
`--input betrieb=<JSON>` weiter.
QR-Codes erzeugt das Paket `@preview/zebra`, das Typst beim ersten Bauen
herunterlädt.

## Bauen

Mit `bscli typst`, das Typst dieses Paket mitgibt – ohne Submodul, Symlink
oder Installation unter `~/.local/share/typst`. Die Datei kann irgendwo
liegen:

```sh
bscli typst brief.typ                 # → brief.pdf daneben (PDF/A-2b)
bscli typst brief.typ --bw            # Schwarzweiß: Graustufen, logo-bw.svg
bscli typst brief.typ -o out.pdf --watch
bscli typst brief.typ -- --font-path fonts   # weitere Typst-Optionen
```

Das Paket liegt in `scripts/src/bstools/typst-packages/` und wird mit
`bscli` ausgeliefert. Bei einer neuen Version (`version` in `typst.toml`)
den Ordner `0.1.0` umbenennen und die Importe anpassen.

## Dokumente

`Aushänge/` im Repo enthält die festen Dokumente und Aushänge, gebaut mit `just`:

```sh
cd Aushänge && just            # alle; `just bw` in Schwarzweiß
```
