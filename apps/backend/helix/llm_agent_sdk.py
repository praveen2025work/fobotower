"""LLM adapter on the Claude Agent SDK — the office's LLM interaction layer.

`HELIX_LLM_ADAPTER=agent_sdk` selects it. One `reason()` call is one Agent SDK
`query()` for one proposal group:

  system prompt   the capability's `reasoning.skill`, plus Helix's output rules
  prompt          the case key, the group (key, totals, items) and its priors, as JSON
  tools           ONLY the capability's allowed connector tools, served by an
                  in-process SDK MCP server whose handlers call the Helix gateway
                  (`tools`) — so allow-list, data scope, audit row and figure
                  validation apply to every call the model makes. Built-in Claude
                  Code tools are switched off (`tools=[]`) and no other MCP server
                  is loaded (`strict_mcp_config=True`).
  output          structured: {status, comment, reason}

Office: if your internal wrapper around the Agent SDK differs (gateway URL,
auth, model routing), keep this class's contract — `name` and
`async reason(request, tools) -> ReasonResult` — and change only `_run`.

Settings (environment): HELIX_LLM_MODEL (default claude-opus-5-5),
HELIX_LLM_EFFORT (default high), HELIX_LLM_MAX_TURNS (default 12),
HELIX_LLM_MAX_BUDGET_USD (optional per-group cost ceiling).
"""

import json
import os
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from helix import gateway
from helix.llm import ReasonRequest, ReasonResult, ToolInvoker
from helix.observability import AGENT, set_output, span

SERVER = "helix"

OUTPUT_RULES = """
You are working inside Helix, a governed workflow. Rules that override anything above:
- Use only the tools provided. Every figure you state must come from a tool result
  or from the case data in the prompt; figures that cannot be traced are rejected
  and the group goes to a person.
- If the evidence does not support a conclusion, set status to "escalated" and say
  why in `reason`. Do not guess.
- Reply with the structured result only: status, comment (what you conclude, for a
  reviewer, citing the figures), reason (only when escalating).
""".strip()

# Specialists (manifest reasoning.specialists) become Agent SDK subagents. Their
# tools are the same gateway-backed MCP tools; the main agent reaches them
# through the SDK's subagent tool — the only built-in tool Helix enables.
SUBAGENT_TOOL = os.getenv("HELIX_SUBAGENT_TOOL") or "Agent"

SPECIALIST_RULES = """
You are a specialist inside Helix, a governed workflow. Use only the tools provided;
every figure you report must come from a tool result. Report what you found and the
figures, briefly, to the agent that asked you.
""".strip()


def _specialists_note(specialists: list[dict]) -> str:
    lines = [f"- {sp['name']}: {sp['description']}" for sp in specialists]
    return "Specialists you may hand part of the work to:\n" + "\n".join(lines)


RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["proposed", "escalated"]},
        "comment": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["status", "comment"],
    "additionalProperties": False,
}

QueryFn = Callable[..., AsyncIterator[Any]]


def _schema(request: ReasonRequest) -> dict:
    """The result schema; with a playbook, the model also proposes a verdict
    from the playbook's list (guards in code still apply after)."""
    if not request.verdicts:
        return RESULT_SCHEMA
    return {**RESULT_SCHEMA, "properties": {
        **RESULT_SCHEMA["properties"], "verdict": {"type": "string", "enum": list(request.verdicts)}}}


def _sdk_tool_name(qualified: str) -> str:
    """'gl.journal_lines' -> 'gl_journal_lines'. MCP tool names cannot contain dots,
    and `__` is the separator in `mcp__<server>__<tool>`, so it is avoided too."""
    return re.sub(r"_{2,}", "_", re.sub(r"[^A-Za-z0-9_-]", "_", qualified))


def _gateway_tool(qualified: str, schema: dict, description: str, tools: ToolInvoker):
    @tool(_sdk_tool_name(qualified), description or f"Helix connector tool {qualified}", schema)
    async def handler(args: dict) -> dict:
        try:
            result = await tools(qualified, dict(args))
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            # The model sees the refusal and can adapt; the gateway already audited it.
            return {"content": [{"type": "text", "text": f"Refused: {e}"}], "is_error": True}
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    return handler


