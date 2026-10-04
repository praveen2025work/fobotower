"""Ask about a case (grounded, audited, protected) and its run history."""

from helix import llm
from tests.helix.conftest import FOBO, RECON, VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _open(api, user="alice"):
    return (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user(user))).json()


async def test_asking_about_a_group_answers_from_the_case_and_audits_lookups(api):
    case = await _open(api)
    g = case["groups"][0]
    account = g["group_key"]["account"]
    res = await api.post(f"/api/cases/{case['case_id']}/ask", headers=api.as_user("alice"),
                         json={"question": f"Why is account {account} different?"})
    assert res.status_code == 201, res.text
    answer = res.json()["answer"]
    assert g["label"] in answer["text"] and "Not decided yet" in answer["text"]
    assert answer["meta"]["unverified_figures"] == []          # every figure traces to the run
    assert answer["meta"]["tool_calls"]                          # the stub looked things up
    after = (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("alice"))).json()
    assert any(t["requested_by"] == "chat" for t in after["tool_calls"])
    thread = (await api.get(f"/api/cases/{case['case_id']}/messages", headers=api.as_user("alice"))).json()
    assert [m["role"] for m in thread] == ["user", "assistant"]


async def test_chat_is_for_people_who_can_see_the_case(api):
    case = await _open(api)
    res = await api.post(f"/api/cases/{case['case_id']}/ask", headers=api.as_user("viewer"),
                         json={"question": "anything?"})
    assert res.status_code == 404


async def test_untraceable_figures_in_an_answer_are_flagged(api):
    class Inventive(llm.StubLlm):
        async def ask(self, request, tools):
            return llm.AskResult(answer="It is 123,456.78 off.", model="x")
    case = await _open(api)
    llm._adapter = Inventive()
    res = await api.post(f"/api/cases/{case['case_id']}/ask", headers=api.as_user("alice"),
                         json={"question": "How far off?"})
    assert res.json()["answer"]["meta"]["unverified_figures"] == [123456.78]


async def test_the_model_never_sees_a_pseudonymized_counterparty(api):
    seen = {}

    class Spy(llm.StubLlm):
        async def ask(self, request, tools):
            seen["q"], seen["ctx"] = request.question, str(request.context)
            return llm.AskResult(answer="ok", model="spy")
    cash = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("dan"),
                           json={"case_key": {"entity": "UK01", "date": "2026-09-30"},
                                 "team_group": "cash-bank-ledger"})).json()
    llm._adapter = Spy()
    await api.post(f"/api/cases/{cash['case_id']}/ask", headers=api.as_user("dan"),
                   json={"question": "What about ACME BANK?"})
    assert "ACME BANK" not in seen["ctx"]


async def test_history_shows_each_step_and_where_people_came_in(api):
    case = await _open(api)
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
    hist = (await api.get(f"/api/cases/{case['case_id']}/history", headers=api.as_user("alice"))).json()
    ran = [h["step"] for h in hist if h["event"] == "step"]
    assert ran[:4] == ["load", "compare", "group", "reason"] and "record" in ran
    assert any(h["event"] == "people" and "decisions" in h["step"] for h in hist)
    assert hist[-1]["event"] == "waiting" and hist[-1]["step"] == "publish"
    # the state at the review pause, exactly as the reviewer saw it
    review = next(h for h in hist if h["event"] == "step" and h["step"] == "review")
    state = (await api.get(f"/api/cases/{case['case_id']}/history/{review['checkpoint_id']}",
                           headers=api.as_user("alice"))).json()
    assert state["next"] == ["review"] and state["findings"] and state["decisions"] == []


async def test_history_of_a_fobo_case_includes_the_playbook_steps(api):
    case = (await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("frank"),
                           json={"case_key": {"book": "PRIME-MB-01", "cob": "2026-08-03"},
                                 "team_group": FOBO})).json()
    hist = (await api.get(f"/api/cases/{case['case_id']}/history", headers=api.as_user("frank"))).json()
    assert [h["step"] for h in hist if h["event"] == "step"][:5] == [
        "match", "enrich", "resolve", "classify", "group"]
