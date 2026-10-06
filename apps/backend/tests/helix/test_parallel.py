"""Groups are reasoned several at a time (one at a time under a spend limit),
and specialists reach the Agent SDK as subagents with gateway tools only."""

import asyncio

from helix import llm
from helix.llm import ReasonRequest
from helix.llm_agent_sdk import SUBAGENT_TOOL, ClaudeAgentSdkAdapter
from tests.helix.conftest import CASH, RECON, VARIANCE


class _Slow(llm.StubLlm):
    def __init__(self):
        self.now, self.peak = 0, 0

    async def reason(self, request, tools):
        self.now += 1
        self.peak = max(self.peak, self.now)
        await asyncio.sleep(0.05)
        self.now -= 1
        return await super().reason(request, tools)


async def test_groups_are_reasoned_concurrently(api):
    slow = _Slow()
    llm._adapter = slow
    case = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                           json={"case_key": {"entity": "UK01", "date": "2026-09-30"}, "team_group": CASH})).json()
    assert len([g for g in case["groups"] if g["finding"]["decided_by"].startswith("llm")]) > 1
    assert slow.peak > 1 and case["status"] == "awaiting_review"


async def test_under_a_spend_limit_groups_go_one_at_a_time(api):
    slow = _Slow()
    llm._adapter = slow
    await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                   json={"case_key": {"entity": "UK01", "period": "2026-09"}})
    assert slow.peak == 1


async def test_specialists_become_subagents_with_only_gateway_tools():
    adapter = ClaudeAgentSdkAdapter(query_fn=lambda **k: None)
    req = ReasonRequest(capability_id=RECON, case_id="c", case_key={"book": "B", "cob": "2026-08-03"},
                        skill="Explain the breaks.", group={"group_key": {}, "items": [], "priors": []},
                        allowed_tools=["motif.booking_events"], output="verdict",
                        specialists=[{"name": "booking-events", "description": "Reads booking events",
                                      "instructions": "Find the events.", "tools": ["motif.booking_events"]}])
    opts = await adapter._options(req, tools=None)
    assert opts.tools == [SUBAGENT_TOOL] and SUBAGENT_TOOL in opts.allowed_tools
    agent = opts.agents["booking-events"]
    assert agent.tools == ["mcp__helix__motif_booking_events"] and "Agent One Finance" in agent.prompt
    assert "booking-events: Reads booking events" in opts.system_prompt
    plain = await adapter._options(ReasonRequest(**{**req.__dict__, "specialists": []}), tools=None)
    assert plain.tools == [] and plain.agents is None
