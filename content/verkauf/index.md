---
title: "Verkauf 🍯"
description: |
    Unser Honig hat 2024 bei der Bayerischen Honigprämierung eine Goldmedaille erhalten – darüber gfrein wir uns natürlich narrisch.
    Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
    Seit 2025 tragen wir zudem das Siegel Programm Geprüfte Qualität – Bayern.

    Dieses Jahr war das Wetter ziemlich launisch – darum gibt es heuer nur eine Sorte.
    Aber dafür ist unser Blütenhonig 🍯🌸 etwas ganz Besonderes: Er vereint das ganze Bienenjahr in einem Glas und überrascht mit einem intensiven, aromatischen Geschmack 🤤.
    Probiert ihn aus!
---

Unser Honig hat 2024 bei der Bayerischen Honigprämierung eine [Goldmedaille](/auszeichnungen/2024-11-03-honigpraemierung.pdf) erhalten :w
 darüber gfrein wir uns natürlich narrisch.
Seit 2025 tragen wir zudem das Siegel [Geprüfte Qualität — Bayern](/zertifikate/20250523-gq-zertifikat.pdf).
Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
Unser Honig wird zu 100 % in Bayern erzeugt, gelagert und liebevoll verarbeitet.
{.lead}

Unsere Bienen stehen ganzjährig an festen Standorten im Münchner Grüngürtel.
Mehrmals im Jahr wird geerntet, schonend geschleudert und von Hand ins Glas gefüllt.
Unser Honig kommt direkt aus unserer eigenen Imkerei und wird weder erhitzt noch gefiltert.
Die frische Ernte gibt es jedes Jahr ab September.
In unserer [Honigdatenbank]({{< relref "datenbank" >}}) lässt sich jedes Honiglos bis zum Erntedatum zurückverfolgen.
Bei Fragen sprecht uns gerne an!
{.lead}

Wer sich besonders für Honig interessiert, kann in unsere [Honigkunde]({{< relref "honigkunde" >}}) eintauchen 🧑‍🎓.
{.lead}

## Unser Sortiment 2025

Dieses Jahr war das Wetter ziemlich launisch – darum gibt es heuer nur eine Sorte.
Aber dafür ist unser Blütenhonig 🍯🌸 etwas ganz Besonderes: Er vereint das ganze Bienenjahr in einem Glas und überrascht mit einem intensiven, aromatischen Geschmack 🤤.
Probiert ihn aus!

{{< cards dataset="sortiment" >}}

Alle Produkte und unsere attraktiven Mengenrabatte findet ihr in der [aktuellen Preisliste]({{< relref "verkauf#preisliste" >}}).
Je nach Blüten und Jahreszeit kann der Honig a bisserl anders schmecken oder ausschauen – so wie’s die Natur vorgibt.
Mit der Zeit wird er fester bzw. [kristallisiert]({{< relref "honigkunde#kristallisation" >}}) – des is a ganz natürlicher Vorgang und zeigt, dass er unbehandelt is.

Wenn du ihn wieder flüssig magst, einfach ins warme Wasserbad stellen (bitte [nicht über 40 Grad]({{< relref "honigkunde#zusammenfassung" >}})).

## Verkaufsstellen

Unser Honig kann an folgenden Stellen gekauft werden.
Beim Direktverkauf am besten vorher kurz anrufen oder schreiben.
Wir nehmen Honiggläser gerne gespült zurück – Etikett bitte, wenn möglich, entfernen.

{{< verkaufsstellen.inline >}}
    <table class="table table-striped table-bordered">
        <thead>
            <tr>
              <th>Verkaufsstelle</th>
              <th>Art</th>
              <th>Adresse</th>
              <th>Kontakt</th>
            </tr>
        </thead>
        <tbody>
          {{- range index .Page.Site.Data.verkaufsstellen -}}
            {{ if .active }}
            <tr>
                <td>{{ .name | markdownify }}</td>
                <td>{{ .type | markdownify}}</td>
                <td>{{ .address | markdownify }}</td>
                <td>{{ .contact | markdownify }}</td>
            </tr>
            {{ end }}
          {{- end -}}
        </tbody>
    </table>
{{</ verkaufsstellen.inline >}}

## Preisliste

**Gültig ab 12.09.2025**

{{< pricelist.inline >}}
    <table class="table table-striped table-bordered">
        <thead>
            <tr>
              <th>Art.-Nr.</th>
              <th>Produkt</th>
              <th>Marke</th>
              <th><acronym title="Verkaufseinheit">VKE</acronym></th>
              <th><acronym title="Verpackungseinheit">VPE</acronym></th>
              <th>Preis</th>
              <th>Preis / kg</th>
            </tr>
        </thead>
        <tbody>
          {{- range index .Page.Site.Data.preisliste -}}
            <tr>
                <td>{{ .sku }}</td>
                <td>{{ .product_name }}</td>
                <td>{{ .brand }}</td>
                <td>{{ .vke }}</td>
                <td>{{ .vpe }}</td>
                <td>{{ .price }}</td>
                <td>{{ .price_per_kg }}</td>
            </tr>

          {{- end -}}
        </tbody>
    </table>
{{</ pricelist.inline >}}

Wer gleich **sechs Gläser oder mehr** mitnimmt, zahlt a bissal weniger. 🙂
Auf Wunsch füllen wir den Honig auch in mitgebrachte Gläser oder auch Eimer ab.
Sonderabfüllungen bitte **bis Anfang September** anfragen – dann können wir’s passend einplanen.

Alle Preise sind Endverbraucherpreise (EVP) im Direktverkauf.
Die Abgabe erfolgt in haushaltsüblichen Mengen und nur solange der Vorrat reicht.
Wir sind nach §19 UStG als Kleinbetrieb umsatzsteuerbefreit – es wird keine Mehrwertsteuer ausgewiesen.
Durchgestrichene Sorten sind derzeit ausverkauft.
