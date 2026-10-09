import csv
SPR = {  # sprint: (start, end)
 "S0": ("2026-10-12","2026-10-16"), "S1": ("2026-10-19","2026-10-30"), "S2": ("2026-11-02","2026-11-13"),
 "S3": ("2026-11-16","2026-11-27"), "S4": ("2026-11-30","2026-12-11"), "S5": ("2026-12-14","2026-12-23"),
 "S6": ("2027-01-04","2027-01-15")}
SNAME = {"S0":"S0 Mobilise","S1":"S1","S2":"S2","S3":"S3 Working version","S4":"S4 UAT-1","S5":"S5 UAT-2 and readiness","S6":"S6 Go-live"}

EPICS = [
 # id, name, objective, team, sprints, deliverables, exit, deps
 ("E01","Programme mobilisation and governance","Plan, scope, cadence and approvals for AOF with the FOBO (Helix) use case","PM / Architect","S0-S6",
  "Jira, sprint calendar, RAID log, scope statement, ARB approval, success and go/no-go criteria","Steerco agrees scope, plan and go-live criteria; ARB approved","CAB calendar, change-freeze dates"),
 ("E02","Environments: Dev, UAT, Prod","Three working environments on Rhodium with CI/CD promotion","DevOps","S0-S5",
  "Namespaces, PostgreSQL+pgvector, secrets, SSO proxy, DNS/TLS, CI/CD pipeline, image scanning, backups","Same build promoted Dev -> UAT -> Prod by pipeline; smoke tests pass in each","Rhodium capacity, network/firewall approvals, DBA"),
 ("E03","Codebase sync and build health","Repository on the latest AOF version, building and tested","Backend dev","S0-S2",
  "Latest AOF update applied, helix leftovers removed, deployment fixed (greenlet), tests running in CI, console approach decided","which-version.py reports latest; pytest and web tests green in CI","AOF update package"),
 ("E04","Agent One integration","AOF reasons through Agent One and the bank LLM gateway","Backend dev","S0-S3",
  "LLM adapter (_run), skill session via session_bridge, approved model, tracing, cost limits, real-model eval","FOBO case runs end to end on the approved model in Dev and UAT","Model approval, LLM gateway access"),
 ("E05","Connectors (MCP) and integrations","Read-only access to MB Rec, CATS, MOTIF, security reference data; entitlements; events","Backend dev / DevOps","S0-S5",
  "MCP connectors per env, MB Rec end-of-day event, entitlement roles and data scopes, ticketing","Every connector answers in UAT; refused calls audited; event opens a case","System teams deliver new tools; firewall rules"),
 ("E06","FOBO (Helix) capability on AOF","FOBO Prime and Rates configured, confirmed with Product Control","BA / Product Control SME","S1-S4",
  "Prime and Rates groups, thresholds, playbook checks, sections and checklist, owners and escalation routes","Product Control confirms configuration; data contract signed","Product Control availability, MB Rec tools"),
 ("E07","Parity and evals","Prove AOF answers match or beat today's FOBO (Helix)","Backend dev / QA","S3-S5",
  "Parity runs on the same books/COBs, accepted-differences log, eval sets, agreement thresholds","Parity signed off by Product Control; eval agreement at or above agreed threshold","Decided cases in UAT"),
 ("E08","Console and user experience","Reviewer console deployed and usable in each environment","Frontend dev","S1-S5",
  "Console deployed (AOF reference console build), showcase script, accessibility check, reviewer guide","Reviewers complete UAT scenarios unaided","E03 console decision"),
 ("E09","Security, risk and compliance","All bank approvals for an AI system handling finance data","Architect / Risk","S0-S5",
  "DPIA, data classification, AI/model risk assessment, SAST/dependency scan, pen test, prompt-injection defence, audit integrity, SoD review","All approvals in place before CAB","Risk and security teams' calendars"),
 ("E10","Testing: SIT, performance, UAT","Evidence that it works at production volumes and for the business","QA / Product Control","S2-S5",
  "Test plan, SIT, regression in CI, performance test, UAT cycles 1 and 2, UAT sign-off","UAT signed off; no open Sev1/Sev2","UAT environment, test data"),
 ("E11","Release and go-live","Safe production release and support","DevOps / PM","S5-S6",
  "Runbook, rollback, support model, monitoring and alerts, CAB, prod deploy, parallel run, go/no-go","Go-live 14 Jan with no open Sev1/Sev2; BAU support in place","Change freeze, CAB approval"),
 ("E13","Agent One Finance Diagnostics (Phoenix scraper)","Diagnostics service that reads Phoenix traces, deployed separately outside AWS/BCP; quality checked and improved each sprint","Backend dev / DevOps","S0-S6",
  "Current-state and quality review, hosting outside AWS/BCP, own pipeline, Dev/UAT/Prod deployments, data-quality checks, incremental improvements","Diagnostics running in Prod outside AWS/BCP; outputs reconcile with Phoenix","Hosting platform outside AWS/BCP, Phoenix read access"),
 ("E14","Business and partner engagement (MB Rec, BA)","Committed MB Rec team and BA support through build, UAT and go-live","PM / BA","S0-S6",
  "MB Rec contacts and RACI, weekly sessions, data contract, tool delivery dates, BA requirements and UAT scenarios, interim skill-testing feedback","MB Rec tools and event delivered; BA artefacts signed; feedback loop running","MB Rec team capacity, BA allocation"),
 ("E12","Showcase and change management","Show AOF working with the Helix use case; prepare users","PM / BA","S2-S6",
  "End-November showcase, training, comms, benefits tracking","Showcase held 30 Nov; reviewers trained before go-live","Stakeholder availability"),
]

