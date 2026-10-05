// Records the silent demo, one clip per scene, from the running dev stack
// (API :8300, web :5180). Each scene lasts as long as its spoken line takes at
// about 150 words a minute (silent-scenes.json), so a presenter can talk over it.
//
//   node record-silent.mjs [s01,s02,...] --out <dir>
//
// Then: python build-silent.py <dir>   (trims each clip and joins them)
import { chromium } from "/opt/node22/lib/node_modules/playwright/index.mjs";
import fs from "fs";

const W = "http://localhost:5180";
const API = "http://localhost:8300/api";
const args = process.argv.slice(2);
const OUT = args.includes("--out") ? args[args.indexOf("--out") + 1] : `${process.cwd()}/raw-silent`;
const only = args.find((a) => /^s\d/.test(a));
const SCENES = JSON.parse(fs.readFileSync(new URL("./silent-scenes.json", import.meta.url)));
const sc = Object.fromEntries(SCENES.map((s, i) => [s.id, { ...s, n: i + 1 }]));
const duration = (s) => Math.max(s.id === "s08" ? 12 : 8, s.say.split(/\s+/).length / 2.5 + 1.5);

const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const OVERLAY = `
(function(){ if (document.getElementById('demo-cap')) return;
 const s=document.createElement('style'); s.textContent=\`
 #demo-cap{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);max-width:1060px;z-index:99999;white-space:nowrap;
  background:rgba(0,36,63,.92);color:#fff;font:600 19px/1.3 Inter,system-ui,sans-serif;padding:10px 20px;border-radius:12px;
  border-left:5px solid #00aeef;pointer-events:none;box-shadow:0 10px 30px rgba(0,0,0,.3);opacity:0;transition:opacity .4s}
 #demo-cap.on{opacity:1}
 .demo-hl{position:fixed;z-index:99998;border:3px solid #00aeef;border-radius:10px;box-shadow:0 0 0 9999px rgba(0,20,45,.16),0 0 18px #00aeef;pointer-events:none;transition:all .4s}\`;
 document.head.appendChild(s);
 const c=document.createElement('div'); c.id='demo-cap'; document.body.appendChild(c);})();`;

// A small "3 / 15" in the corner so the presenter can keep pace with the script.
const COUNTER = (n, total) => `
(function(){ if (document.getElementById('demo-n')) return; const d=document.createElement('div'); d.id='demo-n';
 d.textContent='${n} / ${total}'; Object.assign(d.style,{position:'fixed',left:'12px',bottom:'10px',zIndex:99999,
 font:'600 11px Inter,system-ui,sans-serif',color:'#7a8ea3',background:'rgba(255,255,255,.75)',padding:'2px 7px',borderRadius:'999px',pointerEvents:'none'});
 document.body.appendChild(d);})();`;

