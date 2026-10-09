# E08 Testing and parity

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E08 | Testing | 2 Nov 2026 to 23 Dec 2026 | To Do |

**Objective:** Proof it works for Product Control at real volumes, and matches today's FOBO

**Deliverables:** Test plan, integration testing, parity check, performance test, UAT cycles 1 and 2

**Exit criteria:** UAT signed off; parity accepted; no open Sev1/Sev2

**Dependencies:** UAT environment and data

## Stories

### E08-S63 Test plan

As a QA lead, I want a test plan, so that testing covers what matters.

Functional, integration, refusals, limits, posting.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | High | QA | - | To Do |

**Acceptance criteria**

- Done when: Plan approved

### E08-S64 Integration testing in UAT

As a QA lead, I want end-to-end testing in UAT, so that the whole flow works.

End to end: MB Rec to AOF to review to FAS posting.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S3 Working version | R1 Working version | 5 | Highest | QA | UAT | To Do |

**Acceptance criteria**

- Given MB Rec breaks for a book, when the flow runs to review and FAS posting, then every step works with no Sev1/Sev2 open.
- Done when: No open Sev1/Sev2

**Blocked by:** E08-S63, E04-S33

### E08-S65 Parity check against today's FOBO

As a Product Control reviewer, I want AOF compared with today's FOBO on the same books and dates, so that I know where it differs.

Same books and dates through today's FOBO and AOF.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S3 Working version | R1 Working version | 5 | Highest | QA / Backend | UAT | To Do |

**Acceptance criteria**

- Done when: Parity report for Prime and Rates

**Blocked by:** E05-S38

### E08-S66 Agree and sign off the differences

As a Product Control reviewer, I want every difference explained and signed, so that parity is accepted.

Every difference explained; Product Control accepts or it is fixed.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 3 | Highest | BA / Product Control | - | To Do |

**Acceptance criteria**

- Done when: Signed list

**Blocked by:** E08-S65

### E08-S67 Performance test at end-of-day volumes

As a QA lead, I want a performance test at end-of-day volumes, so that cases are ready on time.

All books at once, model response times.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 5 | High | QA / Backend | UAT | To Do |

**Acceptance criteria**

- Given all books at end of day, when they run together, then every case is ready by the agreed time.
- Done when: Cases ready by the agreed time

### E08-S68 Evaluation set and agreement threshold

As a Product Control reviewer, I want an evaluation set and an agreed threshold, so that each change is checked against our decisions.

Decided UAT cases replayed after each change.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 3 | High | Backend / BA | UAT | To Do |

**Acceptance criteria**

- Done when: At or above the agreed threshold

### E08-S69 UAT cycle 1 with Product Control

As a Product Control reviewer, I want a first UAT cycle on real cases, so that defects are found early.

Real cases reviewed; defects triaged.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 5 | Highest | Product Control / QA | UAT | To Do |

**Acceptance criteria**

- Done when: Cycle 1 report

**Blocked by:** E08-S64

### E08-S70 UAT cycle 2 and sign-off

As a Product Control reviewer, I want a second UAT cycle and sign-off, so that we accept the service.

Retest fixes; sign-off.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S5 UAT-2 and readiness | R2 Go-live | 5 | Highest | Product Control / QA | UAT | To Do |

**Acceptance criteria**

- Done when: UAT signed off

**Blocked by:** E08-S69

