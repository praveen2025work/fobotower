# Helix — How a Use Case Works

**Date:** 2026-10-03 · **Status:** draft for team review · **Companion to:**
[`2026-10-03-helix-capability-platform-design.md`](2026-10-03-helix-capability-platform-design.md)

What Helix provides as infrastructure, what a use case brings, and what
happens — layer by layer — from onboarding a use case to auditing a decision
it produced. One worked example runs through the whole document.

## 1. The platform in one picture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  GENERIC UI (Next.js)                                                        │
│  capability switcher · case list · case detail · agent chat · evidence ·     │
│  review & sign-off · capability builder · connector admin · workflow tab     │
├──────────────────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION (LangGraph)                                                   │
│  manifest → versioned workflow → graph of core steps                          │
│  load · match · compare · group · enrich · reason · draft                     │
│  validate · review · record   ◀── mandatory gates                            │
│  checkpoints in Postgres: pause for people, resume, replay                   │
├───────────────────────────┬───────────────────────────┬──────────────────────┤
│  LLM CONNECTIVITY         │  KNOWLEDGE GRAPH          │  ENTITLEMENT         │
│  reasoning port           │  subjects, lineage,       │  central bank        │
│  none · session service · │  past decisions (priors), │  service: roles +    │
│  direct (Claude)          │  bitemporal "as of"       │  data scopes         │
│  guards applied by code   │  one namespace per use    │  fail closed         │
│                           │  case (pgvector for       │                      │
│                           │  similarity)              │                      │
├───────────────────────────┴───────────────────────────┴──────────────────────┤
│  MCP GATEWAY                                                                 │
│  one door to every bank system · tool allow-list per use case ·              │
│  data scope enforced on every call · every call recorded                     │
├──────────────────────────────────────────────────────────────────────────────┤
│  CONNECTORS (onboarded by the Helix team)                                    │
│  GL · budget · CATS · MOTIF · custody · … each an MCP server                 │
└──────────────────────────────────────────────────────────────────────────────┘
   AUDIT (Postgres, system of record)      OBSERVABILITY (Phoenix, OpenTelemetry)
   who, what, which version, which data    every step, LLM call, tool call as a trace
```

## 2. Who does what

| Party | Provides | Never has to do |
|---|---|---|
| **Helix team** | The platform above; onboards and approves **MCP connectors**; runs Phoenix | Write code for a specific use case |
| **Use-case owners** (e.g. Product Control, Finance) | A manifest in the capability builder: which connector tools, which steps, rules and thresholds, the agent's instructions, review roles; approve each other's changes | Write code, provision infrastructure, build screens |
| **Preparers / reviewers** | Work cases in the generic UI: read the analysis, ask the agent, approve or reject | Leave Helix to find evidence |
| **Bank systems** | Data through MCP connectors; roles and data scopes through the entitlement service | Know anything about Helix's internals |
| **Audit / model risk** | Review Postgres audit rows and Phoenix traces | Ask engineers to reconstruct what happened |

## 3. Lifecycle of a use case

```
 ① ONBOARD            ② RUN (every case)                          ③ LEARN        ④ AUDIT & OBSERVE
 connector ─┐         open ─▶ load ─▶ analyse ─▶ reason ─▶ draft    decisions      Postgres audit rows
 manifest  ─┼▶ approve        │                     │        │      become         + Phoenix traces,
 owners    ─┘   (4-eyes)      │                     ▼        ▼      priors in the  joined on case_id
                              │                  agent ◀─ MCP ─▶   knowledge graph
                              ▼                  (LLM)   gateway
                         validate ─▶ review (people) ─▶ record
