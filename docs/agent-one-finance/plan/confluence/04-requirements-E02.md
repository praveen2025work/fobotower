# E02 Build and environments (UAT, Prod)

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E02 | Platform | 12 Oct 2026 to 11 Dec 2026 | In Progress |

**Objective:** A working build, deployed through a pipeline to UAT and Prod

**Deliverables:** Build fixed and current, pipeline with tests and scans, UAT environment, reviewer console, Prod environment before the freeze

**Exit criteria:** The same build runs in UAT and Prod; Prod ready by 11 Dec

**Dependencies:** Platform and network requests approved

**Current state:** Build set up; deployment failing on a missing package, fix in progress; latest AOF version applied

## Stories

### E02-S08 Fix the build and deploy (deployment currently failing)

As a platform engineer, I want the build fixed and deploying cleanly, so that the team can deliver changes to UAT.

The build is set up; the deployment fails because a Python package is missing from the image. Fix it in the build and redeploy.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 3 | Highest | DevOps / Backend | UAT | In Progress |

**Acceptance criteria**

- Given the build pipeline, when a release is deployed, then the service starts and passes its health check.
- Done when: Deployment healthy

### E02-S09 Bring the codebase to the latest AOF version and keep it current

As a platform engineer, I want the codebase on the latest AOF version, so that we get fixes and features without drift.

Latest AOF update applied; apply each new update as it arrives and keep our own changes.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 2 | Highest | Backend | - | In Progress |

**Acceptance criteria**

- Done when: On the latest version; tests pass

### E02-S10 Request the UAT and Prod platform (long lead)

As a platform engineer, I want the UAT and Prod platform requested now, so that Prod is ready before 11 Dec.

Raise both requests now; Prod must be ready by 11 Dec.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 1 | Highest | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Done when: Both approved with dates

### E02-S11 Request network access to MB Rec, MOTIF, FAS and the LLM gateway (long lead)

As a platform engineer, I want network access to MB Rec, MOTIF, FAS and the LLM gateway, so that the connections work in UAT and Prod.

Firewall rules for UAT and Prod.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S0 Mobilise | R1 Working version | 2 | Highest | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Done when: Rules approved

### E02-S12 Build pipeline with tests and security scans

As a platform engineer, I want every change built, tested and scanned, so that only safe changes reach UAT and Prod.

Every change is built, tested and scanned before it can be deployed.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S1 | R1 Working version | 5 | Highest | DevOps | - | To Do |

**Acceptance criteria**

- Given a change with a failing test, when the pipeline runs, then the release is stopped.
- Done when: Pipeline green; a failing test stops the release

### E02-S13 Build the UAT environment

As a platform engineer, I want a UAT environment with database, secrets and single sign-on, so that Product Control can test on real data.

Database, secrets, single sign-on, web address.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S1 | R1 Working version | 5 | Highest | DevOps | UAT | To Do |

**Acceptance criteria**

- Given the pipeline, when a release is promoted to UAT, then it deploys and a reviewer can sign in.
- Done when: Release deployed to UAT by the pipeline

**Blocked by:** E02-S10

### E02-S14 Deploy the reviewer console to UAT

As a Product Control reviewer, I want the reviewer console in UAT, so that I can review cases on screen.

The screens reviewers use, behind single sign-on.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | Highest | DevOps / Frontend | UAT | To Do |

**Acceptance criteria**

- Given I am a provisioned reviewer, when I open the console in UAT, then I see my inbox after single sign-on.
- Done when: Reviewers open the console in UAT

**Blocked by:** E02-S13

### E02-S15 Promote releases from UAT to Prod through the pipeline

As a platform engineer, I want the same build promoted from UAT to Prod with an approval gate, so that Prod runs exactly what was tested.

Same build, approval gate before Prod.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S2 | R1 Working version | 3 | High | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Given a release signed off in UAT, when it is promoted, then Prod gets the same build only after approval.
- Done when: Approval gate works

**Blocked by:** E02-S12

### E02-S16 Build the Prod environment before the freeze

As a platform engineer, I want the Prod environment ready by 11 Dec, so that we can release on 5 Jan without a freeze breach.

Database, secrets, single sign-on, web address; ready by 11 Dec. The application is released after the freeze.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 5 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Given the Prod platform, when the smoke test runs, then it passes before 11 Dec.
- Done when: Prod smoke test passes

**Blocked by:** E02-S10

### E02-S17 Backups and restore tested

As a support analyst, I want backups with a tested restore, so that we can recover from data loss.

Database backups and a tested restore.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| S4 UAT-1 | R2 Go-live | 3 | High | DevOps | UAT/Prod | To Do |

**Acceptance criteria**

- Given a backup, when we restore it to UAT, then the cases and audit trail are complete.
- Done when: Restore tested

