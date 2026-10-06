# Agent One Finance steps v2: building blocks for any Finance use case

**Date:** 2026-10-06 · **Status:** phases 1–6 built · **For:** Agent One Finance platform team,
capability owners across Finance (and teams beyond it), architecture.

## 1. Why

Agent One Finance today has 13 steps that run in a straight line over **one list of items**:
- load or match;
- enrich, resolve, classify, compare;
- group, reason, draft;
- validate, review, record;
- publish.

That is enough for FOBO, cash recs, variance commentary and report validation. It is not enough
for the rest of Finance. Agent One Finance is the governed AI platform for Finance, and FOBO is one of its use
cases. Finance alone already needs:
- three-way matches;
- accruals that must post balanced journals;
- SOX testing on a sample;
- balance-sheet certification by account owners;
- a close calendar where one task waits for another;
- price testing against several external sources.

This document does three things:
1. Lists the **processes** Agent One Finance should be able to run (§2).
2. Breaks them into the **operations** they share (§3).
3. Turns those into a **step catalogue v2** (§4), the **engine changes** it needs (§5), and the
   **controls** every step must respect (§6).

§7 then checks the catalogue against real processes, and §8 sets out a phased plan.

## 2. The processes to cover

| Family | Processes | What makes them different |
|---|---|---|
| **Reconciliations** | bank/nostro vs ledger, FOBO, sub-ledger vs GL, custody/positions, intercompany, suspense, card/ATM | 2-way and 3-way matching, many-to-one, tolerances, date windows, ageing, write-off limits |
| **Break and exception investigation** | MB Rec breaks, failed settlements, payment repairs, returned payments, trade booking exceptions | the items come from another system; root cause, owner, follow-through |
| **Variance and flux analysis** | P&L vs budget, balance-sheet flux vs prior periods, forecast vs actual, desk P&L explain | baselines over several periods, materiality, commentary |
| **Balance-sheet substantiation** | account reconciliation and certification, ageing, evidence per account | owner attestation, evidence required, risk-rated accounts |
| **Journals and adjustments** | manual journal review, accruals and prepayments, reclasses, FOBO adjustments, write-offs, reversals | balanced double entry, open periods, authority limits, posting and reversal |
| **Accruals and schedules** | purchase-order accruals (goods received, not invoiced), contract accruals, prepayment amortisation, lease and fixed-asset schedules | computed amounts, schedules over periods, a journal at the end |
| **Intercompany** | matching, netting, settlement, eliminations | many entities, pairs, FX, disputes between two teams |
| **Valuation control** | independent price verification, fair-value hierarchy, valuation reserves | several external sources, tolerances, reserves as journals |
| **Regulatory and management reporting** | report validation, cross-report consistency (e.g. COREP and FINREP), lineage, adjustments | rules across datasets, an attestation chain |
| **Controls testing** | SOX design and operating tests, key control monitoring, user access reviews | sampling, test steps per sample, deficiency rating, evidence |
| **Close management** | close calendar, task dependencies, sign-off cascade (entity → region → group) | cases that wait for other cases, deadlines, roll-up sign-off |
| **Data quality** | static and reference data checks, duplicate detection, completeness | rules over whole datasets, owner routing |
| **Audit and requests** | auditor evidence requests, query responses | evidence collection, chasing, packs |
| **Fees, billing and charges** | fee validation, commission checks, interest recalculation | recompute and compare, client impact |

### 2.1 Beyond Finance: the same blocks elsewhere in the bank

The same platform serves operations, risk, compliance, lending, treasury, client service and
technology. Each family below is case-based work: something arrives, data is gathered and
checked, a proposal is made, a person decides, the outcome is recorded and followed through.

