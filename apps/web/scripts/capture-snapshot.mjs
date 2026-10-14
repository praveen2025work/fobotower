// Records the API responses behind every screen into a snapshot file, so a
// read-only copy of the app (npm run build:snapshot) can be opened anywhere
// without the API: every page, tab and case the console links to, and what
// opens when someone clicks (run history steps, eval runs, version diffs,
// filters, downloads). Run against a live stack: node scripts/capture-snapshot.mjs
//   AOF_WEB (http://localhost:5180), SNAPSHOT_USER (frank), PLAYWRIGHT (module path),
//   SNAPSHOT_CASES (extra case ids to include)
import fs from "fs";
import zlib from "zlib";
const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const WEB = process.env.AOF_WEB ?? "http://localhost:5180";
const USER = process.env.SNAPSHOT_USER ?? "frank";
const OUT = new URL("../src/snapshot/data.b64", import.meta.url);

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
const HEADERS = { "X-AOF-User": USER };
const api = async (path) => (await (await fetch(`http://localhost:8300${path}`, { headers: HEADERS })).json());
const enc = encodeURIComponent;

await visit("/");
await visit("/inbox");
await visit("/capabilities");
const caps = await api("/api/capabilities");
const groupsOf = {};
for (const c of caps) {
  await visit(`/capabilities/${c.id}`);
  groupsOf[c.id] = await api(`/api/capabilities/${enc(c.id)}/groups`).catch(() => []);
  for (const g of groupsOf[c.id]) await visit(`/capabilities/${c.id}/groups/${g.group}`);
}
// Every case the console lists (each capability's cases, the inbox), plus
// SNAPSHOT_CASES: anything the snapshot links to must open in it.
const extra = (process.env.SNAPSHOT_CASES ?? "").split(",").filter(Boolean);
const listed = [];
for (const c of caps) listed.push(...(await api(`/api/capabilities/${enc(c.id)}/cases`)).map((x) => x.case_id));
listed.push(...(await api("/api/inbox")).map((i) => i.case_id));
const caseIds = [...new Set([...extra, ...listed])];
for (const id of caseIds) await visit(`/cases/${id}`);
for (const path of ["/operations", "/authoring", "/audit", "/connectors"]) await visit(path);
await b.close();

// What the console asks for only when someone picks or opens something (a run
// history step, an eval run, two versions to compare, a filter) or downloads a
// file, fetched straight from the API under the same keys.
const get = async (path) => {
  if (data[path]) return data[path].body;
  const r = await fetch(`http://localhost:8300${path}`, { headers: HEADERS });
  if (!r.ok) return null;
  const type = r.headers.get("content-type") ?? "application/octet-stream";
  data[path] = type.includes("json") ? { status: r.status, body: await r.json() }
    : { status: r.status, body: null, file: { type, base64: Buffer.from(await r.arrayBuffer()).toString("base64") } };
  return data[path].body;
};
const recordCase = async (id) => {
  const base = `/api/cases/${enc(id)}`;
  await get(base);
  await get(`${base}/messages`);
  for (const step of (await get(`${base}/history`)) ?? []) await get(`${base}/history/${enc(step.checkpoint_id)}`);
  await get(`${base}/export.xlsx`);
  await get(`${base}/evidence-pack`);
};
for (const id of caseIds) await recordCase(id);
for (const c of caps) {
  const id = enc(c.id);
  const groups = groupsOf[c.id].map((g) => enc(g.group));
  const pairs = (vs) => vs.flatMap((a) => vs.filter((v) => v !== a).map((v) => [a, v]));
  const versions = ((await get(`/api/capabilities/${id}`))?.versions ?? []).map((v) => v.version);
  for (const v of versions) await get(`/api/capabilities/${id}/versions/${v}/export`);
  for (const [a, v] of pairs(versions)) await get(`/api/capabilities/${id}/versions/${a}/diff/${v}`);
  for (const g of groups) {
    const gv = ((await get(`/api/capabilities/${id}/groups/${g}`))?.versions ?? []).map((v) => v.version);
    for (const v of gv) await get(`/api/capabilities/${id}/versions/${v}/export?group=${g}`);
    for (const [a, v] of pairs(gv)) await get(`/api/capabilities/${id}/groups/${g}/versions/${a}/diff/${v}`);
  }
  for (const run of (await get(`/api/capabilities/${id}/evals`)) ?? []) await get(`/api/evals/${enc(run.run_id)}`);
  for (const q of ["", ...groups.map((g) => `?team_group=${g}`)]) {
    for (const part of ["cases", "evals/available", "flow", "contract", "learning", "recurring"]) await get(`/api/capabilities/${id}/${part}${q}`);
  }
  await get(`/api/audit?capability_id=${id}`);
}
// Cases named anywhere in what was recorded (a follow-up, a sampled child case,
// a notification) open too.
const caseRef = new RegExp(`"((?:${caps.map((c) => c.id.replace(/[.]/g, "\\.")).join("|")})\\.[0-9a-f]{12}(?:\\.f\\d+)?)"`, "g");
for (let more = true; more;) {
  const named = new Set([...JSON.stringify(Object.values(data).map((r) => r.body)).matchAll(caseRef)].map((m) => m[1]));
  const missing = [...named].filter((id) => !data[`/api/cases/${enc(id)}`]);
  more = false;
  for (const id of missing) { await recordCase(id); more = more || !!data[`/api/cases/${enc(id)}`]; }
}

// Stored compressed (most of it is run state that repeats); the snapshot unpacks it.
const json = JSON.stringify({ user: USER, captured_at: new Date().toISOString(), responses: data });
fs.writeFileSync(OUT, zlib.gzipSync(json, { level: 9 }).toString("base64"));
const cases = Object.keys(data).filter((k) => /^\/api\/cases\/[^/]+$/.test(k)).length;
console.log(`captured ${Object.keys(data).length} responses, ${cases} cases (${(json.length / 1e6).toFixed(1)} MB) → src/snapshot/data.b64 (${(fs.statSync(OUT).size / 1e6).toFixed(1)} MB)`);
