# Helix developer guide and specification

**Date:** 2026-10-04 · For engineers who run, extend and onboard Helix.
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
   │  /api  (identity header from SSO; X-Helix-User in dev)
   ▼
 Helix API  (FastAPI, apps/backend/helix/web/main.py, :8300)
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
| `apps/backend/helix/` | the platform: `manifest.py` (spec), `workflow.py` + `steps.py` (engine), `runner.py`, `cases.py`, `gateway.py`, `llm.py`, `llm_agent_sdk.py`, `governance.py`, `knowledge.py`, `groups.py`, `capabilities.py`, `scheduler.py`, `controls.py`, `notify.py`, `evidence.py`, `evals.py`, `devtools.py`, `config_sync.py`, `retention.py` |
| `apps/backend/helix/web/main.py` | the HTTP API |
| `apps/backend/helix/mcp_services/documents.py` | documents MCP service: read PDF / Excel, build PDF reports |
| `apps/backend/helix/stub_connectors/` | dev stand-ins for GL, budget, bank, ledger, CATS, MOTIF |
| `apps/backend/migrations/` | Alembic migrations (Helix and FOBO share the DB) |
| `apps/backend/tests/helix/` | Helix tests |
| `apps/web/` | the Helix web app |
| `config/helix/capabilities/*.yaml` | live capabilities (seeded / synced) |
| `config/helix/groups/<capability>/*.yaml` | team groups |
| `config/helix/connectors.yaml` | onboarded connectors and their tool allow-list |
| `config/helix/governance.yaml` | data protection rules |
| `config/helix/knowledge/*.yaml` | reference lineage (e.g. `fobo-reference`) |
| `config/helix/templates/*.yaml` | starting points in *Authoring* |
| `config/helix/dev-users.yaml` | dev entitlements stand-in |
| `docs/helix/examples/` | ready-to-install example capabilities |
| `apps/backend/fobo`, `apps/console` | the FOBO app; unchanged and still running |

## 3. Run it locally

```bash
docker compose up -d postgres                       # Postgres 16 on :5433
cd apps/backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn helix.web.main:app --port 8300    # seeds config/helix on first start

cd ../web && npm install && npm run dev             # http://localhost:5180 (proxies /api → :8300)
```

The defaults are `HELIX_LLM_ADAPTER=stub` (deterministic, no model calls), tracing off,
and dev entitlements. Pick a user in the top-right menu. To bring changed config files into
a running database:

