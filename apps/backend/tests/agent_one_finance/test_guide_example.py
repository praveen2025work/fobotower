"""The guide's example (docs/agent-one-finance/guide/example) is real configuration:
the capability and its group pass every platform check, as they did when the
example was set up, and the steps the README shows are the steps it runs. The
named P&L variant (named-pnl/) is one case across several master books."""

import uuid
from pathlib import Path

import pytest
import yaml

from agent_one_finance import groups
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.stub_connectors import finance

EXAMPLE = Path(__file__).resolve().parents[4] / "docs" / "agent-one-finance" / "guide" / "example"
# The example lives in the AOF repository's docs; a repo that takes only the code skips this file.
pytestmark = pytest.mark.skipif(not EXAMPLE.is_dir(), reason="no docs/agent-one-finance/guide/example here")


def _load(name: str) -> dict:
    return yaml.safe_load((EXAMPLE / name).read_text())


def test_the_example_capability_and_group_pass_every_check():
    m = Manifest.model_validate(_load("capability.yaml"))
    assert problems(m) == []
    assert groups.check(m, _load("group.yaml")) == []


def test_the_example_runs_the_steps_its_readme_shows():
    m = Manifest.model_validate(_load("capability.yaml"))
    assert m.steps == ["load", "enrich", "classify", "group", "reason", "draft", "validate", "review", "record"]
    assert m.pause_before == ["reason", "review"]
    assert m.owners.four_eyes


def test_the_named_pnl_example_passes_every_check():
    m = Manifest.model_validate(_load("named-pnl/capability.yaml"))
    assert problems(m) == []
    assert groups.check(m, _load("named-pnl/group.yaml")) == []
    assert m.case.key == ["named_pnl", "cob"] and m.items.id_field == "break_id"


async def _ok(res, status=200):
    assert res.status_code == status, res.text
    return res.json()


async def test_a_named_pnl_is_one_case_across_its_master_books(api):
    cap = "fobo.named.pnl"
    v = (await _ok(await api.post("/api/authoring/submit", headers=api.as_user("frank"), json={
        "yaml": (EXAMPLE / "named-pnl" / "capability.yaml").read_text()}), 201))["version"]
    await _ok(await api.post(f"/api/capabilities/{cap}/versions/{v}/approve", headers=api.as_user("gina")))
    gv = (await _ok(await api.post(f"/api/capabilities/{cap}/groups", headers=api.as_user("frank"),
                                   json={"config": _load("named-pnl/group.yaml")}), 201))["version"]
    await _ok(await api.post(f"/api/capabilities/{cap}/groups/prime-financing/versions/{gv}/approve",
                             headers=api.as_user("gina")))
    key = {"named_pnl": "PRIME-FINANCING-EMEA", "cob": "2026-10-08"}
    case = await _ok(await api.post(f"/api/capabilities/{cap}/cases", headers=api.as_user("aof-scheduler"),
                                    json={"case_key": key, "team_group": "prime-financing"}), 201)
    assert case["status"] == "paused_before_reason", case.get("error")

    # every master book's breaks, each once: the same instrument may break in two books
    books = finance.NAMED_PNLS["PRIME-FINANCING-EMEA"]
    expected = [r for b in books for r in finance.mbrec_breaks(b, key["cob"])["rows"]]
    assert sorted(i["item_id"] for i in case["items"]) == sorted(r["break_id"] for r in expected)
    assert {i["book"] for i in case["items"]} == set(books)
    # joined on book and instrument: each break has its own book's snapshot
    snap = {(r["book"], r["instrument"]): r
            for r in finance.break_snapshots_named_pnl(key["named_pnl"], key["cob"])["rows"]}
    assert all(i["fo_version"] == snap[(i["book"], i["instrument"])]["fo_version"] for i in case["items"])

    # the master books are on the case, including their MB Rec status; a book
    # MB Rec has not finished is held (R5) while the others are worked
    master = next(d for d in case["datasets"] if d["name"] == "master_books")
    status = {r["book"]: r["status"] for r in master["rows"]}
    assert sorted(status) == books and "In Progress" in status.values()
    assert all((i["category"] == "W") == (status[i["book"]] != "Complete") for i in case["items"])

    # one case, one sign-off: the controller continues it and decides each group once
    after = await _ok(await api.post(f"/api/cases/{case['case_id']}/gates/reason", headers=api.as_user("frank"),
                                     json={"action": "continue", "idempotency_key": uuid.uuid4().hex}))
    assert after["status"] == "awaiting_review" and after["can_decide"]
    for g in after["groups"]:
        answers = [{"id": q["id"], "answer": "yes"} for q in g["checklist"] or []]
        await _ok(await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("frank"), json={
            "group_id": g["group_id"], "action": "approve", "comment": "Agreed.", "checklist": answers,
            "confirmed": bool((g["finding"] or {}).get("requires_confirmation")),
            "idempotency_key": uuid.uuid4().hex}), 201)
    done = await _ok(await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("frank")))
    assert done["status"] == "completed"
    # gina's named P&L is PRIME-FINANCING-EMEA; she sees this case, not one for another named P&L
    assert (await api.get(f"/api/cases/{case['case_id']}", headers=api.as_user("gina"))).status_code == 200
    other = await _ok(await api.post(f"/api/capabilities/{cap}/cases", headers=api.as_user("aof-scheduler"), json={
        "case_key": {"named_pnl": "PRIME-FINANCING-US", "cob": "2026-10-08"}, "team_group": "prime-financing"}), 201)
    assert (await api.get(f"/api/cases/{other['case_id']}", headers=api.as_user("gina"))).status_code == 404
    assert (await api.get(f"/api/cases/{other['case_id']}", headers=api.as_user("frank"))).status_code == 200
