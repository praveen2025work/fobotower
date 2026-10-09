# E06 Agent One Finance Diagnostics

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E06 | Diagnostics | 22 Sep 2026 to 11 Jan 2027 | In Progress |

**Objective:** Diagnostics service reading Phoenix traces, hosted outside AWS/BCP, improved each sprint

**Deliverables:** Diagnostics core, hosting outside AWS/BCP, its own pipeline, UAT and Prod deployments, quality check against Phoenix, improvements

**Exit criteria:** Running in Prod; results match Phoenix

**Dependencies:** Hosting outside AWS/BCP; Phoenix read access

**Current state:** Sprint 1: about 70% built; Sprint 2: remaining items, own pipeline and deployment

## Stories

### E06-S48 Build the Diagnostics core (Phoenix scraper)

As a support analyst, I want agent runs, model calls, errors and cost read from Phoenix traces, so that I can see how the agents run.

Reads Phoenix traces and shows agent runs, model calls, errors and cost. About 70% of the planned Diagnostics was built in Sprint 1.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 1 | R1 Working version | 8 | Highest | Backend | - | Done |

**Acceptance criteria**

- Done when: Core running on test traces

### E06-S49 Confirm hosting outside AWS/BCP

As an architect, I want Diagnostics hosting outside AWS/BCP approved, so that it can be deployed.

Agree the platform and its approvals.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 2 | Highest | Architect / DevOps | - | In Progress |

**Acceptance criteria**

- Done when: Hosting approved

### E06-S50 Diagnostics: finish the remaining 30%

As a support analyst, I want the open Diagnostics items finished, so that Diagnostics is complete enough for UAT.

The items still open after Sprint 1, in priority order.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 5 | Highest | Backend | - | In Progress |

**Acceptance criteria**

- Done when: Agreed items done

**Blocked by:** E06-S48

### E06-S51 Own build pipeline and read-only Phoenix access

As a platform engineer, I want a separate pipeline and read-only Phoenix access, so that Diagnostics is released safely.

Separate from the AOF build; read-only account; secrets stored safely.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 3 | High | DevOps | - | In Progress |

**Acceptance criteria**

- Done when: Pipeline green; Phoenix readable

### E06-S52 Deploy Diagnostics to UAT

As a support analyst, I want Diagnostics running in UAT, so that we see agent health during UAT.

Outside AWS/BCP.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | DevOps | UAT | To Do |

**Acceptance criteria**

- Done when: Runs on schedule in UAT

**Blocked by:** E06-S49, E06-S51

### E06-S53 Quality check: results match Phoenix

As a support analyst, I want Diagnostics results reconciled with Phoenix, so that I can trust what it shows.

Compare counts, timings, errors and costs with Phoenix for sample cases.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | Backend / QA | - | To Do |

**Acceptance criteria**

- Given sample cases, when Diagnostics and Phoenix are compared, then counts, timings, errors and costs match.
- Done when: Reconciliation report; defects logged

### E06-S54 Tests, data checks and security review

As a risk officer, I want Diagnostics tested and reviewed, so that finance data in traces is protected.

Automated checks; confirm finance data in traces is masked.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | High | Backend / Risk | - | To Do |

**Acceptance criteria**

- Done when: Checks run; review signed

### E06-S55 Diagnostics views for the showcase

As a delivery lead, I want Diagnostics views for the showcase, so that the Business sees how the agent runs.

Run health, model calls, cost per case.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Done when: Shown on 30 Nov

**Blocked by:** E06-S52

### E06-S56 Improvements from the quality review and UAT feedback

As a support analyst, I want the top improvements made, so that Diagnostics gets better each sprint.

Next items from the priority list.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Done when: Agreed items done

### E06-S57 Deploy Diagnostics to Prod

As a support analyst, I want Diagnostics running in Prod, so that we see agent health after go-live.

After the freeze, in the same release window.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 8 | R2 Go-live | 2 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Done when: Runs in Prod; results match Phoenix

**Blocked by:** E10-S96

