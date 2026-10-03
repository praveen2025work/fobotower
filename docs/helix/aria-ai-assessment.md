# aria-ai (EAIP) — assessment for Helix

**Date:** 2026-10-03 · **Repo:** `praveen2025work/aria-ai` @ `e74b232` (last commit 2026-06-17)
**Question:** can anything in aria-ai be used for Helix, or should aria-ai itself become Helix?

## 1. Verdict

**Keep Helix (this repo) as the platform. Harvest five pieces from aria-ai's
Python half (`eap-core`). Do not pivot aria-ai into Helix.**

aria-ai is broad and largely working, but it is an *agent* platform (chat
first, LLM specialists fanned out in parallel) built on four stacks with two
competing engines. Helix is a *case/workflow* platform (rules first, the
model only for what rules cannot settle, every figure validated, people sign
off) on one stack that matches the office (Python, LangGraph, Postgres,
Phoenix, real MCP connectors). The parts of aria-ai that Helix lacks sit in
`eap-core`, which is already Python + FastAPI + SQLAlchemy + Postgres — they
port in, they don't need a pivot.

## 2. What was validated

Run in this session on a fresh clone:

| Component | Stack | Result |
|---|---|---|
| `enterprise-agent-platform` (eap-core) | Python 3.12 / FastAPI / LangGraph / LiteLLM | **652 passed**, 7 failed, 2 skipped. The 7 are one test (`test_compose_profiles`) needing a local `.env`; environment, not code |
| `agent-runner` | Node / TypeScript / Anthropic Agent SDK | **230 / 230 passed** |
| `platform-ui` | React 18 / Vite / Tailwind | **494 / 494 passed** |
| `platform-api` | Java 21 / Spring Boot / Oracle | **566 / 569 passed**, 0 failures; the 3 errors are Testcontainers tests that need Docker for Oracle XE (none here) |

Install problems found (fix before anyone else clones it):

1. `eap-core` pins `litellm==1.49.1`, which the package index no longer
   serves — a fresh `pip install` fails. It installs and passes with
   `litellm 1.59.x`.
2. Two eap-core test modules import `pythonjsonlogger`, which eap-core does not
   declare (it comes from `mcp-adapters/requirements.txt`).

Total: **1,942 tests pass**; every failure or error traced to the environment (no `.env`, no Docker), none to code.

## 3. What aria-ai is

The repo's own `docs/GAP_ANALYSIS.md` says it plainly: **"there are TWO
platforms in this repo."**

| | Legacy "ARIA" | eap-core |
|---|---|---|
| Stack | Java 21 / Spring Boot / **Oracle** / Redis, plus the Node agent-runner | Python / FastAPI / **Postgres + pgvector** |
| Orchestrator | durable DAG engine (leases, heartbeats, timers, versioned workflows) | parallel specialist fan-out (`engine/orchestrator.py`) |
| Governance | hook engine, audit, approvals | ported: masking → audit → approval on every tool call |
| Tracing | OpenTelemetry → Phoenix (agent-runner) | Langfuse port; Phoenix is **slated for removal** once Langfuse is the single tracer (`notes/2026-06-03-phoenix-removal.md`, deferred) |
| Status | live path | default lean of the open "engine convergence" decision (D7) — never closed |

Around them: 18 adapter services, 7 industry packs (finance, P&L, healthcare,
HR, marketing, operations, flood claims; 7 agents each), a 40-page UI (about
10 of them product-marketing pages: pricing, solutions, promote), k8s
manifests, Prometheus/Grafana.

## 4. Fit against what Helix needs

