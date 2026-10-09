# E03 Agent One integration: sessions per capability per case

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E03 | Agent One | 12 Oct 2026 to 27 Nov 2026 | To Do |

**Objective:** Agent One sessions are opened per capability per case (and per break group where needed), instead of per user login

**Deliverables:** Session design, per-case sessions in Agent One, case identity and data scope, session lifecycle, model approval, tracing, cost limits

**Exit criteria:** Each FOBO case has its own Agent One session, shared by everyone working the case; no session per login

**Dependencies:** Model and data approval; Agent One team

## Stories

### E03-S18 Confirm the approved model and data rules (long lead)

As a risk officer, I want the approved model and data rules confirmed, so that only approved data reaches the model.

Which model, which data may be sent to it, and what is masked.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 2 | Highest | Architect / Risk | - | To Do |

**Acceptance criteria**

- Done when: Written approval

### E03-S19 Agree the session design with the Agent One team

As an architect, I want the session design agreed with the Agent One team, so that sessions follow the case, not the user login.

Today Agent One opens a session per user login. Target: one session per capability per case (for example one per FOBO book and date), optionally one per break group inside the case. Agree the session key, who it runs as, how long it lives and what is kept.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 2 | Highest | Architect / Backend | - | To Do |

**Acceptance criteria**

- Done when: Design signed by the Agent One team and Architect

### E03-S20 Open an Agent One session per capability per case

As a Product Control reviewer, I want one Agent One session per capability per case, so that everyone working a case shares the same investigation.

When a case opens (by MB Rec's end-of-day trigger or by a person), AOF opens one Agent One session for that capability and case. Logging in no longer creates a session.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S1 | R1 Working version | 5 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a FOBO case for a book and date, when two reviewers open it, then both use the same session.
- Given two different cases, when they run, then they never share a session.
- Given a user, when they log in, then no session is created.
- Done when: Two people on the same case use the same session; two cases never share one; no session per login

**Blocked by:** E03-S19, E03-S18

### E03-S21 Session runs with the case's rights, not the user's

As a risk officer, I want each session to run with the case's identity and book scope, so that a session can only read that case's books.

The session uses the case's own identity and book scope (a service identity for cases opened automatically), so it only reads that case's books.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S1 | R1 Working version | 3 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a session for book A, when it asks for book B's data, then the request is refused and audited.
- Done when: A session cannot read another book; refusals are audited

**Blocked by:** E03-S20

### E03-S22 Session per break group (where needed)

As a Product Control reviewer, I want large cases investigated in parallel by break group, so that results are ready sooner.

Large cases can use one session per break group so groups are investigated in parallel, still under the same case.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Given a case with several break groups, when it runs, then groups are investigated in parallel under the same case.
- Done when: Groups of one case run in parallel in UAT

**Blocked by:** E03-S20

### E03-S23 Session lifecycle: resume, close and keep the record

As a support analyst, I want sessions that resume, close at sign-off and keep their record, so that no work is lost and audit is complete.

A session resumes if a case is re-run or the service restarts, closes when the case is signed off, and its record stays with the case for audit.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Given a case interrupted by a restart, when it is re-run, then the session resumes.
- Given a signed-off case, when the session closes, then its record stays with the case.
- Done when: Resume and close shown in UAT; record kept on the case

**Blocked by:** E03-S20

### E03-S24 Trace every model and system call by case

As a support analyst, I want every model and system call traceable by case number, so that I can explain any outcome.

Each case's session can be traced end to end by its case number.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | High | Backend / DevOps | UAT | To Do |

**Acceptance criteria**

- Given a case number, when I search the traces, then I see every model and system call for it.
- Done when: Trace found by case number

### E03-S25 Cost limits and off switches per capability and case

As a delivery lead, I want cost limits and off switches, so that spend is controlled and we can stop safely.

Daily and per-case limits; FOBO and each connection can be switched off.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 2 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Given a case over its limit, when it reaches the model step, then it goes to a person instead.
- Given FOBO switched off, when a case would open, then nothing runs.
- Done when: Over limit goes to a person; switch-off tested

### E03-S26 Run the FOBO skill in the case's session

As a Product Control reviewer, I want the controllers' FOBO skill run in the case's session, so that we can compare it with the step-by-step set-up.

The controllers' skill runs end to end in the case's session, as an option to the step-by-step set-up.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S3 Working version | R1 Working version | 3 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Done when: One case runs in UAT

**Blocked by:** E03-S20

### E03-S27 Real-model evaluation on decided cases

As a Product Control reviewer, I want the real model checked against cases we already decided, so that we trust its proposals.

Replay cases people decided and compare.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S3 Working version | R1 Working version | 3 | High | Backend / BA | UAT | To Do |

**Acceptance criteria**

- Done when: Agreement recorded; differences reviewed

**Blocked by:** E03-S20

