// Checks the console still uses this project's styles: the Barclays tokens, Tailwind 3,
// the hx-* graphics, the fonts and the theme switch. Run it after any merge or conversion.
//
//   node scripts/check-styles.mjs           check (exit 1 on a failure)
//   node scripts/check-styles.mjs --write   upstream only: record the style files' fingerprints
//
// What it checks:
//   1. the style files are byte-for-byte upstream's (theme/style-manifest.json);
//   2. no hard-coded colours in src (hex, rgb(), hsl(), Tailwind `bg-[#…]`): use the tokens, and only the
//      palette's five families (surface, primary/accent/brand, orange, red, green);
//   3. no other stylesheet in src, and no other UI or CSS library in package.json;
//   4. Tailwind is still major version 3;
//   5. every hx-* class the pages use is defined in src/index.css;
//   6. inline styles only set CSS variables or sizes (a warning, not a failure).

import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const web = fileURLToPath(new URL("..", import.meta.url));
const MANIFEST = join(web, "theme", "style-manifest.json");
const STYLE_FILES = [
  "tailwind.config.js",
  "postcss.config.js",
  "theme/barclays.js",
  "src/index.css",
  "src/theme.ts",
  "index.html",
  "public/pitch/index.html",
];
const OTHER_UI = /^(bootstrap|react-bootstrap|@mui\/|@material-ui\/|antd$|@chakra-ui\/|styled-components$|@emotion\/|bulma$|semantic-ui|@mantine\/|primereact$|@fluentui\/|sass$|less$)/;
const COLOUR = /(#[0-9a-fA-F]{3,8}\b|\brgba?\((?!\s*var\()|\bhsla?\((?!\s*var\())/;
const ARBITRARY = /\b[a-z-]+-\[(#|rgb|hsl)[^\]]*\]/;
// The palette is five meanings: neutral (surface), your turn / brand (primary, accent, brand),
// needs a person's judgement (orange), problem (red), done (green). Other colour families
// carry no meaning here and have no dark-mode version in the Barclays theme.
const OFF_PALETTE = /\b(?:text|bg|border|border-[lrtbxy]|ring|from|via|to|fill|stroke|divide|outline|decoration|caret|placeholder)-(slate|gray|zinc|neutral|stone|amber|yellow|lime|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/;
const OK_INLINE = /^(--hx-[a-z-]+|\["--hx-[a-z-]+" as string\]|width|height|fontSize)$/;

const sha = (f) => createHash("sha256").update(readFileSync(join(web, f))).digest("hex");
const walk = (d) => readdirSync(d).flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? (n === "node_modules" || n === "__tests__" ? [] : walk(p)) : [p];
});

if (process.argv.includes("--write")) {
  const files = Object.fromEntries(STYLE_FILES.map((f) => [f, sha(f)]));
  writeFileSync(MANIFEST, JSON.stringify({
    about: "Fingerprints of the console's style files, written upstream by scripts/check-styles.mjs --write. Do not edit by hand.",
    files,
  }, null, 2) + "\n");
  console.log(`wrote ${relative(web, MANIFEST)} (${STYLE_FILES.length} files)`);
  process.exit(0);
}

const fail = [];
const warn = [];

// 1. the style files are upstream's
if (!existsSync(MANIFEST)) fail.push("theme/style-manifest.json is missing: copy it from upstream");
else {
  const { files } = JSON.parse(readFileSync(MANIFEST, "utf8"));
  for (const [f, h] of Object.entries(files)) {
    if (!existsSync(join(web, f))) fail.push(`${f}: missing (upstream has it)`);
    else if (sha(f) !== h) fail.push(`${f}: differs from upstream (take upstream's file; office changes to styles go upstream first)`);
  }
}

// 2. colours come from the tokens; 6. inline styles
const src = walk(join(web, "src")).filter((p) => /\.(tsx?|jsx?)$/.test(p) && !p.includes(`${join("src", "snapshot")}`));
for (const p of src) {
  const rel = relative(web, p);
  readFileSync(p, "utf8").split("\n").forEach((line, i) => {
    const code = line.replace(/\/\/.*$/, "");
    if (COLOUR.test(code)) fail.push(`${rel}:${i + 1}: hard-coded colour; use a token class (bg-primary-600, text-surface-700, …) or rgb(var(--c-…)): ${line.trim().slice(0, 100)}`);
    const off = code.match(OFF_PALETTE);
    if (off) fail.push(`${rel}:${i + 1}: \`${off[0]}\` is outside the palette; use surface, primary/accent, orange (needs a person), red (problem) or green (done)`);
    if (ARBITRARY.test(code)) fail.push(`${rel}:${i + 1}: arbitrary Tailwind colour; use a token: ${line.trim().slice(0, 100)}`);
    const m = code.match(/style=\{\{([^}]*)\}\}/);
    if (m) {
      const keys = m[1].split(",").map((s) => s.split(":")[0].trim()).filter(Boolean);
      const odd = keys.filter((k) => !OK_INLINE.test(k));
      if (odd.length) warn.push(`${rel}:${i + 1}: inline style ${odd.join(", ")}; prefer a class`);
    }
  });
}

// 3. one stylesheet, no other UI library
const sheets = walk(join(web, "src")).filter((p) => /\.(css|scss|sass|less)$/.test(p)).map((p) => relative(web, p));
for (const s of sheets) if (s !== join("src", "index.css")) fail.push(`${s}: another stylesheet; put styles in src/index.css (@layer components) using the tokens`);
const pkg = JSON.parse(readFileSync(join(web, "package.json"), "utf8"));
const deps = { ...pkg.dependencies, ...pkg.devDependencies };
for (const d of Object.keys(deps)) if (OTHER_UI.test(d)) fail.push(`package.json: ${d} is another UI or CSS library; the console uses Tailwind with the Barclays tokens only`);

// 4. Tailwind 3
if (!/^\D*3\./.test(deps.tailwindcss ?? "")) fail.push(`package.json: tailwindcss ${deps.tailwindcss ?? "missing"}; the console is built for Tailwind 3`);

// 5. hx-* classes are defined
const css = readFileSync(join(web, "src", "index.css"), "utf8");
const defined = new Set([...css.matchAll(/\.(hx-[a-z-]+)/g)].map((m) => m[1]));
const vars = new Set([...css.matchAll(/(--hx-[a-z-]+)/g)].map((m) => m[1].slice(2)));
for (const p of src) {
  const text = readFileSync(p, "utf8");
  for (const m of text.matchAll(/className=[^>]*?\b(hx-[a-z-]+)/g)) {
    if (!defined.has(m[1]) && !vars.has(m[1])) fail.push(`${relative(web, p)}: class ${m[1]} is not defined in src/index.css`);
  }
}

for (const w of warn) console.log(`warn  ${w}`);
for (const f of fail) console.log(`FAIL  ${f}`);
console.log(fail.length ? `\n${fail.length} style problem(s).` : `styles ok: upstream style files, tokens only, Tailwind ${deps.tailwindcss}, ${defined.size} hx-* classes`);
process.exit(fail.length ? 1 : 0);
