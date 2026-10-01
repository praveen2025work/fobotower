# MCP Server and Per-L4 Agent Sessions — Design

**Date:** 2026-10-01 · **Status:** approved in conversation · **Branch:** `feat/mcp-server-l4-sessions`

## 1. Purpose

Make the orchestrator ready to hand judgement work to the bank's existing
session-based agent harness at production volume.

Today the Reason step sends **one harness request per unsettled break** (up to
thousands a day for CATS vs MOTIF) and the harness has **no way to look
anything up**: the MCP tools the contract names do not exist. This change:

1. **MCP server** — exposes the knowledge graph and the run's breaks to the
   agent as read-only tools, served by the backend itself.
2. **Per-L4 agent sessions** — the Reason step makes **one harness session per
   L4 rec run** (Rates, Prime, FI Credit…), not per break; it starts the
   session, waits for it with restart safety, and keeps the full response for
   audit.

Out of scope: bank integrations (CATS/MOTIF/FAS adapters, BAM login), starting
investigations from the Ready event instead of the board's first read, chat
continuing the harness session, CI, evaluations.

## 2. Rules

- **Rules first, unchanged.** Every break is still offered to the deterministic
  classifier first. Only breaks it cannot settle go to the agent.
- **Every break passes the guards.** The agent's verdicts go through
  `guard_verdict` per break exactly as today.
- **No guessing.** A break the agent's response does not cover, a failed or
  timed-out session, or an unparseable response escalates with an evidence gap
  `reasoning:<break_id>` — the same outcome as today's failure path.
- **Read-only tools.** No MCP tool writes anything except its own audit row.
- **No behaviour change when no reasoner is configured** (`reasoner: none`, the
  default): runs, findings and the console look exactly as today.

## 3. Agent session lifecycle (`agent_session` table)

One row per investigation session (thread) that needed the agent. Columns:

| Column | Type | Meaning |
|---|---|---|
| `agent_session_id` | str(64) PK | `<investigation_session_id>:agent` |
| `investigation_session_id` | str(64) FK, unique | the run's thread |
| `status` | str(16) | `starting` → `running` → `completed` / `failed` |
| `harness_session_id` | str(128) null | the harness's own id, once known |
| `token_hash` | str(64) | sha256 hex of the per-session MCP token |
| `caller` | JSONB | the `Caller` the run executes as |
| `business_date` | date | as-of date for every tool |
| `breaks` | JSONB | `{break_id: {...evidence, "pattern_code": str}}` for the unsettled breaks |
| `request` | JSONB | what was sent (token redacted) |
| `response` | JSONB null | the harness's final payload |
| `error` | text null | why it failed |
| `created_ts`, `finished_ts` | timestamptz | |

Reason step behaviour by existing row status:

| Row | Action |
|---|---|
| none | create (`starting`), **commit**, start the harness session, store `harness_session_id`, set `running`, **commit**, then wait |
| `starting` | the process died before the harness answered: treat as failed (escalate); do not start a second session |
| `running` | resume waiting on the stored `harness_session_id` (restart safety) |
| `completed` | reuse the stored `response`; no new session |
| `failed` | escalate the unsettled breaks with the stored error |

The step commits before waiting so the MCP server (its own DB session) can see
the row and no transaction stays open during the wait.

## 4. MCP server

