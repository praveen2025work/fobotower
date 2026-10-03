# Helix

One platform that accounting groups onboard their AI-assisted work into as
**configuration**: reconciliations, variance commentary, reviews. The Helix
team onboards connectors (bank systems as MCP servers); each capability is a
versioned manifest over them, run by LangGraph, governed end to end, and
worked in one console.

aria-ai (EAIP) has been pivoted into Helix: its UI shell, its governance
(masking, approval-gated actions) and its BRD-to-pack authoring live here
now — see [`aria-ai-assessment.md`](aria-ai-assessment.md) for what was
taken and why.

Design: [`../superpowers/specs/2026-10-03-helix-capability-platform-design.md`](../superpowers/specs/2026-10-03-helix-capability-platform-design.md) ·
walkthrough: [`…-helix-how-a-use-case-works.md`](../superpowers/specs/2026-10-03-helix-how-a-use-case-works.md)

## What runs where

| | Here (outside the office) | In the office — configure, don't code |
|---|---|---|
| LLM | `stub` — deterministic, calls tools through the gateway | `HELIX_LLM_ADAPTER=agent_sdk` — the **Claude Agent SDK** adapter (§3.1) |
| Observability | local Phoenix, or no-op | your **Phoenix**: `PHOENIX_COLLECTOR_ENDPOINT`, or `HELIX_TRACING_SETUP` for your own wrapper (§3.2) |
| Entitlement | `config/helix/dev-users.yaml` | `HELIX_ENTITLEMENT_URL` (or `HELIX_ENTITLEMENT_ADAPTER`) (§3.3) |
| Identity | the console's user switcher | `HELIX_IDENTITY_HEADER` — the header your SSO proxy sets |
| Connectors | in-process stub MCP servers | `transport: http` + `url` in `config/helix/connectors.yaml` (§3.4) |
| Data protection | `config/helix/governance.yaml` | same file, your field names (§3.5) |

## 1. Run it

```bash
cd apps/backend && .venv/bin/alembic upgrade head
.venv/bin/uvicorn helix.web.main:app --port 8300 --reload        # the Helix API
```

```bash
cd apps/web && npm install && npm run dev                          # http://localhost:5180
```

Optional, to see traces: `pip install arize-phoenix && phoenix serve` (port 6006), then start the API with
`PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006` and `pip install -e ".[phoenix]"`.

Users (top-right switcher, development only):

| User | Is |
|---|---|
| `alice` | Finance preparer, UK01 only |
| `bob` | Finance reviewer + capability owner, all entities — releases write-backs |
| `carol` | Finance capability owner — authors and changes capabilities, cannot sign off |
| `dan`, `erin` | Cash operations — the bank-vs-ledger reconciliation |
| `viewer` | No roles — sees nothing |

A full pass: as **alice**, Capabilities → *P&L variance commentary* → open lane UK01 / 2026-09 →
approve each proposal. As **bob**, the lane is in your Inbox as *Release* → release the
write-back → it is published. As **carol**, Authoring → paste a BRD → draft → submit; as
**bob**, approve the draft → a new capability is live.

Tests: `cd apps/backend && .venv/bin/python -m pytest -q tests/helix` (73) ·
`cd apps/web && npm test` (10) · `npm run typecheck`.

## 2. How it is built

```
apps/web/                         the console — aria-ai's UI shell (React, TS, Tailwind, TanStack Query)
  Overview · Inbox · Capabilities · Case workspace (3-pane) · Authoring · Audit · Connectors
apps/backend/helix/
  web/main.py       FastAPI :8300
  manifest.py       capability manifest schema + validator (steps, gates, tools, expressions)
  capabilities.py   versions; owner drafts → another owner approves; new capabilities from drafts
  authoring.py      BRD → draft manifest (Agent SDK or template), judged by the validator
  workflow.py       core step registry + gates → a checkpointed LangGraph graph per case
  steps.py          load · match · compare · group · reason · draft · validate · review · record · publish
  gateway.py        the MCP gateway: allow-list, read/write, data scope, protection, audit, span
  governance.py     mask + reversible pseudonyms between bank data and the model
  llm.py            the reasoning port: none · stub · agent_sdk · "module:attr"
  llm_agent_sdk.py  the Claude Agent SDK adapter
  entitlement.py    central entitlements client, cache, dev stub — fails closed
  knowledge.py      knowledge graph: approved decisions → next run's priors (bitemporal)
  observability.py  OpenTelemetry + OpenInference conventions; Phoenix registration
  views.py          overview / inbox / audit across capabilities, filtered per caller
  stub_connectors/  GL, budget, bank, ledger, reporting (write) — real MCP servers
config/helix/
  connectors.yaml   onboarded connectors, tool allow-list, read/write, data scope   (Helix team)
  governance.yaml   mask / pseudonymize fields, trace payload policy               (Helix team)
  capabilities/     one manifest per capability                                    (owners)
  dev-users.yaml    development stand-in for central entitlements
```

One case, end to end:

```
open (entitlement, data scope) ─▶ LangGraph run pinned to the manifest version   ── one Phoenix trace
  load/match ── gateway ──▶ connector                    every call → helix_tool_call (audit)
  compare · group (+ priors from the knowledge graph)
  reason: rules first; the rest → Agent SDK with ONLY the capability's read tools,
          served in-process, each call back through the gateway; protected data only
  draft · validate — every figure in a proposal must appear in data the run read
  ── pause ── reviewers approve / reject per group (idempotent)
  record — approved explanations become priors
  ── pause ── a second person releases the write-back (four-eyes)
  publish — write tool via the gateway, only now
```

