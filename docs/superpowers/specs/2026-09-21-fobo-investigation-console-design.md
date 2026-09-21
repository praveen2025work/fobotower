# FOBO Investigation Console — Design

**Version:** 1.0
**Status:** Approved design, ready for implementation planning
**Date:** 2026-09-21
**Repository:** `git@github.com:praveen2025work/fobotower.git`

---

## 1. Purpose and position

This document specifies a standalone application that makes the FOBO Control Tower
mock real: a controller opens a completed reconciliation analysis, interrogates it in
business language, pulls missing evidence from owning source systems through approved
tools or dropped files, and records a governed decision with a replayable audit trail.

The application is built to **AgentOne component conventions** but runs **entirely
separately**. Migration into AgentOne is performed later, by hand, by the repository
owner. Nothing in this design assumes access to an AgentOne checkout at build time.

### 1.1 Source documents

| Document | Role in this design |
|---|---|
| Helix Controller Investigation Model — BRD v1.9 | Governing contract. Session model, tool separation, decision rules R1–R7, data model, controls C1–C7, acceptance criteria A1–A10 |
| FOBO Agent — System Architecture v1.0 | Workflow state machine, bitemporal graph schema, cause checks, failure matrix, observability attributes |
| FOBO Control Tower — Agent One (HTML mock) | Target UI surface, design tokens, information architecture, analytics metrics |
| AgentOne Platform tech-stack reference | Component conventions, directory layout, event contract that migration must satisfy |

Where these conflict, section 3 records the resolution and its justification.

---

## 2. Decisions taken

These four decisions were made explicitly and are not revisited during implementation.

| # | Decision | Chosen | Consequence |
|---|---|---|---|
| **D1** | Vertical slice | **Full local stack on fixtures** | UI, FastAPI, LangGraph, MCP servers and Postgres all genuinely run. Every source adapter reads fixtures. Four adapter classes are swapped at migration; nothing else changes |
| **D2** | Orchestration | **Two lanes, one session** | LangGraph owns the batch investigation with no model in the control flow. Claude Agent SDK owns only the controller's chat drawer, bounded by a tool allow-list. Both read and write one `investigation_session_id` |
| **D3** | Knowledge graph | **Bitemporal graph + pgvector alongside** | Postgres `node`/`edge` with valid and transaction time for resolution, lineage and entitlement. pgvector beside it for similar-break recall and pattern grouping |
| **D4** | Code style | **JSX components + generated contract types** | Components are `.jsx` and drop into AgentOne unchanged. The event and evidence contract is defined once in Pydantic and generated to JSON Schema plus `.d.ts` |

### 2.1 Assumptions

1. **Fixtures are synthesised** from the mock's illustrative data — `APAC-CASH-01`
   through `APAC-CASH-12`, 14 breaks, the four patterns (`P-204`, `CPTY-REF`,
   `LATE-BOOK`, `DUP-SETTLE`), 7 recs across 3 regions, 4 run windows — plus a large
   synthetic population of approximately 4,800 breaks to exercise R4 paging. File-drop
   ingestion is built so real extracts replace fixtures without code change.
2. **The console is a full agent screen** mounted at `/fobo`, not a Module Federation
   remote. The mock carries its own top navigation and tab bar, which is a screen.
3. **Ports do not collide with AgentOne**, so both stacks can run simultaneously.
4. **No source system is reachable** during development. Every adapter is a fixture
   adapter behind the real adapter interface.

---

## 3. Reconciliations with the source documents

Two places where the source documents disagree, and how this design resolves them.

### 3.1 Session grain — rec/book/run, not per break

The architecture doc specifies `thread_id = break_id`, one workflow thread per break.
The BRD's data model keys `INVESTIGATION_SESSION` by `reconciliation_id`,
`master_book`, `business_date` and `run_id`. The mock settles it: run `R-1055` shows
**14 breaks in one case**, approved in **four pattern groups**, with a single
"Approve all 6" control.

**Resolution:** `thread_id = investigation_session_id`, at rec/book/run grain. The
break population lives inside the workflow state. The `gather` node fans out across
it. The review interrupt fires once per session, and the controller approves per
pattern group.

**Justification:** a per-break thread cannot offer group approval at all, because no
single thread can see the other thirteen breaks. Group approval is the product's
stated efficiency lever, so the grain must be the group's container.

### 3.2 A missing node — `group`

The mock's headline analytics metric is *"Decisions saved: 20 → 6"*. Neither source
document contains a step that performs that collapse.

**Resolution:** a `group` node is added between `gather` and `rank`. It clusters
breaks by cause-check signature, then reranks with pgvector against historical
resolution narratives to attach a pattern label and its prior approval rate.

**Justification:** this node is the efficiency lever the product is sold on, and it is
where pgvector earns its place in D3. Without it, pattern grouping has no owner and
the analytics tab has nothing to measure.

**Resulting node sequence:**

```
resolve → gather → group → rank → draft → validate → review ⏸ → record | escalate
```

---

## 4. Architecture

### 4.1 Two lanes, one session