def _prompt(request: ReasonRequest) -> str:
    return json.dumps({
        "capability": request.capability_id,
        "case": request.case_key,
        "group": {k: request.group[k] for k in ("label", "group_key", "total", "count")
                  if k in request.group},
        "items": request.group.get("items", []),
        "approved_explanations_for_similar_groups": request.group.get("priors", []),
        **({"notes_from_people": request.notes} if request.notes else {}),
        **({"reviewer_note": request.reviewer_note,
            "previous_finding": request.previous_finding} if request.reviewer_note else {}),
        "output": request.output,
    }, default=str, indent=1)


def _parse(result: ResultMessage | None) -> dict:
    if result is None:
        raise RuntimeError("the agent returned no result")
    if result.is_error:
        raise RuntimeError(f"agent error ({result.subtype}): {'; '.join(result.errors or [])}")
    out = result.structured_output
    if out is None and result.result:
        out = json.loads(result.result)
    if not isinstance(out, dict) or out.get("status") not in ("proposed", "escalated"):
        raise RuntimeError(f"agent result does not match the schema: {out!r}")
    return out


def _parse_any(result: ResultMessage | None) -> dict:
    """A structured result as a dict, whatever its schema (used by authoring)."""
    if result is None:
        raise RuntimeError("the agent returned no result")
    if result.is_error:
        raise RuntimeError(f"agent error ({result.subtype}): {'; '.join(result.errors or [])}")
    out = result.structured_output
    if out is None and result.result:
        out = json.loads(result.result)
    if not isinstance(out, dict):
        raise RuntimeError(f"agent result is not an object: {out!r}")
    return out


class ClaudeAgentSdkAdapter:
    name = "agent-sdk"

    def __init__(self, *, model: str | None = None, effort: str | None = None,
                 max_turns: int | None = None, max_budget_usd: float | None = None,
                 query_fn: QueryFn | None = None):
        env = os.getenv
        self.model = model or env("HELIX_LLM_MODEL") or "claude-opus-5-5"
        self.effort = effort or env("HELIX_LLM_EFFORT") or "high"
        self.max_turns = max_turns or int(env("HELIX_LLM_MAX_TURNS") or 12)
        budget = max_budget_usd if max_budget_usd is not None else env("HELIX_LLM_MAX_BUDGET_USD")
        self.max_budget_usd = float(budget) if budget else None
        self._query = query_fn or query  # tests inject a stand-in

    async def _options(self, request: ReasonRequest, tools: ToolInvoker) -> ClaudeAgentOptions:
        reg = gateway.registry()
        sdk_tools = []
        for qualified in request.allowed_tools:
            found = reg.tool(qualified)
            description = found[2].description if found else ""
            schema = await gateway.tool_schema(qualified)
            sdk_tools.append(_gateway_tool(qualified, schema, description, tools))
        names = {q: f"mcp__{SERVER}__{_sdk_tool_name(q)}" for q in request.allowed_tools}
        agents = {sp["name"]: AgentDefinition(
            description=sp["description"],
            prompt=f"{sp['instructions'].strip()}\n\n{SPECIALIST_RULES}",
            tools=[names[t] for t in sp.get("tools", []) if t in names],
            model=self.model) for sp in request.specialists}
        return ClaudeAgentOptions(
            system_prompt=f"{request.skill.strip()}\n\n{OUTPUT_RULES}"
            + (f"\n\n{_specialists_note(request.specialists)}" if agents else ""),
            # no built-in Claude Code tools — only the subagent tool when there are specialists
            tools=[SUBAGENT_TOOL] if agents else [],
            agents=agents or None,
            mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=sdk_tools)},
            strict_mcp_config=True,         # and no other MCP servers
            allowed_tools=[f"mcp__{SERVER}__{t.name}" for t in sdk_tools] + ([SUBAGENT_TOOL] if agents else []),
            permission_mode="dontAsk",      # headless: anything not allowed is denied
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            model=self.model,
            effort=self.effort,
            output_format={"type": "json_schema", "schema": _schema(request)},
        )

    async def _run(self, prompt: str, options: ClaudeAgentOptions) -> ResultMessage | None:
        result = None
        async for message in self._query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message
        return result

    async def reason(self, request: ReasonRequest, tools: ToolInvoker) -> ReasonResult:
        with span("llm.agent_sdk", kind=AGENT, input=_prompt(request),
                  case_id=request.case_id, capability_id=request.capability_id,
                  group_id=request.group.get("group_id"), model=self.model,
                  tools=",".join(request.allowed_tools)) as sp:
            options = await self._options(request, tools)
            result = await self._run(_prompt(request), options)
            out = _parse(result)
            usage = {
                "input_tokens": (result.usage or {}).get("input_tokens"),
                "output_tokens": (result.usage or {}).get("output_tokens"),
                "cost_usd": result.total_cost_usd,
                "turns": result.num_turns,
                "duration_ms": result.duration_ms,
                "session_id": result.session_id,
            }
            set_output(sp, out)
            for k, v in usage.items():
                if v is not None:
                    sp.set_attribute(f"helix.llm.{k}", v)
            return ReasonResult(status=out["status"], comment=out.get("comment", ""),
                                reason=out.get("reason") or None, model=self.model, usage=usage,
                                verdict=out.get("verdict") or None)