| Helix requirement (agreed design) | aria-ai | Fit |
|---|---|---|
| Helix team supplies **MCP connectors**; office already has them | Its "MCP adapters" are **REST services** (`POST /tools/{name}`, tools discovered from `/openapi.json`) — not the MCP protocol. Neither eap-core nor agent-runner uses an MCP SDK; both call the adapters over plain HTTP | ✗ — they cannot plug into office MCP connectors, nor the office connectors into it, without a translation layer |
| **Phoenix** observability | agent-runner traces to Phoenix today; the plan is Langfuse as the single tracer and Phoenix dropped | ✗ the direction conflicts with the office choice |
| One stack the team can own | Java + Oracle + Node + Python; two engines, convergence undecided | ✗ |
| Deterministic first, LLM only for the rest; every figure validated | Agents "narrate, never invent figures"; a per-agent `validation_contract` flag; no per-figure grounding check against what tools returned | partial |
| Human sign-off per group, decisions feed the next run | Approval gates on write tools; precedent memory | partial — different shape, good parts |
| Capability = config only | Pack = `pack.yaml` (agents, plugins, policies); `brd_to_pack.py` drafts one from a BRD | ✓ strong idea |
| Central entitlement, data-level scope | Role checks; SSO design docs; no data-scope enforcement on tool calls | partial |
| Masking of sensitive fields before the model | **Yes** — field masking in `HookEngine.pre_tool`, before prompt and audit | ✓ Helix lacks this |
| Approval-gated **write-back** tools | **Yes** — approval queue, pause/resume | ✓ Helix lacks this |
| Evaluations | **Yes** — framework, judges, PII-free corpus check, per-pack eval cases | ✓ Helix lacks this |

## 5. What to take into Helix

In priority order. Each is small, Python, and already tested in eap-core.

| # | Take | From (eap-core) | Into Helix as | Why |
|---|---|---|---|---|
| 1 | **Field masking before the model and the audit** | `governance/masking.py`, the mask step of `governance/hooks.py` | a `mask` policy per connector tool in `connectors.yaml`; applied in `gateway.call` before results reach the LLM adapter, the audit row and the span | Bank data in prompts and traces is the first question model-risk will ask |
| 2 | **BRD → manifest drafting** | `authoring/brd_to_pack.py` (one no-tools LLM turn → YAML → same validator; errors returned, never raised; human gate before load) | `POST /api/capabilities/draft-from-brd` → a **draft** `capability_version` that owners approve | Makes "seamless onboarding" literal: a business team pastes requirements, gets a validated draft manifest |
| 3 | **Approval-gated write tools** | `governance/approvals.py`, `engine/run_resume.py` | a `writes:` section on connector tools + a `publish` step after `record` that pauses for a second approver | Write-back (e.g. post a journal, publish commentary) is open question 2 in the design |
| 4 | **Evals** | `evals/framework.py`, `evals/judges.py`, `evals/pii.py`, pack `evals/` cases | `config/helix/capabilities/<id>.evals.yaml` + a runner; datasets from approved decisions | Regression-test a skill or model change before owners approve it |
| 5 | **Similarity priors** | `memory/precedent.py`, `ports/vector.py` | an optional pgvector search behind `knowledge.similar_decisions` | Today priors match the exact group key; similarity finds "like" cases |

Also worth reading, not porting yet: the Java `DagExecutor` (leases,
heartbeats, durable timers) as the reference when Helix adds scheduled and
event-opened cases; `platform-ui` pages `PackAuthoring`, `Approvals`, `Audit`,
`RunConsole` as UX references for the capability builder; the adapter
**backends** (`fobo-backend`, `recon-engine-backend`, `pnl-lineage-backend`) as
richer stub data — wrapped as real MCP servers like
`helix/stub_connectors/finance.py`.

## 6. What not to take

- The agent fan-out as Helix's core loop — Helix is case-centric; an agent is
  what the `reason` step calls, through `HELIX_LLM_ADAPTER`.
- The REST "MCP" adapter protocol — Helix speaks real MCP.
- Langfuse — the office standard is Phoenix.
- Java/Oracle control plane, Node agent-runner — a second and third stack.
- The marketing pages and six demo industries.

## 7. If the team still wants one product, not two

Then the direction is **aria-ai's eap-core moves onto Helix**, not the
reverse: Helix's case model, gateway and gates stay; eap-core's masking,
approvals, authoring, evals and precedent memory come in (§5); aria-ai's
specialist agents can be offered as one implementation of
`HELIX_LLM_ADAPTER`. The Java/Oracle platform and agent-runner are retired
rather than converged.
