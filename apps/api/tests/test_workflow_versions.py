"""Four-eyes workflow versions: seeded from YAML, changed only by a second approver."""

import asyncio

import pytest
from sqlalchemy import text

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import dump_config, read_workflow

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")
ASHA = Caller(staff_id="asha", roles=["PC"], entity_scope=["LE-APAC-01"], region="APAC")
FRONT_OFFICE = Caller(staff_id="fo-user", roles=["FO"], entity_scope=["LE-APAC-01"], region="APAC")


def _lookback(days: int) -> dict:
    raw = dump_config(read_workflow())
    raw["settings"]["gather"]["priors_lookback_days"] = days
    return raw


async def _draft(raw=None, *, by=PRAVEEN, based_on=1, note="change"):
    async with get_session() as s:
        return await versions.create_draft(
            s, raw=raw or _lookback(90), note=note, based_on=based_on, caller=by)


async def _approve(number, *, by=ASHA, key=None):
    async with get_session() as s:
        return await versions.approve(s, number, caller=by, key=key or f"key-{number}")


async def _reject(number, *, by=ASHA, reason="not now"):
    async with get_session() as s:
        return await versions.reject(s, number, caller=by, reason=reason)


async def test_the_yaml_seeds_version_one_as_active():
    async with get_session() as s:
        cur = await versions.active(s)
        row = await versions.get(s, 1)
    assert cur.number == 1 and cur.config == read_workflow()
    assert row.drafted_by == "system" and "fobo-investigation.yaml" in row.note


async def test_concurrent_first_reads_seed_once():
    async def read():
        async with get_session() as s:
            return (await versions.active(s)).number

    assert await asyncio.gather(*(read() for _ in range(5))) == [1] * 5
    async with get_session() as s:
        assert len(await versions.list_versions(s)) == 1


async def test_a_draft_is_saved_with_who_and_why():
    d = await _draft(note="Lookback 180→90 days")
    assert (d.number, d.status, d.based_on, d.drafted_by) == (2, "draft", 1, "praveen")
    assert d.config["settings"]["gather"]["priors_lookback_days"] == 90


async def test_an_invalid_draft_lists_every_problem():
    raw = _lookback(90)
    raw["steps"].remove("reason")
    raw["steps"].remove("validate")
    with pytest.raises(versions.Invalid) as exc:
        await _draft(raw)
    assert any("'reason' cannot be removed" in e for e in exc.value.errors)
    assert any("'validate' cannot be removed" in e for e in exc.value.errors)


async def test_a_draft_needs_a_note():
    with pytest.raises(versions.Invalid, match="note"):
        await _draft(note="   ")


async def test_a_note_over_the_limit_is_refused():
    with pytest.raises(versions.Invalid, match="500"):
        await _draft(note="x" * 501)


async def test_only_product_control_can_draft():
    with pytest.raises(versions.NotAllowed):
        await _draft(by=FRONT_OFFICE)


async def test_a_draft_must_be_based_on_a_real_version():
    with pytest.raises(versions.NotFound):
        await _draft(based_on=99)


async def test_approval_activates_the_draft_and_supersedes_the_old_one():
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert (await versions.active(s)).number == 2
        assert (await versions.get(s, 1)).status == "superseded"
        row = await versions.get(s, 2)
    assert row.decided_by == "asha" and row.decided_at is not None


async def test_the_drafter_cannot_approve_their_own_draft():
    d = await _draft(by=PRAVEEN)
    with pytest.raises(versions.NotAllowed, match="second"):
        await _approve(d.number, by=PRAVEEN)


async def test_only_product_control_can_approve():
    d = await _draft()
    with pytest.raises(versions.NotAllowed):
        await _approve(d.number, by=FRONT_OFFICE)


async def test_a_stale_draft_cannot_be_approved():
    first, second = await _draft(_lookback(90)), await _draft(_lookback(30))
    await _approve(first.number)
    with pytest.raises(versions.Conflict, match="v2 went live"):
        await _approve(second.number)


async def test_a_version_cannot_be_approved_twice():
    d = await _draft()
    await _approve(d.number, key="a")
    with pytest.raises(versions.Conflict):
        await _approve(d.number, key="b")