MILESTONES = [
 ("M0","Mobilised","2026-10-16","Team mobilised, Jira live, environment requests raised; long-lead approvals started"),
 ("M1","Dev green","2026-10-30","Repository on the latest AOF version; Dev deployed; tests in CI; Agent One adapter connected in Dev"),
 ("M2","FOBO Prime end to end in Dev; UAT ready","2026-11-13","Real MB Rec (read-only) data in Dev; UAT environment built"),
 ("M3","Working version showcase (UAT)","2026-11-30","FOBO Prime and Rates on AOF in UAT, demonstrated end to end"),
 ("M4","Prod environment ready, before the freeze","2026-12-11","Prod environment and connectors in place before the change freeze starts; no application deployed yet"),
 ("M5","UAT, security and parity sign-off; CAB submitted","2026-12-18","UAT signed, pen test closed, parity accepted, CAB request in for 5 Jan"),
 ("M6","Production deployed and parallel run","2027-01-06","Deployed 5 Jan after the freeze ends; smoke-tested; parallel run with today's process from 6 Jan"),
 ("M7","Go-live","2027-01-14","Go/no-go passed; Product Control uses AOF for FOBO Prime and Rates"),
]

# id, epic, summary, description, acceptance, priority, points, sprint, team, env, depends
S = [
 # E01
 ("E01","Set up Jira project, boards and sprint calendar","Create the Jira project, epics and stories from this plan; two-week sprints S0-S6.","Board live; all epics and stories imported; sprint dates agreed","High",1,"S0","PM","",""),
 ("E01","Confirm scope and out-of-scope","Scope: AOF core + Agent One integration + FOBO Prime and Rates. Out: other capabilities, SIEM integration (post go-live), skill-session variant in prod (optional).","Scope statement signed by sponsor","Highest",2,"S0","PM","",""),
 ("E01","Confirm CAB deadline for the January window","Change freeze confirmed: 11 Dec to 4 Jan, no Production changes. Confirm the CAB submission deadline for a deployment on 5 Jan.","CAB deadline recorded in the plan","Highest",1,"S0","PM","","","In Progress"),
 ("E01","RAID log, weekly status and steerco cadence","Risks, assumptions, issues, dependencies tracked weekly; steerco fortnightly.","RAID log live; first status sent","High",2,"S0","PM","",""),
 ("E01","ARB review of AOF and FOBO architecture","Present the C4 model (docs/agent-one-finance/architecture) and the governance controls; record conditions.","ARB approval with conditions logged as stories","Highest",3,"S1","Architect","","Architecture docs"),
 ("E01","Define success and go/no-go criteria","Measures: agreement with people (evals), zero unverified figures, hours saved, Sev1/Sev2 count, parity accepted.","Criteria agreed by sponsor and Product Control","High",2,"S1","PM / BA","",""),
 ("E01","Go/no-go sign-off matrix","Who signs what: Product Control, Risk, Security, Operations, Sponsor.","Matrix agreed","High",1,"S4","PM","",""),
 # E02
 ("E02","Fix foundational build and deploy to Dev (deployment failing)","Foundational AOF build set up; deployment currently failing (greenlet missing from the image). Find the cause in the Dockerfile/CI, fix and redeploy (fix-greenlet-deploy.md).","Dev deployment healthy; import greenlet works in the image","Highest",3,"S0","DevOps / Backend","Dev","","In Progress"),
 ("E02","Request UAT namespace on Rhodium (long lead)","Raise the request with capacity, quotas and network needs.","Request approved with a delivery date","Highest",1,"S0","DevOps","UAT",""),
 ("E02","Request Prod namespace on Rhodium (long lead)","Raise the request early; production approvals take longest.","Request approved with a delivery date","Highest",1,"S0","DevOps","Prod",""),
 ("E02","Request firewall rules to MB Rec, CATS, MOTIF, LLM gateway","Per environment, from the Rhodium namespace to each system and the LLM gateway.","Rules approved for Dev, UAT, Prod","Highest",2,"S0","DevOps","All",""),
 ("E02","PostgreSQL with pgvector in Dev; run migrations","Database per environment; alembic upgrade head; least-privilege app role.","alembic at head in Dev; app connects","High",3,"S1","DevOps / DBA","Dev",""),
 ("E02","CI pipeline: build, test, scan, push","pytest, vitest, tsc, check:styles, SAST/dependency scan, image build and push to the registry.","Pipeline green on main; failing test blocks the image","Highest",5,"S1","DevOps","Dev",""),
 ("E02","Secrets per environment","AOF_* settings, event secret, proxy secret, connector keys, LLM credentials in the bank secret store.","No secret in repo or image; rotated per env","Highest",3,"S1","DevOps","All",""),
 ("E02","SSO proxy and identity header in Dev","Reverse proxy sets the user header and proxy secret; console and API behind it.","User signs in via SSO and sees their inbox in Dev","Highest",3,"S1","DevOps","Dev",""),
 ("E02","Build UAT environment","Namespace, database, secrets, SSO proxy, DNS/TLS, connectors.","Pipeline deploys to UAT; smoke test passes","Highest",5,"S2","DevOps","UAT","UAT namespace approved"),
 ("E02","Promotion pipeline Dev -> UAT -> Prod with approvals","Same image promoted; manual approval gates for UAT and Prod.","One image tag runs in Dev and UAT","High",3,"S2","DevOps","All",""),
 ("E02","Backup, restore and DR for PostgreSQL","Backups, a tested restore, RPO/RTO agreed.","Restore tested in UAT","High",3,"S4","DevOps / DBA","UAT/Prod",""),
 ("E02","Build Prod environment","Before the change freeze starts on 11 Dec: namespace, database, secrets, SSO proxy, DNS/TLS. The application is deployed after the freeze.","Prod smoke test passes (no business use yet)","Highest",5,"S4","DevOps","Prod","Prod namespace approved"),
 # E03
 ("E03","Verify the repository is on the latest AOF version","AOF update applied; run which-version.py; resolve any differences; keep our own files (connectors, LLM adapter).","Report shows the latest version; only our own files differ","Highest",1,"S0","Backend","Dev","","In Progress"),
 ("E03","Remove remaining helix references","Search code, tests, config, Dockerfile for helix; rename per the rename map.","grep finds no helix in code/config/tests","Highest",3,"S0","Backend","Dev",""),
 ("E03","Make the test suite run in CI","Install test dependencies (pytest-asyncio etc.), provide a test database; fix environment-only failures.","pytest runs fully; counts reported","Highest",3,"S0","Backend / DevOps","Dev",""),
 ("E03","FOBO config: only steps whose tools exist","Remove steps needing tools not yet provided (break_history_book, breaks_all); keep skill-session capability inactive.","Both capabilities pass the platform check","Highest",1,"S0","Backend","Dev",""),
 ("E03","Decide console approach (AOF reference console vs Next.js port)","Check bank standards and npm mirror; recommendation: deploy the AOF reference console (apps/web) as built.","Decision recorded by Architect","Highest",1,"S0","Architect / Frontend","",""),
 ("E03","Apply each AOF update","Apply each new AOF update package as it arrives; keep our own changes.","Sync done per sprint; tests green","Medium",1,"S1","Backend","Dev",""),
 # E04
 ("E04","Confirm approved model and data classification for the LLM gateway (long lead)","Which model, which data classes may be sent, masking rules.","Written approval for FOBO data on the chosen model","Highest",2,"S0","Architect / Risk","",""),
 ("E04","LLM adapter via Agent One (_run) in Dev","_run calls the bank LLM gateway; masking on; read-only tools.","A FOBO group is reasoned by the real model in Dev","Highest",5,"S1","Backend","Dev","Model approval"),
 ("E04","Skill session via Agent One session_bridge","investigate() through the Agent One session bridge; transcript kept on the case.","Skill-session capability runs one case in Dev","Medium",5,"S3","Backend","Dev",""),
 ("E04","Tracing of model and tool calls","Phoenix or the bank observability stack; trace joined on case id.","A case's trace is findable by case id","High",3,"S2","Backend / DevOps","Dev/UAT",""),
 ("E04","Spend limits and token budgets","Per case and per day for FOBO; off switches tested.","Over-limit case escalates to a person; switch-off blocks calls","High",2,"S2","Backend","Dev",""),
 ("E04","Real-model eval in Dev","Run the real-model eval runbook on decided cases.","Eval agreement recorded; differences reviewed","High",3,"S3","Backend / BA","Dev",""),
 # E05
 ("E05","Map AOF roles and data scopes to the users already provisioned","Users are already provisioned for interim testing; map them to AOF roles (reviewer, owner) and book scopes in configuration. No new access requests.","Provisioned users see only their books; refusals audited","Highest",5,"S1","Backend / IAM","Dev",""),
 ("E05","MB Rec connector (breaks, break history) in Dev","MCP connector, read-only, allow-listed tools.","FOBO case loads real breaks in Dev","Highest",5,"S1","Backend","Dev","Firewall rules"),
 ("E05","Request new MB Rec tools","book_status, break_history_book, breaks_all (data contract: fobo-skill/mbrec-data-contract.md).","MB Rec commits delivery dates","Highest",1,"S0","BA","",""),
 ("E05","CATS connector (trades, positions, pnl_components)","Read-only MCP connector.","Tools answer in Dev","High",5,"S2","Backend","Dev",""),
 ("E05","MOTIF connector (trades, positions, booking_events, pnl_components)","Read-only MCP connector.","Tools answer in Dev","High",5,"S2","Backend","Dev",""),
 ("E05","MB Rec end-of-day event opens a case","MB Rec calls POST /api/events with the event secret; late exceptions open follow-ups.","Event opens a FOBO case in Dev and UAT","High",3,"S2","Backend / MB Rec","Dev/UAT",""),
 ("E05","Connectors in UAT","All connectors configured and reachable in UAT.","Operations page shows all connectors up in UAT","Highest",3,"S2","DevOps","UAT",""),
 ("E05","Security reference data (corporate_actions, bond_metadata)","Optional for go-live; needed for some skill checks.","Tools answer, or deferred with a decision","Medium",3,"S3","Backend","Dev",""),
 ("E05","Ticketing for escalations","Escalated groups raise tickets to owning teams.","Ticket raised from an approved escalation in UAT","Medium",3,"S3","Backend","UAT",""),
 ("E05","Connectors in Prod","All connectors configured and reachable in Prod, before the freeze starts on 11 Dec.","Operations page shows all connectors up in Prod","Highest",3,"S4","DevOps","Prod",""),
 # E06
 ("E06","Confirm thresholds and parameters with Product Control","Data contract: materiality, tolerances, ageing; replace placeholders.","Data contract signed","Highest",3,"S1","BA / Product Control","",""),
 ("E06","Configure FOBO Prime group on real data","Books, keys, reviewers, owners; approve versions four-eyes.","Prime case runs end to end in Dev","Highest",5,"S2","BA / Backend","Dev",""),
 ("E06","Review playbook checks, categories and verdicts","Walk Product Control through checks, verdict table and guards.","Product Control confirms or changes each check","Highest",5,"S2","BA / Product Control","",""),
 ("E06","Sign-off checklist and answer sections","FOBO section 12 sections and section 14 checklist confirmed.","Reviewer completes checklist in Dev","High",2,"S2","BA","Dev",""),
 ("E06","Configure FOBO Rates group","As Prime, for Rates books.","Rates case runs end to end in UAT","High",5,"S3","BA / Backend","UAT",""),
 ("E06","Owners and escalation routes","Who owns each category; who is asked for evidence (desk, Operations).","Escalations and questions reach the right people in UAT","High",2,"S3","BA","UAT",""),
 ("E06","Enable algorithm steps when MB Rec tools arrive","Turn on history and systemic steps; approve the new version.","Steps run and fill their fields in UAT","Medium",2,"S3","Backend","UAT","New MB Rec tools"),
 ("E06","Follow-through and late exceptions","Next-COB re-check; follow-up cases for late breaks.","Demonstrated in UAT","Medium",2,"S3","Backend / QA","UAT",""),
 # E07
 ("E07","Parity runs: FOBO (Helix) vs AOF on the same books and COBs","Use fobo_aof_parity.py on agreed samples.","Parity report produced for Prime and Rates","Highest",5,"S3","Backend / QA","UAT",""),
 ("E07","Accepted-differences log and sign-off","Every difference explained; Product Control accepts or fixes.","Signed accepted-differences log","Highest",3,"S4","BA / Product Control","",""),
 ("E07","Eval sets for Prime and Rates","Decided UAT cases as eval sets; agreement threshold agreed.","Eval run at or above threshold","High",3,"S4","Backend / BA","UAT",""),
 ("E07","Re-run evals after each config or model change","Part of the release checklist.","Eval result attached to each release","Medium",1,"S5","Backend","UAT",""),
 # E08
 ("E08","Deploy console in Dev behind the proxy","Per E03 decision; static build served behind SSO proxy.","Reviewer opens the console in Dev","Highest",3,"S1","Frontend / DevOps","Dev",""),
 ("E08","Deploy console in UAT","Same build promoted.","Console works in UAT","Highest",2,"S2","DevOps","UAT",""),
 ("E08","Console screens on the five-colour rule","Any screens we built follow styles.md; check:styles green.","check:styles passes","Medium",2,"S3","Frontend","Dev",""),
 ("E08","Accessibility and browser check","Bank browsers, keyboard use, contrast in light and dark.","No blocking issues","Medium",2,"S4","Frontend / QA","UAT",""),
 ("E08","Reviewer guide for Product Control","Short guide: inbox, case review, checklist, asking for evidence.","Guide published","High",2,"S4","BA","",""),
 # E09
 ("E09","DPIA and data classification","Data flows, classes sent to the model, masking, retention.","DPIA approved","Highest",5,"S0","Architect / Risk","",""),
 ("E09","AI / model risk assessment","Human-in-the-loop evidence, evals, figure checking, off switches, audit.","Risk acceptance recorded","Highest",5,"S1","Architect / Risk","",""),
 ("E09","Defence against instructions hidden in tool data","Mark tool output as data; flag instruction-like text; eval with hostile cases (pre-pilot gap).","Hostile-data eval cases escalate, never auto-propose","Highest",5,"S2","Backend","Dev",""),
 ("E09","Audit integrity: confirm DB controls or make tamper-evident","Ask DBA/controls; if not covered, revoke UPDATE/DELETE and add a hash chain.","Decision and evidence recorded","High",3,"S3","Architect / Backend","",""),
 ("E09","SAST and dependency scan clean","Fix or accept findings.","No open high/critical findings","Highest",2,"S2","DevOps / Backend","",""),
 ("E09","Book and run penetration test on UAT","Book in S0; run in S4; fix findings.","Pen test report with no open high findings","Highest",3,"S4","Security","UAT","Booking slot"),
 ("E09","Segregation of duties and entitlements review","Owners, reviewers, four-eyes approval, release by a second person.","Review signed","High",2,"S4","Risk / BA","UAT",""),
 # E10
 ("E10","Test plan and SIT cases","Functional, integration, negative (refusals, off switches, limits).","Plan approved","High",3,"S2","QA","",""),
 ("E10","Regression suite in CI","Backend and web tests plus API smoke tests on each deploy.","Regression runs on every pipeline","High",3,"S2","QA / DevOps","Dev",""),
 ("E10","SIT execution","Execute SIT in Dev/UAT; log defects.","No open Sev1/Sev2","Highest",5,"S3","QA","UAT",""),
 ("E10","Performance test at production volumes","Books x breaks per COB, end-of-day burst, model latency.","Cases ready before the agreed review time","High",5,"S4","QA / Backend","UAT",""),
 ("E10","UAT plan with Product Control","Scenarios, users, data, schedule.","Plan agreed","Highest",2,"S3","BA / QA","",""),
 ("E10","UAT cycle 1","Product Control reviews real cases; defects triaged.","Cycle 1 report","Highest",5,"S4","Product Control / QA","UAT",""),
 ("E10","UAT cycle 2 and sign-off","Retest fixes; sign-off.","UAT signed off","Highest",5,"S5","Product Control / QA","UAT",""),
 # E11
 ("E11","Runbook and rollback plan","Deploy, smoke test, rollback, connector failure, model outage (groups go to people).","Runbook reviewed by Operations","Highest",3,"S5","DevOps / Backend","Prod",""),
 ("E11","Support model: L1, L2, L3 and on-call","Who answers what; platform support vs business.","Support model signed; BAU support from go-live","Highest",2,"S5","PM / Operations","Prod",""),
 ("E11","Monitoring and alerts","Set up in Prod on 4–5 Jan, after the freeze and before go-live: health, connector down, refused-call spikes, spend limit reached, eval drop.","Alerts reach on-call in a test","Highest",3,"S6","DevOps","Prod",""),
 ("E11","CAB submission","Change request with evidence: UAT, pen test, risk, runbook.","CAB approved for the January window","Highest",2,"S5","PM","Prod","M4 sign-offs"),
 ("E11","Production deploy and smoke test","5 Jan, the first working day after the freeze: deploy the signed-off image; smoke test; no business use yet.","Smoke test passes in Prod","Highest",2,"S6","DevOps","Prod","CAB approval"),
 ("E11","Parallel run with today's process","Product Control works both ways for agreed books; compare.","Parallel-run report","Highest",3,"S6","Product Control / BA","Prod",""),
 ("E11","Go/no-go and go-live","Go/no-go on 13 Jan; go-live 14 Jan.","Go decision recorded; users live","Highest",1,"S6","PM","Prod",""),

 # E13 Diagnostics (Phoenix scraper)
 ("E13","Current-state review of Agent One Finance Diagnostics","Partially built. Inventory what exists: code, configuration, schedule, outputs, tests, known issues.","Written current state with gaps and a prioritised improvement list","Highest",2,"S0","Backend","Dev","","In Progress"),
 ("E13","Quality check: outputs reconcile with Phoenix","Sample traces across capabilities; compare counts, timings, errors and costs with Phoenix; check error handling and retries.","Reconciliation report; defects logged","Highest",3,"S1","Backend / QA","Dev",""),
 ("E13","Confirm hosting outside AWS/BCP","Agree the platform (for example on-prem) and its approvals; network path to Phoenix.","Hosting decision and request approved","Highest",2,"S0","Architect / DevOps","",""),
 ("E13","Separate build pipeline and image for Diagnostics","Own repo or module, CI build, tests, scan; independent of the AOF API image.","Pipeline green; image in the registry","High",3,"S1","DevOps","Dev",""),
 ("E13","Phoenix read-only connectivity per environment","Service account, read-only, credentials in the secret store; masking of finance fields in outputs.","Diagnostics reads Phoenix in Dev with no write rights","Highest",2,"S1","DevOps / Backend","Dev",""),
 ("E13","Deploy Diagnostics to Dev","Outside AWS/BCP per the hosting decision.","Runs on schedule in Dev; outputs visible","Highest",3,"S1","DevOps","Dev","Hosting decision"),
 ("E13","Automated tests and data-quality checks","Unit tests and checks on missing traces, duplicates, time windows.","Checks run in CI and on each run","High",3,"S2","Backend / QA","Dev",""),
 ("E13","Security review of Diagnostics outputs","Traces may hold finance data: confirm masking, retention, who may see outputs.","Review signed","High",2,"S2","Architect / Risk","",""),
 ("E13","Deploy Diagnostics to UAT","Same image promoted.","Runs in UAT against UAT traces","High",2,"S3","DevOps","UAT",""),
 ("E13","Diagnostics views for the showcase","Run health, model calls, refusals, cost per case for FOBO.","Shown at the 30 Nov showcase","High",2,"S3","Backend","UAT",""),
 ("E13","Incremental improvements (sprint 2)","Top items from the quality review.","Agreed items done","Medium",3,"S2","Backend","Dev",""),
 ("E13","Incremental improvements (sprint 4)","Next items from the backlog and UAT feedback.","Agreed items done","Medium",3,"S4","Backend","UAT",""),
 ("E13","Runbook and monitoring for Diagnostics","Schedule failures, Phoenix unreachable, stale outputs.","Alerts reach on-call in a test","High",2,"S5","DevOps","Prod",""),
 ("E13","Deploy Diagnostics to Prod","Outside AWS/BCP; included in the CAB request.","Runs in Prod; outputs reconcile with Phoenix","Highest",2,"S6","DevOps","Prod","CAB approval"),
 # E14 Engagement
 ("E14","MB Rec: named contacts, RACI and weekly working session","Agree who in MB Rec owns connectors, the end-of-day event and the new tools.","RACI agreed; weekly session in calendars","Highest",1,"S0","PM","","","In Progress"),
 ("E14","MB Rec: walk through the data contract","Fields each check reads; thresholds; new tools (fobo-skill/mbrec-data-contract.md).","MB Rec confirms fields and gaps","Highest",2,"S1","BA / MB Rec","",""),
 ("E14","MB Rec: committed delivery dates for new tools and the event","book_status, break_history_book, breaks_all; end-of-day event to AOF.","Dates in the plan; tracked weekly","Highest",1,"S1","PM / MB Rec","",""),
 ("E14","MB Rec: integration test of the end-of-day event in UAT","Event opens a case; late exceptions open follow-ups.","Passed in UAT","High",2,"S3","MB Rec / QA","UAT",""),
 ("E14","MB Rec: UAT and go-live support","Named support during UAT and the go-live week.","Support named in the runbook","High",1,"S4","PM","",""),
 ("E14","Assign BA and onboard","BA owns requirements, Product Control sessions and UAT scenarios.","BA allocated and onboarded","Highest",1,"S0","PM","","","In Progress"),
 ("E14","BA: current FOBO process and requirements","Map today's FOBO break investigation and sign-off; confirm what AOF must do on day one.","Process map and requirements signed by Product Control","Highest",3,"S1","BA","",""),
 ("E14","BA: acceptance criteria and UAT scenarios","Scenarios per category and verdict; edge cases (late breaks, escalations).","Scenarios signed","High",3,"S2","BA","",""),
 ("E14","Interim skill testing in finance agent chat: weekly feedback","Users are already provisioned and test their skill in the chat; collect findings weekly.","Weekly feedback log","High",1,"S0","BA","","","In Progress"),
 ("E14","Turn skill-testing feedback into skill and playbook changes","Update the skill file and playbook checks; re-run evals.","Changes approved; evals re-run","High",3,"S2","BA / Backend","Dev",""),
 # E12
 ("E12","Showcase script and data","FOBO case from MB Rec event to sign-off; How it runs; Evals; Operations.","Script and data ready","Highest",2,"S3","BA / PM","UAT",""),
 ("E12","Showcase rehearsal and delivery (30 Nov)","Rehearse 27 Nov; deliver 30 Nov.","Showcase held; feedback logged as stories","Highest",2,"S3","PM / Team","UAT",""),
 ("E12","Reviewer training","Product Control reviewers, owners, platform support.","All go-live users trained","High",3,"S5","BA","UAT",""),
 ("E12","Stakeholder communications","Go-live comms, what changes for users, support contacts.","Comms sent","Medium",1,"S6","PM","",""),
 ("E12","Benefits tracking","Hours saved (declared and measured), agreement, escalations.","Benefits reported after go-live","Medium",2,"S6","PM / BA","Prod",""),
]

