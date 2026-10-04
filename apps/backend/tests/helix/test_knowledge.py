"""The knowledge graph: priors from related decisions, reference lineage read
as of a business date, and retention with legal hold."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text

from helix import knowledge, retention
from helix.db import engine, get_session
from helix.models import Case, KgEdge, RetentionEvent, ToolCall
from tests.helix.conftest import VARIANCE

NS = "test.kg"


async def test_priors_come_from_the_same_subject_then_from_shared_entities():
    await knowledge.record_decision(NS, {"account": "6100"}, case_id="c1", group_id="g", action="approve",
                                    comment="Salaries: hiring plan", decided_by="bob",
                                    entities={"account": {"6100"}, "cost_centre": {"CC10"}})
    await knowledge.record_decision(NS, {"account": "6200"}, case_id="c2", group_id="g", action="approve",
                                    comment="Travel: offsite", decided_by="bob",
                                    entities={"account": {"6200"}, "cost_centre": {"CC10", "CC20"}})
    await knowledge.record_decision(NS, {"account": "6200"}, case_id="c3", group_id="g", action="reject",
                                    comment="wrong", decided_by="bob", entities={"cost_centre": {"CC20"}})
    priors = await knowledge.similar_decisions(
        NS, {"account": "6200"}, entities={"account": {"6200"}, "cost_centre": {"CC10", "CC20"}})
    assert [(p["case_id"], p["match"]) for p in priors] == [
        ("c2", "same subject"), ("c1", "shared cost_centre")]      # rejections never teach


async def test_priors_older_than_the_lookback_are_left_out():
    await knowledge.record_decision(NS, {"book": "B1"}, case_id="old", group_id="g", action="approve",
                                    comment="Late booking", decided_by="frank")
    await knowledge.record_decision(NS, {"book": "B1"}, case_id="new", group_id="g", action="approve",
                                    comment="Late booking again", decided_by="frank")
    async with get_session() as s:      # backdate the first decision 200 days
        await s.execute(text("UPDATE helix_kg_node SET valid_from = valid_from - interval '200 days' "
                             "WHERE namespace = :ns AND attrs->>'case_id' = 'old'"), {"ns": NS})
        await s.commit()
    within = await knowledge.similar_decisions(NS, {"book": "B1"}, lookback_days=180)
    assert [p["case_id"] for p in within] == ["new"]          # FOBO: the last 180 days only
    assert {p["case_id"] for p in await knowledge.similar_decisions(NS, {"book": "B1"})} == {"old", "new"}


async def test_recording_the_same_decision_twice_is_a_no_op():
    for _ in range(2):
        await knowledge.record_decision(NS, {"account": "1"}, case_id="c9", group_id="g", action="approve",
                                        comment="x", decided_by="bob", entities={"account": {"1"}})
    async with get_session() as s:
        n = (await s.execute(select(func.count()).select_from(KgEdge).where(
            KgEdge.namespace == NS, KgEdge.from_id == "decision:c9:g"))).scalar_one()
    assert n == 2          # explains + concerns, once each


async def test_reference_lineage_is_read_as_of_the_business_date():
    start = {"book:PRIME-MB-05", "book:PRIME-MB-01"}
    june = await knowledge.walk("fobo-reference", start, ["belongs_to"], as_of="2026-06-30")
    august = await knowledge.walk("fobo-reference", start, ["belongs_to"], as_of="2026-08-03")
    assert june["book:PRIME-MB-05"].attrs["name"] == "APAC-TREASURY"     # before the move
    assert august["book:PRIME-MB-05"].attrs["name"] == "APAC-CASH"
    teams = await knowledge.walk("fobo-reference", start, ["belongs_to", "escalates_to"], as_of="2026-06-30")
    assert {k: v.attrs["name"] for k, v in teams.items()} == {
        "book:PRIME-MB-05": "Desk", "book:PRIME-MB-01": "Operations"}
    assert await knowledge.walk("fobo-reference", {"book:NOPE"}, ["belongs_to"]) == {}


async def test_loading_reference_data_again_adds_nothing():
    async with get_session() as s:
        before = (await s.execute(select(func.count()).select_from(KgEdge))).scalar_one()
    await knowledge.seed_reference()
    async with get_session() as s:
        after = (await s.execute(select(func.count()).select_from(KgEdge))).scalar_one()
    assert before == after


# ---------- retention ----------

async def _finished_case(api) -> str:
    case = (await api.post(f"/api/capabilities/{VARIANCE}/cases", headers=api.as_user("alice"),
                           json={"case_key": {"entity": "UK01", "period": "2026-09"}})).json()
    for g in case["groups"]:
        await api.post(f"/api/cases/{case['case_id']}/decisions", headers=api.as_user("alice"),
                       json={"group_id": g["group_id"], "action": "approve",
                             "idempotency_key": f"{case['case_id']}-{g['group_id']}"})
    res = await api.post(f"/api/cases/{case['case_id']}/publish", headers=api.as_user("bob"),
                         json={"idempotency_key": "release-for-retention"})
    assert res.json()["case"]["status"] == "completed"
    return case["case_id"]


async def test_finished_cases_are_removed_after_retention_and_leave_a_record(api):
    case_id = await _finished_case(api)
    later = datetime.now(timezone.utc) + timedelta(days=2556)
    assert await retention.purge(now=datetime.now(timezone.utc)) == []          # not due yet
    assert await retention.purge(now=later, dry_run=True) == [case_id]
    assert await retention.purge(now=later) == [case_id]
    async with get_session() as s:
        assert await s.get(Case, case_id) is None
        assert (await s.execute(select(ToolCall).where(ToolCall.case_id == case_id))).first() is None
        [event] = (await s.execute(select(RetentionEvent))).scalars().all()
        assert (event.case_id, event.retention_days) == (case_id, 2555)
        taught = (await s.execute(select(KgEdge).where(KgEdge.from_id.startswith(f"decision:{case_id}:")))).first()
        assert taught is None
    async with engine.connect() as conn:
        left = (await conn.execute(text("SELECT count(*) FROM checkpoints WHERE thread_id = :t"),
                                   {"t": f"helix:{case_id}"})).scalar_one()
    assert left == 0


async def test_a_legal_hold_keeps_a_case_and_only_owners_set_it(api):
    case_id = await _finished_case(api)
    url = f"/api/cases/{case_id}/legal-hold"
    assert (await api.post(url, headers=api.as_user("alice"), json={"hold": True, "reason": "x"})).status_code == 403
    assert (await api.post(url, headers=api.as_user("carol"), json={"hold": True})).status_code == 409
    ok = await api.post(url, headers=api.as_user("carol"), json={"hold": True, "reason": "FCA enquiry 2026-114"})
    assert ok.status_code == 200 and ok.json()["legal_hold"] is True
    later = datetime.now(timezone.utc) + timedelta(days=2556)
    assert await retention.purge(now=later) == []
    await api.post(url, headers=api.as_user("carol"), json={"hold": False})
    assert await retention.purge(now=later) == [case_id]
