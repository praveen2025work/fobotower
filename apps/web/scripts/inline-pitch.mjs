// Folds the pitch page (public/pitch/index.html) and its screenshots into one
// HTML file that opens straight from disk or an email attachment:
//   node scripts/inline-pitch.mjs  →  docs/helix/pitch/helix-pitch.html
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(web, "public", "pitch");
const out = join(web, "..", "..", "docs", "helix", "pitch", "helix-pitch.html");

const html = readFileSync(join(src, "index.html"), "utf8")
  .replace(/src="img\/([^"]+\.png)"/g, (_, name) =>
    `src="data:image/png;base64,${readFileSync(join(src, "img", name)).toString("base64")}"`);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, html);
console.log(`wrote ${out} (${Math.round(html.length / 1024)} KB)`);
