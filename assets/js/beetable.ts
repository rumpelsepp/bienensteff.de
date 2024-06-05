import { DateTime } from "luxon";
import { getParam } from "./main";

function formatDate(date: DateTime): string {
  return date.setLocale('de-DE').toLocaleString({
    weekday: 'short',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
}

async function fetchSheet(url: string) {
  const resp = await fetch(url);
  return resp.json();
}

class TableBase {
  target: HTMLTableElement;

  genHeader(): HTMLTableSectionElement | null{
    return null;
  }
  
  genBody(): HTMLTableSectionElement | null {
    return null;
  }
  
  render(target: HTMLTableElement) {
    let hdr = this.genHeader();
    if (hdr !== null) {
      target.appendChild(hdr);
    }
    let body = this.genBody();
    if (body !== null) {
      target.appendChild(body);
    }
  }
}

class BeetableBase extends TableBase {
  startDate: DateTime;

  constructor(date: DateTime | Date) {
    super();

    if (date instanceof Date) {
      this.startDate = DateTime.fromJSDate(date);
    } else {
      this.startDate = date;
    }
  }
}

class Beetable extends BeetableBase {
  schlupfDate: DateTime;
  eilageDate: DateTime;
  brutfreiDate: DateTime;
  verdeckeltDate: DateTime;
  jungbienenDate: DateTime;

  constructor(date: DateTime | Date) {
    super(date);
    
    this.schlupfDate = this.startDate.plus({days: 11});;
    this.eilageDate = this.schlupfDate.plus({days: 8});
    this.brutfreiDate = this.startDate.plus({days: 21});
    this.verdeckeltDate = this.eilageDate.plus({days: 9});
    this.jungbienenDate = this.eilageDate.plus({days: 21});
  }
  
  genBody(): HTMLTableSectionElement {
    let tbody = document.createElement("tbody");
    let tr = tbody.insertRow();
    let td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.startDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.schlupfDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.eilageDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.brutfreiDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.verdeckeltDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.jungbienenDate)));

    tbody.appendChild(tr);
    return tbody;
  }
}

class TUBTable extends BeetableBase {
  fBehandelnDate: DateTime;
  bBrutfreiDate: DateTime;
  bVerdeckeltDate: DateTime;

  constructor(target: HTMLTableElement, date: DateTime) {
    super(date);
    
    this.fBehandelnDate = date.plus({days: 2});
    this.bBrutfreiDate = date.plus({days: 21});
    this.bVerdeckeltDate = date.plus({days: 24});
  }

  genBody(): HTMLTableSectionElement {
    let tbody = document.createElement("tbody");
    let tr = tbody.insertRow();
    let td = tr.insertCell();
    
    td.appendChild(document.createTextNode(formatDate(this.startDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.fBehandelnDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.bBrutfreiDate)));
    td = tr.insertCell();
    td.appendChild(document.createTextNode(formatDate(this.bVerdeckeltDate)));

    tbody.appendChild(tr);
    return tbody;
  }
}

class DataTable extends TableBase {
  data: string[][];
  header: string[];
  highlight: string;

  constructor(header: string[], data: string[][]) {
    super();

    this.data = data;
    this.header = header;
    this.highlight = getParam("h");
  }

  genHeader(): HTMLTableSectionElement {
    let thead = document.createElement("thead");
    let tr = thead.insertRow();
    
    for (const col of this.header) {
      let th = document.createElement("th");
      th.innerHTML = col;
      tr.appendChild(th);
      
      thead.appendChild(tr);
    }
  
    return thead;
  }

  genBody(): HTMLTableSectionElement {
    let tbody = document.createElement("tbody");

    for (const row of this.data) {
      let tr = tbody.insertRow();

      for (const col of row) {
        if (this.highlight == col && !tr.classList.contains("highlight")) {
          tr.classList.add("highlight");
        }

        let td = tr.insertCell();
        td.innerHTML = col;
      }

      tbody.appendChild(tr);
    }
    
    return tbody;
  }
}

class AnalysisTable extends DataTable {
  static async initialize(): AnalysisTable {
    const data = await fetchSheet("database.json");

    const header = [
      "Abfüllung",
      "Los",
      "Schleuderdatum",
      "Abfülldatum",
      `<abbr title="Mindesthaltbarkeitsdatum">MHD</abbr>`,
      "Glastyp",
      "Glasnummer",
      `<abbr title="Sortenempfehlung stammt aus der Laboranalyse">Sortenempfehlung</abbr>`,
      "Laboranalyse",
    ];

    const nv = `<abbr title="nicht vorhanden">—</abbr>`;
    let rows = [];

    for (const rawRow of data.slice()) {
      let aID = rawRow["Nummer"];
      let cID = rawRow["Los"];
      let schleuderDate = rawRow["Schleuderdatum"];
      let abfuellDate = rawRow["Abfülldatum"];
      let mhd = rawRow["MHD"];
      let sort = rawRow["Sorte"];
      let glassType = rawRow["Glastyp"];
      let glassPrefix = rawRow["KN Präfix"];
      let glassStart = rawRow["KN Start"];
      let glassEnd = rawRow["KN End"];
      
      let mhdDiff = DateTime.fromFormat(mhd, "dd.MM.yyyy").toLocal().diff(DateTime.now()).as("months");
      if (mhdDiff < -6) {
        continue
      }

      let analysisFile = rawRow["Analyse"];
      let analysisLink = nv;
      if (analysisFile != "") {
        let url = new URL(`/analysen/${analysisFile}`, `${window.location.protocol}//${window.location.host}`);
        analysisLink = `<a href="${url}">${analysisFile}</a>`;
      }
      
      let glassIDs = nv;
      if (glassStart != "" || glassEnd != "") {
        glassIDs = `<strong>${glassPrefix}</strong>${glassStart}…${glassEnd}`;
      }

      let row = [aID, cID, schleuderDate, abfuellDate, mhd, glassType, glassIDs, sort, analysisLink];
      rows.push(row);
    }

    return new AnalysisTable(header, rows);
  }
}
  
export { AnalysisTable, DataTable, Beetable, TUBTable };