```
                  ┌────────────────────────────────────────┐
                  │   ONE investigation_session_id         │
                  │   session · evidence · audit · version │
                  └───────▲────────────────────▲───────────┘
                          │                    │
        ┌─────────────────┴──────┐   ┌─────────┴────────────────┐
        │ LANE 1 — BATCH         │   │ LANE 2 — INVESTIGATE     │
        │ LangGraph              │   │ Claude Agent SDK         │
        │ model never chooses    │   │ model picks from         │
        │ the next step          │   │ an allow-list only       │
        │                        │   │                          │
        │ resolve → gather →     │   │ question → R1 check →    │
        │ group  → rank  →       │   │ R2 pick app → gate →     │
        │ draft  → validate →    │   │ tool → register →        │
        │ review ⏸ → record      │   │ R7 diff → revise ──┐     │
        └────────┬───────────────┘   └────────────────────┼─────┘
                 │                                        │
                 │         ┌──────────────────────────────┘
                 │         │  re-enters Lane 1 at `draft`
                 ▼         ▼
          ENTITLEMENT GATE — deterministic, never model-decided
                 │
    ┌───────┬────┴───┬────────┬────────────┬──────────┐
    │  MBR  │ MOTIF  │  CATS  │ Trade Store│  Helix   │
    │ tools │ tools  │ tools  │   tools    │ session  │
    └───┬───┴───┬────┴───┬────┴─────┬──────┴────┬─────┘
      adapter adapter  adapter   adapter    (no adapter —
        │       │        │          │        never leaves Helix)
    ┌───┴───────┴────────┴──────────┴───┐
    │ FIXTURE LAYER — 4 classes to swap  │
    └────────────────────────────────────┘
                 │
    ┌────────────┴──────────────────────────────┐
    │ Postgres: bitemporal node/edge · pgvector  │
    │           · LangGraph checkpoints          │
    └────────────────────────────────────────────┘
```

Neither lane touches a source adapter directly. Both converge on the entitlement gate
and the evidence store. That convergence is what makes the audit record single and
replayable, satisfying A10.

### 4.2 Where the model is used, and where it is not

| Function | Performed by | Why |
|---|---|---|
| Decide the next workflow step | **Nothing — the graph is fixed** | Control flow over a P&L adjustment must be deterministic |
| Interpret a controller question | LLM (Lane 2) | Natural language is what the model is for |
| Choose the owning application and tool | LLM, bounded by allow-list | Selection is reasoning; the allow-list constrains it |
| Authorise a call | Entitlement gate, deterministic | Access control must be reproducible and auditable |
| Retrieve, filter, aggregate, page | Adapter, at source | Keeps large payloads out of the model |
| Compare values and totals | Compare service, versioned code | A figure in an adjustment must be reproducible, not generated |
| Rank candidate causes | LLM with forced tool use, **only when more than one positive candidate** | Single-candidate cases take a deterministic fast path |
| Draft the narrative | LLM from labelled evidence | Explanation is language; figures come from evidence references |
| Record the decision | Controller | Material actions stay with the human |

---

## 5. Component specifications

### 5.1 Console (`apps/console`)

Next.js 16 App Router, React 19, JavaScript/JSX, Tailwind v4, shadcn/ui, Zustand,
TanStack Query, Recharts, Framer Motion.

**Routes**

| Route | Purpose |
|---|---|
| `/fobo` | Control Tower — run schedule, region rail, rec selection |
| `/fobo/[sessionId]` | Investigation case — pipeline, analysis, grounding, adjustments |
| `/fobo/analytics` | Agent analytics |

**Stores** (mirroring `financeAgentStore` conventions)

| Store | Holds |
|---|---|
| `foboRunStore` | Run schedule, regions, recs, per-rec status counts |
| `foboSessionStore` | Active investigation session, analysis versions, pipeline stage |
| `foboEvidenceStore` | Evidence items keyed by id, partitioned original vs newly retrieved |
| `foboDecisionStore` | Pattern groups, pending approvals, idempotency keys |

**Component groups** under `src/components/fobo/`: `shell`, `schedule`, `pipeline`,
`analysis`, `grounding`, `adjustments`, `investigate`, `analytics`.

**Design tokens** are lifted verbatim from the mock's `:root` block into
`src/styles/tokens.css` — brand, ground, frosted card, header gradient, status
colours, region colours, book-bar colours, radii and transition. Components reference
tokens only; no literal colour values in component files.

**Hard UI constraints** (from the BRD and the architecture doc, enforced in tests):

- A reject requires a reason; submission is blocked until text is present.
- A draft never renders without its evidence panel.
- The attempt counter is always visible.
- Decisions are disabled when the workflow is unreachable; decisions are never queued
  client-side.
- Original analysis evidence and newly retrieved evidence are visually and
  structurally separated (A5).
- A failed retrieval renders as a failure. The UI has no code path that substitutes a
  value for a missing one (A7).

### 5.2 API (`apps/api`)

FastAPI 0.133, Python 3.12, SQLAlchemy 2.0 async, Alembic.

**Routes**

| Route | Purpose |
|---|---|
| `runs` | Run schedule, region and rec status rollups |
| `sessions` | Open, resume and list investigation sessions |
| `breaks` | Break population within a session, paged |
| `decisions` | Record approve / reject / escalate, idempotent |
| `evidence` | Fetch evidence items and their provenance |
| `uploads` | File drop, hashing, registration as evidence |
| `analytics` | Metrics derived from Phoenix spans |
| `ws/chat` | Streaming controller investigation |

