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
  Helix).
- **Variance**: *P&L variance commentary*.
- **Report validation**: *Report validation*.

## The matrix

| Feature | Setting | FOBO Prime / Rates | Cash | Variance | Report validation |
|---|---|---|---|---|---|
| Item source | `items.load` / `match` | MB Rec's breaks (no re-matching) | Helix matches bank to ledger | GL balances vs budget (`compare`) | Helix matches the report workbook to GL balances |
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
| Tickets | `escalation` | DO NOT POST, CORRECT & RE-POST, escalations → owning team | — | — | — |
| Write-back | `publish` | — | — | commentary to the reporting pack after release | a PDF report after release |
| Schedule / events | `case.opens_on` | event (MB Rec finishes a book) | schedule | schedule (2nd of the month) | manual |
| Deadline | `case.due` | 11:00 (Prime), 12:00 (Rates) next business day | per group | — | — |

**Bold** marks features added in this release.

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