## 3. Office integration

### 3.1 LLM — Claude Agent SDK

`HELIX_LLM_ADAPTER=agent_sdk` (install `pip install -e ".[agent-sdk]"`). Per proposal group,
`helix/llm_agent_sdk.py` runs one `claude_agent_sdk.query()`:

| Option | Value | Why |
|---|---|---|
| `system_prompt` | the capability's `reasoning.skill` + Helix output rules | the use case's instructions, the platform's rules |
| `tools` | `[]` | no built-in Claude Code tools (no Bash, Read, …) |
| `mcp_servers` | one in-process SDK MCP server, `helix` | its tools are exactly the capability's `reasoning.tools`; each handler calls the Helix gateway |
| `strict_mcp_config` | `True` | no other MCP servers load |
| `allowed_tools` | `mcp__helix__<tool>` | those tools run without a permission prompt |
| `permission_mode` | `dontAsk` | headless: anything else is denied |
| `output_format` | JSON schema `{status, comment, reason}` | a structured, checkable answer |
| `model` / `effort` / `max_turns` / `max_budget_usd` | `HELIX_LLM_MODEL` (default `claude-opus-5-5`), `HELIX_LLM_EFFORT` (high), `HELIX_LLM_MAX_TURNS` (12), `HELIX_LLM_MAX_BUDGET_USD` | per deployment |

Tokens, cost, turns and session id are kept on the finding and on the span.

**If your office wraps the Agent SDK** (gateway URL, credentials, model routing), change only
`ClaudeAgentSdkAdapter._run` (the `query()` call) or point `HELIX_LLM_ADAPTER` at your own class
with the same contract: `name` and `async reason(request, tools) -> ReasonResult`. Keep tool calls
going through `tools` — that is what lets Helix validate every figure the model states.

Authoring (§4) uses the same adapter choice, with no tools and structured output `{yaml, assumptions}`.

### 3.2 Observability — Phoenix

- `PHOENIX_COLLECTOR_ENDPOINT=https://phoenix.internal` (+ `PHOENIX_PROJECT_NAME`, default `helix`)
  and `pip install -e ".[phoenix]"`: Helix calls `phoenix.otel.register(..., batch=True,
  auto_instrument=True)`, which also instruments the **Claude Agent SDK** and **LangGraph**
  (`openinference-instrumentation-claude-agent-sdk`, `-langchain`).
- Or `HELIX_TRACING_SETUP=your_pkg.tracing:setup` if your Phoenix connector is a wrapper.
- One case run is one trace; review decisions and releases are their own traces, linked.
  `session.id` = case id (Phoenix's Sessions view shows a case's whole life), `user.id` = caller,
  span kinds CHAIN (case, steps), TOOL (gateway calls), AGENT (the Agent SDK).
- Console link: `VITE_HELIX_TRACE_URL=https://phoenix.internal/projects/<project>/traces/{traceId}`.
- Verified here against Phoenix 20.19.

### 3.3 Entitlement and identity

`GET {HELIX_ENTITLEMENT_URL}/users/{user}/entitlements?app=helix` →
`{"roles": [...], "data_scopes": {"entity": ["UK01"]}}`; a different shape → an adapter
(`HELIX_ENTITLEMENT_ADAPTER`). Cached `HELIX_ENTITLEMENT_TTL_SECONDS` (300); errors fail closed.
The user switcher disappears when `HELIX_ENTITLEMENT_URL` is set.

### 3.4 Connectors

Per connector in `config/helix/connectors.yaml`: `transport: http`, `url`, `headers_env`
(header → env var with its value), and the tool allow-list. For each tool: `scope` (the argument
carrying the data scope) and `access: read | write`. Write tools are never offered to the model and
run only in `publish`, after release. Results may be MCP structured content or JSON text; steps read
a list of records under `rows`.

### 3.5 Data protection

`config/helix/governance.yaml`: `mask` fields never reach the model, traces or the audit copy;
`pseudonymize` fields reach the model as per-case tokens (`«COUNTERPARTY:QXKD»`) that it can still
pass to tools — the gateway restores real values for the connector — and reviewers see real values.
Set `HELIX_PSEUDONYM_KEY` (a secret) in the office. `trace_payloads: masked` hides auto-instrumented
payloads; Helix's own spans carry the model's view only.

## 4. Onboarding a capability

In the console: **Authoring** → paste the BRD → *Draft capability*. The model drafts a manifest
from the onboarded tools; the validator lists anything to fix; edit the YAML; *Submit for approval*;
another owner approves it under *Drafts awaiting approval*. Or write the YAML directly in
`config/helix/capabilities/` (seeds version 1 on a fresh database).

The two built-in capabilities — **P&L variance commentary** (with write-back) and **Cash — bank vs
ledger** — contain no code.

## 5. Next

Similarity priors over pgvector (aria-ai's precedent memory) · evals from approved decisions,
scored in Phoenix · parallel reasoning across groups (LangGraph `Send`) · scheduled and
event-opened cases · capability builder as a form · moving FOBO onto the platform and retiring the
old consoles. See the design spec §14.