| Family | Processes | What makes them different |
|---|---|---|
| **Payments operations** | payment repairs, returns and recalls, investigations (MT199/camt.029 queries), nostro breaks, SWIFT gpi tracking, duplicate payment checks | service-level clocks in hours, counterparty correspondence, cut-offs, FX, payment release stays in the payment system |
| **Trade and securities operations** | failed settlements, trade affirmation exceptions, corporate actions (elections, entitlements), static data breaks, custody reconciliations | events over several days, market cut-offs, claims, many systems per trade |
| **Collateral and margin** | margin call disputes, collateral eligibility, CSA threshold checks | two-party disputes, daily calls, agreed vs disputed amounts |
| **Lending operations** | loan servicing exceptions, covenant monitoring, drawdown checks, annual reviews (preparation), collateral revaluation | documents (facility agreements, financials), dates and covenants, credit officers decide |
| **Client onboarding and KYC** | document collection, periodic reviews, data remediation, beneficial-ownership checks | documents and outreach to the client, refresh cycles; **Agent One Finance prepares, the KYC officer decides** |
| **Financial crime operations** | AML alert triage packs, sanctions hit preparation, fraud case packs, SAR drafting support | strict decision boundary: **Agent One Finance assembles evidence and timelines; a person decides; nothing is auto-closed** |
| **Credit and market risk** | limit breach investigation, VaR back-testing exceptions, model monitoring, counterparty exposure checks, stress test data checks | limits and approvals by authority, daily cycles, quantitative evidence |
| **Operational risk and controls** | incident and loss event capture, RCSA, key risk indicators, issue and action tracking, SOX/controls testing | owners, due dates, evidence, sign-off cascades |
| **Compliance** | trade and communications surveillance alert triage, conflicts checks, gifts and entertainment, regulatory change impact assessment, breach logs | text and voice evidence, policy references, regulatory deadlines |
| **Treasury and liquidity** | cash forecasting variances, liquidity metric checks (LCR/NSFR data), intraday liquidity exceptions, FTP checks | intraday clocks, many entities, regulatory metrics |
| **Client service** | complaints (with regulatory response deadlines), disputes and chargebacks, fee refunds, account servicing requests | client communication, statutory clocks, redress calculation, consistent outcomes |
| **Wealth and markets conduct** | suitability reviews, best-execution monitoring, product governance reviews | sampling, policy rules, documentation |
| **Technology and data** | user access reviews, change approvals, data quality issue triage, entitlement recertification, vendor risk reviews | attestation by owners, recertification cycles, evidence |
| **HR and procurement (finance-adjacent)** | invoice capture, vendor onboarding checks, expense review | documents, three-way match, policy rules |

**Decision boundaries.** Each capability declares what the model may propose and what only a
person decides. In regulated decisions Agent One Finance prepares and evidences; a named person decides; the
system of record executes. Those decisions include:
- credit;
- sanctions;
- AML, SAR and fraud;
- KYC acceptance;
- payment release;
- complaint redress above a limit;
- trade surveillance escalation.

These are enforced the same way FOBO's R2 guard is: in code, after the model.

Out of scope for the model, by policy: anything where AI must not decide. That includes sanctions,
AML and fraud decisions, credit decisions, and payment release. Agent One Finance can **prepare and evidence**
these, but a person decides and existing controlled systems execute.

## 3. The operations they share

Breaking the processes down gives about forty operations in eleven families. Most are generic:
one step type, configured differently per capability.

| Family | Operations |
|---|---|
| **Acquire** | read from a system, match 2 or *n* systems, take an uploaded file, extract from a document (PDF, email, scan), query a warehouse, take an as-of snapshot |
| **Prepare** | map fields and sign conventions, derive computed fields, filter, deduplicate, convert currency as-of, bucket (ageing, size bands), aggregate or roll up a hierarchy, join data sets |
| **Compare** | actual vs baseline, flux over *n* periods, tolerance or date-window matching, many-to-one and sum matching, fuzzy references, cross-dataset consistency rules |
| **Select** | statistical or risk-based sampling, top-*n* by materiality, the population for a test |
| **Assess** | playbook checks and verdict tables, risk scoring, anomaly against history, rules, model judgement, recompute and compare (fees, interest, accruals) |
| **Propose** | journals (balanced), reclasses, write-offs, reserves, schedules over periods, reversals, tickets, communications to counterparties |
| **Control** | tollgates, review, dual control, an authority matrix by amount and role, segregation of duties, attestation by an owner, evidence required, period open or closed |
| **Act and follow** | write back (post, publish, send) after release, wait for an external event, re-check on the next run, chase, escalate, roll up sign-offs, start child cases, report |
| **Time** | service-level and regulatory clocks (hours or business days, paused while waiting on a client), cut-offs, as-of dating, recertification cycles |
| **Context** | a timeline of events across systems, linking related cases and entities (the same client, account or counterparty), prior outcomes for the same party |
| **Parties** | correspondence with clients, counterparties and other teams; outreach and chasing; two-party disputes |

