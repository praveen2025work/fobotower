# FOBO Prime: the data contract and the parameters to confirm

**Date:** 2026-10-05 · **For:** the MB Rec and MOTIF teams (the data), Product Control (the
parameters), and the FOBO Prime group owners.

Helix derives this from the configuration (`fobo-prime.yaml`); it is never typed by hand. The
same list is live in the console: *Capabilities → Break investigation → Groups → FOBO Prime →
Data and parameters*. For any other capability or group the panel shows its own contract. The
API is `GET /api/capabilities/{id}/contract?team_group={group}`.

## How missing data behaves

| A field is missing | Effect |
|---|---|
| read by a cause **check** | the check is negative (it did not find that cause); the next check is tried |
| needed by a validation **test** | the test is **not run**, with the reason; it never passes by default |
| read by a **finding** | the finding is not reached |

So a gap in the feed shows up as "not run" and as more breaks going to a person. It never shows
up as a wrong POST.

## 1. Data Helix reads from each break

`mbrec.breaks` is MB Rec's open breaks for a book and COB. `motif.break_snapshots` is the FO/BO
snapshot joined on the instrument by the *enrich* step. Where both are listed, either source
may provide the field; in the office, agree which one does.

| Field | Read by | Comes from |
|---|---|---|
| `age_days` | check AGED, check TIMING, shown to reviewers | mbrec.breaks |
| `bo_adjustments` | check C6 | mbrec.breaks or motif.break_snapshots |
| `bo_cash_ok` | test BO-5 | mbrec.breaks or motif.break_snapshots |
| `bo_components` | check C4 | mbrec.breaks or motif.break_snapshots |
| `bo_cutoff_ts` | check C1, check TIMING | mbrec.breaks or motif.break_snapshots |
| `bo_dataset_id` | check C3 | mbrec.breaks or motif.break_snapshots |
| `bo_factor_ok` | test BO-3 | mbrec.breaks or motif.break_snapshots |
| `bo_journal_posted` | test BO-6 | mbrec.breaks or motif.break_snapshots |
| `bo_position_balanced` | test BO-1 | mbrec.breaks or motif.break_snapshots |
| `bo_price_source_ok` | test BO-2 | mbrec.breaks or motif.break_snapshots |
| `bo_settled` | test BO-4 | mbrec.breaks or motif.break_snapshots |
| `bo_version` | check C5 | mbrec.breaks or motif.break_snapshots |
| `book` | reference lookup owner_desk, reference lookup owner_team | mbrec.breaks or motif.break_snapshots |
| `book_status` | check R5 | mbrec.breaks or motif.break_snapshots |
| `break_type` | shown to reviewers | mbrec.breaks |
| `cats_amount` | shown to reviewers | mbrec.breaks |
| `cats_calculated` | finding A, finding C, test FO-6 | mbrec.breaks or motif.break_snapshots |
| `desk` | shown to reviewers | mbrec.breaks |
| `difference` | amount, check REAPPLICATION, shown to reviewers | mbrec.breaks |
| `factor_changed` | finding B, test FO-6 | mbrec.breaks or motif.break_snapshots |
| `fo_adjustments` | check C6 | mbrec.breaks or motif.break_snapshots |
| `fo_booking_ts` | check C1, check TIMING | mbrec.breaks or motif.break_snapshots |
| `fo_components` | check C4 | mbrec.breaks or motif.break_snapshots |
| `fo_dataset_id` | check C3 | mbrec.breaks or motif.break_snapshots |
| `fo_open_position` | test FO-1 | mbrec.breaks or motif.break_snapshots |
| `fo_open_price` | test FO-2 | mbrec.breaks or motif.break_snapshots |
| `fo_open_pull_factor` | test FO-3 | mbrec.breaks or motif.break_snapshots |
| `fo_prev_close_position` | test FO-1 | mbrec.breaks or motif.break_snapshots |
| `fo_prev_close_price` | test FO-2 | mbrec.breaks or motif.break_snapshots |
| `fo_prev_pull_factor` | test FO-3 | mbrec.breaks or motif.break_snapshots |
| `fo_price` | test FO-7 | mbrec.breaks or motif.break_snapshots |
| `fo_version` | check C5 | mbrec.breaks or motif.break_snapshots |
| `holiday_carry_ok` | test FO-8 | mbrec.breaks or motif.break_snapshots |
| `instrument` | item id, join with motif.break_snapshots, shown to reviewers | mbrec.breaks |
| `journal_status` | check POSTING_FAILED | mbrec.breaks or motif.break_snapshots |
| `mapping_present` | check C2 | mbrec.breaks or motif.break_snapshots |
| `motif_amount` | shown to reviewers | mbrec.breaks |
| `mtm_unexplained` | test FO-4 | mbrec.breaks or motif.break_snapshots |
| `pnl_expected` | finding A | mbrec.breaks or motif.break_snapshots |
| `prior_adjustment` | check REAPPLICATION | mbrec.breaks or motif.break_snapshots |
| `redemption_event` | finding A, finding B, finding C, test FO-6 | mbrec.breaks or motif.break_snapshots |
| `static_present` | check STATIC_OUTLIER | mbrec.breaks or motif.break_snapshots |
| `trade_pnl_explained` | test FO-5 | mbrec.breaks or motif.break_snapshots |