**Modules**

| Module | Responsibility |
|---|---|
| `app/workflow/` | LangGraph graph, state, nodes |
| `app/agents/base.py` | Claude Agent SDK wrapper, Lane 2 only |
| `app/graph/` | Graph repository, entitlement predicate, query templates |
| `app/evidence/` | Evidence store, source labeller, integrity hashing |
| `app/compare/` | Versioned deterministic comparison rules |
| `app/recon/` | Cause checks C1–C6 |
| `app/observability/` | OpenTelemetry instrumentation |

### 5.3 Contracts (`packages/contracts`)

Pydantic models are the single source of truth. A build step emits JSON Schema and
TypeScript declaration files. The console imports the declarations for editor support
and validates inbound events against the schema at runtime in development.

### 5.4 MCP servers (`mcp_servers/`)

Six FastMCP servers, one per tool group: `helix_session`, `mbr`, `motif`, `cats`,
`tradestore`, `crosssource`. Each runs as its own process in compose.

### 5.5 Recon engine stand-in (`app/recon`)

The architecture doc places the six cause checks in a Java Spring Boot service. This
build implements them in Python behind the same HTTP contract (`POST
/recon/cause-checks`), so the Java service can replace it without touching callers.

| Check | ID | Logic |
|---|---|---|
| Timing | C1 | FO booking timestamp later than BO ledger cut-off |
| Static | C2 | Mapping missing, or valid from a date inside the lookback |
| Valuation | C3 | FO and BO reference different rate or curve datasets |
| Components | C4 | Fee, funding or commission present on one side only |
| Amendment | C5 | Trade version mismatch across snapshots |
| Adjustment | C6 | Adjustment applied on one side, absent on the other |

All six run in parallel and **all six results are returned, including negatives**. The
same `(book, cob_date, snapshot_version)` must produce byte-identical output; this is
asserted in tests.

---

## 6. Data model

Ten entities, following the BRD's proposed model. Postgres, managed by Alembic.

| Entity | Key fields |
|---|---|
| `investigation_session` | `investigation_session_id` PK, `reconciliation_id`, `master_book`, `business_date`, `run_id`, `status`, `created_ts` |
| `interaction_session` | `interaction_session_id` PK, `investigation_session_id` FK, `controller_user_id`, `controller_role`, `start_ts`, `end_ts` |
| `analysis_version` | `analysis_version_id` PK, `investigation_session_id` FK, `summary`, `confidence_tier`, `prompt_version`, `skill_version`, `model_identifier` |
| `evidence_item` | `evidence_id` PK, `investigation_session_id` FK, `source_application`, `storage_mode`, `reference_uri`, `integrity_hash`, `is_original_analysis`, `retrieved_ts` |
| `question` | `question_id` PK, `interaction_session_id` FK, `question_text`, `selected_scope`, `asked_ts` |
| `source_call` | `call_id` PK, `question_id` FK, `application_name`, `mcp_tool_name`, `validated_parameters`, `entitlement_result`, `row_count`, `latency_ms`, `error_detail`, `called_ts` |
| `controller_decision` | `decision_id` PK, `investigation_session_id` FK, `controller_user_id`, `action`, `reason`, `decided_ts` |
| `mcp_tool` | `tool_name` PK, `application_name` FK, `tool_group`, `field_allow_list`, `max_rows`, `timeout_ms` |
| `application` | `application_name` PK, `integration_type`, `adapter_endpoint`, `owning_team` |
| `audit_entry` | `audit_id` PK, `decision_id` FK, `event_type`, `payload_reference`, `event_ts` |

Two additions beyond the BRD, required by decisions taken here:

| Entity | Reason |
|---|---|
| `pattern_group` | `group_id` PK, `investigation_session_id` FK, `pattern_code`, `label`, `mode` (auto or manual), `break_ids`, `historical_approval_rate`. Required by the `group` node (3.2); the BRD model has no home for `P-204` |
| `workflow_checkpoint` | `thread_id`, `node_name`, `state_snapshot` JSONB, `timestamp`, `schema_version`. LangGraph persistence; composite PK on all three of thread, node and timestamp |

`controller_decision` is extended with a nullable `group_id` FK, because the mock
approves per pattern group, not per break.

The graph tables — `node`, `edge`, `break_event` and `break_embedding` — are specified
in §8.1 rather than here. They share the database but not the lifecycle: session
entities are written per investigation, graph entities are written by ingestion and by
the `record` node.

---

## 7. Workflow specification (Lane 1)

### 7.1 State

State is session-grained, per 3.1. Break-level results are keyed by `break_id`.

