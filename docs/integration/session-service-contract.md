# Session Service Contract — FOBO Orchestrator

What the FOBO orchestrator needs from the session service that owns the LLM
call. The orchestrator settles every break it can deterministically; only the
residue — multiple causes fired, or none did — is sent here.

**One request = one break.** The orchestrator never sends a whole run: a
verdict must trace to evidence in the payload, and a one-break payload is what
makes that auditable.

Adapter: `apps/api/app/reasoning/adapters/session_service.py`. Any mismatch
with the service's real shape is fixed in two functions there —
`_build_request` and `_parse_response`.

---

## Minimum contract

If the service can do nothing else, it must do this.

**Request** — a skill reference and one break record.

**Response** — these three fields, because the orchestrator's hard guards
read them and nothing else:

| Field | Type | Why it is load-bearing |
|---|---|---|
| `verdict` | `POST` \| `DO_NOT_POST` \| `ESCALATE` \| `CORRECT_AND_REPOST` | The proposed outcome. The guards may override it. |
| `root_cause.established` | boolean | R6: `false` forces `ESCALATE` regardless of `verdict`. |
| `root_cause.side` | `FO` \| `BO` \| `BOTH` \| `NEITHER` \| `UNKNOWN` | R2: `FO` forbids `POST`. |

Free-text output is **not** sufficient. The guards cannot read prose, so an
unstructured answer is treated as unavailable and the break escalates.

---

## Request

`POST /sessions`

Headers:

```
Content-Type: application/json
Authorization: Bearer <FOBO_SESSION_SERVICE_TOKEN>
Idempotency-Key: <correlation_id>
```

Body — the Appendix A worked case:

```json
{
  "skill_id": "fobo-cats-vs-motif",
  "skill_version": "1.0",
  "correlation_id": "sess-r-1055:b-07",

  "inputs": {
    "break_record": {
      "break_id": "b-07",
      "book": "APAC-CASH-07",
      "line_code": "CASH",
      "cob_date": "2026-08-03",
      "fo_value": 0.0,
      "bo_value": -247000.0,
      "break_amount": 247000.0,
      "checks": [
        { "check_id": "FO-3", "positive": true,
          "description": "Pull factor moved 1.00 -> 0.67",
          "supporting_ids": ["pf-2026-08-03-XS123"] },
        { "check_id": "FO-6", "positive": true,
          "description": "Redemption on corporate action file; CATS PnL zero",
          "supporting_ids": ["ca-2026-08-03-XS123"] }
      ],
      "prior_resolutions": [
        { "break_id": "b-2026-07-14-03", "cob_date": "2026-07-14",
          "pattern_code": "C", "outcome": "DO_NOT_POST" }
      ],
      "lineage": [
        { "node_type": "Desk", "natural_key": "APAC-CASH", "depth": 0 }
      ]
    },

    "already_established": {
      "deterministic_findings": ["FO-1 pass", "FO-2 pass", "FO-4 pass"],
      "unresolved_reason": "multiple simultaneous root causes: FO-3, FO-6",
      "unset_parameters": ["materiality_threshold", "calculation_reasonable_tolerance"]
    }
  },

  "attachments": [
    { "name": "corporate_action_file",
      "uri": "s3://fobo-evidence/2026-08-03/ca-XS123.csv",
      "media_type": "text/csv" }
  ],

  "tools": ["mbrec.get_break", "mbrec.get_prior_journals"],

  "output_schema": { "$ref": "SkillVerdict — see below" }
}
```

| Field | Required | Notes |
|---|---|---|
| `skill_id` | yes | The service holds the skill. It is named, not re-sent — re-uploading it per break pays for the same tokens every call. |
| `skill_version` | recommended | So an audit can tell which revision of the playbook produced a verdict. |
| `correlation_id` | recommended | `<session_id>:<break_id>`. Echoed back; also the idempotency key, so a retried request does not open a second session or pay twice. |
| `inputs.break_record` | yes | The only evidence the model may cite. |
| `inputs.already_established` | recommended | What the orchestrator has already ruled out. Without it the model re-derives settled checks — slower, dearer, and it may contradict them. |
| `attachments` | optional | Files the service should make readable to the model — corporate action file, pricing file, trade file. |
| `tools` | optional | MCP tools the model may call. An allowlist: the orchestrator decides which systems are in scope. |
| `output_schema` | recommended | JSON Schema for the response `output`. Generated from `SkillVerdict`. |

---

## Response

`200 OK`

