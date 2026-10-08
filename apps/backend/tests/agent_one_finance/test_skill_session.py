"""The skill session: one `agent` step runs a skill in one model session.

MB Rec's event opens a case; the model gets the skill (read from a file), the
case key and the allowed tools, reads the data itself through the gateway and
returns a result per break. The gates the platform adds (validate, review,
record) still apply: figures must come from tool results, a person decides."""

import dataclasses
import json
import uuid

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, ToolUseBlock, UserMessage
from mcp.client import Client

from agent_one_finance import llm
from agent_one_finance.capabilities import seed_files
from agent_one_finance.llm import SessionResult
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.stub_connectors import finance

CAP = "break.investigation.skill"
KEY = {"book": "PRIME-MB-04", "cob": "2026-09-24"}


def _base() -> dict:
    return next(m for m in seed_files() if m.id == CAP).model_dump(by_alias=True)


async def _event(api, monkeypatch, key=KEY):
    from agent_one_finance.config import settings
    from agent_one_finance.web import main
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))
    res = await api.post("/api/events", headers={"X-AOF-Event-Secret": "evt"},
                         json={"capability_id": CAP, "case_key": key, "event": "MB Rec end of day"})
    assert res.status_code == 201, res.text
    return (await api.get(f"/api/cases/{res.json()['case_id']}", headers=api.as_user("frank"))).json()


def test_one_step_is_a_whole_workflow_and_the_skill_comes_from_its_file():
    m = Manifest.model_validate(_base())
    assert m.steps == ["agent", "draft", "validate", "review", "record"]     # the gates are added
    assert m.reasoning.skill_file == "skills/fobo-investigation-skill.md"
    assert "FO PnL = BO PnL + Δ FOBO Adjustments" in m.reasoning.skill   # the file's text is stored
    assert problems(m) == []


def test_a_session_cannot_be_mixed_with_load_or_reason_and_needs_its_skill():
    raw = _base()
    m = Manifest.model_validate({**raw, "steps": ["load", "agent"], "items": {**raw["items"],
                                 "load": {"tool": "mbrec.breaks", "args": {"book": "$case.book"}}}})
    assert any("`agent` finds the items" in p for p in problems(m))
    from agent_one_finance.capabilities import with_skill_file
    lost = with_skill_file({**raw["reasoning"], "skill_file": "../../etc/passwd"})
    assert lost["skill"] == ""                                               # never outside the config folder
    found = problems(Manifest.model_validate({**raw, "reasoning": lost}))
    assert any("skill_file `../../etc/passwd` was not read" in p for p in found)


async def test_mb_recs_event_runs_the_skill_in_one_session(api, monkeypatch):
    case = await _event(api, monkeypatch)
    assert case["status"] == "awaiting_review", case.get("error")
    breaks = finance.mbrec_breaks(**KEY)["rows"]
    assert sorted(i["instrument"] for i in case["items"]) == sorted(b["instrument"] for b in breaks)
    assert len(case["groups"]) == len(breaks)                       # one decision per break
    # every system call was the session's, through the gateway; nothing was loaded by a rule step
    assert {c["tool"] for c in case["tool_calls"]} >= {"mbrec.breaks"}
    assert not {c["requested_by"] for c in case["tool_calls"]} & {"load", "enrich"}
    # the stub gives the first verdict offered (ESCALATE), so every break goes to a person
    assert {g["finding"]["verdict"] for g in case["groups"]} == {"ESCALATE"}
    assert {g["finding"]["status"] for g in case["groups"]} == {"escalated"}
    assert all(g["finding"]["sections"][0]["id"] == "root_cause" for g in case["groups"])
    assert "investigated" in case["draft"]["summary"]
    calls = [t for t in case["draft"]["session"]["transcript"] if t["kind"] == "tool_call"]
    assert [t["tool"] for t in calls] == [c["tool"] for c in case["tool_calls"]]   # every call, in one session
    for g in case["groups"]:
        res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"),
                             json={"group_id": g["group_id"], "action": "approve", "comment": "checked",
                                   "idempotency_key": uuid.uuid4().hex})
        assert res.status_code in (200, 201), res.text
    done = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("frank"))).json()
    assert done["status"] == "completed"


class _Model:
    """A stand-in for a real session: reads MB Rec's breaks through the tools
    and answers three of them — right, with an invented figure, with a verdict
    it was not offered."""
    name = "fake"

    async def investigate(self, request, tools):
        rows = (await tools("mbrec.breaks", dict(request.case_key)))["rows"]
        a, b, c = rows[:3]
        return SessionResult(summary="Three breaks looked at.", model="fake", results=[
            {"id": a["instrument"], "status": "proposed", "verdict": "MONITOR",
             "comment": f"Timing: difference {a['difference']:,.2f} clears next COB.",
             "sections": {"root_cause": "Late booking."}, "fields": {"difference": a["difference"]}},
            {"id": b["instrument"], "status": "proposed", "verdict": "POST",
             "comment": "Post 987,654.32.", "sections": {"root_cause": "Mapping."},
             "fields": {"difference": 123456.78}},
            {"id": c["instrument"], "status": "proposed", "verdict": "WRITE_OFF",
             "comment": "Write it off.", "sections": {"root_cause": "Old."}}])