```python
class InvestigationState(TypedDict):
    # Identity
    investigation_session_id: str
    reconciliation_id: str
    master_book: str
    business_date: date
    run_id: str
    caller: Caller

    # Population
    breaks: List[BreakRecord]
    book_resolutions: Dict[str, str]        # break_id -> book_id

    # Gather outputs, keyed by break_id
    deltas: Dict[str, Delta]
    candidates: Dict[str, List[CandidateCause]]
    priors: Dict[str, List[PriorBreak]]
    lineage: Dict[str, List[LineageNode]]
    evidence: List[EvidenceRef]
    evidence_gaps: List[str]

    # Group output
    pattern_groups: List[PatternGroup]

    # Rank / draft / validate
    ranking: Dict[str, List[RankingEntry]]
    draft: Optional[AnalysisDraft]          # what_happened, why, what_to_do, risk
    validation_errors: List[str]
    hypothesis_attempts: int

    # Review
    review_cycles: int
    decisions: List[GroupDecision]

    # Outcome
    outcome: Optional[str]
    escalation_reason: Optional[str]
```

`Caller` carries `staff_id`, `roles`, `entity_scope` and `region`. It is constructed
once, in the API layer, and is immutable thereafter. No other component constructs a
`Caller`.

### 7.2 Loop control

```python
MAX_HYPOTHESIS_ATTEMPTS = 3
MAX_REVIEW_CYCLES = 2
```

Both counters live in state and are checkpointed, so they survive process restarts. A
Bedrock throttle triggers backoff and **does not** increment `hypothesis_attempts`.

### 7.3 Nodes

| Node | Type | Behaviour |
|---|---|---|
| `resolve` | Deterministic | Resolve each break's book via the graph repository, pinned to `as_of = business_date`. Zero matches escalates `UNRESOLVED_BOOK`; multiple matches escalates `AMBIGUOUS_BOOK` and never auto-picks |
| `gather` | Deterministic | Fan out per break: `compute_delta`, `cause_checks`, `lineage`, `similar_breaks`. 30s budget per call, 45s overall. Missing priors degrade and flag `evidence_gaps`; missing delta or cause checks escalate |
| `group` | Hybrid | Cluster breaks by cause-check signature, rerank with pgvector against historical resolutions, attach pattern code, label, mode and historical approval rate |
| `rank` | Hybrid | Fast path: a single positive candidate is assigned 10000 bps deterministically and the model is skipped. Otherwise call the reasoning client with forced tool use |
| `draft` | Model | Produce the four-part narrative — what happened, why, what to do, risk — plus a confidence basis. 400 token cap |
| `validate` | Deterministic | Hard assertions: every figure traces to an evidence reference, candidate ids exist in the input set, evidence ids exist, `share_bps` sums to 10000 ± 100, length, PII, adjustment sanity |
| `review` | Human interrupt | Checkpoint and pause. Resumed by the decisions route |
| `record` | Deterministic | Transactional write of commentary and adjustments, plus graph edges `Break -[EXPLAINED_BY]-> Commentary` and `Break -[RESOLVED_BY]-> Adjustment` |
| `escalate` | Terminal | Set reason code, notify the resolved owner, preserve all gathered evidence |

### 7.4 The `revise` entry point

`revise` is not a node in the linear sequence. It is a resume target: Lane 2 resumes
the checkpointed thread **at `draft`** with an enriched evidence set, producing
`analysis_version` N+1. The previous version is retained; the console renders the
diff.

This is the mechanism that keeps a revised explanation exactly as auditable as the
original. The model never edits an analysis in place — it triggers a deterministic
re-draft through the same validation path.

### 7.5 Escalation reasons

`UNRESOLVED_BOOK`, `AMBIGUOUS_BOOK`, `UNMAPPED_BOOK`, `DELTA_UNAVAILABLE`,
`CHECKS_UNAVAILABLE`, `RETRY_EXHAUSTED`, `VALIDATION_FAILED`.

---

## 8. Knowledge graph specification

### 8.1 Bitemporal schema

```sql
CREATE TABLE node (
    node_id         VARCHAR(64) PRIMARY KEY,
    node_type       VARCHAR(32) NOT NULL,
    natural_key     VARCHAR(128) NOT NULL,
    legal_entity_id VARCHAR(64) NOT NULL,   -- first-class, not in attrs: see 8.4
    attrs           JSONB NOT NULL DEFAULT '{}',
    valid_from      DATE NOT NULL,
    valid_to        DATE,                   -- NULL = currently valid
    recorded_from   TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_to     TIMESTAMPTZ
);

CREATE TABLE edge (
    edge_id        VARCHAR(64) PRIMARY KEY,
    from_node_id   VARCHAR(64) NOT NULL REFERENCES node(node_id),
    to_node_id     VARCHAR(64) NOT NULL REFERENCES node(node_id),
    edge_type      VARCHAR(32) NOT NULL,
    attrs          JSONB NOT NULL DEFAULT '{}',
    valid_from     DATE NOT NULL,
    valid_to       DATE,
    recorded_from  TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_to    TIMESTAMPTZ
);

-- Event layer: breaks as they are raised and resolved, plus their embeddings
CREATE TABLE break_event (
    break_id       VARCHAR(64) PRIMARY KEY,
    book_id        VARCHAR(64) NOT NULL REFERENCES node(node_id),
    line_code      VARCHAR(32) NOT NULL,
    cob_date       DATE NOT NULL,
    fo_value       NUMERIC(20,4),
    bo_value       NUMERIC(20,4),
    delta          NUMERIC(20,4),
    pattern_code   VARCHAR(32),           -- set by the `group` node
    outcome        VARCHAR(32),           -- set by `record`; NULL while open
    narrative      TEXT,                  -- resolution commentary, once recorded
    recorded_from  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE break_embedding (
    break_id         VARCHAR(64) PRIMARY KEY REFERENCES break_event(break_id),
    embedding        vector(1024),
    model_identifier VARCHAR(64) NOT NULL, -- so a model change is detectable
    embedded_ts      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_node_type_key    ON node(node_type, natural_key);
CREATE INDEX idx_node_entity      ON node(legal_entity_id, node_type);
CREATE INDEX idx_edge_from        ON edge(from_node_id, edge_type, valid_from, valid_to);
CREATE INDEX idx_edge_to          ON edge(to_node_id, edge_type, valid_from, valid_to);
CREATE INDEX idx_similar_breaks   ON break_event(book_id, line_code, cob_date);
```

