---
title: Trachtnet Auswertungen
---

Eigene Auswertungen der TrachtNet-Waagstöcke, vor allem für die Regionen, in denen wir imkern.
Die Daten stellt die [Agrarmeteorologie Rheinland-Pfalz](https://www.wetter.rlp.de/Internet/global/inetcntr.nsf/dlr_web_full.xsp?src=N7V9968V90&p1=3M315JB66X) bereit; interaktiv lassen sie sich auch in der [TrachtNet-Weboberfläche](https://dlr-web-daten1.aspdienste.de/cgi-bin/tdsa/tdsa_client.pl) ansehen.
Die Grafiken werden täglich aktualisiert; die letzten zwei Tage fehlen, weil TrachtNet sie erst vorläufig berechnet.
{.lead}

{{< trachtnet-year-select >}}

{{< box header="Kurz gesagt" >}}
- **Tracht:** Das 7-Tage-Mittel der täglichen Gewichtszunahme einer Region liegt mindestens drei Tage lang bei 0,5 kg pro Tag oder mehr.
- **Trachtlücke:** mindestens 7 Tage ohne Tracht zwischen zwei Trachtphasen.
- **Gestrichelt oder hohl gezeichnet:** unsicher – meist fehlen dort Daten. 🐝
{{< /box >}}

<details class="fold-details">
<summary>Methodik im Detail</summary>

**Daten.**
Grundlage ist die tägliche Gewichtsänderung jedes Waagstocks, gemittelt über alle Waagen einer Region.
Tage ohne Daten, längere Null-Reihen abgeschalteter Waagen und die zwei noch vorläufigen letzten Tage fliegen vorher raus.

**Tracht.**

- Gerechnet wird mit dem 7-Tage-Mittel statt mit Einzeltagen, damit ein kühler Tag die Tracht nicht unterbricht.
  Das Mittel läuft über Kalendertage – über Datenlöcher hinweg wird nicht gemittelt.
- Schwelle: 0,5 kg pro Tag, mindestens drei Tage lang, Beginn frühestens im März.
- Liegen zwischen zwei Phasen weniger als 7 Tage, gelten sie als eine – über ein paar kühle Tage oder ein kurzes Datenloch hinweg.
- **Trachtbeginn** ist der erste Tag der ersten Trachtphase des Jahres, **Trachtende** der letzte Tag der letzten.

**Trachtlücke.**
Mindestens 7 Tage zwischen zwei Trachtphasen.
Fehlen in einer Lücke an mehr als zwei Tagen die Daten, ist sie nur gestrichelt umrandet und zählt nicht als längste Lücke des Jahres.

**Unsichere Ränder.**
Haben weniger als 7 der 14 Tage vor dem Trachtbeginn (bzw. nach dem Trachtende) Daten, ist der Punkt hohl gezeichnet und zählt für den Trend nicht.

**Median und Trend.**
Die typische Trachtlücke ergibt sich aus dem Median von Beginn und Länge der längsten Lücke jedes Jahres – anders als ein Mittelwert verzerren ihn einzelne Ausreißerjahre nicht.
Jahre ohne Lücke gehen nicht ein.
Die Trendgerade läuft durch die Mitten dieser Lücken; ein R² unter 0,25 heißt: eher Zufall als Trend.

**Grenzen.**

- Hinter einer Region stecken oft nur wenige Waagen; die Karte zeigt ihre Zahl im Tooltip.
- Fehlen einem Landkreis an mehr als 10 % der Saisontage die Daten, fällt seine Summe zu niedrig aus; die Karte zeigt ihn grau statt eingefärbt.
- Gemessen wird der Nettozuwachs, der Verbrauch des Volks ist also schon abgezogen – die 0,5 kg sind eine Faustregel.
- Fütterungen oder andere Eingriffe am Waagstock können wie Eintrag aussehen.

</details>

## Bayern

{{< klima-widget station_id="03379" region="Bayern" >}}

{{< trachtnet-widget region="Bayern" type="derivative" >}}

{{< trachtnet-widget region="Bayern" type="progress" >}}

{{< trachtnet-widget region="Bayern" type="trend" >}}

Wann in der Saison dagegen kein Eintrag mehr kommt – die Trachtlücken – zeigt die nächste Grafik: die Zeitfenster, in denen geschleudert und aufgebaut werden kann.

{{< trachtnet-widget region="Bayern" type="gaps" >}}

Die folgende Karte zeigt, wo die Völker der TrachtNet-Waagstöcke in der Saison am meisten eintragen – nützlich bei der Frage, wo ein Bienenstand lohnt.

{{< trachtnet-widget region="Bayern" type="map" height="520px" >}}

Kreisgrenzen der Karte: Datenlizenz Deutschland – Namensnennung – Version 2.0 ([dl-de/by-2.0](https://www.govdata.de/dl-de/by-2-0)), © Bundesamt für Kartographie und Geodäsie.

### Oberbayern

<details class="fold-details">
<summary>Diagramme</summary>

{{< trachtnet-widget region="Oberbayern" type="derivative" >}}

{{< trachtnet-widget region="Oberbayern" type="progress" >}}

{{< trachtnet-widget region="Oberbayern" type="gaps" >}}

</details>

### Niederbayern

<details class="fold-details">
<summary>Diagramme</summary>

{{< trachtnet-widget region="Niederbayern" type="derivative" >}}

{{< trachtnet-widget region="Niederbayern" type="progress" >}}

{{< trachtnet-widget region="Niederbayern" type="gaps" >}}

</details>

---

{{< blockquote caption="https://dlr-web-daten1.aspdienste.de/cgi-bin/tdsa/tdsa_client.pl/" >}}
Im TrachtNet Deutschland wird an mittlerweile bald 830 Standorten (Stand: 05.05.25) kontinuierlich der Nahrungseintrag von Bienenvölkern (Nektar/Honig und Pollen) erfasst, verrechnet und zu öffentlich abrufbaren Diagrammen aufbereitet. An dieser Stelle werden die täglichen Gewichtsdifferenzen Tag für Tag aufsummiert. In den ersten Wochen des Jahres fressen die Bienen mehr als sie sammeln und die Bienenvölker werden leichter. Ab Trachtbeginn sammeln die Bienen mehr und legen Vorräte an. Damit nehmen die Volksgewichte kontinuierlich zu, mit Ausnahme von Trachtlücken. Auch das Trachtende wird sichtbar, wenn die Gewichte wieder kontinuierlich bis zum Jahresende abnehmen.
{{</ blockquote >}}
