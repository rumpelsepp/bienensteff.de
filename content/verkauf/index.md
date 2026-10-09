---
title: "Verkauf 🍯"
description: |
    Unser Honig wurde mehrfach bei der Bayerischen Honigprämierung ausgezeichnet – darüber gfrein wir uns natürlich narrisch.
    Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
    Seit 2025 tragen wir zudem das Siegel Geprüfte Qualität – Bayern für Honig.
---

Unser Honig wurde mehrfach bei der Bayerischen Honigprämierung [ausgezeichnet]({{< relref "über-uns#auszeichnungen" >}}).
Darüber gfrein wir uns natürlich narrisch!
Seit 2025 tragen wir zudem das Siegel [Geprüfte Qualität — Bayern](/zertifikate/20250523-gq-zertifikat.pdf).
Ein schöner Beleg für echte Qualität aus unserer kleinen Imkerei.
Unser Honig wird zu 100 % in Bayern erzeugt, gelagert und liebevoll verarbeitet.
{.lead}

Ihr wollt Honig? Schreibt uns kurz mit Sorte und Menge – oder nehmt ihn direkt an einer unserer [Verkaufsstellen](#verkaufsstellen) mit.

<a class="btn btn-primary mb-3" href="{{< relref "kontakt#honig-kaufen--bestellanfrage" >}}">
<i class="bi bi-envelope" aria-hidden="true"></i> Bestellanfrage &amp; Kontakt
</a>

## Sortiment 2026 {#sortiment}

{{< sortiment.inline dataset="sortiment" >}}
{{ $datasetName := .Get "dataset" }}

<div class="row row-cols-1 row-cols-sm-2 row-cols-lg-3 g-4 mb-4">
  {{- range index hugo.Data $datasetName -}}
    {{ if .active }}
    <div class="col">
      {{ $content := .content | markdownify }}
      {{/* Overlays on the photo, the CSS lifts them out of the card body:
           .gqb puts the GQ-Bayern seal in the top left corner, .image_note
           is e.g. "Abbildung ähnlich" for a photo borrowed from a similar
           product. */}}
      {{ if .gqb }}
        {{ $seal := partial "link.html" (dict
          "href" "https://www.gq-bayern.de"
          "class" "sortiment-seal"
          "icon" false
          "text" (`<img src="/GQB-Logo-ohne-txt.svg" loading="lazy" alt="Geprüfte Qualität – Bayern">` | safeHTML)
        ) }}
        {{ $content = printf `%s%s` $content $seal | safeHTML }}
      {{ end }}
      {{ with .image_note }}
        {{ $content = printf `%s<span class="sortiment-image-note">%s</span>` $content (. | htmlEscape) | safeHTML }}
      {{ end }}
      {{ $params := merge . (dict "content" $content "footer" (.footer | markdownify) "cardClass" "sortiment-card h-100") }}
      {{- partial "card.html" $params -}}
    </div>
    {{ end }}
  {{- end -}}
</div>
{{</ sortiment.inline >}}

Preise – auch für größere Mengen – nennen wir euch gern auf [Anfrage]({{< relref "kontakt#honig-kaufen--bestellanfrage" >}}).
Je nach Blüten und Jahreszeit kann der Honig a bisserl anders schmecken oder ausschauen – so wie’s die Natur vorgibt.
Mit der Zeit wird er fester bzw. [kristallisiert]({{< relref "honigkunde#kristallisation" >}}) – des is a ganz natürlicher Vorgang und zeigt, dass er unbehandelt is.

Wenn du ihn wieder flüssig magst, einfach ins warme Wasserbad stellen (bitte [nicht über 40 Grad]({{< relref "honigkunde#honig-verflüssigen" >}})).

## Verkaufsstellen

Unser Honig kann an folgenden Stellen gekauft werden.
Wir nehmen Honiggläser gerne gespült zurück – Etikett bitte, wenn möglich, entfernen.

{{< verkaufsstellen.inline >}}
    <table class="table table-striped table-bordered">
        <thead>
            <tr>
              <th scope="col">Verkaufsstelle</th>
              <th scope="col">Art</th>
              <th scope="col">Adresse</th>
              <th scope="col">Kontakt</th>
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

Wir führen kein klassisches Ladengeschäft mit festen Öffnungszeiten.
Für den Direktverkauf an der Haustür bitte vorher kurz anrufen oder schreiben – wie ihr uns erreicht und wann meist jemand da ist, steht auf der [Kontaktseite]({{< relref "kontakt" >}}).

## Bestellung

Auf Wunsch füllen wir den Honig auch in mitgebrachte Gläser oder auch Eimer ab.
Sonderabfüllungen bitte **bis Anfang September** anfragen – dann können wir’s passend einplanen.

Die Abgabe erfolgt in haushaltsüblichen Mengen und nur solange der Vorrat reicht.
Wir sind nach §19 UStG als Kleinbetrieb umsatzsteuerbefreit – es wird keine Mehrwertsteuer ausgewiesen.

## Wissenswertes

Unsere Bienen stehen ganzjährig an festen Standorten im [Münchner Grüngürtel]({{< relref "über-uns#regionalität" >}}).
Mehrmals im Jahr wird geerntet, schonend geschleudert und von Hand ins Glas gefüllt.
Unser Honig kommt direkt aus unserer eigenen Imkerei und wird weder erhitzt noch gefiltert.
Die frische Ernte gibt es jedes Jahr ab September.
In unserer [Honigdatenbank]({{< relref "datenbank" >}}) lässt sich jedes Honiglos bis zum Erntedatum zurückverfolgen.
Bei Fragen sprecht uns gerne an – alle Wege zu uns findet ihr auf der [Kontaktseite]({{< relref "kontakt" >}}).

Wer sich besonders für Honig interessiert, kann in unsere [Honigkunde]({{< relref "honigkunde" >}}) eintauchen 🧑‍🎓.
Aufgrund vermehrter Rückfragen verweisen wir gerne auf den Punkt [Kristallisation]({{< relref "honigkunde#kristallisation" >}}).
