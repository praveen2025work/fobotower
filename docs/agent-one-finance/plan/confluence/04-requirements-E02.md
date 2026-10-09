# E02 AOF platform on AWS: skeleton, UAT and Prod

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E02 | Platform | 6 Oct 2026 to 14 Dec 2026 | In Progress |

**Objective:** The AOF orchestrator, its database and the reviewer console running on AWS, deployed through the pipeline to UAT and Prod

**Deliverables:** AOF database (Postgres with pgvector), AOF orchestrator service, console at /agentone/finance, one way to take each AOF release, pipeline with tests and scans, UAT, Prod before the freeze

**Exit criteria:** The same build runs in UAT and Prod; Prod ready by 10 Dec

**Dependencies:** Platform and network requests approved

**Current state:** Sprint 2: database set up on AWS; AOF orchestrator deployment and the end-to-end skeleton in progress

## Stories

### E02-S07 Set up the AOF database on AWS (Postgres with pgvector)

As a platform engineer, I want the AOF database on AWS with pgvector, so that AOF can keep its cases, audit trail and knowledge.

The AOF database with the pgvector extension.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 3 | Highest | DevOps | UAT | Done |

**Acceptance criteria**

- Done when: Database reachable from the AOF service; pgvector enabled

### E02-S08 Deploy the AOF orchestrator service to AWS

As a platform engineer, I want the AOF orchestrator running as its own service on AWS, so that the team can deliver changes to UAT.

Its own ECS service from the AOF image (port 8300), health check, database settings from the secrets store. The missing-package failure in the image is fixed.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 5 | Highest | DevOps / Backend | UAT | In Progress |

**Acceptance criteria**

- Given a release from the pipeline, when it is deployed, then the service starts and passes its health check.
- Done when: Service healthy on AWS; health check and sign-in check answer

**Blocked by:** E02-S07

### E02-S09 AOF skeleton end to end on AWS

As a FOBO controller, I want the console, orchestrator and database working together on AWS, so that we can see AOF run before the connections arrive.

The console at /agentone/finance, the AOF service and the database working together; a sample case runs on test data.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 3 | Highest | Backend / Frontend | UAT | In Progress |

**Acceptance criteria**

- Given a sample case on test data, when it is opened in the console at /agentone/finance, then it runs and can be reviewed.
- Done when: A sample case opens, runs and is reviewed on AWS

**Blocked by:** E02-S08

### E02-S10 Request the Prod platform (long lead)

As a platform engineer, I want the Prod platform requested now, so that Prod is ready by 10 Dec.

UAT runs on AWS today. Raise the Prod request now; Prod must be ready by 10 Dec.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 1 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Done when: Approved with dates

### E02-S11 Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)

As a platform engineer, I want network access to MB Rec, MOTIF, FAS and the LLM gateway, so that the connections work in UAT and Prod.

Firewall rules for UAT and Prod.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 2 | Highest | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Done when: Rules approved

### E02-S12 Settle the AOF database migrations

As a platform engineer, I want the AWS database on AOF's migration history, so that every release can change the database safely.

Line up the AWS database with AOF's migration history, then run migrations before every deployment.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 2 | Highest | Backend / DevOps | UAT | To Do |

**Acceptance criteria**

- Given a release with a database change, when it is deployed, then the migration runs first and there is one migration head.
- Done when: One migration head; migrations run in the pipeline

**Blocked by:** E02-S07

### E02-S13 Take each AOF release the same way (sync tool)

As a platform engineer, I want each AOF release taken with the sync tool instead of a hand conversion, so that updates are quick, complete and keep our own changes.

Replace the hand-converted console and backend with the generated release and the sync tool. Our own changes (sign-on, connections) are kept on every update.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | Frontend / Backend | UAT | To Do |

**Acceptance criteria**

- Given a new AOF release, when the sync tool runs, then the console and backend are updated and our sign-on and connection settings are kept.
- Done when: Console at /agentone/finance on the latest release, with its styles and icons; an update is one sync run

### E02-S14 Build pipeline with tests and security scans

As a platform engineer, I want every change built, tested and scanned, so that only safe changes reach UAT and Prod.

Every change is built, tested and scanned before it can be deployed.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 5 | Highest | DevOps | - | To Do |

**Acceptance criteria**

- Given a change with a failing test, when the pipeline runs, then the release is stopped.
- Done when: Pipeline green; a failing test stops the release

### E02-S15 Complete the UAT environment

As a platform engineer, I want UAT complete with single sign-on, secrets and connections, so that the FOBO controllers can test on real data.

Single sign-on, secrets, web address and connections for the AOF service and console.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | DevOps | UAT | To Do |

**Acceptance criteria**

- Given the pipeline, when a release is promoted to UAT, then it deploys and a reviewer can sign in.
- Done when: Release deployed to UAT by the pipeline; a reviewer signs in

**Blocked by:** E02-S08

### E02-S16 Deploy the reviewer console to UAT

As a FOBO controller, I want the reviewer console in UAT, so that I can review cases on screen.

The screens reviewers use, at /agentone/finance behind single sign-on.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 2 | Highest | DevOps / Frontend | UAT | To Do |

**Acceptance criteria**

- Given I am a provisioned reviewer, when I open /agentone/finance in UAT, then I see my inbox after single sign-on.
- Done when: Reviewers open the console in UAT

**Blocked by:** E02-S15

### E02-S17 Promote releases from UAT to Prod through the pipeline

As a platform engineer, I want the same build promoted from UAT to Prod with an approval gate, so that Prod runs exactly what was tested.

Same build, approval gate before Prod.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | High | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Given a release signed off in UAT, when it is promoted, then Prod gets the same build only after approval.
- Done when: Approval gate works

**Blocked by:** E02-S14

### E02-S18 Build the Prod environment before the freeze

As a platform engineer, I want the Prod environment ready by 10 Dec, so that we can release on 5 Jan without a freeze breach.

Database, secrets, single sign-on, web address; ready by 10 Dec. The application is released after the freeze.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 5 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Given the Prod platform, when the smoke test runs, then it passes by 10 Dec.
- Done when: Prod smoke test passes

**Blocked by:** E02-S10

### E02-S19 Backups and restore tested

As a support analyst, I want backups with a tested restore, so that we can recover from data loss.

Database backups and a tested restore.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | High | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Given a backup, when we restore it to UAT, then the cases and audit trail are complete.
- Done when: Restore tested

