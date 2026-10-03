"""The model proposes; code decides what reaches a person."""

from helix import llm
from helix.llm import ReasonResult
from tests.helix.conftest import VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _open(api):
    res = await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                         headers=api.as_user("alice"))
    assert res.status_code == 201, res.text
    return res.json()


class Inventive:
    name = "inventive"

    async def reason(self, request, tools):
        return ReasonResult(status="proposed", comment="Driven by a 987,654.32 accrual.")


class Broken:
    name = "broken"

    async def reason(self, request, tools):
        raise TimeoutError("model did not answer")


class Snooping:
    """Asks for a tool the capability never granted it."""
    name = "snooping"

    async def reason(self, request, tools):
        await tools("ledger.postings", {"entity": "UK01", "date": "2026-09-30"})
        return ReasonResult(status="proposed", comment="ok")


async def test_a_figure_no_tool_returned_is_escalated_not_shown_as_a_conclusion(api):
    llm._adapter = Inventive()
    case = await _open(api)
    for g in case["groups"]:
        assert g["finding"]["status"] == "escalated"
        assert g["finding"]["reason"].startswith("UNGROUNDED_FIGURE: 987,654.32")


async def test_figures_the_tools_returned_pass_validation(api):
    llm._adapter = llm.StubLlm()
    case = await _open(api)
    assert all(g["finding"]["status"] == "proposed" for g in case["groups"])


async def test_with_no_reasoner_everything_the_rules_cannot_settle_goes_to_people(api):
    llm._adapter = llm.NoLlm()
    case = await _open(api)
    assert {g["finding"]["reason"] for g in case["groups"]} == {"NO_REASONER"}
    assert case["status"] == "awaiting_review"


async def test_a_failing_model_escalates_instead_of_failing_the_case(api):
    llm._adapter = Broken()
    case = await _open(api)
    assert case["status"] == "awaiting_review"
    assert all(g["finding"]["reason"].startswith("REASONER_ERROR") for g in case["groups"])


async def test_the_model_cannot_reach_tools_it_was_not_given(api):
    llm._adapter = Snooping()
    case = await _open(api)
    assert all(g["finding"]["reason"].startswith("TOOL_ERROR") for g in case["groups"])
    refused = [c for c in case["tool_calls"] if not c["allowed"]]
    assert refused and refused[0]["requested_by"] == "llm"


async def test_an_office_adapter_plugs_in_by_import_path(monkeypatch):
    from helix import config

    monkeypatch.setenv("HELIX_LLM_ADAPTER", "tests.helix.test_reasoning:Inventive")
    config.settings.cache_clear()
    try:
        llm._adapter = None
        assert llm.llm().name == "inventive"
    finally:
        config.settings.cache_clear()