```

### ① Onboard

| Step | Who | Platform piece | Result |
|---|---|---|---|
| 1. Register the data source as an MCP connector; allow-list its tools; contract test | Helix team | MCP gateway, `connector_version` | Tools appear in the builder's tool picker |
| 2. Second Helix member approves | Helix team | four-eyes on `connector_version` | Connector `active` |
| 3. Create the capability: case key and label, items, steps, rules, agent skill, tools, review roles, screen columns | Use-case owner | Capability builder → manifest | `capability_version` draft |
| 4. Validate | Helix (automatic) | Manifest validator + step `needs`/`produces` check + gates present + tools allowed + roles exist in entitlement | Errors shown in plain words, or ✓ |
| 5. Approve | Another owner | four-eyes on `capability_version` | Capability live; workflow version 1 active |
| 6. Users with its roles see it in the switcher | — | Entitlement | Ready to run |

### ② Run — one case

| # | What happens | Platform piece | Written to |
|---|---|---|---|
| 1 | A case opens: event, schedule, manual start or API | Orchestration | `case_run` pinned to the workflow + manifest versions active now |
| 2 | Caller's roles and data scopes fetched | Entitlement | cached on the run; checked on every later call |
| 3 | `load`: items fetched through a connector tool, scope enforced, `in_scope` applied | MCP gateway | `case_item` rows; `source_call` row per tool call |
| 4 | `match` / `compare`: deterministic arithmetic | Orchestration (code, no LLM) | state: deltas, breaks / variances |
| 5 | `group`: items collapsed into proposal groups; priors attached from past decisions | Knowledge graph | `proposal_group` rows |
| 6 | `enrich`: listed tools called per group for evidence | MCP gateway | `source_call` rows |
| 7 | `reason`: rules settle what they can; the rest goes to the agent with the skill and allowed tools only | LLM connectivity + MCP gateway | `agent_session`; agent's tool calls as `source_call` rows |
| 8 | Guards check every agent verdict; anything unevidenced escalates | Orchestration (code, not the model) | findings, evidence gaps |
| 9 | `draft`: summary / commentary written | LLM or template | `analysis_version` |
| 10 | `validate` **gate**: every figure must trace to a `source_call` result, or the draft is rejected | Orchestration | validation errors → retry or escalate |
| 11 | `review` **gate**: run pauses; entitled people see it in the UI, chat with the agent, approve/reject per group or item | Generic UI + LangGraph interrupt | `session_message`, `decision` (idempotent) |
| 12 | `record` **gate**: outcome written; optional write-back tool | Orchestration + MCP gateway | `decision`, knowledge-graph priors |

Every step runs inside an OpenTelemetry span, so the same run is visible in
Phoenix as one trace (§7).

### ③ Learn

Approved decisions are written to the knowledge graph as **priors**: "this
pattern, on this subject, was approved with this explanation". The next run's
`group` step attaches them, and the agent can query them through the
`core.similar_decisions` tool. Approval rates per pattern (FOBO's "88% from 42
priors") are derived from them, never typed in.

### ④ Audit and observe — §6 and §7.

## 4. Worked example — month-end P&L variance commentary

A Finance team wants AI-drafted commentary on material month-end variances.

**Onboard**

1. The Helix team onboards two connectors: `gl` (tools `gl.variances`,
   `gl.journal_lines`) and `budget` (`budget.plan_lines`), each with `entity`
   as its data-scope argument.
2. A Finance owner builds the capability in the console: case label "Lane",
   key `entity × period`, opens on schedule (06:00 on working day 2), items
   from `gl.variances`, in scope if `|variance| ≥ £50,000`, steps
   `load → group → reason → draft → validate → review → record`, group by
   `account`, the agent skill "explain each variance from GL and budget;
   cite every figure", review roles `FIN_PREPARER`, `FIN_REVIEWER`.
3. A second owner approves. Done — no code, no deployment.

**Run (UK01, September)**

| Time | What happens | Seen where |
|---|---|---|
| 06:00 | Scheduler opens lane `UK01 / 2026-09`; pinned to manifest v3, workflow v2 | Case list: "Analysing" |
| 06:00 | Entitlement for the service caller: scope `entity: UK01` | Phoenix: `entitlement.check` span |
| 06:01 | `load` calls `gl.variances(entity=UK01, period=2026-09)` → 412 lines, 23 material | `source_call` #1; Phoenix tool span with row count |
| 06:01 | `group` by account → 9 groups; 4 have priors from earlier months | `proposal_group` rows |
| 06:01 | `reason`: rule "FX revaluation accounts → standard comment" settles 2 groups; 7 go to the agent | Phoenix: `rule.evaluate` spans |
| 06:02 | Agent calls `gl.journal_lines` ×7, `budget.plan_lines` ×7, `core.similar_decisions` ×3 through the gateway | 17 `source_call` rows; 17 tool spans under the LLM span |
| 06:04 | Agent returns commentary per group; guards pass 6, escalate 1 (cited a figure no tool returned) | finding `escalated: UNGROUNDED_FIGURE` |
| 06:04 | `draft` + `validate`: every figure traced to a `source_call` result | Case detail: analysis + evidence links |
| 06:04 | Run pauses for review | Case list: "Awaiting sign-off" |
| 09:15 | Preparer opens the lane, asks "why is 6100 up 40%?" — answered from the evidence; approves 6 groups, rewrites the escalated one | `session_message`, `decision` rows |
| 11:30 | Reviewer (four-eyes) approves | `decision` row; run resumes |
| 11:30 | `record`: commentary published; decisions become priors for October | Knowledge graph priors |

**Audit, three months later:** "Who approved the commentary on account 6100
for UK01 in September, and what was it based on?" → one query on `decision`
gives the people and time; its `case_id` opens the Phoenix trace showing the
exact prompt, the skill version, each tool call and its result, and the
model's answer — §6, §7.

## 5. Each platform layer, and what a use case configures in it

### 5.1 Orchestration — LangGraph

- **Built per case** from the capability's pinned workflow version: the
  manifest's step list compiled into a LangGraph `StateGraph` (today's
  `build_graph`, made per capability).
- **Checkpointed in Postgres** — a run survives restarts, pauses for people
  (`interrupt_before=[review]`), and resumes in a fresh process (tested today).
- **Safe by construction:** step order is validated before a run starts;
  `validate`, `review`, `record` cannot be removed; the model never decides
  the next step.
- *Use case configures:* which core steps, their settings, where else to pause.

### 5.2 Knowledge graph

- Postgres `node`/`edge` tables with **bitemporal** reads (the graph as it
  stood on the business date) and pgvector for similarity — already built.
- **Namespaced per use case**; the core holds subjects (entities, books,
  accounts), their lineage, and **decisions as priors**.
- Populated from connectors (`load`/`enrich` can upsert subjects) and by
  `record` (decisions); read by `group` and the `core.similar_decisions` tool.
- *Use case configures:* which item fields are subjects, and lineage depth.

### 5.3 LLM connectivity

- One **reasoning port**, three adapters, already built: `none` (rules only,
  everything else escalates to people), `session_service` (the bank's agent
  harness, one session per case), `direct` (Claude via the Anthropic SDK, for
  development).
- The agent reaches data **only** through the MCP gateway with the case's
  per-session token — it cannot see tools the manifest did not grant, or data
  the case's caller is not entitled to.
- **Guards are code**: a verdict that cites no tool result, or breaks a rule,
  is escalated, never shown as a conclusion.
- Tokens, cost, latency per session are recorded (on `source_call` today) and
  traced in Phoenix.
- *Use case configures:* reasoner, skill text, allowed tools, output type
  (verdict / commentary / classification).

### 5.4 Generic UI

- Rendered from the manifest: `items.display` columns, case label,
  proposal groups with approve/reject, the agent chat, evidence (each
  `source_call` with the rows it returned), run trace, and a "View trace in
  Phoenix" link per case.
- Builder screens for owners; connector admin for the Helix team.
- *Use case configures:* labels, columns, which panels show.

### 5.5 MCP gateway and connectors

- One door to every bank system. Per call: tool allowed for this capability?
  caller entitled to this scope? scope argument clamped, timeout/retry,
  `source_call` row, OpenTelemetry span.
- *Helix team configures:* the connector. *Use case configures:* which of its
  tools to use.

## 6. Audit — the system of record (Postgres)

Audit answers **"who decided what, based on which data, under which rules"**,
and must be complete, immutable and queryable for years.

| Question | Answered by |
|---|---|
| Which rules and steps were in force? | `capability_version`, `workflow_version` (drafter, approver, timestamps) — the run is pinned to both |
| What data did the system and the agent see? | `source_call`: tool, arguments, caller scope, entitlement result, rows returned, latency |
| What did the agent conclude, and was it guarded? | `agent_session` (request, response), findings, evidence gaps |
| What was shown to the reviewer? | `analysis_version` |
| What did people say and decide? | `session_message`, `decision` (idempotency key, user, time, reason, items) |
| Could it be replayed? | LangGraph checkpoints: every step's state |
| Who changed a connector or capability? | `connector_version`, `capability_version` |

Rows are append-only; corrections are new rows. This is what an auditor
signs off on. It exists today for FOBO and becomes per-capability.

## 7. Observability — Arize Phoenix

Observability answers **"how did the run behave"**: the full sequence of
steps, prompts, model outputs, tool calls, timings, tokens and errors —
for debugging, model-risk review, quality evaluation and cost.

### 7.1 How it is wired

- **OpenTelemetry** in the backend, exporting OTLP to a **self-hosted
  Phoenix** (data stays inside the bank; port 6007, per the original design).
- **OpenInference instrumentors** — `openinference-instrumentation-langchain`
  (covers LangGraph runs and steps) and `openinference-instrumentation-anthropic`
  (the `direct` adapter's model calls) — give LLM-aware spans with no
  hand-written tracing.
- **Custom spans** where Helix owns the code: case open, entitlement check,
  MCP gateway call, rule evaluation, guard check, validate, review decision.
- **Session-service calls**: Helix propagates the trace context (W3C
  `traceparent`) to the bank's agent harness, so its spans join the same
  trace when the harness is instrumented; when it is not, Helix still records
  the request/response span and every MCP tool call the agent makes, because
  those pass through the gateway.

### 7.2 One case = one trace

```
case_run  UK01/2026-09  [helix.capability_id=fin.variance-commentary, case_id, workflow_version=2, manifest_version=3]
 ├─ entitlement.check                    roles, scopes, cache hit
 ├─ step.load
 │   └─ mcp.call gl.variances            connector=gl, rows=412, scope=UK01, 180 ms
 ├─ step.group                           groups=9, priors=4
 ├─ step.reason
 │   ├─ rule.evaluate ×9                 settled=2
 │   ├─ llm.session  (agent)             model, tokens in/out, cost, skill_version
 │   │   ├─ mcp.call gl.journal_lines ×7
 │   │   ├─ mcp.call budget.plan_lines ×7
 │   │   └─ mcp.call core.similar_decisions ×3
 │   └─ guard.check ×7                   passed=6, escalated=1 (UNGROUNDED_FIGURE)
 ├─ step.draft
 ├─ step.validate                        figures=31, traced=31
 └─ review.pause  … resumed by decision (separate linked trace: who, when)