## 4. Step catalogue v2

Each step type is generic and configured per capability. **★** marks a new step type and **●**
one that exists today. Every step keeps the current contract:
- it declares what it **needs** and **produces**, and the platform checks the order;
- external access goes **only through the gateway** (entitlements, audit, masking);
- nothing writes without approval.

### 4.1 Acquire

| Step | Does | Typical configuration |
|---|---|---|
| ● `load` | items from one tool | `tool`, `args` |
| ● `match` | 2-way match | `left`, `right`, `keys`, `tolerance` |
| ★ `match_n` | *n*-way match: purchase order, goods receipt and invoice; statement, ledger and nostro | `sources[]`, `keys`, `tolerances` per field, `date_window`, `many_to_one: sum` |
| ★ `intake` | items from an uploaded file (CSV, Excel), with a column map and checks | `columns`, `required`, `types`, `max_rows` |
| ★ `extract` | fields from documents (invoices, confirmations, statements) by the model, **each value checked against the source text** and marked low-confidence for review | `fields[{name, type, required}]`, `documents_tool` |
| ★ `dataset` | load a **named** reference set beside the items (FX rates, the budget, prior periods, a chart of accounts) | `name`, `tool`, `args`, `as_of` |

### 4.2 Prepare

| Step | Does | Configuration |
|---|---|---|
| ● `enrich` | join a tool's rows onto items | `tool`, `keys` |
| ● `resolve` | reference-graph lookups as of a date | `node`, `path`, `as` |
| ★ `derive` | computed fields from safe expressions | `fields: {name: expression}` e.g. `age_days: days_between(value_date, case.cob)` |
| ★ `filter` | keep or drop items, with the dropped items **kept and shown** (never silently lost) | `keep_when` |
| ★ `convert` | FX conversion as of a date from a named rate set; base and reporting currency | `amount_fields`, `from`, `to`, `rates: dataset` |
| ★ `bucket` | bands: ageing (0–30, 31–60…), size, risk | `field`, `bands[]`, `as` |
| ★ `aggregate` | roll up by keys or an account hierarchy; totals kept with their members | `by`, `sum[]`, `hierarchy: dataset` |
| ★ `dedupe` | find duplicates (exact or fuzzy) and mark them | `keys`, `fuzzy: {field, threshold}` |
| ★ `transform` | call **a team's own tool** with the items and use what it returns (for logic that expressions can't hold) | `tool`, `returns: items\|fields` |

### 4.3 Compare and select

| Step | Does | Configuration |
|---|---|---|
| ● `compare` | actual vs baseline | `measure`, `baseline`, `as` |
| ★ `flux` | vs *n* prior periods: change, % change, trend, z-score | `periods`, `dataset`, `thresholds` |
| ★ `consistency` | rules **across** data sets (report A total = report B line; sub-ledger = GL) | `checks[{id, when, message}]` |
| ★ `sample` | statistical, monetary-unit or risk-based sample, **reproducible** (seed kept for the auditor) | `method`, `size` or `confidence`, `stratify_by`, `always_include_when` |

### 4.4 Assess

| Step | Does | Configuration |
|---|---|---|
| ● `classify` | playbook: cause checks, tests, categories, verdicts, guards | `playbook` |
| ★ `score` | weighted risk score into bands (high, medium, low) that later steps use | `factors[{when, weight}]`, `bands` |
| ★ `anomaly` | unusual against the item's own history (statistical, no model) | `history: dataset`, `method`, `threshold` |
| ★ `recompute` | recompute a figure by formula or tool and compare to what was booked (fees, interest, accruals, FX revaluation) | `formula` or `tool`, `compare_to`, `tolerance` |
| ● `group`, `reason`, `draft` | groups, then rules → model → person, then summary | as today |

### 4.5 Propose

| Step | Does | Configuration |
|---|---|---|
| ★ `propose_entries` | **journals** from approved findings or a formula: balanced debits and credits, valid accounts and cost centres, an open period, a reversal date for accruals; each entry checked before anyone sees it | `template{lines[{account, side, amount}]}`, `period`, `reverse_on`, `chart: dataset` |
| ★ `schedule` | amounts over periods (prepayment amortisation, leases, accrual release) | `method: straight_line\|effective_rate`, `periods` |
| ★ `compose` | drafts outbound communications (counterparty query, client notice) from approved findings; **never sent without release** | `template`, `to_field`, `channel_tool` |