`break_event` is the event layer the architecture doc describes: rows are written by
`record` as breaks are raised and resolved, and read back by `similar_breaks` as
priors. It is deliberately not bitemporal — a break is an event that happened, not a
fact whose validity changes over time.

Reference data is **never updated in place**. A change closes the existing edge by
setting `valid_to = effective_date - 1` and inserts a new one. Updating in place
destroys `as_of` history, which is the one property the whole temporal design exists
to provide.

Dialect-specific SQL lives in `app/graph/queries/`, selected by a dialect setting, so
the Oracle variant can be added without touching repository callers.

### 8.2 Repository interface

```python
class GraphRepository(Protocol):
    def resolve_book(self, book_ref: str, as_of: date, caller: Caller) -> BookResolution: ...
    def book_context(self, book_id: str, as_of: date, caller: Caller) -> BookContext: ...
    def lineage(self, book_id: str, direction: str, depth: int,
                as_of: date, caller: Caller) -> List[LineageNode]: ...
    def similar_breaks(self, book_id: str, line_code: str, cob_date: date,
                       lookback: int, caller: Caller) -> List[PriorBreak]: ...
```

Every method takes `as_of` and `caller`. Neither is optional, and neither has a
default. A method that could be called without them would eventually be called
without them.

### 8.3 Lineage traversal

Bounded recursive CTE, depth-limited to prevent cycles, with every join filtered by
`valid_from <= :as_of AND (valid_to IS NULL OR valid_to >= :as_of)`. Maximum depth 4
in the workflow; the MCP tool truncates at 50 hops.

### 8.4 Entitlement predicate

Applied to every query before execution, never after:

```python
def build_entitlement_predicate(caller: Caller):
    return and_(
        Node.node_type.in_(visible_node_types(caller.roles)),
        Node.legal_entity_id.in_(caller.entity_scope),
    )
```

**Visibility matrix**

| Node type | FO | BO | PC | REG | RISK |
|---|---|---|---|---|---|
| Trade | ✅ | ❌ | ✅ | ❌ | ✅ |
| Position | ✅ | ❌ | ❌ | ❌ | ✅ |
| LedgerEntry | ❌ | ✅ | ✅ | ✅ | ❌ |
| StaticMapping | ❌ | ✅ | ❌ | ✅ | ❌ |
| Adjustment | ❌ | ✅ | ✅ | ❌ | ❌ |
| RiskRun | ✅ | ❌ | ❌ | ❌ | ✅ |
| Job | ✅ | ✅ | ✅ | ❌ | ❌ |
| Book | ✅ | ✅ | ✅ | ✅ | ✅ |
| Desk | ✅ | ✅ | ✅ | ✅ | ✅ |

Post-filtering is prohibited: it leaks through counts and timing. Prompt instructions
are not access controls.

### 8.5 Caching

Reference-layer reads are cached on `(method, args, as_of, caller_scope)`. Event-layer
reads are never cached. **The cache key includes `caller_scope`**, so one controller's
cached lineage can never be served to another.

### 8.6 pgvector

Two uses, both advisory on top of a deterministic core:

1. **`similar_breaks` rerank** — the indexed structural query on
   `(book_id, line_code, cob_date)` runs first and bounds the candidate set. Embedding
   similarity over prior break narratives then reranks within that set. Embeddings
   never widen the set beyond what the structural query and entitlement predicate
   allow.
2. **Pattern labelling in `group`** — cluster by cause-check signature, then match the
   cluster centroid against historical resolution narratives to attach a pattern code
   and its approval rate.

Embeddings are generated through the Bedrock embeddings client and stored in
`break_embedding` (§8.1), keyed by `break_id` and carrying the model identifier so a
model change is detectable. A similarity result whose `model_identifier` differs from
the current one is ignored rather than compared across embedding spaces.

---

## 9. MCP tool layer

Tools are separated by application. That separation is the control: it makes a MOTIF
request independently governed, owned and audited from a CATS request.

### 9.1 Catalogue

| Group | Tools |
|---|---|
| **Helix session** (no adapter) | `helix_get_analysis_context`, `helix_get_evidence_item`, `helix_get_investigation_history` |
| **MBR** | `mbr_summarise_breaks`, `mbr_search_breaks`, `mbr_get_break_details` |
| **MOTIF** | `motif_summarise_exceptions`, `motif_search_exceptions`, `motif_get_exception_details`, `motif_get_record_history` |
| **CATS** | `cats_get_book_values`, `cats_get_trade_values`, `cats_get_record_history` |
| **Trade Store** | `tradestore_get_trade_details`, `tradestore_get_trades`, `tradestore_get_trade_history` |
| **Cross-source** (no adapter) | `compare_cats_motif_values`, `get_request_status`, `check_application_health` |