Helix computes the rest itself: the category, side, cause and cause reason (playbook), the
`carried_*` fields (follow-through: what was decided on the last COB), and the owning desk
(reference lookups).

### Asks of MB Rec

1. **`book_status`** (`Complete` when the book is final). R5 depends on it: until a book is
   complete, nothing is investigated.
2. **`journal_status`** (`posted`, `rejected` or `not generated`). This drives the posting-failure
   scenario, CORRECT & RE-POST.
3. **`static_present`**, false when the instrument has no static or enrichment data. This drives
   the static-outlier scenario.
4. **`prior_adjustment`**: yesterday's adjustment for the position. This drives the
   reapplication scenario.
5. **`age_days`**: how many COBs the break has been open. This drives the timing and aged checks.
6. The **instrument** as the break's id, which must be stable from COB to COB. Follow-through
   matches a break to the last COB's decision on it.

### Asks of MOTIF / CATS (through the snapshots)

The FO-1…FO-8 and BO-1…BO-6 inputs above, and the booking timestamps, cut-off, versions,
components and adjustments the cause checks C1–C6 read.

## 2. Parameters Product Control must confirm (P1)

All are empty until confirmed. While a parameter is empty:
- a test that needs it is **not run**;
- a POST that depends on it is flagged **"requires controller confirmation"**. Approving it then
  needs a tick and the controller's words.

| Parameter | Unit | Used by |
|---|---|---|
| `calculation_reasonable_tolerance` | GBP | not used by any rule yet |
| `materiality_threshold` | GBP | verdicts (a POST asks the reviewer to confirm while unset) |
| `mtm_market_movement_tolerance` | GBP | test FO-4 (not run while unset) |
| `posting_policy_reference` | — | verdicts (a POST asks the reviewer to confirm while unset) |
| `same_day_resolution_cutoff` | time (IST) | not used by any rule yet |

Two are **not used by any rule yet**:
- `calculation_reasonable_tolerance` (FO-6). The FO-6 test today judges by the redemption flags
  alone. Once a tolerance is confirmed, add it to FO-6's `policy` and `fails_when`.
- `same_day_resolution_cutoff` (§10). Once it is confirmed, a rule can use it: a break raised
  after the cut-off goes to MONITOR rather than ESCALATE.

To set one: *Configure → Thresholds* on the group, then a second owner approves. The change is
versioned, and past cases keep the values they ran on.

### Also to confirm (not parameters)

| Item | Where it lives |
|---|---|
| Escalation routing per category | `playbook.categories.*.escalate_to` and the ticketing tool's `team` |
| Books in scope | the reviewers' data scopes, and which books MB Rec notifies Helix about |
| Who may be asked (desk, Operations, CATS support) and their roles | `requests.targets` |
| The §14 checklist wording | `review.checklist` |
