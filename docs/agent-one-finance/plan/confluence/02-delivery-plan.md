# Delivery plan

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Sprints, milestones and epics; live dates come from Jira |

> Insert the Jira **Timeline** (or Advanced Roadmaps) macro here, filtered to this project, so dates stay live. The tables below are the baseline agreed on 9 Oct 2026.

## Sprints

| Sprint | Start | End |
|---|---|---|
| S0 Mobilise | 12 Oct 2026 | 16 Oct 2026 |
| S1 | 19 Oct 2026 | 30 Oct 2026 |
| S2 | 2 Nov 2026 | 13 Nov 2026 |
| S3 Working version | 16 Nov 2026 | 27 Nov 2026 |
| S4 UAT-1 | 30 Nov 2026 | 11 Dec 2026 |
| S5 UAT-2 and readiness | 14 Dec 2026 | 23 Dec 2026 |
| S6 Go-live | 4 Jan 2027 | 15 Jan 2027 |

## Releases

| Release | Date | Contains |
|---|---|---|
| R1 Working version | 30 Nov 2026 | Everything needed for the working version in UAT and the 30 Nov showcase (S0 to S3) |
| R2 Go-live | 14 Jan 2027 | UAT sign-off, Prod and go-live (S4 to S6) |

## Milestones

| ID | Milestone | Date | Meaning |
|---|---|---|---|
| M0 | Mobilised | 16 Oct 2026 | Team mobilised, Jira live, long-lead requests raised |
| M1 | Build green in UAT | 30 Oct 2026 | Build fixed, on the latest AOF version and deployed to UAT through the pipeline |
| M2 | FOBO Prime end to end in UAT | 13 Nov 2026 | Real MB Rec breaks investigated; MOTIF connected; FAS posting tested |
| M3 | Working version showcase | 30 Nov 2026 | FOBO Prime and Rates on AOF in UAT, shown end to end |
| M4 | Prod ready before the freeze | 11 Dec 2026 | Prod environment and connections in place; no application deployed yet |
| M5 | UAT, security and parity sign-off; CAB submitted | 18 Dec 2026 | UAT signed, penetration test closed, parity accepted, CAB request in for 5 Jan |
| M6 | Released to Prod; parallel run | 6 Jan 2027 | Released 5 Jan after the freeze; parallel run with today's process from 6 Jan |
| M7 | Go-live | 14 Jan 2027 | Product Control uses AOF for FOBO Prime and Rates |

## Epics

| Jira | Epic | From | To | Stories | Points | Exit criteria |
|---|---|---|---|---|---|---|
| E01 | Programme and governance | 12 Oct 2026 | 11 Dec 2026 | 7 | 11 | Steerco agrees scope, plan and go-live criteria |
| E02 | Build and environments (UAT, Prod) | 12 Oct 2026 | 11 Dec 2026 | 10 | 32 | The same build runs in UAT and Prod; Prod ready by 11 Dec |
| E03 | Agent One integration: sessions per capability per case | 12 Oct 2026 | 27 Nov 2026 | 10 | 29 | Each FOBO case has its own Agent One session, shared by everyone working the case; no session per login |
| E04 | Data connections: MB Rec, MOTIF and FAS | 12 Oct 2026 | 11 Dec 2026 | 9 | 33 | Breaks load from MB Rec; an approved adjustment posts to MOTIF through FAS in UAT |
| E05 | FOBO (Helix) set-up with Product Control | 19 Oct 2026 | 27 Nov 2026 | 9 | 28 | Product Control confirms the set-up |
| E06 | Agent One Finance Diagnostics | 12 Oct 2026 | 15 Jan 2027 | 9 | 23 | Running in Prod; results match Phoenix |
| E07 | Security, risk and controls | 12 Oct 2026 | 11 Dec 2026 | 8 | 26 | All approvals in place before the CAB request |
| E08 | Testing and parity | 2 Nov 2026 | 23 Dec 2026 | 8 | 34 | UAT signed off; parity accepted; no open Sev1/Sev2 |
| E09 | Business engagement and showcase | 12 Oct 2026 | 23 Dec 2026 | 10 | 21 | Showcase held 30 Nov; reviewers trained before go-live |
| E10 | Go-live and support | 14 Dec 2026 | 15 Jan 2027 | 8 | 18 | Live on 14 Jan with no open Sev1/Sev2; support in place |