async def test_figures_must_come_from_tools_and_verdicts_from_the_list(api, monkeypatch):
    monkeypatch.setattr(llm, "_adapter", _Model())
    case = await _event(api, monkeypatch)
    rows = finance.mbrec_breaks(**KEY)["rows"]
    f = {g["group_key"]["instrument"]: g["finding"] for g in case["groups"]}
    assert (f[rows[0]["instrument"]]["status"], f[rows[0]["instrument"]]["verdict"]) == ("proposed", "MONITOR")
    bad = f[rows[1]["instrument"]]
    assert bad["status"] == "escalated" and "987,654.32" in bad["reason"] and "123,456.78" in bad["reason"]
    assert f[rows[2]["instrument"]]["reason"].startswith("NO_VALID_VERDICT")
    assert [c["tool"] for c in case["tool_calls"]] == ["mbrec.breaks"]


class _ReasonOnly:
    """An office adapter with `reason` only: the session runs as one group."""
    name = "office"

    async def reason(self, request, tools):
        await tools("mbrec.breaks", dict(request.case_key))
        return llm.ReasonResult(status="proposed", comment="All breaks are timing.", verdict="MONITOR",
                                sections={"root_cause": "Late bookings."})


async def test_an_adapter_without_sessions_answers_for_the_whole_case(api, monkeypatch):
    monkeypatch.setattr(llm, "_adapter", _ReasonOnly())
    case = await _event(api, monkeypatch)
    assert case["status"] == "awaiting_review", case.get("error")
    [g] = case["groups"]
    assert (g["group_id"], g["finding"]["verdict"], g["finding"]["status"]) == ("all", "MONITOR", "proposed")


async def test_the_agent_sdk_runs_one_session_with_the_skill_and_the_gateway_tools(api, monkeypatch):
    from agent_one_finance.llm_agent_sdk import ClaudeAgentSdkAdapter
    calls = []

    async def fake(*, prompt, options):
        calls.append({"prompt": json.loads(prompt), "options": options})
        async with Client(options.mcp_servers["aof"]["instance"]) as mcp:
            res = await mcp.call_tool("mbrec_breaks", json.loads(prompt)["case"])
            first = json.loads(res.content[0].text)["rows"][0]
        # what the SDK streams back: the model's words and tool call, then the tool's answer
        yield AssistantMessage(content=[TextBlock("I will read MB Rec's breaks first."),
                                        ToolUseBlock("t1", "mcp__aof__mbrec_breaks", json.loads(prompt)["case"])],
                               model="m")
        yield UserMessage(content=[ToolResultBlock("t1", [{"type": "text", "text": res.content[0].text}])])
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=4,
                            session_id="s", total_cost_usd=0.02, usage={"input_tokens": 1, "output_tokens": 1},
                            structured_output={"summary": "One break.", "results": [
                                {"id": first["instrument"], "status": "proposed", "verdict": "MONITOR",
                                 "comment": f"Difference {first['difference']:,.2f} is timing.",
                                 "sections": {"root_cause": "Timing."},
                                 "fields": {"difference": first["difference"]}}]})

    monkeypatch.setattr(llm, "_adapter", ClaudeAgentSdkAdapter(query_fn=fake))
    case = await _event(api, monkeypatch)
    [g] = case["groups"]
    assert g["finding"]["verdict"] == "MONITOR" and g["finding"]["status"] == "proposed"
    opts = calls[0]["options"]
    assert "FO PnL = BO PnL" in opts.system_prompt and "one result per item" in opts.system_prompt
    assert opts.max_turns == 40 and opts.tools == []
    schema = opts.output_format["schema"]["properties"]["results"]["items"]["properties"]
    assert schema["verdict"]["enum"][0] == "ESCALATE" and "root_cause" in schema["sections"]["properties"]
    assert [c["tool"] for c in case["tool_calls"]] == ["mbrec.breaks"]       # through the gateway, audited
    session = case["draft"]["session"]                                     # the conversation is kept on the case
    assert (session["session_id"], session["turns"], session["skill_file"]) == ("s", 4, "skills/fobo-investigation-skill.md")
    kinds = [(t["role"], t["kind"]) for t in session["transcript"]]
    assert kinds == [("user", "prompt"), ("model", "text"), ("model", "tool_call"), ("tool", "tool_result"),
                     ("model", "answer")]
    assert session["transcript"][2]["tool"] == "mbrec_breaks" and session["transcript"][3]["rows"] == len(finance.mbrec_breaks(**KEY)["rows"])
