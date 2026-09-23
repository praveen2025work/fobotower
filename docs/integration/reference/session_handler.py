"""Reference handler for the session service — Claude Agent SDK.

Shows how one FOBO break request from the orchestrator maps onto an Agent
SDK session. It is a reference, not the service: the service already exists
and owns its own HTTP layer, auth and deployment.

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
]


def build_options(request: dict) -> ClaudeAgentOptions:
    """One orchestrator request -> one set of session options."""
    return ClaudeAgentOptions(
        # The skill is loaded from <cwd>/.claude/skills/fobo-investigation/.
        cwd=os.environ["SESSION_SERVICE_ROOT"],
        setting_sources=["project"],
        skills=[request["skill_id"]],
        # The orchestrator's knowledge graph and engines, as MCP tools.
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
        # Validated against SkillVerdict; the SDK re-prompts on mismatch.
        output_format={"type": "json_schema", "schema": request["output_schema"]},
        max_turns=request.get("max_turns", 20),
    )


def build_prompt(request: dict) -> str:
    """Dispatch the skill by name, with the break as the evidence."""
    return (
        f"/{request['skill_id']}\n\n"
        "Break record:\n```json\n"
        + json.dumps(request["inputs"], indent=2, default=str)
        + "\n```"
    )


async def handle(request: dict) -> dict:
    """Run one session and shape the response the orchestrator expects."""
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
        return _failed(request, "skill_not_loaded", f"{request['skill_id']} not discovered")
    if result is None:
        return _failed(request, "no_result", "session ended without a result")
    if result.subtype == "error_max_structured_output_retries":
        return _failed(request, "schema_retries_exhausted", "no valid SkillVerdict produced")
    # success with no structured_output is a failure too (Agent SDK docs).
    if result.subtype != "success" or not result.structured_output:
        return _failed(request, result.subtype or "unknown", "no structured output")

    return {
        "session_id": result.session_id,
        "correlation_id": request.get("correlation_id"),
        "status": "completed",
        "output": result.structured_output,
        "tool_calls": tool_calls,
        "usage": result.usage,
        "total_cost_usd": result.total_cost_usd,
        "num_turns": result.num_turns,
    }


def _failed(request: dict, code: str, message: str) -> dict:
    return {
        "correlation_id": request.get("correlation_id"),
        "status": "failed",
        "error": {"code": code, "message": message},
    }
