# Features by capability

**Date:** 2026-10-05

Every feature below is part of the platform. It is switched on and shaped by **configuration**
(the capability's YAML, or a team group's `set`, both editable in *Configure*), never by code
written for one team. The matrix shows how each capability in this repository uses each
feature, so a new team can see its options.

**Columns:**
- **FOBO Prime / FOBO Rates**: *Break investigation*, groups `fobo-prime` and `fobo-rates`
  (MB Rec's breaks).
- **Cash**: *Reconciliation investigation*, group `cash-bank-ledger` (bank vs ledger, matched by
  Agent One Finance).
- **Variance**: *P&L variance commentary*.
- **Report validation**: *Report validation*.

## The matrix

| Feature | Setting | FOBO Prime / Rates | Cash | Variance | Report validation |
|---|---|---|---|---|---|
| Item source | `items.load` / `match` | MB Rec's breaks (no re-matching) | Agent One Finance matches bank to ledger | GL balances vs budget (`compare`) | Agent One Finance matches the report workbook to GL balances |
| **Data steps** (steps v2) | `step_settings` | — | — | — | — |
| Join more data | `enrich` | MOTIF snapshots per instrument | — | — | — |
| Reference lookups | `resolve` | book → desk → escalation team, as of the COB | — | — | — |
| Playbook (checks, tests, categories, verdict table, guards) | `playbook` | the controllers' skill: R5, §8 scenarios, timing, end state, C1–C6, FO-1…BO-6, R2 | — (rules) | — (rules) | — |
| Rules | `rules` | — | write-off within limit; **not twice** (follow-through) | FX revaluation | rounding |
| Tollgate before the model | `pause_before`, `tollgates` | controller approves the classification, adds the desk's word | — | — | — |
| Model tools and specialists | `reasoning.tools`, `.specialists` | booking events, MB Rec history, **CATS and MOTIF trades** (§7); booking-events and **trade-level** specialists | counterparty history | journal lines, budget lines | journal lines, document list and PDF reader |
| **Answer in sections** | `reasoning.sections` | §12: root cause, hypotheses, tests not performed, verdict and why, remediation, control, end state (required ones enforced) | — | what drove it, one-off or recurring, action (optional) | — |
| Ask for evidence | `requests.targets` | desk (trader), Operations, CATS support | — (add targets to use) | — | — |
| **Chase questions** | `requests.remind_after_hours`, `.escalate_after_hours` | 2 h, then 4 h | — | — | — |
| **Answer with a file** | `requests.allow_attachments` | yes | yes (default) | yes (default) | yes (default) |
| **Sign-off checklist** | `review.checklist` | §14's questions, required, prefilled from tests, evidence, verdict, sections | write-off questions (optional) | three questions (optional) | — |
| Confirmation of unset thresholds (P1) | `playbook.verdict_policy`, `review.confirm` | Prime: all unset; Rates: materiality and policy confirmed | — | — | — |
| Late items | `case.late_items` | follow-up case with only the new breaks | ignore | ignore | ignore |
| **Follow-through** | `follow_through` | POST / CORRECT & RE-POST / MONITOR re-tested next COB: **BO + adj = FO** or stays open (U); MONITOR not cleared → K | an item decided yesterday and still open is not written off twice | — (could follow commentary month to month) | — |
| Recurring items | `insights.recurring` | same instrument, same book | — | — | — |
| **Unexplained items** | `insights.unexplained` | no check explained it, or H Novel (§9 feedback) | what no rule or the model settled | the same, over 90 days | — |
| **Rule candidates** | `insights.automation_after` | judgement calls approved unchanged 5× | 5× | an account's commentary approved unchanged 3× | default (5×) |
| **Data and parameters** | derived | MB Rec / MOTIF fields per check and test; thresholds to confirm | match fields, write-off limit | GL fields, materiality | workbook and GL fields |
| **Algorithm evidence** ([algorithms](algorithms.md)) | `step_settings` (offsets, subset_match, cluster, fuzzy_match, trend, anomaly robust) | wrong-instrument pairs, split bookings, the same break in several books, typo'd names in MOTIF, trend and how unusual; four new judgement categories N, O, S, Y | — | — | — |
| **Proposed checks** | `insights.automation_after` | conditions that predict the approved verdict, for the playbook's owners | yes | yes | — |
| Tickets | `escalation` | DO NOT POST, CORRECT & RE-POST, escalations → owning team | — | — | — |
| Write-back | `publish` | — | — | commentary to the reporting pack after release | a PDF report after release |
| Schedule / events | `case.opens_on` | event (MB Rec finishes a book) | schedule | schedule (2nd of the month) | manual |
| Deadline | `case.due` | 11:00 (Prime), 12:00 (Rates) next business day | per group | — | — |

**Bold** marks features added in this release.

## Steps v2: accruals, complaints, control testing

The same matrix for the example capabilities built from the step families
(steps v2, phases 2–6):
- **Accruals** is *Month-end accruals* (`fin.accruals`).
- **Complaints** is *Complaint handling* (`client.complaints`).
- **Control test** is *Control operating test* (`controls.operating-test`), with one
  `controls.sample-test` child case per sample.

| Feature | Setting | Accruals | Complaints | Control test |
|---|---|---|---|---|
| Item source | `items.load` | GRNI from the ledger | the day's complaints | the period's payment exceptions (the population) |
| Period open? | `period_check` | yes: a closed period stops the run | — | — |
| Reference data | `dataset` | chart of accounts; the delegated-authority matrix | internal watch list | — |
| Recompute | `recompute` | — | the fee from the tariff vs the fee charged | — |
| Journals | `propose_entries` | balanced per account, checked against the chart | — | — |
| Sampling | `sample` | — | — | 3, random, seed kept |
| Child cases and waiting | `spawn`, `await` | — | — | one per sample; continues when all are finished (72 h timeout) |
| Timeline, related cases | `timeline`, `link` | — | account events (the model reads them); the client's earlier complaints | — |
| Clocks | `clock` | — | final response: 40 business days, warned 5 days before | — |
| Screening | `screen` | — | watch list candidates (a person decides) | — |
| Messages | `compose`, `outreach` | — | acknowledgement per topic, sent after a handler approves | — |
| Authority | `review.authority_dataset` / `.authority` | from the bank's matrix: two reviewers over 250k, never in bulk | — | — |
| Reserved decisions | `boundaries` | — | redress above the limit: the complaints lead | — |
| Attestation | `attest` | — | — | the control owner, before review |
| Write-back | `post` / `publish` | journals posted after a financial controller releases them | — | — |
| Report | `report` | — | — | the test's PDF, kept with the case |

## Turning a feature on for another team

1. Open *Capabilities → name → Configure* (or the team group's page). Each feature is a field
   in the stage it belongs to:

   | Stage | Features |
   |---|---|
   | *Rules, then the model* | sections |
   | *Human review* | checklist, questions and chasing |
   | *Record, tickets and follow-up* | follow-through, unexplained items, rule candidates |

2. The editor checks each change as it is made. For example, it rejects follow-through on a field
   that is not in the case key, or a checklist prefill naming a section that does not exist.
3. A second owner approves the change. New cases use it; past cases keep the version they ran on.
4. For anything the model does, run an eval on the draft first
   ([runbook](real-model-evals.md)).

A team group may set a feature only if the capability lists it under `configurable`. For
*Break investigation* and *Reconciliation investigation*, these are listed: `follow_through`,
`reasoning.sections`, `review.checklist`, `requests` and `insights`.

## Payment exceptions: the first non-finance capability

*Payment exceptions* (`payments.exceptions`) is built only from generic data steps:
1. the day's FX rates as a data set;
2. duplicates and test payments set aside, kept on the case with the reason;
3. amounts converted to GBP, with a missing rate flagged;
4. hours since arrival, banded against the service level;
5. the payments team's own risk score, from its own service (`transform`);
6. rules for closed accounts (AC04) and missing addresses (BE04), with the model for the rest.

Payments Operations decides, and payment release stays in the payments system.