- Package `fobo/mcp_server/`, built on the official `mcp` SDK **2.x**
  (`from mcp.server.mcpserver import MCPServer`; v1's `FastMCP` was renamed).
- Streamable HTTP, stateless, JSON responses, mounted on the FastAPI app at
  **`/mcp`**. Mounted **only when `FOBO_MCP_URL` is set** (the URL the
  reasoner hands to the harness). Otherwise `/mcp` does not exist.
- **Auth: per-agent-session bearer token.** When the Reason step starts a
  session it generates a random token (`secrets.token_urlsafe(32)`), stores
  only its sha256, and sends the token in the request's `mcp.token`. A tool
  call is answered only if its bearer token matches an `agent_session` whose
  status is `running` (or `starting`). Any other request → 401. The token is
  dead as soon as the session completes or fails. `FOBO_MCP_TOKEN` is
  retired.
- The token resolves the **agent context**: investigation session id, caller,
  business date and the unsettled breaks. Every graph read uses that caller's
  entitlement predicate and that business date.
- **Every tool call writes one `source_call` row** with
  `application_name="agent"`, the tool name, parameters, row count, summary,
  latency and rows, so it appears in the console's MCP data panel.

Tools (all read-only):

| Tool | Input | Returns |
|---|---|---|
| `fobo_list_tests` | `side` FO\|BO | tests for that side (`tests_for_side`) |
| `fobo_evidence_required` | `test_id` | evidence types the test needs |
| `fobo_required_on_fail` | `test_id` | tests that must run when it fails |
| `fobo_unset_policies` | `params` list (optional; default = the workflow's `verdict_policy_params`) | which have no value |
| `fobo_book_context` | `book_ref` | resolved book id, desk, legal entity, upward lineage |
| `fobo_similar_breaks` | `break_id` (must be one of the session's breaks) | prior resolutions for that break's book and line |
| `fobo_list_breaks` | `pattern_code` (optional), `page` ≥1, `page_size` 1–100 (default 50) | the session's unsettled breaks, compact, paged, with total |
| `fobo_break_detail` | `break_id` (must be one of the session's breaks) | that break's full evidence record |

Asking for a break outside the session returns a tool error, not data.

## 5. Contract v2 (orchestrator ↔ harness)

**Start:** `POST {FOBO_SESSION_SERVICE_URL}/sessions`

```json
{
  "skill_id": "fobo-investigation",
  "correlation_id": "sess-r-2031",
  "inputs": {
    "rec": {"reconciliation_id": "R-2031", "master_book": "FICR-MB",
            "business_date": "2026-08-03", "run_id": "run-R-2031-20260803"},
    "patterns": [
      {"pattern_code": "UNGROUPED", "label": "No cause identified",
       "break_count": 5, "total_amount": 1234.5,
       "sample": [{"break_id": "B-3", "...": "evidence record"}]}
    ],
    "already_established": {"total": 8, "settled_by_rules": 3, "unsettled": 5}
  },
  "mcp": {"url": "https://<backend>/mcp", "token": "<per-session token>"},
  "tools": ["mcp__fobo__fobo_list_tests", "..."],
  "output_schema": {"$ref": "RecVerdict"}
}
```

`sample` holds at most `reason.sample_breaks_per_pattern` (default 5) break
records per pattern, largest absolute amount first. `mcp` and `tools` are
present only when `FOBO_MCP_URL` is set.

**Response** (to the POST, and to `GET {base}/sessions/{session_id}`):

```json
{
  "session_id": "h-123", "correlation_id": "sess-r-2031",
  "status": "running | completed | failed",
  "output": {
    "summary": "…",
    "patterns": [{"pattern_code": "UNGROUPED", "...": "SkillVerdict fields"}],
    "exceptions": [{"break_id": "B-7", "reason": "…", "verdict": {"...": "SkillVerdict"}}]
  },
  "tool_calls": [{"tool": "mcp__fobo__fobo_break_detail", "arguments": {"break_id": "B-3"}}],
  "usage": {}, "total_cost_usd": 0.12, "num_turns": 9,
  "error": {"code": "…", "message": "…"}
}
```

`output` is required when `status` is `completed`. While `running`, the
orchestrator polls `GET /sessions/{session_id}` every
`session_service.poll_interval_seconds` (default 5) up to
`session_service.max_wait_seconds` (default 900). Past that it marks the row
`failed` (timeout) and escalates. `timeout_seconds` stays as the per-HTTP-call
timeout.

**Verdict mapping per unsettled break:** an `exceptions` entry for the break →
that verdict; else the `patterns` entry for its pattern → that verdict; else
escalate with gap `reasoning:<break_id>`. Exceptions naming breaks outside the
request are ignored.

Pydantic models (in `fobo/reasoning/contracts.py`): `PatternVerdict(SkillVerdict)`
adds `pattern_code: str`; `BreakException` = `break_id`, `reason`,
`verdict: SkillVerdict`; `RecVerdict` = `summary`, `patterns`, `exceptions`.

## 6. Reasoning port v2

`ReasoningPort` gains the rec-level call; the per-break `investigate` is removed.

- `start(request: dict) -> HarnessStatus` and `poll(harness_session_id) -> HarnessStatus`,
  where `HarnessStatus` carries `session_id`, `status`, `output: RecVerdict | None`
  and the raw payload. Adapters raise `ReasoningUnavailable` on transport or
  parse failure.
- `SessionServiceReasoner` implements both over HTTP (contract v2).
- `DirectReasoner` (local development only) answers `start` synchronously with
  one model call that returns a `RecVerdict` (status `completed`), model
  `claude-opus-5-5`.
- `NullReasoner` raises `ReasoningUnavailable`, as today.
- The waiting loop (poll interval, max wait, sleeping) lives in the Reason step
  helper, not in adapters, so tests can drive it with a fake clock/sleep.

## 7. What the console shows

No UI changes. Agent-decided findings show as today (`deterministic: false`,
`requires_sme_review: true`) and additionally carry `reasoner`,
`harness_session_id` and `pattern_code`. The MCP data panel shows each agent
tool call (`application: agent`) and one `agent.session` row per session with
the harness's summary, cost, turns and status.

## 8. Stub harness (demo and manual test)

`apps/backend/scripts/stub_harness.py`: a small FastAPI app on port 8200
implementing contract v2. `POST /sessions` returns `running`, then a background
task calls the orchestrator's MCP server with the given URL/token
(`fobo_list_breaks`, then `fobo_break_detail` for each sample break) and
completes with a deterministic `RecVerdict`: per pattern, root cause
established, side BO, category G, verdict POST, `requires_sme_review: true`.
Run with `FOBO_REASONER=session_service FOBO_SESSION_SERVICE_URL=http://localhost:8200
FOBO_MCP_URL=http://localhost:8100/mcp`. FI Credit (R-2031, 5 unsettled) and
Collateral (R-2048, 1 unsettled) exercise it.

## 9. Known limitation (not fixed here)

Investigations still start on the board's first read. With a real harness, a
rec whose agent session runs for minutes holds that board request open for as
long. Moving investigation start to the Ready event (P1 #7) removes this.

## 10. Verification

`pytest -q` (backend) green including new tests; `npm run test:e2e` green;
manual run with the stub harness shows FI Credit's agent findings and the
agent's MCP calls in the console.
