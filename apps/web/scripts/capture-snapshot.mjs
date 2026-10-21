// Records the API responses behind every screen into a snapshot file, so a
// read-only copy of the app (npm run build:snapshot) can be opened anywhere
// without the API: every page, tab and task the console links to, and what
// opens when someone clicks (run history steps, eval runs, version diffs,
// filters, downloads). Run against a live stack: node scripts/capture-snapshot.mjs
//   AOF_WEB (http://localhost:5180), SNAPSHOT_USER (frank), PLAYWRIGHT (module path),
//   SNAPSHOT_TASKS (extra task ids to include), SNAPSHOT_AGENTS (agent ids to include;
//   default all), SNAPSHOT_SCOPE (all, or config: the agents' configuration only, no tasks)
import fs from "fs";
import zlib from "zlib";
const { chromium } = await import(process.env.PLAYWRIGHT ?? "playwright");
const WEB = process.env.AOF_WEB ?? "http://localhost:5180";
const USER = process.env.SNAPSHOT_USER ?? "frank";
const AGENTS = (process.env.SNAPSHOT_AGENTS ?? "").split(",").filter(Boolean);
const CONFIG = process.env.SNAPSHOT_SCOPE === "config";
// Chosen agents with their tasks: the platform pages (operations, audit, authoring) are left out.
const SCOPE = CONFIG ? "config" : AGENTS.length ? "agents" : "all";
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
// Opens a page, then every tab it has (and, in a task, every proposal), so what
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

