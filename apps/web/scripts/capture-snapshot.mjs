// Records the API responses behind the main screens into a snapshot file, so
// a read-only copy of the app (npm run build:snapshot) can be opened anywhere
// without the API. Run against a live stack: node scripts/capture-snapshot.mjs
//   AOF_WEB (http://localhost:5180), SNAPSHOT_USER (frank), PLAYWRIGHT (module path),
//   SNAPSHOT_CASES (extra case ids to include)
import fs from "fs";
const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const WEB = process.env.AOF_WEB ?? "http://localhost:5180";
const USER = process.env.SNAPSHOT_USER ?? "frank";
const OUT = new URL("../src/snapshot/data.json", import.meta.url);

const b = await chromium.launch({ executablePath: process.env.CHROMIUM });
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.addInitScript((u) => localStorage.setItem("aof.user", u), USER);
const data = {};
p.on("response", async (r) => {
  const u = new URL(r.url());
  if (!u.pathname.startsWith("/api/") || r.request().method() !== "GET") return;
  const ct = r.headers()["content-type"] ?? "";
  if (!ct.includes("json")) return;
  try { data[u.pathname + u.search] = { status: r.status(), body: await r.json() }; } catch { /* body gone */ }
});
const visit = async (path, tabs = []) => {
  await p.goto(WEB + path); await p.waitForTimeout(1800);
  for (const t of tabs) {
    await p.getByRole("tab", { name: t }).or(p.getByRole("button", { name: t, exact: true })).first().click().catch(() => {});
    await p.waitForTimeout(900);
  }
};
const api = async (path) => (await (await fetch(`http://localhost:8300${path}`, { headers: { "X-AOF-User": USER } })).json());

await visit("/");
await visit("/inbox");
await visit("/capabilities");
for (const c of await api("/api/capabilities")) {
  await visit(`/capabilities/${c.id}`, [/^groups$/i, /^cases$/i, /^configure$/i, /^flow$/i, /^evals$/i, /^versions$/i]);
  for (const g of await api(`/api/capabilities/${c.id}/groups`).catch(() => [])) await visit(`/capabilities/${c.id}/groups/${g.group}`);
}
// SNAPSHOT_CASES: extra cases to include (comma-separated ids), e.g. the demo's.
const extra = (process.env.SNAPSHOT_CASES ?? "").split(",").filter(Boolean);
const inbox = (await api("/api/inbox")).slice(0, 12).map((i) => i.case_id);
for (const id of [...new Set([...extra, ...inbox])]) await visit(`/cases/${id}`, ["Ask about this case", "Run history", "Proposal"]);
for (const path of ["/operations", "/authoring", "/audit", "/connectors"]) await visit(path);
await b.close();
fs.writeFileSync(OUT, JSON.stringify({ user: USER, captured_at: new Date().toISOString(), responses: data }));
console.log(`captured ${Object.keys(data).length} responses → src/snapshot/data.json`);
