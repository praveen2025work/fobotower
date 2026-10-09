import csv
# Two-week sprints, Tuesday to Monday. Sprint 1 is done, Sprint 2 is under way, Sprint 3 starts 20 Oct.
SPR = {  # sprint: (start, end)
 "S1": ("2026-09-22","2026-10-05"), "S2": ("2026-10-06","2026-10-19"), "S3": ("2026-10-20","2026-11-02"),
 "S4": ("2026-11-03","2026-11-16"), "S5": ("2026-11-17","2026-11-30"), "S6": ("2026-12-01","2026-12-14"),
 "S7": ("2026-12-15","2026-12-28"), "S8": ("2026-12-29","2027-01-11"), "S9": ("2027-01-12","2027-01-25")}
SNAME = {k: f"Sprint {k[1:]}" for k in SPR}  # the Jira sprint names
SFOCUS = {"S1":"Diagnostics","S2":"AOF skeleton on AWS","S3":"Connections and sessions","S4":"FOBO Prime end to end",
          "S5":"Working version","S6":"UAT 1 and Prod ready","S7":"UAT 2 and sign-offs","S8":"Release and parallel run",
          "S9":"Go-live"}
SPRINT_STATE = {"S1": "Done", "S2": "Now"}
TODAY = "2026-10-09"
FREEZE = ("2026-12-11", "2027-01-04")

EPICS = [
 # id, name, objective, team, (span from stories), deliverables, exit criteria, dependencies
 ("E01","Programme and governance","Plan, scope, approvals and reporting","PM / Architect","",
  "Jira and sprint calendar, scope, architecture review, success and go/no-go criteria, CAB date","Steerco agrees scope, plan and go-live criteria","Change freeze 11 Dec to 4 Jan; CAB calendar"),
 ("E02","AOF platform on AWS: skeleton, UAT and Prod","The AOF orchestrator, its database and the reviewer console running on AWS, deployed through the pipeline to UAT and Prod","DevOps / Backend","",
  "AOF database (Postgres with pgvector), AOF orchestrator service, console at /agentone/finance, one way to take each AOF release, pipeline with tests and scans, UAT, Prod before the freeze","The same build runs in UAT and Prod; Prod ready by 10 Dec","Platform and network requests approved"),
 ("E03","Agent One integration: sessions per capability per case","Agent One sessions are opened per capability per case (and per break group where needed), instead of per user login","Backend","",
  "Session design, per-case sessions in Agent One, case identity and data scope, session lifecycle, model approval, tracing, cost limits","Each FOBO case has its own Agent One session, shared by everyone working the case; no session per login","Model and data approval; Agent One team"),
 ("E04","Data connections: MB Rec, MOTIF and FAS","Read breaks from MB Rec and bookings from MOTIF; post approved adjustments to MOTIF through FAS","Backend / DevOps","",
  "MB Rec and MOTIF connections, MB Rec end-of-day trigger, FAS posting of approved adjustments, user roles, Prod connections","Breaks load from MB Rec; an approved adjustment posts to MOTIF through FAS in UAT","MB Rec, MOTIF and FAS teams; network rules"),
 ("E05","FOBO (Helix) set-up with Product Control","FOBO Prime and Rates configured and confirmed by Product Control","BA / Product Control","",
  "Thresholds, checks and verdicts, sign-off checklist, owners, which verdicts post adjustments","Product Control confirms the set-up","Product Control time; MB Rec data"),
 ("E06","Agent One Finance Diagnostics","Diagnostics service reading Phoenix traces, hosted outside AWS/BCP, improved each sprint","Backend / DevOps","",
  "Diagnostics core, hosting outside AWS/BCP, its own pipeline, UAT and Prod deployments, quality check against Phoenix, improvements","Running in Prod; results match Phoenix","Hosting outside AWS/BCP; Phoenix read access"),
 ("E07","Security, risk and controls","All approvals for an AI system that reads finance data and posts adjustments","Architect / Risk","",
  "DPIA, AI risk assessment, posting controls, security scans, penetration test, access review","All approvals in place before the CAB request","Risk and security teams"),
 ("E08","Testing and parity","Proof it works for Product Control at real volumes, and matches today's FOBO","QA / Product Control","",
  "Test plan, integration testing, parity check, performance test, UAT cycles 1 and 2","UAT signed off; parity accepted; no open Sev1/Sev2","UAT environment and data"),
 ("E09","Business engagement and showcase","MB Rec and BA engaged; users' feedback used; working version shown on 30 Nov","PM / BA","",
  "MB Rec working sessions and dates, BA requirements and UAT scenarios, interim skill-testing feedback, showcase, training","Showcase held 30 Nov; reviewers trained before go-live","MB Rec and BA availability"),
 ("E10","Go-live and support","Safe release on 5 Jan and go-live on 14 Jan","DevOps / PM","",
  "Runbook, support model, CAB, Prod release, monitoring, parallel run, go/no-go","Live on 14 Jan with no open Sev1/Sev2; support in place","CAB approval"),
]

