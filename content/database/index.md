---
title: Honigdatenbank
---

Jedes unserer Honiggläser ist mit einer Glas-, Los- oder Abfüllnummer gekennzeichnet.
Beispielsweise enthalten alle Honiggläser vom Deutschen Imkerbund (DIB) eine aufsteigende Nummer mit einem vorangehenden Buchstabencode.
Weitere Informationen, wie z. B. die zugehörige Honiganalyse, können der unten stehenden Tabelle entnommen werden.
Einträge mit abgelaufenem Mindesthaltbarkeitsdatum werden automatisch nach 6 Monaten entfernt.

<script type="module">
  import { AnalysisTable } from "/js/main.js";

  let target = document.querySelector("#beetable #output");
  let table = await AnalysisTable.initialize(target);
  table.render(target);
</script>

<div id="beetable">
    <table id="output" class="sortable">
    </table>
</div>
