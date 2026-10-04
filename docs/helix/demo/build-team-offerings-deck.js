// Helix — what we offer each accounting team. Structured deck: theme, layouts, sections.
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("/root/.claude/skills/synced/3f22aee8-e3bd-41eb-916f-b201df2155e5_b4394eef-3dd3-453b-9af2-c91ffab241ff/pptx/scripts/apply_theme.js");

const OUT = process.argv[2] || "helix-team-offerings.pptx";

const THEME = {
  name: "Helix Navy",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2430", lt1: "FFFFFF", dk2: "00395D", lt2: "EEF4F8",
    accent1: "00AEEF", accent2: "00395D", accent3: "0B7A5A", accent4: "C77700", accent5: "6B3FA0", accent6: "B42318",
    hlink: "007EB6", folHlink: "6B3FA0",
  },
};
const HEX = THEME.colors;

async function icon(Comp, color, size = 256) {
  const svg = renderToStaticMarkup(React.createElement(Comp, { color: `#${color}`, size }));
  const buf = await sharp(Buffer.from(svg)).resize(size, size).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.title = "Helix — what we offer each accounting team";
  pres.author = "Helix";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // ---------- layouts ----------
  pres.defineSlideMaster({
    title: "Title Dark",
    background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.55, w: 8.8, h: 1.3, fontSize: 40, bold: true, color: C.background1, valign: "bottom" }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.0, w: 8.8, h: 1.9, fontSize: 18, color: C.accent1, valign: "top" }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "Content",
    background: { color: C.background1 },
    margin: [0.5, 0.5, 0.5, 0.5],
    slideNumber: { x: 9.2, y: 5.25, w: 0.5, h: 0.25, fontSize: 9, color: C.text1, align: "right" },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 28, bold: true, color: C.text2, valign: "middle" }, text: "" } },
      { text: { text: "Helix · governed AI for accounting teams", options: { x: 0.5, y: 5.25, w: 5, h: 0.25, fontSize: 9, color: C.text1, isTextBox: true } } },
    ],
  });

  // reusable pieces
  const iconCircle = async (slide, Comp, x, y, d = 0.5, bg = C.accent1, fg = "FFFFFF") => {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: bg }, line: { color: bg }, objectName: "icon-circle" });
    slide.addImage({ data: await icon(Comp, fg), x: x + d * 0.22, y: y + d * 0.22, w: d * 0.56, h: d * 0.56, objectName: "icon" });
  };
  const card = (slide, x, y, w, h, fill = C.background2) =>
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: "card" });
  const chip = (slide, text, x, y, live) => {
    const color = live ? C.accent3 : C.accent4;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 1.55, h: 0.26, fill: { color: "FFFFFF" }, line: { color, width: 1 }, rectRadius: 0.13, objectName: "status" });
    slide.addText(text, { x, y, w: 1.55, h: 0.26, fontSize: 10, bold: true, color, align: "center", valign: "middle", margin: 0, isTextBox: true });
  };

  // ---------- 1. Title ----------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "Title Dark", sectionTitle: "Introduction" });
  s.addText("Helix for accounting teams", { placeholder: "title" });
  s.addText("What each team gets — one governed platform, configured per team", { placeholder: "body" });
  s.addNotes("Helix is one platform where accounting teams run reconciliations, reviews and commentary with AI doing the legwork and people making every decision. This deck covers what each team gets.");

  // ---------- 2. At a glance ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Introduction" });
  s.addText("One platform, each team configured its own way", { placeholder: "title" });
  const stats = [
    ["6", "capabilities and team groups running today on development data"],
    ["4", "ready examples for further teams, waiting only on their data feeds"],
    ["0", "code per new use case: a team is a configuration file, approved four-eyes"],
  ];
  stats.forEach(([n, label], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.35, 2.85, 2.35);
    s.addText(n, { x: x + 0.25, y: 1.5, w: 2.4, h: 1.05, fontSize: 60, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(label, { x: x + 0.25, y: 2.6, w: 2.4, h: 0.95, fontSize: 14, color: C.text1, margin: 0, valign: "top", isTextBox: true });
  });
  s.addText("Each team keeps its own data, rules, thresholds, reviewers and schedule — on the same review screens and controls as everyone else.",
    { x: 0.5, y: 3.95, w: 9.0, h: 0.7, fontSize: 15, italic: true, color: C.text2, margin: 0, isTextBox: true });
  s.addNotes("Running today on development data: FOBO Prime, FOBO Rates, Cash, Variance commentary, Accruals, Report validation. Ready examples: balance sheet substantiation (runs on dev connectors), intercompany, journal controls, suspense clearing.");

  // ---------- 3. How it works ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Introduction" });
  s.addText("Every case runs the same way", { placeholder: "title" });
  const steps = [
    [fa.FaDatabase, "Data lands", "On a schedule or when the source system says it is ready"],
    [fa.FaProjectDiagram, "Matched", "Classified by the team's own rules and playbook"],
    [fa.FaSearch, "Explained", "Rules first, then the model, every figure traced to source"],
    [fa.FaUserCheck, "People decide", "One decision per pattern, four-eyes where it matters"],
    [fa.FaPaperPlane, "Released", "Recorded; written back only after a second person releases it"],
  ];
  for (let i = 0; i < steps.length; i++) {
    const [ic, head, body] = steps[i];
    const x = 0.5 + i * 1.84;
    await iconCircle(s, ic, x + 0.55, 1.35, 0.6, i === 3 ? C.text2 : C.accent1);
    if (i < steps.length - 1) s.addShape(pres.shapes.LINE, { x: x + 1.25, y: 1.65, w: 1.1, h: 0, line: { color: C.accent1, width: 1.5, endArrowType: "triangle" }, objectName: "flow-arrow" });
    s.addText(head, { x, y: 2.1, w: 1.7, h: 0.45, fontSize: 15, bold: true, color: C.text2, align: "center", margin: 0, isTextBox: true });
    s.addText(body, { x, y: 2.55, w: 1.7, h: 1.1, fontSize: 12, color: C.text1, align: "center", valign: "top", margin: 0, isTextBox: true });
  }
  card(s, 0.5, 3.95, 9.0, 0.85);
  s.addText([
    { text: "Then: ", options: { bold: true, color: C.text2 } },
    { text: "tickets to the owning team, deadline reminders, recurring problems flagged, evidence pack and Excel download for audit.", options: { color: C.text1 } },
  ], { x: 0.75, y: 4.0, w: 8.5, h: 0.75, fontSize: 14, valign: "middle", margin: 0, isTextBox: true });

  // ---------- 4. FOBO ----------
  pres.addSection({ title: "What each team gets" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "What each team gets" });
  s.addText("FOBO: CATS vs MOTIF for Prime and Rates", { placeholder: "title" });
  const fobo = [
    ["Prime", ["Prime books, opened 06:30 every business day", "Signed off by 11:00 the day after COB", "Thresholds not yet confirmed: postings flagged for confirmation"]],
    ["Rates", ["London and New York Rates books, opened 07:15", "Signed off by 12:00, own reviewers", "Thresholds confirmed: postings go through as proposed"]],
  ];
  for (let i = 0; i < 2; i++) {
    const [team, lines] = fobo[i];
    const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.85, 3.35);
    s.addText(team, { x: x + 0.25, y: 1.42, w: 2.4, h: 0.45, fontSize: 20, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(lines.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < lines.length - 1 } })),
      { x: x + 0.25, y: 1.92, w: 2.45, h: 1.9, fontSize: 13, color: C.text1, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
    chip(s, "Running on dev data", x + 0.25, 4.2, true);
  }
  card(s, 6.6, 1.3, 2.9, 3.35, C.text2);
  s.addText("Shared by both", { x: 6.85, y: 1.42, w: 2.45, h: 0.45, fontSize: 18, bold: true, color: C.background1, margin: 0, isTextBox: true });
  const shared = ["FOBO's own playbook: 6 cause checks, 14 validation tests", "Verdict per break: post, don't post, escalate", "Owning team for every break", "Front-office causes never post", "Ticket raised for the team that fixes it"];
  s.addText(shared.map((t, j) => ({ text: t, options: { bullet: true, breakLine: j < shared.length - 1 } })),
    { x: 6.85, y: 1.92, w: 2.45, h: 2.65, fontSize: 13, color: C.background1, paraSpaceAfter: 6, valign: "top", margin: 0, isTextBox: true });
  s.addNotes("Same engine, same rules for both teams; each team has its own books, reviewers, thresholds and schedule. A new desk is a new configuration file.");

  // ---------- 5. Finance & reporting ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "What each team gets" });
  s.addText("Finance, FP&A and reporting", { placeholder: "title" });
  const fin = [
    [fa.FaChartLine, "Variance commentary", "Material variances to budget explained from journal lines; published to the reporting pack after release", true],
    [fa.FaCalendarCheck, "Accruals review", "On the 3rd of each month, movements against plan explained; large ones need a second reviewer", true],
    [fa.FaFileExcel, "Report validation", "A management report in Excel checked against the ledger; signed PDF published", true],
    [fa.FaBalanceScale, "Balance sheet substantiation", "Every material balance matched to its filed support; unsupported ones escalated", false],
  ];
  for (let i = 0; i < fin.length; i++) {
    const [ic, head, body, live] = fin[i];
    const x = 0.5 + (i % 2) * 4.6, y = 1.25 + Math.floor(i / 2) * 1.95;
    card(s, x, y, 4.4, 1.75);
    await iconCircle(s, ic, x + 0.25, y + 0.25, 0.55);
    s.addText(head, { x: x + 0.95, y: y + 0.22, w: 3.25, h: 0.4, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(body, { x: x + 0.95, y: y + 0.62, w: 3.3, h: 0.72, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true });
    chip(s, live ? "Running on dev data" : "Ready example", x + 0.95, y + 1.38, live);
  }

  // ---------- 6. Operations & controls ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "What each team gets" });
  s.addText("Cash, intercompany and ledger control", { placeholder: "title" });
  const ops = [
    [fa.FaUniversity, "Cash: bank vs ledger", "Small differences proposed for write-off by rule; the rest explained and reviewed", true],
    [fa.FaExchangeAlt, "Intercompany", "Receivable matched to payable; FX rounding settled by rule, missing payables chased", false],
    [fa.FaClipboardCheck, "Journal entry controls", "Same person posting and approving, closed periods, out-of-hours and round amounts", false],
    [fa.FaBroom, "Suspense clearing", "Items aged and explained; clearing journals posted only after a second person releases", false],
  ];
  for (let i = 0; i < ops.length; i++) {
    const [ic, head, body, live] = ops[i];
    const x = 0.5 + (i % 2) * 4.6, y = 1.25 + Math.floor(i / 2) * 1.95;
    card(s, x, y, 4.4, 1.75);
    await iconCircle(s, ic, x + 0.25, y + 0.25, 0.55);
    s.addText(head, { x: x + 0.95, y: y + 0.22, w: 3.25, h: 0.4, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(body, { x: x + 0.95, y: y + 0.62, w: 3.3, h: 0.72, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true });
    chip(s, live ? "Running on dev data" : "Needs its data feed", x + 0.95, y + 1.38, live);
  }
  s.addNotes("Intercompany needs an intercompany feed; journal controls need a journals feed; suspense clearing needs suspense data and journal-posting access. Each is a configuration file already validated by the platform.");

  // ---------- 7. Every team gets ----------
  pres.addSection({ title: "Common to every team" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Common to every team" });
  s.addText("What every team gets, whatever the process", { placeholder: "title" });
  const common = [
    [fa.FaBolt, "Work arrives prepared", "Opened, matched, classified and explained before anyone starts"],
    [fa.FaLayerGroup, "One decision per pattern", "Approve straightforward groups together; flagged ones one by one"],
    [fa.FaEye, "Clear review screens", "What is needed, from whom and why; escalations in plain words"],
    [fa.FaShieldAlt, "Controls built in", "Four-eyes, confirmations, maker-checker, release by a second person"],
    [fa.FaTicketAlt, "Follow-through", "Tickets to the owning team, deadlines, recurring problems flagged"],
    [fa.FaFileAlt, "Audit and outputs", "Evidence pack, Excel download, cover while away, hours saved measured"],
  ];
  for (let i = 0; i < common.length; i++) {
    const [ic, head, body] = common[i];
    const x = 0.5 + (i % 3) * 3.05, y = 1.25 + Math.floor(i / 3) * 1.9;
    await iconCircle(s, ic, x, y, 0.5);
    s.addText(head, { x: x + 0.65, y: y + 0.02, w: 2.25, h: 0.55, fontSize: 15, bold: true, color: C.text2, valign: "top", margin: 0, isTextBox: true });
    s.addText(body, { x: x + 0.65, y: y + 0.62, w: 2.25, h: 1.0, fontSize: 12, color: C.text1, valign: "top", margin: 0, isTextBox: true });
  }

  // ---------- 8. Technology & risk ----------
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Common to every team" });
  s.addText("For technology and risk: one platform to run", { placeholder: "title" });
  const tech = [
    [fa.FaKey, "Entitlements on every data access", "Each call checked against the person's roles and data scope, and logged"],
    [fa.FaUserSecret, "Sensitive data masked", "Account numbers masked and counterparties pseudonymised before the model sees anything"],
    [fa.FaPowerOff, "Cost caps and off switches", "Spend capped per case and per day; any capability, team or connector off in one click"],
    [fa.FaFlask, "Tested before it goes live", "New versions replayed on past decisions; promoted between environments and approved again"],
  ];
  for (let i = 0; i < tech.length; i++) {
    const [ic, head, body] = tech[i];
    const y = 1.2 + i * 0.95;
    await iconCircle(s, ic, 0.5, y, 0.55, C.text2);
    s.addText(head, { x: 1.25, y: y - 0.02, w: 8.2, h: 0.35, fontSize: 16, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(body, { x: 1.25, y: y + 0.33, w: 8.2, h: 0.4, fontSize: 13, color: C.text1, margin: 0, isTextBox: true });
  }

  // ---------- 9. Onboarding ----------
  pres.addSection({ title: "Getting started" });
  s = pres.addSlide({ masterName: "Content", sectionTitle: "Getting started" });
  s.addText("Bringing on a new team", { placeholder: "title" });
  const paths = [
    ["Same kind of work", "Another reconciliation, say", "One configuration file on an existing capability, approved by the team's second owner"],
    ["New kind of work", "A new review or control", "Drafted from a written requirement or template, checked by the platform, live after a second owner approves"],
    ["New data source", "A system not yet connected", "Connected once by the platform team; after that every team uses it through configuration"],
  ];
  paths.forEach(([head, sub, body], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.3, 2.85, 2.75);
    s.addText(String(i + 1), { x: x + 0.25, y: 1.45, w: 0.6, h: 0.6, fontSize: 32, bold: true, color: C.accent1, margin: 0, isTextBox: true });
    s.addText(head, { x: x + 0.25, y: 2.08, w: 2.4, h: 0.4, fontSize: 17, bold: true, color: C.text2, margin: 0, isTextBox: true });
    s.addText(sub, { x: x + 0.25, y: 2.48, w: 2.4, h: 0.32, fontSize: 12, italic: true, color: C.text1, margin: 0, isTextBox: true });
    s.addText(body, { x: x + 0.25, y: 2.85, w: 2.4, h: 1.3, fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true });
  });
  s.addNotes("Numbered by effort: the first is configuration only, the third is the one that needs platform work.");

  // ---------- 10. Status & next steps ----------
  s = pres.addSlide({ masterName: "Title Dark", sectionTitle: "Getting started" });
  s.addText("Where we are, and next steps", { placeholder: "title" });
  s.addText([
    { text: "Today: running end to end on development data with a stand-in model", options: { bullet: true, breakLine: true } },
    { text: "To go live: office connectors (CATS, MOTIF, ledger), the real model, SSO", options: { bullet: true, breakLine: true } },
    { text: "Proposed: pilot FOBO Prime and Rates, measure hours saved, then accruals and substantiation", options: { bullet: true } },
  ], { placeholder: "body" });

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