```bash
cd apps/backend && .venv/bin/python -m helix.config_sync   # each changed file → a draft
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
owners: { people: [carol], role: HELIX_FIN_VARCOMM_OWNER, four_eyes: true }

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
  opens_as: helix-scheduler

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
- Put it in `config/helix/capabilities/` and run `config_sync`; a second owner approves.
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
# config/helix/groups/recon.investigation/cats-motif-rates.yaml (abridged)
group: cats-motif-rates
name: CATS vs MOTIF — Rates (FOBO)
owners: { people: [rita, raj], role: HELIX_FOBO_RATES_OWNER, four_eyes: true }
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

Source of truth: `apps/backend/helix/manifest.py` (Pydantic; unknown keys are refused).

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
| `steps` | list | required | see §7 |
| `pause_before` | list | `[review]` | the run waits for people before these steps |
| `tollgates` | {step: {roles, check, stop_needs_comment}} | {} | who passes each stop other than review and publish, and what they check (§7a) |
| `group_by` | list | [] (one group) | item fields that form a group |
| `rules` | list[Rule] | [] | settled before the model |
| `reasoning` | ReasoningSpec | | the model |
| `review` | ReviewSpec | required | who decides |
| `publish` | PublishSpec | — | write-back after release |
| `enrich` | list[EnrichSpec] | [] | join more data onto items |
| `playbook` | PlaybookSpec | — | deterministic checks, tests, verdicts (§9) |
| `knowledge` | KnowledgeSpec | | priors and reference lineage |
| `resolve` | list[ResolveSpec] | [] | graph lookups onto items |
| `retention` | {days} | — | how long cases are kept (legal hold overrides) |
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
| `schedule` | — | cron (`min hour dom mon dow`, in `HELIX_SCHEDULE_TZ`) |
| `schedule_keys` | [] | keys to open per tick; templates `{prev_business_day}`, `{prev_month}`, … |
| `events` | false | may `POST /api/events` open cases |
| `opens_as` | — | the service user scheduled or event cases run as |

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
- **How it is recorded.** Each decision is stored in `helix_gate_decision` and shown on the
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
`config/helix/groups/recon.investigation/cats-motif.yaml` and
[`../fobo-on-helix.md`](../fobo-on-helix.md).

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
# config/helix/connectors.yaml
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
5. One `helix_tool_call` row is written: allowed or refused, rows, time, error.
6. Masking is applied to what the model, traces and audit copy see.

`scripts/helix_office_smoke.py --user <id>` checks real connectors end to end. Office
services such as RAG, the data explorer and plugins' MCP servers are onboarded the same
way. See `config/helix/connectors.office.example.yaml`.

## 11. Knowledge graph and reference data

The graph is bitemporal: every edge has `valid_from` / `valid_to`.

- **Reference files** (`config/helix/knowledge/*.yaml`) hold `namespace`, `nodes`
  (`id`, `kind`, `attrs`) and `edges`. For example, PRIME-MB-05 moved desk on 2026-07-01,
  so a COB before that date resolves the old desk.
- **Approved decisions** become priors. They are matched on the same subject first, then
  on shared entities, within `priors_lookback_days`.
- The graph is used by `resolve` and passed to the model as `group.priors`.

## 12. Data protection

`config/helix/governance.yaml` holds the protection rules:

| Rule | Effect |
|---|---|
| `mask` | Irreversible `***MASKED***` for the model, traces and audit copies |
| `pseudonymize` | Per-case tokens such as `«COUNTERPARTY:QXKD»`. The model reasons with tokens, the gateway reverses them for connectors, and reviewers see real values. |
| `scrub` | Protected values are also removed from free text: labels, comments, reviewer notes |
| `trace_payloads: masked` | Hides payloads in auto-instrumented spans |

## 13. Settings

Every setting comes from the environment, read once in `helix/config.py`.

| Variable | Default | Purpose |
|---|---|---|
| `HELIX_DATABASE_URL` | `FOBO_DATABASE_URL` or local :5433 | Postgres |
| `HELIX_CONFIG_DIR` | `config/helix` | configuration folder |
| `HELIX_LLM_ADAPTER` | stub | none · stub · agent_sdk · `module:attr` |
| `PHOENIX_COLLECTOR_ENDPOINT` / `HELIX_TRACING_SETUP` | — | tracing |
| `HELIX_ENTITLEMENT_URL` | — (dev users) | central entitlements |
| `HELIX_ENTITLEMENT_TTL_SECONDS` | 60 | entitlement cache |
| `HELIX_IDENTITY_HEADER` | X-Helix-User | SSO proxy header |
| `HELIX_TRUSTED_PROXY_SECRET` | — | refuse requests not from the proxy |
| `HELIX_ENTITLEMENT_WEBHOOK_SECRET` | — | enables entitlement invalidation |
| `HELIX_RUN_MODE` | background | background · inline |
| `HELIX_SCHEDULER` / `HELIX_SCHEDULE_TZ` | on / UTC | schedule loop |
| `HELIX_EVENT_SECRET` | — | enables `POST /api/events` |
| `HELIX_ADMIN_ROLE` | HELIX_PLATFORM_ADMIN | platform support |
| `HELIX_ENV_NAME` / `HELIX_PROMOTION_KEY` | dev / — | promotion bundles |
| `HELIX_NOTIFY_WEBHOOK_URL` / `HELIX_CONSOLE_URL` | — | Teams / Power Automate |
| `HELIX_DOCUMENTS_DIR` | — | documents service folder |
| `HELIX_REPORTS_STORE` / `HELIX_REPORTS_DIR` | db / — | where PDF reports go |

## 14. HTTP API

All routes are under `/api` and are identified by the identity header.

| Area | Routes |
|---|---|
| Me / platform | `GET /me`, `GET /platform`, `GET /overview`, `GET /operations`, `GET /inbox`, `GET /audit` |
| Capabilities | `GET /capabilities`, `GET /capabilities/{id}`, `POST /capabilities/{id}/versions`, `POST /capabilities/{id}/versions/{v}/approve`, `GET …/versions/{a}/diff/{b}`, `GET …/versions/{v}/export`, `GET …/flow`, `POST …/instructions`, `POST /cases/{id}/gates/{step}` (pass or stop at a tollgate), `POST …/check` (a manifest or group config, checked without storing: `{ok, problems}`) |
| Groups | `GET /capabilities/{id}/groups`, `GET …/groups/{g}`, `POST …/groups`, `POST …/groups/{g}/versions/{v}/approve`, `GET …/groups/{g}/versions/{a}/diff/{b}` |
| Authoring | `POST /authoring/draft` (BRD → manifest), `POST /authoring/submit`, `GET /authoring/drafts`, `GET /authoring/templates`, `POST /promotion/import` |
| Cases | `GET/POST /capabilities/{id}/cases`, `GET /cases/{id}`, `POST /cases/{id}/decisions`, `POST …/decisions/bulk`, `POST …/groups/{g}/reinvestigate`, `POST …/rerun`, `POST …/publish`, `POST …/publish/retry`, `GET …/documents/{name}`, `POST …/legal-hold` |
| Evidence and chat | `POST /cases/{id}/evidence`, `GET …/evidence/{name}`, `GET …/evidence-pack`, `GET …/messages`, `POST …/ask`, `GET …/history`, `GET …/history/{checkpoint}` |
| Operations | `GET /notifications`, `POST /notifications/read`, `POST /events`, `GET /schedules`, `GET/POST /switches`, `POST /capabilities/{id}/evals`, `GET …/evals`, `GET /evals/{run}`, `POST /entitlements/invalidate` |

To open a case from a script:

```bash
curl -X POST localhost:8300/api/capabilities/fin.accruals-review/cases \
  -H 'X-Helix-User: alice' -H 'Content-Type: application/json' \
  -d '{"case_key": {"entity": "UK01", "period": "2026-09"}}'
```

## 15. Extension points

| To add | Do |
|---|---|
| A use case | A manifest (no code) |
| A team on a shared capability | A group file (no code) |
| A bank system | An MCP server + an entry in `connectors.yaml`; Helix code is unchanged |
| An LLM connector | `HELIX_LLM_ADAPTER=pkg.mod:obj`, an object with `name` and `async reason(request: ReasonRequest, tools)` (see `helix/llm.py`) |
| Tracing | `HELIX_TRACING_SETUP=pkg.mod:fn`, called once at startup |
| Entitlements | `HELIX_ENTITLEMENT_URL` (or an adapter) returning roles and data scopes |
| A template | A YAML file in `config/helix/templates/` |
| A new step type | Code: `helix/steps.py` + `STEPS` in `workflow.py` (declare needs/produces), with tests; the platform team owns it |

## 16. Testing

```bash
cd apps/backend && .venv/bin/python -m pytest -q          # backend (needs Postgres; test DB fobo_test)
cd apps/backend && .venv/bin/python -m pytest -q tests/helix
cd apps/web && npx vitest run && npx tsc --noEmit -p .    # web
cd apps/console && npx vitest run                         # FOBO console
```

| Test file | Covers |
|---|---|
| `tests/helix/test_fobo_playbook.py` | FOBO rules as behaviour: verdicts, R2, P1, blocking tests, Prime vs Rates visibility and ownership |
| `tests/helix/test_examples.py` | every example in `docs/helix/examples/` validates, allowing only its listed missing connectors |
| `tests/helix/test_groups.py` | configurable paths, group ownership, merging |

A new capability should come with a test that opens a case with `HELIX_RUN_MODE=inline`
and asserts the groups and findings.

## 17. Deploying in the office

1. Point `connectors.yaml` at the real MCP servers (see `connectors.office.example.yaml`),
   with secrets in the environment.
2. Set `HELIX_LLM_ADAPTER=agent_sdk` (Claude Agent SDK), `PHOENIX_COLLECTOR_ENDPOINT`,
   `HELIX_ENTITLEMENT_URL`, `HELIX_IDENTITY_HEADER` and `HELIX_TRUSTED_PROXY_SECRET`.
3. Run `alembic upgrade head`, start the API, and run `scripts/helix_office_smoke.py`.
4. Promote capabilities from UAT using export → import → approve.

See [`../office-platform-and-roadmap.md`](../office-platform-and-roadmap.md) and
[`../README.md`](../README.md#what-runs-where).