MILESTONES = [
 ("M1","Diagnostics first version","2026-10-05","About 70% of Diagnostics built in Sprint 1; improvements and deployment continue"),
 ("M2","AOF skeleton on AWS","2026-10-19","Orchestrator service, database and console at /agentone/finance running together on AWS"),
 ("M3","FOBO Prime end to end in UAT","2026-11-16","Real MB Rec breaks investigated in their own Agent One session; MOTIF connected; FAS posting tested"),
 ("M4","Working version showcase","2026-11-30","FOBO Prime and Rates on AOF in UAT, shown end to end with Diagnostics"),
 ("M5","Prod ready before the freeze","2026-12-10","Prod environment and connections in place; no application deployed yet"),
 ("M6","UAT, security and parity sign-off; CAB submitted","2026-12-18","UAT signed, penetration test closed, parity accepted, CAB request in for 5 Jan"),
 ("M7","Released to Prod; parallel run","2027-01-06","Released 5 Jan after the freeze; parallel run with today's process from 6 Jan"),
 ("M8","Go-live","2027-01-14","Product Control uses AOF for FOBO Prime and Rates"),
]

# epic, summary, description, done when, priority, points, sprint, team, environment, depends on, [status]
S = [
 # E01 Programme and governance
 ("E01","Set up Jira, sprint calendar and weekly status","Load this plan into Jira; two-week sprints, Sprint 3 from 20 Oct; weekly status to stakeholders.","Board live; first status sent","High",1,"S2","PM","","","In Progress"),
 ("E01","Agree scope with the Business","In: FOBO Prime and Rates on AOF, MB Rec and MOTIF data, approved adjustments posted to MOTIF through FAS, Diagnostics. Out: other use cases.","Scope signed by the Business","Highest",2,"S2","PM","","","In Progress"),
 ("E01","Confirm the CAB deadline for a 5 Jan release","Change freeze confirmed: 11 Dec to 4 Jan.","CAB deadline in the plan","Highest",1,"S2","PM","","","In Progress"),
 ("E01","RAID log and fortnightly steerco","Risks, assumptions, issues and dependencies tracked weekly.","RAID log live","High",1,"S3","PM","",""),
 ("E01","Architecture review (ARB)","Present the architecture and controls; record conditions.","ARB approval; conditions added as stories","Highest",3,"S3","Architect","",""),
 ("E01","Agree success and go/no-go criteria","For example: agreement with reviewers, no unverified figures, hours saved, no open Sev1/Sev2.","Criteria agreed","High",2,"S3","PM / BA","",""),
 ("E01","Go/no-go sign-off list","Who signs: the Business (Product Control), Risk, Security, Operations.","List agreed","High",1,"S6","PM","",""),
 # E02 AOF platform on AWS
 ("E02","Set up the AOF database on AWS (Postgres with pgvector)","The AOF database with the pgvector extension.","Database reachable from the AOF service; pgvector enabled","Highest",3,"S2","DevOps","UAT","","Done"),
 ("E02","Deploy the AOF orchestrator service to AWS","Its own ECS service from the AOF image (port 8300), health check, database settings from the secrets store. The missing-package failure in the image is fixed.","Service healthy on AWS; health check and sign-in check answer","Highest",5,"S2","DevOps / Backend","UAT","","In Progress"),
 ("E02","AOF skeleton end to end on AWS","The console at /agentone/finance, the AOF service and the database working together; a sample case runs on test data.","A sample case opens, runs and is reviewed on AWS","Highest",3,"S2","Backend / Frontend","UAT","","In Progress"),
 ("E02","Request the Prod platform (long lead)","UAT runs on AWS today. Raise the Prod request now; Prod must be ready by 10 Dec.","Approved with dates","Highest",1,"S2","DevOps","Prod",""),
 ("E02","Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)","Firewall rules for UAT and Prod.","Rules approved","Highest",2,"S2","DevOps","UAT/Prod",""),
 ("E02","Settle the AOF database migrations","Line up the AWS database with AOF's migration history, then run migrations before every deployment.","One migration head; migrations run in the pipeline","Highest",2,"S3","Backend / DevOps","UAT",""),
 ("E02","Take each AOF release the same way (sync tool)","Replace the hand-converted console and backend with the generated release and the sync tool. Our own changes (sign-on, connections) are kept on every update.","Console at /agentone/finance on the latest release, with its styles and icons; an update is one sync run","Highest",3,"S3","Frontend / Backend","UAT",""),
 ("E02","Build pipeline with tests and security scans","Every change is built, tested and scanned before it can be deployed.","Pipeline green; a failing test stops the release","Highest",5,"S3","DevOps","",""),
 ("E02","Complete the UAT environment","Single sign-on, secrets, web address and connections for the AOF service and console.","Release deployed to UAT by the pipeline; a reviewer signs in","Highest",3,"S3","DevOps","UAT",""),
 ("E02","Deploy the reviewer console to UAT","The screens reviewers use, at /agentone/finance behind single sign-on.","Reviewers open the console in UAT","Highest",2,"S3","DevOps / Frontend","UAT",""),
 ("E02","Promote releases from UAT to Prod through the pipeline","Same build, approval gate before Prod.","Approval gate works","High",3,"S4","DevOps","UAT/Prod",""),
 ("E02","Build the Prod environment before the freeze","Database, secrets, single sign-on, web address; ready by 10 Dec. The application is released after the freeze.","Prod smoke test passes","Highest",5,"S6","DevOps","Prod",""),
 ("E02","Backups and restore tested","Database backups and a tested restore.","Restore tested","High",3,"S6","DevOps","UAT/Prod",""),
 # E03 Agent One integration
 ("E03","Confirm the approved model and data rules (long lead)","Which model, which data may be sent to it, and what is masked.","Written approval","Highest",2,"S2","Architect / Risk","",""),
 ("E03","Agree the session design with the Agent One team","Today Agent One opens a session per user login. Target: one session per capability per case (for example one per FOBO book and date), optionally one per break group inside the case. Agree the session key, who it runs as, how long it lives and what is kept.","Design signed by the Agent One team and Architect","Highest",2,"S3","Architect / Backend","",""),
 ("E03","Open an Agent One session per capability per case","When a case opens (by MB Rec's end-of-day trigger or by a person), AOF opens one Agent One session for that capability and case. Logging in no longer creates a session.","Two people on the same case use the same session; two cases never share one; no session per login","Highest",5,"S4","Backend","UAT","Session design"),
 ("E03","Session runs with the case's rights, not the user's","The session uses the case's own identity and book scope (a service identity for cases opened automatically), so it only reads that case's books.","A session cannot read another book; refusals are audited","Highest",3,"S4","Backend","UAT",""),
 ("E03","Trace every model and system call by case","Each case's session can be traced end to end by its case number.","Trace found by case number","High",3,"S4","Backend / DevOps","UAT",""),
 ("E03","Session per break group (where needed)","Large cases can use one session per break group so groups are investigated in parallel, still under the same case.","Groups of one case run in parallel in UAT","Medium",3,"S5","Backend","UAT",""),
 ("E03","Session lifecycle: resume, close and keep the record","A session resumes if a case is re-run or the service restarts, closes when the case is signed off, and its record stays with the case for audit.","Resume and close shown in UAT; record kept on the case","High",3,"S5","Backend","UAT",""),
 ("E03","Cost limits and off switches per capability and case","Daily and per-case limits; FOBO and each connection can be switched off.","Over limit goes to a person; switch-off tested","High",2,"S5","Backend","UAT",""),
 ("E03","Run the FOBO skill in the case's session","The controllers' skill runs end to end in the case's session, as an option to the step-by-step set-up.","One case runs in UAT","Medium",3,"S5","Backend","UAT",""),
 ("E03","Real-model evaluation on decided cases","Replay cases people decided and compare.","Agreement recorded; differences reviewed","High",3,"S5","Backend / BA","UAT",""),
 # E04 Data connections
 ("E04","MB Rec: request the extra data the checks need (long lead)","Book status, history by book, and breaks across books.","MB Rec gives delivery dates","Highest",1,"S2","BA","",""),
 ("E04","MB Rec: read breaks and break history","Read-only connection.","Real breaks load into a case in UAT","Highest",5,"S3","Backend","UAT","Network access"),
 ("E04","FAS: agree posting rules with Product Control and MOTIF","Which adjustments are posted, accounts and booking fields, limits, who releases.","Posting rules signed","Highest",2,"S3","BA / Product Control","",""),
 ("E04","Give provisioned users their AOF roles and books","Users are already provisioned; set who reviews, who releases and which books each sees.","Users see only their books","Highest",3,"S3","Backend","UAT",""),
 ("E04","MB Rec: end-of-day notification opens a case","When MB Rec finishes a book, AOF opens the case; late breaks open a follow-up.","Case opens automatically in UAT","High",3,"S4","Backend / MB Rec","UAT",""),
 ("E04","MOTIF: read trades, positions and booking events","Read-only connection.","MOTIF data available in UAT","Highest",5,"S4","Backend","UAT","Network access"),
 ("E04","FAS: post approved adjustments to MOTIF","Connect the FAS service. Only adjustments approved by a reviewer and released by a second person are posted; each is posted once.","Approved adjustment posted to MOTIF in UAT; a second post is refused; audit shows who approved and released","Highest",8,"S4","Backend","UAT","Posting rules; FAS test access"),
 ("E04","FAS: confirm each posted adjustment in MOTIF","Read back from MOTIF that the adjustment landed; flag any that did not.","Every UAT posting confirmed","High",3,"S5","Backend","UAT",""),
 ("E04","Connections in Prod before the freeze","MB Rec, MOTIF and FAS reachable from Prod by 10 Dec.","All connections up in Prod","Highest",3,"S6","DevOps","Prod",""),
 # E05 FOBO set-up
 ("E05","Confirm thresholds and parameters with Product Control","Materiality, tolerances, ageing.","Values signed","Highest",3,"S3","BA / Product Control","",""),
 ("E05","Set up FOBO Prime","Books, reviewers, owners.","A Prime case runs end to end in UAT","Highest",5,"S4","BA / Backend","UAT",""),
 ("E05","Review checks, categories and verdicts with Product Control","Each check, the verdict table and its guards.","Product Control confirms or changes each one","Highest",5,"S4","BA / Product Control","",""),
 ("E05","Sign-off checklist and reviewer answers","What a reviewer must confirm before approving.","Reviewer completes the checklist in UAT","High",2,"S4","BA","UAT",""),
 ("E05","Set up FOBO Rates","As Prime, for Rates books.","A Rates case runs end to end in UAT","High",5,"S5","BA / Backend","UAT",""),
 ("E05","Which verdicts post an adjustment, and who releases it","Link the verdicts to FAS posting; set the releasing role.","Shown working in UAT","Highest",2,"S5","BA / Product Control","UAT",""),
 ("E05","Owners and escalation routes","Who owns each category; who is asked for evidence.","Questions and escalations reach the right people","High",2,"S5","BA","UAT",""),
 ("E05","Turn on extra checks when MB Rec's new data arrives","History, systemic and trend checks.","Checks run in UAT","Medium",2,"S5","Backend","UAT","MB Rec extra data"),
 ("E05","Next-day follow-up and late breaks","Re-check decisions on the next business day; late breaks get their own case.","Shown in UAT","Medium",2,"S5","Backend / QA","UAT",""),
 # E06 Diagnostics
 ("E06","Build the Diagnostics core (Phoenix scraper)","Reads Phoenix traces and shows agent runs, model calls, errors and cost. About 70% of the planned Diagnostics was built in Sprint 1.","Core running on test traces","Highest",8,"S1","Backend","","","Done"),
 ("E06","Confirm hosting outside AWS/BCP","Agree the platform and its approvals.","Hosting approved","Highest",2,"S2","Architect / DevOps","","","In Progress"),
 ("E06","Diagnostics: finish the remaining 30%","The items still open after Sprint 1, in priority order.","Agreed items done","Highest",5,"S2","Backend","","","In Progress"),
 ("E06","Own build pipeline and read-only Phoenix access","Separate from the AOF build; read-only account; secrets stored safely.","Pipeline green; Phoenix readable","High",3,"S2","DevOps","","","In Progress"),
 ("E06","Deploy Diagnostics to UAT","Outside AWS/BCP.","Runs on schedule in UAT","Highest",3,"S3","DevOps","UAT","Hosting approved"),
 ("E06","Quality check: results match Phoenix","Compare counts, timings, errors and costs with Phoenix for sample cases.","Reconciliation report; defects logged","Highest",3,"S3","Backend / QA","",""),
 ("E06","Tests, data checks and security review","Automated checks; confirm finance data in traces is masked.","Checks run; review signed","High",3,"S4","Backend / Risk","",""),
 ("E06","Diagnostics views for the showcase","Run health, model calls, cost per case.","Shown on 30 Nov","High",2,"S5","Backend","UAT",""),
 ("E06","Improvements from the quality review and UAT feedback","Next items from the priority list.","Agreed items done","Medium",3,"S6","Backend","UAT",""),
 ("E06","Deploy Diagnostics to Prod","After the freeze, in the same release window.","Runs in Prod; results match Phoenix","Highest",2,"S8","DevOps","Prod","CAB approval"),
 # E07 Security, risk and controls
 ("E07","DPIA and data classification","Data flows, what the model sees, masking, retention.","DPIA approved","Highest",5,"S3","Architect / Risk","",""),
 ("E07","AI and model risk assessment","People decide every outcome; evaluations; off switches; audit trail.","Risk acceptance recorded","Highest",5,"S3","Architect / Risk","",""),
 ("E07","Protect the model from instructions hidden in data","Text from source systems is treated as data, never as instructions.","Test cases with hidden instructions go to a person","Highest",3,"S4","Backend","UAT",""),
 ("E07","Security scans clean","Code and dependency scans.","No open high or critical findings","Highest",2,"S4","DevOps / Backend","",""),
 ("E07","Controls for posting adjustments","Reviewer approval, release by a different person, limits, posted once, full audit.","Signed by Risk and Product Control","Highest",3,"S5","Risk / BA","",""),
 ("E07","Audit trail cannot be changed","Confirm database controls, or add protection.","Evidence recorded","High",3,"S5","Architect / Backend","",""),
 ("E07","Penetration test on UAT","Book the slot in Sprint 3; run it in Sprint 6; fix findings.","No open high findings","Highest",3,"S6","Security","UAT",""),
 ("E07","Access and segregation-of-duties review","Reviewers, releasers, owners.","Review signed","High",2,"S6","Risk / BA","UAT",""),
 # E08 Testing and parity
 ("E08","Test plan","Functional, integration, refusals, limits, posting.","Plan approved","High",3,"S4","QA","",""),
 ("E08","Integration testing in UAT","End to end: MB Rec to AOF to review to FAS posting.","No open Sev1/Sev2","Highest",5,"S5","QA","UAT",""),
 ("E08","Parity check against today's FOBO","Same books and dates through today's FOBO and AOF.","Parity report for Prime and Rates","Highest",5,"S5","QA / Backend","UAT",""),
 ("E08","Agree and sign off the differences","Every difference explained; Product Control accepts or it is fixed.","Signed list","Highest",3,"S6","BA / Product Control","",""),
 ("E08","Performance test at end-of-day volumes","All books at once, model response times.","Cases ready by the agreed time","High",5,"S6","QA / Backend","UAT",""),
 ("E08","Evaluation set and agreement threshold","Decided UAT cases replayed after each change.","At or above the agreed threshold","High",3,"S6","Backend / BA","UAT",""),
 ("E08","UAT cycle 1 with Product Control","Real cases reviewed; defects triaged.","Cycle 1 report","Highest",5,"S6","Product Control / QA","UAT",""),
 ("E08","UAT cycle 2 and sign-off","Retest fixes; sign-off.","UAT signed off","Highest",5,"S7","Product Control / QA","UAT",""),
 # E09 Business engagement and showcase
 ("E09","MB Rec: contacts, responsibilities and a weekly session","Who owns the connection, the end-of-day trigger and the extra data.","Weekly session running","Highest",1,"S2","PM","","","In Progress"),
 ("E09","Assign and onboard the BA","Owns requirements, Product Control sessions and UAT scenarios.","BA in place","Highest",1,"S2","PM","","","In Progress"),
 ("E09","Interim skill testing: weekly feedback","Users already test their skill in finance agent chat; collect findings each week.","Weekly feedback log","High",1,"S2","BA","","","In Progress"),
 ("E09","MB Rec: walk through the data needed","Fields each check reads; gaps.","MB Rec confirms","Highest",2,"S3","BA / MB Rec","",""),
 ("E09","Delivery dates from MB Rec, MOTIF and FAS","Dates for extra data, end-of-day trigger and FAS posting in UAT and Prod.","Dates in the plan, tracked weekly","Highest",1,"S3","PM","",""),
 ("E09","BA: today's FOBO process and requirements","Map the current investigation and sign-off.","Signed by Product Control","Highest",3,"S3","BA","",""),
 ("E09","BA: UAT scenarios","By category and verdict, including late breaks and postings.","Scenarios signed","High",3,"S4","BA","",""),
 ("E09","Use skill-testing feedback to improve the checks","Update the skill and checks; re-run the evaluation.","Changes approved","High",3,"S4","BA / Backend","UAT",""),
 ("E09","Showcase on 30 Nov","Script, data, rehearsal on 27 Nov: MB Rec breaks to review to posting, plus Diagnostics.","Showcase held; feedback logged","Highest",3,"S5","PM / BA","UAT",""),
 ("E09","Reviewer training and guide","Product Control reviewers, releasers and support.","All go-live users trained","High",3,"S7","BA","UAT",""),
 # E10 Go-live and support
 ("E10","Runbook and rollback plan","Release, checks, rollback, what to do if a connection or the model is down.","Reviewed by Operations","Highest",3,"S7","DevOps / Backend","Prod",""),
 ("E10","Support model","Who answers what, and on-call.","Signed; support from go-live","Highest",2,"S7","PM / Operations","Prod",""),
 ("E10","CAB request for 5 Jan","With UAT, security, risk and runbook evidence; submitted by 18 Dec.","CAB approved","Highest",2,"S7","PM","Prod","Sign-offs"),
 ("E10","Release to Prod on 5 Jan and smoke test","First working day after the freeze; no business use yet.","Smoke test passes","Highest",2,"S8","DevOps","Prod","CAB approval"),
 ("E10","Monitoring and alerts in Prod","Health, connection down, spend limit, failed postings.","Alerts reach on-call in a test","Highest",3,"S8","DevOps","Prod",""),
 ("E10","Parallel run with today's process","Product Control works both ways on agreed books from 6 to 12 Jan.","Parallel-run report","Highest",3,"S8","Product Control / BA","Prod",""),
 ("E10","Go/no-go and go-live","Go/no-go 13 Jan; live 14 Jan.","Go decision recorded","Highest",1,"S9","PM","Prod",""),
 ("E10","Go-live communications and benefits tracking","What changes for users; hours saved and agreement reported.","Comms sent; first benefits report","Medium",2,"S9","PM / BA","",""),
]

