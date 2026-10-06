# Agent One Finance by example

**Date:** 2026-10-04. Worked examples for the accounting teams. The FOBO cases are real
runs on the dev data, COB 2026-09-30. The other capabilities are configuration files you
can install today. Each one says whether it runs now or which connector it waits for.

- [1. One capability, many teams](#1-one-capability-many-teams)
- [2. FOBO: CATS vs MOTIF Prime vs Rates](#2-fobo-cats-vs-motif-prime-vs-rates)
- [3. FOBO walk-throughs (real runs)](#3-fobo-walk-throughs-real-runs)
- [4. Other accounting capabilities](#4-other-accounting-capabilities)
- [5. Installing an example](#5-installing-an-example)

## 1. One capability, many teams

A **capability** is a kind of work, such as "reconciliation investigation". It fixes the
workflow and its gates (validate → review → record). A **team group** sets that team's
part: sources, keys, thresholds, playbook, instructions, reviewers and schedule. Each team
sees only its own books and cases, and only its own owners approve changes to its group.

```
Reconciliation investigation (capability: workflow, gates, retention)
├── CATS vs MOTIF — Prime (FOBO)   frank, gina   · PRIME-MB-01…06
├── CATS vs MOTIF — Rates (FOBO)   rita, raj     · RATES-LDN-01…04, RATES-NY-01/02
├── Cash — bank vs ledger          dan           · cash accounts
└── Intercompany (example)         IC owners     · entity pairs        ← docs/agent-one-finance/examples
```

## 2. FOBO: CATS vs MOTIF Prime vs Rates

Both groups run FOBO's playbook, the same rules as `config/playbook/fobo-cats-vs-motif.yaml`:

- six cause checks, C1–C6;
- 14 validation tests, FO-1…FO-8 and BO-1…BO-6;
- FO-6 findings A/B/C;
- categories A–H;
- the verdict table;
- the R2 guard: an FO-side cause never posts.

| | **Prime** — `cats-motif.yaml` | **Rates** — `cats-motif-rates.yaml` |
|---|---|---|
| Books (data scope) | PRIME-MB-01…06 | RATES-LDN-01…04, RATES-NY-01/02 |
| Group owners (approve changes) | frank, gina (`AOF_FOBO_RECON_OWNER`) | rita, raj (`AOF_FOBO_RATES_OWNER`) |
| Sign off breaks | `FOBO_CONTROLLER` | `FOBO_RATES_CONTROLLER` |
| Opens | 06:30 business days, yesterday's COB, plus MOTIF's EOD event | 07:15 business days, after the Rates EOD curves, plus events |
| Match tolerance (MTM) | 0.50 | 1.00 |
| Materiality / posting policy | unset → a POST says *"requires controller confirmation"* (P1) | 10,000 GBP / `PC-RATES-2026-03` (confirmed) → POST stands as is |
| FO-4 / FO-6 tolerances | unset → FO-4 is *not run* | unset → FO-4 is *not run* |
| Model instructions | booking events: late booking, amendment, FX fixing, cancel/rebook | curve datasets and fixings first, then booking events |
| Lineage (knowledge graph) | book → desk → escalation team, as of the COB | same; desks RATES-LDN / RATES-NY → "Rates desk" |

The same rules apply to both groups. Only the team, its thresholds and its scope differ.
If Product Control confirms Prime's materiality, a Prime owner edits one line and a second
Prime owner approves it. Rates is not touched.

## 3. FOBO walk-throughs (real runs)

Each run follows these steps:

```
match CATS↔MOTIF → enrich (dated snapshots) → resolve (book→desk→team @COB)
→ classify (C1–C6 + tests) → group (category × side) → reason (table | model) → draft
→ validate (every figure traced) → review (controller) → record
```

### Prime — PRIME-MB-04, COB 2026-09-30

| Break | Difference | Cause check | Category / side | Verdict | Owner |
|---|---:|---|---|---|---|
| EURUSD FWD | −42,000 (amount break) | C5 *"Pending desk confirmation since the 11:00 run"* | E Trade booking / FO | **DO_NOT_POST**: fix it at the desk (R2) | Desk |
| JGB 10Y | −538,284.17 (missing in MOTIF) | C1 *"Nostro statement received after 23:30 cutoff"* | C Redemption / BO | **POST**, *requires controller confirmation* (P1: materiality unset) | CATS support |

The checks settled both breaks deterministically (`decided_by: playbook`), so no model
call was needed. FO-4 shows **not run** because its tolerance is unset; it is never shown
as passed. The controller approves or rejects each group and enters a comment where
required.

### Prime — PRIME-MB-02

| Break | Cause | Category / side | Verdict | Owner |
|---|---|---|---|---|
| IRS 10Y EUR | C2 *"Reference does not resolve in static data"*; BO-6 failed (journal not posted) | F Data quality / BO | **DO_NOT_POST** | Technology |
| SOFR FUT | C5 pending desk confirmation | E / FO | **DO_NOT_POST** | Desk |

### Prime — a held POST (COB 2026-08-03)

PRIME-MB-04 had a D/BO break, so the table said **POST**. But test FO-1 failed: the prior
day's close position did not equal today's open. FO-1 blocks a POST, so the verdict became
**ESCALATE**, with the note *"Held: FO-1 failed: Hold adjustment; escalate position issue"*.

### Rates — RATES-LDN-04, COB 2026-09-30

| Break | Difference | Cause | Category / side | Verdict |
|---|---:|---|---|---|
| CDX IG | 120 | C6 *"Two entries with identical settlement reference"* | D Settlement / BO | **POST**, with no confirmation flag (Rates thresholds confirmed) |
| GILT 5Y | 120 | C5 pending desk confirmation | E / FO | **DO_NOT_POST** |
| ITRAXX MAIN | −360,748.61 (missing in MOTIF) | no cause check fired; FO-6 finding **A** *"Pull factor event missing; expected PnL exists, FO shows zero"* | C Redemption / FO | **DO_NOT_POST** |

Compare this with Prime: a D/BO POST on Prime carries *"requires controller confirmation"*,
but on Rates it does not. The ITRAXX break shows the findings at work: no cause check
explained it, but FO-6's redemption analysis did.

### Rates — RATES-LDN-01 and RATES-LDN-03

- **LDN-01, UST 10Y:** C2 → F/BO → **DO_NOT_POST**. The knowledge graph resolves the owner
  to desk RATES-LDN, team "Rates desk".
- **LDN-03:** C4 breaks (CDX IG 15,000; EURUSD FWD; SOFR FUT). C4 is *"Fee or funding
  component present on one side only"*, and its side is **UNKNOWN**. Under R2 an unproven
  side is never settled by the table, so these go to the model, which reads the booking
  events and can hand off to the booking-events subagent. They also go to SME review
  (`sme_review`). The model's verdict still passes the guards.

### Who sees what

- frank (Prime) sees only PRIME books, Prime cases and the Prime schedule.
- rita sees RATES-LDN-01…04. raj sees all six Rates books.
- Neither team can approve the other's changes. Tests:
  `apps/backend/tests/agent_one_finance/test_fobo_playbook.py`.

## 4. Other accounting capabilities

| Example | Kind | What it does | People | Runs now? |
|---|---|---|---|---|
| **Variance commentary** (`fin-variance-commentary`, live) | capability | Material actual-vs-budget variances explained from journal lines; a reviewer signs off | carol | **Yes** (gl, budget) |
| **Cash — bank vs ledger** (live group) | rec group | Bank statement lines matched to ledger cash; timing and fees by rule, the rest by the model | dan | **Yes** |
| **Report validation** (live) | capability | A management report (Excel) checked against the ledger; every difference explained; a PDF validation report published after sign-off | carol | **Yes** (documents, gl) |
| [Accruals review](examples/accruals-review.yaml) | capability | On the 3rd of each month, accruals that moved materially against plan are explained from journals. A second reviewer when ≥ 250k; a spend limit per case and per day | carol | **Yes**: gl, budget |
| [Balance sheet substantiation](examples/balance-sheet-substantiation.yaml) | capability | Every balance ≥ 100k matched to its filed support (PDF/workbook); unsupported balances are escalated. After a second person releases it, a signed **PDF pack** is published | carol | **Yes**: gl, documents |
| [Intercompany recon](examples/intercompany-recon.group.yaml) | rec group (3rd team on the recon engine) | A's receivable from B matched to B's payable to A. FX rounding ≤ 50 GBP proposed by rule; a missing payable is escalated to the counterpart | `IC_ACCOUNTANT` | Needs `ic.receivables`, `ic.payables` |
| [Journal entry controls](examples/journal-entry-controls.yaml) | capability with playbook | Manual journals checked: **SOD** (posted = approved → ESCALATE), **CLOSED** period → ESCALATE, **HOURS** / **ROUND** go to the model and a controller; clean journals ACCEPT | `FINANCIAL_CONTROLLER` | Needs `gl.journal_entries` |
| [Suspense clearing](examples/suspense-clearing.yaml) | capability with write-back | Items ≥ 3 days in suspense aged and matched to a home account. A clearing journal is **posted** only after review and a four-eyes release (idempotent) | carol | Needs `gl.suspense_items`, `gl.post_journal` (write) |

What the examples show:

- **A new team on an existing engine:** intercompany. It is one YAML file with no code.
- **Your own rulebook:** journal entry controls. Its playbook has checks, categories, a
  verdict table, and judgement calls that go to the model. This is the same mechanism as
  FOBO.
- **Documents in and out:** balance sheet substantiation. It reads filed PDFs and Excel and
  publishes a PDF. Reviewers can also upload evidence to any case, and every case can
  produce an **evidence pack** PDF for audit.
- **Writing back to a system:** suspense clearing. Nothing is written until a second person
  releases it. Every call goes through the gateway and is audited.
- **Running on a schedule:** accruals (the 3rd of each month) and FOBO (each business
  morning).

`apps/backend/tests/agent_one_finance/test_examples.py` validates every example and allows only the
missing-connector problems listed above.

## 5. Installing an example

1. If a connector is missing, the Agent One Finance team onboards it. That is one entry in
   `config/agent-one-finance/connectors.yaml` (see `connectors.office.example.yaml`).
2. Copy the file in:
   - a capability goes to `config/agent-one-finance/capabilities/<id>.yaml`;
   - a rec group goes to `config/agent-one-finance/groups/recon.investigation/<group>.yaml`.
3. `python -m agent_one_finance.config_sync` turns the file into a draft. A second owner approves it,
   and the next case runs on it. (On a fresh database the files seed directly.)
4. Or skip the files: open *Authoring*, paste the YAML (or start from a template), submit,
   and have another owner approve it.

Before turning it on, run an **eval** (*Capability → Evals*). It replays past decided
cases on the draft in shadow, without writing anything, and reports how often the draft
agrees with what people decided.