`create_evidence_export` is deliberately out of scope; see section 17.

### 9.2 Tool contract

Every tool declares, and the server enforces:

- a **field allow-list** — only named fields are ever returned;
- **mandatory scope filters** — COB date and master book at minimum;
- **`max_rows`** and **`timeout_ms`**;
- a response envelope carrying `row_count`, `truncated` and `source_timestamp`.

Filter parameters are validated against fixed templates. **Model-generated SQL is
never executed**, under any circumstance.

### 9.3 Adapters

One adapter per application, implementing a single interface. In this build all four
are fixture adapters:

| Application | Interface at migration | Fixture behaviour now |
|---|---|---|
| MBR | Query service | Reads `fixtures/mbr/*.json` |
| MOTIF | Query service | Reads `fixtures/motif/*.json` |
| CATS | File or API | Reads `fixtures/cats/*.csv` through DuckDB |
| Trade Store | REST API | Reads `fixtures/tradestore/*.json` |

Swapping to real systems means replacing four classes. Filtering, paging and
aggregation already happen inside the adapter, so the boundary does not move.

---

## 10. The enrichment loop (Lane 2)

Rules are evaluated in order. R5 and R6 can interrupt at any point during retrieval.

| Rule | Question answered | Behaviour |
|---|---|---|
| **R1** | Do I already have this? | If session evidence suffices, answer from it. **No source call** |
| **R2** | Who owns the missing data? | Identify the owning application; call only that application's approved tool |
| **R3** | What if I need two systems? | Call each separately. Keep every record labelled by source. Never merge into one undifferentiated result |
| **R4** | What if the result is enormous? | Return count and grouped summary first. Controller narrows scope, then a bounded page is requested |
| **R5** | What if the source fails? | Show the failure. **Never invent an answer** |
| **R6** | What if access is denied? | Do not retrieve, do not display. Record the blocked attempt |
| **R7** | What if new evidence changes the picture? | Preserve both versions and show what changed. Never silently overwrite |

### 10.1 Sequence

1. Controller asks a question. The exact text and selected scope are stored.
2. Context builder assembles the package: analysis summary, business identifiers,
   evidence references, controller access scope, tool policy. **Never a full dataset,
   never credentials, never raw rows.**
3. Model returns its interpretation, chosen application and chosen tool.
4. Entitlement gate authorises. Denied follows R6.
5. The permitted call reaches exactly one application lane.
6. Adapter filters, aggregates and pages at source; returns a bounded result with
   `row_count` and `truncated`.
7. Evidence is registered with `source_application`, `retrieved_ts`,
   `is_original_analysis = false` and an integrity hash.
8. If values need comparing, `compare_cats_motif_values` runs versioned deterministic
   code over linked evidence ids and returns the difference with its references.
9. If the picture has changed, `revise` resumes the thread at `draft` (7.4).
10. The controller records the action and reason.

### 10.2 Large populations

Scope → summarise → narrow → page → detail. Mandatory filters on COB date, master
book, reconciliation and region. Counts and grouped totals precede rows. Pages are
bounded and carry a continuation token. Detail is fetched for selected ids only.

---

## 11. File ingestion

A dropped file is not a special case. It takes the identical evidence path:

1. Upload to `api/routes/uploads.py`; size and type validated.
2. Integrity hash computed; file stored; `reference_uri` recorded.
3. Registered as an `evidence_item` with `source_application` set to the owning
   application and `storage_mode = copy`.
4. Parsed into DuckDB for querying.
5. Exposed to both lanes through the owning application's tool group — for CATS, via
   the file adapter the BRD already anticipates.

The result is that a file and a tool call produce identically shaped, identically
labelled evidence, and the console renders them the same way. One path, not two.

Copies are made only where retention and classification rules permit; otherwise
evidence is stored by reference. This is a configuration switch on the evidence store,
defaulting to reference.

---

## 12. Event contract

Generated from Pydantic in `packages/contracts`. This table is the migration surface
and must stay stable.

| Event | Emitted by | Payload |
|---|---|---|
| `run.progress` | Lane 1 | `session_id`, `node`, `breaks_processed`, `breaks_total` |
| `thinking` | both | `text`, `session_id` |
| `text` | Lane 2 | `delta`, `interaction_session_id` |
| `tool_use` | both | `application`, `tool`, `validated_parameters`, `row_count`, `truncated`, `latency_ms`, `entitlement_result` |
| `evidence.registered` | both | `evidence_id`, `source_application`, `retrieved_ts`, `is_original_analysis` |
| `analysis.version` | Lane 1 | `analysis_version_id`, `supersedes`, `diff` |
| `approval.required` | Lane 1 | `group_id`, `pattern_code`, `break_ids`, `historical_approval_rate` |
| `decision.recorded` | API | `decision_id`, `action`, `reason`, `idempotency_key` |
| `error` | both | `code`, `message`, `application`, `recoverable` |

