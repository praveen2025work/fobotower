"""The FOBO skill simulation: one data set built around the FOBO Investigation
Skill v1.0 (stub_connectors/fobo_simulation.py), run two ways.

  single step   break.investigation.skill: `steps: [agent]`, one session reads
                everything through the MCP tools and decides each break
  multi step    break.investigation + fobo-prime: load, enrich, algorithm
                evidence, playbook, a tollgate, the model for judgement groups

The model is the skill simulator (stub_connectors/fobo_skill_simulator.py): a
deterministic stand-in that follows the skill exactly, so the expected answers
are fixed."""

import dataclasses
import uuid

import pytest

from agent_one_finance import llm
from agent_one_finance.stub_connectors import fobo_simulation as sim
from agent_one_finance.stub_connectors.fobo_skill_simulator import FoboSkillSimulator

COB = sim.SIM_COB


@pytest.fixture(autouse=True)
def simulator(monkeypatch):
    monkeypatch.setattr(llm, "_adapter", FoboSkillSimulator())


async def _event(api, monkeypatch, capability, book, group=None):
    from agent_one_finance.config import settings
    from agent_one_finance.web import main
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))
    body = {"capability_id": capability, "case_key": {"book": book, "cob": COB}}
    if group:
        body["team_group"] = group
    res = await api.post("/api/events", headers={"X-AOF-Event-Secret": "evt"}, json=body)
    assert res.status_code == 201, res.text
    return (await api.get(f"/api/cases/{res.json()['case_id']}", headers=api.as_user("frank"))).json()


def _expected(book):
    return {b["instrument"]: b["expected"] for b in sim.BREAKS[book]}


async def test_single_step_decides_every_break_as_the_skill_does(api, monkeypatch):
    case = await _event(api, monkeypatch, "break.investigation.skill", "PRIME-SIM-01")
    assert case["status"] == "awaiting_review", case.get("error")
    got = {g["group_key"]["instrument"]: g["finding"] for g in case["groups"]}
    items = {i["instrument"]: i for i in case["items"]}
    for ins, exp in _expected("PRIME-SIM-01").items():
        assert got[ins]["verdict"] == exp["verdict"], ins
        assert items[ins]["category"] == exp["category"], ins
        assert not (got[ins].get("reason") or "").startswith("UNGROUNDED"), (ins, got[ins]["reason"])
    session = case["draft"]["session"]
    tools = [t["tool"] for t in session["transcript"] if t["kind"] == "tool_call"]
    assert tools[:4] == ["mbrec.book_status", "mbrec.breaks", "cats.pnl_components", "motif.pnl_components"]
    assert {"secref.corporate_actions", "secref.bond_metadata", "mbrec.break_history", "cats.trades"} <= set(tools)
    emb = next(g for g in case["groups"] if g["group_key"]["instrument"] == "EMB AMORT 2031")["finding"]
    assert [s["id"] for s in emb["sections"]][:3] == ["break_summary", "checks", "root_cause"]
    assert "FO-6" in next(s["text"] for s in emb["sections"] if s["id"] == "checks")


async def test_single_step_holds_an_incomplete_book(api, monkeypatch):
    case = await _event(api, monkeypatch, "break.investigation.skill", "PRIME-SIM-02")
    assert {g["finding"]["verdict"] for g in case["groups"]} == {"ESCALATE"}
    tools = [t["tool"] for t in case["draft"]["session"]["transcript"] if t["kind"] == "tool_call"]
    assert tools == ["mbrec.book_status", "mbrec.breaks"]          # R5: nothing else is read


async def test_multi_step_settles_the_deterministic_breaks_and_asks_for_the_rest(api, monkeypatch):
    case = await _event(api, monkeypatch, "break.investigation", "PRIME-SIM-01", "fobo-prime")
    assert case["status"] == "paused_before_reason", case.get("error")
    after = (await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                            json={"action": "continue", "idempotency_key": uuid.uuid4().hex})).json()
    assert after["status"] == "awaiting_review", after.get("error")
    items = {i["instrument"]: i for i in after["items"]}
    by_cat = {(g["group_key"]["category"], g["group_key"]["side"]): g["finding"] for g in after["groups"]}
    assert items["EMB AMORT 2031"]["category"] == "C" and by_cat[("C", "FO")]["verdict"] == "DO_NOT_POST"
    assert items["UST 2.5 2029"]["category"] == "R" and by_cat[("R", "BO")]["verdict"] == "CORRECT_AND_REPOST"
    assert items["XYZ STRUCT NOTE"]["category"] == "F" and by_cat[("F", "BO")]["verdict"] == "DO_NOT_POST"
    assert items["BUND 0 2030"]["category"] == "J" and by_cat[("J", "BO")]["verdict"] == "POST"
    assert items["IRS 7Y GBP"]["category"] == "D" and by_cat[("D", "BO")]["verdict"] == "POST"
    # no cause check explains these three: one judgement group, the model looks, a person decides
    assert {i for i, it in items.items() if it["category"] == "H"} == {"GILT 4.25 2045", "ARG 2035", "CORP 5.1 2028"}
    assert by_cat[("H", "UNKNOWN")]["decided_by"].startswith("llm")
    assert by_cat[("H", "UNKNOWN")]["verdict"] == "ESCALATE"


async def test_multi_step_holds_an_incomplete_book(api, monkeypatch):
    case = await _event(api, monkeypatch, "break.investigation", "PRIME-SIM-02", "fobo-prime")
    after = (await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                            json={"action": "continue", "idempotency_key": uuid.uuid4().hex})).json()
    assert {i["category"] for i in after["items"]} == {"W"}
    assert {g["finding"]["verdict"] for g in after["groups"]} == {"ESCALATE"}
