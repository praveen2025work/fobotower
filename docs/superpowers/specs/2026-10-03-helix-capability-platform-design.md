# Helix Capability Platform — Design

**Date:** 2026-10-03 · **Status:** draft for team review · **Branch:** `claude/exciting-darwin-7xukjj`

## 1. Purpose

Turn the FOBO Investigation Console into **Helix**: one application that
accounting groups onboard their own AI-assisted work into — reconciliations,
variance commentary, sign-off packs, exception reviews — without building a
new app each time.

FOBO (CATS vs MOTIF) stops being *the* application and becomes the **first
capability pack** on the platform. It keeps working throughout, and its test
suite is the safety net that proves the extraction changed nothing.

Decisions already taken (2026-10-03):

| Question | Decision |
|---|---|
| What happens to FOBO | Kept, as the first capability pack |
| How a capability is onboarded | **Config-first + plugins**: a manifest, steps picked from a shared library; Python steps / console panels only where config cannot express it |
| What proves the platform is generic | The onboarding and orchestration mechanism itself, shown by a second, minimal pack built only from core parts — not a second business domain yet |
| Name | **Helix** (package `helix`, UI title "Helix") |

Out of scope here: choosing the second real business capability, bank
integrations, a no-code builder UI (it becomes possible once the manifest
exists — §12).

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
| MCP server, per-session bearer token, audit row per call (`mcp_server/`) | Eight `fobo_*` tools | **Generic server**, FOBO tools |
| Grounding: every retrieval is a `source_call` row (`grounding/`) | — | **Generic** |
| Human review pause, idempotent decisions (`web/decisions.py`) | Decisions per pattern group of breaks | **Generic idea**, FOBO shape |
| Chat over the session (`console_views/chat.py`) | Deterministic intent router over breaks | **Generic shell**, FOBO intents |
| Knowledge graph, bitemporal `as_of`, entitlement (`knowledge_graph/`) | Books, desks, lineage | **Generic store**, FOBO ontology |
| Cause checks C1–C6, playbook (FO/BO tests), book resolution | — | **FOBO** |
| `reconciliation`, `run`, `break_event`, `pattern_group` tables | — | **FOBO** |
| `InvestigationState` keys (`master_book`, `breaks`, `deltas`…) | — | **FOBO** |
| Console: board, rec nav, adjustments panel, book drawers | — | **FOBO**; the shell, session panel, workflow tab, MCP inspector are generic |

## 3. Concepts

```
Helix (platform)
 ├─ Capability ── "what kind of work"         e.g. fobo.cats-vs-motif, sample.review
 │    ├─ Manifest      config: subjects, steps, rules, tools, review, views
 │    ├─ Workflow      versioned, four-eyes approved, per capability
 │    ├─ Rules         the pack's playbook (was config/playbook/)
 │    └─ Pack code     optional: extra steps, tools, guards, console panels
 │
 └─ Case ── "one unit of that work"           e.g. Prime rec run on 03-Aug
      ├─ Items         what the case is about (breaks, variances, lines…)
      ├─ Run           one LangGraph thread, pinned to a workflow version
      ├─ Evidence      source_call rows: every retrieval, tool call
      ├─ Proposals     what the run suggests, grouped (pattern groups today)
      ├─ Conversation  chat with the case's session
      └─ Decisions     human sign-off; feeds tomorrow's priors
```

| Platform term | FOBO term today | Variance-commentary example |
|---|---|---|
| Capability | the FOBO console | P&L variance commentary |
| Case | investigation session (rec × L4 × business date) | entity × month-end |
| Item | break | account-line variance |
| Proposal group | pattern group | variance driver |
| Proposal | drafted adjustment / verdict | drafted commentary line |
| Decision | controller decision | preparer/reviewer sign-off |
| Subject | rec, master book | entity, cost centre |

## 4. The capability manifest

Each pack ships one `capability.yaml`. It is validated at load — like the
playbook and workflow validators today, a reference to an unknown step, tool
or rule fails the load, not a run.

