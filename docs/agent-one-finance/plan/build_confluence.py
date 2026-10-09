"""Confluence pages for the delivery plan, from the same data as the HTML page
and the Jira import. Writes Markdown files to ./confluence: paste each into a
Confluence page (the editor converts Markdown on paste), or use the Markdown macro."""

import datetime as dt
import os
import runpy

HERE = os.path.dirname(os.path.abspath(__file__))
g = runpy.run_path(os.path.join(HERE, "plan_data.py" if os.path.exists(os.path.join(HERE, "plan_data.py")) else "gen.py"))
EPICS, MIL, SPR, SNAME, STORIES = g["EPICS"], g["MILESTONES"], g["SPR"], g["SNAME"], g["STORIES"]
DOR, DOD, RELEASES, COMPONENT, RELEASE_OF = g["DOR"], g["DOD"], g["RELEASES"], g["COMPONENT"], g["RELEASE_OF"]
EST, CUR = g["EPIC_STATUS"], g["CURRENT"]
OUT = os.path.join(os.getcwd(), "confluence")
os.makedirs(OUT, exist_ok=True)
TODAY = "9 Oct 2026"


def d(x):
    return dt.date.fromisoformat(x).strftime("%d %b %Y").lstrip("0")


def header(title, purpose):
    return (f"# {title}\n\n"
            f"| Owner | Status | Last updated | Purpose |\n|---|---|---|---|\n"
            f"| *(name)* | Draft | {TODAY} | {purpose} |\n\n")


def cell(t):
    return str(t).replace("|", "\\|").replace("\n", " ")


pages = {}

# 1. Project overview
p = header("Agent One Finance with the FOBO (Helix) use case: overview", "What we are delivering, for whom, and by when")
p += ("## Summary\n\nCore Agent One Finance, integrated with Agent One, investigates FOBO breaks from MB Rec for "
      "Product Control and posts approved adjustments to MOTIF through FAS. People decide every outcome; "
      "an adjustment is posted only after a reviewer approves it and a different person releases it.\n\n"
      "## Key dates\n\n| Date | What |\n|---|---|\n"
      + "".join(f"| {d(m[2])} | **{m[0]} {cell(m[1])}**: {cell(m[3])} |\n" for m in MIL)
      + "\nChange freeze: 11 Dec 2026 to 4 Jan 2027 (no Production changes).\n\n"
      "## Scope\n\n**In:** FOBO Prime and Rates on AOF; MB Rec and MOTIF data; approved adjustments posted to MOTIF "
      "through FAS; Agent One sessions per capability per case; Agent One Finance Diagnostics; UAT and Prod.\n\n"
      "**Out:** other use cases; CATS.\n\n"
      "## Epics\n\n| Jira | Epic | Team | Status |\n|---|---|---|---|\n"
      + "".join(f"| {e[0]} | {cell(e[1])} | {cell(e[3])} | {EST.get(e[0], 'To Do')} |\n" for e in EPICS)
      + "\n## Child pages\n\nDelivery plan · Ways of working · Requirements by epic · Decision log · RAID log\n")
pages["01-overview.md"] = p

# 2. Delivery plan
p = header("Delivery plan", "Sprints, milestones and epics; live dates come from Jira")
p += ("> Insert the Jira **Timeline** (or Advanced Roadmaps) macro here, filtered to this project, so dates stay live. "
      "The tables below are the baseline agreed on " + TODAY + ".\n\n"
      "## Sprints\n\n| Sprint | Start | End |\n|---|---|---|\n"
      + "".join(f"| {cell(SNAME[k])} | {d(a)} | {d(b)} |\n" for k, (a, b) in SPR.items())
      + "\n## Releases\n\n| Release | Date | Contains |\n|---|---|---|\n"
      + "".join(f"| {r[0]} | {d(r[1])} | {r[2]} |\n" for r in RELEASES)
      + "\n## Milestones\n\n| ID | Milestone | Date | Meaning |\n|---|---|---|---|\n"
      + "".join(f"| {m[0]} | {cell(m[1])} | {d(m[2])} | {cell(m[3])} |\n" for m in MIL)
      + "\n## Epics\n\n| Jira | Epic | From | To | Stories | Points | Exit criteria |\n|---|---|---|---|---|---|---|\n")
