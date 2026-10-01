# Session Service Contract v2 — FOBO Orchestrator ↔ Agent Harness

The orchestrator settles every break it can with the playbook's rules. Only the
residue — multiple root causes fired, or none did — goes to the bank's agent
harness (the session service), which runs it through the **Claude Agent SDK**.

**One session = one L4 rec run.** Rates, Prime, FI Credit and the rest each get
one session per run, not one per break. A CATS vs MOTIF run can leave thousands
of breaks unsettled, and a session per break is neither affordable nor fast.
The orchestrator groups the unsettled breaks into patterns, sends each pattern
with a small sample, and the agent reads the rest through the orchestrator's
MCP server.

| Piece | Where |
|---|---|
| Orchestrator adapter | `apps/backend/fobo/reasoning/adapters/session_service.py` |
| Request builder | `apps/backend/fobo/reasoning/requests.py` |
| Start, wait, map back to breaks | `apps/backend/fobo/investigation/agent_run.py` |
| MCP server the agent calls | `apps/backend/fobo/mcp_server/` |
| Stub harness (demo and manual test) | `apps/backend/scripts/stub_harness.py` |
| Reference session handler | [`reference/session_handler.py`](reference/session_handler.py) |
| Skill to deploy | [`skills/fobo-investigation/SKILL.md`](../../skills/fobo-investigation/SKILL.md) |
| Full source skill (reference) | [`docs/skills/fobo-investigation-cats-vs-motif.md`](../skills/fobo-investigation-cats-vs-motif.md) |

Verified against `claude-agent-sdk` **0.2.158**. Every option and message field
below was read from the installed package, not recalled.

---

## Start, then poll

An agent session for a whole rec can run for minutes, longer than one HTTP
call should stay open. So the orchestrator starts the session, then polls it.

1. **Start:** `POST {FOBO_SESSION_SERVICE_URL}/sessions` with the request
   below. The harness answers at once, normally with `status: "running"` and
   its own `session_id`.
2. **Poll:** `GET {FOBO_SESSION_SERVICE_URL}/sessions/{session_id}` until
   `status` is `completed` or `failed`. Same response shape.

Before starting, the orchestrator writes an `agent_session` row and commits
it. If the backend restarts mid-wait, the next run resumes polling the stored
`session_id` instead of starting a second session.

Three settings govern it. They live in the workflow config
(`config/workflow/fobo-investigation.yaml`, edited through the Workflow tab):

| Setting | Default | Meaning |
|---|---|---|
| `session_service.poll_interval_seconds` | 5 | Seconds between polls while the session runs. |
| `session_service.max_wait_seconds` | 900 | How long one session may run. Past this, the breaks escalate. |
| `reason.sample_breaks_per_pattern` | 5 | Break records sent per pattern, largest absolute amount first. The agent fetches the rest through MCP. |

`session_service.timeout_seconds` (default 120) is the timeout for each single
HTTP call, start or poll.

If the harness requires a bearer token, set `FOBO_SESSION_SERVICE_TOKEN`; the
orchestrator sends it on both calls.

---

## Request

`POST /sessions`:

```json
{
  "skill_id": "fobo-investigation",
  "correlation_id": "sess-r-2031",
  "inputs": {
    "rec": {
      "reconciliation_id": "R-2031",
      "master_book": "FICR-MB",
      "business_date": "2026-08-03",
      "run_id": "run-R-2031-20260803"
    },
    "patterns": [
      {
        "pattern_code": "UNGROUPED",
        "label": "No cause identified",
        "break_count": 5,
        "total_amount": 1234.5,
        "sample": [
          {
            "break_id": "B-3",
            "book": "FICR-MB-03",
            "line_code": "PNL",
            "cob_date": "2026-08-03",
            "fo_value": 0.0,
            "bo_value": -412.0,
            "break_amount": 412.0,
            "pattern_code": "UNGROUPED",
            "checks": []
          }
        ]
      }
    ],
    "already_established": {"total": 8, "settled_by_rules": 3, "unsettled": 5}
  },
  "mcp": {"url": "https://<backend>/mcp", "token": "<per-session token>"},
  "tools": [
    "mcp__fobo__fobo_list_tests",
    "mcp__fobo__fobo_evidence_required",
    "mcp__fobo__fobo_required_on_fail",
    "mcp__fobo__fobo_unset_policies",
    "mcp__fobo__fobo_book_context",
    "mcp__fobo__fobo_similar_breaks",
    "mcp__fobo__fobo_list_breaks",
    "mcp__fobo__fobo_break_detail"
  ],
  "output_schema": {"$ref": "RecVerdict"}
}
```

