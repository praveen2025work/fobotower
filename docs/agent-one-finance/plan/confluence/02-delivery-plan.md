# Delivery plan

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Sprints, milestones and epics; live dates come from Jira |

> Insert the Jira **Timeline** (or Advanced Roadmaps) macro here, filtered to this project, so dates stay live. The tables below are the baseline agreed on 9 Oct 2026.

## Sprints

| Sprint | Start | End | Focus | State |
|---|---|---|---|---|
| Sprint 1 | 22 Sep 2026 | 5 Oct 2026 | Diagnostics | Done |
| Sprint 2 | 6 Oct 2026 | 19 Oct 2026 | AOF skeleton on AWS | Now |
| Sprint 3 | 20 Oct 2026 | 2 Nov 2026 | Connections and sessions | Planned |
| Sprint 4 | 3 Nov 2026 | 16 Nov 2026 | FOBO Prime end to end | Planned |
| Sprint 5 | 17 Nov 2026 | 30 Nov 2026 | Working version | Planned |
| Sprint 6 | 1 Dec 2026 | 14 Dec 2026 | UAT 1 and Prod ready | Planned |
| Sprint 7 | 15 Dec 2026 | 28 Dec 2026 | UAT 2 and sign-offs | Planned |
| Sprint 8 | 29 Dec 2026 | 11 Jan 2027 | Release and parallel run | Planned |
| Sprint 9 | 12 Jan 2027 | 25 Jan 2027 | Go-live | Planned |

## Releases

| Release | Date | Contains |
|---|---|---|
| R1 Working version | 30 Nov 2026 | Everything needed for the working version in UAT and the 30 Nov showcase (Sprints 1 to 5) |
| R2 Go-live | 14 Jan 2027 | UAT sign-off, Prod and go-live (Sprints 6 to 9) |

## Milestones

| ID | Milestone | Date | Meaning |
|---|---|---|---|
| M1 | Diagnostics first version | 5 Oct 2026 | About 70% of Diagnostics built in Sprint 1; improvements and deployment continue |
| M2 | AOF skeleton on AWS | 19 Oct 2026 | Orchestrator service, database and console at /agentone/finance running together on AWS |
| M3 | FOBO Prime end to end in UAT | 16 Nov 2026 | Real MB Rec breaks investigated in their own Agent One session; MOTIF connected; FAS posting tested |
| M4 | Working version showcase | 30 Nov 2026 | FOBO Prime and Rates on AOF in UAT, shown end to end with Diagnostics |
| M5 | Prod ready before the freeze | 10 Dec 2026 | Prod environment and connections in place; no application deployed yet |
| M6 | UAT, security and parity sign-off; CAB submitted | 18 Dec 2026 | UAT signed, penetration test closed, parity accepted, CAB request in for 5 Jan |
| M7 | Released to Prod; parallel run | 6 Jan 2027 | Released 5 Jan after the freeze; parallel run with today's process from 6 Jan |
| M8 | Go-live | 14 Jan 2027 | The FOBO controllers use AOF for FOBO Prime and Rates |

## Epics

| Jira | Epic | From | To | Stories | Points | Exit criteria |
|---|---|---|---|---|---|---|
| E01 | Programme and governance | 6 Oct 2026 | 14 Dec 2026 | 6 | 8 | Steerco agrees scope, plan and go-live criteria |
| E02 | AOF platform on AWS: skeleton, UAT and Prod | 6 Oct 2026 | 14 Dec 2026 | 13 | 40 | The same build runs in UAT and Prod; Prod ready by 10 Dec |
| E03 | Agent One integration: sessions per capability per case | 6 Oct 2026 | 30 Nov 2026 | 10 | 29 | Each FOBO case has its own Agent One session, shared by everyone working the case; no session per login |
| E04 | Data connections: MB Rec, MOTIF and FAS | 6 Oct 2026 | 14 Dec 2026 | 9 | 33 | Breaks load from MB Rec; an approved adjustment posts to MOTIF through FAS in UAT |
| E05 | FOBO (Helix) set-up with the FOBO controllers | 20 Oct 2026 | 30 Nov 2026 | 9 | 28 | The FOBO controllers confirm the set-up |
| E06 | Agent One Finance Diagnostics | 22 Sep 2026 | 11 Jan 2027 | 10 | 34 | Running in Prod; results match Phoenix |
| E07 | Governance, approvals and controls | 6 Oct 2026 | 28 Dec 2026 | 16 | 51 | All approvals and artefacts approved before the CAB request on 18 Dec |
| E08 | Testing and parity with the FOBO controllers | 3 Nov 2026 | 28 Dec 2026 | 9 | 36 | FOBO controllers sign off UAT; parity accepted; no open Sev1/Sev2 |
| E09 | Business engagement and showcase | 6 Oct 2026 | 28 Dec 2026 | 11 | 22 | Showcase held 30 Nov; FOBO controllers trained before go-live |
| E10 | Go-live and support | 15 Dec 2026 | 25 Jan 2027 | 8 | 18 | Live on 14 Jan with no open Sev1/Sev2; support in place |
