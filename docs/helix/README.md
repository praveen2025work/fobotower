# Helix — platform skeleton

The runnable skeleton of the design in
[`docs/superpowers/specs/2026-10-03-helix-capability-platform-design.md`](../superpowers/specs/2026-10-03-helix-capability-platform-design.md)
and [`…-helix-how-a-use-case-works.md`](../superpowers/specs/2026-10-03-helix-how-a-use-case-works.md).

Everything is real and runs end to end. The parts that live in the office —
the LLM, Phoenix, the central entitlements service, SSO and the bank's MCP
connectors — sit behind configuration. Here they are stubs; in the office you
point them at the real thing. **No Helix code changes.**

| | Here (stub) | In the office (configure) |
|---|---|---|
| LLM | `StubLlm` — deterministic, calls tools through the gateway | `HELIX_LLM_ADAPTER=your_pkg.llm:Adapter` (§3.1) |
| Tracing | no-op (OpenTelemetry API, no provider) | `PHOENIX_COLLECTOR_ENDPOINT=…` or `HELIX_TRACING_SETUP=your_pkg.tracing:setup` (§3.2) |
| Entitlement | `config/helix/dev-users.yaml` | `HELIX_ENTITLEMENT_URL=…` or `HELIX_ENTITLEMENT_ADAPTER=…` (§3.3) |
| Identity | `X-Helix-User` from the console's user switcher | `HELIX_IDENTITY_HEADER=X-Remote-User` (your SSO proxy) |
| Connectors | in-process MCP servers (`helix/stub_connectors/finance.py`) | `transport: http` + `url` in `config/helix/connectors.yaml` (§3.4) |

FOBO is untouched and runs beside it (same database, its own API on :8100).
Nothing in `helix/` imports `fobo/`, and a test enforces that.

## 1. Run it

```bash
docker compose up -d postgres              # or the local Postgres the web-session hook starts
cd apps/backend && .venv/bin/alembic upgrade head
.venv/bin/uvicorn helix.web.main:app --port 8300 --reload
```

```bash
cd apps/console && npm run dev             # then open http://localhost:3100/helix
```

Pick a user in the header (they come from `dev-users.yaml`):

| User | Can |
|---|---|
| `alice` | Finance preparer, entity UK01 only — open and sign off variance lanes |
| `bob` | Finance reviewer and capability owner, all entities |
| `carol` | Owner of the variance capability (can change it, cannot sign off cases) |
| `dan`, `erin` | Cash operations — the bank-vs-ledger reconciliation |
| `viewer` | No roles — sees nothing |

Try: as `alice`, open lane `UK01` / `2026-09`, approve every proposal; then
open `2026-10` and see September's approved explanations as priors. Try
`US01` as alice — refused by entitlement.

Tests: `cd apps/backend && .venv/bin/python -m pytest -q tests/helix`
(49 tests) and `cd apps/console && npx vitest run src/helix`.

## 2. How it is built

```
apps/backend/helix/
  config.py          every setting and plug point, from the environment
  manifest.py        the capability manifest schema + validator
  capabilities.py    manifest versions; owner draft → another owner approves
  workflow.py        core step registry, gate rules, manifest → LangGraph
  steps.py           load · match · compare · group · reason · draft · validate · review · record
  rules.py           safe expressions for in_scope / rules (no eval)
  gateway.py         the MCP gateway: allow-list, data scope, audit row, span
  llm.py             LLM port: none · stub · your adapter
  entitlement.py     central entitlement client, cache, dev stub — fails closed
  knowledge.py       knowledge graph: decisions → next run's priors (bitemporal)
  observability.py   OpenTelemetry spans; Phoenix or your setup, optional
  cases.py           open → run → review pause → decide → resume → record
  models.py          helix_* tables (the audit record)
  web/main.py        FastAPI, :8300
  stub_connectors/   stand-in GL, budget, bank, ledger MCP servers
config/helix/
  connectors.yaml    onboarded connectors and their tool allow-list   (Helix team)
  capabilities/*.yaml one manifest per capability                     (capability owners)
  dev-users.yaml     development stand-in for central entitlements
apps/console/src/helix/   the generic UI, rendered from the manifest  (/helix)
```

A run, per case:

```
open (entitlement + data scope) ─▶ LangGraph, pinned to the manifest version
  load/match ── gateway ──▶ connector          every call → helix_tool_call
  compare · group (+ priors from the knowledge graph)
  reason: rules first; the rest → LLM adapter, whose tool calls go through the same gateway
  draft · validate (every figure must appear in data the run read, else escalated)
  ── pause ── people approve / reject per group (idempotent, review roles only)
  record: approved explanations → knowledge graph → next run's priors
```

## 3. Plugging in the office services

