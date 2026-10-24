// The traceability database as bscli's src/bstools/cli/dump_db.py writes
// it (assets/db/db.json): five flat tables, a record pointing to another by
// that one's id. Here it is read, cut down to what is public today and
// followed along the way of the honey:
//
//   Schleuderung (S) -> Eimer (E) -> Los (L) -> Abfüllung (A) -> Artikel (SKU)

export interface Article {
    id: string;
    sku: string;
    gtin: string | null;
    label: string | null;
    name: string | null;
    description: string | null;
    auto_description: string | null;
    gqb_certified: boolean;
    brand: { name: string | null; hint: string | null; corporate_claim: string | null };
    packaging: {
        label: string | null;
        net_weight: number | string | null;
        filling_unit: string | null;
        type: string | null;
        unit: number | null;
    };
}

export interface Filling {
    id: string;
    article_id: string | null;
    label: string | null;
    batch_id: string | null;
    date: string | null;
    best_before_date: string | null;
    dib_field: string | null;
}

export interface Bucket {
    id: string;
    batch_id: string | null;
    centrifugation_id: string | null;
}

export interface Analysis {
    water: number | null;
    report_number: string | null;
    issuer: string | null;
    file_name: string | null;
    before_homogenisation: boolean;
}

export interface Batch {
    id: string;
    honey_type: string | null;
    gqb_compliant: boolean;
    public_note: string | null;
    analyses: Analysis[];
}

export interface Centrifugation {
    id: string;
    date: string | null;
}

export interface Db {
    articles: Article[];
    fillings: Filling[];
    buckets: Bucket[];
    batches: Batch[];
    centrifugations: Centrifugation[];
}

export type Row = Article | Filling | Bucket | Batch | Centrifugation;
export type KindName = "article" | "filling" | "batch" | "bucket" | "centrifugation";

// What a record is, by the letters its id begins with.
export const KINDS: Record<string, { kind: KindName; name: string; what: string }> = {
    S: { kind: "centrifugation", name: "Schleuderung", what: "Eine Schleuderung ist ein Erntetag: Der Honig wird aus den Waben geschleudert und in Eimer gefüllt." },
    E: { kind: "bucket", name: "Eimer", what: "Ein Eimer ist ein Lagergebinde, in das der Honig bei einer Schleuderung gefüllt wurde." },
    L: { kind: "batch", name: "Los", what: "Ein Los ist eine Charge Honig: die Eimer, die zusammen als eine Sorte abgefüllt werden." },
    A: { kind: "filling", name: "Abfüllung", what: "Eine Abfüllung sind die Gläser eines Artikels, die an einem Tag aus einem Los abgefüllt wurden. Ihre Nummer steht auf dem Etikett." },
    SKU: { kind: "article", name: "Artikel", what: "Ein Artikel ist ein Produkt, wie es im Verkauf steht: eine Honigsorte in einem bestimmten Glas mit einem bestimmten Etikett." },
};

export function kindOf(id: string) {
    return KINDS[id.split("-")[0].toUpperCase()];
}

// The database as far as it is public on the day given (YYYY-MM-DD): what
// there may still be a jar of on somebody's shelf. A filling past its
// best-before date is left out, and with it what led to nothing but such
// fillings -- a batch all of whose fillings have expired, the buckets of
// such a batch (or of none) and a centrifugation none of whose buckets is
// left. A batch that has not been filled yet stays; articles all stay.
// dump_db.py's drop_expired() applies the same rule when it writes the
// file, so this only catches what has expired since.
export function publicOn(db: Db, today: string): Db {
    const fillings = db.fillings.filter((f) => (f.best_before_date ?? "") >= today);
    const filled = new Set(db.fillings.map((f) => f.batch_id));
    const current = new Set(fillings.map((f) => f.batch_id));
    const batches = db.batches.filter((b) => current.has(b.id) || !filled.has(b.id));
    const batchIds = new Set(batches.map((b) => b.id));
    const buckets = db.buckets.filter((e) => e.batch_id !== null && batchIds.has(e.batch_id));
    const centrifugationIds = new Set(buckets.map((e) => e.centrifugation_id));
    const centrifugations = db.centrifugations.filter((s) => centrifugationIds.has(s.id));
    return { articles: db.articles, fillings, buckets, batches, centrifugations };
}

// Today in the reader's time zone, as YYYY-MM-DD.
export function today(): string {
    const now = new Date();
    return [now.getFullYear(), now.getMonth() + 1, now.getDate()].map((n) => String(n).padStart(2, "0")).join("-");
}

// The record with the id, case not minding, from whichever table.
export function find(db: Db, id: string): Row | undefined {
    const wanted = id.toUpperCase();
    return Object.values(db)
        .flat()
        .find((row: Row) => row.id.toUpperCase() === wanted);
}

export interface Trace {
    centrifugations: Centrifugation[];
    buckets: Bucket[];
    batches: Batch[];
    fillings: Filling[];
    articles: Article[];
}

const byId = <T extends { id: string }>(a: T, b: T) => a.id.localeCompare(b.id);

// Everything a record is connected to, from the harvest to the product on
// the shelf, in both directions. A bucket belongs to one centrifugation
// and one batch, a filling to one batch and one article; the batches are
// the hinge: whatever the record, its batches are found first, and from
// them the rest.
export function trace(db: Db, row: Row): Trace {
    const kind = kindOf(row.id).kind;
    let batchIds: (string | null)[] = [];
    let fillings: Filling[] = [];
    let buckets: Bucket[] = [];
    let centrifugations: Centrifugation[] = [];

    if (kind === "filling") {
        fillings = [row as Filling];
        batchIds = [(row as Filling).batch_id];
    } else if (kind === "batch") {
        batchIds = [row.id];
    } else if (kind === "bucket") {
        buckets = [row as Bucket];
        batchIds = [(row as Bucket).batch_id];
    } else if (kind === "centrifugation") {
        centrifugations = [row as Centrifugation];
        buckets = db.buckets.filter((e) => e.centrifugation_id === row.id);
        batchIds = buckets.map((e) => e.batch_id);
    } else {
        fillings = db.fillings.filter((f) => f.article_id === row.id);
        batchIds = fillings.map((f) => f.batch_id);
    }

    const batchSet = new Set(batchIds.filter((id) => id !== null));
    const batches = db.batches.filter((b) => batchSet.has(b.id));
    if (fillings.length === 0) fillings = db.fillings.filter((f) => f.batch_id !== null && batchSet.has(f.batch_id));
    if (buckets.length === 0) buckets = db.buckets.filter((e) => e.batch_id !== null && batchSet.has(e.batch_id));
    if (centrifugations.length === 0) {
        const ids = new Set(buckets.map((e) => e.centrifugation_id));
        centrifugations = db.centrifugations.filter((s) => ids.has(s.id));
    }
    const articleIds = new Set(fillings.map((f) => f.article_id));
    const articles = kind === "article" ? [row as Article] : db.articles.filter((a) => articleIds.has(a.id));

    return {
        centrifugations: centrifugations.sort(byId),
        buckets: buckets.sort(byId),
        batches: batches.sort(byId),
        fillings: fillings.sort(byId),
        articles: articles.sort(byId),
    };
}
