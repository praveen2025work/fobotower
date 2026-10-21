"""FOBO by group and region: one event per FOBO group (Rates 500081, FI Credit 500082),
region and COB opens one task that reconciles every book of that group in that region
— Rates EMEA, Rates APAC and Rates AMER are three tasks, each with its own breaks,
proposals and sign-off. Also: the books in the stand-in CATS and MOTIF and in the
reference data, and what loading reference data and reading many tasks need."""

import dataclasses

import pytest
from sqlalchemy import select, update

from agent_one_finance import knowledge
from agent_one_finance.db import get_session
from agent_one_finance.models import KgNode
from agent_one_finance.stub_connectors import fobo_books

RECON, GROUP = "recon.investigation", "cats-vs-motif"
COB = "2026-10-20"
RATES, FIC = "500081", "500082"


@pytest.fixture
def events(monkeypatch):
    from agent_one_finance.config import settings
    from agent_one_finance.web import main
    monkeypatch.setattr(main, "settings", lambda: dataclasses.replace(settings(), event_secret="evt"))


async def _event(api, group, region, cob=COB, group_name=None):
    """FOBO's feed: "FOBO CSV loaded" for one group, region and COB."""
    key = {"group": int(group), "region": region, "cob": cob, **({"group_name": group_name} if group_name else {})}
    res = await api.post("/api/events", headers={"X-AOF-Event-Secret": "evt"},
                         json={"agent_id": RECON, "team_group": GROUP, "task_key": key, "event": "FOBO CSV loaded"})
    assert res.status_code == 201, res.text
    return res.json()["task_id"]


async def _task(api, task_id, user="dana"):
    res = await api.get(f"/api/tasks/{task_id}", headers=api.as_user(user))
    return res.json() if res.status_code == 200 else res.status_code


def test_the_reference_data_holds_the_stubs_books():
    from scripts.write_fobo_books import path, render
    for biz in fobo_books.BUSINESSES.values():
        assert path(biz).read_text() == render(biz), "run scripts/write_fobo_books.py"
    assert len(fobo_books.BOOKS) >= 1900
    for group in (RATES, FIC):
        assert all(fobo_books.books_in(group, region) for region in ("EMEA", "APAC", "AMER"))


async def test_three_events_open_three_rates_tasks_each_for_every_book_of_its_region(api, events):
    ids = [await _event(api, RATES, region, group_name="Rates") for region in ("EMEA", "APAC", "AMER")]
    assert len(set(ids)) == 3
    assert await _event(api, RATES, "EMEA", group_name="Rates") == ids[0]          # the feed again: the same task
    for task_id, region in zip(ids, ("EMEA", "APAC", "AMER")):
        task = await _task(api, task_id)
        assert task["subject"] == f"Rates {region} · COB {COB}"
        assert task["task_key"] == {"group": RATES, "region": region, "cob": COB}
        assert task["status"] == "awaiting_review" and task["items"]
        region_books = set(fobo_books.books_in(RATES, region))
        assert {it["book"] for it in task["items"]} <= region_books
        assert len({it["book"] for it in task["items"]}) > 5                  # one task, many books
        for it in task["items"]:
            info = fobo_books.BOOKS[it["book"]]
            assert (it["book_desk"], it["book_product"]) == (info["desk"], info["product"])
            assert [c["id"] for c in it["checks"]] == ["C1", "C2", "C3", "C4", "C5", "C6"]
        # Proposals are by category and side across the region's books.
        assert all(g["group_key"].keys() == {"category", "side"} for g in task["groups"])
        assert max(len({i.split("|")[0] for i in g["item_ids"]}) for g in task["groups"]) > 1
        reads = {t["tool"]: t for t in task["tool_calls"] if t["requested_by"] == "match"}
        assert reads["cats.group_positions"]["arguments"] == {"group": RATES, "region": region, "cob": COB}
        assert reads["cats.group_positions"]["row_count"] > 1000                 # every position of the region
        assert len(reads["cats.group_positions"]["result"]["rows"]) == 100        # the page shows the first rows


async def test_a_group_the_reference_data_does_not_name_takes_the_events_name(api, events):
    task = await _task(api, await _event(api, "500099", "EMEA", group_name="Securitised"))
    assert task["subject"] == f"Securitised EMEA · COB {COB}"


async def test_a_controller_sees_only_their_group_and_region(api, events):
    rates_emea = await _event(api, RATES, "EMEA")
    rates_apac = await _event(api, RATES, "APAC")
    fic_apac = await _event(api, FIC, "APAC")
    assert (await _task(api, rates_apac, "hana"))["subject"] == f"Rates APAC · COB {COB}"
    assert await _task(api, rates_emea, "hana") == 404                         # Rates, another region
    assert await _task(api, fic_apac, "hana") == 404                           # APAC, another group
    assert (await _task(api, fic_apac, "mei"))["subject"] == f"FI Credit APAC · COB {COB}"
    listed = (await api.get(f"/api/agents/{RECON}/tasks?team_group={GROUP}", headers=api.as_user("raj"))).json()
    assert {t["task_id"] for t in listed} == {rates_emea, rates_apac}          # every Rates region, no FI Credit