async function caption(p, text) {
  if (!text) return;
  await p.evaluate(OVERLAY);
  await p.evaluate((t) => { const c = document.getElementById("demo-cap"); c.textContent = t; c.classList.add("on"); }, text);
}
async function box(locator) { return locator.first().boundingBox().catch(() => null); }
async function drawHl(p, bb, pad = 6) {
  await p.evaluate(([bb, pad]) => {
    document.querySelectorAll(".demo-hl").forEach((e) => e.remove());
    if (!bb) return; const h = document.createElement("div"); h.className = "demo-hl";
    Object.assign(h.style, { left: bb.x - pad + "px", top: bb.y - pad + "px", width: bb.width + 2 * pad + "px", height: bb.height + 2 * pad + "px" });
    document.body.appendChild(h);
  }, [bb, pad]);
}
async function highlight(p, locator) { await sleep(250); await p.evaluate(OVERLAY); await drawHl(p, await box(locator)); }
async function hlUnion(p, a, c) {
  await sleep(250); await p.evaluate(OVERLAY);
  const A = await box(a), B = await box(c);
  if (!A || !B) return drawHl(p, A || B);
  const x = Math.min(A.x, B.x), y = Math.min(A.y, B.y);
  await drawHl(p, { x, y, width: Math.max(A.x + A.width, B.x + B.width) - x, height: Math.max(A.y + A.height, B.y + B.height) - y }, 8);
}
// The card a piece of text sits in: its nearest rounded ancestor.
const cardOf = (locator) => locator.first().locator('xpath=ancestor-or-self::*[contains(@class,"rounded")][1]');
const clearHl = (p) => p.evaluate(() => document.querySelectorAll(".demo-hl").forEach((e) => e.remove()));
const scrollTo = (p, locator) => locator.first().evaluate((e) => e.scrollIntoView({ block: "center", behavior: "smooth" }));

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
  <div class="f">Helix · governed AI for accounting operations</div></body></html>`;
}
async function revealLines(p, dur, startFrac = 0.06) {
  const n = await p.locator("li").count();
  await sleep(dur * startFrac * 1000);
  for (let i = 0; i < n; i++) { await p.locator("li").nth(i).evaluate((e) => e.classList.add("on")); await sleep((dur * (1 - startFrac) * 1000) / (n + 0.8)); }
}

async function openCase(user, group, key) {
  const r = await fetch(`${API}/capabilities/recon.investigation/cases`, { method: "POST",
    headers: { "X-Helix-User": user, "Content-Type": "application/json" },
    body: JSON.stringify({ case_key: key, team_group: group }) });
  const cid = (await r.json()).case_id;
  for (let i = 0; i < 60; i++) {
    const c = await (await fetch(`${API}/cases/${cid}`, { headers: { "X-Helix-User": user } })).json();
    if (c.status === "awaiting_review") return c;
    await sleep(500);
  }
  throw new Error(`case ${cid} did not reach review`);
}

const PRIME_CONFIRM = process.env.CASE_CONFIRM || "recon.investigation.ddfbb3d6a1f8";   // PRIME-MB-04 · 09-24
const PRIME_ESCALATED = process.env.CASE_ESCALATED || "recon.investigation.8d1e3f40526d"; // PRIME-MB-04 · 09-22

const scenes = {
  async s01(p, d) {
    await p.setContent(card("Helix", ["AI does the legwork: gather, match, classify, draft", "People make every decision", "One governed platform for every accounting team"], "Governed AI for accounting operations"));
    return () => revealLines(p, d);
  },
  async s02(p, d) {
    await p.setContent(card("Today: investigation by hand", ["Pull the data, break by break", "Find the cause, write it up, chase the sign-off", "≈ 12 minutes per break (FOBO's own basis)", "Every team builds its own tooling"], "The problem"));
    return () => revealLines(p, d);
  },
  async s03(p, d, s) {
    await p.goto(`${W}/`); await sleep(1800);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 120); await highlight(p, cardOf(p.getByText("Hours saved (30 days)")));
      await sleep(d * 230); await hlUnion(p, cardOf(p.getByText("Awaiting my review")), cardOf(p.getByText("Overdue", { exact: true })));
      await sleep(d * 230); await highlight(p, cardOf(p.getByText("Escalated to people")));
      await sleep(d * 230); await highlight(p, cardOf(p.getByText("My inbox")));
    };
  },
  async s04(p, d, s) {
    await p.goto(`${W}/inbox`); await sleep(1800);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 150); await highlight(p, p.locator("tbody tr").first());
      await sleep(d * 220); await hlUnion(p, p.getByText("At stake"), p.getByText("889,056.98 GBP"));
      await sleep(d * 200); await clearHl(p);
      await highlight(p, p.getByRole("button", { name: /Needs confirmation/ })); await sleep(900);
      await p.getByRole("button", { name: /Needs confirmation/ }).click(); await sleep(700);
      await highlight(p, p.locator("tbody"));
    };
  },
  async s05(p, d, s) {
    await p.goto(`${W}/cases/${PRIME_CONFIRM}`); await sleep(2200);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 60); await highlight(p, p.getByRole("status", { name: "Your review" }));
      await sleep(d * 230); await highlight(p, p.getByRole("button", { name: /Redemption break · back office/ }));
      await sleep(d * 120); await hlUnion(p, p.getByText("Category", { exact: true }), p.getByText(/Requires controller confirmation/));
      await sleep(d * 260); await clearHl(p);
      await scrollTo(p, p.getByText("Approved before")); await sleep(900);
      await highlight(p, p.getByText("Approved before").locator("xpath=.."));
    };
  },
  async s06(p, d, s) {
    await p.goto(`${W}/cases/${PRIME_CONFIRM}`); await sleep(2200);
    await p.getByRole("button", { name: /Redemption break · front office/ }).click(); await sleep(600);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 100);
      await hlUnion(p, p.getByText("Side", { exact: true }), p.getByText("DO NOT POST", { exact: true }).last());
    };
  },
  async s07(p, d, s) {
    await p.goto(`${W}/cases/${PRIME_ESCALATED}`); await sleep(2200);
    await p.getByRole("button", { name: /Novel break/ }).click(); await sleep(500);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 80); await hlUnion(p, p.getByText("Category", { exact: true }), p.getByText(/Needs your judgement: the model/));
      await sleep(d * 220); await clearHl(p);
      const why = p.getByRole("region", { name: "Why it was escalated" }).or(p.locator('section[aria-label="Why it was escalated"]'));
      await scrollTo(p, why); await sleep(1000);
      await highlight(p, why);
      await sleep(d * 300);
      await highlight(p, p.getByText("What you can do").locator("xpath=.."));
    };
  },
  async s08(p, d, s) {
    // A case nobody has asked about yet, so the new answer is the one on screen.
    const c = await openCase("rita", "cats-motif-rates", { book: process.env.ASK_BOOK || "RATES-LDN-01", cob: process.env.ASK_COB || "2026-09-24" });
    console.log("s08 case", c.case_id);
    await p.goto(`${W}/cases/${c.case_id}`); await sleep(2000);
    await p.getByRole("tab", { name: "Ask about this case" }).or(p.getByRole("button", { name: "Ask about this case" })).first().click();
    await sleep(500);
    return async () => {
      await caption(p, s.caption);
      const input = p.getByRole("textbox").first();
      await input.click(); await input.pressSequentially("Why do these breaks differ, and who owns them?", { delay: 35 });
      await p.getByRole("button", { name: "Ask" }).click();
      await sleep(2000);
      // The answer's byline: which model answered and how many audited lookups it made.
      const byline = p.getByText(/llm:stub/).last();
      await scrollTo(p, byline); await sleep(900);
      await highlight(p, byline);
    };
  },
  async s09(p, d, s) {
    const c = await openCase("rita", "cats-motif-rates", { book: process.env.SIGNOFF_BOOK || "RATES-LDN-02", cob: process.env.SIGNOFF_COB || "2026-09-26" });
    console.log("s09 case", c.case_id, c.groups.map((g) => g.label));
    await p.goto(`${W}/cases/${c.case_id}`); await sleep(2200);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 60); await highlight(p, p.getByText("Proposals", { exact: true }).locator("xpath=ancestor::div[2]"));
      await sleep(d * 220);
      const all = p.getByRole("button", { name: /Approve \d+ straightforward/ });
      await highlight(p, all); await sleep(1200);
      await all.click(); await sleep(800);
      const confirm = p.getByRole("dialog").getByRole("button", { name: /Approve/ });
      if (await confirm.count()) { await confirm.first().click(); }
      await sleep(2500);
      await highlight(p, p.getByRole("status").first());
      await sleep(d * 150);
      if (await p.getByText(/^INC\d+/).count()) await highlight(p, p.getByText(/^INC\d+/).first());
      await sleep(d * 150);
      await highlight(p, p.getByRole("button", { name: /Download Excel/ }).or(p.getByRole("link", { name: /Download Excel/ })));
    };
  },
  async s10(p, d, s) {
    await p.goto(`${W}/capabilities/recon.investigation/groups/cats-motif-rates`); await sleep(2000);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 80); await highlight(p, cardOf(p.getByText("People", { exact: true }).locator("xpath=..")));
      await sleep(d * 350); await highlight(p, cardOf(p.getByText("What this group sets").locator("xpath=..")));
    };
  },
  async s11(p, d, s) {
    await p.goto(`${W}/authoring`); await sleep(1800);
    return async () => {
      await caption(p, s.caption);
      const sel = p.locator("select").first();
      await sleep(d * 80); await highlight(p, sel); await sleep(1200);
      await sel.selectOption({ index: 3 }); await sleep(d * 250);
      await highlight(p, p.getByText(/Passes every platform check/));
      await sleep(d * 250);
      await highlight(p, p.getByRole("button", { name: "Submit for approval" }));
    };
  },
  async s12(p, d, s) {
    await p.goto(`${W}/operations`); await sleep(2200);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 60); await hlUnion(p, p.getByText(/PLATFORM HEALTHY/i), p.getByText(/Entitlement: dev-stub/).last());
      await sleep(d * 250); await hlUnion(p, p.getByText(/^Live tail$/i), p.getByRole("button", { name: /Pause/ }));
      await sleep(d * 200); await clearHl(p);
      await scrollTo(p, p.getByText("Off switches")); await sleep(1200);
      await hlUnion(p, p.getByText("Off switches"), p.getByRole("button", { name: "Switch off" }));
    };
  },
  async s16(p, d, s) {
    const r = await fetch(`${API}/capabilities/break.investigation/cases`, { method: "POST",
      headers: { "X-Helix-User": "frank", "Content-Type": "application/json" },
      body: JSON.stringify({ case_key: { book: process.env.GATE_BOOK || "PRIME-MB-04", cob: process.env.GATE_COB || "2026-10-01" }, team_group: "fobo-prime" }) });
    const cid = (await r.json()).case_id;
    for (let i = 0; i < 60; i++) {
      const c = await (await fetch(`${API}/cases/${cid}`, { headers: { "X-Helix-User": "frank" } })).json();
      if (c.status === "paused_before_reason") break;
      await sleep(500);
    }
    console.log("s16 case", cid);
    await p.goto(`${W}/cases/${cid}`); await sleep(2200);
    return async () => {
      await caption(p, s.caption);
      await sleep(d * 60); await highlight(p, cardOf(p.getByText("Your tollgate")));
      await sleep(d * 300); await highlight(p, p.locator("table").first());
      await sleep(d * 200); await clearHl(p);
      const note = p.getByLabel("Note (optional)");
      await note.click(); await note.pressSequentially("Desk: the swap was amended on Friday", { delay: 30 });
      await highlight(p, p.getByRole("button", { name: "Approve and continue" }));
    };
  },
  async s17(p, d, s) {
    await p.goto(`${W}/cases/${process.env.CASE_SECTIONS || "break.investigation.8baaeb378852"}`); await sleep(2200);
    await p.getByRole("button", { name: /Aged break · side not proven/ }).first().click(); await sleep(700);
    return async () => {
      await caption(p, s.caption);
      const dl = p.getByText("Root cause", { exact: true }).first().locator("xpath=ancestor::dl[1]");
      await sleep(d * 60); await scrollTo(p, dl); await sleep(700); await highlight(p, dl);
      await sleep(d * 330); await clearHl(p);
      const list = p.locator("fieldset").filter({ hasText: "Sign-off checklist" });
      await scrollTo(p, list); await sleep(900); await highlight(p, list);
      for (const q of ["What did I check?", "Why did I check it?", "What evidence did I find?"]) {
        await sleep(700);
        await p.getByRole("radiogroup", { name: q }).getByRole("radio", { name: "yes" }).click().catch(() => {});
      }
    };
  },
  async s18(p, d, s) {
    await p.goto(`${W}/cases/${process.env.CASE_DAY2 || "break.investigation.0a1f2f67ef18"}`); await sleep(2200);
    return async () => {
      await caption(p, s.caption);
      const ft = p.getByText("Follow-through", { exact: true }).first().locator("xpath=..");
      await sleep(d * 50); await scrollTo(p, ft); await sleep(800); await highlight(p, ft);
      await sleep(d * 300); await clearHl(p);
      await p.getByRole("link", { name: "reopened" }).first().click(); await sleep(2200);
      await p.getByRole("button", { name: /Adjustment did not clear/ }).first().click().catch(() => {}); await sleep(800);
      await hlUnion(p, p.getByText("Category", { exact: true }).first(), p.getByText("Product Control", { exact: true }).first());
    };
  },
  async s14(p, d) {
    await p.setContent(card("What it means", ["Analysts move from investigating to reviewing", "One decision per pattern, not per break", "The same features and controls for every team", "New use cases as configuration, not new builds"], "Time and efficiency"));
    return () => revealLines(p, d);
  },
  async s15(p, d) {
    await p.setContent(card("Proposed next steps", ["Pilot: FOBO CATS vs MOTIF, Prime and Rates", "Measure hours saved against the 12-minute basis", "Then: month-end accruals · balance sheet substantiation"], "Next"));
    return () => revealLines(p, d, 0.12);
  },
};

const users = { s03: "frank", s04: "frank", s05: "frank", s06: "frank", s07: "frank", s08: "rita", s09: "rita", s10: "rita", s11: "carol", s12: "frank", s16: "frank", s17: "frank", s18: "frank" };
fs.mkdirSync(OUT, { recursive: true });
for (const id of Object.keys(scenes)) {
  if (only && !only.split(",").includes(id)) continue;
  const s = sc[id];
  const d = duration(s);
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: `${OUT}/${id}`, size: { width: 1280, height: 720 } } });
  await ctx.addInitScript((u) => { localStorage.setItem("helix.user", u); localStorage.setItem("helix.theme", "light"); }, users[id] ?? "frank");
  const t0 = Date.now();
  const p = await ctx.newPage();
  const act = await scenes[id](p, d, s);
  await p.evaluate(COUNTER(s.n, SCENES.length));
  const start = (Date.now() - t0) / 1000;
  const run = act();
  await sleep(d * 1000);
  await run;
  const dur = Math.max(d, (Date.now() - t0) / 1000 - start);   // never cut a step short
  const path = await p.video().path();
  await ctx.close();
  fs.writeFileSync(`${OUT}/${id}.json`, JSON.stringify({ path, start, dur }));
  console.log(id, "start", start.toFixed(2), "dur", dur.toFixed(1));
}
await b.close();