for e in EPICS:
    a, b = e[4].split("-")
    its = [s for s in STORIES if s["ep"] == e[0]]
    p += f"| {e[0]} | {cell(e[1])} | {d(SPR[a][0])} | {d(SPR[b][1])} | {len(its)} | {sum(s['pts'] for s in its)} | {cell(e[6])} |\n"
pages["02-delivery-plan.md"] = p

# 3. Ways of working
p = header("Ways of working", "How we write, size and finish stories")
p += ("## Story template\n\n**Title:** a short action (what gets done).\n\n"
      "**Description:** *As a* \\<role\\>, *I want* \\<goal\\>, *so that* \\<benefit\\>. Then the details.\n\n"
      "**Acceptance criteria:** Given \\<context\\>, when \\<action\\>, then \\<result\\>, for each behaviour to test; "
      "and one *Done when* line.\n\n"
      "## Definition of Ready\n\n" + "".join(f"- {x}\n" for x in DOR)
      + "\n## Definition of Done\n\n" + "".join(f"- {x}\n" for x in DOD)
      + "\n## Jira conventions\n\n"
      "- Issue types: Epic and Story; sub-tasks are added by the team at sprint planning.\n"
      "- Epics link stories through **Parent** (Jira Cloud) or **Epic Link** (Jira Data Center); the import file has both.\n"
      "- Story points on the Fibonacci scale (1, 2, 3, 5, 8); two-week sprints.\n"
      "- Releases (Fix Version): " + "; ".join(f"{r[0]} ({d(r[1])})" for r in RELEASES) + ".\n"
      "- Components: " + ", ".join(dict.fromkeys(COMPONENT.values())) + ".\n"
      "- Labels: AOF, FOBO; long-lead for requests with long lead times; diagnostics for the Diagnostics service.\n"
      "- Dependencies are *is blocked by* links between issues.\n"
      "- Priority: Highest, High, Medium.\n\n"
      "## Ceremonies\n\nSprint planning and review every two weeks; daily stand-up; fortnightly steerco; "
      "weekly working session with MB Rec.\n")
pages["03-ways-of-working.md"] = p

# 4. Requirements per epic
for e in EPICS:
    its = [s for s in STORIES if s["ep"] == e[0]]
    a, b = e[4].split("-")
    p = header(f"{e[0]} {e[1]}", "Requirements for this epic; one section per story")
    p += (f"| Jira epic | Component | Dates | Status |\n|---|---|---|---|\n"
          f"| {e[0]} | {COMPONENT[e[0]]} | {d(SPR[a][0])} to {d(SPR[b][1])} | {EST.get(e[0], 'To Do')} |\n\n"
          f"**Objective:** {e[2]}\n\n**Deliverables:** {e[5]}\n\n**Exit criteria:** {e[6]}\n\n**Dependencies:** {e[7]}\n\n"
          + (f"**Current state:** {CUR[e[0]]}\n\n" if e[0] in CUR else "")
          + "## Stories\n\n")
    for s in its:
        p += (f"### {s['id']} {s['summ']}\n\n{s['story']}\n\n{s['desc']}\n\n"
              f"| Sprint | Release | Points | Priority | Team | Environment | Status |\n|---|---|---|---|---|---|---|\n"
              f"| {cell(SNAME[s['spr']])} | {RELEASE_OF[s['spr']]} | {s['pts']} | {s['pri']} | {cell(s['team'])} | {s['env'] or '-'} | {s['st']} |\n\n"
              "**Acceptance criteria**\n\n" + "".join(f"- {x}\n" for x in s["gwt"]) + f"- Done when: {s['acc']}\n\n"
              + (f"**Blocked by:** {', '.join(s['blocked_ids'])}\n\n" if s["blocked_ids"] else ""))
    pages[f"04-requirements-{e[0]}.md"] = p

