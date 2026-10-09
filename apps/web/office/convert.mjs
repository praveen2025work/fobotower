// Builds the office form of the console: the files the office's Agent One frontend
// (Next.js App Router, JSX, its own Tailwind) takes as they are, under /finance.
//
//   node office/convert.mjs [--out ../../office/aos-frontend] [--check]
//
// What it does, the same way every time:
//   - every console source file: types removed (TSX -> JSX), formatted, and the few
//     Vite and react-router specifics swapped for Next.js ones (see REWRITES);
//   - one Next.js page per console route (src/app/finance/...), read from App.tsx;
//   - the console's styles compiled once here and scoped to #aof-root, so they
//     neither depend on nor change the office's own Tailwind set-up;
//   - aof-frontend.json: every file with its hash, the packages and icons it needs.
// --check fails if the committed output is not what this script makes now.

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import autoprefixer from "autoprefixer";
import postcss from "postcss";
import prettier from "prettier";
import tailwindcss from "tailwindcss";
import loadConfig from "tailwindcss/loadConfig.js";
import { blankSourceFile } from "ts-blank-space";
import ts from "typescript";

const WEB = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(WEB, "src");
const ROOT_ID = "aof-root";
const COMPONENTS = "src/components/financeagent"; // where the console lives in the office repo
const APP = "src/app/finance"; // its Next.js routes

const args = process.argv.slice(2);
const OUT = path.resolve(args.includes("--out") ? args[args.indexOf("--out") + 1] : path.join(WEB, "../../office/aos-frontend"));
const CHECK = args.includes("--check");

// Upstream-only files: the Vite entry and routes (replaced by Next.js pages and
// office/FinanceShell), tests, and the offline snapshot build.
const SKIP = [/^main\.tsx$/, /^App\.tsx$/, /\.d\.ts$/, /(^|\/)__tests__\//, /^test\//, /^snapshot\//];

/** [file pattern, from, to, times expected (0 = any)]. Each must match as often as expected, so an upstream change is noticed. */
const REWRITES = [
  [/./, /from "react-router-dom"/g, (rel) => `from "${rel("office/router")}"`, 0],
  [/^api\/client\.ts$/, /import\.meta\.env\.VITE_AOF_API/g, () => "process.env.NEXT_PUBLIC_AOF_API", 1],
  [/^pages\/CaseWorkspace\.tsx$/, /import\.meta\.env\.VITE_AOF_TRACE_URL/g, () => "process.env.NEXT_PUBLIC_AOF_TRACE_URL", 1],
  [/^components\/ui\.tsx$/, /import\.meta\.env\.MODE === "test"/g, () => 'process.env.NODE_ENV === "test"', 1],
  // The theme belongs to the console, not to Agent One's page.
  [/^theme\.ts$/, /document\.documentElement\.dataset\.theme = theme;/g,
    () => `const root = document.getElementById("${ROOT_ID}");\n  if (root) root.dataset.theme = theme;`, 1],
];

const sha = (text) => createHash("sha256").update(text).digest("hex").slice(0, 16);
const posix = (p) => p.split(path.sep).join("/");

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((d) => {
    const p = path.join(dir, d.name);
    return d.isDirectory() ? walk(p) : [p];
  });
}

async function format(code, file) {
  return prettier.format(code, { parser: "babel", filepath: file, printWidth: 120 });
}

/** TS/TSX source -> JS/JSX: types blanked out (code and comments stay where they were), then formatted. */
async function toJs(source, file) {
  const kind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.ESNext, true, kind);
  const js = blankSourceFile(sf, (node) => {
    throw new Error(`${file}: cannot strip "${node.getText().slice(0, 60)}" (enums and namespaces are not allowed in the console)`);
  });
  return format(js, file.replace(/\.tsx?$/, ".jsx"));
}

const header = (from) =>
  `// Generated from apps/web/${from} by apps/web/office/convert.mjs. Office changes to this file are\n` +
  `// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.\n`;

