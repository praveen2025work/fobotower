# E07 Security, risk and controls

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E07 | Risk and controls | 20 Oct 2026 to 14 Dec 2026 | To Do |

**Objective:** All approvals for an AI system that reads finance data and posts adjustments

**Deliverables:** DPIA, AI risk assessment, posting controls, security scans, penetration test, access review

**Exit criteria:** All approvals in place before the CAB request

**Dependencies:** Risk and security teams

## Stories

### E07-S59 DPIA and data classification

As a risk officer, I want a DPIA and data classification, so that data use is approved.

Data flows, what the model sees, masking, retention.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 5 | Highest | Architect / Risk | - | To Do |

**Acceptance criteria**

- Done when: DPIA approved

### E07-S60 AI and model risk assessment

As a risk officer, I want an AI and model risk assessment, so that the bank accepts the residual risk.

People decide every outcome; evaluations; off switches; audit trail.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 5 | Highest | Architect / Risk | - | To Do |

**Acceptance criteria**

- Done when: Risk acceptance recorded

### E07-S61 Protect the model from instructions hidden in data

As a risk officer, I want text from source systems treated as data only, so that no one can steer the model through the data.

Text from source systems is treated as data, never as instructions.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a break comment containing an instruction, when the case runs, then the group goes to a person and nothing is proposed automatically.
- Done when: Test cases with hidden instructions go to a person

### E07-S62 Security scans clean

As a risk officer, I want code and dependency scans clean, so that no known vulnerabilities go live.

Code and dependency scans.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 2 | Highest | DevOps / Backend | - | To Do |

**Acceptance criteria**

- Done when: No open high or critical findings

### E07-S63 Controls for posting adjustments

As a risk officer, I want posting controls signed off, so that postings to MOTIF are safe.

Reviewer approval, release by a different person, limits, posted once, full audit.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | Highest | Risk / BA | - | To Do |

**Acceptance criteria**

- Done when: Signed by Risk and Product Control

**Blocked by:** E04-S33

### E07-S64 Audit trail cannot be changed

As a risk officer, I want an audit trail that cannot be changed, so that it stands as evidence.

Confirm database controls, or add protection.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | High | Architect / Backend | - | To Do |

**Acceptance criteria**

- Done when: Evidence recorded

### E07-S65 Penetration test on UAT

As a risk officer, I want a penetration test with no open high findings, so that the service is safe to go live.

Book the slot in Sprint 3; run it in Sprint 6; fix findings.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Highest | Security | UAT | To Do |

**Acceptance criteria**

- Done when: No open high findings

**Blocked by:** E02-S16

### E07-S66 Access and segregation-of-duties review

As a risk officer, I want access and segregation of duties reviewed, so that no one can approve and release the same posting.

Reviewers, releasers, owners.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 2 | High | Risk / BA | UAT | To Do |

**Acceptance criteria**

- Done when: Review signed