ASK_RULES = """
You are answering a reviewer's question about one case inside Helix, a governed
workflow. Answer from the case data in the prompt and the tools provided only.
Every figure you state must come from them; say plainly when the data does not
answer the question. Be brief and specific. Reply with the structured result only.
""".strip()

ASK_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


async def _ask(self: "ClaudeAgentSdkAdapter", request, tools):
    from helix.llm import AskResult

    reg = gateway.registry()
    sdk_tools = []
    for qualified in request.allowed_tools:
        found = reg.tool(qualified)
        sdk_tools.append(_gateway_tool(qualified, await gateway.tool_schema(qualified),
                                       found[2].description if found else "", tools))
    options = ClaudeAgentOptions(
        system_prompt=f"{request.skill.strip()}\n\n{ASK_RULES}",
        tools=[], mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=sdk_tools)},
        strict_mcp_config=True, allowed_tools=[f"mcp__{SERVER}__{t.name}" for t in sdk_tools],
        permission_mode="dontAsk", max_turns=self.max_turns, max_budget_usd=self.max_budget_usd,
        model=self.model, effort=self.effort,
        output_format={"type": "json_schema", "schema": ASK_SCHEMA})
    prompt = json.dumps({"case": request.case_key, "question": request.question,
                         "earlier_turns": request.history, "case_data": request.context},
                        default=str, indent=1)
    with span("llm.agent_sdk.ask", kind=AGENT, input=prompt, case_id=request.case_id,
              capability_id=request.capability_id, model=self.model) as sp:
        result = await self._run(prompt, options)
        out = _parse_any(result)
        set_output(sp, out)
        return AskResult(answer=str(out.get("answer", "")), model=self.model,
                         usage={"cost_usd": result.total_cost_usd, "turns": result.num_turns})


ClaudeAgentSdkAdapter.ask = _ask

JUDGE_SCHEMA = {"type": "object", "properties": {"score": {"type": "number", "minimum": 0, "maximum": 1},
                                                 "reason": {"type": "string"}},
                "required": ["score"], "additionalProperties": False}


async def _judge(self: "ClaudeAgentSdkAdapter", expected: str, actual: str) -> float:
    """LLM-as-judge for eval runs: does the new explanation say what the
    approved one said (same cause, same figures, same action)? 0–1."""
    options = ClaudeAgentOptions(
        system_prompt=("You compare two explanations of the same accounting difference. Score 1 when they "
                       "give the same cause, figures and action; 0 when they disagree; in between for partly. "
                       "Reply with the structured result only."),
        tools=[], strict_mcp_config=True, permission_mode="dontAsk", max_turns=2,
        model=self.model, effort="low", output_format={"type": "json_schema", "schema": JUDGE_SCHEMA})
    out = _parse_any(await self._run(json.dumps({"approved": expected, "new": actual}), options))
    return max(0.0, min(1.0, float(out["score"])))


ClaudeAgentSdkAdapter.judge = _judge


def describe(adapter: ClaudeAgentSdkAdapter) -> dict:
    """What `/api/platform` reports about the configured adapter."""
    return {"name": adapter.name, "model": adapter.model, "effort": adapter.effort,
            "max_turns": adapter.max_turns, "max_budget_usd": adapter.max_budget_usd}

