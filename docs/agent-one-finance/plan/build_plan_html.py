import html, runpy, datetime as dt
g = runpy.run_path(__import__("os").path.join(__import__("os").path.dirname(__file__), "plan_data.py"))
EPICS, MIL, S, SPR, SNAME = g["EPICS"], g["MILESTONES"], g["S"], g["SPR"], g["SNAME"]
EST, CUR = g["EPIC_STATUS"], g["CURRENT"]
e = html.escape
order = ["S0","S1","S2","S3","S4","S5","S6"]
def d(x): return dt.date.fromisoformat(x)
def fmt(x): return d(x).strftime("%d %b").lstrip("0")
def fmty(x): return d(x).strftime("%d %b %Y").lstrip("0")

# stories with ids (same numbering as the CSV)
stories=[]; n=0
for s in S:
    n+=1; ep,summ,desc,acc,pri,pts,spr,team,env,dep=s[:10]; st=s[10] if len(s)>10 else "To Do"
    stories.append(dict(id=f"{ep}-S{n:02d}",ep=ep,summ=summ,desc=desc,acc=acc,pri=pri,pts=pts,spr=spr,team=team,env=env,dep=dep,st=st))
by_ep={x[0]:[s for s in stories if s["ep"]==x[0]] for x in EPICS}
tot_pts=sum(s["pts"] for s in stories)

# gantt columns: working-day weights; freeze column between S5 and S6
cols=[("S0",5),("S1",10),("S2",10),("S3",10),("S4",10),("S5",8),("FZ",4),("S6",10)]
colidx={c:i+2 for i,(c,_) in enumerate(cols)}   # grid col line start (col 1 = labels)
gtc="minmax(12rem,15rem) "+" ".join(f"{w}fr" for _,w in cols)

def chip(st):
    cls={"In Progress":"prog","To Do":"todo","Done":"done"}.get(st,"todo")
    return f'<span class="chip {cls}">{e(st)}</span>'

head_cells="".join(
    f'<div class="gh{" fz" if c=="FZ" else ""}" style="grid-column:{colidx[c]}"><b>{"Freeze" if c=="FZ" else e(c)}</b>'
    f'<span>{"24 Dec–3 Jan" if c=="FZ" else fmt(SPR[c][0])+"–"+fmt(SPR[c][1])}</span></div>' for c,_ in cols)
rows=""
for ep in EPICS:
    a,b=ep[4].split("-"); st=EST.get(ep[0],"To Do")
    start=colidx[a]; end=colidx[b]+1
    rows+=(f'<a class="gl" href="#{ep[0]}"><span class="mono">{ep[0]}</span> {e(ep[1])}</a>'
           f'<div class="bar {"prog" if st=="In Progress" else ""}" style="grid-column:{start}/{end}" title="{e(ep[1])}: {fmty(SPR[a][0])} to {fmty(SPR[b][1])}"></div>')
# milestone row
def col_for(date):
    for c in order:
        if d(SPR[c][0])<=d(date)<=d(SPR[c][1])+dt.timedelta(days=2): return c
    return "S4" if date.startswith("2026-11-30") else "S6"
mrow='<div class="gl mlabel">Milestones</div>'
grp={}
for m in MIL: grp.setdefault(col_for(m[2]),[]).append(m)
for c,ms in grp.items():
    mrow+=f'<div class="ms" style="grid-column:{colidx[c]}/{colidx[c]+1}">'+"".join(f'<span title="{e(m[1])} ({fmty(m[2])})"><i></i><span class="mono">{m[0]}</span></span>' for m in ms)+'</div>'

ms_items="".join(f'<li><span class="mono mid">{m[0]}</span><time class="mono">{fmty(m[2])}</time><div><b>{e(m[1])}</b><p>{e(m[3])}</p></div></li>' for m in MIL)

