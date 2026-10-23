// The page of the database (layouts/db/overview.html) as HTML: the
// overview without ?q=, the record with its id in ?q= -- every page of a
// record built the same way, so that one who has read one can read them
// all: what kind of record it is, where it stands on the way of the honey
// and what it is connected to, its own particulars, and then the records
// next to it as tables. Styled by .db-* in bundle_src/css/db.css.

import { type Analysis, type Article, type Batch, type Bucket, type Centrifugation, type Db, type Filling, type Row, type Trace, KINDS, kindOf, trace } from "./data";

// --- HTML ---

// Markup that is safe to put into a page as it is.
class Html {
    constructor(readonly text: string) {}
}

// A template whose values are escaped -- except Html, e.g. what html``
// itself returned, and lists of it. null, undefined and false leave
// nothing.
function html(strings: TemplateStringsArray, ...values: unknown[]): Html {
    return new Html(strings.reduce((out, part, i) => out + part + (i < values.length ? fill(values[i]) : ""), ""));
}

function fill(value: unknown): string {
    if (value instanceof Html) return value.text;
    if (Array.isArray(value)) return value.map(fill).join("");
    if (value === null || value === undefined || value === false) return "";
    return String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

// The pieces joined by " · ".
function dotted(items: Html[]): Html {
    return new Html(items.map((i) => i.text).join(" · "));
}

// --- What the page hands over ---

export interface Page {
    // Prefix of the address a record keeps for good, e.g. on the label of
    // a jar: https://db.bienensteff.de/?q=
    permalink: string;
    // What marks a link as external (the theme's link-external-mark.html).
    externalMark: Html;
    // The picture of a record, if there is one, as a figure.
    image: (id: string, caption?: string) => Html | null;
}

export function pageFrom(app: HTMLElement): Page {
    const template = (selector: string) => document.querySelector<HTMLTemplateElement>(selector)?.innerHTML ?? "";
    return {
        permalink: app.dataset.permalink ?? "?q=",
        externalMark: new Html(template("template[data-db-external-mark]")),
        image: (id, caption) => {
            const figure = template(`template[data-db-image="${CSS.escape(id.toLowerCase())}"]`);
            if (!figure) return null;
            // The figure's caption is the record's id; another one is put in.
            return new Html(caption === undefined ? figure : figure.replace(/(<figcaption[^>]*>)[\s\S]*?(<\/figcaption>)/, `$1${fill(caption)}$2`));
        },
    };
}

// --- Pieces ---

const yesNo = (flag: boolean) => (flag ? "ja" : "nein");

function date(iso: string | null): Html {
    if (!iso) return html``;
    const [y, m, d] = iso.split("-");
    return html`<time datetime="${iso}">${d}.${m}.${y}</time>`;
}

const percent = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const water = (fraction: number) => `${percent.format(fraction * 100)} %`;

function link(id: string, text?: string | null): Html {
    return html`<a href="?q=${id.toLowerCase()}">${text || id}</a>`;
}

// A GTIN, linked to "Verified by GS1" -- except internal numbers from the
// restricted-circulation range (GTIN-13 beginning with 2), which GS1 has
// no record of.
function gtin(page: Page, value: string | null): Html {
    if (!value) return html``;
    if (value.length === 13 && value.startsWith("2")) {
        return html`<span title="Interne Nummer (nicht im GS1-Register)">${value}</span>`;
    }
    const url = `https://www.gs1.org/services/verified-by-gs1/results?gtin=${encodeURIComponent(value)}`;
    return html`<a href="${url}" target="_blank" rel="noopener noreferrer">${value}${page.externalMark}</a>`;
}

const row = (head: Html | string, value: Html | string | null | undefined) => html`<tr><th scope="row">${head}</th><td>${value}</td></tr>`;
const abbr = (text: string, title: string) => html`<abbr title="${title}">${text}</abbr>`;

const GQ_COMPLIANT = "Das Los erfüllt die Anforderungen von „Geprüfte Qualität – Bayern“. Ob ein Glas daraus das Siegel trägt, steht bei der Abfüllung.";
const MHD = abbr("MHD", "Mindesthaltbarkeitsdatum");
const DIB = abbr("DIB-Kontrollnummern", "Kontrollnummern der Gewährverschlüsse des Deutschen Imkerbunds");

// A table of records; a head given as [text, class] sets the class on
// its column head, e.g. text-end for numbers.
function table(head: (Html | [Html, string])[], rows: Html[]): Html {
    const th = (h: Html | [Html, string]) => (Array.isArray(h) ? html`<th scope="col" class="${h[1]}">${h[0]}</th>` : html`<th scope="col">${h}</th>`);
    return html`<div class="table-responsive"><table class="table db-table">
        <thead><tr>${head.map(th)}</tr></thead>
        <tbody>${rows}</tbody>
    </table></div>`;
}

// The way of the honey as a row of five steps, and at each step the
// records the given one is connected to; its own step is marked.
function chain(id: string, t: Trace): Html {
    const current = kindOf(id).kind;
    const steps: { prefix: string; what: string; rows: Row[] }[] = [
        { prefix: "S", what: "Honig wird geerntet", rows: t.centrifugations },
        { prefix: "E", what: "und in Eimern gelagert", rows: t.buckets },
        { prefix: "L", what: "Eimer bilden eine Charge", rows: t.batches },
        { prefix: "A", what: "die in Gläser abgefüllt wird", rows: t.fillings },
        { prefix: "SKU", what: "und als Produkt verkauft", rows: t.articles },
    ];
    return html`<nav class="db-chain" aria-label="Rückverfolgung"><ol>${steps.map(({ prefix, what, rows }) => {
        const here = KINDS[prefix].kind === current;
        const ids = rows.map((r) => {
            const text = "sku" in r ? r.sku : r.id;
            return r.id === id ? html`<strong>${text}</strong>` : link(r.id, text);
        });
        return html`<li class="db-chain-step${here ? " db-chain-step--current" : ""}"${here ? html` aria-current="step"` : ""}>
            <span class="db-chain-name">${KINDS[prefix].name}</span>
            <span class="db-chain-what">${what}</span>
            <span class="db-chain-ids">${ids.length ? ids : html`<span class="db-chain-none">noch keine</span>`}</span>
        </li>`;
    })}</ol></nav>`;
}

// The five kinds along the way of the honey, for the overview.
function legend(): Html {
    return html`<nav class="db-chain db-chain--legend" aria-label="Aufbau der Datenbank"><ol>${["S", "E", "L", "A", "SKU"].map(
        (prefix) => html`<li class="db-chain-step">
            <span class="db-chain-name">${KINDS[prefix].name}</span>
            <span class="db-chain-ids"><strong>${prefix}-…</strong></span>
            <span class="db-chain-what">${KINDS[prefix].what}</span>
        </li>`,
    )}</ol></nav>`;
}

function fillingTable(db: Db, fillings: Filling[], columns: { article?: boolean; batch?: boolean }): Html {
    const head: Html[] = [html`Abfüllung`];
    if (columns.article) head.push(html`Artikel`);
    if (columns.batch) head.push(html`Los`);
    head.push(html`Abgefüllt am`, MHD, abbr("GQ-Siegel", "Ob die Gläser das Siegel „Geprüfte Qualität – Bayern“ tragen: eine Eigenschaft des Artikels."), DIB);
    return table(
        head,
        fillings.map((f) => {
            const article = db.articles.find((a) => a.id === f.article_id);
            return html`<tr>
                <td>${link(f.id)}</td>
                ${columns.article ? html`<td>${f.article_id ? link(f.article_id, f.label) : ""}</td>` : ""}
                ${columns.batch ? html`<td>${f.batch_id ? link(f.batch_id) : ""}</td>` : ""}
                <td>${date(f.date)}</td>
                <td>${date(f.best_before_date)}</td>
                <td>${article ? yesNo(article.gqb_certified) : ""}</td>
                <td>${f.dib_field}</td>
            </tr>`;
        }),
    );
}

function bucketTable(db: Db, buckets: Bucket[], columns: { centrifugation?: boolean; batch?: boolean }): Html {
    const head: Html[] = [html`Eimer`];
    if (columns.centrifugation) head.push(html`Schleuderung`, html`Geschleudert am`);
    if (columns.batch) head.push(html`Los`);
    return table(
        head,
        buckets.map((e) => {
            const centrifugation = db.centrifugations.find((s) => s.id === e.centrifugation_id);
            return html`<tr>
                <td>${link(e.id)}</td>
                ${columns.centrifugation ? html`<td>${e.centrifugation_id ? link(e.centrifugation_id) : ""}</td><td>${date(centrifugation?.date ?? null)}</td>` : ""}
                ${columns.batch ? html`<td>${e.batch_id ? link(e.batch_id) : ""}</td>` : ""}
            </tr>`;
        }),
    );
}

// --- Particulars of a record ---

// The laboratory analyses of a batch and what else is to be said about it
// in public: the water content each found and the report it is from, so
// that it can be laid on the table when somebody asks. A sample taken
// before homogenising did not measure the honey as it is sold: its result
// is left out, its report named as such.
function lab(batch: Batch): Html[] {
    const rows = batch.analyses.flatMap((a: Analysis) => [
        a.water !== null ? row(abbr("Wassergehalt (Laboranalyse)", "Messung einer homogenisierten Probe im Labor"), water(a.water)) : null,
        a.report_number
            ? row(
                  "Laboranalyse",
                  html`${a.report_number}${a.issuer ? `, ${a.issuer}` : ""}${a.before_homogenisation ? ", Probe vor dem Homogenisieren" : ""}${a.file_name ? html` (Datei <code>${a.file_name}</code>)` : ""}`,
              )
            : null,
    ]);
    if (batch.analyses.length === 0) {
        rows.push(row("Wassergehalt", "Für dieses Los liegt keine Laboranalyse vor. Wir stellen mit eigenen Stichproben sicher, dass der Wassergehalt die Anforderungen erfüllt."));
    }
    if (batch.public_note) rows.push(row("Hinweis", batch.public_note));
    return rows.filter((r) => r !== null);
}

function articleRows(page: Page, a: Article): Html[] {
    const p = a.packaging;
    return [
        row(abbr("SKU", "Stock Keeping Unit"), a.sku),
        a.gtin ? row(abbr("GTIN", "Global Trade Item Number (vormals EAN)"), gtin(page, a.gtin)) : null,
        a.description || a.auto_description ? row("Beschreibung", a.description || a.auto_description) : null,
        a.brand.name ? row("Marke", a.brand.name) : null,
        a.brand.hint ? row("Produkthinweis", a.brand.hint) : null,
        a.brand.corporate_claim ? row("Marketingbotschaft", a.brand.corporate_claim) : null,
        p.label ? row("Gebinde", `${p.label}${(p.unit ?? 0) > 1 ? `, ${p.type} zu ${p.unit}` : ""}`) : null,
        row("Mit Siegel „Geprüfte Qualität – Bayern“", yesNo(a.gqb_certified)),
    ].filter((r) => r !== null);
}

function particulars(db: Db, page: Page, r: Row): Html[] {
    const batchOf = (id: string | null) => db.batches.find((b) => b.id === id);
    const withType = (b: Batch | undefined) => (b?.honey_type ? ` (${b.honey_type})` : "");
    switch (kindOf(r.id).kind) {
        case "article":
            return articleRows(page, r as Article);
        case "filling": {
            const f = r as Filling;
            const batch = batchOf(f.batch_id);
            const sku = f.article_id?.replace(/^SKU-/, "");
            return [
                row("Abfüllnummer", f.id),
                f.article_id ? row("Artikel", html`${link(f.article_id, f.label)} (${sku})`) : null,
                row("Abgefüllt am", date(f.date)),
                row(MHD, date(f.best_before_date)),
                f.batch_id ? row("Los", html`${link(f.batch_id)}${withType(batch)}`) : null,
                ...(batch ? lab(batch) : []),
                f.dib_field ? row(DIB, f.dib_field) : null,
            ].filter((x) => x !== null);
        }
        case "batch": {
            const b = r as Batch;
            return [row("Losnummer", b.id), row("Sortenempfehlung", b.honey_type), row(abbr("GQ-Bayern-konform", GQ_COMPLIANT), yesNo(b.gqb_compliant)), ...lab(b)];
        }
        case "bucket": {
            const e = r as Bucket;
            const centrifugation = db.centrifugations.find((s) => s.id === e.centrifugation_id);
            return [
                row("Eimernummer", e.id),
                e.centrifugation_id ? row("Schleuderung", html`${link(e.centrifugation_id)}${centrifugation ? html` vom ${date(centrifugation.date)}` : ""}`) : null,
                e.batch_id ? row("Los", html`${link(e.batch_id)}${withType(batchOf(e.batch_id))}`) : null,
            ].filter((x) => x !== null);
        }
        case "centrifugation": {
            const s = r as Centrifugation;
            return [row("Schleuderungsnummer", s.id), row("Geschleudert am", date(s.date))];
        }
    }
}

// What comes next to the record, as tables.
function neighbours(db: Db, page: Page, r: Row, t: Trace): Html[] {
    const section = (title: string, body: Html | null) => (body ? html`<h2>${title}</h2>${body}` : null);
    const fillings = (columns: { article?: boolean; batch?: boolean }) => (t.fillings.length ? fillingTable(db, t.fillings, columns) : null);
    const buckets = (columns: { centrifugation?: boolean; batch?: boolean }) => (t.buckets.length ? bucketTable(db, t.buckets, columns) : null);
    const batchId = "batch_id" in r ? r.batch_id : null;
    switch (kindOf(r.id).kind) {
        case "article":
            return [section("Abfüllungen im Verkauf", fillings({ batch: true }))].filter((x) => x !== null);
        case "filling":
            // What is in the jar first: who has a jar in hand wants to
            // know what it is before where it came from.
            return [
                ...t.articles.map(
                    (a) => html`<h2>Artikel</h2>
                        <table class="table">${row("Bezeichnung", link(a.id, a.label))}${articleRows(page, a)}</table>
                        ${page.image(a.id, a.label ?? undefined)}`,
                ),
                section(`Eimer des Loses ${batchId ?? ""}`, buckets({ centrifugation: true })),
            ].filter((x) => x !== null);
        case "batch":
            return [section("Eimer in diesem Los", buckets({ centrifugation: true })), section("Abfüllungen aus diesem Los", fillings({ article: true }))].filter((x) => x !== null);
        case "bucket":
            return [section(`Abfüllungen aus dem Los ${batchId ?? ""}`, fillings({ article: true }))].filter((x) => x !== null);
        case "centrifugation":
            return [section("Eimer dieser Schleuderung", buckets({ batch: true })), section("Abfüllungen aus den Losen dieser Schleuderung", fillings({ article: true, batch: true }))].filter((x) => x !== null);
    }
}

// --- Pages ---

// The title of a record: an article by its label, everything else by its id.
export function titleOf(r: Row): string {
    return ("label" in r && "sku" in r && r.label) || r.id;
}

export function record(db: Db, page: Page, r: Row): Html {
    const kind = kindOf(r.id);
    const t = trace(db, r);
    const permalink = `${page.permalink}${r.id.toLowerCase()}`;
    const image = page.image(r.id);
    return html`<header class="content-header">
            <p class="db-kind">${kind.name}</p>
            <h1>${titleOf(r)}</h1>
            <p class="db-what">${kind.what}</p>
        </header>
        <h2>Rückverfolgung</h2>
        ${chain(r.id, t)}
        <h2>Angaben</h2>
        <table class="table">${particulars(db, page, r)}${row("Permalink", html`<a href="${permalink}">${permalink}</a>`)}</table>
        ${neighbours(db, page, r, t)}
        ${image ? html`<hr>${image}` : ""}`;
}

export function notFound(id: string): Html {
    return html`<header class="content-header"><h1>Nicht gefunden</h1></header>
        <p>Einen Eintrag mit der Nummer <strong>${id}</strong> gibt es in der Datenbank nicht (mehr). Abfüllungen, deren Mindesthaltbarkeit abgelaufen ist, zeigen wir nicht mehr an.</p>
        <p><a href="?">Zur Übersicht der Datenbank</a></p>`;
}

// The overview: the reading aid and the three ways in -- an article on
// sale, a batch, a centrifugation, the newest first.
export function overview(db: Db, page: Page): Html {
    const onSale = db.articles.filter((a) => db.fillings.some((f) => f.article_id === a.id)).sort((a, b) => a.sku.localeCompare(b.sku));
    const newestFirst = <T extends { id: string }>(rows: T[]) => [...rows].sort((a, b) => b.id.localeCompare(a.id));
    return html`<h2>So ist die Datenbank zu lesen</h2>
        <p>Jedes Glas lässt sich über seine Abfüllnummer bis zu dem Tag zurückverfolgen, an dem der Honig geschleudert wurde – und umgekehrt jede Schleuderung bis zu den Gläsern, die daraus entstanden sind.
        Der Honig durchläuft dabei fünf Stationen, und jede hat eine eigene Nummer.
        Auf der Seite eines Eintrags steht oben immer dieselbe Kette, mit allem, was davor und danach kam.</p>
        ${legend()}
        <h2>Artikel im Verkauf</h2>
        ${table(
            [html`Artikelnummer`, html`GTIN`, html`Produktname`, html`Marke`],
            onSale.map(
                (a) => html`<tr><td>${link(a.id, a.sku)}</td><td>${gtin(page, a.gtin)}</td><td>${a.name} ${a.packaging.net_weight} ${a.packaging.filling_unit}</td><td>${a.brand.name}</td></tr>`,
            ),
        )}
        <h2>Honiglose</h2>
        ${table(
            [html`Los`, html`Sortenempfehlung`, abbr("GQ-konform", GQ_COMPLIANT), html`Schleuderung`, [abbr("Wasser", "Wassergehalt laut Laboranalyse einer homogenisierten Probe"), "text-end"], html`Abfüllungen`],
            newestFirst(db.batches).map((b) => {
                const t = trace(db, b);
                const measured = b.analyses.find((a) => a.water !== null);
                return html`<tr>
                    <td>${link(b.id)}</td>
                    <td>${b.honey_type}</td>
                    <td>${yesNo(b.gqb_compliant)}</td>
                    <td>${dotted(t.centrifugations.map((s) => link(s.id)))}</td>
                    <td class="text-end">${measured?.water != null ? water(measured.water) : ""}</td>
                    <td>${dotted(t.fillings.map((f) => link(f.id)))}</td>
                </tr>`;
            }),
        )}
        <h2>Schleuderungen</h2>
        ${table(
            [html`Schleuderung`, html`Geschleudert am`, html`Lose`],
            newestFirst(db.centrifugations).map(
                (s) => html`<tr><td>${link(s.id)}</td><td>${date(s.date)}</td><td>${dotted(trace(db, s).batches.map((b) => link(b.id)))}</td></tr>`,
            ),
        )}`;
}

export type { Html };
