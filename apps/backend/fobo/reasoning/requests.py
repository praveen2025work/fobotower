"""The contract v2 request, built as a pure function.

Kept apart from the HTTP adapter because both the adapter and the Reason
step's orchestration need it, and because it is the one place the shape of
what the agent is told lives. It reads the environment at call time so a
deployment can switch MCP on without a restart of anything but the config.
"""

import os

from fobo.reasoning.contracts import RecVerdict

# The orchestrator's graph and engines, as the model sees them.
FOBO_MCP_TOOLS = tuple(
    f"mcp__fobo__{name}"
    for name in (
        "fobo_list_tests",
        "fobo_evidence_required",
        "fobo_required_on_fail",
        "fobo_unset_policies",
        "fobo_book_context",
        "fobo_similar_breaks",
        "fobo_list_breaks",
        "fobo_break_detail",
    )
)


def build_request(
    *,
    correlation_id: str,
    rec: dict,
    patterns: list[dict],
    already_established: dict,
    mcp_token: str,
) -> dict:
    """One L4 rec run, one session. The skill is named, not inlined: the
    service holds it on disk, and re-sending it per run would pay for the
    same tokens every time. `mcp_token` is minted per agent session, so a
    leaked token cannot outlive the run it was issued for."""
    request = {
        # Must match the `name` in skills/fobo-investigation/SKILL.md.
        "skill_id": os.getenv("FOBO_SESSION_SKILL_ID", "fobo-investigation"),
        "correlation_id": correlation_id,
        "inputs": {
            "rec": rec,
            "patterns": patterns,
            "already_established": already_established,
        },
        "output_schema": RecVerdict.model_json_schema(),
    }
    # Only offer the graph as tools when there is one to offer. Naming an
    # unreachable MCP server would fail the session for no benefit.
    mcp_url = os.getenv("FOBO_MCP_URL")
    if mcp_url:
        request["mcp"] = {"url": mcp_url, "token": mcp_token}
        request["tools"] = list(FOBO_MCP_TOOLS)
    return request
