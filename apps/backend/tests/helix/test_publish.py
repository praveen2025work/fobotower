"""Approval-gated write-back: only `publish`, only after a second person releases it."""

import pytest

from helix import gateway
from helix.capabilities import seed_files
from helix.entitlement import Caller
from helix.manifest import Manifest, problems
from helix.stub_connectors import finance
from tests.helix.conftest import VARIANCE

KEY = {"entity": "UK01", "period": "2026-09"}


async def _reviewed_case(api, user="alice"):
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", json={"case_key": KEY},
                           headers=api.as_user(user))).json()
    for g in case["groups"]:
        res = await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user(user),
                             json={"group_id": g["group_id"], "action": "approve",
                                   "comment": f"Agreed: {g['label']}",
                                   "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
        last = res.json()
    return last["case"]


async def _release(api, case_id, user, key="release-key-1"):
    return await api.post(f"/api/cases/{case_id}/publish", headers=api.as_user(user),
                          json={"idempotency_key": key})


async def test_reviewed_case_waits_for_a_second_person_before_writing_back(api):
    finance.PUBLISHED.clear()
    case = await _reviewed_case(api)
    assert case["status"] == "awaiting_publish"
    assert finance.PUBLISHED == []                      # nothing written yet
    assert case["publish"]["can_release"] is False      # alice reviewed it

    own = await _release(api, case["case_id"], "alice")
    assert own.status_code == 403

    ok = await _release(api, case["case_id"], "bob")
    assert ok.status_code == 201, ok.text
    done = ok.json()["case"]
    assert (done["status"], done["outcome"]) == ("completed", "published")
    assert {p["account"] for p in finance.PUBLISHED} == {g["group_key"]["account"] for g in case["groups"]}
    assert all(p["commentary"].startswith("Agreed: ") for p in finance.PUBLISHED)
    writes = [c for c in done["tool_calls"] if c["tool"] == "reporting.publish_commentary"]
    assert writes and all(c["requested_by"] == "publish" and c["allowed"] for c in writes)


async def test_release_is_idempotent_and_happens_once(api):
    finance.PUBLISHED.clear()
    case = await _reviewed_case(api)
    first = await _release(api, case["case_id"], "bob", key="same-release-key")
    again = await _release(api, case["case_id"], "bob", key="same-release-key")
    other = await _release(api, case["case_id"], "carol", key="another-key-123")
    assert first.status_code == again.status_code == 201
    assert again.json()["replayed"] is True
    assert other.status_code in (403, 409)
    assert len(finance.PUBLISHED) == len(case["groups"])


async def test_only_publish_approver_roles_can_release(api):
    case = await _reviewed_case(api)
    assert (await _release(api, case["case_id"], "carol")).status_code == 403  # owner, not FIN_REVIEWER


async def test_a_write_tool_is_refused_to_steps_and_to_the_model():
    caller = Caller("bob", frozenset({"FIN_REVIEWER"}), {"entity": frozenset({"*"})})
    args = {"entity": "UK01", "period": "2026-09", "account": "6100", "commentary": "x"}
    for requested_by in ("load", "llm"):
        ctx = gateway.CallContext(capability_id=VARIANCE, caller=caller,
                                  allowed_tools=frozenset({"reporting.publish_commentary"}),
                                  requested_by=requested_by)
        with pytest.raises(gateway.ToolDenied, match="only the publish step"):
            await gateway.call(ctx, "reporting.publish_commentary", args)
    ctx = gateway.CallContext(capability_id=VARIANCE, caller=caller,
                              allowed_tools=frozenset({"reporting.publish_commentary"}),
                              requested_by="publish")        # but no release recorded
    with pytest.raises(gateway.ToolDenied, match="after a second person approves"):
        await gateway.call(ctx, "reporting.publish_commentary", args)


def _variance(**changes) -> list[str]:
    m = next(m for m in seed_files() if m.id == VARIANCE).model_dump(by_alias=True)
    return problems(Manifest.model_validate({**m, **changes}))


def test_write_back_rules_are_validated():
    base = next(m for m in seed_files() if m.id == VARIANCE).model_dump(by_alias=True)
    assert "the run must pause before `publish` for a second approval" in _variance(
        pause_before=["review"])
    assert "`publish` must come right after `record`, last" in _variance(
        steps=["load", "compare", "group", "reason", "draft", "validate", "review", "publish", "record"])
    assert "publish.tool `gl.balances` is not a write tool" in _variance(
        publish={**base["publish"], "tool": "gl.balances"})
    reasoning = {**base["reasoning"], "tools": ["gl.journal_lines", "reporting.publish_commentary"]}
    assert ("tool `reporting.publish_commentary` writes to a bank system; only `publish` may use it"
            in _variance(reasoning=reasoning))


async def test_a_failed_write_back_is_retried_without_repeating_the_writes_that_landed(api):
    finance.PUBLISHED.clear()
    case = await _reviewed_case(api)
    failing = case["groups"][0]["group_key"]["account"]
    finance.FAIL_ACCOUNTS.add(failing)
    try:
        done = (await _release(api, case["case_id"], "bob")).json()["case"]
    finally:
        finance.FAIL_ACCOUNTS.discard(failing)
    assert (done["status"], done["outcome"]) == ("failed", "publish_failed")
    assert failing in done["error"] and done["can_retry_publish"] is True
    landed = {p["account"] for p in finance.PUBLISHED}
    assert failing not in landed and len(landed) == len(case["groups"]) - 1

    assert (await api.post(f"/api/cases/{case['case_id']}/publish/retry",
                           headers=api.as_user("alice"))).status_code == 403   # a reviewer
    res = await api.post(f"/api/cases/{case['case_id']}/publish/retry", headers=api.as_user("bob"))
    assert res.status_code == 201, res.text
    after = res.json()
    assert (after["case"]["status"], after["case"]["outcome"]) == ("completed", "published")
    assert len(after["skipped"]) == len(case["groups"]) - 1
    # every account published exactly once
    assert sorted(p["account"] for p in finance.PUBLISHED) == sorted(
        g["group_key"]["account"] for g in case["groups"])
    keys = [p["idempotency_key"] for p in finance.PUBLISHED]
    assert len(set(keys)) == len(keys) and all(k.startswith(case["case_id"] + ":") for k in keys)


async def test_retry_is_only_for_a_failed_write_back(api):
    case = await _reviewed_case(api)
    res = await api.post(f"/api/cases/{case['case_id']}/publish/retry", headers=api.as_user("bob"))
    assert res.status_code == 409