The console's `WebSocketClient` auto-reconnects and resubscribes by
`investigation_session_id`. Because all state lives in Postgres, a reconnect that
lands on a different worker loses nothing.

---

## 13. Error handling

| Failure | Detected in | Behaviour |
|---|---|---|
| Book unresolvable | `resolve` | Escalate `UNRESOLVED_BOOK` |
| Book ambiguous | `resolve` | Escalate `AMBIGUOUS_BOOK`. Never auto-pick |
| Mapping missing for `as_of` | Graph repository | Escalate `UNMAPPED_BOOK`, raise a control finding |
| Delta unavailable | Recon | Escalate. There is nothing to explain |
| Cause checks unavailable | Recon | Escalate. Refuse to rank without candidates |
| Priors unavailable | Graph repository | Continue degraded, flag `evidence_gaps`, surface in the analysis panel |
| Model returns an unknown candidate | `rank` | Validation error, retry within cap |
| Model invents a number | `validate` | Validation error, retry within cap |
| Bedrock throttled | Reasoning client | Backoff, max 3 retries. Does **not** consume a hypothesis attempt |
| Retry cap reached | Workflow | Escalate `RETRY_EXHAUSTED` with all evidence attached |
| Source adapter down | Adapter | Circuit breaker opens. `check_application_health` reports it. UI states the source is unavailable and retrieves nothing |
| Entitlement denied | Gate | Blocked, nothing displayed, attempt recorded |
| Checkpoint schema mismatch | Checkpoint store | Migrate or drain. **Never best-effort deserialize** |
| Duplicate decision | Decisions route | 409 on a repeated `Idempotency-Key` |

Every decision request requires an `Idempotency-Key` header. A duplicated P&L
adjustment is the worst available outcome, and a retry on a flaky connection is the
likeliest way to cause one.

---

## 14. Security

- **Authentication** in this build is a development stub that constructs the same
  `Caller` object real auth would. Swapping to OAuth2 plus an entitlement service
  touches exactly one function.
- **Authorisation** is enforced in the graph repository and the entitlement gate.
  Never in the console, never in a prompt, never by post-filtering.
- **The `Caller` is constructed once**, in the API layer, and is immutable. No other
  component builds one.
- **No credentials, tokens or raw pre-entitlement rows** ever enter a prompt.
- **PII detection** runs in `validate`. Counterparty names are redacted from model
  inputs where the caller is not entitled, and a draft containing an unauthorised
  counterparty reference is rejected.
- **Evidence** is encrypted at rest and in transit; audit access is restricted.

---

## 15. Observability

Phoenix with OpenTelemetry instrumentation for LangGraph, Bedrock and the MCP layer.

**Span attributes:** `investigation_session_id`, `book_id`, `cob_date`, `as_of`,
`hypothesis_attempts`, `candidate_count`, `evidence_gaps`, `prompt_version`,
`skill_version`, `model_identifier`, `caller_scope`, and per source call the
application, tool, validated parameters, entitlement result, latency, row count and
error detail.

**The analytics tab reads from these spans**, not from a parallel pipeline. Grounding
pass rate, draft acceptance, decisions saved, median draft-to-sign-off and estimated
hours saved are therefore measured rather than asserted.

Grounding pass rate reflects the numeric-grounding validator, not model confidence.
The two are different things and are labelled differently in the UI.

---

## 16. Testing

| Layer | Approach |
|---|---|
| Workflow | pytest-asyncio per node. Fixture states drive each branch, including every escalation reason |
| Graph repository | Query tests against a seeded database, including bitemporal correctness — a query at an earlier `as_of` returns the earlier hierarchy |
| Entitlement | Negative tests asserting a caller **cannot** see what the visibility matrix forbids, per role and per node type |
| MCP tools | Contract tests for field allow-list, `max_rows`, timeout and truncation flag |
| Determinism | Same `(book, cob_date, snapshot_version)` produces byte-identical cause-check output |
| Event contract | Every event validated against generated JSON Schema in both directions. This is the test that stops the two lanes drifting |
| Console | Vitest and React Testing Library from the first commit, including the hard UI constraints in 5.1 |
| Evaluation | One case per acceptance criterion A1–A10 |

Frontend tests exist from commit one specifically because AgentOne has none. Adding
them here costs little and the configuration migrates with the app.

---

## 17. Out of scope

| Excluded | Reason |
|---|---|
| Bulk export path (`create_evidence_export`) | The BRD defers it; scope-summarise-narrow-page-detail covers the population |
| Oracle | Postgres behind an Oracle-swappable repository interface |
| Neptune or a native graph database | No measured need; the migration trigger is a median traversal above 200ms at depth 4 |
| Airflow ingestion | A fixture loader script serves this build |
| BAM SSO | Development caller stub, one function to swap |
| Automated posting to MOTIF or FAS | Read-only investigation, matching the BRD's go-live position |
| Cross-entity or cross-region aggregation | Outside the current reconciliation scope |

---

## 18. Local runtime

| Service | Port | Notes |
|---|---|---|
| Console | 3100 | Next.js dev server |
| API | 8100 | Uvicorn, single worker in development |
| Postgres | 5433 | pgvector extension enabled |
| Phoenix | 6007 | Traces and evaluation |
| MCP servers | 9101–9106 | One per tool group |

