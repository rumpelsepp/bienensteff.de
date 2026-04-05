---
title: "Verkauf 🍯"
description: |
    Unser Honig wurde mehrfach bei der Bayerischen Honigprämierung ausgezeichnet – darüber gfrein wir uns natürlich narrisch.
    Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
    Seit 2025 tragen wir zudem das Siegel Geprüfte Qualität – Bayern für Honig.

    Dieses Jahr war das Wetter ziemlich launisch – darum gibt es heuer nur eine Sorte.
    Aber dafür ist unser Blütenhonig 🍯🌸 etwas ganz Besonderes: Er vereint das ganze Bienenjahr in einem Glas und überrascht mit einem intensiven, aromatischen Geschmack 🤤.
    Probiert ihn aus!
---

Unser Honig wurde mehrfach bei der Bayerischen Honigprämierung [ausgezeichnet]({{< relref "über-uns#auszeichnungen" >}}).
Darüber gfrein wir uns natürlich narrisch!
Seit 2025 tragen wir zudem das Siegel [Geprüfte Qualität — Bayern](/zertifikate/20250523-gq-zertifikat.pdf).
Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
Unser Honig wird zu 100 % in Bayern erzeugt, gelagert und liebevoll verarbeitet.
{.lead}

## Sortiment 2025 {#sortiment}

{{< box header="! Ausverkauft !" >}}
Unser Sortiment aus 2025 ist restlos ausverkauft! Vielen Dank an alle treuen Kunden, wir freuen uns auf die kommende Saison 2026! 🍯🐝
{{</ box >}}

Dieses Jahr war das Wetter ziemlich launisch – darum gibt es heuer nur eine Sorte.
Aber dafür ist unser Blütenhonig 🍯🌸 etwas ganz Besonderes: Er vereint das ganze Bienenjahr in einem Glas und überrascht mit einem intensiven, aromatischen Geschmack 🤤.
Probiert ihn aus!

{{< sortiment.inline dataset="sortiment" >}}
{{ $datasetName := .Get "dataset" }}

<div class="row">
  {{- range index hugo.Data $datasetName -}}
    {{ if .active }}
    <div class="col-sm-6 mb-4">
      {{ $params := merge . (dict "content" (.content | markdownify) "footer" (.footer | markdownify) "cardClass" "me-2") }}
      {{- partial "card.html" $params -}}
    </div>
    {{ end }}
  {{- end -}}
</div>
{{</ sortiment.inline >}}

Alle Produkte und unsere attraktiven Mengenrabatte findet ihr in der [aktuellen Preisliste]({{< relref "verkauf#preisliste" >}}).
Je nach Blüten und Jahreszeit kann der Honig a bisserl anders schmecken oder ausschauen – so wie’s die Natur vorgibt.
Mit der Zeit wird er fester bzw. [kristallisiert]({{< relref "honigkunde#kristallisation" >}}) – des is a ganz natürlicher Vorgang und zeigt, dass er unbehandelt is.

Wenn du ihn wieder flüssig magst, einfach ins warme Wasserbad stellen (bitte [nicht über 40 Grad]({{< relref "honigkunde#zusammenfassung" >}})).

## Verkaufsstellen

Unser Honig kann an folgenden Stellen gekauft werden.
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
          {{- range index hugo.Data.verkaufsstellen -}}
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

### Öffnungszeiten

Wir führen kein klassisches Ladengeschäft mit Öffnungszeiten.
Beim Direktverkauf am besten vorher kurz anrufen oder schreiben.
In München ist tendentiell immer an Montagen tagsüber jemand zu Hause (ganz unverbindliche Info).

## Preisliste

{{< pricelist.inline >}}
    <p>
      <strong>
      Gültig ab
      {{ time.AsTime (index hugo.Data.preisliste.timestamp) | time.Format ":date_medium"}}
      </strong>
    </p>

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
          {{- range index hugo.Data.preisliste.articles -}}
            {{ if .in_stock }}
            <tr>
            {{ else }}
            <tr class="line-through">
            {{ end }}
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

## Wissenswertes

Unsere Bienen stehen ganzjährig an festen Standorten im Münchner Grüngürtel.
Mehrmals im Jahr wird geerntet, schonend geschleudert und von Hand ins Glas gefüllt.
Unser Honig kommt direkt aus unserer eigenen Imkerei und wird weder erhitzt noch gefiltert.
Die frische Ernte gibt es jedes Jahr ab September.
In unserer [Honigdatenbank]({{< relref "datenbank" >}}) lässt sich jedes Honiglos bis zum Erntedatum zurückverfolgen.
Bei Fragen sprecht uns gerne an!

Wer sich besonders für Honig interessiert, kann in unsere [Honigkunde]({{< relref "honigkunde" >}}) eintauchen 🧑‍🎓.
Aufgrund vermehrter Rückfragen verweisen wir gerne auf den Punkt [Kristallisation]({{< relref "honigkunde#kristallisation" >}}).
