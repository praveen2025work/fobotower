import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import fs from "fs";
const W = "http://localhost:5180";
const DIR = process.cwd();
const sc = Object.fromEntries(JSON.parse(fs.readFileSync("scenes.json")).map((s) => [s.id, s]));
const only = process.argv[2];
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const OVERLAY = `
(function(){ if (document.getElementById('demo-cap')) return;
 const s=document.createElement('style'); s.textContent=\`
 #demo-cap{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:1040px;z-index:99999;
  background:rgba(0,24,53,.92);color:#fff;font:600 21px/1.35 Inter,system-ui,sans-serif;padding:12px 22px;border-radius:12px;
  border-left:5px solid #00aeef;pointer-events:none;box-shadow:0 10px 30px rgba(0,0,0,.35);opacity:0;transition:opacity .4s}
 #demo-cap.on{opacity:1}
 .demo-hl{position:fixed;z-index:99998;border:3px solid #00aeef;border-radius:10px;box-shadow:0 0 0 9999px rgba(0,20,45,.18),0 0 18px #00aeef;pointer-events:none;transition:all .4s}
 #demo-step{position:fixed;top:14px;right:18px;z-index:99999;background:#00aeef;color:#00243f;font:700 13px Inter,system-ui;padding:5px 11px;border-radius:999px}\`;
 document.head.appendChild(s);
 const c=document.createElement('div'); c.id='demo-cap'; document.body.appendChild(c);})();`;

async function caption(p, text) {
  await p.evaluate(OVERLAY);
  await p.evaluate((t) => { const c = document.getElementById("demo-cap"); c.textContent = t; c.classList.add("on"); }, text);
}
async function highlight(p, locator) {
  await sleep(250);
  const bb = await locator.first().boundingBox().catch(() => null);
  await p.evaluate((bb) => {
    document.querySelectorAll(".demo-hl").forEach((e) => e.remove());
    if (!bb) return; const h = document.createElement("div"); h.className = "demo-hl";
    Object.assign(h.style, { left: bb.x - 6 + "px", top: bb.y - 6 + "px", width: bb.width + 12 + "px", height: bb.height + 12 + "px" });
    document.body.appendChild(h);
  }, bb);
}
async function hlUnion(p, a, b) {
  await sleep(250);
  const A = await a.first().boundingBox().catch(() => null), B = await b.first().boundingBox().catch(() => null);
  if (!A || !B) return highlight(p, A ? a : b);
  const bb = { x: Math.min(A.x, B.x), y: Math.min(A.y, B.y) };
  bb.width = Math.max(A.x + A.width, B.x + B.width) - bb.x; bb.height = Math.max(A.y + A.height, B.y + B.height) - bb.y;
  await p.evaluate((bb) => { document.querySelectorAll(".demo-hl").forEach((e) => e.remove());
    const h = document.createElement("div"); h.className = "demo-hl";
    Object.assign(h.style, { left: bb.x - 8 + "px", top: bb.y - 8 + "px", width: bb.width + 16 + "px", height: bb.height + 16 + "px" });
    document.body.appendChild(h); }, bb);
}
const clearHl = (p) => p.evaluate(() => document.querySelectorAll(".demo-hl").forEach((e) => e.remove()));

function card(title, lines, kicker) {
  return `<html><head><style>
  body{margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;padding:0 110px;box-sizing:border-box;
   background:radial-gradient(circle at 85% 20%,#0b4f8a 0,#00395d 40%,#001b33 100%);color:#fff;font-family:Inter,system-ui,sans-serif}
  .k{color:#00aeef;font-weight:700;letter-spacing:.14em;text-transform:uppercase;font-size:17px;margin-bottom:18px}
  h1{font-size:54px;margin:0 0 28px;line-height:1.1}
  ul{list-style:none;padding:0;margin:0} li{font-size:27px;margin:16px 0;opacity:0;transform:translateY(8px);transition:all .6s}
  li.on{opacity:1;transform:none} li:before{content:"";display:inline-block;width:12px;height:12px;border-radius:50%;background:#00aeef;margin-right:18px;vertical-align:middle}
  .f{position:absolute;bottom:34px;left:110px;font-size:15px;opacity:.6}
  </style></head><body><div class="k">${kicker}</div><h1>${title}</h1><ul>${lines.map((l) => `<li>${l}</li>`).join("")}</ul>
  <div class="f">Agent One Finance · governed AI for accounting operations</div></body></html>`;
}
async function revealLines(p, dur, startFrac = 0.08) {
  const n = await p.locator("li").count();
  for (let i = 0; i < n; i++) { await p.locator("li").nth(i).evaluate((e) => e.classList.add("on")); await sleep((dur * (1 - startFrac) * 1000) / (n + 0.6)); }
}