### 4.6 Control

| Step | Does | Configuration |
|---|---|---|
| ● `validate` 🔒, `review` 🔒, `record` 🔒 | figures traced; people decide; decisions recorded | as today, plus checklist and sections |
| ★ `approve` | **authority matrix**: the approver needed depends on amount, type and entity; multiple levels; segregation of duties enforced across levels | `matrix[{when, roles, count}]` |
| ★ `attest` | an **owner certifies** (an account, a control, a report) with a statement, evidence required, and an expiry | `statement`, `owners_from`, `evidence_required`, `valid_for_days` |
| ★ `period_check` | stop if the accounting period is closed or locked for the entity | `calendar_tool`, `fail: stop\|escalate` |

### 4.7 Act and follow

| Step | Does | Configuration |
|---|---|---|
| ● `publish` | write back after a second person's release | `tool`, `per`, `args` |
| ★ `post` | `publish` specialised for journals: **dry-run first** (validation by the ledger), then post; references stored; one-click reversal as a new case | `ledger_tool`, `dry_run_tool` |
| ★ `await` | wait for an external event or answer (statement arrives, counterparty confirms), with a timeout and an escalation | `event`, `timeout_hours`, `on_timeout` |
| ★ `spawn` | open **child cases** per entity, account or sample item; the parent waits and rolls up | `for_each`, `capability`, `key`, `rollup` |
| ★ `report` | a document (PDF, Excel) for the pack or the auditor, from the case's record | `template`, `format`, `distribute_tool` |
| ● follow-through, escalation, chasing | as today | as today |

### 4.8 Time, context and parties (Finance and beyond)