Every port is offset from AgentOne's defaults so both stacks run simultaneously.
`docker-compose.yml` brings up the full set; the fixture loader runs as a one-shot
service on first start.

---

## 19. Fixtures

| Fixture set | Contents |
|---|---|
| Reference graph | Books, desks, entities, cost centres, mappings and ownership for the mock's 7 recs across APAC, EMEA and AMER, with at least one book whose hierarchy changed mid-period, to prove `as_of` correctness |
| Break population — small | The mock's 14 breaks across `APAC-CASH-01`…`12`, producing exactly the four pattern groups `P-204`, `CPTY-REF`, `LATE-BOOK`, `DUP-SETTLE` |
| Break population — large | ~4,800 breaks on one reconciliation, to exercise R4 scope-summarise-narrow-page-detail |
| Prior resolutions | 60 days of history including 42 prior `P-204` resolutions at an 88% approval rate, so the `group` node's historical rate is derived rather than hard-coded |
| Source records | CATS cash movements, MOTIF ledger entries, MBR break records and Trade Store trade facts, deliberately inconsistent in the ways the six cause checks detect |
| Edge cases | An unresolvable book, an ambiguous book, a source that fails on demand, a book outside the default caller's entity scope |

The small population must reproduce the mock's numbers exactly. If the fixtures
produce different pattern groups than the mock shows, the grouping logic is wrong and
the test suite says so.

---

## 20. Migration into AgentOne

| Step | Action |
|---|---|
| 1 | Copy `apps/console/src/app/fobo/`, `src/components/fobo/`, the four stores, the hooks and `tokens.css` into the AgentOne frontend. Paths already match |
| 2 | Add `/fobo` to the sidebar navigation |
| 3 | Copy `app/workflow/`, `app/graph/`, `app/evidence/`, `app/compare/` and `app/recon/` into the AgentOne backend |
| 4 | Register the routes in `api/main.py` |
| 5 | Register the MCP servers in `config/agents/base.yaml`; add access rules to `config/tool_governance.yaml` and content rules to `policies.yaml` |
| 6 | Replace the four fixture adapters with real ones |
| 7 | Replace the caller stub with BAM plus the entitlement service |
| 8 | Point the database configuration at the AgentOne RDS instance and run the Alembic migrations |
| 9 | Add the MCP sidecars to the task definition and extend the CI configuration |

Steps 6 and 7 are the only ones requiring new code. Everything else is a move plus a
registration.

---

## 21. Build order

| Phase | Delivers | Proves |
|---|---|---|
| **1** | Contracts package, Postgres schema, fixture loader, LangGraph happy path through the review interrupt, console shell with run schedule and pipeline rail | Checkpoint and resume genuinely work |
| **2** | Analysis panel, grounding list, pattern-grouped adjustments, group approval, idempotent decision recording, `record` node | The mock, live on real state |
| **3** | Helix, MOTIF and CATS tool groups, entitlement gate, chat drawer, R1–R7, `revise`, evidence diff | The investigation loop |
| **4** | MBR and Trade Store tool groups, file ingestion, R4 paging, analytics tab, evaluation suite | Full BRD coverage |

Phase 3 covers two source applications before four, mirroring the BRD's own §19.4
scope decision for the same reason: it proves the whole chain without multiplying
entitlement and source-approval work.

---

## 22. Acceptance criteria mapping

| # | Criterion | Satisfied by |
|---|---|---|
| A1 | Controller opens a completed analysis and sees outcome, explanation, evidence and next step | §5.1 routes, §7.3 `draft` |
| A2 | Follow-up question in business language answered from labelled evidence | §10 |
| A3 | Answer from stored evidence when sufficient; call only the owning application otherwise | §10 R1, R2 |
| A4 | Every evidence item identifies source application and retrieval time | §6 `evidence_item`, §12 `evidence.registered` |
| A5 | Original and newly retrieved evidence visually and structurally separated | §6 `is_original_analysis`, §7.4 `revise`, §5.1 |
| A6 | Denied entitlement blocks retrieval and display, and is recorded | §8.4, §10 R6, §13 |
| A7 | A source failure is shown as a failure; no answer fabricated | §10 R5, §13 |
| A8 | Large population handled without exceeding payload limits | §9.2, §10.2 |
| A9 | Resumed session reconstructs context from the stored business session | §7.1, §6 `workflow_checkpoint`, §12 reconnect |
| A10 | Complete session history retained and replayable | §6, §15 |

---

## 23. Open points

These do not block implementation on fixtures. Each is a swap, not a redesign, and
each has a defined default until answered.

| # | Point | Default until answered |
|---|---|---|
| O1 | Approved tools and returned fields per application | The catalogue in §9.1 with conservative allow-lists |
| O2 | Integration type per application — API, query service, file or restricted adapter | Per §9.3 |
| O3 | Retention periods for sessions, evidence and prompts | Retained indefinitely in development; reference storage is the default |
| O4 | Maker-checker rules | Single approver in development; the decision record already carries approver identity |
| O5 | Conflicting-evidence handling beyond R7 | Both versions retained and diffed; no automatic reconciliation |

---

*End of design document*
