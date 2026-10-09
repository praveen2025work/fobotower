import html, runpy, datetime as dt
g = runpy.run_path(__import__("os").path.join(__import__("os").path.dirname(__file__), "plan_data.py"))
EPICS, MIL, S, SPR, SNAME = g["EPICS"], g["MILESTONES"], g["S"], g["SPR"], g["SNAME"]
EST, CUR, SFOCUS, SSTATE, TODAY, FREEZE = g["EPIC_STATUS"], g["CURRENT"], g["SFOCUS"], g["SPRINT_STATE"], g["TODAY"], g["FREEZE"]
e = html.escape
order = list(SPR)
NOW = next(k for k, v in SSTATE.items() if v == "Now")
NEXT = order[order.index(NOW) + 1]
def d(x): return dt.date.fromisoformat(x)
def fmt(x): return d(x).strftime("%d %b").lstrip("0")
def fmty(x): return d(x).strftime("%d %b %Y").lstrip("0")

# stories with ids (same numbering as the CSV)
stories=g["STORIES"]
COMPONENT, RELEASE_OF, RELEASES, DOR, DOD = g["COMPONENT"], g["RELEASE_OF"], g["RELEASES"], g["DOR"], g["DOD"]
by_ep={x[0]:[s for s in stories if s["ep"]==x[0]] for x in EPICS}
tot_pts=sum(s["pts"] for s in stories)