ORDER=list(SPR)
assert all(x[6] in SPR for x in S), [x[1] for x in S if x[6] not in SPR]
def _span(eid):
    sp=sorted({x[6] for x in S if x[0]==eid}, key=ORDER.index)
    return f"{sp[0]}-{sp[-1]}"
EPICS=[(x[0],x[1],x[2],x[3],_span(x[0]),*x[5:]) for x in EPICS]
EPIC_STATUS={"E01":"In Progress","E02":"In Progress","E06":"In Progress","E09":"In Progress"}
CURRENT={"E01":"Plan re-baselined on 9 Oct: two-week sprints, Sprint 3 from 20 Oct",
 "E02":"Sprint 2: database set up on AWS; AOF orchestrator deployment and the end-to-end skeleton in progress",
 "E06":"Sprint 1: about 70% built; Sprint 2: remaining items, own pipeline and deployment",
 "E09":"MB Rec and BA engagement starting; users testing their skill in finance agent chat"}
import os as _o0, sys as _s0
_s0.path.insert(0, _o0.path.dirname(_o0.path.abspath(__file__)))
from standards import COMPONENT
with open("AOF-FOBO-L1-plan.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    w.writerow(["Type","ID","Name","Objective / description","Team","Start","End","Sprints","Key deliverables","Exit criteria","Dependencies","Status","Current state","Component"])
    for e in EPICS:
        a,b=e[4].split("-"); w.writerow(["Epic",e[0],e[1],e[2],e[3],SPR[a][0],SPR[b][1],e[4],e[5],e[6],e[7],EPIC_STATUS.get(e[0],"To Do"),CURRENT.get(e[0],""),COMPONENT[e[0]]])
    for m in MILESTONES:
        w.writerow(["Milestone",m[0],m[1],m[3],"",m[2],m[2],"","","",""])
    w.writerow([]); w.writerow(["Sprint","","Name","Focus","State","Start","End"])
    for k,(a,b) in SPR.items(): w.writerow(["Sprint",k,SNAME[k],SFOCUS[k],SPRINT_STATE.get(k,"Planned"),a,b])
    w.writerow(["Freeze","","Bank change freeze (confirmed)","No Production changes; UAT work continues","",*FREEZE])

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from standards import US, COMPONENT, RELEASE_OF, RELEASES, DOR, DOD

# check the story wording covers every story and every link points at a story
_names = {x[1] for x in S}
assert set(US) == _names, (set(US) ^ _names)
for _k, _v in US.items():
    for _b in _v[4]:
        assert _b in _names, (_k, _b)

def gwt_lines(summ):
    role, want, why, gwt, _ = US[summ]
    return [f"Given {g}, when {w}, then {t}." for g, w, t in (gwt or [])]

def user_story(summ):
    role, want, why, _, _ = US[summ]
    article = "an" if role[0].lower() in "aeiou" else "a"
    return f"As {article} {role}, I want {want}, so that {why}."

STORIES = []
for _n, x in enumerate(S, 1):
    ep, summ, desc, acc, pri, pts, spr, team, env, dep = x[:10]
    STORIES.append(dict(id=f"{ep}-S{_n:02d}", ep=ep, summ=summ, desc=desc, acc=acc, pri=pri, pts=pts, spr=spr,
                        team=team, env=env, st=x[10] if len(x) > 10 else "To Do", story=user_story(summ),
                        gwt=gwt_lines(summ), blocked=US[summ][4]))
ID_OF = {s["summ"]: s["id"] for s in STORIES}
for s in STORIES:
    s["blocked_ids"] = [ID_OF[b] for b in s["blocked"]]

def ac_text(s):
    return "\n".join(["- " + g for g in s["gwt"]] + ["- Done when: " + s["acc"]])

with open("AOF-FOBO-stories.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    MAXB = max(len(s["blocked_ids"]) for s in STORIES)
    w.writerow(["Issue ID","Issue Type","Summary","Description","Acceptance Criteria","Parent","Epic Name","Epic Link",
                "Priority","Story Points","Sprint","Start Date","Due Date","Fix Version","Component","Labels","Labels","Labels",
                "Team","Environment"] + ["Blocked By"]*MAXB + ["Status"])
    names={e[0]:e[1] for e in EPICS}
    for e in EPICS:
        a,b=e[4].split("-")
        w.writerow([e[0],"Epic",e[1],f"{e[2]}\n\nDeliverables: {e[5]}\n\nDependencies: {e[7]}",f"- Done when: {e[6]}","",e[1],"",
                    "High","",SNAME[a],SPR[a][0],SPR[b][1],"",COMPONENT[e[0]],"AOF","FOBO","",e[3],""] + [""]*MAXB + [EPIC_STATUS.get(e[0],"To Do")])
    for s in STORIES:
        desc = f"{s['story']}\n\nDetails: {s['desc']}\n\nAcceptance criteria:\n{ac_text(s)}"
        third = "long-lead" if "long lead" in s["summ"].lower() else ("diagnostics" if s["ep"]=="E06" else "")
        w.writerow([s["id"],"Story",s["summ"],desc,ac_text(s),s["ep"],"",names[s["ep"]],
                    s["pri"],s["pts"],SNAME[s["spr"]],SPR[s["spr"]][0],SPR[s["spr"]][1],RELEASE_OF[s["spr"]],COMPONENT[s["ep"]],
                    "AOF","FOBO",third,s["team"],s["env"]] + (s["blocked_ids"]+[""]*MAXB)[:MAXB] + [s["st"]])
    print(len(STORIES),"stories", sum(s["pts"] for s in STORIES),"points")
