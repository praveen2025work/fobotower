# E08 Testing and parity with the FOBO controllers

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E08 | Testing | 3 Nov 2026 to 28 Dec 2026 | To Do |

**Objective:** Proof, by the FOBO controllers who run the use case, that it works at real volumes and matches today's FOBO

**Deliverables:** Test plan, test books and dates, integration testing, parity check, performance test, UAT cycles 1 and 2 run by the FOBO controllers

**Exit criteria:** FOBO controllers sign off UAT; parity accepted; no open Sev1/Sev2

**Dependencies:** FOBO controllers' time; UAT environment and data

## Stories

### E08-S74 Test plan

As a QA lead, I want a test plan, so that testing covers what matters.

Functional, integration, refusals, limits, posting; which FOBO controllers test what, and when.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | High | QA / FOBO controllers | - | To Do |

**Acceptance criteria**

- Done when: Plan approved by the FOBO controllers' lead

### E08-S75 FOBO controllers' test books and dates

As a FOBO controller, I want the test books and dates chosen with us, with outcomes we already know, so that UAT and parity prove AOF on our own work.

Prime and Rates books and business dates for UAT and parity, with the outcomes the controllers already know.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 2 | Highest | FOBO controllers / BA | UAT | To Do |

**Acceptance criteria**

- Done when: Test data agreed with the FOBO controllers

**Blocked by:** E09-S83

### E08-S76 Integration testing in UAT

As a QA lead, I want end-to-end testing in UAT, so that the whole flow works.

End to end: MB Rec to AOF to review to FAS posting.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 5 | Highest | QA | UAT | To Do |

**Acceptance criteria**

- Given MB Rec breaks for a book, when the flow runs to review and FAS posting, then every step works with no Sev1/Sev2 open.
- Done when: No open Sev1/Sev2

**Blocked by:** E08-S74, E04-S36

### E08-S77 Parity check against today's FOBO

As a FOBO controller, I want AOF compared with today's FOBO on the same books and dates, so that I know where it differs.

Same books and dates through today's FOBO and AOF; the FOBO controllers compare the outcomes.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 5 | Highest | FOBO controllers / QA | UAT | To Do |

**Acceptance criteria**

- Done when: Parity report for Prime and Rates

**Blocked by:** E05-S40

### E08-S78 FOBO controllers sign off the differences

As a FOBO controller, I want every difference explained and signed, so that parity is accepted.

Every difference explained; the FOBO controllers accept it or it is fixed.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Highest | FOBO controllers / BA | - | To Do |

**Acceptance criteria**

- Done when: Signed list

**Blocked by:** E08-S77

### E08-S79 Performance test at end-of-day volumes

As a QA lead, I want a performance test at end-of-day volumes, so that cases are ready on time.

All books at once, model response times.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 5 | High | QA / Backend | UAT | To Do |

**Acceptance criteria**

- Given all books at end of day, when they run together, then every case is ready by the agreed time.
- Done when: Cases ready by the agreed time

### E08-S80 Evaluation set and agreement threshold

As a FOBO controller, I want an evaluation set and an agreed threshold, so that each change is checked against our decisions.

Cases the FOBO controllers decided in UAT, replayed after each change.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | High | Backend / FOBO controllers | UAT | To Do |

**Acceptance criteria**

- Done when: At or above the agreed threshold

### E08-S81 UAT cycle 1 with the FOBO controllers

As a FOBO controller, I want a first UAT cycle on real cases, so that defects are found early.

The FOBO controllers review real cases for their books; defects triaged.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 5 | Highest | FOBO controllers / QA | UAT | To Do |

**Acceptance criteria**

- Done when: Cycle 1 report

**Blocked by:** E08-S76

### E08-S82 UAT cycle 2 and the FOBO controllers' sign-off

As a FOBO controller, I want a second UAT cycle and sign-off, so that we accept the service.

The FOBO controllers retest fixes and sign off.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 7 | R2 Go-live | 5 | Highest | FOBO controllers / QA | UAT | To Do |

**Acceptance criteria**

- Done when: UAT signed off by the FOBO controllers' lead

**Blocked by:** E08-S81

