# The FOBO Investigation Skill in Agent One Finance

**Date:** 2026-10-05 · **Source:** [`fobo-investigation-skill-v1.0.md`](fobo-investigation-skill-v1.0.md)
(the controllers' skill) · **Where it lives:** *Break investigation* capability, group
*FOBO Prime — MB Rec breaks* (`config/helix/groups/break.investigation/fobo-prime.yaml`).

## The translation in one picture

The skill describes two kinds of work, and Agent One Finance splits them the way the skill's own §9
does:

| The skill says | In Agent One Finance it becomes | Runs as |
|---|---|---|
| What is **mechanical**: tests, findings, categories, the verdict table, R2, R5, P1, the §8 scenarios (~80%) | the **playbook**: checks, tests, findings, categories, verdict table, guards, thresholds | code, on every break, before any model; the same answer every time |
| What needs **judgement**: multiple causes, complex corporate actions, novel and aged breaks, unproven side (~20%) | the **model's instructions** (`reasoning.skill`), with only the read tools the group allows | the model, one group of breaks at a time; always SME review (R7) |
| What a **person** decides | the **tollgate** (before the model) and **review** (sign-off) | the controller |

So the skill text is not pasted into the model whole. The parts that can be codified are
enforced in code, where the model cannot get them wrong. The model gets the rest, plus the
rules it must never break.

**Status key:**
- **In Agent One Finance** — already there before today.
- **Added now** — added to the FOBO Prime configuration today.
- **Gap** — needed building; all are now built (listed at the end).

## Section by section

| Skill | Agent One Finance | Status |
|---|---|---|
| **§1 Role** — senior Product Controller, forensic, evidence-backed root cause plus verdict | First paragraph of `reasoning.skill` | Added now |
| **§2 Invariant** FO PnL = BO PnL + Δ adjustments | Stated in `reasoning.skill`; checked on the next COB by follow-through (§4 step 9 below) | In Agent One Finance |
| **R1** A break is a symptom, not an instruction to post | Nothing posts without a cause: the table posts only when a check positively found a BO cause; no positive check → H Novel → ESCALATE | In Agent One Finance |
| **R2** Never assume FO is correct | Guard in code: a POST whose cause is FO becomes ESCALATE, after the table *and* after the model. An unproven side is never settled by the table; it goes to the model and an SME | In Agent One Finance |
| **R3** Decompose before you diagnose | Every test names the component it validates (Position, Price, MTM, Pull Factor…); results are per break, never aggregate | In Agent One Finance |
| **R4** Truth before adjustment | The verdict comes from the category the checks proved; the model is told the same | In Agent One Finance |
| **R5** Do not begin while books are incomplete | Check `R5` (first): `book_status != 'Complete'` → category W *Books not complete* → **ESCALATE** to Operations, whatever the side (`any_side`). The model is never called for it | Added now |
| **R6** If you cannot evidence it, escalate it | Any figure the model states that does not trace to data is escalated (validate gate); no positive check → Novel → ESCALATE | In Agent One Finance |
| **R7** Route by determinism | `categories.*.determinism`: deterministic + proven side → table, `decided_by: playbook`; judgement → model + `sme_review` | In Agent One Finance |
| **Decomposition map** | `playbook.tests[].validates` and `side` | In Agent One Finance |
| **Failure modes** | Posting by elimination: impossible by the table (it posts only on a positive BO cause), forbidden to the model. MOTIF rejection: check `POSTING_FAILED` → CORRECT_AND_REPOST. Price = 0: FO-7, a blocking test. Plausible cause as *the* cause: the model must label hypotheses | In Agent One Finance + added now |
| **§4 Sequence** 0 confirm processing | `R5` check | Added now |
| §4 step 1 break universe | `load` from MB Rec's open breaks (`mbrec.breaks`); no re-matching | In Agent One Finance |
| §4 steps 2–5 FO, then BO, then trade level, then Novel | All tests run on every break (negatives kept, so the reviewer sees what was ruled out); the first positive check in order is the cause; nothing found → H Novel | In Agent One Finance (all run rather than stopping early; same result, more evidence) |
| §4 steps 6–7 classify, decide | Categories and the verdict table | In Agent One Finance |
| §4 step 8 remediation | Tickets to the owning team on DO_NOT_POST, CORRECT_AND_REPOST and escalations; the model writes the remediation | In Agent One Finance + added now |
| §4 step 9 end state | `follow_through`: every approved POST, CORRECT & RE-POST and MONITOR is re-tested on the book's next COB. A break that is gone has cleared (shown on the earlier case). One still open after an adjustment → check `ADJUSTMENT_NOT_CLEARED` → U *Adjustment did not clear* → ESCALATE (the investigation stays open). A MONITOR that did not clear → `MONITOR_NOT_CLEARED` → K | In Agent One Finance |
| **§5 FO-1…FO-8** | `playbook.tests`, each with `fails_when`, the fields it `needs`, its evidence, `on_fail`; FO-1, FO-2, FO-4, FO-7 hold a POST (`blocks_post`); FO-3 failing requires FO-6 | In Agent One Finance |
| A test whose evidence is missing | "not run", never passed (§13: "unable to test") | In Agent One Finance |
| **FO-6 findings A/B/C** | `playbook.findings`: A and B indicate a category and side FO; C proceeds to BO | In Agent One Finance |
| Worked case (pull factor 1.00 → 0.67) | Finding A → C/FO → DO_NOT_POST, owner CATS support (`tests/helix/test_fobo_playbook.py`) | In Agent One Finance |
| **§6 BO-1…BO-6** | `playbook.tests` with side BO | In Agent One Finance |
| Decision Point 2 — do not post by elimination | As R1; and in `reasoning.skill` | In Agent One Finance + added now |
| **§7 Trade level** | `cats.trades` and `motif.trades` are the model's tools (quantity, direction, consideration, price, pull factor, settlement), with a *trade-level* specialist that compares them per trade | In Agent One Finance |
| **§8 Reapplication** | Check `REAPPLICATION`: `prior_adjustment` equals today's difference → J *Reapplication* (BO) → **POST**, flagged for confirmation while thresholds are unset (P1) | Added now |
| §8 Missing side | Check `MISSING_SIDE` (after timing, so a late booking stays T): `break_type == 'missing_motif'` → M *Missing side*, judgement → the model with the trade tools, then a person | In Agent One Finance |
| §8 Static outlier | Check `STATIC_OUTLIER`: `not static_present` → F *Data quality* (BO) → **DO NOT POST** | Added now |
| §8 Posting failure | Check `POSTING_FAILED`: `journal_status == 'rejected'` → R *Rejected posting* → **CORRECT_AND_REPOST**, ticket to Operations | Added now |
| **§9 Categories A–H** | `playbook.categories` A–H with determinism and owning team; plus T (timing), K (aged), W (books not complete), R (rejected posting), J (reapplication) | In Agent One Finance + added now |
| "Exactly one primary category" | The first positive check; the others are kept on the break as secondary evidence | In Agent One Finance |
| Category H feeds skill evolution | *Learning from the work* lists H and breaks no check explained (`insights.unexplained`) for the skill's owners, and judgement calls approved unchanged 5× as rule candidates; eval sets replay decided cases on a changed playbook | In Agent One Finance |
| **§10 Verdicts** POST / DO NOT POST / ESCALATE / CORRECT & RE-POST | All four in the table; plus MONITOR for timing differences | Added now (CORRECT_AND_REPOST) |
| **§11 Remediation** | Tickets to the owning team (`escalation`); *Recurring items* for "recurring or systemic"; the model writes who to engage and which preventative control or MB Rec rule to propose | In Agent One Finance + added now |
| "If an adjustment was posted: BO + adjustments = FO, else stays open" | `follow_through` and `ADJUSTMENT_NOT_CLEARED` (see §4 step 9 above) | In Agent One Finance |
| **§12 Output format** | 1 break summary → the break table · 2 checks performed → the tests table · 4 classification → category, side, determinism · 3, 5, 6, 7 → `reasoning.sections`: root cause, hypotheses, tests not performed, verdict and why, remediation, preventative control, end state, each its own field; a required one missing sends the group to a person | In Agent One Finance |
| **§13 Evidence discipline** — say which tests could not run | Tests "not run" with the reason; the model must state them and their effect on confidence | In Agent One Finance + added now |
| §13 "ask for it" | *Ask for evidence*: a reviewer asks the desk, Operations or CATS support (`requests.targets`); the group waits; the answer goes back to the model | Added now |
| **§14 Completion checklist** | `review.checklist`: the questions answered yes / no / n/a before approving, with Agent One Finance's answer next to each (tests, evidence and answers, verdict, root cause, remediation…); kept on the decision. Questions 6 and 7 are one ("why, or why not") since only one applies | In Agent One Finance |
| **§15 Governing principle** | The design: components first, verdict mechanical once the cause is known | In Agent One Finance |
| **Local parameters** | `policy`, all `null` until Product Control confirms; the *Data and parameters* panel lists each, where it is used, and what is still to confirm ([data contract](mbrec-data-contract.md)). FOBO Rates has materiality and the posting policy confirmed | In Agent One Finance (cut-off and FO-6 tolerance not yet used by a rule) |
| **P1** never invent a threshold | A POST while a threshold is unset is flagged "requires controller confirmation"; approving it needs a tick and the controller's words; a test whose threshold is unset is "not run" | In Agent One Finance |
| Appendix A worked example | Reproduced in the behaviour tests | In Agent One Finance |

## What MB Rec must provide

The playbook reads these fields from each break. In dev they come from a stub. In the office,
they come from MB Rec or from the extra-data step (MOTIF snapshots).

| Field | Used by | From |
|---|---|---|
| `book_status` | R5 | MB Rec |
| `journal_status` (posted / rejected / not generated) | posting failure, BO-6 | MB Rec or MOTIF |
| `static_present` | static outlier | MB Rec enrichment |
| `prior_adjustment` | reapplication | MB Rec (yesterday's adjustment for the position) |
| `age_days` | timing, aged | MB Rec |
| `fo_booking_ts`, `bo_cutoff_ts`, versions, components, adjustments | cause checks C1–C6, timing | MOTIF snapshots (`enrich`) |
| `fo_prev_close_position`, `fo_open_position`, prices, pull factors, redemption flags, … | FO-1…FO-8, BO-1…BO-6, findings | CATS and MOTIF, joined by `enrich` |

A field that is missing makes the test that needs it "not run". Nothing is assumed.

## Gaps: what needed building — all done

1. ~~Ask for evidence (§13)~~: `requests`. Questions are chased after 2 hours and escalated after
   4, and answers may carry a file. See the [Teams/email recipe](../guide/questions-by-teams-or-email.md).
2. ~~Late exceptions~~: `case.late_items: follow_up`.
3. ~~Structured output (§12)~~: `reasoning.sections`.
4. ~~End-state validation (§11, §4 step 9)~~: `follow_through`.
5. ~~Trade-level tool (§7)~~: `cats.trades`, `motif.trades`.
6. ~~Category H report~~: *Learning from the work*.
7. ~~Completion checklist (§14)~~: `review.checklist`.

Each is a platform feature that any capability can use, not something built for FOBO alone.
See [features by capability](../guide/features-by-capability.md).

What remains is for people, not code:
- Product Control confirms the parameters;
- MB Rec and MOTIF provide the fields in the [data contract](mbrec-data-contract.md);
- the controllers' decisions in Agent One Finance become the eval set ([runbook](../guide/real-model-evals.md)).

## Keeping the skill and Agent One Finance in step

The skill document stays the authority. When Product Control changes it:

1. Change the matching part of `fobo-prime.yaml`: a check, test, category or verdict-table
   row, or the instructions. Use *Configure* or the YAML.
2. Run the eval set: replay last month's decided cases on the draft and compare.
3. A second owner approves the change. New cases use it; past cases keep the version they
   ran on.
