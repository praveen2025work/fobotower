# Jira and Confluence standards for the plan: user-story wording, Given/When/Then
# for stories with testable behaviour, dependencies as links between stories,
# components, releases, Definition of Ready and Definition of Done.
# Keyed by story summary (see plan_data.py).

RELEASES = [
    ("R1 Working version", "2026-11-30", "Everything needed for the working version in UAT and the 30 Nov showcase (Sprints 1 to 5)"),
    ("R2 Go-live", "2027-01-14", "UAT sign-off, Prod and go-live (Sprints 6 to 9)"),
]
RELEASE_OF = {**{k: "R1 Working version" for k in ("S1", "S2", "S3", "S4", "S5")},
              **{k: "R2 Go-live" for k in ("S6", "S7", "S8", "S9")}}

COMPONENT = {"E01": "Programme", "E02": "Platform", "E03": "Agent One", "E04": "Connections", "E05": "FOBO",
             "E06": "Diagnostics", "E07": "Risk and controls", "E08": "Testing", "E09": "Engagement",
             "E10": "Go-live"}

DOR = [
    "Written as a user story (As a … I want … so that …) with a clear title",
    "Acceptance criteria agreed with the person who will accept it",
    "Dependencies known and linked; none blocking the sprint",
    "Estimated by the team (story points)",
    "Fits in one sprint; split if not",
    "Environment, data and access needed are available",
]
DOD = [
    "Acceptance criteria met and shown to the person who accepts it",
    "Code reviewed, merged and built by the pipeline; tests and security scans pass",
    "Deployed to UAT (or Prod where the story says so)",
    "No open Sev1/Sev2 defects against the story",
    "Documentation, runbook or Confluence page updated where affected",
    "Jira status, links and time spent up to date",
]

