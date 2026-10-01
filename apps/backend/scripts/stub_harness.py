"""A stub agent harness for demos and manual tests — not a reasoner.

    cd apps/backend && .venv/bin/uvicorn scripts.stub_harness:app --port 8200

Implements contract v2 (docs/integration/session-service-contract.md) the way
the bank's harness would be called: `POST /sessions` starts a session and
answers `running`; `GET /sessions/{id}` returns it as it stands. In the
background the session does what a real agent does with its tools — it
connects to the orchestrator's MCP server with the session's bearer token and
reads the breaks (`fobo_list_breaks`, then `fobo_break_detail` for each sample
break) — and then completes with a fixed RecVerdict.

The verdict is deterministic and identical for every pattern. It exists so the
orchestrator's start/poll loop, MCP auth, per-call audit and verdict mapping
can be exercised end to end without a model. Nothing it says about a break is
a judgement, and it must never be pointed at real breaks.

Sessions live in memory; restarting the stub forgets them, which the
orchestrator sees as a failed poll and escalates.
"""

import asyncio
import itertools
import sys
from typing import Any

import httpx2
from fastapi import FastAPI, HTTPException
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from fobo.reasoning.contracts import CATEGORY_NAMES, RecVerdict

TOOL_PREFIX = "mcp__fobo__"
LIST_PAGE_SIZE = 100
CATEGORY = "G"

app = FastAPI(title="FOBO stub agent harness")

_sessions: dict[str, dict[str, Any]] = {}
_counter = itertools.count(1)
# Strong references, so a running session's task is not garbage collected.
_tasks: set[asyncio.Task] = set()


class StubError(Exception):
    """A tool call the stub could not complete."""


@app.post("/sessions")
async def start_session(request: dict) -> dict:
    session_id = f"stub-{next(_counter)}"
    _sessions[session_id] = {
        "session_id": session_id,
        "correlation_id": request.get("correlation_id"),
        "status": "running",
    }
    task = asyncio.create_task(run_session(session_id, request))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return _sessions[session_id]


@app.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    payload = _sessions.get(session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"no session {session_id}")
    return payload


async def run_session(
    session_id: str, request: dict, *, http_client: httpx2.AsyncClient | None = None
) -> dict:
    """Read the breaks through MCP (when offered), then complete or fail.

    `http_client` is for tests that serve the MCP app in-process; it must
    already carry the bearer header.
    """
    try:
        tool_calls: list[dict] = []
        patterns = request["inputs"]["patterns"]
        mcp = request.get("mcp")
        if mcp:
            read = await _read_breaks(mcp, patterns, tool_calls, http_client)
        else:
            read = sum(len(p["sample"]) for p in patterns)
        output = _verdict(patterns, read, mcp is not None)
        _sessions[session_id] = {
            **_sessions.get(session_id, {"session_id": session_id}),
            "status": "completed",
            "output": output,
            "tool_calls": tool_calls,
            "usage": {},
            "total_cost_usd": 0,
            "num_turns": len(tool_calls) + 1,
        }
    except Exception as exc:  # noqa: BLE001 — reported as the session's failure
        _sessions[session_id] = {
            **_sessions.get(session_id, {"session_id": session_id}),
            "status": "failed",
            "error": {"code": "stub_error", "message": f"{type(exc).__name__}: {exc}"},
        }
    return _sessions[session_id]


async def _read_breaks(
    mcp: dict, patterns: list[dict], tool_calls: list[dict],
    http_client: httpx2.AsyncClient | None,
) -> int:
    """List the session's breaks, then fetch each sample break's detail.
    Returns how many break records were read in full."""
    owned = http_client is None
    if owned:
        http_client = create_mcp_http_client(
            headers={"Authorization": f"Bearer {mcp['token']}"}
        )
    try:
        async with Client(streamable_http_client(mcp["url"], http_client=http_client)) as client:
            await _call(client, tool_calls, "fobo_list_breaks", {"page_size": LIST_PAGE_SIZE})
            sample_ids = [b["break_id"] for p in patterns for b in p["sample"]]
            for break_id in sample_ids:
                await _call(client, tool_calls, "fobo_break_detail", {"break_id": break_id})
            return len(sample_ids)
    finally:
        if owned:
            await http_client.aclose()


async def _call(client: Client, tool_calls: list[dict], name: str, arguments: dict) -> dict:
    tool_calls.append({"tool": f"{TOOL_PREFIX}{name}", "arguments": arguments})
    result = await client.call_tool(name, arguments)
    if result.is_error:
        text = " ".join(getattr(c, "text", "") for c in result.content)
        raise StubError(f"{name} failed: {text}")
    return result.structured_content or {}


def _verdict(patterns: list[dict], read: int, via_mcp: bool) -> dict:
    source = "through MCP" if via_mcp else "from the request's samples"
    output = {
        "summary": (
            f"Stub harness: read {read} break(s) {source} across "
            f"{len(patterns)} pattern(s). Fixed demo verdict, not a judgement."
        ),
        "patterns": [_pattern_verdict(p) for p in patterns],
        "exceptions": [],
    }
    # Fail here rather than hand the orchestrator something it will reject.
    return RecVerdict.model_validate(output).model_dump(mode="json")


def _pattern_verdict(pattern: dict) -> dict:
    code = pattern["pattern_code"]
    return {
        "pattern_code": code,
        "break_summary": (
            f"{pattern['break_count']} break(s) in pattern {code} "
            f"({pattern.get('label', '')}), total {pattern.get('total_amount')}."
        ),
        "checks_performed": [{
            "test_id": "BO-6",
            "checked": "Corporate action reflected in MOTIF",
            "result": "Fail",
            "evidence": "Stub harness: fixed demo result, no evidence was weighed.",
        }],
        "root_cause": {
            "established": True,
            "statement": "Stub harness: corporate action not reflected in Back Office.",
            "contributing": [],
            "side": "BO",
        },
        "classification": {
            "category_code": CATEGORY,
            "category_name": CATEGORY_NAMES[CATEGORY],
            "secondary_code": None,
            "deterministic": False,
        },
        "verdict": "POST",
        "verdict_reason": "Stub harness demo verdict. A real harness reasons from the evidence.",
        "remediation": {
            "who_to_engage": ["Product Control"],
            "what_to_raise": ["Confirm the corporate action with the BO team"],
            "preventative_control": None,
        },
        "end_state_validation": "Stub harness: not validated; the investigation remains open.",
        "requires_sme_review": True,
        "competing_hypotheses": [],
        "unset_parameters": [],
    }


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8200
    uvicorn.run(app, host="127.0.0.1", port=port)
