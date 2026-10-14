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
const reading = new Set(); // response bodies still being read
// FNV-1a of a request body, as bodyKey in src/snapshot/install.ts.
const bodyKey = (body) => {
  let h = 0x811c9dc5;
  for (let i = 0; i < body.length; i++) h = Math.imul(h ^ body.charCodeAt(i), 0x01000193) >>> 0;
  return h.toString(16);
};
p.on("response", async (r) => {
  const u = new URL(r.url());
  if (!u.pathname.startsWith("/api/")) return;
  const method = r.request().method();
  // GETs, and the configuration check (it stores nothing) keyed by its exact body.
  const key = method === "GET" ? u.pathname + u.search
    : method === "POST" && u.pathname.endsWith("/check") ? `POST ${u.pathname}${u.search} ${bodyKey(r.request().postData() ?? "")}` : null;
  if (!key) return;
  const ct = r.headers()["content-type"] ?? "";
  if (!ct.includes("json")) return;
  const read = r.json().then((body) => { data[key] = { status: r.status(), body }; }, () => { /* body gone */ });
  reading.add(read); read.finally(() => reading.delete(read));
});
// Waits until nothing has been in flight for a while: a tab can load code, then
// wait out a debounce (the configuration check), before it asks the API.
let inflight = 0;
p.on("request", () => inflight++);
p.on("requestfinished", () => inflight--);
p.on("requestfailed", () => inflight--);
const settle = async () => {
  for (let quiet = 0, waited = 0; quiet < 900 && waited < 10_000; waited += 100) {
    await p.waitForTimeout(100);
    quiet = inflight > 0 ? 0 : quiet + 100;
  }
  await Promise.allSettled([...reading]);
};
// Opens a page, then every tab it has (and, in a case, every proposal), so what
// each one loads is recorded.
const visit = async (path) => {
  await p.goto(WEB + path); await settle();
  const tabs = p.locator('[role="tablist"]:visible [role="tab"]');
  for (let i = 0; i < await tabs.count(); i++) {
    await tabs.nth(i).click({ timeout: 2000 }).catch(() => {});
    await settle();
  }
  const proposals = p.locator('aside[aria-label="Proposals"] li button');
  for (let i = 0; i < await proposals.count(); i++) {
    await proposals.nth(i).click({ timeout: 2000 }).catch(() => {});
    await settle();
  }
};
const api = async (path) => (await (await fetch(`http://localhost:8300${path}`, { headers: { "X-AOF-User": USER } })).json());

await visit("/");
await visit("/inbox");
await visit("/capabilities");
for (const c of await api("/api/capabilities")) {
  await visit(`/capabilities/${c.id}`);
  for (const g of await api(`/api/capabilities/${c.id}/groups`).catch(() => [])) await visit(`/capabilities/${c.id}/groups/${g.group}`);
}
// SNAPSHOT_CASES: extra cases to include (comma-separated ids), e.g. the demo's.
const extra = (process.env.SNAPSHOT_CASES ?? "").split(",").filter(Boolean);
const inbox = (await api("/api/inbox")).slice(0, 12).map((i) => i.case_id);
const caseIds = [...new Set([...extra, ...inbox])];
for (const id of caseIds) await visit(`/cases/${id}`);
for (const path of ["/operations", "/authoring", "/audit", "/connectors"]) await visit(path);
await b.close();

// The files behind the download buttons (a case's Excel export and evidence pack,
// a version's export), fetched directly so they download from the snapshot too.
const file = async (path) => {
  const r = await fetch(`http://localhost:8300${path}`, { headers: { "X-AOF-User": USER } });
  if (!r.ok) return;
  const type = r.headers.get("content-type") ?? "application/octet-stream";
  data[path] = type.includes("json") ? { status: r.status, body: await r.json() }
    : { status: r.status, body: null, file: { type, base64: Buffer.from(await r.arrayBuffer()).toString("base64") } };
};
for (const id of caseIds) {
  await file(`/api/cases/${encodeURIComponent(id)}/export.xlsx`);
  await file(`/api/cases/${encodeURIComponent(id)}/evidence-pack`);
}
for (const c of await api("/api/capabilities")) {
  const enc = encodeURIComponent(c.id);
  for (const v of (await api(`/api/capabilities/${enc}`)).versions ?? []) await file(`/api/capabilities/${enc}/versions/${v.version}/export`);
  for (const g of await api(`/api/capabilities/${enc}/groups`).catch(() => [])) {
    const ge = encodeURIComponent(g.group);
    for (const v of (await api(`/api/capabilities/${enc}/groups/${ge}`)).versions ?? []) await file(`/api/capabilities/${enc}/versions/${v.version}/export?group=${ge}`);
  }
}
fs.writeFileSync(OUT, JSON.stringify({ user: USER, captured_at: new Date().toISOString(), responses: data }));
console.log(`captured ${Object.keys(data).length} responses → src/snapshot/data.json`);
