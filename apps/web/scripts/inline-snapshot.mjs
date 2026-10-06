// Folds the snapshot build (dist-snapshot/snapshot.html + its one script and one
// stylesheet) into a single self-contained file: dist-snapshot/agent-one-finance-snapshot.html.
// A module script loaded by URL is blocked when a page is opened from disk
// (file://); inline, it runs anywhere, with no server and no network.
import fs from "fs";

const dir = new URL("../dist-snapshot/", import.meta.url);
const page = fs.existsSync(new URL("snapshot.html", dir)) ? "snapshot.html" : "index.html";
let html = fs.readFileSync(new URL(page, dir), "utf8");
const asset = (rel) => fs.readFileSync(new URL(rel.replace(/^\.\//, ""), dir), "utf8");

html = html.replace(/<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g, (_, href) => `<style>\n${asset(href)}\n</style>`);
html = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g,
  // "</script" inside the code would end the tag early.
  (_, src) => `<script type="module">\n${asset(src).replace(/<\/script/gi, "<\\/script")}\n</script>`);
if (/src="\.\/assets|href="\.\/assets/.test(html)) throw new Error("an asset was not inlined");

const out = new URL("agent-one-finance-snapshot.html", dir);
fs.writeFileSync(out, html);
console.log(`single-file snapshot: ${out.pathname} (${(html.length / 1024).toFixed(0)} KB)`);