```

**Standard attributes on every span:** `helix.capability_id`,
`helix.case_id`, `helix.workflow_version`, `helix.manifest_version`,
`helix.user` (the caller, or the service identity for scheduled runs), plus
`helix.connector_id` / `helix.tool` on gateway spans. One **Phoenix project
per capability**, so each use-case team sees only its own traces.

### 7.3 What teams use Phoenix for

| Need | Phoenix feature |
|---|---|
| "Why did this case escalate?" | Open the case's trace from the UI link |
| Model quality over time | **Evaluations** on drafts: groundedness (every figure cited), relevance; run on every draft or sampled |
| Regression before changing a skill or model | **Datasets** built from approved decisions; replay the new skill against them and compare (experiments) |
| Cost and latency per use case | Token / latency dashboards per project |
| Prompt and skill versions | `skill_version`, `prompt_version` attributes; filter traces by version |

### 7.4 Audit vs observability — why both

| | Audit (Postgres) | Observability (Phoenix) |
|---|---|---|
| Purpose | Evidence for decisions | Behaviour of the system |
| Audience | Auditors, controllers, model risk | Helix team, use-case owners, model risk |
| Completeness | Mandatory; a write failure fails the step | Best effort; an export failure never fails a run |
| Retention | Years, per records policy | Shorter, per Phoenix storage policy |
| Content | Decisions, data references, versions | Full prompts, outputs, timings, tokens |
| Joined by | `case_id`, and the trace id stored on `case_run` | `case_id` span attribute |

**Sensitive data.** Prompts and tool results can contain client data, so
Phoenix is self-hosted, access is gated by the same entitlement roles, and
each connector's `classification` decides whether tool payloads are exported
in full, masked, or as row counts only.

## 8. What exists today, and what each phase adds

| Piece | Today (FOBO) | Delivered in (design §14) |
|---|---|---|
| LangGraph orchestration, checkpoints, pause/resume | ✓ | per-capability graphs: Phase 1 |
| Versioned workflows, four-eyes | ✓ | per capability: Phase 1 |
| Knowledge graph, bitemporal, priors | ✓ (FOBO ontology) | namespaces: Phase 4 |
| Reasoning port: none / session service / direct | ✓ | per-capability skill and tools: Phase 4 |
| MCP server, per-session token, `source_call` audit | ✓ (FOBO tools) | gateway + connectors: Phase 3 |
| Central entitlement | — (dev "Act as" only) | Phase 2 |
| Generic UI, capability builder, connector admin | — (FOBO console) | Phase 5 |
| **Phoenix observability** | — (planned in the first design, not built) | **new Phase 1a** — small, and useful immediately: it shows FOBO's behaviour before and after the refactor |
