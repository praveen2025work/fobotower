# E10 Go-live and support

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E10 | Go-live | 15 Dec 2026 to 25 Jan 2027 | To Do |

**Objective:** Safe release on 5 Jan and go-live on 14 Jan

**Deliverables:** Runbook, support model, CAB, Prod release, monitoring, parallel run, go/no-go

**Exit criteria:** Live on 14 Jan with no open Sev1/Sev2; support in place

**Dependencies:** CAB approval

## Stories

### E10-S85 Runbook and rollback plan

As a support analyst, I want a runbook and rollback plan, so that we can operate and back out safely.

Release, checks, rollback, what to do if a connection or the model is down.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 7 | R2 Go-live | 3 | Highest | DevOps / Backend | Prod | To Do |

**Acceptance criteria**

- Done when: Reviewed by Operations

### E10-S86 Support model

As a support analyst, I want an agreed support model, so that users know who to call.

Who answers what, and on-call.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 7 | R2 Go-live | 2 | Highest | PM / Operations | Prod | To Do |

**Acceptance criteria**

- Done when: Signed; support from go-live

### E10-S87 CAB request for 5 Jan

As a delivery lead, I want CAB approval for 5 Jan, so that we can release after the freeze.

With UAT, security, risk and runbook evidence; submitted by 18 Dec.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 7 | R2 Go-live | 2 | Highest | PM | Prod | To Do |

**Acceptance criteria**

- Done when: CAB approved

**Blocked by:** E08-S74, E07-S65, E08-S70

### E10-S88 Release to Prod on 5 Jan and smoke test

As a platform engineer, I want the signed-off build released to Prod on 5 Jan, so that the parallel run can start.

First working day after the freeze; no business use yet.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 8 | R2 Go-live | 2 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Given CAB approval, when the build is released on 5 Jan, then the smoke test passes.
- Done when: Smoke test passes

**Blocked by:** E10-S87, E02-S19

### E10-S89 Monitoring and alerts in Prod

As a support analyst, I want monitoring and alerts in Prod, so that problems are seen before users notice.

Health, connection down, spend limit, failed postings.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 8 | R2 Go-live | 3 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Given a connection down or a failed posting, when it happens, then on-call is alerted.
- Done when: Alerts reach on-call in a test

### E10-S90 Parallel run with today's process

As a Product Control reviewer, I want a week working both ways on agreed books, so that we go live with confidence.

Product Control works both ways on agreed books from 6 to 12 Jan.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 8 | R2 Go-live | 3 | Highest | Product Control / BA | Prod | To Do |

**Acceptance criteria**

- Done when: Parallel-run report

**Blocked by:** E10-S88

### E10-S91 Go/no-go and go-live

As a delivery lead, I want a go/no-go decision on 13 Jan, so that we go live on 14 Jan only if ready.

Go/no-go 13 Jan; live 14 Jan.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 9 | R2 Go-live | 1 | Highest | PM | Prod | To Do |

**Acceptance criteria**

- Done when: Go decision recorded

**Blocked by:** E10-S90

### E10-S92 Go-live communications and benefits tracking

As a delivery lead, I want go-live communications and a benefits report, so that users are informed and value is measured.

What changes for users; hours saved and agreement reported.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 9 | R2 Go-live | 2 | Medium | PM / BA | - | To Do |

**Acceptance criteria**

- Done when: Comms sent; first benefits report