if (!CONFIG) {
  await visit("/");
  await visit("/inbox");
}
await visit("/agents");
const caps = (await api("/api/agents")).filter((c) => !AGENTS.length || AGENTS.includes(c.id));
const groupsOf = {};
for (const c of caps) {
  await visit(`/agents/${c.id}`);
  groupsOf[c.id] = await api(`/api/agents/${enc(c.id)}/groups`).catch(() => []);
  for (const g of groupsOf[c.id]) await visit(`/agents/${c.id}/groups/${g.group}`);
}
// Every task the console lists (each agent's tasks, the inbox), plus
// SNAPSHOT_TASKS: anything the snapshot links to must open in it.
const extra = (process.env.SNAPSHOT_TASKS ?? "").split(",").filter(Boolean);
const listed = [];
if (!CONFIG) {
  for (const c of caps) listed.push(...(await api(`/api/agents/${enc(c.id)}/tasks`)).map((x) => x.task_id));
  listed.push(...(await api("/api/inbox")).filter((i) => !AGENTS.length || AGENTS.includes(i.agent_id)).map((i) => i.task_id));
}
const taskIds = CONFIG ? [] : [...new Set([...extra, ...listed])];
for (const id of taskIds) await visit(`/tasks/${id}`);
for (const path of SCOPE === "all" ? ["/operations", "/authoring", "/audit", "/connectors"] : ["/connectors"]) await visit(path);
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
const recordTask = async (id) => {
  const base = `/api/tasks/${enc(id)}`;
  await get(base);
  await get(`${base}/messages`);
  for (const step of (await get(`${base}/history`)) ?? []) await get(`${base}/history/${enc(step.checkpoint_id)}`);
  await get(`${base}/export.xlsx`);
  await get(`${base}/evidence-pack`);
};
for (const id of taskIds) await recordTask(id);
for (const c of caps) {
  const id = enc(c.id);
  const groups = groupsOf[c.id].map((g) => enc(g.group));
  const pairs = (vs) => vs.flatMap((a) => vs.filter((v) => v !== a).map((v) => [a, v]));
  const versions = ((await get(`/api/agents/${id}`))?.versions ?? []).map((v) => v.version);
  for (const v of versions) await get(`/api/agents/${id}/versions/${v}/export`);
  for (const [a, v] of pairs(versions)) await get(`/api/agents/${id}/versions/${a}/diff/${v}`);
  for (const g of groups) {
    const gv = ((await get(`/api/agents/${id}/groups/${g}`))?.versions ?? []).map((v) => v.version);
    for (const v of gv) await get(`/api/agents/${id}/versions/${v}/export?group=${g}`);
    for (const [a, v] of pairs(gv)) await get(`/api/agents/${id}/groups/${g}/versions/${a}/diff/${v}`);
  }
  if (!CONFIG) for (const run of (await get(`/api/agents/${id}/evals`)) ?? []) await get(`/api/evals/${enc(run.run_id)}`);
  for (const q of ["", ...groups.map((g) => `?team_group=${g}`)]) {
    for (const part of CONFIG ? ["flow", "contract"] : ["tasks", "evals/available", "flow", "contract", "learning", "recurring"]) {
      await get(`/api/agents/${id}/${part}${q}`);
    }
  }
  if (SCOPE === "all") await get(`/api/audit?agent_id=${id}`);
}
// The chosen agents only; a config-only snapshot keeps their configuration and the
// connectors, and nothing about tasks (the inbox and notifications are empty).
if (AGENTS.length || CONFIG) {
  const keep = new Set(caps.map((c) => c.id));
  data["/api/agents"].body = data["/api/agents"].body.filter((c) => keep.has(c.id));
  for (const key of Object.keys(data)) {
    const m = key.match(/^(?:POST )?\/api\/agents\/([^/?\s]+)/);
    if (m && !keep.has(decodeURIComponent(m[1]))) delete data[key];
  }
}
if (SCOPE === "agents") {
  // Lists shared by every agent keep only the chosen agents' tasks.
  const ours = (taskId) => caps.some((c) => new RegExp(`^${c.id.replace(/[.]/g, "\\.")}\\.[0-9a-f]{12}`).test(taskId ?? ""));
  if (data["/api/inbox"]) data["/api/inbox"].body = data["/api/inbox"].body.filter((i) => ours(i.task_id));
  if (data["/api/requests"]) data["/api/requests"].body = data["/api/requests"].body.filter((r) => ours(r.task_id));
  if (data["/api/notifications"]) {
    const items = data["/api/notifications"].body.items.filter((n) => !n.task_id || ours(n.task_id));
    data["/api/notifications"].body = { ...data["/api/notifications"].body, items, unread: items.filter((n) => !n.read).length };
  }
  if (data["/api/overview"]) {
    const keep = new Set(caps.map((c) => c.id));
    data["/api/overview"].body.agents = data["/api/overview"].body.agents.filter((c) => keep.has(c.id));
  }
  for (const key of Object.keys(data)) if (/^\/api\/(operations|audit|authoring|schedules|switches)\b/.test(key)) delete data[key];
}
if (CONFIG) {
  const config = [/^\/api\/(me|me\/delegations|dev\/users|platform|agents)$/, /^(POST )?\/api\/agents\/[^/?\s]+(\/(groups(\/[^/?]+)?|flow|contract|versions\/.+|groups\/[^/]+\/versions\/.+|check))?(\?team_group=[^&]+)?( \S+)?$/,
    /^\/api\/operations$/];
  for (const key of Object.keys(data)) if (!config.some((re) => re.test(key))) delete data[key];
  data["/api/inbox"] = { status: 200, body: [] };
  data["/api/notifications"] = { status: 200, body: { unread: 0, items: [] } };
  data["/api/requests"] = { status: 200, body: [] };
}
// Tasks named anywhere in what was recorded (a follow-up, a sampled child task,
// a notification) open too.
const taskRef = new RegExp(`"((?:${caps.map((c) => c.id.replace(/[.]/g, "\\.")).join("|")})\\.[0-9a-f]{12}(?:\\.f\\d+)?)"`, "g");
for (let more = !CONFIG; more;) {
  const named = new Set([...JSON.stringify(Object.values(data).map((r) => r.body)).matchAll(taskRef)].map((m) => m[1]));
  const missing = [...named].filter((id) => !data[`/api/tasks/${enc(id)}`]);
  more = false;
  for (const id of missing) { await recordTask(id); more = more || !!data[`/api/tasks/${enc(id)}`]; }
}

// Notifications and questions about a task the snapshot does not hold are left out.
const kept = (taskId) => !taskId || !!data[`/api/tasks/${enc(taskId)}`];
if (data["/api/notifications"]) {
  const items = data["/api/notifications"].body.items.filter((n) => kept(n.task_id));
  data["/api/notifications"].body = { ...data["/api/notifications"].body, items, unread: items.filter((n) => !n.read).length };
}
if (data["/api/requests"]) data["/api/requests"].body = data["/api/requests"].body.filter((r) => kept(r.task_id));

// Stored compressed (most of it is run state that repeats); the snapshot unpacks it.
const json = JSON.stringify({ user: USER, captured_at: new Date().toISOString(), scope: SCOPE, responses: data });
fs.writeFileSync(OUT, zlib.gzipSync(json, { level: 9 }).toString("base64"));
const tasks = Object.keys(data).filter((k) => /^\/api\/tasks\/[^/]+$/.test(k)).length;
console.log(`captured ${Object.keys(data).length} responses, ${tasks} tasks (${(json.length / 1e6).toFixed(1)} MB) → src/snapshot/data.b64 (${(fs.statSync(OUT).size / 1e6).toFixed(1)} MB)`);