const scenes = {
  async s01(p, d) {
    await p.setContent(card("Agent One Finance", ["AI does the legwork: gather, match, classify, draft", "People make every decision", "One governed platform for every accounting team"], "Governed AI for accounting operations"));
    return async () => { await revealLines(p, d); };
  },
  async s02(p, d) {
    await p.setContent(card("Today: investigation by hand", ["Pull positions from CATS and MOTIF, break by break", "Find the cause, write it up, chase sign-off", "≈ 12 minutes per break — FOBO's own basis", "Every team builds its own tooling"], "The problem"));
    return async () => { await revealLines(p, d); };
  },
  async s03(p, d) {
    await p.goto(`${W}/inbox`); await sleep(1800);
    return async () => {
      await caption(p, "Cases open themselves at 06:30 — matched and classified before the controller arrives");
      await sleep(d * 300); await highlight(p, p.getByText(/PRIME-MB-04 · COB 2026-09-30/)); await sleep(d * 400);
      await highlight(p, p.locator("aside, nav").getByText("Inbox")); 
    };
  },
  async s04(p, d) {
    await p.goto(`${W}/cases/recon.investigation.8c93e414cf1b`); await sleep(2200);
    return async () => {
      await caption(p, "FOBO's own playbook: 6 cause checks · 14 validation tests · a verdict table");
      await sleep(d * 250);
      await p.getByText(/Redemption break/).first().click(); await sleep(600);
      await hlUnion(p, p.getByText("Category", { exact: true }), p.getByText("CATS support", { exact: true }));
      await caption(p, "Received after cut-off → back-office redemption break → POST, flagged for controller confirmation");
      await sleep(d * 450);
      await highlight(p, p.getByText(/controller confirmation:/i));
    };
  },
  async s05(p, d) {
    await p.goto(`${W}/cases/recon.investigation.8c93e414cf1b`); await sleep(2200);
    return async () => {
      await p.getByText(/Trade booking break/).first().click(); await sleep(500);
      await caption(p, "Rule R2, enforced in code: a front-office cause never posts");
      await hlUnion(p, p.getByText("Category", { exact: true }), p.getByText("DO NOT POST", { exact: true }).last());
      await sleep(d * 420); await clearHl(p);
      await p.mouse.move(700, 500); await p.mouse.wheel(0, 520); await sleep(700);
      await caption(p, "Every figure traced to the system call it came from — untraceable means escalated");
      await highlight(p, p.getByText(/connector calls\)/i));
    };
  },
  async s06(p, d) {
    await p.goto(`${W}/cases/recon.investigation.09209ca6f5f4`); await sleep(2000);
    await p.getByRole("tab", { name: "Ask about this case" }).or(p.getByRole("button", { name: "Ask about this case" })).first().click();
    await sleep(500);
    return async () => {
      await caption(p, "Ask in plain English — answers use only this case's data, every lookup audited");
      const box = p.getByRole("textbox").first();
      await box.click(); await box.pressSequentially("Why is UST 10Y different, and who owns it?", { delay: 30 });
      await p.getByRole("button", { name: "Ask" }).click();
      await sleep(2200);
      await highlight(p, p.getByText(/llm:stub/).last());
    };
  },
  async s07(p, d) {
    const cob = process.env.S07_COB || "2026-09-25";
    const r = await fetch("http://localhost:8300/api/capabilities/recon.investigation/cases", { method: "POST",
      headers: { "X-Helix-User": "rita", "Content-Type": "application/json" },
      body: JSON.stringify({ case_key: { book: "RATES-LDN-02", cob }, team_group: "cats-motif-rates" }) });
    const cid = (await r.json()).case_id;
    for (let i = 0; i < 60; i++) { const c = await (await fetch(`http://localhost:8300/api/cases/${cid}`, { headers: { "X-Helix-User": "rita" } })).json();
      if (c.case?.status === "awaiting_review" || c.status === "awaiting_review") break; await sleep(500); }
    console.log("s07 case", cid);
    await p.goto(`${W}/cases/${cid}`); await sleep(2200);
    return async () => {
      await caption(p, "Breaks grouped into patterns — one decision covers many breaks");
      await highlight(p, p.getByText("Proposals").locator("xpath=ancestor::div[2]"));
      await sleep(d * 300);
      await highlight(p, p.getByRole("button", { name: /Approve all/ }));
      await sleep(900);
      await p.getByRole("button", { name: /Approve all/ }).click(); await sleep(2200);
      await caption(p, "Signed off in seconds — evidence pack ready for audit");
      await highlight(p, p.getByText("Evidence pack (PDF)"));
    };
  },
  async s08(p, d) {
    await p.goto(`${W}/capabilities/recon.investigation/groups/cats-motif-rates`); await sleep(2000);
    return async () => {
      await caption(p, "Rates: same engine, same playbook — its own books, thresholds, schedule and reviewers");
      await hlUnion(p, p.getByText("People", { exact: true }), p.getByText("FOBO_RATES_CONTROLLER", { exact: true }));
      await sleep(d * 400);
      await hlUnion(p, p.getByText("What this group sets"), p.getByText("reasoning.specialists", { exact: true }).first());
    };
  },
  async s09(p, d) {
    await p.goto(`${W}/authoring`); await sleep(1800);
    return async () => {
      await caption(p, "New work — accruals, substantiation, intercompany — drafted from a requirement or template");
      await highlight(p, p.getByLabel("Template")); await sleep(1000);
      await p.getByLabel("Template").selectOption({ index: 3 }); await sleep(d * 300);
      await highlight(p, p.getByText(/Passes every platform check/));
      await caption(p, "Checked by the platform · live only when a second owner approves");
      await sleep(d * 250);
      await highlight(p, p.getByRole("button", { name: "Submit for approval" }));
    };
  },
  async s10(p, d) {
    await p.goto(`${W}/operations`); await sleep(2200);
    return async () => {
      await caption(p, "One platform to run: entitlements on every call · masking · audit");
      await hlUnion(p, p.getByText(/PLATFORM HEALTHY/i), p.getByText(/Entitlement: dev-stub/).last());
      await sleep(d * 300);
      await hlUnion(p, p.getByText(/^Live tail$/i), p.getByRole("button", { name: /Pause/ }));
      await sleep(d * 250); await clearHl(p);
      await p.getByText("Off switches").evaluate((e) => e.scrollIntoView({ block: "center", behavior: "smooth" })); await sleep(1200);
      await caption(p, "Costs capped · any capability, team or connector switched off in one click");
      await hlUnion(p, p.getByText("Off switches"), p.getByRole("button", { name: "Switch off" }));
    };
  },
  async s11(p, d) {
    await p.setContent(card("What it means", ["Analysts move from investigating to reviewing", "One decision per pattern, not per break", "The same controls for every team", "New use cases as configuration, not new builds", "Illustrative: 200 breaks a day × 12 min = 40 hours of investigation"], "Time and efficiency"));
    return async () => { await revealLines(p, d); };
  },
  async s12(p, d) {
    await p.setContent(card("Proposed next steps", ["Pilot: FOBO CATS vs MOTIF — Prime and Rates", "Measure hours saved against the 12-minute basis", "Then: month-end accruals · balance sheet substantiation"], "Next"));
    return async () => { await revealLines(p, d, 0.15); };
  },
};

const users = { s03: "frank", s04: "frank", s05: "frank", s06: "rita", s07: "rita", s08: "rita", s09: "carol", s10: "frank" };
for (const id of Object.keys(scenes)) {
  if (only && !only.split(",").includes(id)) continue;
  const d = sc[id].dur + 0.8;
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: `${DIR}/raw/${id}`, size: { width: 1280, height: 720 } } });
  const user = users[id] ?? "frank";
  await ctx.addInitScript((u) => { localStorage.setItem("helix.user", u); localStorage.setItem("helix.theme", "light"); }, user);
  const t0 = Date.now();
  const p = await ctx.newPage();
  const act = await scenes[id](p, d);
  const start = (Date.now() - t0) / 1000;
  const run = act();
  await sleep(d * 1000);
  await run;
  const path = await p.video().path();
  await ctx.close();
  fs.writeFileSync(`${DIR}/raw/${id}.json`, JSON.stringify({ path, start, dur: d }));
  console.log(id, "start", start.toFixed(2), "dur", d);
}
await b.close();