```json
{
  "session_id": "svc-8f2a91",
  "correlation_id": "sess-r-1055:b-07",
  "status": "completed",

  "output": {
    "break_summary": "EM amortising bond. FO (CATS) PnL = 0. BO (MOTIF) PnL = -£247k. Break = £247k. Pull factor 1.00 -> 0.67.",
    "checks_performed": [
      { "test_id": "FO-3", "checked": "Pull factor continuity",
        "result": "Fail", "evidence": "Factor moved 1.00 -> 0.67" },
      { "test_id": "FO-6", "checked": "Redemption analysis",
        "result": "Fail", "evidence": "Redemption on CA file; expected PnL ≈ £247k; CATS produced zero" },
      { "test_id": "BO-1", "checked": "Position",
        "result": "Unable to test", "evidence": "Not required — FO root cause established at FO-6" }
    ],
    "root_cause": {
      "established": true,
      "statement": "CATS failed to generate redemption PnL on the pull factor movement.",
      "contributing": ["Pull factor update applied without redemption event"],
      "side": "FO"
    },
    "classification": {
      "category_code": "C",
      "category_name": "Redemption break",
      "secondary_code": "B",
      "deterministic": true
    },
    "verdict": "DO_NOT_POST",
    "verdict_reason": "Genuine break originating in FO. Posting would mask a CATS calculation failure.",
    "remediation": {
      "who_to_engage": ["Desk", "Product Control", "CATS support"],
      "what_to_raise": ["DQ incident with root-cause analysis request"],
      "preventative_control": "MBREC rule: factor movement present AND redemption PnL absent in FO -> auto-exception"
    },
    "end_state_validation": "No adjustment posted. Open pending FO correction.",
    "requires_sme_review": false,
    "competing_hypotheses": [],
    "unset_parameters": ["calculation_reasonable_tolerance"]
  },

  "model": "claude-opus-5-5",
  "usage": {
    "input_tokens": 1840,
    "output_tokens": 612,
    "cache_read_input_tokens": 15230
  },
  "tool_calls": [
    { "tool": "mbrec.get_prior_journals",
      "arguments": { "book": "APAC-CASH-07", "lookback_days": 60 },
      "row_count": 3, "status": "ok", "latency_ms": 212 }
  ],
  "trace_id": "phx-4c1e7d"
}
```

| Field | Required | Used for |
|---|---|---|
| `output` | **yes** | Must validate against `SkillVerdict`. The three load-bearing fields above live here. |
| `status` | yes | `completed`, `failed` or `refused` — see errors. |
| `correlation_id` | recommended | Matching the response to the break it answers. |
| `tool_calls` | recommended | The Grounding panel and the §14 checklist ("what did I check?"). Without it, what the model looked up is invisible to the audit trail. |
| `usage` | recommended | Cost per break, and whether the skill prompt is actually being cached. |
| `model`, `trace_id` | recommended | Reproducing a verdict later. |

The adapter also accepts `result` in place of `output`, or a bare
`SkillVerdict` at the top level.

---

## Errors

The orchestrator must distinguish **"could not reason"** from **"reasoned,
and the answer is escalate"**. They lead to different records.

| Situation | Response | Orchestrator does |
|---|---|---|
| Reasoned; cause not established | `200`, `status: completed`, `output.verdict: ESCALATE`, `root_cause.established: false` | Records the model's escalation and its hypotheses. |
| Model declined | `200`, `status: refused` | Escalates; flags an evidence gap. |
| Session failed | `200`, `status: failed`, `error: {code, message}` — or any `5xx` | Escalates; flags an evidence gap; retryable. |
| Bad request | `4xx` with `error.message` | Escalates; logged as a contract fault, not retried. |
| `output` fails schema validation | — | Treated as unavailable; escalates. |

In every failure case the break escalates. There is no fallback to a guess.

---

## Open questions for the session service

1. **Synchronous or asynchronous?** A judgement-based break can take a
   minute or more. If `POST /sessions` returns immediately with a
   `session_id`, the adapter needs either a `GET /sessions/{id}` to poll or a
   webhook to receive. The current adapter assumes synchronous with a 120s
   timeout.
2. **Structured output.** Can the service enforce `output_schema`, or does it
   return free text? The latter cannot drive the guards.
3. **Tool calls.** Are the MCP calls the model made returned in the response?
4. **Attachments.** By URI (the service fetches) or uploaded inline?
5. **Idempotency.** Does the service honour `Idempotency-Key`, or should the
   orchestrator deduplicate on its side?

---

## `SkillVerdict` JSON Schema

Generated from `apps/api/app/reasoning/contracts.py`. Regenerate with:

```bash
cd apps/api && .venv/bin/python -c "import json; from app.reasoning.contracts import SkillVerdict; print(json.dumps(SkillVerdict.model_json_schema(), indent=2))"
```
