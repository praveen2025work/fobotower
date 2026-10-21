# E03 Agent One integration: sessions per agent per task

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E03 | Agent One | 6 Oct 2026 to 30 Nov 2026 | To Do |

**Objective:** Agent One sessions are opened per agent per task (and per break group where needed), instead of per user login

**Deliverables:** Session design, per-task sessions in Agent One, task identity and data scope, session lifecycle, model approval, tracing, cost limits

**Exit criteria:** Each FOBO task has its own Agent One session, shared by everyone working the task; no session per login

**Dependencies:** Model and data approval; Agent One team

## Stories

### E03-S20 Confirm the approved model and data rules (long lead)

As a risk officer, I want the approved model and data rules confirmed, so that only approved data reaches the model.

Which model, which data may be sent to it, and what is masked.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 2 | Highest | Architect / Risk | - | To Do |

**Acceptance criteria**

- Done when: Written approval

### E03-S21 Agree the session design with the Agent One team

As an architect, I want the session design agreed with the Agent One team, so that sessions follow the task, not the user login.

Today Agent One opens a session per user login. Target: one session per agent per task (for example one per FOBO book and date), optionally one per break group inside the task. Agree the session key, who it runs as, how long it lives and what is kept.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 2 | Highest | Architect / Backend | - | To Do |

**Acceptance criteria**

- Done when: Design signed by the Agent One team and Architect

### E03-S22 Open an Agent One session per agent per task

As a FOBO controller, I want one Agent One session per agent per task, so that everyone working a task shares the same investigation.

When a task opens (by MB Rec's end-of-day trigger or by a person), AOF opens one Agent One session for that agent and task. Logging in no longer creates a session.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 5 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a FOBO task for a book and date, when two reviewers open it, then both use the same session.
- Given two different tasks, when they run, then they never share a session.
- Given a user, when they log in, then no session is created.
- Done when: Two people on the same task use the same session; two tasks never share one; no session per login

**Blocked by:** E03-S21, E03-S20

### E03-S23 Session runs with the task's rights, not the user's

As a risk officer, I want each session to run with the task's identity and book scope, so that a session can only read that task's books.

The session uses the task's own identity and book scope (a service identity for tasks opened automatically), so it only reads that task's books.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a session for book A, when it asks for book B's data, then the request is refused and audited.
- Done when: A session cannot read another book; refusals are audited

**Blocked by:** E03-S22

### E03-S24 Trace every model and system call by task

As a support analyst, I want every model and system call traceable by task number, so that I can explain any outcome.

Each task's session can be traced end to end by its task number.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | High | Backend / DevOps | UAT | To Do |

**Acceptance criteria**

- Given a task number, when I search the traces, then I see every model and system call for it.
- Done when: Trace found by task number

### E03-S25 Session per break group (where needed)

As a FOBO controller, I want large tasks investigated in parallel by break group, so that results are ready sooner.

Large tasks can use one session per break group so groups are investigated in parallel, still under the same task.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Given a task with several break groups, when it runs, then groups are investigated in parallel under the same task.
- Done when: Groups of one task run in parallel in UAT

**Blocked by:** E03-S22

### E03-S26 Session lifecycle: resume, close and keep the record

As a support analyst, I want sessions that resume, close at sign-off and keep their record, so that no work is lost and audit is complete.

A session resumes if a task is re-run or the service restarts, closes when the task is signed off, and its record stays with the task for audit.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Given a task interrupted by a restart, when it is re-run, then the session resumes.
- Given a signed-off task, when the session closes, then its record stays with the task.
- Done when: Resume and close shown in UAT; record kept on the task

**Blocked by:** E03-S22

### E03-S27 Cost limits and off switches per agent and task

As a delivery lead, I want cost limits and off switches, so that spend is controlled and we can stop safely.

Daily and per-task limits; FOBO and each connection can be switched off.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 2 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Given a task over its limit, when it reaches the model step, then it goes to a person instead.
- Given FOBO switched off, when a task would open, then nothing runs.
- Done when: Over limit goes to a person; switch-off tested

### E03-S28 Run the FOBO skill in the task's session

As a FOBO controller, I want the controllers' FOBO skill run in the task's session, so that we can compare it with the step-by-step set-up.

The controllers' skill runs end to end in the task's session, as an option to the step-by-step set-up.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | Medium | Backend | UAT | To Do |

**Acceptance criteria**

- Done when: One task runs in UAT

**Blocked by:** E03-S22

### E03-S29 Real-model evaluation on decided tasks

As a FOBO controller, I want the real model checked against tasks we already decided, so that we trust its proposals.

Replay tasks the FOBO controllers decided and compare.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | High | Backend / BA | UAT | To Do |

**Acceptance criteria**

- Done when: Agreement recorded; differences reviewed

**Blocked by:** E03-S22