| Step | Does | Configuration |
|---|---|---|
| ★ `clock` | starts service-level or regulatory clocks per case or group (e.g. a complaint's 8-week final response, a payment investigation's 24 h, a breach report's 72 h), in business or calendar time, **paused while waiting on the client**; warns and escalates as each clock runs down | `clocks[{id, starts, due, calendar, pause_when, warn_before}]` |
| ★ `timeline` | builds one ordered timeline of events from several systems (payments, emails, calls, trades, logins) for the reviewer and the model | `sources[{tool, time_field, label}]` |
| ★ `link` | finds related cases and entities (same client, account, counterparty, ISIN) across capabilities through the knowledge graph, and shows prior outcomes | `on[]`, `lookback_days`, `capabilities[]` |
| ★ `screen` | fuzzy name and identifier matching against a reference list (internal watch lists, counterparties, sanctioned-entity extracts supplied by the control function), producing **candidate hits only**; never clears or confirms a hit | `list: dataset`, `fields`, `threshold` |
| ★ `outreach` | sends a request to a client or counterparty from an approved template through the bank's channel, then waits (with `await`) and chases; the answer becomes evidence | `template`, `channel_tool`, `chase_after_hours` |

Every one of these is generic. A complaints team, a payments team and a KYC team configure the
same `clock`, with different clocks.

## 5. Engine changes needed

The catalogue needs six changes to how a capability's workflow is described and run. They are
listed in the order to do them.

| # | Change | Why | Compatibility |
|---|---|---|---|
| E1 | **Step instances**: `steps: [{id: load_bank, type: load, …config}]`. A type may appear more than once (two `dataset`s, two `enrich`es), and the config sits with the step instead of in top-level sections | real processes read several sources and transform in several passes | today's `steps: [load, …]` and top-level sections still load; they become one instance each |
| E2 | **Named data sets**: the case holds `items` plus named sets (`rates`, `budget`, `prior`, `chart`), versioned per case | FX, budgets, hierarchies and history are inputs, not items | `items` stays the main set |
| E3 | **Conditional steps**: `when:` on a step, an expression over the case (`case.entity_type == 'branch'`, `count(items) > 0`) | one capability serving variants without copies | absent = always run |
| E4 | **Lanes per group**: `route` sends each group down a lane (`auto`, `standard`, `enhanced`) chosen by score, amount or category; lanes differ in review, approval matrix and checklist | high-risk items get more control; low-risk get less friction | default: one lane |
| E5 | **Waiting and child cases**: a case can wait (`await`) or wait for its children (`spawn`), with deadlines; dependencies between cases (close calendar) | close management, sign-off cascades, testing per sample | new states: `waiting`, `waiting_on_children` |
| E7 | **Decision boundaries**: `boundaries: [{verdicts or actions, reserved_for: person, roles}]`, enforced in code after the model and at review (no "approve all"), shown on the case | regulated decisions (credit, sanctions, AML, KYC, release) must stay with named people | absent = today's rules |
| E6 | **Step SDK for the platform team**: a step type is a class with a config schema, `needs` and `produces`, a run function, and an editor descriptor; it is tested by a shared harness | new types added safely, each one generic | today's steps become the first users |

Branching stays declarative, through `when`, lanes and the playbook. There is no free-form flow
chart: auditors and second owners must be able to read what will happen.

## 6. Controls every step respects

These are platform rules, not per-step choices:

1. **Every external read and write goes through the gateway**, with entitlements, data scope,
   audit, masking and classification.
2. **No write without approval.** Posting, sending and publishing need a release by someone other
   than the reviewer. Ledgers get a dry run first. Writes are idempotent, and a reversal is a new,
   approved case.
3. **Rules before the model; the model is never final.** Deterministic steps run first, every
   model figure is validated, and judgement goes to a person. The model is not used for credit,
   sanctions, AML, fraud or payment release.
4. **Segregation of duties.** The preparer is not the approver, the reviewer is not the releaser,
   and authority limits apply per approval level.
5. **Period and as-of discipline.** Every amount has a date and currency; FX and reference data
   are as of the case's date; closed periods are respected.
6. **Nothing silently dropped.** Filtered, deduplicated and out-of-scope items stay on the case,
   with the reason.
7. **Reproducible.** The configuration version, data snapshots, sample seed and tool results are
   kept, so a run can be explained and repeated for an auditor.
8. **Evidence and retention.** Evidence packs, attestations and decisions are kept for the
   retention period, under legal hold when needed.
9. **Model risk.** Every model-using configuration has an eval set before going live, and drift is
   monitored. Its instructions are versioned and approved like code.
10. **Thresholds are owned.** Every threshold is a named `policy` value with an owner, never a
    literal; an unset one stops or flags rather than defaulting (P1).

## 7. The catalogue against real processes

Each row shows how the steps compose. This is how a capability owner would configure the
process.

| Process | Pipeline (★ = new) |
|---|---|
| **Three-way match (purchase order / goods receipt / invoice)** | ★`match_n` → ★`derive` (price and quantity variance) → `classify` → `group` → `reason` → `validate` → `review` → `record` → `publish` (block or release in the purchasing system) |
| **Nostro reconciliation** | `match` (statement vs ledger, date window, many-to-one) → ★`bucket` (ageing) → ★`score` → ★`route` lanes → `reason` → `review` → `record` → follow-through |
| **Accruals for goods received, not invoiced** | `load` (goods receipts) → ★`dataset` (invoices) → ★`recompute` (accrual) → ★`filter` (materiality) → ★`propose_entries` (accrual and reversal) → ★`period_check` → `validate` → `review` → ★`approve` (authority matrix) → `record` → ★`post`. *Built: `config/helix/capabilities/fin-accruals.yaml`* |
| **Balance-sheet substantiation** | `load` (trial balance) → ★`dataset` (prior periods) → ★`flux` → ★`score` (account risk) → ★`spawn` (one child case per account) → each child: ★`attest` by the account owner with evidence → parent rolls up → `review` → `record` → ★`report` |
| **Manual journal review** | `load` (journals) → ★`score` (out of hours, round amounts, unusual account pairs, user) → ★`sample` (all high, 10% medium) → `reason` → `review` → `record` |
| **SOX operating-effectiveness test** | `load` (population) → ★`sample` (seeded, stratified) → ★`spawn` (one test per sample, each with its own checklist and evidence) → roll-up → deficiency rating via playbook → `review` → ★`attest` (control owner) → ★`report`. *Built: `config/helix/capabilities/controls-operating-test.yaml` and `controls-sample-test.yaml`* |
| **Intercompany matching and netting** | ★`match_n` (entity A vs entity B, both directions) → ★`convert` (FX) → ★`aggregate` (pairs) → `classify` → ★`route` → `reason` → `review` (both entities' owners) → `record` → ★`propose_entries` (eliminations) |
| **Independent price verification** | `load` (positions) → ★`dataset` ×3 (vendor prices) → ★`derive` (median, spread) → ★`recompute` (vs desk mark) → `classify` (tolerance by asset class, fair-value level) → `reason` → `review` → ★`propose_entries` (valuation reserves) |
| **Regulatory report validation** | ★`dataset` ×n (reports, GL) → ★`consistency` (cross-report rules) → `group` → `reason` → `review` → ★`attest` (report owner) → ★`report` |
| **Close calendar** | a parent case per entity and period → ★`spawn` tasks with dependencies → ★`await` children → roll-up sign-off entity → region → group |
| **Fee and interest validation** | `load` (charges) → ★`recompute` (from the tariff tool) → `classify` → `group` → `reason` → `review` → ★`compose` (client notice, released) → `publish` (refund instruction) |
| **Invoice capture** | ★`intake` or ★`extract` (from PDFs, with low-confidence fields flagged) → ★`dedupe` → `match` (to purchase orders) → `review` → `publish` |
| **Payment exceptions (returns, repairs)** | `load` (exceptions) → ★`dataset` (FX rates) → ★`convert` (to GBP) → ★`derive` (age in hours) → ★`bucket` (SLA band) → ★`dedupe` (duplicate submissions) → ★`filter` (test payments) → ★`transform` (the team's own risk score) → `group` (by reason code) → `reason` → `review` → `record` → `publish` (repair instruction, released). *Built in phase 1: `config/helix/capabilities/payments-exceptions.yaml`* |
| **Payment investigation (customer claim)** | `load` → ★`timeline` (gpi, nostro, messages) → ★`clock` (24 h) → ★`outreach` (counterparty bank query) → ★`await` → `reason` → `review` → ★`compose` (customer reply) → `publish` |
| **Failed settlement** | `load` (fails) → `enrich` (static data) → `classify` (cause: SSI, inventory, counterparty) → ★`clock` (market cut-off) → ★`outreach` (counterparty) → `review` → `record` → follow-through (settled next day?) |
| **Complaint handling** | ★`intake` (complaint) → ★`timeline` (account events) → ★`link` (prior complaints) → ★`clock` (8 weeks, paused on client) → `reason` (proposed outcome and redress, ★`recompute`) → ★`approve` (redress authority matrix) → ★`compose` (final response) → `publish`. *Built: `config/helix/capabilities/client-complaints.yaml`* |
| **AML alert triage pack** | `load` (alerts) → ★`timeline` (transactions) → ★`link` (related parties, prior alerts) → ★`screen` (candidate hits) → `reason` (narrative only; **E7: close or escalate is reserved for the analyst**) → `review` → `record` |
| **KYC periodic review** | ★`spawn` (one per client due) → ★`outreach` (documents) → ★`extract` (from documents) → `classify` (missing or expired) → `review` (KYC officer, reserved decision) → ★`attest` |
| **Covenant monitoring** | ★`extract` (financials from the borrower's pack) → ★`derive` (ratios) → `classify` (breach, near-breach) → `reason` (credit memo draft) → `review` (credit officer, reserved) → `record` → follow-through (next quarter) |
| **Limit breach investigation** | `load` (breaches) → ★`dataset` (limits, exposure history) → ★`flux` → `reason` → ★`approve` (temporary excess by authority) → `record` → follow-through |
| **User access review** | `load` (entitlements) → ★`spawn` (one per manager) → ★`attest` (keep or revoke per line) → ★`report` → `publish` (revocations, released) |
| **Operational loss event** | ★`intake` (event) → ★`derive` (gross/net loss, FX via ★`convert`) → `classify` (Basel event type) → ★`clock` (reporting deadline) → `review` → ★`attest` (business owner) → `record` |
| **FOBO (today)** | `load` (MB Rec) → `enrich` → `resolve` → `classify` → `group` → tollgate → `reason` → `draft` → `validate` → `review` → `record` → follow-through |

Every row uses only generic steps. Nothing in the catalogue is specific to one team or one division: finance, operations, risk, compliance, lending and client service configure the same building blocks.

## 8. Plan

| Phase | Delivers | Unlocks |
|---|---|---|
| **1. Engine foundations** ✅ *built* | E1 step instances, E2 named data sets, E3 conditional steps, E6 step SDK; ★`dataset`, `derive`, `filter`, `convert`, `bucket`, `aggregate`, `dedupe`, `transform` | most data preparation by configuration; teams plug in their own logic (`transform`); first non-finance capability: payment exceptions |
| **2. Accounting actions** ✅ *built* | ★`propose_entries`, `schedule`, `period_check`, `approve` (authority matrix), `post` (dry run, then post), `recompute` | accruals, adjustments, reserves, write-offs end to end |
| **3. Assurance** ✅ *built* | ★`sample`, `score`, `anomaly`, `flux`, `consistency`, `attest`, E4 lanes | SOX testing, journal review, substantiation, report validation |
| **4. Orchestration** ✅ *built* | E5 `await`, `spawn`, dependencies; ★`report`, `compose` | close management, sign-off cascades, testing per sample, counterparty workflows |
| **5. Acquisition** ✅ *built* | ★`match_n`, `intake`, `extract` | three-way match, intercompany, invoice capture, document-heavy work |
| **6. Time, context and parties** ✅ *built* | ★`clock`, `timeline`, `link`, `screen`, `outreach`; E7 decision boundaries | payments and trade operations, complaints, KYC, financial-crime packs, lending |

Each phase:
- keeps today's capabilities running unchanged;
- adds the steps to the Configure editor and the guided authoring questions;
- ships with tests;
- adds a worked example capability to `docs/helix/examples/`.

## 9. As built

All six phases are built. The step types are in `helix/stepkit.py` (data) and
`helix/steps_v2.py` (the rest). The engine changes are in `helix/workflow.py`, `runner.py`,
`authority.py` and `timekeeping.py`. Each type has a form in *Configure → Configurable steps*.
The developer guide §7b is the reference.

Where the build differs from the plan above:
- **`route` and `approve` are review settings, not steps.**
  - Lanes (E4) and the approval matrix are one setting: `review.authority`.
  - Tiers carry `lane`, `roles`, `approvals` and `bulk`.
  - Placing them in `review` means they apply to every group whatever steps ran.
- **The authority matrix can come from either place.**
  - In configuration: `review.authority` tiers.
  - From the bank's delegated-authority system: a `dataset` step, named in
    `review.authority_dataset`.
- **Decision boundaries (E7) are a top-level setting.**
  - `boundaries` is set per capability, in each capability's own words.
  - Each boundary names a `when` or `verdicts`, the roles, and whether the model may propose.
- **`extract` has both controls.**
  - A confidence threshold (`accept_confidence`).
  - A `regulated` flag that sends every value to a person.
  - In all cases a value must appear in its quote, and the quote must appear in the document.
- **Waiting (E5) is a status.**
  - A waiting case has status `waiting_<step>`, continued by an event (the events API or a
    person) or by its child cases finishing.
  - The scheduler times waits out and keeps clocks.
- **Dependencies between tasks** (a close calendar) are a parent that waits on children, layered
  as needed. There is no separate dependency graph.

Example capabilities, with stub connectors here and office connector examples in
`config/helix/connectors.office.example.yaml`:
- month-end accruals (`fin.accruals`);
- complaint handling (`client.complaints`);
- a control operating test with one child case per sample (`controls.operating-test`,
  `controls.sample-test`).

## 10. Decisions taken

All the options were taken:
- phases in the proposed order;
- the authority matrix in configuration **or** from the bank's system;
- `extract` with a threshold **and** a regulated flag;
- boundaries per capability;
- each office system as a connector.

The original questions follow for the record.

## 11. Decisions needed (original)

1. **The order of the phases.** The proposal is 1 → 2 → 3 → 4 → 5. Phase 2 comes before 3 if
   journals are the priority.
2. **Which ledger and calendar tools** `post` and `period_check` call in the office. Each is a
   connector.
3. **Whether `extract` (model reading documents) is allowed** for regulated documents, and with
   what confidence threshold for automatic acceptance.
4. **The authority matrix source.** Is it held in Agent One Finance configuration, or read from the bank's
   delegated-authority system?
