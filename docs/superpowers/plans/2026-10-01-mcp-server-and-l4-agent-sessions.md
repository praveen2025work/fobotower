# MCP Server and Per-L4 Agent Sessions — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-10-01-mcp-server-and-l4-agent-sessions-design.md` (binding authority — read the section each task names)
**Branch:** `feat/mcp-server-l4-sessions`

## Global Constraints

- Backend lives in `apps/backend`, package `fobo`. Python 3.12, venv at `apps/backend/.venv`.
- Run tests from `apps/backend`: `.venv/bin/python -m pytest -q` (uses the test database `fobo_test` on localhost:5433; Postgres runs in Docker and is up). The suite currently has **383 passing tests**; it must stay green.
- TDD: write the failing test first, see it fail, implement, see it pass.
- Match the surrounding code: module docstrings explaining *why*, small functions, pydantic models with `extra="forbid"` where the codebase does, async SQLAlchemy 2.0 style (`select`, `session.scalars`, `session.execute`). Comment density like neighbouring files.
- New tables: add the SQLAlchemy model **and** an Alembic migration whose `down_revision` is the current head `f3b8d1c6a4e7`, **and** add the table name to `TABLES` in `tests/conftest.py` (child tables first) so tests truncate it.
- The `mcp` SDK is **version 2.x** (installed: 2.2.0). v1's `FastMCP` does not exist; use `from mcp.server.mcpserver import MCPServer`. Inspect the installed package for exact APIs; do not code from v1 memory.
- Never break `reasoner: none` (the default): with no reasoner configured, runs and findings must be exactly as before.
- Commits: conventional format `<type>: <description>`, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commit on the current branch; never push.
- Do not touch `apps/console` (no UI changes in this plan).

---

## Task 1: `agent_session` table and repository

**Spec:** §3.

**Files:**
- Modify `fobo/db/models_session.py`: add `AgentSession` model with exactly the spec §3 columns (`agent_session_id` PK str(64); `investigation_session_id` str(64) FK → `investigation_session.investigation_session_id`, unique; `status` str(16); `harness_session_id` str(128) nullable; `token_hash` str(64); `caller` JSONB; `business_date` Date; `breaks` JSONB; `request` JSONB; `response` JSONB nullable; `error` Text nullable; `created_ts` timestamptz server default now(); `finished_ts` timestamptz nullable). Add an index on `token_hash`.
- Create migration `migrations/versions/a9c4e2f7b1d5_agent_session.py` (`down_revision = "f3b8d1c6a4e7"`), upgrade creates the table + index, downgrade drops them.
- Modify `tests/conftest.py`: add `"agent_session"` to `TABLES` before `"investigation_session"`.
- Create `fobo/reasoning/agent_sessions.py` with:
  - `new_token() -> tuple[str, str]` returning `(token, sha256_hex)` using `secrets.token_urlsafe(32)` and `hashlib.sha256`.
  - `hash_token(token: str) -> str`.
  - `async def get_for_investigation(session, investigation_session_id) -> AgentSession | None`.
  - `async def create(session, *, investigation_session_id, token_hash, caller: dict, business_date, breaks: dict, request: dict) -> AgentSession` — status `starting`, id `f"{investigation_session_id}:agent"`.
  - `async def mark_running(session, row, harness_session_id)`, `async def mark_completed(session, row, response: dict)`, `async def mark_failed(session, row, error: str, response: dict | None = None)` — completed/failed set `finished_ts`.
  - `async def find_active_by_token(session, token: str) -> AgentSession | None` — matches `hash_token(token)` and status in (`starting`, `running`); otherwise None.
  - These helpers do not commit; callers commit.
- Create `tests/test_agent_sessions.py`.

**Tests (at least):** token pair hashes consistently and tokens differ per call; create → status `starting`, id format; mark_running/completed/failed transitions and `finished_ts`; `find_active_by_token` finds a running row, returns None for a wrong token, and None once the row is completed or failed; unique constraint — a second create for the same investigation raises `IntegrityError`. Tests need an `investigation_session` row to satisfy the FK — look at how existing tests (e.g. `tests/test_grounding.py`) create one.

Also run `.venv/bin/alembic upgrade head` once against the dev database to prove the migration applies, then `.venv/bin/alembic downgrade -1` and `upgrade head` again.