l1_rows=""
for ep in EPICS:
    a,b=ep[4].split("-"); st=EST.get(ep[0],"To Do"); pts=sum(s["pts"] for s in by_ep[ep[0]])
    cur=CUR.get(ep[0],"")
    l1_rows+=(f'<tr><td class="mono">{ep[0]}</td><td><a href="#{ep[0]}"><b>{e(ep[1])}</b></a><p class="sub">{e(ep[2])}</p>'
              f'{"<p class=cur>Now: "+e(cur)+"</p>" if cur else ""}</td><td>{e(ep[3])}</td>'
              f'<td class="mono nowrap">{fmt(SPR[a][0])} – {fmt(SPR[b][1])}</td><td class="num mono">{len(by_ep[ep[0]])}</td><td class="num mono">{pts}</td>'
              f'<td>{e(ep[6])}</td><td>{chip(st)}</td></tr>')

sections=""
for ep in EPICS:
    a,b=ep[4].split("-"); st=EST.get(ep[0],"To Do"); items=by_ep[ep[0]]
    trs="".join(
        f'<tr data-spr="{s["spr"]}"><td class="mono nowrap">{s["id"]}</td><td><b>{e(s["summ"])}</b><p class="sub">{e(s["desc"])}</p>'
        f'<p class="acc"><span>Done when</span> {e(s["acc"])}</p>{"<p class=dep><span>Depends on</span> "+e(s["dep"])+"</p>" if s["dep"] else ""}</td>'
        f'<td class="mono nowrap">{s["spr"]}<span class="sub2">{fmt(SPR[s["spr"]][0])}–{fmt(SPR[s["spr"]][1])}</span></td>'
        f'<td class="num mono">{s["pts"]}</td><td>{e(s["team"])}</td><td>{e(s["env"]) or "–"}</td>'
        f'<td><span class="pri {s["pri"].lower()}">{e(s["pri"])}</span></td><td>{chip(s["st"])}</td></tr>' for s in items)
    sections+=(f'<details class="epic" id="{ep[0]}"><summary><span class="mono eid">{ep[0]}</span><span class="et">{e(ep[1])}</span>'
               f'<span class="em mono">{fmt(SPR[a][0])} – {fmt(SPR[b][1])} · {len(items)} stories · {sum(s["pts"] for s in items)} pts</span>{chip(st)}</summary>'
               f'<div class="eb"><dl><div><dt>Objective</dt><dd>{e(ep[2])}</dd></div><div><dt>Deliverables</dt><dd>{e(ep[5])}</dd></div>'
               f'<div><dt>Exit criteria</dt><dd>{e(ep[6])}</dd></div><div><dt>Dependencies</dt><dd>{e(ep[7])}</dd></div><div><dt>Team</dt><dd>{e(ep[3])}</dd></div></dl>'
               f'<div class="tw"><table class="st"><thead><tr><th>ID</th><th>Story</th><th>Sprint</th><th class="num">Pts</th><th>Team</th><th>Env</th><th>Priority</th><th>Status</th></tr></thead>'
               f'<tbody>{trs}</tbody></table></div></div></details>')

spr_pts={c:sum(s["pts"] for s in stories if s["spr"]==c) for c in order}
filt="".join(f'<button type="button" class="fb" data-f="{c}" id="f-{c}">{c} <span class="mono">{spr_pts[c]}</span></button>' for c in order)
inprog=sum(1 for s in stories if s["st"]=="In Progress")

