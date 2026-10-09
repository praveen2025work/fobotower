# E05 FOBO (Helix) set-up with Product Control

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E05 | FOBO | 20 Oct 2026 to 30 Nov 2026 | To Do |

**Objective:** FOBO Prime and Rates configured and confirmed by Product Control

**Deliverables:** Thresholds, checks and verdicts, sign-off checklist, owners, which verdicts post adjustments

**Exit criteria:** Product Control confirms the set-up

**Dependencies:** Product Control time; MB Rec data

## Stories

### E05-S40 Confirm thresholds and parameters with Product Control

As a Product Control reviewer, I want materiality, tolerances and ageing confirmed, so that the checks use our values.

Materiality, tolerances, ageing.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | BA / Product Control | - | To Do |

**Acceptance criteria**

- Done when: Values signed

### E05-S41 Set up FOBO Prime

As a Product Control reviewer, I want FOBO Prime set up on AOF, so that Prime breaks are investigated end to end.

Books, reviewers, owners.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 5 | Highest | BA / Backend | UAT | To Do |

**Acceptance criteria**

- Given a Prime book and date, when the case runs, then each break group has a proposal ready for review.
- Done when: A Prime case runs end to end in UAT

**Blocked by:** E05-S40, E04-S32

### E05-S42 Review checks, categories and verdicts with Product Control

As a Product Control reviewer, I want each check, category and verdict reviewed, so that the outcomes match how we work.

Each check, the verdict table and its guards.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 5 | Highest | BA / Product Control | - | To Do |

**Acceptance criteria**

- Done when: Product Control confirms or changes each one

### E05-S43 Sign-off checklist and reviewer answers

As a Product Control reviewer, I want a sign-off checklist, so that every approval meets the same standard.

What a reviewer must confirm before approving.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 2 | High | BA | UAT | To Do |

**Acceptance criteria**

- Given a proposal, when I approve it, then the required checklist answers are recorded.
- Done when: Reviewer completes the checklist in UAT

### E05-S44 Set up FOBO Rates

As a Product Control reviewer, I want FOBO Rates set up on AOF, so that Rates breaks are investigated end to end.

As Prime, for Rates books.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 5 | High | BA / Backend | UAT | To Do |

**Acceptance criteria**

- Given a Rates book and date, when the case runs, then each break group has a proposal ready for review.
- Done when: A Rates case runs end to end in UAT

**Blocked by:** E05-S41

### E05-S45 Which verdicts post an adjustment, and who releases it

As a Product Control reviewer, I want the verdicts that post adjustments and the releasing role set, so that posting follows our rules.

Link the verdicts to FAS posting; set the releasing role.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | Highest | BA / Product Control | UAT | To Do |

**Acceptance criteria**

- Given an approved POST verdict, when it is released by the releasing role, then an adjustment is posted.
- Done when: Shown working in UAT

**Blocked by:** E04-S33

### E05-S46 Owners and escalation routes

As a Product Control reviewer, I want owners and escalation routes set, so that questions reach the right people.

Who owns each category; who is asked for evidence.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | High | BA | UAT | To Do |

**Acceptance criteria**

- Done when: Questions and escalations reach the right people

### E05-S47 Turn on extra checks when MB Rec's new data arrives

As a Product Control reviewer, I want the extra checks on when MB Rec's data arrives, so that more breaks are explained.

History, systemic and trend checks.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Done when: Checks run in UAT

**Blocked by:** E04-S31

### E05-S48 Next-day follow-up and late breaks

As a Product Control reviewer, I want decisions re-checked the next day and late breaks in their own case, so that nothing is missed.

Re-check decisions on the next business day; late breaks get their own case.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | Medium | Backend / QA | UAT | To Do |

**Acceptance criteria**

- Given a decision that a break would clear, when the next business day runs, then the case shows whether it cleared.
- Done when: Shown in UAT