---

## Task 2: Contract v2 models and reasoning port v2 (adapters)

**Spec:** §5, §6.

**Files:**
- Modify `fobo/reasoning/contracts.py`: add `PatternVerdict(SkillVerdict)` with `pattern_code: str`; `BreakException(BaseModel)` with `break_id: str`, `reason: str`, `verdict: SkillVerdict`; `RecVerdict(BaseModel)` with `summary: str`, `patterns: list[PatternVerdict]`, `exceptions: list[BreakException] = []` (use `Field(default_factory=list)`). Keep `SkillVerdict` unchanged.
- Modify `fobo/reasoning/port.py`: add `HarnessStatus` (a frozen dataclass or pydantic model) with `session_id: str`, `status: Literal["running","completed","failed"]`, `output: RecVerdict | None`, `payload: dict`, `error: str | None`. Replace the per-break `investigate` in `ReasoningPort` with `async def start(self, request: dict) -> HarnessStatus` and `async def poll(self, session_id: str) -> HarnessStatus`. Update the module docstring: the port is now rec-level (one request per L4 run); explain why (volume).
- Rewrite `fobo/reasoning/adapters/session_service.py` to contract v2:
  - Config unchanged except: `FOBO_MCP_TOKEN` is **removed** (tokens are per session now). `FOBO_MCP_URL` still decides whether `mcp`/`tools` are offered.
  - `build_request(*, correlation_id, rec, patterns, already_established, mcp_token) -> dict` (module-level or method; keep it pure) producing exactly the spec §5 request. `mcp` = `{"url": FOBO_MCP_URL, "token": mcp_token}` and `tools` = the 8 tool names prefixed `mcp__fobo__` (`fobo_list_tests, fobo_evidence_required, fobo_required_on_fail, fobo_unset_policies, fobo_book_context, fobo_similar_breaks, fobo_list_breaks, fobo_break_detail`), only when `FOBO_MCP_URL` is set. `output_schema` = `RecVerdict.model_json_schema()`.
  - `start(request)` → `POST {base}/sessions`; `poll(session_id)` → `GET {base}/sessions/{session_id}`. Both use `httpx.AsyncClient(timeout=settings().session_service.timeout_seconds)` and the bearer header as today.
  - `_parse_status(payload) -> HarnessStatus`: `status` must be one of running/completed/failed (else `ReasoningUnavailable`); `session_id` required; `completed` requires `output` that validates as `RecVerdict` (else `ReasoningUnavailable` naming the validation problem); `failed` → `HarnessStatus(status="failed", error="<code> — <message>")` (do not raise; the step records it). Transport errors and non-2xx → `ReasoningUnavailable`.
- Rewrite `fobo/reasoning/adapters/null.py`: `start`/`poll` raise `ReasoningUnavailable` with the existing message.
- Rewrite `fobo/reasoning/adapters/direct.py`: `start(request)` makes one `messages.parse` call with `output_format=RecVerdict`, user content = the request's `inputs` as JSON, system = `reasoning_prompt()`; returns `HarnessStatus(session_id="direct-<uuid4 hex[:12]>", status="completed", output=parsed, payload={})`. `poll` raises `ReasoningUnavailable("direct reasoner completes synchronously")`. Set `MODEL = "claude-opus-5-5"`. Update the second system text block in `fobo/reasoning/prompt.py` so it describes a rec-level task: patterns with samples, return a verdict per pattern and exceptions for breaks that do not fit.
- Modify `fobo/investigation/settings.py`: `ReasonSettings.sample_breaks_per_pattern: int = Field(5, ge=1, le=50, description="Break records sent per pattern in the agent request; the agent fetches the rest through MCP")`; `SessionServiceSettings.max_wait_seconds: float = Field(900.0, gt=0, le=3600, description="How long one agent session may run before the breaks escalate")` and `poll_interval_seconds: float = Field(5.0, gt=0, le=60, description="Seconds between status checks while an agent session runs")`. Keep `timeout_seconds` but change its description to "Seconds allowed per HTTP call to the session service". Add the three settings with their defaults and short comments to `config/workflow/fobo-investigation.yaml`.
- Rewrite `tests/test_session_service_adapter.py` for v2 (keep the skill-id-matches-SKILL.md test). Use `httpx.MockTransport` (patch the client construction or inject a transport via a constructor parameter `transport=None` passed to `AsyncClient`).

