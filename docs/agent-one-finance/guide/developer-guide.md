# Agent One Finance developer guide and specification

**Date:** 2026-10-04 · For engineers who run, extend and onboard Agent One Finance.
End users: see [`user-guide.md`](user-guide.md).

**Contents**

1. [Architecture](#1-architecture)
2. [Repository layout](#2-repository-layout)
3. [Run it locally](#3-run-it-locally)
4. [Create a capability (spec walk-through)](#4-create-a-capability)
5. [Add a team group](#5-add-a-team-group)
6. [Manifest specification](#6-manifest-specification)
7. [Steps and gates](#7-steps-and-gates)
8. [Expressions](#8-expressions)
9. [Playbooks (FOBO-style rules)](#9-playbooks)
10. [Connectors and the gateway](#10-connectors-and-the-gateway)
11. [Knowledge graph and reference data](#11-knowledge-graph-and-reference-data)
12. [Data protection](#12-data-protection)
13. [Settings (environment)](#13-settings)
14. [HTTP API](#14-http-api)
15. [Extension points](#15-extension-points)
16. [Testing](#16-testing)
17. [Deploying in the office](#17-deploying-in-the-office)

## 1. Architecture

```
 Browser (apps/web: React 18 + TS + Vite + Tailwind, Barclays light/dark)
   │  /api  (identity header from SSO; X-AOF-User in dev)
   ▼
 Agent One Finance API  (FastAPI, apps/backend/agent_one_finance/web/main.py, :8300)
   ├── capabilities / groups   versioned manifests, four-eyes approval, config_sync
   ├── cases                   open → run → review → record → (release → publish)
   │     └── runner ── LangGraph StateGraph per manifest
   │            · AsyncPostgresSaver checkpoints · interrupt before review/publish
   │            · background runs, advisory lock, startup recovery
   ├── steps                   load, match, enrich, resolve, classify, compare, group,
   │                           reason, draft, validate*, review*, record*, publish  (*gates)
   ├── llm                     none | stub | agent_sdk (Claude Agent SDK) | module:attr
   ├── gateway (MCP client)    allow-list · data-scope check · audit row · protection · trace
   │     └── connectors (MCP servers): gl, budget, bank, ledger, cats, motif, documents, …
   ├── knowledge               bitemporal graph: reference lineage + approved decisions (priors)
   ├── governance              mask / pseudonymize / scrub between data and the model
   ├── scheduler, events       cron + key templates; POST /api/events
   ├── notify, controls        bell + webhook; off switches; spend limits
   ├── evidence, evals         uploads, evidence pack PDF; shadow runs on past cases
   └── devtools                diff, instructions, flow, templates, promotion bundles
   ▼
 Postgres 16 (SQLAlchemy async, Alembic)  ·  OpenTelemetry/OpenInference → Phoenix
```

There are five rules the design holds to:

1. **No code per use case.** A capability is a manifest. New work means a new YAML file.
2. **The model proposes; code and people decide.** Guards and validation run after the
   model, and people approve.
3. **Every data access goes through the gateway**, which checks the allow-list and data
   scope, writes an audit row, and applies protection.
4. **Gates cannot be removed.** validate, review and record are always present.
5. **A case keeps the exact manifest it ran on.** Past runs never change.

## 2. Repository layout

| Path | What |
|---|---|
| `apps/backend/agent_one_finance/` | the platform: `manifest.py` (spec), `workflow.py` + `steps.py` (engine), `runner.py`, `cases.py`, `gateway.py`, `llm.py`, `llm_agent_sdk.py`, `governance.py`, `knowledge.py`, `groups.py`, `capabilities.py`, `scheduler.py`, `controls.py`, `notify.py`, `evidence.py`, `evals.py`, `devtools.py`, `config_sync.py`, `retention.py` |
| `apps/backend/agent_one_finance/web/main.py` | the HTTP API |
| `apps/backend/agent_one_finance/mcp_services/documents.py` | documents MCP service: read PDF / Excel, build PDF reports |
| `apps/backend/agent_one_finance/stub_connectors/` | dev stand-ins for GL, budget, bank, ledger, CATS, MOTIF |
| `apps/backend/migrations/` | Alembic migrations (Agent One Finance and FOBO share the DB) |
| `apps/backend/tests/agent_one_finance/` | Agent One Finance tests |
| `apps/web/` | the Agent One Finance web app |
| `config/agent-one-finance/capabilities/*.yaml` | live capabilities (seeded / synced) |
| `config/agent-one-finance/groups/<capability>/*.yaml` | team groups |
| `config/agent-one-finance/connectors.yaml` | onboarded connectors and their tool allow-list |
| `config/agent-one-finance/governance.yaml` | data protection rules |
| `config/agent-one-finance/knowledge/*.yaml` | reference lineage (e.g. `fobo-reference`) |
| `config/agent-one-finance/templates/*.yaml` | starting points in *Authoring* |
| `config/agent-one-finance/dev-users.yaml` | dev entitlements stand-in |
| `docs/agent-one-finance/examples/` | ready-to-install example capabilities |
| `apps/backend/fobo`, `apps/console` | the FOBO app; unchanged and still running |

## 3. Run it locally

```bash
docker compose up -d postgres                       # Postgres 16 on :5433
cd apps/backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn agent_one_finance.web.main:app --port 8300    # seeds config/agent-one-finance on first start

cd ../web && npm install && npm run dev             # http://localhost:5180 (proxies /api → :8300)
```

The defaults are `AOF_LLM_ADAPTER=stub` (deterministic, no model calls), tracing off,
and dev entitlements. Pick a user in the top-right menu. To bring changed config files into
a running database:

```bash
cd apps/backend && .venv/bin/python -m agent_one_finance.config_sync   # each changed file → a draft
```

Then approve the drafts in *Authoring* as a second owner.

## 4. Create a capability

This is the walk-through behind the user guide's screenshots: **Accruals review**
([`../examples/accruals-review.yaml`](../examples/accruals-review.yaml)). The file has six
parts:

```yaml
# 1. Identity and owners: who may change it (four-eyes: the drafter cannot approve)
id: fin.accruals-review
name: Accruals review
owners: { people: [carol], role: AOF_FIN_VARCOMM_OWNER, four_eyes: true }

# 2. What one case is, and how it opens
case:
  label: Accruals
  item_label: Accrual line
  key: [entity, period]                 # identifies a case
  subject: "{entity} accruals · {period}"
  scopes: { entity: entity }            # case field → entitlement dimension
  opens_on: schedule
  schedule: "0 9 3 * *"                 # 09:00 on the 3rd
  schedule_keys: [{ entity: UK01, period: "{prev_month}" }, { entity: US01, period: "{prev_month}" }]
  opens_as: aof-scheduler

# 3. Where the items come from, and which are in scope
items:
  load: { tool: gl.balances, args: { entity: $case.entity, period: $case.period } }
  id_field: line_id
  amount_field: variance
  display: [account, account_name, cost_centre, actual, budget, variance]
  in_scope: (startswith(account, '6') or startswith(account, '7')) and abs(variance) >= policy.materiality
compare: { measure: actual, baseline: budget, as: variance }
policy: { materiality: { value: 25000, unit: GBP } }

# 4. The workflow (gates are mandatory) and how items group
steps: [load, compare, group, reason, draft, validate, review, record]
group_by: [account]
rules:                                  # settle the obvious without the model
  - id: fx-reval
    when: startswith(account, '71')
    then: { status: proposed, comment: "Account {account}: {total} is FX revaluation of accrued balances; no action." }

# 5. The model: instructions and the read tools it may call
reasoning:
  reasoner: llm
  tools: [gl.journal_lines, budget.plan_lines]
  skill: |
    You review month-end accruals. ...

# 6. People and limits
review: { roles: [FIN_PREPARER, FIN_REVIEWER], dual_review_when: "abs(total) >= 250000" }
knowledge: { entities: [account, cost_centre] }
limits: { max_cost_usd_per_case: 5, max_cost_usd_per_day: 50 }
retention: { days: 2555 }
```

To get it live, do **one** of the following:

- Paste it in *Authoring* and submit; a second owner approves it.
- Put it in `config/agent-one-finance/capabilities/` and run `config_sync`; a second owner approves.
- On a fresh database, it is seeded at startup.

`POST /api/authoring/submit` runs the same validation as the UI. Before you submit, check:

- every tool exists in `connectors.yaml`;
- every expression parses and uses only allowed names;
- `steps` contains the gates in order;
- every `publish` tool has `access: write`;
- the roles are set.

## 5. Add a team group

A capability lists `configurable` paths. A group file sets only those paths, and its own
owners approve its changes. The capability's owners keep the workflow, gates, write-back
and retention.

```yaml
# config/agent-one-finance/groups/recon.investigation/cats-motif-rates.yaml (abridged)
group: cats-motif-rates
name: CATS vs MOTIF — Rates (FOBO)
owners: { people: [rita, raj], role: AOF_FOBO_RATES_OWNER, four_eyes: true }
set:
  case:   { key: [book, cob], scopes: { book: book }, schedule: "15 7 * * 1-5", schedule_keys: [...] }
  match:  { left: { tool: cats.positions, ... }, right: { tool: motif.positions, ... }, tolerance: 1.0 }
  policy: { materiality_threshold: { value: 10000, unit: GBP }, ... }
  playbook: { ... }                     # same playbook as Prime
  reasoning: { skill: "...", tools: [motif.booking_events] }
  review: { roles: [FOBO_RATES_CONTROLLER] }
```

A value at a configurable path **replaces** the capability's value; it is not merged. A
path that is not configurable is refused with the list of allowed paths. Visibility is
per group: a person sees a group's cases and schedule only when they hold its review
role or are an owner, *and* the case is inside their data scope.

## 6. Manifest specification

Source of truth: `apps/backend/agent_one_finance/manifest.py` (Pydantic; unknown keys are refused).

### Top level

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | `^[a-z0-9][a-z0-9.-]{1,62}$` | required | stable id |
| `name`, `description` | str | | shown in the catalogue |
| `owners` | Owners | required | who may change it |
| `case` | CaseSpec | required | what a case is, how it opens |
| `items` | ItemsSpec | required | where items come from |
| `match` | MatchSpec | — | two-sided reconciliation (instead of `items.load`) |
| `compare` | CompareSpec | — | measure vs baseline → a variance field |
| `policy` | {name: {value, unit?}} | {} | thresholds used in expressions as `policy.<name>`; `null` = not confirmed |
| `steps` | list of step ids | required | see §7; core steps by name, configurable steps by any id |
| `step_settings` | {id: {type, when, label, with}} | {} | the type and settings of each configurable step (31 types, §7b), and `when` on any non-gate step |
| `boundaries` | list | [] | decisions reserved for named people (§7b) |
| `pause_before` | list | `[review]` | the run waits for people before these steps |
| `tollgates` | {step: {roles, check, stop_needs_comment}} | {} | who passes each stop other than review and publish, and what they check (§7a) |
| `requests` | {targets: [{id, name, roles, users}], hold_decision, reinvestigate_on_answer, remind_after_hours, escalate_after_hours, allow_attachments} | no targets | who reviewers may ask for evidence; an open question holds its group; an answer (optionally with a file) goes to the model; unanswered ones are chased, then escalated |
| `follow_through` | {series, order_by, verdicts} | — | re-check each decision in the next run of the series: items still there carry `carried_verdict`, `carried_from`, `carried_runs` (and groups `carried`); the earlier case shows what cleared |
| `group_by` | list | [] (one group) | item fields that form a group |
| `rules` | list[Rule] | [] | settled before the model |
| `reasoning` | ReasoningSpec | | the model; `reasoning.sections` [{id, label, hint, required}] makes it answer in named parts (a required one missing → escalated; every section's figures are validated) |
| `review` | ReviewSpec | required | who decides; `review.checklist` [{id, label, required, prefill}] are questions answered before approving (prefill: tests, evidence, verdict, category or a section id) |
| `publish` | PublishSpec | — | write-back after release |
| `enrich` | list[EnrichSpec] | [] | join more data onto items |
| `playbook` | PlaybookSpec | — | deterministic checks, tests, verdicts (§9) |
| `knowledge` | KnowledgeSpec | | priors and reference lineage |
| `resolve` | list[ResolveSpec] | [] | graph lookups onto items |
| `retention` | {days} | — | how long cases are kept (legal hold overrides) |
| `insights` | {recurring, unexplained: {categories, lookback_days}, automation_after} | | items that keep coming back; items nothing explained; model proposals approved unchanged N times (rule candidates). `GET /api/capabilities/{id}/recurring`, `/learning` |
| `metrics` | {manual_minutes_per_item: 12} | | basis of "hours saved" |
| `limits` | {max_cost_usd_per_case, max_cost_usd_per_day} | — | spend caps; over the cap → escalate to people |
| `configurable` | list of dotted paths (`x.*` allowed) | [] | what groups may set |

### Owners

| Field | Default | Meaning |
|---|---|---|
| `people` | [] | user ids |
| `role` | — | an entitlement role |
| `four_eyes` | true | the drafter of a version cannot approve it |

### case

| Field | Default | Meaning |
|---|---|---|
| `label`, `item_label` | Case / Item | wording in the UI |
| `key` | required | fields identifying a case, e.g. `[entity, period]` |
| `subject` | — | template, e.g. `"{book} · COB {cob}"` |
| `scopes` | {} | case field → entitlement dimension, checked on every read |
| `opens_on` | manual | manual · api · schedule · event |
| `schedule` | — | cron (`min hour dom mon dow`, in `AOF_SCHEDULE_TZ`) |
| `schedule_keys` | [] | keys to open per tick; templates `{prev_business_day}`, `{prev_month}`, … |
| `events` | false | may `POST /api/events` open cases |
| `opens_as` | — | the service user scheduled or event cases run as |

`case.late_items`: `ignore` (default) or `follow_up`. With `follow_up`, a later event for a key that
already has a case opens a follow-up case (`<case>.f<n>`, `follow_up_of` set). Its `load` takes
only the items no case for that key has yet. With nothing new, it closes as `no_new_items`.

### items, match, compare, enrich

| Spec | Fields |
|---|---|
| `items` | `load: {tool, args}`, `id_field`, `amount_field`, `display` (columns), `in_scope` (expression) |
| `match` | `left`, `right` (`{tool, args}`), `keys`, `amount_field`, `tolerance` (0.0), `left_label`, `right_label` → items carry `break_type` (`amount_break`, `missing_<right_label>`, `missing_<left_label>`) and `difference` |
| `compare` | `measure`, `baseline`, `as` (variance) |
| `enrich[]` | `tool`, `args`, `keys` (join keys), `prefix` |

Tool arguments can use `$case.<field>`, `$case_id` and `$subject`.

### rules[]

```yaml
- id: fx-rounding
  when: abs(total) <= policy.fx_tolerance       # over the group's fields
  then: { status: proposed | escalated, comment: "template {total} {currency}", reason: "..." }
```

### reasoning

| Field | Default | Meaning |
|---|---|---|
| `reasoner` | llm | `llm` or `none` (people only) |
| `skill` | "" | instructions to the model |
| `tools` | [] | read tools the model may call (via the gateway) |
| `specialists[]` | [] | Agent SDK subagents: `name`, `description`, `instructions`, `tools` |
| `output` | commentary | verdict · commentary · classification |

### review

| Field | Default | Meaning |
|---|---|---|
| `roles` | required | who may decide |
| `require_comment` | reject, escalated | when a comment is mandatory |
| `opener_may_decide` | true | maker-checker when false |
| `dual_review_when` | — | expression: true → two approvers |
| `authority` | [] | tiers: `when`, `label`, `roles`, `approvals` (1–5), `lane`, `bulk` (§7b) |
| `authority_dataset` | — | a data set read from the bank's delegated-authority system, used instead of `authority` |
| `max_reinvestigations` | 2 | "Investigate again" limit (0–10) |

### publish (write-back)

| Field | Meaning |
|---|---|
| `tool` | a connector tool with `access: write` |
| `per` | `group` (one call per approved group) or `case` (one call, e.g. a PDF report) |
| `args` | literals, `$case.*`, `$case_id`, `$subject`; per group `$group.<field>` and `$comment`; per case `$approved` and `$sign_off` |
| `approver_roles` | who may release; a different person from the reviewer |

### knowledge, resolve

| Spec | Fields |
|---|---|
| `knowledge` | `entities` (item fields linked in the graph, for priors), `reference` (namespace, e.g. `fobo-reference`), `as_of` (case field for bitemporal reads, e.g. `cob`), `priors_lookback_days` |
| `resolve[]` | `node` (template, e.g. `"book:{book}"`), `path` (relations, e.g. `[belongs_to, escalates_to]`), `as` (item field to set), `take` (`name` or an attribute or `id`) |

## 7. Steps and gates

| Step | Needs | Produces | Notes |
|---|---|---|---|
| `load` | case key | items | `items.load` |
| `match` | case key | items | `match`; two sides, tolerance |
| `enrich` | items | items | joins `enrich[]` |
| `resolve` | items | items | knowledge-graph lookups as of `knowledge.as_of` |
| `classify` | items | items | playbook checks, tests, findings |
| `compare` | items | items | `compare` |
| `group` | items | groups | `group_by` |
| `reason` | items, groups | findings | playbook table → rules → model (in parallel per group) → guards |
| `agent` | case key | items, groups, findings | a skill session: the skill, the case key and `reasoning.tools` go to the model in one session; one result per item ([skill-session.md](skill-session.md)). `steps: [agent]` alone is a whole workflow: draft and the gates are added |
| `draft` | groups, findings | draft | headline and summary |
| `validate` ◆ | findings | findings, validation_errors | every figure must trace to the run's data or tool results; otherwise escalated |
| `review` ◆ ⏸ | findings, draft | decisions | people |
| `record` ◆ | decisions | outcome | approved decisions go to the knowledge graph (future priors) |
| `publish` ⏸ | decisions | published | after release; idempotent |

◆ marks a gate, which is mandatory. ⏸ marks a pause (`pause_before`). The order is checked
on submit: every step's inputs must be produced by an earlier step.

### How the steps feed the model

The steps run in order, and each one adds to what the model is given. The model never
compares the two systems itself: `match` does that in code (keys plus tolerance), so the
breaks are exact, repeatable and the same on every run. By the time a group reaches
`reason`, each item carries:

1. **Both sides' values and the difference** — from `match` (or `load` and `compare`).
2. **Extra data joined on** — from `enrich`, e.g. dated FO/BO snapshots.
3. **Reference data as of the business date** — from `resolve`, e.g. the owning desk and
   team.
4. **The playbook's work** — from `classify`: every cause check (negatives kept), every
   validation test (pass, fail or not run), the category and the side.
5. **Its group, and priors** — from `group`: similar approved decisions from the
   knowledge graph.

The model then gets one group at a time with all of that, plus:
- the read tools the capability allows (through the gateway);
- its instructions;
- any specialists.

What the rules or the verdict table settle never reaches the model. Whatever it proposes
is checked afterwards by the guards and `validate`.

## 7a. Tollgates: a person approves the work so far

Any step except the first can have a **tollgate** (`pause_before` plus an optional
`tollgates` entry). The run stops before that step and waits for a person, who sees what the
earlier steps produced and then either:

- **continues** — the run resumes at that step from its checkpoint, or
- **stops** — the case ends as `stopped`, with their reason, and may be re-run as a new
  attempt.

```yaml
pause_before: [reason, review, publish]
tollgates:
  reason:                       # before the model is asked anything
    roles: [FIN_REVIEWER]       # empty = the capability's reviewers
    check: Do the variances tie to the ledger, and is the budget this month's?
    stop_needs_comment: true
```

- **How it shows.** The case status is `paused_before_<step>`. It appears in the inbox of
  people with those roles (action `gate`), notifies them, and counts against the deadline.
- **How it is recorded.** Each decision is stored in `aof_gate_decision` and shown on the
  case.
- **What crosses it.** A run crosses a tollgate only through `POST /api/cases/{id}/gates/{step}`
  (`{action: continue|stop, comment, idempotency_key}`). A recovery or restart never skips
  it.
- **Where to set it.** In *Configure*: each step has a "Tollgate" switch with who passes it
  and what they check.

Typical places:
- before `reason`: check the matched data before any model spend;
- before `group`: check the playbook's classification;
- before `enrich`: check the match is complete.

## 7b. Configurable steps (steps v2)

Besides the core steps, a capability adds **generic data steps** by configuration, as many as it
needs and in any order, each under its own id:

```yaml
steps: [load, fx, dedupe_refs, drop_tests, to_gbp, age, sla, risk, group, reason, draft, validate, review, record]
step_settings:
  fx:          {type: dataset,  with: {name: fx, tool: refdata.fx_rates, args: {date: $case.date}}}
  dedupe_refs: {type: dedupe,   with: {keys: [payment_ref, amount]}}
  drop_tests:  {type: filter,   with: {keep_when: "not is_test", reason: test payment}}
  to_gbp:      {type: convert,  with: {amounts: [amount], currency_field: currency, to: GBP, rates: fx}}
  age:         {type: derive,   with: {fields: {age_hours: "hours_between(received_at, case.date + 'T18:00:00')"}}}
  sla:         {type: bucket,   with: {field: age_hours, as: sla_band, bands: [{label: within 4h, upto: 4}, {label: over 4h}]}}
  risk:        {type: transform, when: "count > 0", with: {tool: payments.risk_score, send: [amount_gbp, reason_code], returns: fields}}
```

| Type | Does | Settings |
|---|---|---|
| `dataset` | reads a **named data set** beside the items (rates, limits, budget, prior periods); kept on the case | `name`, `tool`, `args` |
| `derive` | computed fields from expressions over the item, `case.<field>` and `policy`; a failure gives `None` and `derive_errors`, never a guess | `fields: {name: expression}` |
| `filter` | keeps matching items; the others **stay on the case** with `excluded_by` and `excluded_reason` | `keep_when`, `reason` |
| `convert` | currency conversion with a data set of rates; a missing rate sets `fx_missing`, never assumed | `amounts`, `currency_field`, `to`, `rates`, `suffix` |
| `bucket` | bands (ageing, size, service level) | `field`, `as`, `bands[{label, upto}]` |
| `dedupe` | duplicates by key fields, set aside (kept) or marked | `keys`, `drop` |
| `aggregate` | roll-up with totals and counts, into the items or a data set | `by`, `sum`, `keep`, `into` |
| `transform` | sends the items (only the fields in `send`) to a **team's own tool** through the gateway and uses what it returns | `tool`, `args`, `send`, `returns: fields\|items` |

`when` on any step (not the gates): an expression over `case.<field>`, `policy.<name>` and `count`
(items so far). A step that does not run is recorded in the case's draft (`skipped_steps`).

The platform checks each step's settings against its schema and its expressions when the manifest
is checked. It checks the order with what each step needs and produces, including named data sets:
"`to_gbp` needs data set `fx`, produced by no earlier step". The tools a step calls are the only
ones the gateway allows. New types are added through the step SDK (`agent_one_finance/stepkit.py`): a config
schema, `needs`, `produces`, `tools`, `expressions` and a run function. The design and the next
phases are in [`../design/step-catalogue-v2.md`](../design/step-catalogue-v2.md).

Expressions gained `case.<field>`, `days_between`, `hours_between`, `weekday`, `coalesce`,
`ifelse`, `lower`, `upper`, `int` and `sum`.

### The other families (phases 2–6)

| Family | Type | Does | Settings |
|---|---|---|---|
| Accounting | `recompute` | recalculates a figure (fee, interest, accrual) by formula or a team's tool and compares it with what was booked; `<as>_ok` is `None` when it cannot tell | `formula` or `tool`, `compare_to`, `as`, `tolerance` |
| | `schedule` | spreads each item's amount over periods into a data set (the last period takes the rounding) | `amount`, `periods`, `start`, `into` |
| | `period_check` | stops the run (escalated, `PERIOD_CLOSED`) if the period is not open | `tool`, `args`, `status_field`, `open_values` |
| | `propose_entries` | balanced journals per group, checked against a chart-of-accounts data set; an unbalanced entry escalates the group (`ENTRY_INVALID`) | `when`, `lines[{account, side, amount, narrative}]`, `period`, `chart`, `into` |
| | `post` | after `record`: posts the **approved** journals, the ledger's own check (`dry_run_tool`) first, each once (idempotency key); outcome `posted` or `post_failed` | `tool` (write), `dry_run_tool`, `args`, `approver_roles` |
| Assurance | `flux` | change, % change and z-score of each item against its own history (a data set); `method: robust` uses median and MAD; `same` compares like with like (e.g. month-end) | `history`, `key`, `value`, `history_value`, `prefix`, `method`, `same` |
| | `anomaly` | flags items far from their history (z-score threshold) | as `flux`, plus `threshold` |
| | `consistency` | totals across items and data sets; each failing check becomes an item | `checks[{id, left, right, tolerance, message}]` |
| | `sample` | reproducible sample (seed kept): random, largest, weighted by value, or systematic monetary-unit (`mus`); stratified; some always in; the rest kept, marked | `method`, `size` or `percent`, `field`, `stratify_by`, `always_include_when` |
| | `score` | weighted factors and/or a numeric formula → score, reasons and band (a priority: size, age, recurrence) | `factors[{when, weight, label}]`, `formula`, `as`, `bands` |
| | `attest` | an owner certifies a statement at the tollgate before it; who, when, evidence, expiry kept (`attestations`) | `statement`, `roles`, `evidence_required`, `valid_for_days` |
| Orchestration | `await` | the run waits (status `waiting_<step>`) for an event or for its child cases; times out to a person or carries on | `event` (`children` for child cases), `timeout_hours`, `on_timeout`, `roles` |
| | `spawn` | one child case per item in another capability (`parent_case_id`) | `capability`, `team_group`, `key`, `max_children` |
| | `compose` | drafts each group's message for the reviewer (never sent by itself) | `when`, `to`, `subject`, `body` |
| | `report` | after `record`: the case's PDF report, kept with the case (`documents`) | `name` |
| Acquisition | `match_n` | matches 2–6 systems by key, many-to-one sums; keeps what does not agree (`amount_break`, `missing_<system>`) | `sources[{label, tool, args, amount_field}]`, `keys`, `tolerance` |
| | `intake` | a workbook into items by column map; failing rows kept aside with `intake_problems` | `tool`, `columns`, `id_field`, `required`, `numbers` |
| | `extract` | fields from a document: patterns, then the model (`extract` on the adapter); a value must appear in its quote and the quote in the document; below `accept_confidence`, or every value when `regulated`, goes to a person | `tool`, `fields[{name, hint, required, pattern}]`, `accept_confidence`, `regulated` |
| Time and parties | `clock` | service-level or regulatory clocks per item (hours or business days, paused hours); warned before and on breach (scheduler) | `clocks[{id, label, starts, hours or business_days, warn_before_hours, pause_hours_field}]` |
| | `timeline` | one ordered timeline from several systems; the model reads it (`for_model`) | `sources[{tool, args, time_field, label}]`, `into` |
| | `link` | earlier cases on the same client/account/counterparty, in any capability | `match_on`, `lookback_days`, `capabilities`, `limit` |
| | `screen` | fuzzy name matching against a list data set: **candidates only**, never cleared by Agent One Finance | `list`, `fields`, `list_field`, `threshold` |
| | `outreach` | sends each drafted message through a write tool after a person approves at the tollgate before it | `tool` (write), `roles`, `when` |
| Algorithms ([guide](algorithms.md)) | `offsets` | pairs equal-and-opposite amounts in the same group | `amount`, `within`, `same`, `tolerance`, `as` |
| | `subset_match` | up to 5 rows (a data set or the other items) that add up to the item's amount; smallest first; says if ambiguous | `target`, `pool`, `pool_value`, `pool_label`, `within`, `when`, `sign`, `max_size`, `max_pool`, `tolerance`, `as` |
| | `trend` | growing, shrinking, steady or flipping over the item's history; slope | `history`, `key`, `value`, `history_value`, `order`, `oldest_first`, `min_points`, `as` |
| | `cluster` | how many other books or entities break the same way (counts only, unless `show_where`) | `same`, `across`, `amount`, `within_pct`, `min_count`, `peers_tool`, `peers_args`, `show_where`, `as` |
| | `fuzzy_match` | near-identical references (Jaro–Winkler), optionally a similar amount: candidates only | `field`, `pool`, `pool_field`, `when`, `amount`, `pool_amount`, `amount_within_pct`, `threshold`, `as` |
| | `benford` | first digits against Benford's law (Nigrini's bands) and round amounts over the items; too few is "not run" | `field`, `min_items`, `round_to`, `as` |

**Rules the platform checks.**
- Only `publish` or `post` (one of them) and `report` may follow `record`; the run must pause
  before the write-back step for a second person.
- `attest` and `outreach` need a person first: their id must be in `pause_before` (their
  tollgate, passed by their `roles`).
- A `spawn` needs a later `await` with `event: children`.
- A step that writes may only name `access: write` tools; any other step may only read.
- `await` steps pause the run by themselves.

**Waiting and events.**
- A case at an `await` step has status `waiting_<step>` and `waiting_since`.
- A system delivers the event with `POST /api/cases/{id}/events/{step}`, sending
  `X-AOF-Event-Secret` and a body of `{payload: {...}}`.
- A person with the step's `roles` can deliver it from the case page.
- The scheduler continues a wait past `timeout_hours` with `{timed_out: true}`.
- For `event: children` the run continues on its own once every child case has finished, and the
  children's outcomes land on the items as `child_status` and `child_outcome`.

### Authority and decision boundaries (E7)

```yaml
review:
  roles: [FIN_PREPARER, FIN_REVIEWER]
  authority_dataset: authority        # rows from the bank's delegated-authority system: min_amount, max_amount, roles, approvals, lane, bulk
  authority:                          # …or tiers in configuration (first that holds applies)
    - { when: "total >= 1000000", label: large, roles: [FIN_CONTROLLER], approvals: 2, lane: enhanced, bulk: false }
    - { label: standard }
boundaries:
  - when: "total > policy.redress_limit"     # or verdicts: [RETURN]
    roles: [COMPLAINTS_LEAD]
    model_may_propose: false
    reason: redress above the handler's limit
```

- **Authority tiers** are applied to every group's proposal (`finding.authority`).
  - A person without the tier's roles is refused ("above your authority").
  - The group needs `approvals` *different* people.
  - With `bulk: false` it is left out of "Approve all".
  - The case shows `approvals: {needed, by, settled}` per group.
- **Boundaries** reserve a decision for named roles (`finding.reserved`).
  - Nobody else may decide it, and it is never decided in bulk.
  - If the model proposed it and `model_may_propose` is false, the proposal is withheld
    (`withheld_proposal`) and the group goes to a person (`RESERVED: …`).
- Who may see a case widens to the release, tier, boundary and tollgate roles.

## 8. Expressions

Expressions appear in `in_scope`, `rules[].when`, `dual_review_when`, playbook
`checks/tests/findings/guards`. They are a safe Python subset, parsed with `ast` and
whitelisted:

- **Names:** item or group fields, `policy.<name>`.
- **Operators:** `and or not`, comparisons, `+ - * / %`, `in`.
- **Functions:** `abs min max len round float str startswith contains symdiff`.

Anything else is refused at validation, with the allowed list in the error.

## 9. Playbooks

This is how FOBO's rulebook is expressed. See
`config/agent-one-finance/groups/recon.investigation/cats-motif.yaml` and
[`../fobo-on-agent-one-finance.md`](../fobo-on-agent-one-finance.md).

| Part | Meaning |
|---|---|
| `checks[]` | `{id, when, category, side, reason}`. All checks run on every item and negatives are kept. The first positive check is the cause. |
| `tests[]` | `{id, side, validates, check, fails_when, needs, evidence, policy, on_fail, requires_on_fail, blocks_post}`. A test whose `needs` are missing or whose `policy` is unset is **not run**, never passed. |
| `findings[]` | `{id, test, when, indicates, side, description}`. A finding explains a break that no check explained. |
| `categories` | `{X: {name, determinism: deterministic|judgement, escalate_to, any_side}}`, plus `default_category`. `any_side: true` settles the category by its table even when the side is not proven (e.g. books not complete); its table must give one verdict for every side |
| `verdicts` | category × side → verdict. Deterministic + proven side = settled by the table (`decided_by: playbook`). |
| `guards[]` | `{verdict, when, instead, reason}`, applied in code after the table *and* after the model (R2: an FO cause never POSTs) |
| `blocked_verdict` | what a POST becomes when a `blocks_post` test failed (ESCALATE) |
| `confirm_verdicts` + `verdict_policy` | P1: a POST while these policies are null is flagged "requires controller confirmation" |
| `comment` | template for a playbook finding |

## 10. Connectors and the gateway

```yaml
# config/agent-one-finance/connectors.yaml
connectors:
  gl:
    name: General ledger
    transport: http                 # or inproc (dev stubs: target: module:builder)
    url: https://gl-mcp.internal.example/mcp
    headers_env: { Authorization: GL_MCP_AUTHORIZATION }   # value from env, never in the file
    classification: internal
    tools:
      balances:     { description: ..., scope: { arg: entity, key: entity } }
      post_journal: { description: ..., scope: { arg: entity, key: entity },
                      access: write, idempotency_arg: idempotency_key }
```

Every call (`gateway.call`) is checked and recorded in order:

1. The tool must be in the allow-list and used by this capability.
2. The scope argument must be inside the caller's entitlements.
3. A write tool is callable only by `publish` after release, never by the model.
4. Pseudonymized values are reversed for the connector.
5. One `aof_tool_call` row is written: allowed or refused, rows, time, error.
6. Masking is applied to what the model, traces and audit copy see.

`scripts/aof_office_smoke.py --user <id>` checks real connectors end to end. Office
services such as RAG, the data explorer and plugins' MCP servers are onboarded the same
way. See `config/agent-one-finance/connectors.office.example.yaml`.

## 11. Knowledge graph and reference data

The graph is bitemporal: every edge has `valid_from` / `valid_to`.

- **Reference files** (`config/agent-one-finance/knowledge/*.yaml`) hold `namespace`, `nodes`
  (`id`, `kind`, `attrs`) and `edges`. For example, PRIME-MB-05 moved desk on 2026-07-01,
  so a COB before that date resolves the old desk.
- **Approved decisions** become priors. They are matched on the same subject first, then
  on shared entities, within `priors_lookback_days`.
- The graph is used by `resolve` and passed to the model as `group.priors`.

## 12. Data protection

`config/agent-one-finance/governance.yaml` holds the protection rules:

| Rule | Effect |
|---|---|
| `mask` | Irreversible `***MASKED***` for the model, traces and audit copies |
| `pseudonymize` | Per-case tokens such as `«COUNTERPARTY:QXKD»`. The model reasons with tokens, the gateway reverses them for connectors, and reviewers see real values. |
| `scrub` | Protected values are also removed from free text: labels, comments, reviewer notes |
| `trace_payloads: masked` | Hides payloads in auto-instrumented spans |

## 13. Settings

Every setting comes from the environment, read once in `agent_one_finance/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `AOF_DATABASE_URL` | `FOBO_DATABASE_URL` or local :5433 | Postgres |
| `AOF_CONFIG_DIR` | `config/agent-one-finance` | configuration folder |
| `AOF_LLM_ADAPTER` | stub | none · stub · agent_sdk · `module:attr` |
| `PHOENIX_COLLECTOR_ENDPOINT` / `AOF_TRACING_SETUP` | — | tracing |
| `AOF_ENTITLEMENT_URL` | — (dev users) | central entitlements |
| `AOF_ENTITLEMENT_TTL_SECONDS` | 60 | entitlement cache |
| `AOF_IDENTITY_HEADER` | X-AOF-User | SSO proxy header |
| `AOF_TRUSTED_PROXY_SECRET` | — | refuse requests not from the proxy |
| `AOF_ENTITLEMENT_WEBHOOK_SECRET` | — | enables entitlement invalidation |
| `AOF_RUN_MODE` | background | background · inline |
| `AOF_SCHEDULER` / `AOF_SCHEDULE_TZ` | on / UTC | schedule loop |
| `AOF_EVENT_SECRET` | — | enables `POST /api/events` |
| `AOF_ADMIN_ROLE` | AOF_PLATFORM_ADMIN | platform support |
| `AOF_ENV_NAME` / `AOF_PROMOTION_KEY` | dev / — | promotion bundles |
| `AOF_NOTIFY_WEBHOOK_URL` / `AOF_CONSOLE_URL` | — | Teams / Power Automate |
| `AOF_DOCUMENTS_DIR` | — | documents service folder |
| `AOF_REPORTS_STORE` / `AOF_REPORTS_DIR` | db / — | where PDF reports go |

## 14. HTTP API

All routes are under `/api` and are identified by the identity header.

| Area | Routes |
|---|---|
| Me / platform | `GET /me`, `GET /platform`, `GET /overview`, `GET /operations`, `GET /inbox`, `GET /audit` |
| Capabilities | `GET /capabilities`, `GET /capabilities/{id}`, `POST /capabilities/{id}/versions`, `POST /capabilities/{id}/versions/{v}/approve`, `GET …/versions/{a}/diff/{b}`, `GET …/versions/{v}/export`, `GET …/flow`, `POST …/instructions`, `POST /cases/{id}/gates/{step}` (pass or stop at a tollgate), `POST /cases/{id}/requests` (ask for evidence), `GET /requests` (questions for me), `POST /requests/{rid}/answer` (an addressee, or a bot with the event secret and `answered_by`), `POST /requests/{rid}/answer-with-file` (multipart: answer, file, answered_by), `POST /requests/{rid}/cancel`, `GET /capabilities/{id}/contract?team_group=` (data needed, parameters to confirm), `GET …/learning` (unexplained items, rule candidates), `GET …/recurring`, `POST …/check` (a manifest or group config, checked without storing: `{ok, problems}`) |
| Groups | `GET /capabilities/{id}/groups`, `GET …/groups/{g}`, `POST …/groups`, `POST …/groups/{g}/versions/{v}/approve`, `GET …/groups/{g}/versions/{a}/diff/{b}` |
| Authoring | `GET /authoring/modes` (which ways are offered), `POST /authoring/guided` (answers → manifest, no model), `POST /authoring/draft` (BRD → manifest; a model, or the nearest template without one), `POST /authoring/submit`, `GET /authoring/drafts`, `GET /authoring/templates`, `POST /promotion/import` |
| Cases | `GET/POST /capabilities/{id}/cases`, `GET /cases/{id}`, `POST /cases/{id}/decisions` (with `checklist` answers when the capability has a sign-off checklist), `POST …/decisions/bulk`, `POST …/groups/{g}/reinvestigate`, `POST …/rerun`, `POST …/publish`, `POST …/publish/retry`, `GET …/documents/{name}` (published, or kept by a `report` step), `POST …/legal-hold`, `POST …/events/{step}` (the event a waiting case continues with: a system with the event secret, or a person with the step's roles) |
| Evidence and chat | `POST /cases/{id}/evidence`, `GET …/evidence/{name}`, `GET …/evidence-pack`, `GET …/messages`, `POST …/ask`, `GET …/history`, `GET …/history/{checkpoint}` |
| Operations | `GET /notifications`, `POST /notifications/read`, `POST /events`, `GET /schedules`, `GET/POST /switches`, `POST /capabilities/{id}/evals`, `GET …/evals`, `GET /evals/{run}`, `POST /entitlements/invalidate` |

To open a case from a script:

```bash
curl -X POST localhost:8300/api/capabilities/fin.accruals-review/cases \
  -H 'X-AOF-User: alice' -H 'Content-Type: application/json' \
  -d '{"case_key": {"entity": "UK01", "period": "2026-09"}}'
```

## 15. Extension points

| To add | Do |
|---|---|
| A use case | A manifest (no code) |
| A team on a shared capability | A group file (no code) |
| A bank system | An MCP server + an entry in `connectors.yaml`; Agent One Finance code is unchanged |
| An LLM connector | `AOF_LLM_ADAPTER=pkg.mod:obj`, an object with `name` and `async reason(request: ReasonRequest, tools)` (see `agent_one_finance/llm.py`) |
| Tracing | `AOF_TRACING_SETUP=pkg.mod:fn`, called once at startup |
| Entitlements | `AOF_ENTITLEMENT_URL` (or an adapter) returning roles and data scopes |
| A template | A YAML file in `config/agent-one-finance/templates/` |
| A new step type | Code: `agent_one_finance/steps.py` + `STEPS` in `workflow.py` (declare needs/produces), with tests; the platform team owns it |

## 16. Testing

```bash
cd apps/backend && .venv/bin/python -m pytest -q          # backend (needs Postgres; test DB fobo_test)
cd apps/backend && .venv/bin/python -m pytest -q tests/agent_one_finance
cd apps/web && npx vitest run && npx tsc --noEmit -p .    # web
cd apps/web && npm run check:styles                         # the console keeps this project's styles (guide/styles.md)
cd apps/console && npx vitest run                         # FOBO console
```

| Test file | Covers |
|---|---|
| `tests/agent_one_finance/test_fobo_playbook.py` | FOBO rules as behaviour: verdicts, R2, P1, blocking tests, Prime vs Rates visibility and ownership |
| `tests/agent_one_finance/test_examples.py` | every example in `docs/agent-one-finance/examples/` validates, allowing only its listed missing connectors |
| `tests/agent_one_finance/test_groups.py` | configurable paths, group ownership, merging |

A new capability should come with a test that opens a case with `AOF_RUN_MODE=inline`
and asserts the groups and findings.

## 17. Deploying in the office

1. Point `connectors.yaml` at the real MCP servers (see `connectors.office.example.yaml`),
   with secrets in the environment.
2. Set `AOF_LLM_ADAPTER=agent_sdk` (Claude Agent SDK), `PHOENIX_COLLECTOR_ENDPOINT`,
   `AOF_ENTITLEMENT_URL`, `AOF_IDENTITY_HEADER` and `AOF_TRUSTED_PROXY_SECRET`.
3. Run `alembic upgrade head`, start the API, and run `scripts/aof_office_smoke.py`.
4. Promote capabilities from UAT using export → import → approve.

See [`../office-platform-and-roadmap.md`](../office-platform-and-roadmap.md) and
[`../README.md`](../README.md#what-runs-where).
