# Ways of working

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | How we write, size and finish stories |

## Story template

**Title:** a short action (what gets done).

**Description:** *As a* \<role\>, *I want* \<goal\>, *so that* \<benefit\>. Then the details.

**Acceptance criteria:** Given \<context\>, when \<action\>, then \<result\>, for each behaviour to test; and one *Done when* line.

## Definition of Ready

- Written as a user story (As a … I want … so that …) with a clear title
- Acceptance criteria agreed with the person who will accept it
- Dependencies known and linked; none blocking the sprint
- Estimated by the team (story points)
- Fits in one sprint; split if not
- Environment, data and access needed are available

## Definition of Done

- Acceptance criteria met and shown to the person who accepts it
- Code reviewed, merged and built by the pipeline; tests and security scans pass
- Deployed to UAT (or Prod where the story says so)
- No open Sev1/Sev2 defects against the story
- Documentation, runbook or Confluence page updated where affected
- Jira status, links and time spent up to date

## Jira conventions

- Issue types: Epic and Story; sub-tasks are added by the team at sprint planning.
- Epics link stories through **Parent** (Jira Cloud) or **Epic Link** (Jira Data Center); the import file has both.
- Story points on the Fibonacci scale (1, 2, 3, 5, 8); two-week sprints, Tuesday to Monday.
- Releases (Fix Version): R1 Working version (30 Nov 2026); R2 Go-live (14 Jan 2027).
- Components: Programme, Platform, Agent One, Connections, FOBO, Diagnostics, Risk and controls, Testing, Engagement, Go-live.
- Labels: AOF, FOBO; long-lead for requests with long lead times; diagnostics for the Diagnostics service.
- Dependencies are *is blocked by* links between issues.
- Priority: Highest, High, Medium.

## Ceremonies

Sprint planning and review every two weeks; daily stand-up; fortnightly steerco; weekly working session with MB Rec.