**Tests (at least):** request shape (skill_id, correlation_id, inputs.rec/patterns/already_established, output_schema == `RecVerdict.model_json_schema()`); `mcp`/`tools` present only with `FOBO_MCP_URL`, carrying the per-session token and all 8 prefixed tool names; parse running / completed / failed; completed without output → `ReasoningUnavailable`; invalid output → `ReasoningUnavailable`; unknown status → `ReasoningUnavailable`; HTTP 500 → `ReasoningUnavailable`; poll hits `GET /sessions/<id>`; NullReasoner raises; settings defaults (5, 900, 5) and bounds; the YAML still validates (existing workflow config tests cover loading — keep them green).

The contract markdown is rewritten in Task 6; until then `tests/test_session_service_adapter.py` must not parse JSON examples from it (drop the `_documented` helper usage or point it at Task 6 — Task 6 re-adds a doc-consistency test).

---

## Task 3: Reason step — one agent session per L4 run

**Spec:** §2, §3, §5 (mapping), §7.

**Files:**
- Create `fobo/investigation/agent_run.py` holding the orchestration so `steps/reason.py` stays small:
  - `build_patterns(unsettled: dict[str, dict], pattern_groups, sample_size) -> list[dict]` — group unsettled break evidence by the `pattern_code` of the `PatternGroup` containing it (a break in no group → `"UNGROUPED"`, label "No cause identified"); each pattern: `pattern_code`, `label`, `break_count`, `total_amount` (sum of `abs(break_amount or 0)`, rounded to 2 dp), `sample` = up to `sample_size` evidence dicts sorted by `abs(break_amount or 0)` descending. Patterns ordered by `break_count` desc then code.
  - `map_verdicts(rec_verdict: RecVerdict, unsettled_ids) -> dict[str, tuple[SkillVerdict | None, str | None]]` — per break: exception verdict, else its pattern's verdict, else `(None, "not covered by the agent's response")`. Needs each break's pattern code (from the `breaks` evidence dicts, which carry `pattern_code`).
  - `async def run_agent(session, state, unsettled, *, reasoner, sleep=asyncio.sleep, clock=time.monotonic) -> AgentOutcome` implementing the spec §3 lifecycle table exactly (create/commit → start → mark_running/commit → wait loop using `poll` every `poll_interval_seconds` until completed/failed or `max_wait_seconds` elapsed → mark_completed or mark_failed + commit). A start that returns `completed` immediately (DirectReasoner) skips polling. `AgentOutcome` carries `rec_verdict | None`, `harness_session_id | None`, `error | None`, `payload`. `ReasoningUnavailable` anywhere → row failed with that message (if a row exists) and outcome error.
  - The request is built with `SessionServiceReasoner.build_request`'s shape — put the pure request builder somewhere both the adapter and this module can import without a cycle (e.g. keep it in the adapter module as a module-level function and import it here, or move it to `fobo/reasoning/requests.py`); the token comes from `new_token()`; the stored `request` has the token replaced by `"<redacted>"`.
  - After the session ends (any outcome, including reuse of a completed row), record **one** `source_call` via `GroundingRecorder(session, investigation_session_id)`: `application="agent"`, `tool="agent.session"`, `params={"harness_session_id", "patterns", "breaks"}`, `row_count=number of unsettled breaks`, `summary` = the RecVerdict summary (or the error), `error` = the error, `rows` = `[{"tool": ..., "arguments": ...}]` from the payload's `tool_calls` (empty list if none). Do not record it twice when reusing a completed row on a re-run (check for an existing `agent.session` call for this investigation first).