# summary: (role, I want, so that, [(given, when, then)] or None, [blocked by: summaries])
US = {
 # E01
 "Set up Jira, sprint calendar and weekly status": ("delivery lead", "the plan loaded into Jira with a sprint calendar and a weekly status", "everyone works from one plan and sees progress", None, []),
 "Agree scope with the Business": ("delivery lead", "the scope agreed with the Business", "we build what the Business needs and nothing else", None, []),
 "Confirm the CAB deadline for a 5 Jan release": ("delivery lead", "the CAB deadline for a 5 Jan release", "the release is approved before the freeze ends", None, []),
 "RAID log and fortnightly steerco": ("delivery lead", "a RAID log and a fortnightly steerco", "risks and decisions are visible and acted on", None, []),
 "Architecture review (ARB)": ("architect", "the architecture approved by ARB", "the design is accepted before we build on it", None, ["Agree the session design with the Agent One team"]),
 "Agree success and go/no-go criteria": ("delivery lead", "success and go/no-go criteria agreed", "the go-live decision is objective", None, []),
 "Go/no-go sign-off list": ("delivery lead", "a list of who signs go/no-go", "the right people approve go-live", None, []),
 # E02
 "Set up the AOF database on AWS (Postgres with pgvector)": ("platform engineer", "the AOF database on AWS with pgvector", "AOF can keep its cases, audit trail and knowledge", None, []),
 "Deploy the AOF orchestrator service to AWS": ("platform engineer", "the AOF orchestrator running as its own service on AWS", "the team can deliver changes to UAT", [("a release from the pipeline", "it is deployed", "the service starts and passes its health check")], ["Set up the AOF database on AWS (Postgres with pgvector)"]),
 "AOF skeleton end to end on AWS": ("Product Control reviewer", "the console, orchestrator and database working together on AWS", "we can see AOF run before the connections arrive", [("a sample case on test data", "it is opened in the console at /agentone/finance", "it runs and can be reviewed")], ["Deploy the AOF orchestrator service to AWS"]),
 "Request the Prod platform (long lead)": ("platform engineer", "the Prod platform requested now", "Prod is ready by 10 Dec", None, []),
 "Settle the AOF database migrations": ("platform engineer", "the AWS database on AOF's migration history", "every release can change the database safely", [("a release with a database change", "it is deployed", "the migration runs first and there is one migration head")], ["Set up the AOF database on AWS (Postgres with pgvector)"]),
 "Take each AOF release the same way (sync tool)": ("platform engineer", "each AOF release taken with the sync tool instead of a hand conversion", "updates are quick, complete and keep our own changes", [("a new AOF release", "the sync tool runs", "the console and backend are updated and our sign-on and connection settings are kept")], []),
 "Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)": ("platform engineer", "network access to MB Rec, MOTIF, FAS and the LLM gateway", "the connections work in UAT and Prod", None, []),
 "Build pipeline with tests and security scans": ("platform engineer", "every change built, tested and scanned", "only safe changes reach UAT and Prod", [("a change with a failing test", "the pipeline runs", "the release is stopped")], []),
 "Complete the UAT environment": ("platform engineer", "UAT complete with single sign-on, secrets and connections", "Product Control can test on real data", [("the pipeline", "a release is promoted to UAT", "it deploys and a reviewer can sign in")], ["Deploy the AOF orchestrator service to AWS"]),
 "Deploy the reviewer console to UAT": ("Product Control reviewer", "the reviewer console in UAT", "I can review cases on screen", [("I am a provisioned reviewer", "I open /agentone/finance in UAT", "I see my inbox after single sign-on")], ["Complete the UAT environment"]),
 "Promote releases from UAT to Prod through the pipeline": ("platform engineer", "the same build promoted from UAT to Prod with an approval gate", "Prod runs exactly what was tested", [("a release signed off in UAT", "it is promoted", "Prod gets the same build only after approval")], ["Build pipeline with tests and security scans"]),
 "Build the Prod environment before the freeze": ("platform engineer", "the Prod environment ready by 10 Dec", "we can release on 5 Jan without a freeze breach", [("the Prod platform", "the smoke test runs", "it passes by 10 Dec")], ["Request the Prod platform (long lead)"]),
 "Backups and restore tested": ("support analyst", "backups with a tested restore", "we can recover from data loss", [("a backup", "we restore it to UAT", "the cases and audit trail are complete")], []),
 # E03
 "Confirm the approved model and data rules (long lead)": ("risk officer", "the approved model and data rules confirmed", "only approved data reaches the model", None, []),
 "Agree the session design with the Agent One team": ("architect", "the session design agreed with the Agent One team", "sessions follow the case, not the user login", None, []),
 "Open an Agent One session per capability per case": ("Product Control reviewer", "one Agent One session per capability per case", "everyone working a case shares the same investigation", [("a FOBO case for a book and date", "two reviewers open it", "both use the same session"), ("two different cases", "they run", "they never share a session"), ("a user", "they log in", "no session is created")], ["Agree the session design with the Agent One team", "Confirm the approved model and data rules (long lead)"]),
 "Session runs with the case's rights, not the user's": ("risk officer", "each session to run with the case's identity and book scope", "a session can only read that case's books", [("a session for book A", "it asks for book B's data", "the request is refused and audited")], ["Open an Agent One session per capability per case"]),
 "Session per break group (where needed)": ("Product Control reviewer", "large cases investigated in parallel by break group", "results are ready sooner", [("a case with several break groups", "it runs", "groups are investigated in parallel under the same case")], ["Open an Agent One session per capability per case"]),
 "Session lifecycle: resume, close and keep the record": ("support analyst", "sessions that resume, close at sign-off and keep their record", "no work is lost and audit is complete", [("a case interrupted by a restart", "it is re-run", "the session resumes"), ("a signed-off case", "the session closes", "its record stays with the case")], ["Open an Agent One session per capability per case"]),
 "Trace every model and system call by case": ("support analyst", "every model and system call traceable by case number", "I can explain any outcome", [("a case number", "I search the traces", "I see every model and system call for it")], []),
 "Cost limits and off switches per capability and case": ("delivery lead", "cost limits and off switches", "spend is controlled and we can stop safely", [("a case over its limit", "it reaches the model step", "it goes to a person instead"), ("FOBO switched off", "a case would open", "nothing runs")], []),
 "Run the FOBO skill in the case's session": ("Product Control reviewer", "the controllers' FOBO skill run in the case's session", "we can compare it with the step-by-step set-up", None, ["Open an Agent One session per capability per case"]),
 "Real-model evaluation on decided cases": ("Product Control reviewer", "the real model checked against cases we already decided", "we trust its proposals", None, ["Open an Agent One session per capability per case"]),
 # E04
 "MB Rec: read breaks and break history": ("Product Control reviewer", "breaks and their history read from MB Rec", "each case starts from the real breaks", [("a book and date in MB Rec", "a case opens", "its breaks load read-only")], ["Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)"]),
 "MB Rec: request the extra data the checks need (long lead)": ("BA", "MB Rec's extra data requested with dates", "the extra checks can be turned on", None, []),
 "MB Rec: end-of-day notification opens a case": ("Product Control reviewer", "a case opened automatically when MB Rec finishes a book", "work is ready when I start", [("MB Rec finishes a book", "it sends its notification", "a case opens"), ("a late break for an open book", "MB Rec notifies", "a follow-up case opens")], ["MB Rec: read breaks and break history"]),
 "MOTIF: read trades, positions and booking events": ("Product Control reviewer", "trades, positions and booking events read from MOTIF", "breaks are explained from the booking side", [("a break", "it is investigated", "the MOTIF data used is shown on the case")], ["Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)"]),
 "FAS: agree posting rules with Product Control and MOTIF": ("BA", "the posting rules agreed", "only the right adjustments are posted", None, []),
 "FAS: post approved adjustments to MOTIF": ("Product Control reviewer", "approved adjustments posted to MOTIF through FAS", "I do not re-key them", [("an adjustment approved by a reviewer and released by a second person", "it is posted", "it reaches MOTIF through FAS"), ("an adjustment already posted", "it is posted again", "the second post is refused"), ("an adjustment not released", "anyone tries to post it", "nothing is posted")], ["FAS: agree posting rules with Product Control and MOTIF", "Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)"]),
 "FAS: confirm each posted adjustment in MOTIF": ("Product Control reviewer", "each posting confirmed in MOTIF", "I know it landed", [("a posted adjustment", "MOTIF is read back", "the case shows it confirmed, or flags it")], ["FAS: post approved adjustments to MOTIF"]),
 "Give provisioned users their AOF roles and books": ("Product Control reviewer", "my AOF role and books set", "I see only my books", [("a reviewer for book A", "they open the inbox", "they see only book A's cases")], []),
 "Connections in Prod before the freeze": ("platform engineer", "MB Rec, MOTIF and FAS reachable from Prod by 10 Dec", "the 5 Jan release needs no network change", None, ["Build the Prod environment before the freeze"]),
 # E05
 "Confirm thresholds and parameters with Product Control": ("Product Control reviewer", "materiality, tolerances and ageing confirmed", "the checks use our values", None, []),
 "Set up FOBO Prime": ("Product Control reviewer", "FOBO Prime set up on AOF", "Prime breaks are investigated end to end", [("a Prime book and date", "the case runs", "each break group has a proposal ready for review")], ["Confirm thresholds and parameters with Product Control", "MB Rec: read breaks and break history"]),
 "Review checks, categories and verdicts with Product Control": ("Product Control reviewer", "each check, category and verdict reviewed", "the outcomes match how we work", None, []),
 "Sign-off checklist and reviewer answers": ("Product Control reviewer", "a sign-off checklist", "every approval meets the same standard", [("a proposal", "I approve it", "the required checklist answers are recorded")], []),
 "Set up FOBO Rates": ("Product Control reviewer", "FOBO Rates set up on AOF", "Rates breaks are investigated end to end", [("a Rates book and date", "the case runs", "each break group has a proposal ready for review")], ["Set up FOBO Prime"]),
 "Which verdicts post an adjustment, and who releases it": ("Product Control reviewer", "the verdicts that post adjustments and the releasing role set", "posting follows our rules", [("an approved POST verdict", "it is released by the releasing role", "an adjustment is posted")], ["FAS: agree posting rules with Product Control and MOTIF"]),
 "Owners and escalation routes": ("Product Control reviewer", "owners and escalation routes set", "questions reach the right people", None, []),
 "Turn on extra checks when MB Rec's new data arrives": ("Product Control reviewer", "the extra checks on when MB Rec's data arrives", "more breaks are explained", None, ["MB Rec: request the extra data the checks need (long lead)"]),
 "Next-day follow-up and late breaks": ("Product Control reviewer", "decisions re-checked the next day and late breaks in their own case", "nothing is missed", [("a decision that a break would clear", "the next business day runs", "the case shows whether it cleared")], []),
 # E06
 "Build the Diagnostics core (Phoenix scraper)": ("support analyst", "agent runs, model calls, errors and cost read from Phoenix traces", "I can see how the agents run", None, []),
 "Diagnostics: finish the remaining 30%": ("support analyst", "the open Diagnostics items finished", "Diagnostics is complete enough for UAT", None, ["Build the Diagnostics core (Phoenix scraper)"]),
 "Confirm hosting outside AWS/BCP": ("architect", "Diagnostics hosting outside AWS/BCP approved", "it can be deployed", None, []),
 "Quality check: results match Phoenix": ("support analyst", "Diagnostics results reconciled with Phoenix", "I can trust what it shows", [("sample cases", "Diagnostics and Phoenix are compared", "counts, timings, errors and costs match")], []),
 "Own build pipeline and read-only Phoenix access": ("platform engineer", "a separate pipeline and read-only Phoenix access", "Diagnostics is released safely", None, []),
 "Deploy Diagnostics to UAT": ("support analyst", "Diagnostics running in UAT", "we see agent health during UAT", None, ["Confirm hosting outside AWS/BCP", "Own build pipeline and read-only Phoenix access"]),
 "Tests, data checks and security review": ("risk officer", "Diagnostics tested and reviewed", "finance data in traces is protected", None, []),
 "Diagnostics views for the showcase": ("delivery lead", "Diagnostics views for the showcase", "the Business sees how the agent runs", None, ["Deploy Diagnostics to UAT"]),
 "Improvements from the quality review and UAT feedback": ("support analyst", "the top improvements made", "Diagnostics gets better each sprint", None, []),
 "Deploy Diagnostics to Prod": ("support analyst", "Diagnostics running in Prod", "we see agent health after go-live", None, ["CAB request for 5 Jan"]),
 # E07
 "DPIA and data classification": ("risk officer", "a DPIA and data classification", "data use is approved", None, []),
 "AI and model risk assessment": ("risk officer", "an AI and model risk assessment", "the bank accepts the residual risk", None, []),
 "Protect the model from instructions hidden in data": ("risk officer", "text from source systems treated as data only", "no one can steer the model through the data", [("a break comment containing an instruction", "the case runs", "the group goes to a person and nothing is proposed automatically")], []),
 "Security scans clean": ("risk officer", "code and dependency scans clean", "no known vulnerabilities go live", None, []),
 "Controls for posting adjustments": ("risk officer", "posting controls signed off", "postings to MOTIF are safe", None, ["FAS: agree posting rules with Product Control and MOTIF"]),
 "Audit trail cannot be changed": ("risk officer", "an audit trail that cannot be changed", "it stands as evidence", None, []),
 "Penetration test on UAT": ("risk officer", "a penetration test with no open high findings", "the service is safe to go live", None, ["Complete the UAT environment"]),
 "Access and segregation-of-duties review": ("risk officer", "access and segregation of duties reviewed", "no one can approve and release the same posting", None, []),
 # E08
 "Test plan": ("QA lead", "a test plan", "testing covers what matters", None, []),
 "Integration testing in UAT": ("QA lead", "end-to-end testing in UAT", "the whole flow works", [("MB Rec breaks for a book", "the flow runs to review and FAS posting", "every step works with no Sev1/Sev2 open")], ["Test plan", "FAS: post approved adjustments to MOTIF"]),
 "Parity check against today's FOBO": ("Product Control reviewer", "AOF compared with today's FOBO on the same books and dates", "I know where it differs", None, ["Set up FOBO Prime"]),
 "Agree and sign off the differences": ("Product Control reviewer", "every difference explained and signed", "parity is accepted", None, ["Parity check against today's FOBO"]),
 "Performance test at end-of-day volumes": ("QA lead", "a performance test at end-of-day volumes", "cases are ready on time", [("all books at end of day", "they run together", "every case is ready by the agreed time")], []),
 "Evaluation set and agreement threshold": ("Product Control reviewer", "an evaluation set and an agreed threshold", "each change is checked against our decisions", None, []),
 "UAT cycle 1 with Product Control": ("Product Control reviewer", "a first UAT cycle on real cases", "defects are found early", None, ["Integration testing in UAT"]),
 "UAT cycle 2 and sign-off": ("Product Control reviewer", "a second UAT cycle and sign-off", "we accept the service", None, ["UAT cycle 1 with Product Control"]),
 # E09
 "MB Rec: contacts, responsibilities and a weekly session": ("delivery lead", "named MB Rec contacts and a weekly session", "MB Rec work is planned and tracked", None, []),
 "Assign and onboard the BA": ("delivery lead", "a BA in place", "requirements and UAT are owned", None, []),
 "Interim skill testing: weekly feedback": ("BA", "weekly feedback from users testing their skill", "we improve the checks from real use", None, []),
 "MB Rec: walk through the data needed": ("BA", "MB Rec to confirm the data each check needs", "gaps are known early", None, []),
 "Delivery dates from MB Rec, MOTIF and FAS": ("delivery lead", "committed dates from MB Rec, MOTIF and FAS", "dependencies are in the plan", None, []),
 "BA: today's FOBO process and requirements": ("BA", "today's FOBO process mapped", "the new process matches the Business's needs", None, []),
 "BA: UAT scenarios": ("BA", "UAT scenarios signed", "UAT covers every category and verdict", None, ["BA: today's FOBO process and requirements"]),
 "Use skill-testing feedback to improve the checks": ("Product Control reviewer", "the checks improved from skill-testing feedback", "proposals get better", None, ["Interim skill testing: weekly feedback"]),
 "Showcase on 30 Nov": ("delivery lead", "the working version shown on 30 Nov", "the Business sees it end to end", None, ["Set up FOBO Prime", "Set up FOBO Rates"]),
 "Reviewer training and guide": ("Product Control reviewer", "training and a short guide", "I can use AOF from day one", None, []),
 # E10
 "Runbook and rollback plan": ("support analyst", "a runbook and rollback plan", "we can operate and back out safely", None, []),
 "Support model": ("support analyst", "an agreed support model", "users know who to call", None, []),
 "CAB request for 5 Jan": ("delivery lead", "CAB approval for 5 Jan", "we can release after the freeze", None, ["UAT cycle 2 and sign-off", "Penetration test on UAT", "Agree and sign off the differences"]),
 "Release to Prod on 5 Jan and smoke test": ("platform engineer", "the signed-off build released to Prod on 5 Jan", "the parallel run can start", [("CAB approval", "the build is released on 5 Jan", "the smoke test passes")], ["CAB request for 5 Jan", "Build the Prod environment before the freeze"]),
 "Monitoring and alerts in Prod": ("support analyst", "monitoring and alerts in Prod", "problems are seen before users notice", [("a connection down or a failed posting", "it happens", "on-call is alerted")], []),
 "Parallel run with today's process": ("Product Control reviewer", "a week working both ways on agreed books", "we go live with confidence", None, ["Release to Prod on 5 Jan and smoke test"]),
 "Go/no-go and go-live": ("delivery lead", "a go/no-go decision on 13 Jan", "we go live on 14 Jan only if ready", None, ["Parallel run with today's process"]),
 "Go-live communications and benefits tracking": ("delivery lead", "go-live communications and a benefits report", "users are informed and value is measured", None, []),
}