page=f'''<title>Agent One Finance Delivery Plan</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one reading column; summary first (dates, gantt, milestones, level 1), level 2 stories below as one fold per epic */
:root {{
  --bg:#f6f8fb; --surface:#ffffff; --ink:#0d1b2e; --muted:#53627a; --line:#dde3ec;
  --accent:#00395d; --accent-2:#0076b6; --bar:#9fb7cf; --prog:#0076b6; --warn:#a85d00; --warn-bg:#fdf1e2;
  --ok:#1e7d4f; --ok-bg:#e5f4ec; --todo-bg:#eef1f5; --freeze:repeating-linear-gradient(135deg,#e4e9f0 0 6px,#f6f8fb 6px 12px);
  --display:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --body:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#0b1420; --surface:#111d2c; --ink:#e6edf6; --muted:#9aaabf; --line:#22334a;
  --accent:#8cc8f0; --accent-2:#5fb3e8; --bar:#3b5878; --prog:#3d9ad6; --warn:#f0b36a; --warn-bg:#3a2a14;
  --ok:#6fcf9b; --ok-bg:#163326; --todo-bg:#1a2838; --freeze:repeating-linear-gradient(135deg,#1a2838 0 6px,#0b1420 6px 12px); color-scheme:dark }} }}
:root[data-theme="dark"] {{
  --bg:#0b1420; --surface:#111d2c; --ink:#e6edf6; --muted:#9aaabf; --line:#22334a;
  --accent:#8cc8f0; --accent-2:#5fb3e8; --bar:#3b5878; --prog:#3d9ad6; --warn:#f0b36a; --warn-bg:#3a2a14;
  --ok:#6fcf9b; --ok-bg:#163326; --todo-bg:#1a2838; --freeze:repeating-linear-gradient(135deg,#1a2838 0 6px,#0b1420 6px 12px); color-scheme:dark }}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--ink); font:15px/1.55 var(--body); }}
.wrap {{ max-width:72rem; margin:0 auto; padding-inline:16px; padding-block:2rem 4rem; display:grid; gap:2.5rem }}
.wrap > * {{ min-width:0 }}
.mono {{ font-family:var(--mono); font-variant-numeric:tabular-nums }}
h1,h2,h3 {{ font-family:var(--display); text-wrap:balance; margin:0; letter-spacing:-.01em }}
h1 {{ font-size:clamp(1.7rem,3.5vw,2.4rem); font-weight:800; color:var(--accent) }}
h2 {{ font-size:1.25rem; font-weight:700; margin-bottom:.9rem }}
.eyebrow {{ font:600 .72rem var(--mono); letter-spacing:.12em; text-transform:uppercase; color:var(--accent-2); margin:0 0 .4rem }}
header p.lede {{ max-width:62ch; color:var(--muted); margin:.6rem 0 0 }}
.keys {{ display:flex; flex-wrap:wrap; gap:.6rem 2rem; margin-top:1.4rem; padding-top:1.2rem; border-top:1px solid var(--line) }}
.keys div {{ display:grid; gap:.1rem }}
.keys dt {{ font:600 .68rem var(--mono); letter-spacing:.1em; text-transform:uppercase; color:var(--muted) }}
.keys dd {{ margin:0; font-weight:700; font-size:1.05rem }}
.keys dd.big {{ color:var(--accent) }}
a {{ color:var(--accent-2) }} a:focus-visible,button:focus-visible,summary:focus-visible {{ outline:2px solid var(--accent-2); outline-offset:2px }}
.panel {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:1.1rem 1.2rem }}
.tw {{ overflow-x:auto }}
/* gantt */
.gantt {{ display:grid; grid-template-columns:{gtc}; row-gap:.35rem; column-gap:0; min-width:52rem; align-items:center }}
.gh {{ font-size:.72rem; color:var(--muted); padding:0 .35rem .5rem; border-left:1px solid var(--line); display:grid; line-height:1.3 }}
.gh b {{ color:var(--ink); font:600 .75rem var(--mono) }}
.gh.fz {{ background:var(--freeze); border-radius:4px 4px 0 0 }}
.gl {{ grid-column:1; font-size:.82rem; color:var(--ink); text-decoration:none; padding-right:.75rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }}
.gl:hover {{ color:var(--accent-2) }} .gl .mono {{ color:var(--muted); font-size:.72rem }}
.bar {{ height:.85rem; background:var(--bar); border-radius:3px; margin-inline:2px }}
.bar.prog {{ background:var(--prog) }}
.mlabel {{ font-weight:600; padding-top:.6rem; border-top:1px solid var(--line) }}
.ms {{ display:flex; flex-wrap:wrap; align-items:center; gap:.2rem .6rem; font-size:.72rem; padding-top:.6rem; border-top:1px solid var(--line); padding-left:.3rem }}
.ms > span {{ display:inline-flex; align-items:center; gap:.3rem }} .ms i {{ width:.6rem; height:.6rem; background:var(--accent); transform:rotate(45deg); display:inline-block }}
.legend {{ display:flex; flex-wrap:wrap; gap:1.2rem; font-size:.78rem; color:var(--muted); margin-top:.9rem }}
.legend span::before {{ content:""; display:inline-block; width:.9rem; height:.55rem; border-radius:2px; margin-right:.4rem; vertical-align:middle; background:var(--bar) }}
.legend .lp::before {{ background:var(--prog) }} .legend .lf::before {{ background:var(--freeze) }}
.legend .lm::before {{ width:.55rem; height:.55rem; background:var(--accent); transform:rotate(45deg); border-radius:0 }}
/* milestones */
ol.mil {{ list-style:none; margin:0; padding:0; display:grid; gap:.1rem }}
ol.mil li {{ display:grid; grid-template-columns:2.6rem 7.5rem 1fr; gap:.8rem; padding:.6rem 0; border-bottom:1px solid var(--line); align-items:baseline }}
ol.mil li:last-child {{ border-bottom:0 }}
ol.mil .mid {{ color:var(--accent); font-weight:600 }} ol.mil time {{ color:var(--muted); font-size:.85rem }}
ol.mil p {{ margin:.1rem 0 0; color:var(--muted); font-size:.88rem }}
/* tables */
table {{ width:100%; border-collapse:collapse; font-size:.86rem }}
th {{ text-align:left; font:600 .68rem var(--mono); letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:.5rem .6rem; border-bottom:1px solid var(--line); white-space:nowrap }}
td {{ padding:.6rem; border-bottom:1px solid var(--line); vertical-align:top }}
tbody tr:last-child td {{ border-bottom:0 }}
td a {{ color:var(--ink); text-decoration:none }} td a:hover b {{ color:var(--accent-2) }}
.num {{ text-align:right }} .nowrap {{ white-space:nowrap }}
.sub {{ color:var(--muted); margin:.2rem 0 0; font-size:.82rem; max-width:62ch }}
.sub2 {{ display:block; color:var(--muted); font-size:.72rem }}
.cur {{ margin:.3rem 0 0; font-size:.8rem; color:var(--warn) }}
.acc,.dep {{ margin:.3rem 0 0; font-size:.8rem }} .acc span,.dep span {{ font:600 .66rem var(--mono); letter-spacing:.06em; text-transform:uppercase; color:var(--accent-2); margin-right:.3rem }}
.dep span {{ color:var(--warn) }}
.chip {{ display:inline-block; font:600 .7rem var(--body); padding:.15rem .5rem; border-radius:999px; white-space:nowrap }}
.chip.todo {{ background:var(--todo-bg); color:var(--muted) }} .chip.prog {{ background:var(--warn-bg); color:var(--warn) }} .chip.done {{ background:var(--ok-bg); color:var(--ok) }}
.pri {{ font-size:.78rem; white-space:nowrap }} .pri.highest {{ font-weight:700 }} .pri.medium {{ color:var(--muted) }}
/* level 2 */
.tools {{ display:flex; flex-wrap:wrap; gap:.4rem; align-items:center; margin-bottom:1rem }}
.tools .lbl {{ font-size:.8rem; color:var(--muted); margin-right:.2rem }}
.fb,.tb {{ font:500 .8rem var(--body); background:var(--surface); color:var(--ink); border:1px solid var(--line); border-radius:999px; padding:.3rem .7rem; cursor:pointer }}
.fb .mono {{ color:var(--muted); font-size:.72rem }}
.fb[aria-pressed="true"] {{ background:var(--accent); color:var(--surface); border-color:var(--accent) }}
.fb[aria-pressed="true"] .mono {{ color:inherit; opacity:.8 }}
.tb {{ margin-left:auto }}
details.epic {{ background:var(--surface); border:1px solid var(--line); border-radius:10px; margin-bottom:.6rem }}
details.epic > summary {{ list-style:none; cursor:pointer; display:flex; flex-wrap:wrap; align-items:center; gap:.4rem .8rem; padding:.85rem 1.1rem }}
details.epic > summary::-webkit-details-marker {{ display:none }}
details.epic > summary::before {{ content:"›"; font-weight:700; color:var(--muted); transition:transform .15s }}
details.epic[open] > summary::before {{ transform:rotate(90deg) }}
.eid {{ color:var(--muted); font-size:.78rem }} .et {{ font-weight:700; flex:1 1 16rem; min-width:0 }} .em {{ color:var(--muted); font-size:.75rem }}
.eb {{ padding:0 1.1rem 1rem; border-top:1px solid var(--line) }}
.eb dl {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(14rem,1fr)); gap:.8rem 1.4rem; margin:1rem 0 }}
.eb dt {{ font:600 .66rem var(--mono); letter-spacing:.08em; text-transform:uppercase; color:var(--muted) }}
.eb dd {{ margin:.15rem 0 0; font-size:.86rem }}
table.st {{ min-width:46rem }}
tr.hide {{ display:none }}
.cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(18rem,1fr)); gap:1rem }}
.cols ul {{ margin:.2rem 0 0; padding-left:1.1rem; font-size:.88rem }} .cols li {{ margin:.25rem 0 }}
.cols h3 {{ font-size:.95rem; margin-bottom:.3rem }}
footer {{ color:var(--muted); font-size:.8rem }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none!important }} }}
@media (max-width:640px) {{ ol.mil li {{ grid-template-columns:2.4rem 1fr }} ol.mil li > div {{ grid-column:2 }} .tb {{ margin-left:0 }} }}
</style>
<div class="wrap">
<header>
  <p class="eyebrow">Delivery plan · prepared {dt.date(2026,10,9).strftime("%d %b %Y").lstrip("0")}</p>
  <h1>Agent One Finance with the FOBO (Helix) use case</h1>
  <p class="lede">Core Agent One Finance, integrated with the office Agent One, delivering FOBO break investigation for Product Control: a working version in UAT by the end of November and go-live in mid-January, across Dev, UAT and Prod.</p>
  <dl class="keys">
    <div><dt>Working version</dt><dd class="big">30 Nov 2026</dd></div>
    <div><dt>Go-live</dt><dd class="big">14 Jan 2027</dd></div>
    <div><dt>Scope</dt><dd>{len(EPICS)} epics · {len(stories)} stories · {tot_pts} pts</dd></div>
    <div><dt>Under way</dt><dd>{inprog} stories in progress</dd></div>
  </dl>
</header>

<section aria-labelledby="t-time">
  <h2 id="t-time">Timeline</h2>
  <div class="panel"><div class="tw"><div class="gantt">
    <div class="gh" style="grid-column:1;border-left:0"><b>Epic</b><span>Sprint dates</span></div>{head_cells}{rows}{mrow}
  </div></div>
  <div class="legend"><span>Planned</span><span class="lp">In progress now</span><span class="lf">Assumed change freeze (to confirm)</span><span class="lm">Milestone</span></div></div>
</section>

<section aria-labelledby="t-ms">
  <h2 id="t-ms">Milestones</h2>
  <div class="panel"><ol class="mil">{ms_items}</ol></div>
</section>

<section aria-labelledby="t-l1">
  <h2 id="t-l1">Level 1: epics</h2>
  <div class="panel tw"><table style="min-width:52rem"><thead><tr><th>ID</th><th>Epic</th><th>Team</th><th>Dates</th><th class="num">Stories</th><th class="num">Pts</th><th>Exit criteria</th><th>Status</th></tr></thead><tbody>{l1_rows}</tbody></table></div>
</section>

<section aria-labelledby="t-crit">
  <h2 id="t-crit">What the dates depend on</h2>
  <div class="cols">
    <div class="panel"><h3>Long-lead items to raise in S0</h3><ul>
      <li>UAT and Prod namespaces on Rhodium</li><li>Firewall rules to MB Rec, CATS, MOTIF and the LLM gateway</li>
      <li>Approved model and data classification for the LLM gateway</li><li>DPIA and AI / model risk assessment</li>
      <li>Penetration test slot; CAB dates and change-freeze window</li><li>MB Rec new tools and end-of-day event; hosting for Diagnostics outside AWS/BCP</li></ul></div>
    <div class="panel"><h3>Assumptions</h3><ul>
      <li>Team: 2 backend, 1 frontend (part-time), 1 DevOps, 1 QA, 1 BA, PM and architect; Product Control SME part-time</li>
      <li>Diagnostics has its own developer or agreed DevOps time (S1 and S2 are the heaviest sprints)</li>
      <li>Product Control available for configuration in S1–S2 and UAT in S4–S5</li>
      <li>Change freeze 24 Dec – 3 Jan, to be confirmed</li><li>Users are already provisioned and testing their skill in finance agent chat</li></ul></div>
    <div class="panel"><h3>Top risks</h3><ul>
      <li>Foundational build: Dev deployment is failing today (dependency in the image)</li>
      <li>MB Rec tool delivery slips: the dependent checks stay off; go-live is not blocked</li>
      <li>Approvals (model, DPIA, pen test, CAB) run late: each week late moves go-live by about a week</li>
      <li>Office console is a port of upstream screens: needs a manual check until it runs the upstream build</li></ul></div>
  </div>
</section>

<section aria-labelledby="t-l2">
  <h2 id="t-l2">Level 2: stories by epic</h2>
  <div class="tools" role="group" aria-label="Show stories for a sprint">
    <span class="lbl">Sprint</span><button type="button" class="fb" data-f="" id="f-all" aria-pressed="true">All <span class="mono">{tot_pts}</span></button>{filt}
    <button type="button" class="tb" id="toggle">Expand all</button>
  </div>
  {sections}
</section>

<footer>Story points per sprint are shown on the sprint buttons. The same plan is in AOF-FOBO-L1-plan.csv and AOF-FOBO-stories.csv (Jira import) beside this page.</footer>
</div>
<script>
(function () {{
  var btns = document.querySelectorAll(".fb"), epics = document.querySelectorAll("details.epic"), tog = document.getElementById("toggle");
  function apply(f) {{
    btns.forEach(function (b) {{ b.setAttribute("aria-pressed", String(b.dataset.f === f)); }});
    epics.forEach(function (ep) {{
      var shown = 0;
      ep.querySelectorAll("tbody tr").forEach(function (tr) {{ var on = !f || tr.dataset.spr === f; tr.classList.toggle("hide", !on); if (on) shown++; }});
      ep.hidden = f && !shown; if (f) ep.open = shown > 0;
    }});
    try {{ localStorage.setItem("aofplan.f", f); }} catch (e) {{}}
  }}
  btns.forEach(function (b) {{ b.addEventListener("click", function () {{ apply(b.dataset.f); }}); }});
  tog.addEventListener("click", function () {{
    var open = !Array.prototype.every.call(epics, function (x) {{ return x.hidden || x.open; }});
    epics.forEach(function (x) {{ if (!x.hidden) x.open = open; }}); tog.textContent = open ? "Collapse all" : "Expand all";
  }});
  var saved = ""; try {{ saved = localStorage.getItem("aofplan.f") || ""; }} catch (e) {{}}
  if (saved) apply(saved);
  if (location.hash) {{ var t = document.getElementById(location.hash.slice(1)); if (t && t.tagName === "DETAILS") t.open = true; }}
}})();
</script>
'''
open("aof-fobo-plan.artifact.html","w").write(page)
open("aof-fobo-plan.html","w").write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head>\n<body>\n'+page+'</body></html>\n')
print(len(page), "chars;", len(stories), "stories")