/** Routes from App.tsx: [{ path, component, module }]. */
function routes() {
  const app = fs.readFileSync(path.join(SRC, "App.tsx"), "utf8");
  const modules = {};
  for (const m of app.matchAll(/const (\w+) = lazy\(\(\) => import\("\.\/(pages\/\w+)"\)\);/g)) modules[m[1]] = m[2];
  for (const m of app.matchAll(/import (\w+) from "\.\/(pages\/\w+)";/g)) modules[m[1]] = m[2];
  const out = [];
  for (const m of app.matchAll(/<Route path="([^"]+)" element=\{(?:page\()?<(\w+) \/>\)?\} \/>/g)) {
    if (!modules[m[2]]) throw new Error(`App.tsx: route ${m[1]} renders ${m[2]}, which is not a page import`);
    out.push({ path: m[1], component: m[2], module: modules[m[2]] });
  }
  if (out.length < 10) throw new Error(`App.tsx: found ${out.length} routes, expected at least 10; update routes() in convert.mjs`);
  return out;
}

async function css(files) {
  const config = loadConfig(path.join(WEB, "tailwind.config.js"));
  const scoped = {
    ...config,
    content: files,
    important: `#${ROOT_ID}`,
  };
  const scope = {
    postcssPlugin: "aof-scope",
    Rule(rule) {
      if (rule.parent?.type === "atrule" && /keyframes$/.test(rule.parent.name)) return;
      if (rule.__scoped) return;
      rule.__scoped = true;
      rule.selectors = rule.selectors.flatMap((s) => {
        if (s.startsWith(`#${ROOT_ID}`)) return [s];
        if (/^(:root|html|body|:host)(?=$|[\s,[:])/.test(s)) return [s.replace(/^(:root|html|body|:host)/, `#${ROOT_ID}`)];
        if (s === "*" ) return [`#${ROOT_ID}`, `#${ROOT_ID} *`];
        return [`#${ROOT_ID} ${s}`];
      });
    },
  };
  const source = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
  const result = await postcss([tailwindcss(scoped), autoprefixer, scope]).process(source, { from: path.join(SRC, "index.css") });
  return (
    `/* Generated from apps/web/src/index.css and the console's Tailwind classes by apps/web/office/convert.mjs.\n` +
    `   Every rule is scoped to #${ROOT_ID}, so it neither needs nor changes Agent One's own Tailwind set-up.\n` +
    `   Do not edit: regenerate upstream. */\n` +
    result.css +
    `\n/* The console fills the space Agent One gives it. Set --aof-height on #${ROOT_ID} (for example\n` +
    `   calc(100vh - 64px) under a 64px header); full height by default. */\n` +
    `#${ROOT_ID} { height: var(--aof-height, 100vh); }\n` +
    `#${ROOT_ID} .h-screen { height: var(--aof-height, 100vh); }\n` +
    `#${ROOT_ID} .min-h-screen { min-height: var(--aof-height, 100vh); }\n`
  );
}

async function build() {
  const files = {}; // office path -> { text, from }
  const sources = walk(SRC)
    .map((p) => posix(path.relative(SRC, p)))
    .filter((rel) => /\.(tsx?|css)$/.test(rel) && !SKIP.some((re) => re.test(rel)) && rel !== "index.css")
    .sort();
  const icons = new Set();
  for (const rel of sources) {
    let text = fs.readFileSync(path.join(SRC, rel), "utf8");
    const depth = rel.split("/").length - 1;
    const relTo = (target) => (depth ? "../".repeat(depth) : "./") + target;
    for (const [where, from, to, times] of REWRITES) {
      if (!where.test(rel)) continue;
      const n = (text.match(from) ?? []).length;
      if (times && n !== times) throw new Error(`${rel}: expected ${times} × ${from}, found ${n}; update REWRITES in convert.mjs`);
      text = text.replace(from, to(relTo));
    }
    if (/import\.meta/.test(text)) throw new Error(`${rel}: import.meta is Vite-only; add a rewrite in convert.mjs`);
    for (const m of text.matchAll(/import \{([^}]+)\} from "lucide-react"/g))
      for (const name of m[1].split(",")) {
        const n = name.replace(/\btype\b/, "").trim();
        if (n && n !== "LucideIcon" && n !== "LucideProps") icons.add(n.split(/\s+as\s+/)[0]);
      }
    const out = rel.replace(/\.tsx$/, ".jsx").replace(/\.ts$/, ".js");
    files[`${COMPONENTS}/${out}`] = { text: header(`src/${rel}`) + (await toJs(text, rel)), from: `apps/web/src/${rel}` };
  }

  for (const name of ["router.js", "FinanceShell.jsx"]) {
    const text = fs.readFileSync(path.join(WEB, "office/templates", name), "utf8");
    files[`${COMPONENTS}/office/${name}`] = { text: await format(text, name), from: `apps/web/office/templates/${name}` };
  }

  const contentFiles = walk(SRC).filter((p) => /\.(tsx?)$/.test(p) && !/__tests__|\/test\/|\/snapshot\//.test(p));
  contentFiles.push(path.join(WEB, "office/templates/FinanceShell.jsx"));
  files[`${COMPONENTS}/finance.css`] = { text: await css(contentFiles), from: "apps/web/src/index.css" };

  const fromApp = (dir) => posix(path.relative(dir, COMPONENTS));
  files[`${APP}/layout.jsx`] = {
    from: "apps/web/office/convert.mjs",
    text: await format(
      `"use client";\n${header("src/main.tsx")}\n` +
        `import dynamic from "next/dynamic";\n\nimport "${fromApp(APP)}/finance.css";\n\n` +
        `// The console runs in the browser only, as it does upstream.\n` +
        `const FinanceShell = dynamic(() => import("${fromApp(APP)}/office/FinanceShell"), { ssr: false });\n\n` +
        `export default function FinanceLayout({ children }) {\n  return <FinanceShell>{children}</FinanceShell>;\n}\n`,
      "layout.jsx",
    ),
  };
  const routeList = routes();
  for (const r of routeList) {
    const dir = r.path === "/" ? APP : `${APP}/${r.path.slice(1).replace(/:(\w+)/g, "[$1]")}`;
    const rel = fromApp(dir);
    files[`${dir}/page.jsx`] = {
      from: "apps/web/src/App.tsx",
      text: await format(
        `"use client";\n${header("src/App.tsx")}\n` +
          `import dynamic from "next/dynamic";\n\nimport { Loading } from "${rel}/components/ui";\n\n` +
          `// ${r.path} in the console.\n` +
          `const Page = dynamic(() => import("${rel}/${r.module}"), { ssr: false, loading: () => <Loading what="page" /> });\n\n` +
          `export default function ${r.component}Page() {\n  return <Page />;\n}\n`,
        "page.jsx",
      ),
    };
  }

  const pkg = JSON.parse(fs.readFileSync(path.join(WEB, "package.json"), "utf8"));
  const needs = ["@tanstack/react-query", "clsx", "lucide-react", "yaml"];
  const manifest = {
    about: "The Agent One Finance console in the office's Agent One frontend shape. Made by apps/web/office/convert.mjs; copied into aos-frontend by aof_sync.py.",
    root: `#${ROOT_ID}`,
    routes: routeList.map((r) => ({ path: `/finance${r.path === "/" ? "" : r.path}`, page: r.module })),
    dependencies: Object.fromEntries(needs.map((n) => [n, pkg.dependencies[n]])),
    peer: { next: ">=15", react: ">=18.3" },
    env: { NEXT_PUBLIC_AOF_API: "the AOF API base, default /api", NEXT_PUBLIC_AOF_TRACE_URL: "optional: link to a case's traces" },
    icons: [...icons].sort(),
    files: Object.fromEntries(Object.entries(files).sort().map(([p, f]) => [p, { sha: sha(f.text), from: f.from }])),
  };
  files["aof-frontend.json"] = { text: JSON.stringify(manifest, null, 2) + "\n" };
  return files;
}

const files = await build();
if (CHECK) {
  const stale = Object.entries(files).filter(([p, f]) => !fs.existsSync(path.join(OUT, p)) || fs.readFileSync(path.join(OUT, p), "utf8") !== f.text);
  const extra = fs.existsSync(OUT) ? walk(OUT).map((p) => posix(path.relative(OUT, p))).filter((p) => !(p in files)) : [];
  if (stale.length || extra.length) {
    console.error(`office/aos-frontend is out of date (${stale.length} changed, ${extra.length} extra). Run: npm run office:build`);
    for (const [p] of stale.slice(0, 20)) console.error(`  changed: ${p}`);
    for (const p of extra.slice(0, 20)) console.error(`  extra:   ${p}`);
    process.exit(1);
  }
  console.log(`office/aos-frontend is up to date (${Object.keys(files).length} files)`);
} else {
  fs.rmSync(OUT, { recursive: true, force: true });
  for (const [p, f] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(OUT, p)), { recursive: true });
    fs.writeFileSync(path.join(OUT, p), f.text);
  }
  console.log(`${OUT}: ${Object.keys(files).length} files`);
}
