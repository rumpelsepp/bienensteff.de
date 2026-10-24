// The page of the traceability database (layouts/db/overview.html): loads
// the database, cuts it down to what is public today and shows the record
// whose id is in ?q=, or the overview. The links between records are plain
// links to ?q=…, so back and forward work as on any page.
//
// The overview arrives with the page, made at build time for the day in
// data-rendered-on (bundle_src/prerender-db.mjs); it is made anew only if
// the database is not the same on the reader's day. A record is known only
// here: until it is shown, the page says it is on its way (.db-view-record,
// set in layouts/_partials/head/extra.html).

import { type Db, find, publicOn, today } from "./data";
import { notFound, overview, pageFrom, record, titleOf } from "./view";

const FAILED = '<p class="db-status">Die Datenbank konnte nicht geladen werden – bitte die Seite neu laden.</p>';

export async function initDb(app: HTMLElement, responsePromise: Promise<Response>): Promise<void> {
    const id = new URLSearchParams(location.search).get("q")?.trim();
    const renderedOn = app.dataset.renderedOn;

    // What went wrong on the way is said on the page, not only in the
    // console: an empty page tells the visitor nothing. An overview that
    // came with the page stays.
    let all: Db;
    try {
        const response = await responsePromise;
        if (!response.ok) throw new Error(`database: ${response.status} ${response.statusText}`);
        all = (await response.json()) as Db;
    } catch (cause) {
        console.error("Failed to load the database:", cause);
        if (id) showRecord(app, FAILED);
        else if (!renderedOn) app.innerHTML = FAILED;
        return;
    }
    const db = publicOn(all, today());
    const page = pageFrom(app);

    if (!id) {
        if (renderedOn && JSON.stringify(publicOn(all, renderedOn)) === JSON.stringify(db)) return;
        app.innerHTML = overview(db, page).text;
        return;
    }

    const row = find(db, id);
    showRecord(app, (row ? record(db, page, row) : notFound(id)).text);
    document.title = `${row ? titleOf(row) : "Nicht gefunden"} | ${app.dataset.site ?? ""}`;
}

// A record takes the whole page, its own heading in place of the
// overview's.
function showRecord(app: HTMLElement, text: string): void {
    const article = app.closest("article") ?? app;
    article.innerHTML = text;
    document.documentElement.classList.remove("db-view-record");
}
