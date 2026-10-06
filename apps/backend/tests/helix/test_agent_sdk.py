"""The Claude Agent SDK adapter, without calling the API.

`query()` is replaced by a stand-in that behaves like the model: it connects to
the adapter's real in-process SDK MCP server over the MCP protocol, calls tools
(which go through the Agent One Finance gateway), and returns a ResultMessage. Everything
but the model itself is the production path.
"""

import json

from claude_agent_sdk import ResultMessage
from mcp.client import Client

from helix import llm
from helix.llm_agent_sdk import ClaudeAgentSdkAdapter
from tests.helix.conftest import VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


def _result(output: dict | None, *, is_error=False, errors=None) -> ResultMessage:
    return ResultMessage(subtype="error_during_execution" if is_error else "success",
                         duration_ms=1200, duration_api_ms=900, is_error=is_error, num_turns=3,
                         session_id="sess-1", total_cost_usd=0.0123,
                         usage={"input_tokens": 1500, "output_tokens": 220},
                         structured_output=output, errors=errors)


class FakeModel:
    """Records each query and plays one scripted 'model' behaviour."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    async def __call__(self, *, prompt, options):
        self.calls.append({"prompt": json.loads(prompt), "options": options})
        server = options.mcp_servers["helix"]["instance"]
        async with Client(server) as mcp:
            output = await self.behaviour(mcp, json.loads(prompt))
        yield output


async def _cite_first_journal(mcp, prompt):
    account = prompt["group"]["group_key"]["account"]
    res = await mcp.call_tool("gl_journal_lines", {**prompt["case"], "account": account})
    lines = json.loads(res.content[0].text)["rows"]
    top = max(lines, key=lambda r: r["amount"])
    return _result({"status": "proposed",
                    "comment": f"Largest journal {top['journal_id']} for {top['amount']:,.2f} drives account {account}."})


async def _open(api):
    res = await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                         headers=api.as_user("alice"))
    assert res.status_code == 201, res.text
    return res.json()


async def test_the_agent_gets_only_the_capabilitys_tools_and_helix_rules():
    fake = FakeModel(_cite_first_journal)
    adapter = ClaudeAgentSdkAdapter(query_fn=fake)
    from helix.llm import ReasonRequest

    request = ReasonRequest(
        capability_id=VARIANCE, case_id="c1", case_key=KEY, skill="Explain variances.",
        group={"group_id": "6100", "label": "account 6100", "group_key": {"account": "6100"},
               "total": 1.0, "count": 1, "items": [], "priors": []},
        allowed_tools=["gl.journal_lines", "budget.plan_lines"], output="commentary")
    options = await adapter._options(request, tools=None)
    assert options.tools == []                      # no built-in Claude Code tools
    assert options.strict_mcp_config is True        # no other MCP servers
    assert options.allowed_tools == ["mcp__helix__gl_journal_lines",
                                     "mcp__helix__budget_plan_lines"]
    assert options.permission_mode == "dontAsk"
    assert options.system_prompt.startswith("Explain variances.")
    assert "figures that cannot be traced" in options.system_prompt
    assert options.output_format["type"] == "json_schema"
    assert options.model == "claude-opus-5-5"


async def test_model_tool_calls_go_through_the_gateway_and_its_figures_are_validated(api):
    fake = FakeModel(_cite_first_journal)
    llm._adapter = ClaudeAgentSdkAdapter(query_fn=fake)
    case = await _open(api)

    assert {g["finding"]["status"] for g in case["groups"]} == {"proposed"}
    finding = case["groups"][0]["finding"]
    assert finding["decided_by"] == "llm:agent-sdk"
    assert finding["usage"]["cost_usd"] == 0.0123 and finding["usage"]["turns"] == 3
    model_calls = [c for c in case["tool_calls"] if c["requested_by"] == "llm"]
    assert model_calls and all(c["tool"] == "gl.journal_lines" and c["allowed"] for c in model_calls)
    # the prompt carried the group, its items and the case key — nothing else
    sent = fake.calls[0]["prompt"]
    assert sent["case"] == KEY and sent["items"] and "group_key" in sent["group"]


async def test_an_invented_figure_from_the_model_is_escalated(api):
    async def invent(mcp, prompt):
        return _result({"status": "proposed", "comment": "Driven by a 4,444,444.44 accrual."})
    llm._adapter = ClaudeAgentSdkAdapter(query_fn=FakeModel(invent))
    case = await _open(api)
    assert all(g["finding"]["reason"].startswith("UNGROUNDED_FIGURE: 4,444,444.44")
               for g in case["groups"])


async def test_data_outside_the_callers_scope_is_refused_to_the_model(api):
    seen = {}

    async def snoop(mcp, prompt):
        res = await mcp.call_tool("gl_journal_lines", {"entity": "US01", "period": "2026-09",
                                                       "account": "6100"})
        seen["error"], seen["text"] = res.is_error, res.content[0].text
        return _result({"status": "escalated", "comment": "", "reason": "no evidence"})

    llm._adapter = ClaudeAgentSdkAdapter(query_fn=FakeModel(snoop))
    case = await _open(api)
    assert seen["error"] is True and "not entitled to entity=US01" in seen["text"]
    refused = [c for c in case["tool_calls"] if not c["allowed"]]
    assert refused and refused[0]["requested_by"] == "llm"
    assert {g["finding"]["status"] for g in case["groups"]} == {"escalated"}


async def test_an_agent_error_escalates_the_group(api):
    async def fail(mcp, prompt):
        return _result(None, is_error=True, errors=["overloaded"])
    llm._adapter = ClaudeAgentSdkAdapter(query_fn=FakeModel(fail))
    case = await _open(api)
    assert all("REASONER_ERROR" in g["finding"]["reason"] and "overloaded" in g["finding"]["reason"]
               for g in case["groups"])


async def test_selected_by_configuration(monkeypatch):
    from helix import config

    monkeypatch.setenv("HELIX_LLM_ADAPTER", "agent_sdk")
    monkeypatch.setenv("HELIX_LLM_MODEL", "claude-sonnet-5-5")
    config.settings.cache_clear()
    try:
        llm._adapter = None
        adapter = llm.llm()
        assert adapter.name == "agent-sdk" and adapter.model == "claude-sonnet-5-5"
    finally:
        config.settings.cache_clear()
