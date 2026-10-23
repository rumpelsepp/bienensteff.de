// The page of the traceability database (layouts/db/overview.html): loads
// the database, cuts it down to what is public today and shows the record
// whose id is in ?q=, or the overview. The links between records are plain
// links to ?q=…, so back and forward work as on any page.

import { type Db, find, publicOn, today } from "./data";
import { notFound, overview, pageFrom, record, titleOf } from "./view";

export async function initDb(app: HTMLElement, responsePromise: Promise<Response>): Promise<void> {
    // What went wrong on the way is said on the page, not only in the
    // console: an empty page tells the visitor nothing.
    let db: Db;
    try {
        const response = await responsePromise;
        if (!response.ok) throw new Error(`database: ${response.status} ${response.statusText}`);
        db = publicOn((await response.json()) as Db, today());
    } catch (cause) {
        console.error("Failed to load the database:", cause);
        app.innerHTML = '<p class="db-status">Die Datenbank konnte nicht geladen werden – bitte die Seite neu laden.</p>';
        return;
    }

    const page = pageFrom(app);

    const id = new URLSearchParams(location.search).get("q")?.trim();
    if (!id) {
        app.innerHTML = overview(db, page).text;
        return;
    }

    // A record takes the whole page, its own heading in place of the
    // overview's.
    const article = app.closest("article") ?? app;
    const row = find(db, id);
    article.innerHTML = (row ? record(db, page, row) : notFound(id)).text;
    document.title = `${row ? titleOf(row) : "Nicht gefunden"} | ${app.dataset.site ?? ""}`;
}