```yaml
# packs/fobo/capability.yaml
id: fobo.cats-vs-motif
name: CATS vs MOTIF investigation
owner: Product Control
version: "1.0"

case:
  label: Rec run                    # what the UI calls a case
  item_label: Break
  key: [rec_id, l4, business_date]  # what makes a case unique
  opens_on: ready_event             # ready_event | schedule | manual | api

items:
  source: pack                      # pack | core_table | mcp_tool
  schema: fobo.break                # JSON schema id, for the generic views

workflow: workflow.yaml             # the existing format, unchanged
rules: playbook.yaml                # pack-owned; validated by the pack's loader

steps:                              # core library + this pack's own steps
  core: [group, reason, draft, validate, review, record]
  pack: [resolve, gather, rank]     # fobo/steps/*.py, registered by the pack

reasoning:
  default: none                     # none | session_service | direct
  skill: skills/fobo-investigation/SKILL.md
  guards: [fobo.r2, fobo.r6, fobo.p1]

tools:                              # exposed to the agent over MCP
  - fobo.list_tests
  - fobo.book_context
  - fobo.similar_breaks
  - core.case_items                 # generic: list/inspect the case's items

review:
  approve_by: [proposal_group, item]
  four_eyes: false
  roles: [FO, PC]

views:                              # console panels, from the core set or the pack
  detail: [core.session, fobo.adjustments]
  drawers: [fobo.book, core.mcp_inspector, core.trace]
```

The **minimal sample pack** (§11, phase 4) uses only `core.*` entries — that
is the proof the platform is generic.

## 5. Core contracts

### 5.1 Pack interface (Python)

```python
class CapabilityPack(Protocol):
    id: str                                   # matches capability.yaml
    manifest_path: Path

    def steps(self) -> list[Step]: ...        # pack steps, same Step dataclass as today
    def tools(self) -> list[McpTool]: ...     # namespaced "<pack>.<tool>"
    def guards(self) -> list[Guard]: ...
    async def load_items(self, session, case: CaseRef) -> list[Item]: ...
    async def seed(self, session) -> None: ...  # demo / reference data, optional
```

Packs register through a Python entry point (`helix.packs`), so a new pack can
live in its own package or repo and be installed alongside Helix.

### 5.2 Steps

The `Step` dataclass and `needs`/`produces` validation stay as they are.
Two changes:

- **Namespacing.** State keys a pack produces live under `pack.<key>`; core
  keys (`case_id`, `items`, `proposal_groups`, `findings`, `draft`,
  `decisions`, `outcome`, `evidence_gaps`…) are shared. The validator then
  catches a core step that silently depends on a FOBO key.
- **Core gates every workflow must contain**, whatever the manifest says:
  `review` (no decision without a person), `validate` (no ungrounded figure),
  `record` after `review`. These are today's `required_because` rules,
  promoted from FOBO policy to platform invariants. A pack can add required
  steps; it cannot remove core ones.

### 5.3 Case state

```python
class CaseState(TypedDict, total=False):
    case_id: str; capability_id: str; business_date: date
    caller: Caller; workflow_version: int
    items: list[dict]
    proposal_groups: list[ProposalGroup]   # was PatternGroup
    findings: dict[str, dict]
    draft: AnalysisDraft | None
    validation_errors: list[str]; evidence_gaps: list[str]
    decisions: list[dict]; outcome: str | None; escalation_reason: str | None
    pack: dict[str, Any]                   # pack-owned keys
```

### 5.4 Reasoning, tools, chat