# 5. Decision log
DECISIONS = [
    ("D01", "Environments are UAT and Prod", "Agreed", "No separate Dev environment is set up for this delivery."),
    ("D02", "CATS is out of scope", "Agreed", "FOBO uses MB Rec and MOTIF data."),
    ("D03", "Adjustments are posted to MOTIF through FAS", "Agreed", "Only after a reviewer approves and a different person releases; each posted once; read back from MOTIF."),
    ("D04", "Agent One sessions per capability per case", "Agreed (design to sign)", "Not per user login; optionally per break group inside a case. Session runs with the case's rights."),
    ("D05", "Diagnostics hosted outside AWS/BCP", "Agreed (platform to confirm)", "Separate build and deployment from AOF."),
    ("D06", "Change freeze 11 Dec to 4 Jan", "Confirmed", "Prod built before the freeze; application released on 5 Jan."),
    ("D07", "Scope and go/no-go owned by the Business", "Agreed", "Sign-off by the Business (Product Control), Risk, Security and Operations."),
    ("D08", "Reviewer console approach", "Open", "Use the AOF reference console as built, or port to the existing Next.js console."),
]
p = header("Decision log", "Decisions taken and still open")
p += "| ID | Decision | Status | Notes | Date | Decided by |\n|---|---|---|---|---|---|\n"
p += "".join(f"| {x[0]} | {cell(x[1])} | {x[2]} | {cell(x[3])} | {TODAY} | *(name)* |\n" for x in DECISIONS)
pages["05-decision-log.md"] = p

# 6. RAID log
RAID = [
    ("R1", "Risk", "Prod not ready by 11 Dec", "High", "Raise platform and network requests in S0; track weekly", "DevOps"),
    ("R2", "Risk", "Posting to MOTIF through FAS needs controls sign-off and FAS access in UAT", "High", "Agree posting rules in S1; controls story in S3", "BA / Risk"),
    ("R3", "Risk", "Late approvals (model, DPIA, penetration test, CAB)", "High", "Start in S0; each week late moves go-live by about a week", "PM"),
    ("R4", "Risk", "MB Rec extra data arrives late", "Medium", "Extra checks stay off; go-live not blocked", "BA"),
    ("A1", "Assumption", "Product Control available for set-up in S1–S2 and UAT in S4–S5", "", "Confirm with the Business", "PM"),
    ("A2", "Assumption", "Users are already provisioned for interim skill testing", "", "", "PM"),
    ("I1", "Issue", "The build deployment is failing (missing package in the image)", "High", "Fix in progress", "DevOps"),
    ("D1", "Dependency", "MB Rec: extra data and end-of-day notification", "", "Weekly session; dates in plan", "PM"),
    ("D2", "Dependency", "FAS: test access in UAT and Prod connection", "", "Dates in plan", "PM"),
    ("D3", "Dependency", "Agent One team: session per capability per case", "", "Design agreed in S0", "Architect"),
]
p = header("RAID log", "Risks, assumptions, issues and dependencies")
p += "| ID | Type | Description | Rating | Action | Owner |\n|---|---|---|---|---|---|\n"
p += "".join(f"| {x[0]} | {x[1]} | {cell(x[2])} | {x[3]} | {cell(x[4])} | {x[5]} |\n" for x in RAID)
pages["06-raid-log.md"] = p

# index
p = ("# Confluence pages\n\nCreate a page tree in the project space and paste each file into a page of the same name. "
     "Confluence converts Markdown on paste; on Data Center, use the Markdown macro if paste does not convert.\n\n"
     "| File | Page |\n|---|---|\n"
     + "".join(f"| `{k}` | {v.splitlines()[0][2:]} |\n" for k, v in sorted(pages.items())))
pages["00-index.md"] = p

for k, v in pages.items():
    with open(os.path.join(OUT, k), "w") as f:
        f.write(v)
print(len(pages), "pages ->", OUT)