async def test_most_books_reconcile_clean():
    clean = sum(fobo_books.clean(b, COB) and fobo_books.issue_instrument(b, COB) is None for b in fobo_books.BOOKS)
    assert clean / len(fobo_books.BOOKS) > 0.5


async def test_loading_reference_data_closes_a_version_the_file_now_closes():
    # The Rates books gained business and region on 14 October: the version before
    # is closed that day. A database loaded before the change has it open; loading
    # again closes it, so a read as of a later COB sees one version.
    async with get_session() as s:
        await s.execute(update(KgNode).where(KgNode.node_id == "book:RATES-LDN-01",
                                             KgNode.valid_to.isnot(None)).values(valid_to=None))
        await s.commit()
    await knowledge.seed_reference()
    async with get_session() as s:
        rows = (await s.execute(select(KgNode).where(KgNode.node_id == "book:RATES-LDN-01"))).scalars().all()
    assert sum(r.valid_to is None for r in rows) == 1
    now = await knowledge.walk("fobo-reference", {"book:RATES-LDN-01"}, [], as_of=COB)
    assert now["book:RATES-LDN-01"].attrs["region"] == "EMEA"
    before = await knowledge.walk("fobo-reference", {"book:RATES-LDN-01"}, [], as_of="2026-10-13")
    assert "region" not in before["book:RATES-LDN-01"].attrs


async def test_tasks_on_the_same_versions_share_one_checked_manifest(api, events):
    from agent_one_finance import runner
    from agent_one_finance.models import Task

    for region in ("APAC", "AMER"):
        await _event(api, RATES, region)
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(Task.team_group == GROUP))).scalars().all()
    first, second = rows[0], rows[1]
    assert await runner.pinned(first) is await runner.pinned(second)
    # A snapshot that differs is checked on its own, never served from the cache.
    second.manifest = {**second.manifest, "name": "Changed"}
    assert (await runner.pinned(second)).name == "Changed"
    assert (await runner.pinned(first)).name == "Helix FOBO Agent"


async def test_a_regional_lookup_must_be_within_both_the_group_and_the_region():
    from agent_one_finance import gateway
    from agent_one_finance.entitlement import Caller

    hana = Caller(user_id="hana", roles={"FOBO_RATES_CONTROLLER"},
                  data_scopes={"fobo_group": {RATES}, "region": {"APAC"}})
    ctx = gateway.CallContext(agent_id=RECON, caller=hana, requested_by="chat",
                              allowed_tools=frozenset({"motif.group_booking_events"}))
    args = {"group": RATES, "cob": COB}
    assert (await gateway.call(ctx, "motif.group_booking_events", {**args, "region": "APAC"}))["rows"]
    with pytest.raises(gateway.ToolDenied, match="region=EMEA"):
        await gateway.call(ctx, "motif.group_booking_events", {**args, "region": "EMEA"})
    with pytest.raises(gateway.ToolDenied, match=f"fobo_group={FIC}"):
        await gateway.call(ctx, "motif.group_booking_events", {**args, "group": FIC, "region": "APAC"})


async def test_each_regional_task_has_its_own_summary(api, events):
    emea = await _event(api, RATES, "EMEA")
    apac = await _event(api, RATES, "APAC")
    res = await api.get(f"/api/tasks/{emea}/summary", headers=api.as_user("rita"))
    assert res.status_code == 200, res.text
    s = res.json()
    task = await _task(api, emea)
    assert s["subject"] == f"Rates EMEA · COB {COB}" and s["by"] == ["book_desk", "book_product", "book"]
    # What it read: every position of every Rates EMEA book on each side.
    cats = next(x for x in s["sources"] if x["tool"] == "cats.group_positions")
    assert cats["distinct"]["book"] == len(fobo_books.books_in(RATES, "EMEA"))
    assert cats["without_items"]["book"] == cats["distinct"]["book"] - s["items"]["distinct"]["book"]
    # What it found, by desk, then product, then book; every break counted once.
    assert s["items"]["count"] == len(task["items"])
    desks = s["breakdown"]
    assert {d["value"] for d in desks} <= {b["desk"] for b in fobo_books.BOOKS.values()}
    assert sum(d["items"] for d in desks) == s["items"]["count"]
    assert sum(p["items"] for d in desks for p in d["children"]) == s["items"]["count"]
    assert all(c["field"] == "book" for d in desks for p in d["children"] for c in p["children"])
    # Its proposals span books, and no decision is taken yet.
    assert {p["group_id"] for p in s["proposals"]} == {g["group_id"] for g in task["groups"]}
    assert max(p["distinct"]["book"] for p in s["proposals"]) > 1
    assert s["items"]["open"] == s["items"]["in_proposals"]
    # The model session: who decided which proposal, and what the model was offered.
    assert set(s["model"]["decided_by"]) <= {"playbook", "llm", "rule", "none"}
    assert s["model"]["tools"] == ["motif.group_booking_events"]
    assert [sp["name"] for sp in s["model"]["specialists"]] == ["booking-events"]
    # Rates APAC is a different task with its own summary; Rita (EMEA) cannot read it.
    assert (await api.get(f"/api/tasks/{apac}/summary", headers=api.as_user("rita"))).status_code == 404
    assert (await api.get(f"/api/tasks/{apac}/summary", headers=api.as_user("hana"))).json()["subject"] == f"Rates APAC · COB {COB}"
