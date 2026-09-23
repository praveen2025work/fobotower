# Session Service Contract — FOBO Orchestrator ↔ Claude Agent SDK

The orchestrator settles every break it can deterministically. Only the
residue — multiple root causes fired, or none did — goes to the session
service, which runs it through the **Claude Agent SDK**.

**One request = one break.** A verdict must trace to evidence in the payload,
and a one-break payload is what keeps that auditable.

| Piece | Where |
|---|---|
| Orchestrator adapter | `apps/api/app/reasoning/adapters/session_service.py` |
| Reference session handler | [`reference/session_handler.py`](reference/session_handler.py) |
| Skill to deploy | [`skills/fobo-investigation/SKILL.md`](../../skills/fobo-investigation/SKILL.md) |
| Full source skill (reference) | [`docs/skills/fobo-investigation-cats-vs-motif.md`](../skills/fobo-investigation-cats-vs-motif.md) |

Verified against `claude-agent-sdk` **0.2.158**. Every option and message field
below was read from the installed package, not recalled.

---

## The three fields that matter

The orchestrator's hard guards read exactly these, and nothing else:

| Field | Guard |
|---|---|
| `verdict` | The proposal. The guards may override it. |
| `root_cause.established` | `false` forces `ESCALATE` (R6). |
| `root_cause.side` | `FO` forbids `POST` (R2). |

The Agent SDK enforces them for you. With `output_format` set, it validates
the model's answer against the schema and **re-prompts on mismatch** — a
response missing `root_cause.side`, or with a verdict outside the four
allowed values, is rejected before it reaches the orchestrator. Both cases
were tested under the SDK's draft-07 validator.

---

## Request → `ClaudeAgentOptions`

What the orchestrator sends, and the Agent SDK option each field becomes:

| Request field | Agent SDK | Notes |
|---|---|---|
| `skill_id` | `skills=["fobo-investigation"]` + `setting_sources=["project"]` | Loaded from `<cwd>/.claude/skills/fobo-investigation/SKILL.md`. Named, not re-sent. |
| `inputs` | the prompt | Dispatched as `/fobo-investigation` followed by the break record. |
| `mcp.url`, `mcp.token` | `mcp_servers={"fobo": {"type": "http", ...}}` | The orchestrator's knowledge graph and engines. |
| `tools` | `allowed_tools` | Allowlist. Must include `"Skill"`. MCP tools are named `mcp__fobo__<tool>`. |
| `output_schema` | `output_format={"type": "json_schema", "schema": ...}` | `SkillVerdict`. Draft-07 compatible as generated. |
| `max_turns` | `max_turns` | Default 20. |
| `correlation_id` | — | Echoed back. Also the idempotency key. |

Request body:

```json
{
  "skill_id": "fobo-investigation",
  "correlation_id": "sess-r-1055:b-07",
  "inputs": {
    "break_record": {
      "break_id": "b-07",
      "book": "APAC-CASH-07",
      "cob_date": "2026-08-03",
      "fo_value": 0.0,
      "bo_value": -247000.0,
      "break_amount": 247000.0,
      "checks": [
        { "check_id": "FO-3", "positive": true, "description": "Pull factor moved 1.00 -> 0.67" },
        { "check_id": "FO-6", "positive": true, "description": "Redemption on CA file; CATS PnL zero" }
      ]
    },
    "already_established": {
      "deterministic_findings": ["FO-1 pass", "FO-2 pass", "FO-4 pass"],
      "unresolved_reason": "multiple simultaneous root causes: FO-3, FO-6"
    }
  },
  "mcp": { "url": "https://fobo-orchestrator.internal/mcp", "token": "<token>" },
  "tools": [
    "mcp__fobo__fobo_list_tests",
    "mcp__fobo__fobo_evidence_required",
    "mcp__fobo__fobo_similar_breaks"
  ],
  "output_schema": { "$ref": "SkillVerdict" }
}
```

---

## `ResultMessage` → response

| Response field | Agent SDK source |
|---|---|
| `output` | `ResultMessage.structured_output` |
| `status` | from `ResultMessage.subtype` — see errors |
| `session_id` | `ResultMessage.session_id` |
| `tool_calls` | every `ToolUseBlock` (`name`, `input`) in `AssistantMessage.content` |
| `usage` | `ResultMessage.usage` |
| `total_cost_usd` | `ResultMessage.total_cost_usd` |
| `num_turns` | `ResultMessage.num_turns` |

