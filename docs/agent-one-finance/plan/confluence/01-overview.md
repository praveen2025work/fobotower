# Agent One Finance with the FOBO (Helix) use case: overview

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | What we are delivering, for whom, and by when |

## Summary

Core Agent One Finance, integrated with Agent One, investigates FOBO breaks from MB Rec for Product Control and posts approved adjustments to MOTIF through FAS. People decide every outcome; an adjustment is posted only after a reviewer approves it and a different person releases it.

## Key dates

| Date | What |
|---|---|
| 5 Oct 2026 | **M1 Diagnostics first version**: About 70% of Diagnostics built in Sprint 1; improvements and deployment continue |
| 19 Oct 2026 | **M2 AOF skeleton on AWS**: Orchestrator service, database and console at /agentone/finance running together on AWS |
| 16 Nov 2026 | **M3 FOBO Prime end to end in UAT**: Real MB Rec breaks investigated in their own Agent One session; MOTIF connected; FAS posting tested |
| 30 Nov 2026 | **M4 Working version showcase**: FOBO Prime and Rates on AOF in UAT, shown end to end with Diagnostics |
| 10 Dec 2026 | **M5 Prod ready before the freeze**: Prod environment and connections in place; no application deployed yet |
| 18 Dec 2026 | **M6 UAT, security and parity sign-off; CAB submitted**: UAT signed, penetration test closed, parity accepted, CAB request in for 5 Jan |
| 6 Jan 2027 | **M7 Released to Prod; parallel run**: Released 5 Jan after the freeze; parallel run with today's process from 6 Jan |
| 14 Jan 2027 | **M8 Go-live**: Product Control uses AOF for FOBO Prime and Rates |

Change freeze: 11 Dec 2026 to 4 Jan 2027 (no Production changes).

Sprints are two weeks, Tuesday to Monday. Sprint 1 (Diagnostics) is done, Sprint 2 (AOF skeleton on AWS) is under way, and Sprint 3 starts on 20 Oct 2026.

## Scope

**In:** FOBO Prime and Rates on AOF; MB Rec and MOTIF data; approved adjustments posted to MOTIF through FAS; Agent One sessions per capability per case; Agent One Finance Diagnostics; UAT and Prod.

**Out:** other use cases; CATS.

## Epics

| Jira | Epic | Team | Status |
|---|---|---|---|
| E01 | Programme and governance | PM / Architect | In Progress |
| E02 | AOF platform on AWS: skeleton, UAT and Prod | DevOps / Backend | In Progress |
| E03 | Agent One integration: sessions per capability per case | Backend | To Do |
| E04 | Data connections: MB Rec, MOTIF and FAS | Backend / DevOps | To Do |
| E05 | FOBO (Helix) set-up with Product Control | BA / Product Control | To Do |
| E06 | Agent One Finance Diagnostics | Backend / DevOps | In Progress |
| E07 | Security, risk and controls | Architect / Risk | To Do |
| E08 | Testing and parity | QA / Product Control | To Do |
| E09 | Business engagement and showcase | PM / BA | In Progress |
| E10 | Go-live and support | DevOps / PM | To Do |

## Child pages

Delivery plan · Ways of working · Requirements by epic · Decision log · RAID log
