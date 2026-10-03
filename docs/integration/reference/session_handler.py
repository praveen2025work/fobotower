"""Reference handler for the session service — Claude Agent SDK, contract v2.

Shows how one FOBO request — one L4 rec run: its patterns, a sample of breaks
per pattern, and the per-session MCP token — maps onto one Agent SDK session.
It is a reference, not the service: the service already exists and owns its
own HTTP layer, auth, deployment and the start-then-poll wrapper
(POST /sessions answers `running`; GET /sessions/{id} returns what `handle`
returns once it finishes).

Verified against claude-agent-sdk 0.2.158. Every option and message field
used here was read from the installed package, not recalled.
"""

import json
import os

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    ToolUseBlock,
    query,
)

SKILL_NAME = "fobo-investigation"

# MCP tools are exposed to the model as mcp__<server>__<tool>.
FOBO_TOOLS = [
    "mcp__fobo__fobo_list_tests",
    "mcp__fobo__fobo_evidence_required",
    "mcp__fobo__fobo_required_on_fail",
    "mcp__fobo__fobo_similar_breaks",
    "mcp__fobo__fobo_book_context",
    "mcp__fobo__fobo_unset_policies",
    "mcp__fobo__fobo_list_breaks",
    "mcp__fobo__fobo_break_detail",
]


def build_options(request: dict) -> ClaudeAgentOptions:
    """One orchestrator request -> one set of session options."""
    return ClaudeAgentOptions(
        # The skill is loaded from <cwd>/.claude/skills/fobo-investigation/.
        cwd=os.environ["SESSION_SERVICE_ROOT"],
        setting_sources=["project"],
        skills=[request["skill_id"]],
        # The orchestrator's knowledge graph and this run's breaks, as MCP
        # tools. The token is minted for this session and dies with it.
        mcp_servers={
            "fobo": {
                "type": "http",
                "url": request["mcp"]["url"],
                "headers": {"Authorization": f"Bearer {request['mcp']['token']}"},
            }
        },
        # An allowlist: the orchestrator decides which systems are in scope.
        # "Skill" must be listed when an explicit tool list is given.
        allowed_tools=["Skill", "Read", *request.get("tools", FOBO_TOOLS)],
        # Validated against RecVerdict; the SDK re-prompts on mismatch.
        output_format={"type": "json_schema", "schema": request["output_schema"]},
        # A whole rec: enough turns to page through the breaks.
        max_turns=request.get("max_turns", 60),
    )


def build_prompt(request: dict) -> str:
    """Dispatch the skill by name, with the rec run as the evidence: the rec,
    its patterns with sample breaks, and what the rules already settled."""
    return (
        f"/{request['skill_id']}\n\n"
        "L4 rec run:\n```json\n"
        + json.dumps(request["inputs"], indent=2, default=str)
        + "\n```"
    )


async def handle(request: dict, session_id: str) -> dict:
    """Run one session to the end and shape the response the orchestrator
    polls for: session_id, status, output (a RecVerdict), tool_calls."""
    tool_calls: list[dict] = []
    skill_loaded = None
    result: ResultMessage | None = None

    async for message in query(prompt=build_prompt(request), options=build_options(request)):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            # Fail loudly if the skill did not load: without it the model
            # reasons from nothing, and the verdict would look normal.
            skill_loaded = request["skill_id"] in message.data.get("skills", [])
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tool_calls.append({"tool": block.name, "arguments": block.input})
        elif isinstance(message, ResultMessage):
            result = message

    if skill_loaded is False:
        return _failed(request, session_id, "skill_not_loaded", f"{request['skill_id']} not discovered")
    if result is None:
        return _failed(request, session_id, "no_result", "session ended without a result")
    if result.subtype == "error_max_structured_output_retries":
        return _failed(request, session_id, "schema_retries_exhausted", "no valid RecVerdict produced")
    # success with no structured_output is a failure too (Agent SDK docs).
    if result.subtype != "success" or not result.structured_output:
        return _failed(request, session_id, result.subtype or "unknown", "no structured output")

    return {
        # The id the orchestrator polls with, not the SDK's own.
        "session_id": session_id,
        "correlation_id": request.get("correlation_id"),
        "status": "completed",
        "output": result.structured_output,
        "tool_calls": tool_calls,
        "usage": result.usage,
        "total_cost_usd": result.total_cost_usd,
        "num_turns": result.num_turns,
    }


def _failed(request: dict, session_id: str, code: str, message: str) -> dict:
    return {
        "session_id": session_id,
        "correlation_id": request.get("correlation_id"),
        "status": "failed",
        "error": {"code": code, "message": message},
    }