```json
{
  "session_id": "5f2a91c0-...",
  "correlation_id": "sess-r-1055:b-07",
  "status": "completed",
  "output": {
    "break_summary": "EM amortising bond. FO PnL = 0. BO PnL = -£247k. Pull factor 1.00 -> 0.67.",
    "checks_performed": [
      { "test_id": "FO-3", "checked": "Pull factor continuity", "result": "Fail",
        "evidence": "Factor moved 1.00 -> 0.67" },
      { "test_id": "FO-6", "checked": "Redemption analysis", "result": "Fail",
        "evidence": "Redemption on CA file; expected PnL ≈ £247k; CATS produced zero" }
    ],
    "root_cause": {
      "established": true,
      "statement": "CATS failed to generate redemption PnL on the pull factor movement.",
      "contributing": [],
      "side": "FO"
    },
    "classification": {
      "category_code": "C", "category_name": "Redemption break",
      "secondary_code": "B", "deterministic": false
    },
    "verdict": "DO_NOT_POST",
    "verdict_reason": "Genuine break originating in FO. Posting would mask a CATS calculation failure.",
    "remediation": {
      "who_to_engage": ["Desk", "Product Control", "CATS support"],
      "what_to_raise": ["DQ incident with root-cause analysis request"],
      "preventative_control": "MBREC rule: factor movement present AND redemption PnL absent in FO -> auto-exception"
    },
    "end_state_validation": "No adjustment posted. Open pending FO correction.",
    "requires_sme_review": true,
    "competing_hypotheses": [
      "FO-6 finding A (pull factor event missing): redemption confirmed on CA file, CATS PnL zero — strong",
      "FO-6 finding B (factor applied too early): no evidence the event is effective later — weak"
    ],
    "unset_parameters": ["calculation_reasonable_tolerance"]
  },
  "tool_calls": [
    { "tool": "mcp__fobo__fobo_evidence_required", "arguments": { "test_id": "FO-6" } }
  ],
  "usage": { "input_tokens": 1840, "output_tokens": 612, "cache_read_input_tokens": 15230 },
  "total_cost_usd": 0.041,
  "num_turns": 4
}
```

---

## Errors

The orchestrator must tell **"could not reason"** apart from **"reasoned, and
the answer is escalate"**. They produce different records.

| Agent SDK outcome | `status` | Orchestrator does |
|---|---|---|
| `subtype: "success"` with `structured_output` | `completed` | Applies the guards to the verdict. |
| `subtype: "success"` with **no** `structured_output` | `failed` | Escalates; evidence gap. The SDK docs call this out as a failure. |
| `subtype: "error_max_structured_output_retries"` | `failed` | Escalates; evidence gap. The model could not produce a valid verdict. |
| `init` message lacks the skill in its `skills` list | `failed` | Escalates; configuration fault. Without the skill the model reasons from nothing and the verdict would look normal. |
| Any other error subtype, or an exception | `failed` | Escalates; evidence gap; retryable. |

In every failure case the break escalates. There is no fallback to a guess.

---

## Questions answered by the Agent SDK

| Open question | Answer |
|---|---|
| Can the service enforce the output schema? | **Yes** — `output_format`, validated and re-prompted on mismatch. |
| Are the model's tool calls returned? | **Yes** — `ToolUseBlock`s in the message stream. The reference handler collects them. |
| Sync or async? | `query()` streams until a `ResultMessage`. A judgement case may take a minute or more; how the service exposes that over HTTP is still its choice. |
| How are skills delivered? | As files: `<cwd>/.claude/skills/<name>/SKILL.md`. There is no API to register one. |

## Still open

1. **Deploying the skill.** `skills/fobo-investigation/SKILL.md` in this repo
   must be copied to the service's `<cwd>/.claude/skills/fobo-investigation/`.
   Who owns that step, and on what trigger?
2. **The orchestrator's MCP server.** The skill tells the model to look the
   playbook up through `fobo_*` tools rather than recall it. That server is
   not built yet. Until it is, the service should load the **full** source
   skill, which carries the playbook inline.
3. **HTTP timeout.** The orchestrator adapter waits 120s. Is that enough, or
   does the service return a session ID to poll?
