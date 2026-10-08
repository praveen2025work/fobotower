# Algorithms in Agent One Finance

**Date:** 2026-10-08

Agent One Finance uses algorithms to find **evidence**. An algorithm step adds fields to each item,
and sometimes a small data set; it never matches, removes, posts or decides anything. A
playbook check or a person decides what the evidence means. Every algorithm gives the same
answer for the same inputs, and every result explains itself: what was paired, which rows add
up, how many other books.

Each algorithm is a configurable step (`step_settings`), set in *Configure → Configurable
steps*, checked with the manifest and run under the same gateway and audit as every other
step. Code: `apps/backend/agent_one_finance/algorithms.py` and `steps_v2.py`. Tests:
`tests/agent_one_finance/test_algorithms.py`.

## The algorithms

| Step type | Finds | How | Adds to each item |
|---|---|---|---|
| `offsets` | Equal-and-opposite amounts: booked to the wrong instrument, a cancel and rebook, a reversal across the cut-off | Pairs each positive amount with the closest unpaired negative of the same size (within the tolerance) in the same `within` group, e.g. the book. Sorted search, so it is fast on large cases | `offset`, `offset_with`, `offset_pair`; a data set of the pairs |
| `subset_match` | A few rows that together explain an amount: a split or partial booking | Searches sets of 1 to `max_size` (at most 5) rows from a data set, or from the other items, for one that sums to the target within the tolerance. It searches the smallest sets first and stops after 250,000 tries, saying so | `subset_found`, `subset_members`, `subset_sum`, `subset_unique` (false if another set also works), `subset_complete` |
| `trend` | How an item moved over its own history: growing, shrinking, steady, or flipping sign | Least-squares slope over the history plus today, sign changes, and whether the size grew at every step | `trend_direction`, `trend_slope`, `trend_flips`, `trend_points`, `trend_growing` |
| `cluster` | The same item breaking the same way in several books or entities: one systemic cause | Counts other places with the same key fields, the same sign and an amount within `within_pct`, either read through a tool or from the case's own items | `systemic`, `systemic_count`; `systemic_where` only if `show_where` is set |
| `fuzzy_match` | References that differ only by a typo or format | Jaro–Winkler similarity on references cleaned to letters and digits, optionally with an amount within a percentage. The output is candidates only | `near`, `near_candidates` (top 3, with scores) |
| `benford` | Populations whose amounts look made up; round amounts | First-digit test against Benford's law, with Nigrini's conformity bands for the mean absolute deviation, a chi-square value, and a z-test per digit. Fewer than `min_items` amounts → "not run", never a pass | `benford_digit`, `benford_over`, `round_amount`; a summary data set |
| `anomaly`, `flux` with `method: robust` | An item unusual against its own history, even when the history already has outliers | Median and 1.4826 × MAD instead of mean and standard deviation. `same: <field>` compares only with past rows that have the item's value of that field, e.g. month-end with month-end | `anomaly`, `anomaly_z`; `flux_*` |
| `sample` with `method: mus` | An audit sample weighted by value | Systematic monetary-unit sampling: one point every *total ÷ size* currency units from a random start seeded by the case. An item at least one interval long is always in. The same case always gets the same sample | `sampled`; a data set with the seed |
| `score` with `formula` | A priority to order the work | A numeric expression added to any weighted factors, e.g. `abs(difference) / 10000 + age_days * 5 + ifelse(recurring, 20, 0)`, with bands | the score, its reasons, its band |

### Learning checks from decisions

*Learning from the work → Checks the decisions suggest* reads the judgement calls people
approved. For each category where people approved more than one verdict, it looks for the
simplest condition on the items' own fields that predicts the verdict. That is one condition,
or failing that two joined by `and`. It needs at least 95% precision and at least
`insights.automation_after` cases (5 by default).

Example: `trend_direction == 'shrinking'` → MONITOR in K (aged), 6 of 6 cases, never wrong. A
proposal is a valid playbook expression, but it changes nothing by itself. The playbook's
owners replay it on past cases (an eval) and a second owner approves it before it becomes a
check. Code: `propose_checks` in `insights.py`.

## How FOBO uses them

*Break investigation* (shared by FOBO Prime and FOBO Rates) runs these steps between loading
MB Rec's breaks and the playbook:

| Step | Type | Reads | For |
|---|---|---|---|
| `history` | dataset | `mbrec.break_history_book` | Each break's last five COBs |
| `events` | dataset | `motif.booking_events` | The book's booking events |
| `bo_positions` | dataset | `motif.positions` | MOTIF's instrument names (for near matches only; breaks still come only from MB Rec) |
| `offsets` | offsets | the breaks | Booked to the wrong instrument |
| `split_bookings` | subset_match | `events` | Partial bookings that add up to the break |
| `systemic` | cluster | `mbrec.breaks_all` | The same instrument breaking in other books; only the count is kept on the case |
| `near_refs` | fuzzy_match | `bo_positions` | A missing instrument MOTIF holds under a typo, with the same MTM within 1% |
| `trend` | trend | `history` | Growing, shrinking, flipping |
| `unusual` | anomaly (robust) | `history` | A break unusually large for its instrument |

The FOBO playbooks (`fobo-prime.yaml`, `fobo-rates.yaml`) name four new categories from this
evidence:

| Check | When | Category | Placed |
|---|---|---|---|
| `NEAR_MATCH` | `near` | N · Near-identical reference | Before *missing side* |
| `SYSTEMIC` | `systemic` | Y · Same break in several books | After C1–C6 |
| `OFFSET` | `offset` | O · Booked to the wrong instrument | After C1–C6 |
| `SPLIT_BOOKING` | `split_found` | S · Split booking | After C1–C6 |

**No FOBO verdict changes.** The new checks sit where they only rename breaks that went to a
person anyway: H *Novel* (after C1–C6) or M *Missing side*, both ESCALATE. All four new
categories are judgement calls with verdict ESCALATE, so the model investigates and a person
decides, now with the evidence beside the break. Every verdict matches the old FOBO run.
Category differs only for those breaks (H or M became N, O, S or Y); log them as accepted
differences in the parity log (change guide §6). The model's instructions name the evidence
fields and ask it to say which it used.

## Adding one for another team

1. Open *Capabilities → name → Configure → Configurable steps → Add*, choose from
   *Algorithms*, and fill in the form. The platform checks the settings and the order: a step
   that reads a data set must come after the step that makes it.
2. To act on the evidence, add a check to the playbook or a rule. For example:
   `{ id: OFFSET, when: "offset", category: O, … }`, or a `score` factor
   `{ when: "systemic", weight: 30 }`.
3. Replay last month's cases on the draft (an eval), then a second owner approves it.

Examples for other teams:
- **Journal-entry controls:** `benford` and round amounts over the period's journals.
- **Control testing:** `sample` with `method: mus`.
- **Payments:** `fuzzy_match` on beneficiary names (candidates only; screening stays with
  `screen`).
- **Cash:** `offsets` and `subset_match` between bank and ledger lines.
