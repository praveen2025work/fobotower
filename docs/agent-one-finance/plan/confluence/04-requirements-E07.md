# E07 Governance, approvals and controls

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E07 | Risk and controls | 6 Oct 2026 to 28 Dec 2026 | In Progress |

**Objective:** Every approval and artefact AOF needs (TAC, ARB, CAF, CDO, DAIP, CARA, DPIA, AI risk) approved before the CAB request; controls built and tested. One team member owns the approvals.

**Deliverables:** Artefact register; TAC, ARB, CAF, CDO, DAIP and CARA approvals; DPIA; AI and model risk assessment; posting controls; security scans; penetration test; access review

**Exit criteria:** All approvals and artefacts approved before the CAB request on 18 Dec

**Dependencies:** Forum calendars (TAC, ARB, CAF, CDO, DAIP, CARA); Risk and Security teams

**Current state:** Governance lead building the artefact register and booking TAC, ARB, CAF, CDO, DAIP and CARA dates

## Stories

### E07-S58 Artefact register and approval calendar

As a governance lead, I want every artefact, its approver, forum and date in one register, so that no approval is missed or late for the CAB request.

Every artefact that needs approval (design, DPIA, risk assessments, test evidence, runbook, support model, CAB pack), its approver, the forum (TAC, ARB, CAF, CDO, DAIP, CARA) and its date. Kept by the governance lead and reviewed at each steerco.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 2 | Highest | Governance lead | - | In Progress |

**Acceptance criteria**

- Done when: Register agreed; forum dates booked

### E07-S59 TAC approval

As a governance lead, I want TAC approval for AOF, so that the design is approved before we build on it.

Prepare the TAC pack (architecture, hosting on AWS next to the Agent One API, data flows); present; record conditions as stories.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | Governance lead / Architect | - | To Do |

**Acceptance criteria**

- Done when: TAC approval; conditions in Jira

**Blocked by:** E07-S58

### E07-S60 Architecture review (ARB)

As an architect, I want the architecture approved by ARB, so that the design is accepted before we build on it.

Present the architecture and controls; record conditions.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | Architect / Governance lead | - | To Do |

**Acceptance criteria**

- Done when: ARB approval; conditions added as stories

**Blocked by:** E03-S21

### E07-S61 DPIA and data classification

As a risk officer, I want a DPIA and data classification, so that data use is approved.

Data flows, what the model sees, masking, retention.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 5 | Highest | Governance lead / Risk | - | To Do |

**Acceptance criteria**

- Done when: DPIA approved

### E07-S62 DAIP approval

As a governance lead, I want DAIP approval for AOF's use of AI, so that the AI use is approved.

Submit AOF's AI use (approved model, data sent to it, a person decides every outcome, evaluations, off switches) to DAIP.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | Highest | Governance lead | - | To Do |

**Acceptance criteria**

- Done when: DAIP approval recorded

**Blocked by:** E03-S20

### E07-S63 AI and model risk assessment

As a risk officer, I want an AI and model risk assessment, so that the bank accepts the residual risk.

People decide every outcome; evaluations; off switches; audit trail.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 5 | Highest | Governance lead / Risk | - | To Do |

**Acceptance criteria**

- Done when: Risk acceptance recorded

### E07-S64 Protect the model from instructions hidden in data

As a risk officer, I want text from source systems treated as data only, so that no one can steer the model through the data.

Text from source systems is treated as data, never as instructions.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a break comment containing an instruction, when the case runs, then the group goes to a person and nothing is proposed automatically.
- Done when: Test cases with hidden instructions go to a person

### E07-S65 Security scans clean

As a risk officer, I want code and dependency scans clean, so that no known vulnerabilities go live.

Code and dependency scans.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 2 | Highest | DevOps / Backend | - | To Do |

**Acceptance criteria**

- Done when: No open high or critical findings

### E07-S66 CDO approval

As a governance lead, I want CDO approval for the data AOF reads and keeps, so that data use is approved.

Submit the data AOF reads and keeps (MB Rec breaks, MOTIF bookings, FAS postings), its lineage and retention, to CDO.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | Highest | Governance lead | - | To Do |

**Acceptance criteria**

- Done when: CDO approval recorded

**Blocked by:** E07-S61

### E07-S67 CARA

As a governance lead, I want the CARA completed and its findings closed, so that the security risk is accepted before go-live.

Complete the CARA for AOF with the security team; track findings to closure.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 5 | Highest | Governance lead / Security | - | To Do |

**Acceptance criteria**

- Done when: CARA approved; findings closed or accepted

**Blocked by:** E07-S65

### E07-S68 Controls for posting adjustments

As a risk officer, I want posting controls signed off, so that postings to MOTIF are safe.

Reviewer approval, release by a different person, limits, posted once, full audit.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | Highest | Risk / BA | - | To Do |

**Acceptance criteria**

- Done when: Signed by Risk and the FOBO controllers' lead

**Blocked by:** E04-S32

### E07-S69 Audit trail cannot be changed

As a risk officer, I want an audit trail that cannot be changed, so that it stands as evidence.

Confirm database controls, or add protection.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | High | Architect / Backend | - | To Do |

**Acceptance criteria**

- Done when: Evidence recorded

### E07-S70 CAF approval

As a governance lead, I want CAF approval for AOF, so that the release can go to CAB.

Complete and submit the CAF for AOF; track to approval.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Highest | Governance lead | - | To Do |

**Acceptance criteria**

- Done when: CAF approval recorded

**Blocked by:** E07-S58

### E07-S71 Penetration test on UAT

As a risk officer, I want a penetration test with no open high findings, so that the service is safe to go live.

Book the slot in Sprint 3; run it in Sprint 6; fix findings.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Highest | Security | UAT | To Do |

**Acceptance criteria**

- Done when: No open high findings

**Blocked by:** E02-S15

### E07-S72 Access and segregation-of-duties review

As a risk officer, I want access and segregation of duties reviewed, so that no one can approve and release the same posting.

FOBO controllers who review, those who release, owners.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 2 | High | Risk / BA | UAT | To Do |

**Acceptance criteria**

- Done when: Review signed

### E07-S73 All artefacts approved before the CAB request

As a governance lead, I want every artefact in the register approved, with evidence, so that the CAB request is complete.

Every artefact in the register approved, with evidence linked in Confluence; CAB pack assembled.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 7 | R2 Go-live | 3 | Highest | Governance lead | - | To Do |

**Acceptance criteria**

- Done when: Register shows every artefact approved

**Blocked by:** E07-S59, E07-S60, E07-S61, E07-S66, E07-S62, E07-S63, E07-S67, E07-S70