| Field | Meaning |
|---|---|
| `skill_id` | The skill to apply. Must match `name` in `SKILL.md`. Override with `FOBO_SESSION_SKILL_ID`. |
| `correlation_id` | The investigation session id. Echoed back; also the idempotency key. |
| `inputs.rec` | Which rec run this is, and its business date. |
| `inputs.patterns` | One entry per pattern: code, label, how many breaks, their total absolute amount, and a sample of full break records. Breaks no pattern claimed are under `UNGROUPED`. |
| `inputs.already_established` | How many breaks the run has, how many the rules settled, how many are left for the agent. |
| `mcp`, `tools` | Present only when `FOBO_MCP_URL` is set. See [MCP](#mcp). |
| `output_schema` | Shown here as a reference. The real request carries the full JSON Schema of `RecVerdict` (`fobo/reasoning/contracts.py`). |

---

## Response

The same shape answers the POST and every GET:

```json
{
  "session_id": "h-123",
  "correlation_id": "sess-r-2031",
  "status": "completed",
  "output": {
    "summary": "Five FI Credit breaks, one pattern. All trace to a coupon not yet booked in MOTIF; B-7 differs.",
    "patterns": [
      {
        "pattern_code": "UNGROUPED",
        "break_summary": "Five FICR-MB breaks, BO short by the coupon amount on each.",
        "checks_performed": [
          {"test_id": "BO-6", "checked": "Corporate action reflected in MOTIF",
           "result": "Fail", "evidence": "Coupon on the CA file; MOTIF shows no cash event"}
        ],
        "root_cause": {"established": true,
                       "statement": "MOTIF did not book the coupon payment.",
                       "contributing": [], "side": "BO"},
        "classification": {"category_code": "G", "category_name": "Corporate action break",
                           "secondary_code": null, "deterministic": false},
        "verdict": "POST",
        "verdict_reason": "Genuine BO timing difference; FO is correct.",
        "remediation": {"who_to_engage": ["BO operations"],
                        "what_to_raise": ["Book the coupon in MOTIF"],
                        "preventative_control": null},
        "end_state_validation": "BO + Adjustments = FO once posted.",
        "requires_sme_review": true,
        "competing_hypotheses": [],
        "unset_parameters": ["materiality_threshold"]
      }
    ],
    "exceptions": [
      {
        "break_id": "B-7",
        "reason": "FO value is zero; the coupon is missing on both sides.",
        "verdict": {
          "break_summary": "B-7: FO and BO both lack the coupon.",
          "checks_performed": [
            {"test_id": "FO-6", "checked": "Redemption and coupon analysis",
             "result": "Fail", "evidence": "CA file shows the coupon; CATS PnL zero"}
          ],
          "root_cause": {"established": true,
                         "statement": "CATS did not generate the coupon PnL.",
                         "contributing": [], "side": "FO"},
          "classification": {"category_code": "G", "category_name": "Corporate action break",
                             "secondary_code": null, "deterministic": false},
          "verdict": "DO_NOT_POST",
          "verdict_reason": "Originates in FO; posting would mask it.",
          "remediation": {"who_to_engage": ["CATS support"],
                          "what_to_raise": ["DQ incident"],
                          "preventative_control": null},
          "end_state_validation": "Open pending FO correction.",
          "requires_sme_review": true,
          "competing_hypotheses": [],
          "unset_parameters": []
        }
      }
    ]
  },
  "tool_calls": [
    {"tool": "mcp__fobo__fobo_list_breaks", "arguments": {"page_size": 50}},
    {"tool": "mcp__fobo__fobo_break_detail", "arguments": {"break_id": "B-3"}}
  ],
  "usage": {"input_tokens": 18400, "output_tokens": 2610},
  "total_cost_usd": 0.12,
  "num_turns": 9
}
```

| Field | Meaning |
|---|---|
| `session_id` | The harness's own id. The orchestrator polls with it. |
| `status` | `running`, `completed` or `failed`. Anything else is treated as a failure. |
| `output` | A `RecVerdict`. **Required** when `status` is `completed`. |
| `output.patterns` | One `SkillVerdict` per pattern, plus its `pattern_code`. |
| `output.exceptions` | Breaks that do not fit their pattern's verdict, each with its own. |
| `tool_calls`, `usage`, `total_cost_usd`, `num_turns` | Kept for audit and shown in the console's MCP data panel. |
| `error` | `{"code": "...", "message": "..."}` when `status` is `failed`. |

---

## Verdict mapping

For each unsettled break, in order:

1. An `exceptions` entry for that break → its verdict.
2. Else the `patterns` entry for the break's pattern → that verdict.
3. Else the break escalates, with evidence gap `reasoning:<break_id>`.

Exceptions naming breaks outside the request are ignored. Every verdict then
goes through the orchestrator's guards, break by break, exactly as a rule's
verdict does.

## The three fields that matter

The orchestrator's hard guards read exactly these, and nothing else:

| Field | Guard |
|---|---|
| `verdict` | The proposal. The guards may override it. |
| `root_cause.established` | `false` forces `ESCALATE` (R6). |
| `root_cause.side` | `FO` forbids `POST` (R2). |

The Agent SDK enforces the schema for you. With `output_format` set, it
validates the model's answer and **re-prompts on mismatch**.

---

## Errors

The orchestrator must tell **"could not reason"** apart from **"reasoned, and
the answer is escalate"**. They produce different records. In every failure
case the unsettled breaks escalate. There is no fallback to a guess.

| What happens | Orchestrator does |
|---|---|
| `completed` with a valid `RecVerdict` | Maps verdicts to breaks and applies the guards. |
| Still `running` past `max_wait_seconds` | Marks the session `failed` (timeout); escalates. |
| `failed` | Records the error; escalates. |
| `completed` without a valid `output` | Treated as failed; escalates. |
| HTTP error, timeout or unknown `status` on start or poll | Treated as failed; escalates. |
| Backend stopped after writing the row but before the harness answered | Not restarted (it may have started); escalates. |

What the harness should report as `failed`, from the Agent SDK's result:

| Agent SDK outcome | `status` |
|---|---|
| `subtype: "success"` with `structured_output` | `completed` |
| `subtype: "success"` with **no** `structured_output` | `failed` |
| `subtype: "error_max_structured_output_retries"` | `failed` |
| `init` message lacks the skill in its `skills` list | `failed` — without the skill the model reasons from nothing and the verdict would look normal |
| Any other error subtype, or an exception | `failed` |

---

## MCP

When `FOBO_MCP_URL` is set, the backend serves an MCP server at `/mcp`
(streamable HTTP, stateless, JSON responses) and the request tells the harness
where it is. `FOBO_MCP_URL` is the URL the **harness** uses to reach the
backend, so set it to an address the harness can resolve.

**Auth is per session.** For each agent session the orchestrator mints a
random token, keeps only its sha256, and sends the token in `mcp.token`. The
harness passes it as `Authorization: Bearer <token>`. The MCP server answers
only while that session is starting or running; any other token gets a 401.
The token dies when the session completes or fails.

The token also fixes what the agent may see: the rec's caller (entitlements),
its business date, and its unsettled breaks. Every tool call is recorded as a
`source_call` row with `application_name = "agent"`, and appears in the
console's MCP data panel.

All tools are read-only. The model sees them as `mcp__fobo__<tool>`.

| Tool | Input | Returns |
|---|---|---|
| `fobo_list_tests` | `side`: `FO` or `BO` | The tests for that side. |
| `fobo_evidence_required` | `test_id` | The evidence types the test needs. |
| `fobo_required_on_fail` | `test_id` | The tests that must run when it fails. |
| `fobo_unset_policies` | `params` (optional; default the workflow's verdict policy params) | Which have no value. |
| `fobo_book_context` | `book_ref` | The resolved book id, desk, legal entity and upward lineage. |
| `fobo_similar_breaks` | `break_id` (one of this session's) | Prior resolutions for that break's book and line. |
| `fobo_list_breaks` | `pattern_code` (optional), `page` ≥ 1, `page_size` 1–100 (default 50) | This session's unsettled breaks, compact and paged, with the total. |
| `fobo_break_detail` | `break_id` (one of this session's) | That break's full evidence record. |

Asking for a break outside the session returns a tool error, not data.

---

## Request → `ClaudeAgentOptions`

One session handles a whole L4 rec run. What the orchestrator sends, and the
Agent SDK option each field becomes:

| Request field | Agent SDK | Notes |
|---|---|---|
| `skill_id` | `skills=["fobo-investigation"]` + `setting_sources=["project"]` | Loaded from `<cwd>/.claude/skills/fobo-investigation/SKILL.md`. Named, not re-sent. |
| `inputs` | the prompt | Dispatched as `/fobo-investigation` followed by the rec, its patterns and samples. |
| `mcp.url`, `mcp.token` | `mcp_servers={"fobo": {"type": "http", "url": ..., "headers": {"Authorization": "Bearer ..."}}}` | The orchestrator's knowledge graph and the session's breaks. |
| `tools` | `allowed_tools` | Allowlist. Must include `"Skill"`. MCP tools are named `mcp__fobo__<tool>`. |
| `output_schema` | `output_format={"type": "json_schema", "schema": ...}` | `RecVerdict`. Draft-07 compatible as generated. |
| `correlation_id` | — | Echoed back. Also the idempotency key. |

Allow enough turns for the agent to page through the breaks: a rec with many
patterns needs more than a single break did.

## `ResultMessage` → response

| Response field | Agent SDK source |
|---|---|
| `output` | `ResultMessage.structured_output` |
| `status` | from `ResultMessage.subtype` — see errors |
| `session_id` | the harness's id for the session (it may differ from `ResultMessage.session_id`) |
| `tool_calls` | every `ToolUseBlock` (`name`, `input`) in `AssistantMessage.content` |
| `usage` | `ResultMessage.usage` |
| `total_cost_usd` | `ResultMessage.total_cost_usd` |
| `num_turns` | `ResultMessage.num_turns` |

---

## Trying it without a harness

`scripts/stub_harness.py` implements this contract with a fixed verdict. It
calls the MCP server the way a real agent would (`fobo_list_breaks`, then
`fobo_break_detail` for each sample break), so the start/poll loop, the token
auth and the audit rows can be checked end to end. It is not a reasoner. The
README has the commands.

## Still open

1. **Deploying the skill.** `skills/fobo-investigation/SKILL.md` must be
   copied to the service's `<cwd>/.claude/skills/fobo-investigation/`. Who
   owns that step, and on what trigger? It now describes a whole L4 run, so
   the deployed copy must be updated with this contract.
2. **The harness's HTTP format.** This contract assumes `POST /sessions` and
   `GET /sessions/{id}` with the bodies above. The bank's harness team must
   confirm its real routes, status values and error shape, or the adapter
   changes to match.
3. **Reaching the MCP server.** The harness must be able to open a connection
   to `FOBO_MCP_URL`. On the bank's network that is a firewall and TLS
   question, not a code one.