- **Reasoning port** — unchanged transport. The request gains
  `capability_id` and a pack-supplied payload. The response contract becomes
  "a verdict per item or per group" with the pack's guards applied by graph
  code, never by the model (today's rule, kept).
- **MCP server** — one server, tools namespaced per pack. The session token
  is already scoped per agent session; a tool from another capability is
  refused (a new check).
- **Chat** — the deterministic router stays; intents are contributed by the
  pack (FOBO's "explain B-8") plus core intents ("what's pending", "show
  evidence for X"). Anything unrouted goes to the reasoner, as today.

## 6. Data model

Additive first. FOBO tables stay; they become the FOBO pack's tables.

| Table | Change |
|---|---|
| `capability` (new) | `capability_id`, `name`, `owner`, `manifest` (JSONB), `status`, `loaded_at` |
| `workflow_version` | add `capability_id`; "one active version" becomes **one per capability** (the partial unique index gains the column) |
| `investigation_session` → `case_run` | add `capability_id`, `case_key` (JSONB), `subject` (label for the UI). FOBO's `reconciliation_id`/`master_book` move into `case_key`. A view keeps the old name for one release |
| `case_item` (new, optional) | `case_id`, `item_id`, `kind`, `payload` JSONB — for packs with no tables of their own. FOBO keeps `break_event` |
| `pattern_group` → `proposal_group` | rename + `capability_id`; columns already generic |
| `controller_decision` → `decision` | `break_ids` → `item_ids`; otherwise unchanged |
| `source_call`, `session_message`, `agent_session`, `analysis_version`, `evidence_item` | add `capability_id` (denormalised, for per-capability analytics and entitlement) |
| `node`/`edge` knowledge graph | add `namespace` (one per pack); entitlement + bitemporal reads unchanged |
| `reconciliation`, `run`, `break_event`, `break_embedding` | unchanged; owned by the FOBO pack |

**Checkpoint compatibility.** LangGraph checkpoints store module paths. The
existing `sys.modules` alias pattern (`fobo/contracts/models.py`) is reused
for `fobo.*` → `helix.*` so open FOBO runs still resume. A test resumes a
checkpoint written before the move.

## 7. Orchestration

```
           ┌──────────── Helix core ────────────┐
event ───▶ │ open case ─▶ pick capability ─▶ pin │ ─▶ LangGraph run
(ready /   │                 workflow version    │     steps: core ∪ pack
schedule / └─────────────────────────────────────┘     gates: validate, review, record
manual)                                                    │
                                                           ▼
                   reasoner (port) ◀── MCP tools ◀── agent session
                                                           │
                                     human review (pause) ─┤
                                                           ▼
                                           decisions ─▶ priors for the next run
```

- `build_graph(capability, version)` replaces the single global build; the
  code path is the same, the step table is `core ∪ pack`.
- A case is opened by an **event** (`ready_event` today), a **schedule**, a
  **manual** start in the console, or an **API** call. FOBO's "first read of
  the board starts the run" becomes an explicit `opens_on` choice.
- One workflow per capability, versioned and approved per capability. The
  Workflow tab gains a capability selector; nothing else about it changes.
- Entitlement: a caller's roles are checked per capability (`review.roles`)
  as well as per entity scope (today).

## 8. Package layout

```
apps/backend/
  helix/
    core/
      workflow/      versions, settings, graph, step_registry (mechanism), gates
      steps/         group, reason, draft, validate, review, record, escalate
      reasoning/     port, adapters, request/response contracts
      mcp/           server, auth, audit, core tools
      grounding/     source_call recorder
      knowledge/     graph store, bitemporal reads, entitlement
      cases/         open/resume/read a case; decisions; chat router
      capabilities/  manifest schema, loader, validator, pack registry
      db/            core models + migrations
      web/           FastAPI app, auth, generic routes
    packs/
      fobo/          capability.yaml, workflow.yaml, playbook.yaml,
                     steps/ (resolve, gather, rank), cause_checks/, guards,
                     tools/, views/, seed_data/, db models for its tables
      sample/        capability.yaml only + a seed file — the generality proof
apps/console/src/
  core/              shell, capability switcher, case list, case detail,
                     session panel, workflow tab, MCP inspector, trace
  packs/fobo/        event board, adjustments panel, book drawer, constants
  packs/registry.js  view id → component, as listed in each manifest's `views`
```

## 9. API

| New | Replaces |
|---|---|
| `GET /api/capabilities` | — |
| `GET /api/capabilities/{cap}/board` | `GET /api/board` (kept as an alias for `fobo.cats-vs-motif` for one release) |
| `POST /api/cases/{case_id}/messages` | `POST /api/recs/{rec_id}/messages` |
| `POST /api/cases/{case_id}/decisions` | `POST /api/recs/{rec_id}/decisions` |
| `POST /api/capabilities/{cap}/cases` (open), `GET /api/cases/{id}/trace` | `/api/recs/{id}/investigate`, `/trace` |
| `/api/capabilities/{cap}/workflow/*` | `/api/workflow/*` |

## 10. Onboarding a capability

1. `helix capability new <id>` scaffolds `packs/<id>/` with a manifest,
   workflow and an empty rules file.
2. Fill in the manifest: case key, item schema, steps from the core library,
   tools, review policy, views.
3. Only if config cannot express it: add a step, tool, guard or panel in the
   pack, registered by name.
4. `helix capability validate <id>` — manifest, workflow order (existing
   `needs`/`produces` check), core gates present, every referenced
   tool/view/guard exists.
5. Load it: the capability row is created and workflow version 1 is
   **drafted**; a second person approves it in the Workflow tab — the same
   four-eyes rule as a workflow change today.
6. It appears in the console's capability switcher for callers with its roles.

## 11. Delivery phases

Each phase ships on its own, with the full suite green and **no FOBO
behaviour change** (same board, same figures, same decisions).

| # | Phase | Outcome |
|---|---|---|
| 0 | **Rename + split** — `fobo` → `helix.core` + `helix.packs.fobo`, console `core/` + `packs/fobo/`; checkpoint alias; docs | Pure moves; the full backend (475) and console suites pass unchanged |
| 1 | **Capability registry** — manifest schema + validator, `capability` table, FOBO manifest, pack registration, per-capability workflow versions | `/api/capabilities` lists FOBO; Workflow tab is per capability |
| 2 | **Generic case model** — `CaseState` with `pack.*` namespace, `case_run`, `proposal_group`, `decision`, `capability_id` columns; core steps read core keys only | Core steps have no FOBO imports (enforced by an import-lint test) |
| 3 | **Generic console shell** — capability switcher, generic case list/detail, view registry; FOBO board becomes the FOBO pack's view | FOBO looks the same; a pack without custom views still gets a usable UI |
| 4 | **Onboarding toolkit + sample pack** — scaffold/validate CLI, `case_item` table, core MCP tools, `packs/sample` from config only | A capability onboarded with zero Python — the generality proof |
| 5 | **Second real capability** — chosen with the team (variance commentary, generic recon, …) | — |

Phase 0 is mechanical and large; phases 1–4 are each roughly the size of the
MCP/agent-session change.

## 12. Open questions for the team

1. **Tenancy.** One shared database with `capability_id` everywhere (this
   design), or a schema per accounting group? Shared is simpler; per-group is
   stronger isolation if groups must not see each other's data.
2. **Who approves onboarding a capability** — Product Control only, or each
   group's own controllers?
3. **Entitlement source.** Roles per capability from the bank's IAM / BAM, or
   managed in Helix?
4. **Name for "case"** in the UI — case, session, review, run?
5. **No-code builder.** Once the manifest exists, a console editor for it is
   a natural phase 6. In scope for this year?

## 13. Risks

| Risk | Mitigation |
|---|---|
| Big-bang rename breaks open FOBO runs | Checkpoint module alias + a resume-old-checkpoint test (pattern already in the repo) |
| Over-generalising before a second real pack exists | Core grows only from what FOBO *and* the sample pack both need; anything else stays in the pack |
| Core quietly depending on FOBO | Import-lint test: nothing under `helix.core` imports `helix.packs` |
| Two workflow tabs/APIs during migration | Aliases live one release, then are removed |