### 3.1 LLM

Write one class; point `HELIX_LLM_ADAPTER` at it. It receives the request and
a `tools` function. **Call tools only through `tools`** — that is how the
gateway enforces the allow-list and data scope and records what the model
saw, which is what `validate` checks the model's figures against.

```python
# your_pkg/llm.py
from helix.llm import ReasonRequest, ReasonResult

class Adapter:
    name = "office-llm"

    def __init__(self):
        self.client = make_your_llm_connector_client()      # your existing connector

    async def reason(self, request: ReasonRequest, tools) -> ReasonResult:
        # request.skill         the capability's instructions (system prompt)
        # request.group         {label, group_key, items, priors, total, count}
        # request.allowed_tools ["gl.journal_lines", …] — expose these as model tools
        # tools(name, args)     executes one through the Helix MCP gateway → dict
        answer = await run_tool_loop(self.client, request, tools)   # your loop
        return ReasonResult(status="proposed", comment=answer.text,
                            model=answer.model, usage={"input_tokens": …, "output_tokens": …})
```

`HELIX_LLM_ADAPTER=your_pkg.llm:Adapter`. A raised exception, a refused tool,
or a figure no tool returned all become an escalation for a person — never a
silent conclusion (`tests/helix/test_reasoning.py`).

### 3.2 Phoenix

Helix emits OpenTelemetry spans (`case.run`, `step.*`, `reason.group`,
`mcp.call`, `review.decision`) with `helix.case_id`, `helix.capability_id`,
`helix.connector_id`, `helix.tool`, `helix.user`, … One case is one trace; its
id is stored on `helix_case.trace_id`. Choose one:

- `pip install -e ".[phoenix]"` and `PHOENIX_COLLECTOR_ENDPOINT=https://phoenix.internal` —
  Helix calls `phoenix.otel.register(project_name="helix", auto_instrument=True)`,
  which also instruments LangGraph and LLM SDKs.
- `HELIX_TRACING_SETUP=your_pkg.tracing:setup` — your function installs
  whatever tracer provider your office connector uses.

For the console's trace link set
`NEXT_PUBLIC_HELIX_TRACE_URL=https://phoenix.internal/projects/<project>/traces/{traceId}`.
A tracing failure never fails a run.

### 3.3 Entitlement and identity

`HELIX_ENTITLEMENT_URL=https://entitlements.internal/api` — Helix calls
`GET {url}/users/{user}/entitlements?app=helix` and expects
`{"roles": [...], "data_scopes": {"entity": ["UK01", ...]}}`. If your
service's shape differs, write an adapter (`async get(user_id) -> Caller`)
and set `HELIX_ENTITLEMENT_ADAPTER=your_pkg.ent:Adapter`. Answers are cached
`HELIX_ENTITLEMENT_TTL_SECONDS` (300); unknown user, error or outage → 403.

`HELIX_IDENTITY_HEADER` names the header your SSO proxy sets with the user id.
In the office, do not expose `/api/dev/users`'s switcher — it is empty when
`HELIX_ENTITLEMENT_URL` is set.

### 3.4 Connectors

Replace a stub entry in `config/helix/connectors.yaml`:

```yaml
gl:
  name: General ledger
  transport: http
  url: https://gl-mcp.internal/mcp
  headers_env: { Authorization: GL_MCP_AUTHORIZATION }   # the value comes from this env var
  classification: internal
  tools:
    balances:      { scope: { arg: entity, key: entity } }
    journal_lines: { scope: { arg: entity, key: entity } }
```

Tool names and argument names must match what the real server exposes; the
capability manifests reference them as `connector.tool`. Results may be MCP
structured content or JSON text; a list of records under `rows` is what the
steps read.

## 4. Onboarding a capability

1. Copy a manifest in `config/helix/capabilities/` and change it: case key and
   label, which connector tools load the items, `compare` or `match`,
   `in_scope`, `group_by`, `rules`, the model's `skill` and `tools`, review
   roles, owners.
2. Validate — loading it runs every check (steps, gates, tools, expressions);
   problems are listed in plain words.
3. On a fresh database it seeds version 1. After that changes are API-driven:
   `POST /api/capabilities/{id}/versions` by an owner, then
   `…/versions/{n}/approve` by a different owner.

The two capabilities here — **P&L variance commentary** and **Cash — bank vs
ledger** — contain no code. That is the bar for every new one.

## 5. Not in the skeleton yet

Scheduled and event-driven case opening (`opens_on` is recorded, only manual
and API opening run); a capability builder and connector admin in the console
(the APIs for capability versions exist); connector onboarding with approval in
the database (today: `connectors.yaml` under code review); chat with a case;
moving FOBO onto the platform. These are phases 3–6 of the design.
