# Helix Capability Platform — Design

**Date:** 2026-10-03 · **Revision:** 2 (team answers folded in) · **Status:** draft for team review · **Skeleton:** built — see [`docs/helix/README.md`](../../helix/README.md) · **Branch:** `claude/exciting-darwin-7xukjj`

## 1. Purpose

Turn the FOBO Investigation Console into **Helix**: one application that
accounting groups onboard their own AI-assisted work into — reconciliations,
variance commentary, sign-off packs, exception reviews — without building a
new app each time.

**The operating model:** the Helix team onboards **MCP connectors** (the
bank's data sources, as tools). Everything else a new capability needs —
its workflow, rules, agent instructions, review policy and screens — is
configuration that its owners set up in Helix, and it works without Helix
writing code for it.

FOBO (CATS vs MOTIF) stops being *the* application and becomes the **first
capability** on the platform. It is the one capability allowed to keep
bespoke code, because it predates the platform; it keeps working throughout,
and its test suite proves the extraction changed nothing.

### Decisions (2026-10-03)

| Question | Decision |
|---|---|
| What happens to FOBO | Kept, as the first capability (legacy pack with its own code) |
| What the Helix team builds per new capability | **Only MCP connectors.** Workflow, rules, prompts, review, UI are configuration |
| How a capability is defined | A manifest, edited in the console, built from the core step library and the onboarded connectors' tools. Pack code is a Helix-team escape hatch, not the onboarding path |
| What proves the platform is generic | A second capability onboarded with **zero code**: one connector plus configuration |
| Database | **One shared database**; every row carries `capability_id` |
| Who approves a capability and its changes | The capability's **owners** — several named people, plus a bank role — with four-eyes (drafter ≠ approver) |
| Where roles and data access come from | The bank's **central entitlements system**, at data level, called by Helix through a configured entitlement URL |
| What the unit of work is called | Core term **case**; each capability sets its own UI label (FOBO: "Rec run"; others may use "lane", "review", …) — §3 |
| Name | **Helix** (package `helix`, UI title "Helix") |
| Observability | **Arize Phoenix**, self-hosted, via OpenTelemetry/OpenInference; one trace per case, one Phoenix project per capability. Postgres stays the audit system of record. Walkthrough: [`2026-10-03-helix-how-a-use-case-works.md`](2026-10-03-helix-how-a-use-case-works.md) |

Out of scope: choosing the second real business capability; building
specific bank connectors (each is its own small onboarding, §6.4).

## 2. What is already generic, and what is FOBO

The engine is closer to a platform than its names suggest. The work is
mostly *separating* code, not rewriting it.

| Part | Today | Verdict |
|---|---|---|
| Workflow versions, drafts, diff, four-eyes approval (`investigation/versions.py`, `workflow_version`) | One global workflow | **Generic** — needs a `capability_id` |
| Step registry with `needs`/`produces` validation (`investigation/step_registry.py`) | One flat dict of FOBO steps | **Generic mechanism**, FOBO content |
| Graph builder, pause/resume, checkpoint pinning (`investigation/graph.py`) | Builds the one workflow | **Generic** |
| Reasoning port: start/poll, adapters `none` / `session_service` / `direct` (`reasoning/port.py`, `adapters/`) | Request/response shaped as `RecVerdict` | **Generic transport**, FOBO payload |
| Verdict guards R2/R6/P1 (`reasoning/guards.py`) | FOBO rules | **FOBO** (the *idea* of guards is core) |
| MCP server, per-session bearer token, audit row per call (`mcp_server/`) | Eight `fobo_*` tools served locally | **Generic server**, FOBO tools; becomes the connector gateway (§6) |
| Grounding: every retrieval is a `source_call` row (`grounding/`) | — | **Generic** |
| Human review pause, idempotent decisions (`web/decisions.py`) | Decisions per pattern group of breaks | **Generic idea**, FOBO shape |
| Chat over the session (`console_views/chat.py`) | Deterministic intent router over breaks | **Generic shell**, FOBO intents |
| Knowledge graph, bitemporal `as_of`, entitlement (`knowledge_graph/`) | Books, desks, lineage; entity scope on the `Caller` | **Generic store**, FOBO ontology; entitlement moves to the central service (§7) |
| Cause checks C1–C6, playbook (FO/BO tests), book resolution | — | **FOBO** |
| `reconciliation`, `run`, `break_event`, `pattern_group` tables | — | **FOBO** |
| `InvestigationState` keys (`master_book`, `breaks`, `deltas`…) | — | **FOBO** |
| Console: board, rec nav, adjustments panel, book drawers | — | **FOBO**; the shell, session panel, workflow tab, MCP inspector are generic |

## 3. Concepts

```
Helix (platform)
 ├─ Connector ─── an onboarded MCP server: a bank system's data as tools      ← Helix team
 │
 ├─ Capability ── "what kind of work"                                          ← capability owners
 │    ├─ Manifest      subjects, items, steps, rules, agent skill, review, views
 │    ├─ Tools         chosen from the onboarded connectors
 │    ├─ Workflow      versioned, four-eyes approved by the owners
 │    └─ Owners        named people + a bank role; approve every change
 │
 └─ Case ──────── "one unit of that work"   e.g. Prime rec run on 03-Aug
      ├─ Items         what the case is about (breaks, variances, lines…)
      ├─ Run           one LangGraph thread, pinned to a workflow version
      ├─ Evidence      source_call rows: every connector tool call
      ├─ Proposals     what the run suggests, grouped
      ├─ Conversation  chat with the case's agent session
      └─ Decisions     human sign-off; feeds the next run's priors
```

| Platform term | FOBO today | Variance-commentary example |
|---|---|---|
| Capability | the FOBO console | P&L variance commentary |
| Case (UI label set per capability) | investigation session — "Rec run" | "Lane": entity × month-end |
| Item | break | account-line variance |
| Proposal group | pattern group | variance driver |
| Proposal | drafted adjustment / verdict | drafted commentary line |
| Decision | controller decision | preparer/reviewer sign-off |
| Subject | rec, master book | entity, cost centre |

**Why "case" in code.** The team floated case, train and lane. The code
keeps one neutral term so core APIs and tables never need renaming; the UI
word is `case.label` in each manifest, so a capability can show "Lane" or
"Train" with no code change. If the team prefers *lane* platform-wide, it is
a find-and-replace before Phase 0, not after.

## 4. The capability manifest

Each capability is one manifest, stored versioned in the database (edited in
the console's capability builder, downloadable/uploadable as YAML — the
same pattern as the Workflow tab today). It is validated on save: a
reference to an unknown step, connector tool, role or view is refused, not
discovered mid-run.

A **zero-code** capability — the shape every new one takes:

```yaml
id: pc.variance-commentary
name: P&L variance commentary
owners:
  people: [jdoe, asmith, rkumar]       # approve manifest + workflow changes
  role: HELIX_PC_VARCOMM_OWNER          # bank role from central entitlements
  four_eyes: true                       # drafter cannot approve own change

case:
  label: Lane                           # what the UI calls a case
  item_label: Variance
  key: [entity, period]                 # what makes a case unique
  opens_on: schedule                    # event | schedule | manual | api
  schedule: "0 6 2 * *"                 # 06:00 on the 2nd, for month-end

items:
  load: { tool: gl.variances, args: { entity: $case.entity, period: $case.period } }
  id_field: line_id
  amount_field: variance
  display: [account, cost_centre, actual, budget, variance]   # generic table columns
  in_scope: "abs(variance) >= policy.materiality"

policy:
  materiality: { value: 50000, unit: GBP }

steps: [load, group, reason, draft, validate, review, record]   # core library only
group_by: [account]                                             # generic grouping key

reasoning:
  reasoner: session_service
  skill: |                                                      # the agent's instructions
    Explain each material variance using the GL and budget tools.
    Cite every figure from a tool result. Do not estimate.
  tools: [gl.variances, gl.journal_lines, budget.plan_lines]    # from onboarded connectors
  output: commentary                                            # verdict | commentary | classification

review:
  approve_by: [proposal_group, item]
  roles: [PC_PREPARER, PC_REVIEWER]     # who can decide, from central entitlements
  four_eyes: true

views:
  detail: [core.session, core.items_table, core.proposals]
```

FOBO's manifest has the same shape, plus `pack: fobo` naming its legacy
steps (resolve, gather, rank), guards and panels.

## 5. Generic steps — what makes zero-code possible

New capabilities can only use core steps, so the core library must cover the
common shapes of accounting control work. Every step is driven by manifest
fields, never by capability-specific code.

| Step | Does | Configured by |
|---|---|---|
| `load` | Load the case's items through a connector tool; apply `in_scope` | `items.load`, `items.in_scope` |
| `match` | Two-sided match on keys with tolerance → matched / breaks (generic recon) | `match.left`, `match.right`, `match.keys`, `match.tolerance` |
| `compare` | Period-over-period / actual-vs-plan deltas (variance) | `compare.measures`, `compare.baseline` |
| `group` | Collapse items into proposal groups (key fields, or agent-suggested patterns) | `group_by` |
| `enrich` | Call listed tools per group and attach results as evidence | `enrich.tools` |
| `reason` | Settle by rule; send the rest to the agent with the skill and allowed tools; guards applied by code | `rules`, `reasoning.*` |
| `draft` | Write the summary/commentary from findings (template or agent) | `reasoning.output` |
| `validate` | **Core gate.** Every figure in a draft must trace to a recorded tool result | — |
| `review` | **Core gate.** Pause for people with `review.roles` | `review.*` |
| `record` | **Core gate.** Write decisions; publish them as priors; optional write-back tool | `record.publish_tool` |

- The existing `needs`/`produces` validation stays, so a manifest that lists
  `reason` before `load` is refused with a readable message.
- Steps write core state keys only (`items`, `proposal_groups`, `findings`,
  `draft`, `decisions`, …). FOBO's legacy steps write under `pack.*`.
- **Rules without code.** `rules` is a list of `when` (expression over item
  fields, policy values and tool results) → `then` (verdict, escalate, or ask
  the agent). FOBO's playbook keeps its own loader; new capabilities use this.

## 6. Connectors and the MCP gateway

The Helix team's whole per-capability job.

### 6.1 What a connector is

A registered external MCP server — a bank system exposed as tools.

| Field | Meaning |
|---|---|
| `connector_id` | e.g. `gl`, `budget`, `cats`, `motif` |
| `url`, `transport` | streamable HTTP MCP endpoint |
| `auth` | how Helix authenticates to it (service credential from the vault; never in the manifest) |
| `tools` | discovered via MCP `tools/list`, then **allow-listed** by the Helix team |
| `data_scope_param` | which argument carries the user's data scope (entity, book…), so entitlement can be enforced (§7) |
| `classification` | data classification, shown to owners when they pick tools |
| `owner`, `status` | Helix team; `draft` → `active` (four-eyes, Helix team) |

### 6.2 The gateway

Helix's MCP server (today `fobo/mcp_server/`) becomes the **gateway**. Agent
sessions and core steps never call a connector directly:

```
agent session ──(per-session token)──▶ Helix MCP gateway ──▶ connector (bank MCP server)
core step (load/enrich) ─────────────▶        │
                                               ├─ tool allowed for this capability?
                                               ├─ caller entitled to this data scope? (§7)
                                               ├─ inject / clamp the data-scope argument
                                               ├─ call, with timeout + retry
                                               └─ source_call row (audit + grounding)
```

- The per-session bearer token, the audit row per call and the
  application-name labelling already exist; they move from FOBO's local tools
  to proxied connector tools.
- `validate` traces figures to `source_call` rows, so grounding works for any
  connector with no extra code.

### 6.3 Core tools

Served by Helix itself for every capability: `core.case_items`,
`core.item_detail`, `core.similar_decisions` (priors from past decisions),
`core.policy`. FOBO's eight tools become `fobo.*` in its pack.

### 6.4 Onboarding a connector (Helix team)

1. Register URL + auth reference; Helix runs `tools/list`.
2. Allow-list tools; map each tool's data-scope argument.
3. Contract test: Helix calls each tool with a sample scope and checks the
   result against its declared schema.
4. Second Helix team member approves → `active`; its tools appear in the
   capability builder's tool picker.

## 7. Entitlement — central, data-level

Helix holds no roles of its own. It calls the bank's central entitlements
system through a configured URL.

```
GET {HELIX_ENTITLEMENT_URL}/users/{staff_id}/entitlements?app=helix
→ {
    "roles": ["PC_PREPARER", "HELIX_PC_VARCOMM_OWNER"],
    "data_scopes": { "entity": ["UK01", "US02"], "book": ["PRIME-*"] }
  }
```

- **Who can do what** — `roles` gate seeing a capability, deciding in review
  (`review.roles`), and owning it (`owners.role`).
- **Which data** — `data_scopes` filter which cases a user sees and are
  enforced by the gateway on every connector call (§6.2). This replaces the
  `entity_scope` on today's `Caller` with the same semantics: a caller
  outside scope cannot tell a hidden record from a missing one (the existing
  test for this becomes a gateway test).
- Responses are cached per user for a short TTL (config, default 5 min);
  the service being down fails closed.
- `FOBO_ENV=dev`'s "Act as" switch becomes a dev-only stub entitlement
  service with fixture users, so local runs need no bank connectivity.
- The response shape above is a proposal; an adapter maps the bank's real
  API onto it (open question 1).

## 8. Approval and governance

| Change | Drafted by | Approved by |
|---|---|---|
| New connector, connector tool allow-list | Helix team | another Helix team member |
| New capability, manifest change | a capability owner | another owner (`owners.people` or `owners.role`), never the drafter |
| Workflow change for a capability | a capability owner | another owner — today's Workflow tab rule, scoped per capability |
| Review decision on a case | — | a user with `review.roles`; four-eyes if the manifest says so |

Every approval is a versioned row with drafter, approver, timestamps and
reason — the `workflow_version` pattern, extended to `capability_version`
and `connector_version`.

## 9. Data model

Additive first. FOBO tables stay; they become the FOBO pack's tables.

| Table | Change |
|---|---|
| `connector`, `connector_version` (new) | §6.1 fields; versioned, four-eyes |
| `capability`, `capability_version` (new) | `capability_id`, `owners`, `manifest` (JSONB), status, drafter/approver |
| `workflow_version` | add `capability_id`; one active version **per capability** (the partial unique index gains the column) |
| `investigation_session` → `case_run` | add `capability_id`, `case_key` (JSONB), `subject`. FOBO's `reconciliation_id`/`master_book` move into `case_key`; a view keeps the old name for one release |
| `case_item` (new) | `case_id`, `item_id`, `payload` JSONB — where `load` puts items for zero-code capabilities. FOBO keeps `break_event` |
| `pattern_group` → `proposal_group` | rename + `capability_id`; columns already generic |
| `controller_decision` → `decision` | `break_ids` → `item_ids` |
| `source_call`, `session_message`, `agent_session`, `analysis_version`, `evidence_item` | add `capability_id`; `source_call` gains `connector_id` |
| `node`/`edge` knowledge graph | add `namespace`; bitemporal reads unchanged |
| `reconciliation`, `run`, `break_event`, `break_embedding` | unchanged; FOBO pack |

All in one shared database. Queries are scoped by `capability_id` and the
caller's `data_scopes`.

**Checkpoint compatibility.** LangGraph checkpoints store module paths. The
existing `sys.modules` alias pattern (`fobo/contracts/models.py`) is reused
for `fobo.*` → `helix.*` so open FOBO runs still resume; a test resumes a
checkpoint written before the move.

## 10. Orchestration

```
             ┌────────────────────── Helix core ───────────────────────┐
event ─────▶ │ open case ─▶ capability ─▶ pin workflow ─▶ entitlement   │ ─▶ LangGraph run
schedule     │                 version         version       check     │     core steps (+ FOBO legacy)
manual / api └─────────────────────────────────────────────────────────┘     gates: validate, review, record
                                                                                   │
            connectors ◀── MCP gateway ◀── agent session (skill + allowed tools) ◀─┤
                                                                                   │
                                                       review by entitled people ──┤
                                                                                   ▼
                                                               decisions ─▶ priors / write-back
```

- `build_graph(capability, version)` replaces the single global build; same
  code path, step table = core (∪ FOBO legacy for FOBO).
- Cases open on an event (FOBO's Ready event), a schedule, a manual start in
  the console, or an API call — `case.opens_on`.

## 11. Console

- **Capability switcher** — shows capabilities the user's roles allow.
- **Generic case list and case detail**, driven by the manifest:
  `items.display` columns, proposal groups with approve/reject, the agent
  session panel, evidence (MCP inspector), run trace. A zero-code capability
  gets a complete UI from this.
- **Capability builder** — edit the manifest as a form (and as YAML): pick
  connector tools, order steps, set rules and policy, write the agent skill,
  set review roles and owners; validate; submit for owner approval; diff
  against the active version. Built on the Workflow tab's existing draft →
  approve → diff machinery.
- **Connector admin** (Helix team only) — register, allow-list, contract
  test, approve.
- FOBO's event board, adjustments panel and book drawer stay as FOBO views.

## 12. Package layout

```
apps/backend/helix/
  core/
    workflow/      versions, settings, graph, step registry, gates
    steps/         load, match, compare, group, enrich, reason, draft, validate, review, record
    rules/         when/then rule engine for zero-code capabilities
    reasoning/     port, adapters, request/response contracts
    gateway/       MCP gateway: connector registry, client, proxy, core tools, audit
    entitlement/   central-service client, cache, dev stub
    capabilities/  manifest schema, validator, versions, builder API
    cases/         open/resume/read a case; decisions; chat router
    grounding/     source_call recorder
    knowledge/     graph store, bitemporal reads
    db/  web/
  packs/fobo/      legacy: resolve/gather/rank steps, cause checks, playbook,
                   guards, fobo.* tools, seed data, its tables
apps/console/src/
  core/            shell, capability switcher, case list/detail, session panel,
                   capability builder, connector admin, workflow tab, MCP inspector
  packs/fobo/      event board, adjustments panel, book drawer
```

An import-lint test fails the build if anything under `helix.core` imports
`helix.packs`.

## 13. API

| New | Replaces |
|---|---|
| `GET /api/capabilities` (filtered by entitlement) | — |
| `GET/POST /api/capabilities/{cap}/versions`, `…/approve`, `…/reject` | — |
| `GET/POST /api/connectors`, `…/{id}/tools`, `…/approve` | — |
| `GET /api/capabilities/{cap}/cases`, `POST` (manual open) | `GET /api/board` (kept as an alias for FOBO for one release) |
| `POST /api/cases/{case_id}/messages`, `…/decisions` | `/api/recs/{rec_id}/messages`, `…/decisions` |
| `GET /api/cases/{case_id}/trace` | `/api/recs/{rec_id}/trace` |
| `/api/capabilities/{cap}/workflow/*` | `/api/workflow/*` |
| `POST /mcp` (gateway) | `POST /mcp` (FOBO tools) |

## 14. Delivery phases

Each phase ships on its own, with the full suite green and **no FOBO
behaviour change** (same board, same figures, same decisions).

| # | Phase | Outcome |
|---|---|---|
| 0 | **Rename + split** — `fobo` → `helix.core` + `helix.packs.fobo`; console `core/` + `packs/fobo/`; checkpoint alias; docs | Pure moves; the full backend (475) and console suites pass unchanged |
| 1a | **Phoenix observability** — OpenTelemetry + OpenInference (LangGraph, Anthropic), custom spans for gateway/rules/guards/review, `helix.*` attributes, trace id on the case, Phoenix in docker-compose and the web-session hook | FOBO runs visible as traces before the refactor goes further; export failure never fails a run |
| 1 | **Capabilities + owners** — manifest schema and validator, `capability_version` with owner four-eyes, per-capability workflow versions, FOBO manifest | `/api/capabilities` lists FOBO; Workflow tab is per capability |
| 2 | **Central entitlement** — client for `HELIX_ENTITLEMENT_URL`, cache, fail-closed, dev stub replacing "Act as"; data scopes on case visibility | Roles and data access come from outside Helix |
| 3 | **MCP gateway + connectors** — connector registry and approval, proxying with scope enforcement and audit, core tools; FOBO tools re-hosted as `fobo.*` | A stub bank MCP server onboarded as a connector in tests |
| 4 | **Generic case model + core steps** — `case_run`, `case_item`, `proposal_group`, `decision`; `load`, `match`, `compare`, `group`, `enrich`, rule engine | A capability runs end to end from a manifest in tests |
| 5 | **Generic console + capability builder** — switcher, manifest-driven case views, builder, connector admin | **The proof:** a sample capability onboarded with one stub connector and zero code, through the UI |
| 6 | **Second real capability** — one bank connector + configuration, chosen with the team | — |

Phase 0 is mechanical and large; phases 1–5 are each roughly the size of the
MCP/agent-session change.

## 15. Open questions

1. **Entitlement API shape.** The real request/response of the central
   entitlements system (the §7 shape is a placeholder for an adapter), and
   whether it also returns data scopes or those come from a second call.
2. **Write-back.** May a capability write to a bank system after sign-off
   (FOBO's "post to MOTIF via FAS")? If so, write tools need their own
   connector approval tier and four-eyes per decision.
3. **Agent harness per capability.** One session-service deployment for all
   capabilities with the skill sent per session, or a deployed skill per
   capability (today FOBO sends only a skill id)?
4. **Case label.** Confirm "case" as the code term (§3).

## 16. Risks

| Risk | Mitigation |
|---|---|
| Big-bang rename breaks open FOBO runs | Checkpoint module alias + a resume-old-checkpoint test (pattern already in the repo) |
| Core steps not expressive enough, so "zero code" quietly needs code | The sample capability (Phase 5) and the second real one (Phase 6) are the acceptance tests; gaps become new core steps, never per-capability code |
| A capability's agent sees data its users cannot | Scope enforced at the gateway on every call, from the case's caller, not trusted from the agent |
| Entitlement service outage | Fail closed; short cache; clear "entitlements unavailable" state in the UI |
| Core quietly depending on FOBO | Import-lint test: nothing under `helix.core` imports `helix.packs` |
| Two APIs during migration | Aliases live one release, then are removed |
