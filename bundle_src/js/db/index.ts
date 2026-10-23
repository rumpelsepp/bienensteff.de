// The page of the traceability database (layouts/db/overview.html): loads
// the database, cuts it down to what is public today and shows the record
// whose id is in ?q=, or the overview. The links between records are plain
// links to ?q=…, so back and forward work as on any page.

import { type Db, find, publicOn, today } from "./data";
import { notFound, overview, pageFrom, record, titleOf } from "./view";

export async function initDb(app: HTMLElement): Promise<void> {
    const response = await fetch(app.dataset.src ?? "");
    if (!response.ok) throw new Error(`database: ${response.status} ${response.statusText}`);
    const db = publicOn((await response.json()) as Db, today());
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