- Modify `fobo/investigation/steps/reason.py`:
  - First pass: classify every break exactly as today; resolved breaks get their findings exactly as today.
  - Collect the unsettled breaks' evidence (`_evidence(state, brk)` plus `"pattern_code"` and `"book_id"` = `state.get("book_resolutions", {}).get(bid)`). If none, behave exactly as today (no reasoner lookup at all).
  - If any: resolve the reasoner as today (`reasoner` argument wins, else `get_reasoner()`; `ReasoningUnavailable` → every unsettled break escalates with gap `reasoning:<bid>` and `reasoning_error` set — today's failure finding shape). With a reasoner and `session is None` (unit tests without a DB), call `run_agent` with `session=None` support: skip all persistence and recording (document this in the docstring) — or require a session and give the unit tests one; choose one and test it.
  - Apply `map_verdicts`; a break with a verdict gets today's agent finding shape plus `"reasoner"`, `"harness_session_id"`, `"pattern_code"`; a break without one gets today's failure finding shape and gap `reasoning:<bid>`.
  - Every break, both paths, then goes through `guard_verdict` exactly as today.
  - `reasoning_error` = the outcome error (or the "not covered" note listing break ids if some breaks were uncovered), else None.
- Modify `fobo/investigation/step_registry.py`: the reason step `needs` adds `pattern_groups`, `investigation_session_id`, `reconciliation_id`, `master_book`, `run_id`, `caller`. Keep `produces` as is. Run `tests/test_workflow_*` to confirm the shipped workflow still validates (group runs before reason).
- Rewrite the reasoner-dependent tests in `tests/test_reason_step.py` (the `Recording` double becomes a fake port with `start`/`poll` returning scripted `HarnessStatus` values). Add `tests/test_agent_run.py`.

**Tests (at least):** a single-cause break never reaches the reasoner (keep); no unsettled breaks → `start` never called; several unsettled breaks across two patterns → exactly **one** `start` call whose request has both patterns, counts, totals and samples capped at `sample_breaks_per_pattern` sorted by amount; pattern verdict applied to every break of the pattern; an exception overrides its break's pattern verdict; a break not covered → escalation finding + gap; guards still override (side FO + POST → not POST); running then completed via polls (fake sleep/clock, no real waiting); never completes → failed after `max_wait_seconds`, row failed, breaks escalate; harness `failed` → breaks escalate with the error; re-run with a `running` row resumes polling the stored `harness_session_id` without calling `start`; re-run with a `completed` row reuses the response without `start` or `poll` and without a second `agent.session` source_call; a `starting` row → escalates, no `start`; findings carry `harness_session_id`, `pattern_code`, `reasoner`; the `agent.session` source_call is recorded with the tool calls as rows; `reasoner: none` path unchanged.

---

## Task 4: MCP tools (logic)

**Spec:** §4 (tools table, agent context, audit rows).

**Files:**
- Create `fobo/mcp_server/__init__.py` (docstring: what the package is, the auth model in one paragraph).
- Create `fobo/mcp_server/context.py`: `AgentContext` (frozen dataclass): `investigation_session_id`, `caller: Caller`, `business_date: date`, `breaks: dict[str, dict]`. `async def context_for_token(session, token) -> AgentContext | None` using `find_active_by_token` from Task 1 (builds `Caller.model_validate(row.caller)`).
- Create `fobo/mcp_server/tools.py`: one async function per tool in spec §4, each `async def fobo_x(session, ctx: AgentContext, **inputs) -> dict`, using `OntologyRepository` / `GraphRepository` with `ctx.business_date` and `ctx.caller`. Rules:
  - `fobo_book_context(book_ref)`: `resolve_book` → `book_context` → `lineage(book_id, "BELONGS_TO", depth=settings().gather.lineage_max_depth, ...)`; `UnresolvedBook`/`AmbiguousBook` → a `ToolInputError` with a plain message.
  - `fobo_similar_breaks(break_id)`: the break must be in `ctx.breaks` (else `ToolInputError`); uses the break evidence's `book_id` and `line_code` (Task 3 puts both in every agent evidence record; a missing `book_id` → `ToolInputError`) and calls `similar_breaks(book_id, line_code, business_date, settings().gather.priors_lookback_days, caller, limit=settings().gather.max_similar_breaks)`.
  - `fobo_list_breaks(pattern_code=None, page=1, page_size=50)`: validate `page >= 1`, `1 <= page_size <= 100`; filter by pattern; stable order by break_id; return `{"total", "page", "page_size", "breaks": [compact rows: break_id, book, pattern_code, break_amount, line_code]}`.
  - `fobo_break_detail(break_id)`: the full evidence dict; outside the session → `ToolInputError`.
  - `fobo_unset_policies(params=None)`: default `settings().reason.verdict_policy_params`.
  - All results JSON-safe (dates → ISO strings).
  - `ToolInputError(ValueError)` defined in this module.
- Create `fobo/mcp_server/audit.py`: `async def audited(session, ctx, tool_name, params, fn)` — runs the tool, times it, records one `source_call` through `GroundingRecorder(session, ctx.investigation_session_id)` with `application="agent"`, `tool=tool_name`, params, `row_count` (len of the main list in the result, or 1), a short summary, `latency_ms`, `error` on failure, `rows` (the list rows, or `[result]`), commits, and re-raises tool errors after recording them.
- Create `tests/test_mcp_tools.py` (seed the graph with the existing seed loader as other tests do, e.g. `tests/test_ontology.py` / `tests/test_repository.py`; build an `AgentContext` directly).

**Tests (at least):** each tool returns the expected data for seeded rows (e.g. FO-6 evidence = Corporate action file + Pull factor history; FO-3 on fail requires FO-6; PRIME-MB-05 on 2026-08-03 → desk APAC-CASH, on 2026-06-15 → APAC-TREASURY); entitlement — a caller without the entity in scope cannot resolve the book; `fobo_list_breaks` paging and filter and bounds errors; break outside the session → `ToolInputError` for detail and similar; `audited` writes exactly one `source_call` with `application_name == "agent"` on success and one with `error_detail` on failure.

---

## Task 5: MCP server over HTTP, mounted at `/mcp`

**Spec:** §4 (transport, mount condition, auth).

**Files:**
- Modify `apps/backend/pyproject.toml`: add `"mcp>=2.2,<3"` to dependencies (it is already installed in the venv).
- Create `fobo/mcp_server/server.py`:
  - `build_mcp_server() -> MCPServer` registering the 8 tools with the exact names from spec §4, each with a one-sentence description a model can act on and typed parameters (so the SDK generates the input schema). Each registered tool: reads the bearer token for the current request, resolves `AgentContext` with a fresh `SessionFactory()` session, returns 401-equivalent failure if none (see auth below), and runs the Task 4 function through `audited`.
  - Auth: requests to `/mcp` must carry `Authorization: Bearer <token>` matching an active agent session (`context_for_token`). Implement as an ASGI/Starlette middleware wrapping the MCP Starlette app that returns HTTP 401 JSON `{"error": "invalid or expired agent session token"}` when the header is missing or does not resolve, and otherwise stores the resolved `AgentContext` in a `contextvars.ContextVar` for the tool functions. (If the SDK's `token_verifier`/`AuthSettings` gives tools access to the verified token more simply, you may use it instead — but the 401 behaviour and the per-session token semantics must be identical; say which you chose in the report.)
  - Use `streamable_http_app(stateless_http=True, json_response=True, streamable_http_path="/")` (or the path that makes the final URL exactly `/mcp` once mounted). Configure `transport_security` so the mounted app accepts the Host header it will be called with; allowed hosts come from `FOBO_MCP_URL`'s host plus `localhost`/`127.0.0.1` — check the SDK's `TransportSecuritySettings` for the exact fields.
- Modify `fobo/web/main.py`: when `FOBO_MCP_URL` is set, mount the app at `/mcp` and make the FastAPI lifespan also run the MCP server's session manager (check the SDK: the streamable HTTP session manager must be running — typically `async with mcp.session_manager.run():` inside the lifespan). When unset, nothing is mounted and `/mcp` returns 404. Keep `setup_checkpointer()` in the lifespan.
- Create `tests/test_mcp_http.py` using `httpx.AsyncClient(transport=httpx.ASGITransport(app=...))` with an app built while `FOBO_MCP_URL` is set (build the app inside the test via `create_app()` after `monkeypatch.setenv`; ASGITransport does not run lifespans, so enter the MCP session manager context explicitly in the fixture if the SDK requires it). Send raw JSON-RPC (`initialize` if the stateless server requires it, then `tools/list` and `tools/call`) with headers `Accept: application/json, text/event-stream` and `Content-Type: application/json`.

**Tests (at least):** without `FOBO_MCP_URL` `/mcp` is 404; no token → 401; unknown token → 401; token of a completed session → 401; valid token → `tools/list` returns exactly the 8 tool names; `tools/call fobo_evidence_required {"test_id":"FO-6"}` returns the two evidence types and writes one `source_call` with `application_name="agent"` for that investigation; `tools/call fobo_break_detail` for a break outside the session returns a tool error (`isError: true`), not data.

---

## Task 6: Stub harness, contract doc, docs

**Spec:** §5, §8, §9.

**Files:**
- Create `apps/backend/scripts/stub_harness.py`: FastAPI app (run: `.venv/bin/uvicorn scripts.stub_harness:app --port 8200` from `apps/backend`, or a `__main__` block). `POST /sessions` stores the request, returns `{"session_id": "stub-<n>", "correlation_id": ..., "status": "running"}` and starts a background task that: if `mcp` is present, connects to it with the MCP **client** from the `mcp` SDK (streamable HTTP client with the bearer header) and calls `fobo_list_breaks` then `fobo_break_detail` for each sample break; then builds a `RecVerdict` per spec §8 (root cause established, side BO, category G "Corporate action break", verdict POST, requires_sme_review true, one `checks_performed` row, summary naming how many breaks it read) and marks the session completed with `tool_calls` listing the calls it made, `usage: {}`, `total_cost_usd: 0`, `num_turns`. `GET /sessions/{id}` returns the current payload. Errors in the background task → `status: failed` with `error`. Module docstring explains it is a demo/test double, not a reasoner.
- Rewrite `docs/integration/session-service-contract.md` for contract v2: one session per L4 rec run, the request and response exactly as spec §5 (include both as ```json blocks — request first, then response), start-then-poll with the three settings, verdict mapping, error table (running past max wait → failed/escalate; failed → escalate; completed without valid output → escalate), per-session MCP token, the 8 tools with inputs, and "Still open" items updated (skill deployment, harness format confirmation). Keep the Agent SDK mapping section, adapted (one session handles a whole L4; `output_format` = RecVerdict).
- Update `docs/integration/reference/session_handler.py` to the v2 shape (rec-level inputs, RecVerdict schema, returns session_id/status/output/tool_calls). It is reference code; keep it importable-free of new deps beyond what it already uses.
- Update `skills/fobo-investigation/SKILL.md`: the task is now a whole L4 run — patterns with samples; use `fobo_list_breaks`/`fobo_break_detail` to read beyond the sample; return one verdict per pattern and exceptions for breaks that do not fit; never assume a break matches its pattern without checking at least the sample. Keep its `name: fobo-investigation`.
- Add a doc-consistency test to `tests/test_session_service_adapter.py`: the request JSON in the contract doc has the same top-level keys and `inputs` keys as `build_request(...)` output; the response example's `output` validates as `RecVerdict` after filling placeholder values if needed (if the doc uses `"..."` placeholders, write the doc example with real values instead so it validates).
- Update `docs/DEPLOYMENT.md` and `README.md`: `FOBO_MCP_TOKEN` removed; `FOBO_MCP_URL` both enables `/mcp` and is what the harness is told; the three new settings; how to run the stub harness for a demo (three commands); the §9 known limitation in one sentence.
- Update `docs/ARCHITECTURE.md`: add `fobo/mcp_server/` and `fobo/investigation/agent_run.py` rows in the same table style, and mention `agent_session`.

**Verification for this task:** full `pytest -q` green. Then a manual end-to-end run (report the observed output): start the stub harness on 8200; start the backend on 8100 with `FOBO_ENV=dev FOBO_REASONER=session_service FOBO_SESSION_SERVICE_URL=http://localhost:8200 FOBO_MCP_URL=http://localhost:8100/mcp`; reset FI Credit's investigation so it re-runs (delete the rows for `sess-r-2031` from `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` (thread_id), `source_call`, `agent_session`, and its `investigation_session`-dependent rows — or use the README reset command against the dev DB, which resets every rec); `curl localhost:8100/api/board`; then confirm via `curl localhost:8100/api/recs/R-2031/trace` that the reason step reports 5 needing judgement and via SQL that `agent_session` for `sess-r-2031` is `completed` and `source_call` has `application_name='agent'` rows (`fobo_list_breaks`, `fobo_break_detail`, `agent.session`). Stop both servers afterwards.
