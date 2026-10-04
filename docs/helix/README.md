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

FOBO's behaviour on Helix — its playbook as configuration of the CATS vs MOTIF rec group:
[`fobo-on-helix.md`](fobo-on-helix.md).

What Helix inherits from the office agent platform (MCP, plugins, RAG), what
is still missing, and the order to add it:
[`office-platform-and-roadmap.md`](office-platform-and-roadmap.md).

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

After pulling a change to `config/helix/` into an existing database: `python -m helix.config_sync`
drafts the changed capabilities and groups for their owners to approve (Authoring, or the
group's page). Case runs happen in the background (`HELIX_RUN_MODE=background`, the default);
a restarted server finishes the runs it left.

Optional, to see traces: `pip install arize-phoenix && phoenix serve` (port 6006), then start the API with
`PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006` and `pip install -e ".[phoenix]"`.

Users (top-right switcher, development only):

| User | Is |
|---|---|
| `alice` | Finance preparer, UK01 only |
| `bob` | Finance reviewer + capability owner, all entities — releases write-backs |
| `carol` | Finance capability owner — authors and changes capabilities, cannot sign off |
| `dan`, `erin` | Cash operations — the cash rec group (erin also owns the recon capability) |
| `frank` | FOBO controller, all books — owner of the CATS vs MOTIF rec group |
| `gina` | FOBO controller, PRIME-MB-01 only — second owner of CATS vs MOTIF |
| `viewer` | No roles — sees nothing |

A full pass: as **alice**, Capabilities → *P&L variance commentary* → open lane UK01 / 2026-09 →
approve each proposal. As **bob**, the lane is in your Inbox as *Release* → release the
write-back → it is published. As **carol**, Authoring → paste a BRD → draft → submit; as
**bob**, approve the draft → a new capability is live. As **frank**, Capabilities →
*Reconciliation investigation* → Groups shows the two rec groups; open a CATS vs MOTIF rec run for
PRIME-MB-01 / 2026-08-03 — each break shows FOBO's six cause checks, its category, side, verdict
and owning team; a POST is flagged "requires controller confirmation" while the materiality
threshold is unset; set the threshold in the group's YAML and have **gina** approve it. In any case,
*Ask about this case* answers from the case's data, and *Run history* shows each step.
**Operations** is the run-the-bank view.

Tests: `cd apps/backend && .venv/bin/python -m pytest -q tests/helix` (135; the whole backend
including FOBO: 610) · `cd apps/web && npm test` (60, including aria-ai's own tests for the components reused from it) ·
`npm run typecheck`.

## 2. How it is built

```
apps/web/                         the console — aria-ai's UI shell (React, TS, Tailwind, TanStack Query)
  Overview · Inbox · Capabilities · Case workspace (3-pane) · Operations · Authoring · Audit · Connectors
  theme/barclays.js  Barclays light (blue on white) and Barclays dark — CSS variables; sun/moon toggle
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
  stub_connectors/  GL, budget, bank, ledger, reporting (write), CATS, MOTIF — real MCP servers
  mcp_services/     documents: read PDF / Excel, write PDF reports (write) — a real service
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

## 2a. Team groups — one capability, configured by each team

A capability is the shared use case; a **team group** is one team's way of running it — FOBO's rec
groups, generalised. The capability's owners list what may vary (`configurable` in the manifest);
each group's owners set those values in `config/helix/groups/<capability>/<group>.yaml` (version 1)
and then through the console (draft → another group owner approves). A value set at a configurable
path replaces the default there; workflow, gates, write-back and ownership always stay with the
capability.

`recon.investigation` has two rec groups on the same engine:

| | CATS vs MOTIF (FOBO) | Cash — bank vs ledger |
|---|---|---|
| Case | book × COB | entity × date |
| Sources | `cats.positions` vs `motif.positions` | `bank.statement` vs `ledger.postings` |
| Rules / limits | auto-adjust ≤ 250 USD | write-off ≤ 100 GBP |
| Model tools | `motif.booking_events` | `ledger.counterparty_history` |
| Reviewers | `FOBO_CONTROLLER` | `CASH_OPS` |

A case of a grouped capability runs under one group and keeps the exact merged manifest it ran on,
so a later change to the group never alters a past run. Each group's people see only their cases.

## 2b. aria-ai reuse

[`aria-ai-reuse-map.md`](aria-ai-reuse-map.md) maps every aria-ai page and component to users,
developers and run-the-bank, with what is reused, adapted, planned or replaced, and the waves.

## 2c. Documents — PDF and Excel in, PDF reports out

`documents` is a connector Helix provides itself (`helix/mcp_services/documents.py`):
`list_documents`, `read_pdf`, `read_workbook` (read) and `render_pdf_report` (write — the
publish step only, after a second person releases the case). Files are kept per entity:
`HELIX_DOCUMENTS_DIR/<entity>/` to read, `HELIX_REPORTS_DIR/<entity>/` for reports.

**Report validation** uses it: the management report workbook is matched to the ledger,
differences are explained and signed off, and on release one PDF validation report is written
(`publish.per: case`) and offered in the case workspace. Try it as alice (UK01):
entity `UK01`, period `2026-09`, report `mgmt-report-2026-09.xlsx`; release as bob.
Sample documents: `python scripts/make_helix_documents.py`.

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
(`HELIX_ENTITLEMENT_ADAPTER`). Cached `HELIX_ENTITLEMENT_TTL_SECONDS` (60); errors fail closed.
With `HELIX_ENTITLEMENT_WEBHOOK_SECRET` set, the entitlements service can call
`POST /api/entitlements/invalidate` (`{"user_id": …}` or `{}` for everyone, secret in
`X-Helix-Webhook-Secret`) so a revocation applies at once. The user switcher disappears when
`HELIX_ENTITLEMENT_URL` is set.

Identity comes from `HELIX_IDENTITY_HEADER`, set by the SSO proxy. Set
`HELIX_TRUSTED_PROXY_SECRET` too, and have the proxy add it to every request
(`X-Helix-Proxy-Secret`, or `HELIX_PROXY_SECRET_HEADER`): requests without it are refused, so the
identity header cannot be set by anyone who merely reaches the server. `/health` stays open.

### 3.4 Connectors

Per connector in `config/helix/connectors.yaml`: `transport: http`, `url`, `headers_env`
(header → env var with its value), and the tool allow-list. For each tool: `scope` (the argument
carrying the data scope) and `access: read | write`. Write tools are never offered to the model and
run only in `publish`, after release; `idempotency_arg` names the argument that carries Helix's
idempotency key (case:group), so a retried write is the same write. A full office version is in
`config/helix/connectors.office.example.yaml` — office RAG and data-explorer servers are onboarded
the same way. Results may be MCP structured content or JSON text; steps read
a list of records under `rows`.

### 3.5 Data protection

`config/helix/governance.yaml`: `mask` fields never reach the model, traces or the audit copy;
`pseudonymize` fields reach the model as per-case tokens (`«COUNTERPARTY:QXKD»`) that it can still
pass to tools — the gateway restores real values for the connector — and reviewers see real values.
Set `HELIX_PSEUDONYM_KEY` (a secret) in the office. `trace_payloads: masked` hides auto-instrumented
payloads; Helix's own spans carry the model's view only.

### 3.6 Running it

| | |
|---|---|
| Case runs | off the request path (`helix/runner.py`); one run per case across instances (advisory lock); startup finishes runs left `running`; a pause is crossed only by its input (decisions, release) |
| Re-runs | a failed or escalated case → *Run again* → attempt 2 on today's configuration; earlier attempts kept |
| Write-backs | idempotency key per write; a part-failed publish → *Retry write-back* sends only what did not land |
| Reports | PDF reports in the shared database (`HELIX_REPORTS_STORE=db`), served to anyone who can see the case |
| Retention | `retention.days` per capability; `python -m helix.retention [--dry-run]` (schedule it daily); owners put a case on legal hold with a reason |
| Config changes | `python -m helix.config_sync` → drafts → owners approve (four-eyes) |
| Smoke test | `scripts/helix_office_smoke.py --user <id> [--case <cap> --group <g> --key k=v …]` — database, entitlements, every connector, LLM, Phoenix, and one real case |

## 4. Onboarding a capability

In the console: **Authoring** → paste the BRD → *Draft capability*. The model drafts a manifest
from the onboarded tools; the validator lists anything to fix; edit the YAML; *Submit for approval*;
another owner approves it under *Drafts awaiting approval*. Or write the YAML directly in
`config/helix/capabilities/` (seeds version 1 on a fresh database).

The built-in capabilities — **P&L variance commentary** (with write-back), **Reconciliation
investigation** (rec groups: cash bank-vs-ledger, and CATS vs MOTIF running FOBO's playbook) and
**Report validation** (Excel vs ledger, PDF report) — contain no code.

## 5. Next

In the office: run the smoke test with the Agent SDK, Phoenix, entitlements and real connectors.
Then, from [`office-platform-and-roadmap.md`](office-platform-and-roadmap.md): eval sets and
shadow runs in Phoenix · scheduled and event-opened cases · evidence upload into a case ·
notifications · parallel reasoning across groups · FOBO's validation tests (FO-1…BO-6) as
structured checks · moving FOBO's users onto the platform.
