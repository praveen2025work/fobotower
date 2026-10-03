"""BRD → draft manifest → owner approval → a live capability, without code."""

import json

import yaml
from claude_agent_sdk import ResultMessage

from helix import authoring
from helix.entitlement import Caller

BRD = """# Monthly cost-centre variance review

Finance wants commentary on material variances to budget for each entity at
month end, grouped by account, explained from journals and budget notes, and
signed off by a preparer. Approved commentary goes to the reporting pack.
"""


async def _draft(api, user, brd=BRD):
    res = await api.post("/api/authoring/draft", json={"brd": brd}, headers=api.as_user(user))
    assert res.status_code == 200, res.text
    return res.json()


async def test_a_brd_becomes_a_live_capability_after_a_second_owner_approves(api):
    draft = await _draft(api, "carol")
    assert draft["problems"] == [] and draft["author"] == "template"
    assert draft["manifest"]["id"] == "draft.monthly-cost-centre-variance-review"
    assert draft["manifest"]["owners"]["people"] == ["carol"]

    saved = await api.post("/api/authoring/submit", headers=api.as_user("carol"),
                           json={"yaml": draft["yaml"], "note": "from BRD"})
    assert saved.status_code == 201, saved.text
    cap_id = saved.json()["capability_id"]
    assert cap_id not in {c["id"] for c in (await api.get("/api/capabilities", headers=api.as_user("alice"))).json()}

    drafts = (await api.get("/api/authoring/drafts", headers=api.as_user("bob"))).json()
    mine = next(d for d in drafts if d["capability_id"] == cap_id)
    assert mine["new"] is True and mine["can_approve"] is True

    own = await api.post(f"/api/capabilities/{cap_id}/versions/1/approve", headers=api.as_user("carol"))
    assert own.status_code == 403                                     # four-eyes
    ok = await api.post(f"/api/capabilities/{cap_id}/versions/1/approve", headers=api.as_user("bob"))
    assert ok.status_code == 200, ok.text

    live = {c["id"] for c in (await api.get("/api/capabilities", headers=api.as_user("alice"))).json()}
    assert cap_id in live
    case = await api.post(f"/api/capabilities/{cap_id}/cases", headers=api.as_user("alice"),
                          json={"case_key": {"entity": "UK01", "period": "2026-09"}})
    assert case.status_code == 201 and case.json()["status"] == "awaiting_review"


async def test_a_reconciliation_brd_starts_from_the_matching_template(api):
    draft = await _draft(api, "erin", "Daily bank statement vs ledger cash reconciliation for each entity.")
    assert "match" in draft["manifest"]["steps"] and draft["problems"] == []


async def test_a_model_draft_with_mistakes_comes_back_with_its_problems(api):
    seen = {}

    async def fake_query(*, prompt, options):
        seen["prompt"], seen["options"] = prompt, options
        bad = {"id": "fin.bad", "name": "Bad", "owners": {"people": ["carol"]},
               "case": {"key": ["entity"]}, "items": {"load": {"tool": "crm.accounts"}, "id_field": "id"},
               "steps": ["load", "group", "reason", "draft", "review", "record"],
               "review": {"roles": ["FIN_PREPARER"]}}
        yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
                            num_turns=1, session_id="s", structured_output={
                                "yaml": yaml.safe_dump(bad), "assumptions": ["no threshold given"]})

    writer = authoring.AgentSdkAuthor(query_fn=fake_query)
    carol = Caller("carol", frozenset({"HELIX_FIN_VARCOMM_OWNER"}), {"entity": frozenset({"*"})})
    out = await authoring.draft_from_brd(BRD, carol, writer=writer)
    assert "`validate` is required" in out["problems"]
    assert "tool `crm.accounts` is not an onboarded connector tool" in out["problems"]
    assert out["assumptions"] == ["no threshold given"]
    # the model drafted with the platform's real catalogue and no tools of its own
    opts = seen["options"]
    assert opts.tools == [] and opts.strict_mcp_config is True
    context = json.loads(opts.system_prompt.split("Platform context:\n", 1)[1])
    assert "gl.journal_lines" in {t["name"] for t in context["connector_tools"]}
    assert {s["name"] for s in context["core_steps"]} >= {"validate", "review", "record"}


async def test_submitting_a_manifest_with_problems_is_refused_with_them(api):
    draft = await _draft(api, "carol")
    broken = draft["yaml"].replace("- validate\n", "")
    res = await api.post("/api/authoring/submit", headers=api.as_user("carol"), json={"yaml": broken})
    assert res.status_code == 422
    assert "`validate` is required" in res.json()["detail"]["problems"]


async def test_you_cannot_submit_a_capability_you_do_not_own(api):
    draft = await _draft(api, "carol")
    res = await api.post("/api/authoring/submit", headers=api.as_user("alice"), json={"yaml": draft["yaml"]})
    assert res.status_code == 403