# gantt: one column per week (two per sprint), so the freeze and today sit on the right days
W0 = d(SPR[order[0]][0])
nweeks = 2 * len(order)
def wk(x): return max(0, min(nweeks - 1, (d(x) - W0).days // 7))
gtc = "minmax(12rem,15rem) " + " ".join(["1fr"] * nweeks)
def scol(c): return 2 + 2 * order.index(c)

def chip(st):
    cls={"In Progress":"prog","To Do":"todo","Done":"done"}.get(st,"todo")
    return f'<span class="chip {cls}">{e(st)}</span>'

def sstate(c):
    st = SSTATE.get(c)
    return f'<em class="ss {st.lower()}">{e(st)}</em>' if st else ""

# every item has an explicit row, so the today line can overlap them
tw = wk(TODAY); tfrac = ((d(TODAY) - W0).days % 7) / 7 * 100
today_line = (f'<div class="today" style="grid-column:{2 + tw};grid-row:2 / span {len(EPICS) + 1}" aria-hidden="true">'
              f'<i style="left:{tfrac:.0f}%"></i></div>')
head_cells = "".join(
    f'<div class="gh{" now" if SSTATE.get(c) == "Now" else ""}{" done" if SSTATE.get(c) == "Done" else ""}" style="grid-column:{scol(c)} / span 2;grid-row:1">'
    f'<b>{e(c)} {sstate(c)}</b><span>{fmt(SPR[c][0])}–{fmt(SPR[c][1])}</span><span class="fo">{e(SFOCUS[c])}</span></div>' for c in order)
rows = ""
for r, ep in enumerate(EPICS, 2):
    a, b = ep[4].split("-"); st = EST.get(ep[0], "To Do")
    rows += (f'<a class="gl" href="#{ep[0]}" style="grid-row:{r}"><span class="mono">{ep[0]}</span> {e(ep[1])}</a>'
             f'<div class="bar {"prog" if st=="In Progress" else ""}" style="grid-column:{scol(a)} / {scol(b) + 2};grid-row:{r}" title="{e(ep[1])}: {fmty(SPR[a][0])} to {fmty(SPR[b][1])}"></div>')
FZROW, MSROW = len(EPICS) + 2, len(EPICS) + 3
rows += (f'<div class="gl mlabel" style="grid-row:{FZROW}">Change freeze</div><div class="fzbar" style="grid-column:{2 + wk(FREEZE[0])} / {3 + wk(FREEZE[1])};grid-row:{FZROW}" '
         f'title="No Production changes {fmty(FREEZE[0])} to {fmty(FREEZE[1])}"><span>{fmt(FREEZE[0])} – {fmt(FREEZE[1])}</span></div>')
mrow = f'<div class="gl mlabel" style="grid-row:{MSROW}">Milestones</div>'
grp = {}
for m in MIL: grp.setdefault(next(c for c in order if d(SPR[c][0]) <= d(m[2]) <= d(SPR[c][1])), []).append(m)
for c in order:
    ms = grp.get(c, [])
    mrow += f'<div class="ms" style="grid-column:{scol(c)} / span 2;grid-row:{MSROW}">' + "".join(f'<span title="{e(m[1])} ({fmty(m[2])})"><i></i><span class="mono">{m[0]}</span></span>' for m in ms) + '</div>'

sprint_rows = ""
for c in order:
    its = [x for x in stories if x["spr"] == c]
    sprint_rows += (f'<tr class="{"rnow" if SSTATE.get(c) == "Now" else ""}"><td class="mono nowrap">{e(SNAME[c])}</td><td class="mono nowrap">{fmt(SPR[c][0])} – {fmty(SPR[c][1])}</td>'
                    f'<td><b>{e(SFOCUS[c])}</b></td><td class="num mono">{len(its)}</td><td class="num mono">{sum(x["pts"] for x in its)}</td>'
                    f'<td>{sstate(c) or "<span class=sub>Planned</span>"}</td></tr>')

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
        f'<tr data-spr="{s["spr"]}" id="{s["id"]}"><td class="mono nowrap">{s["id"]}</td><td><b>{e(s["summ"])}</b>'
        f'<p class="us">{e(s["story"])}</p><p class="sub">{e(s["desc"])}</p>'
        + ('<ul class="gwt">'+"".join(f'<li>{e(x)}</li>' for x in s["gwt"])+'</ul>' if s["gwt"] else '')
        + f'<p class="acc"><span>Done when</span> {e(s["acc"])}</p>'
        + ('<p class="dep"><span>Blocked by</span> '+", ".join(f'<a href="#{i}" class="mono">{i}</a>' for i in s["blocked_ids"])+'</p>' if s["blocked_ids"] else '')
        + f'</td><td class="mono nowrap">{s["spr"]}<span class="sub2">{fmt(SPR[s["spr"]][0])}–{fmt(SPR[s["spr"]][1])}</span><span class="sub2">{e(RELEASE_OF[s["spr"]].split(" ")[0])}</span></td>'
        f'<td class="num mono">{s["pts"]}</td><td>{e(s["team"])}</td><td>{e(s["env"]) or "–"}</td>'
        f'<td><span class="pri {s["pri"].lower()}">{e(s["pri"])}</span></td><td>{chip(s["st"])}</td></tr>' for s in items)
    sections+=(f'<details class="epic" id="{ep[0]}"><summary><span class="mono eid">{ep[0]}</span><span class="et">{e(ep[1])}</span>'
               f'<span class="em mono">{fmt(SPR[a][0])} – {fmt(SPR[b][1])} · {len(items)} stories · {sum(s["pts"] for s in items)} pts</span>{chip(st)}</summary>'
               f'<div class="eb"><dl><div><dt>Objective</dt><dd>{e(ep[2])}</dd></div><div><dt>Deliverables</dt><dd>{e(ep[5])}</dd></div>'
               f'<div><dt>Exit criteria</dt><dd>{e(ep[6])}</dd></div><div><dt>Dependencies</dt><dd>{e(ep[7])}</dd></div><div><dt>Team</dt><dd>{e(ep[3])}</dd></div><div><dt>Jira component</dt><dd>{e(COMPONENT[ep[0]])}</dd></div></dl>'
               f'<div class="tw"><table class="st"><thead><tr><th>ID</th><th>Story</th><th>Sprint</th><th class="num">Pts</th><th>Team</th><th>Env</th><th>Priority</th><th>Status</th></tr></thead>'
               f'<tbody>{trs}</tbody></table></div></div></details>')

spr_pts={c:sum(s["pts"] for s in stories if s["spr"]==c) for c in order}
filt="".join(f'<button type="button" class="fb" data-f="{c}" id="f-{c}" title="{e(SNAME[c])}: {e(SFOCUS[c])}">{c}{" · now" if SSTATE.get(c)=="Now" else ""} <span class="mono">{spr_pts[c]}</span></button>' for c in order)
inprog=sum(1 for s in stories if s["st"]=="In Progress")
done=sum(1 for s in stories if s["st"]=="Done")

page=f'''<title>Agent One Finance Delivery Plan</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: one reading column; summary first (dates, gantt, milestones, level 1), level 2 stories below as one fold per epic */
:root {{
  --bg:#f6f8fb; --surface:#ffffff; --ink:#0d1b2e; --muted:#53627a; --line:#dde3ec;
  --accent:#00395d; --accent-2:#0076b6; --bar:#9fb7cf; --prog:#0076b6; --warn:#a85d00; --warn-bg:#fdf1e2;
  --ok:#1e7d4f; --ok-bg:#e5f4ec; --todo-bg:#eef1f5; --freeze:repeating-linear-gradient(135deg,#e4e9f0 0 6px,#f6f8fb 6px 12px); --now-bg:#fdf6ea;
  --display:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif; --body:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#0b1420; --surface:#111d2c; --ink:#e6edf6; --muted:#9aaabf; --line:#22334a;
  --accent:#8cc8f0; --accent-2:#5fb3e8; --bar:#3b5878; --prog:#3d9ad6; --warn:#f0b36a; --warn-bg:#3a2a14;
  --ok:#6fcf9b; --ok-bg:#163326; --todo-bg:#1a2838; --freeze:repeating-linear-gradient(135deg,#1a2838 0 6px,#0b1420 6px 12px); --now-bg:#2a2114; color-scheme:dark }} }}
:root[data-theme="dark"] {{
  --bg:#0b1420; --surface:#111d2c; --ink:#e6edf6; --muted:#9aaabf; --line:#22334a;
  --accent:#8cc8f0; --accent-2:#5fb3e8; --bar:#3b5878; --prog:#3d9ad6; --warn:#f0b36a; --warn-bg:#3a2a14;
  --ok:#6fcf9b; --ok-bg:#163326; --todo-bg:#1a2838; --freeze:repeating-linear-gradient(135deg,#1a2838 0 6px,#0b1420 6px 12px); --now-bg:#2a2114; color-scheme:dark }}
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
.gantt {{ display:grid; grid-template-columns:{gtc}; row-gap:.35rem; column-gap:0; min-width:60rem; align-items:center }}
.gh {{ font-size:.72rem; color:var(--muted); padding:0 .35rem .5rem; border-left:1px solid var(--line); display:grid; line-height:1.3 }}
.gh b {{ color:var(--ink); font:600 .75rem var(--mono) }}
.gh .fo {{ color:var(--muted) }}
.gh.now {{ background:var(--now-bg); border-radius:4px 4px 0 0 }} .gh.done b {{ color:var(--muted) }}
.ss {{ font:600 .62rem var(--body); font-style:normal; padding:.05rem .35rem; border-radius:999px; margin-left:.2rem }}
.ss.done {{ background:var(--ok-bg); color:var(--ok) }} .ss.now {{ background:var(--warn-bg); color:var(--warn) }}
.fzbar {{ height:1.1rem; background:var(--freeze); border-radius:3px; margin-inline:2px; font-size:.68rem; color:var(--muted); display:flex; align-items:center; padding-left:.35rem; white-space:nowrap; overflow:hidden }}
.today {{ position:relative; pointer-events:none; align-self:stretch }}
.today i {{ position:absolute; top:-.2rem; bottom:-.2rem; border-left:2px dashed var(--warn) }}
tr.rnow td {{ background:var(--now-bg) }}
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
.legend .lt::before {{ width:0; height:.8rem; border-left:2px dashed var(--warn); background:none; border-radius:0 }}
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
.us {{ margin:.25rem 0 0; font-style:italic; max-width:70ch }}
ul.gwt {{ margin:.35rem 0 0; padding-left:1.1rem; font-size:.8rem; color:var(--ink) }} ul.gwt li {{ margin:.1rem 0 }}
.dep a {{ color:var(--accent-2); text-decoration:none }}
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
  <p class="lede">Core Agent One Finance, integrated with Agent One, investigating FOBO breaks from MB Rec for the FOBO controllers, who run the use case and test it, and posting approved adjustments to MOTIF through FAS. Two-week sprints: Sprint 1 built Diagnostics, Sprint 2 is putting the AOF skeleton on AWS, and Sprint 3 starts on 20 Oct. A working version in UAT by 30 Nov; go-live on 14 Jan.</p>
  <dl class="keys">
    <div><dt>Working version</dt><dd class="big">30 Nov 2026</dd></div>
    <div><dt>Go-live</dt><dd class="big">14 Jan 2027</dd></div>
    <div><dt>Now</dt><dd>{e(SNAME[NOW])} · {fmt(SPR[NOW][0])}–{fmt(SPR[NOW][1])}</dd></div>
    <div><dt>Next</dt><dd>{e(SNAME[NEXT])} from {fmt(SPR[NEXT][0])}</dd></div>
    <div><dt>Scope</dt><dd>{len(EPICS)} epics · {len(stories)} stories · {tot_pts} pts</dd></div>
    <div><dt>Progress</dt><dd>{done} done · {inprog} in progress</dd></div>
  </dl>
</header>

<section aria-labelledby="t-time">
  <h2 id="t-time">Timeline</h2>
  <div class="panel"><div class="tw"><div class="gantt">
    <div class="gh" style="grid-column:1;grid-row:1;border-left:0"><b>Epic</b><span>Sprint dates</span></div>{today_line}{head_cells}{rows}{mrow}
  </div></div>
  <div class="legend"><span>Planned</span><span class="lp">In progress now</span><span class="lf">Change freeze 11 Dec – 4 Jan: no Production changes</span><span class="lt">Today ({fmt(TODAY)})</span><span class="lm">Milestone</span></div></div>
</section>

<section aria-labelledby="t-spr">
  <h2 id="t-spr">Sprints</h2>
  <div class="panel tw"><table style="min-width:40rem"><thead><tr><th>Sprint</th><th>Dates</th><th>Focus</th><th class="num">Stories</th><th class="num">Pts</th><th>State</th></tr></thead><tbody>{sprint_rows}</tbody></table></div>
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
    <div class="panel"><h3>Raise these now (long lead)</h3><ul>
      <li>Prod platform request (Prod needed by 10 Dec)</li>
      <li>Network access to MB Rec, MOTIF, FAS and the LLM gateway</li>
      <li>Model and data approval for the LLM gateway</li>
      <li>Governance forum dates: TAC, ARB, CAF, CDO, DAIP and CARA (one governance lead)</li>
      <li>DPIA, AI risk assessment and penetration test slot</li>
      <li>MB Rec extra data and end-of-day trigger; FAS test access</li>
      <li>Diagnostics hosting outside AWS/BCP</li></ul></div>
    <div class="panel"><h3>Assumptions</h3><ul>
      <li>Team: 2 backend, 1 DevOps, 1 QA, 1 BA, a governance lead, PM and architect; frontend part-time</li>
      <li>Named FOBO controllers available for set-up in Sprints 3–4, UAT in Sprints 6–7 and the parallel run in Sprint 8</li>
      <li>Change freeze 11 Dec – 4 Jan: Prod built by 10 Dec, released on 5 Jan</li>
      <li>Sprint 7 runs over the holidays at reduced capacity</li>
      <li>Users are already provisioned and testing their skill in finance agent chat</li></ul></div>
    <div class="panel"><h3>Top risks</h3><ul>
      <li>Prod not ready by 10 Dec: platform and network requests are the critical path</li>
      <li>AOF orchestrator deployment on AWS finishes in Sprint 2; the database migration history is settled in Sprint 3</li>
      <li>Posting adjustments to MOTIF through FAS needs controls sign-off and FAS access in UAT</li>
      <li>Late approvals (TAC, ARB, CAF, CDO, DAIP, CARA, DPIA, CAB) rest on one governance lead: each week late moves go-live by about a week</li>
      <li>FOBO controllers' time for set-up, UAT and the parallel run not protected</li></ul></div>
  </div>
</section>

<section aria-labelledby="t-ww">
  <h2 id="t-ww">Ways of working</h2>
  <div class="cols">
    <div class="panel"><h3>Definition of Ready</h3><ul>{''.join(f"<li>{e(x)}</li>" for x in DOR)}</ul></div>
    <div class="panel"><h3>Definition of Done</h3><ul>{''.join(f"<li>{e(x)}</li>" for x in DOD)}</ul></div>
    <div class="panel"><h3>Jira conventions</h3><ul>
      <li>Stories are written as user stories with acceptance criteria; Given / When / Then where there is behaviour to test</li>
      <li>Releases: {''.join(f"<b>{e(r[0])}</b> ({fmty(r[1])}) " for r in RELEASES)}</li>
      <li>Components: {e(", ".join(dict.fromkeys(COMPONENT.values())))}</li>
      <li>Dependencies are “is blocked by” links between stories</li>
      <li>Points on the Fibonacci scale (1, 2, 3, 5, 8); two-week sprints</li></ul></div>
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
  function reveal(id) {{ var t = document.getElementById(id); if (!t) return; var d = t.tagName === "DETAILS" ? t : t.closest("details"); if (d) {{ d.hidden = false; d.open = true; }} if (t.tagName === "TR") {{ t.classList.remove("hide"); t.scrollIntoView({{ block: "center" }}); }} }}
  if (location.hash) reveal(location.hash.slice(1));
  document.querySelectorAll('.dep a').forEach(function (a) {{ a.addEventListener("click", function () {{ reveal(a.getAttribute("href").slice(1)); }}); }});
}})();
</script>
'''
open("aof-fobo-plan.artifact.html","w").write(page)
open("aof-fobo-plan.html","w").write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head>\n<body>\n'+page+'</body></html>\n')
print(len(page), "chars;", len(stories), "stories")
