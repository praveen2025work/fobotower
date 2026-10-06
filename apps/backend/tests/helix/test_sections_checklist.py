"""Answers in sections and the sign-off checklist — configured per capability.

FOBO answers in the skill's §12 sections and signs off on its §14 checklist;
variance commentary answers in its own sections with an optional checklist.
The engine is the same: a required section missing from the model's answer
sends the group to a person, and approving needs every required question
answered yes or n/a, kept on the decision."""

import uuid

from tests.helix.conftest import VARIANCE

CAP, GROUP = "break.investigation", "fobo-prime"


async def _fobo_review(api):
    res = await api.post(f"/api/capabilities/{CAP}/cases", headers=api.as_user("frank"),
                         json={"case_key": {"book": "PRIME-MB-04", "cob": "2026-09-24"}, "team_group": GROUP})
    case = res.json()
    res = await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                         json={"action": "continue", "idempotency_key": uuid.uuid4().hex})
    return res.json()


async def test_the_model_answers_in_the_skills_sections(api):
    case = await _fobo_review(api)
    aged = next(g for g in case["groups"] if g["group_key"]["category"] == "K")
    sections = {x["id"]: x for x in aged["finding"]["sections"]}
    assert list(sections) == ["root_cause", "hypotheses", "tests_not_performed", "verdict_reason",
                              "remediation", "preventative_control", "end_state"]
    assert sections["root_cause"]["label"] == "Root cause" and sections["root_cause"]["text"]
    # the playbook settles the timing break in its own words: no model sections
    timing = next(g for g in case["groups"] if g["group_key"]["category"] == "T")
    assert "sections" not in timing["finding"]


async def test_a_required_section_missing_sends_the_group_to_a_person(api, monkeypatch):
    from helix import llm

    async def silent(self, request, tools):
        return llm.ReasonResult(status="proposed", comment="Looks like timing.", model="stub",
                                sections={"root_cause": "Timing"})
    monkeypatch.setattr(llm.StubLlm, "reason", silent)
    case = await _fobo_review(api)
    aged = next(g for g in case["groups"] if g["group_key"]["category"] == "K")
    assert aged["finding"]["status"] == "escalated"
    assert aged["finding"]["reason"].startswith("MISSING_SECTION: Tests not performed, Verdict and why")


async def test_approving_needs_the_sign_off_checklist(api):
    case = await _fobo_review(api)
    g = next(g for g in case["groups"] if g["group_key"]["category"] == "T")
    known = {q["id"]: q["known"] for q in g["checklist"]}
    assert known["adjustment"].startswith("MONITOR")                  # Agent One Finance fills in what it knows
    assert known["why_checked"].startswith("T · Timing difference")
    assert "tests on" in known["what_checked"]

    def post(checklist):
        return api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"),
                        json={"group_id": g["group_id"], "action": "approve", "comment": "ok",
                              "checklist": checklist, "idempotency_key": uuid.uuid4().hex})

    res = await post([{"id": "what_checked", "answer": "yes"}])
    assert res.status_code == 409 and "Who must be engaged afterwards?" in res.json()["detail"]
    res = await post([{"id": "nonsense", "answer": "yes"}])
    assert res.status_code == 409 and "not on the checklist" in res.json()["detail"]
    answers = [{"id": q["id"], "answer": "n/a" if q["id"] == "control" else "yes"} for q in g["checklist"]]
    answers[2]["note"] = "MB Rec history shows it cleared twice before"
    res = await post(answers)
    assert res.status_code == 201, res.text
    decided = next(x for x in res.json()["case"]["groups"] if x["group_id"] == g["group_id"])["decision"]
    kept = {a["id"]: a for a in decided["checklist"]}
    assert kept["evidence"]["note"] == "MB Rec history shows it cleared twice before"
    assert kept["control"]["answer"] == "n/a"
    # rejecting never needs the checklist
    other = next(x for x in case["groups"] if x["group_id"] != g["group_id"])
    rej = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"),
                         json={"group_id": other["group_id"], "action": "reject", "comment": "not this",
                               "idempotency_key": uuid.uuid4().hex})
    assert rej.status_code == 201, rej.text


async def test_variance_commentary_has_its_own_sections_and_an_optional_checklist(api):
    res = await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                         json={"case_key": {"entity": "UK01", "period": "2026-09"}})
    case = res.json()
    model = next(g for g in case["groups"] if (g["finding"] or {}).get("decided_by", "").startswith("llm"))
    assert [x["id"] for x in model["finding"]["sections"]] == ["driver", "one_off", "action"]
    assert next(q for q in model["checklist"] if q["id"] == "driver_evidenced")["known"] == model["finding"]["sections"][0]["text"]
    res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("bob"),
                         json={"group_id": model["group_id"], "action": "approve", "comment": "ok",
                               "idempotency_key": uuid.uuid4().hex})
    assert res.status_code == 201, res.text                          # optional: not required to approve


def test_checklist_prefill_must_name_something_helix_knows():
    from helix.capabilities import seed_files
    from helix.manifest import Manifest, problems
    base = next(m for m in seed_files() if m.id == VARIANCE).model_dump()
    base["review"]["checklist"] = [{"id": "x", "label": "X?", "prefill": "nowhere"}]
    assert any("prefill: `nowhere`" in p for p in problems(Manifest.model_validate(base)))
