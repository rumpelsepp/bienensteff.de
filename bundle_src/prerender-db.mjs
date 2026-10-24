// The overview of the traceability database, made at build time with the
// same code the browser runs (bundle_src/js/db/view.ts), so that the page
// arrives with it instead of growing it after the first paint. npm runs it
// after `npm run build` (postbuild in package.json), from the root of the
// site: after the theme's build, which empties assets/gen/ first.
//
// Writes assets/gen/db/overview.json: {renderedOn, source, html}, source
// the SHA-256 of the db.json it was made from: Hugo leaves the overview
// out once db.json is another (a new dump while `just serve` runs). layouts/db/
// overview.html puts the html into #db-app, and the browser keeps it as
// long as the database is the same on the reader's day as on renderedOn
// (bundle_src/js/db/index.ts). The mark of an external link is the
// theme's, which only Hugo has: it stands in the html as EXTERNAL_MARK.

import crypto from "crypto";
import fs from "fs";
import path from "path";
import * as esbuild from "esbuild";

const EXTERNAL_MARK = "<!--db-external-mark-->";
const out = "assets/gen/db/overview.json";

const { outputFiles } = await esbuild.build({
    stdin: {
        contents: `export { overview, Html } from "./view"; export { publicOn, today } from "./data";`,
        resolveDir: path.resolve("bundle_src/js/db"),
        loader: "ts",
    },
    bundle: true,
    platform: "node",
    format: "esm",
    write: false,
});
const { overview, Html, publicOn, today } = await import(`data:text/javascript;base64,${Buffer.from(outputFiles[0].text).toString("base64")}`);

const renderedOn = today();
const raw = fs.readFileSync("assets/db/db.json", "utf8");
const source = crypto.createHash("sha256").update(raw).digest("hex");
const db = publicOn(JSON.parse(raw), renderedOn);
const page = { permalink: "", externalMark: new Html(EXTERNAL_MARK), image: () => null };

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify({ renderedOn, source, html: overview(db, page).text }));
console.log(`Prerendered the database overview for ${renderedOn}: ${out}`);