ORDER=["S0","S1","S2","S3","S4","S5","S6"]
def _span(eid):
    sp=sorted({x[6] for x in S if x[0]==eid}, key=ORDER.index)
    return f"{sp[0]}-{sp[-1]}"
EPICS=[(x[0],x[1],x[2],x[3],_span(x[0]),*x[5:]) for x in EPICS]
EPIC_STATUS={"E02":"In Progress","E03":"In Progress","E13":"In Progress","E14":"In Progress"}
CURRENT={"E02":"Foundational build set up; Dev deployment failing (greenlet), fix in progress","E03":"Latest AOF update applied; verification in progress",
 "E13":"Partially built; quality review and separate deployment outside AWS/BCP to do","E14":"MB Rec and BA engagement starting",
 "E06":"Users already provisioned; testing their skill in finance agent chat (interim)"}
with open("AOF-FOBO-L1-plan.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    w.writerow(["Type","ID","Name","Objective / description","Team","Start","End","Sprints","Key deliverables","Exit criteria","Dependencies","Status","Current state"])
    for e in EPICS:
        a,b=e[4].split("-"); w.writerow(["Epic",e[0],e[1],e[2],e[3],SPR[a][0],SPR[b][1],e[4],e[5],e[6],e[7],EPIC_STATUS.get(e[0],"To Do"),CURRENT.get(e[0],"")])
    for m in MILESTONES:
        w.writerow(["Milestone",m[0],m[1],m[3],"",m[2],m[2],"","","",""])
    w.writerow([]); w.writerow(["Sprint","","Name","","","Start","End"])
    for k,(a,b) in SPR.items(): w.writerow(["Sprint",k,SNAME[k],"","",a,b])
    w.writerow(["Freeze","","Bank change freeze (confirmed)","No Production changes; UAT work continues","","2026-12-11","2027-01-04"])

with open("AOF-FOBO-stories.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    w.writerow(["Issue ID","Issue Type","Summary","Description","Acceptance Criteria","Parent ID","Epic Name","Priority","Story Points","Sprint","Start Date","Due Date","Team","Environment","Depends On","Labels","Status"])
    names={e[0]:e[1] for e in EPICS}
    for i,e in enumerate(EPICS,1):
        a,b=e[4].split("-")
        w.writerow([e[0],"Epic",e[1],e[2],e[6],"",e[1],"High","",SNAME[a],SPR[a][0],SPR[b][1],e[3],"",e[7],"AOF;FOBO",EPIC_STATUS.get(e[0],"To Do")])
    n=0
    for s in S:
        ep,summ,desc,acc,pri,pts,spr,team,env,dep=s[:10]; st=s[10] if len(s)>10 else "To Do"; n+=1
        w.writerow([f"{ep}-S{n:02d}","Story",summ,desc,acc,ep,names[ep],pri,pts,SNAME[spr],SPR[spr][0],SPR[spr][1],team,env,dep,"AOF;FOBO"+(";long-lead" if "long lead" in summ.lower() else "")+(";diagnostics" if ep=="E13" else ""),st])
    print(n,"stories", sum(s[5] for s in S),"points")
    from collections import defaultdict
    d=defaultdict(int)
    for s in S: d[s[6]]+=s[5]
    print(dict(d))