async def test_an_idempotency_key_is_used_once():
    first = await _draft()
    await _approve(first.number, key="same")
    second = await _draft(based_on=first.number)
    with pytest.raises(versions.Conflict, match="already recorded"):
        await _approve(second.number, key="same")


async def test_an_approval_needs_a_key():
    d = await _draft()
    with pytest.raises(versions.Invalid):
        await _approve(d.number, key="  ")


async def test_two_approvals_racing_leave_exactly_one_active():
    a, b = await _draft(_lookback(90)), await _draft(_lookback(30))
    results = await asyncio.gather(
        _approve(a.number, key="ka"), _approve(b.number, key="kb"), return_exceptions=True)
    assert sum(isinstance(r, versions.Conflict) for r in results) == 1
    async with get_session() as s:
        assert [v.status for v in await versions.list_versions(s)].count("active") == 1


async def test_a_rejection_needs_a_reason():
    d = await _draft()
    with pytest.raises(versions.Invalid):
        await _reject(d.number, reason=" ")


async def test_a_rejection_keeps_who_and_why():
    d = await _draft()
    await _reject(d.number, reason="too aggressive")
    async with get_session() as s:
        row = await versions.get(s, d.number)
    assert (row.status, row.reject_reason, row.decided_by) == ("rejected", "too aggressive", "asha")


async def test_the_drafter_may_withdraw_their_own_draft():
    d = await _draft(by=PRAVEEN)
    assert (await _reject(d.number, by=PRAVEEN)).status == "rejected"


async def test_a_decided_version_cannot_be_rejected():
    d = await _draft()
    await _approve(d.number)
    with pytest.raises(versions.Conflict):
        await _reject(d.number)


async def test_nothing_is_ever_deleted_and_pending_counts_drafts():
    a = await _draft()
    b = await _draft(_lookback(30))
    await _reject(b.number)
    await _draft(_lookback(45))
    async with get_session() as s:
        assert [v.number for v in await versions.list_versions(s)] == [4, 3, 2, 1]
        assert await versions.pending_count(s) == 2
    assert a.number == 2


async def test_an_approval_is_seen_by_the_next_read_without_a_restart():
    async with get_session() as s:
        assert (await versions.active(s)).config.settings.gather.priors_lookback_days == 180
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert (await versions.active(s)).config.settings.gather.priors_lookback_days == 90


async def test_a_run_without_a_version_reads_version_one():
    d = await _draft()
    await _approve(d.number)
    async with get_session() as s:
        assert await versions.config_for(s, None) == read_workflow()


async def test_the_view_is_json_ready():
    d = await _draft()
    v = versions.view(d)
    assert v["number"] == 2 and isinstance(v["drafted_at"], str)
    assert list(v["config"]) == ["version", "name", "steps", "pause_before", "settings"]
    assert "config" not in versions.view(d, with_config=False)


async def test_approve_re_reads_the_row_when_another_session_rejected_it_first():
    """A session that loaded the draft before a competing decision must not
    judge that decision against its now-stale, pre-loaded copy."""
    d = await _draft()
    async with get_session() as s1:
        preloaded = await versions.get(s1, d.number)
        assert preloaded.status == "draft"
        await _reject(d.number)
        with pytest.raises(versions.Conflict):
            await versions.approve(s1, d.number, caller=ASHA, key="race-approve")
    async with get_session() as s:
        row = await versions.get(s, d.number)
    assert row.status == "rejected"


async def test_reject_re_reads_the_row_when_another_session_approved_it_first():
    d = await _draft()
    async with get_session() as s1:
        preloaded = await versions.get(s1, d.number)
        assert preloaded.status == "draft"
        await _approve(d.number)
        with pytest.raises(versions.Conflict):
            await versions.reject(s1, d.number, caller=ASHA, reason="too late")
    async with get_session() as s:
        actives = [v.number for v in await versions.list_versions(s) if v.status == "active"]
    assert actives == [d.number]


async def test_active_raises_a_clear_error_when_none_is_active():
    async with get_session() as s:
        await versions.ensure_seeded(s)
        await s.execute(text("UPDATE workflow_version SET status = 'superseded' WHERE status = 'active'"))
        await s.commit()
    async with get_session() as s:
        with pytest.raises(versions.Conflict):
            await versions.active(s)
