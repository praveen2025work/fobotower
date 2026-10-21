"""An agent's Summary: a COB's tasks across about 1,200 FI Credit books, grouped by
business, region, desk and product, and one decision on a pattern across many
tasks — each task checked exactly as its own "Approve all" would be."""

import uuid

from sqlalchemy import select, update

from agent_one_finance import knowledge
from agent_one_finance.db import get_session
from agent_one_finance.models import KgNode
from agent_one_finance.stub_connectors import fi_credit

RECON, FIC = "recon.investigation", "cats-motif-fi-credit"
COB = "2026-10-20"


async def _open(api, book, cob=COB, group=FIC):
    res = await api.post(f"/api/capabilities/{RECON}/cases", headers=api.as_user("aof-scheduler"),
                         json={"case_key": {"book": book, "cob": cob}, "team_group": group})
    assert res.status_code == 201, res.text
    return res.json()


def _books(region: str, n: int, with_breaks: bool = True) -> list[str]:
    """The first n books of a region that do (or do not) have breaks on the COB."""
    out = []
    for book, info in fi_credit.BOOKS.items():
        if info["region"] != region:
            continue
        broken = not fi_credit.clean(book, COB) or fi_credit.issue_instrument(book, COB) is not None
        if broken == with_breaks:
            out.append(book)
        if len(out) == n:
            break
    return out


def test_the_reference_data_holds_the_stubs_fi_credit_books():
    from scripts.write_fi_credit_books import OUT, render
    assert OUT.read_text() == render(), "run scripts/write_fi_credit_books.py"
    assert len(fi_credit.BOOKS) >= 1000
    regions = {b["region"] for b in fi_credit.BOOKS.values()}
    assert regions == {"APAC", "EMEA", "Americas"}


async def test_an_fi_credit_task_is_named_by_business_region_and_product(api):
    book = _books("APAC", 1)[0]
    case = await _open(api, book)
    info = fi_credit.BOOKS[book]
    assert case["subject"] == f"FI Credit APAC · {info['product']} ({book}) · COB {COB}"
    assert case["labels"]["case"] == "CATS vs MOTIF"
    assert case["labels"]["capability"] == "Helix FOBO Agent"


async def test_most_fi_credit_books_reconcile_clean():
    clean = sum(fi_credit.clean(b, COB) and fi_credit.issue_instrument(b, COB) is None for b in fi_credit.BOOKS)
    assert clean / len(fi_credit.BOOKS) > 0.5


async def test_the_summary_files_each_task_under_its_business_region_desk_and_product(api):
    apac, emea = _books("APAC", 2), _books("EMEA", 2)
    clean = _books("Americas", 1, with_breaks=False)
    for b in apac + emea + clean:
        await _open(api, b)
    day = (await api.get(f"/api/capabilities/{RECON}/summary", headers=api.as_user("dana"))).json()
    assert day["date"] == COB and COB in day["dates"]
    assert [d["label"] for d in day["dimensions"]][:4] == ["Business", "Region", "Desk", "Product"]
    by_case = {t["subject"].split("(")[-1].split(")")[0]: t for t in day["tasks"]}
    for b in apac + emea + clean:
        info = fi_credit.BOOKS[b]
        assert by_case[b]["facts"][:4] == ["FI Credit", info["region"], info["desk"], info["product"]]
    assert by_case[clean[0]]["items"] == 0 and by_case[clean[0]]["open"] == []
    assert all(by_case[b]["open"] for b in apac + emea)
    # A COB with nothing is not offered; another COB is asked for by date.
    other = (await api.get(f"/api/capabilities/{RECON}/summary?date=2026-10-19", headers=api.as_user("dana"))).json()
    assert other["tasks"] == []


async def test_the_summary_shows_only_tasks_the_caller_may_see(api):
    await _open(api, _books("EMEA", 1)[0])
    rates = await _open(api, "RATES-LDN-01", group="cats-motif-rates")
    rita = (await api.get(f"/api/capabilities/{RECON}/summary", headers=api.as_user("rita"))).json()
    assert [t["case_id"] for t in rita["tasks"]] == [rates["case_id"]]
    assert (await api.get(f"/api/capabilities/{RECON}/summary", headers=api.as_user("viewer"))).status_code == 403


async def test_a_pattern_is_decided_across_tasks_each_checked_as_its_own(api):
    books = _books("APAC", 6)
    cases = [await _open(api, b) for b in books]
    day = (await api.get(f"/api/capabilities/{RECON}/summary", headers=api.as_user("mei"))).json()
    ready = [(t["case_id"], g["group_id"]) for t in day["tasks"] for g in t["open"] if g["ready"]]
    held = [(t["case_id"], g["group_id"]) for t in day["tasks"] for g in t["open"] if g["blockers"]]
    assert ready, "some proposals can be approved together"
    targets = {}
    for cid, gid in ready + held:
        targets.setdefault(cid, []).append(gid)
    res = await api.post(f"/api/capabilities/{RECON}/summary/decisions", headers=api.as_user("mei"), json={
        "targets": [{"case_id": c, "group_ids": g} for c, g in targets.items()], "action": "approve",
        "comment": "APAC settlement batch loaded twice in MOTIF; agreed with Operations.",
        "idempotency_key": uuid.uuid4().hex, "review_seconds": 120})
    assert res.status_code == 201, res.text
    out = res.json()
    assert out["decided"] == len(ready)
    assert out["refused_count"] == len(held)
    assert all("one-by-one" in r["reason"] for r in out["reasons"])
    # Each decision is the task's own: recorded on it, by mei, with the comment.
    first = (await api.get(f"/api/cases/{cases[0]['case_id']}", headers=api.as_user("mei"))).json()
    mine = [d for d in first["decisions"] if d["decided_by"] == "mei"]
    assert all(d["comment"].startswith("APAC settlement batch") for d in mine)
    after = (await api.get(f"/api/capabilities/{RECON}/summary", headers=api.as_user("mei"))).json()
    assert not [g for t in after["tasks"] for g in t["open"] if g["ready"]]


async def test_deciding_across_tasks_keeps_each_tasks_rules(api):
    case = await _open(api, _books("EMEA", 1)[0])
    gid = case["groups"][0]["group_id"]
    # Someone without the reviewer role is refused per proposal, not with an error for the lot.
    res = await api.post(f"/api/capabilities/{RECON}/summary/decisions", headers=api.as_user("rita"), json={
        "targets": [{"case_id": case["case_id"], "group_ids": [gid]}, {"case_id": "nope", "group_ids": ["x"]}],
        "action": "approve", "idempotency_key": uuid.uuid4().hex})
    out = res.json()
    assert out["decided"] == 0 and out["refused_count"] == 2
    assert {r["reason"] for r in out["refused"]} >= {"not a task of this agent"}
    bad = await api.post(f"/api/capabilities/{RECON}/summary/decisions", headers=api.as_user("mei"), json={
        "targets": [{"case_id": case["case_id"], "group_ids": [gid]}], "action": "maybe",
        "idempotency_key": uuid.uuid4().hex})
    assert bad.status_code == 422


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


async def test_tasks_on_the_same_versions_share_one_checked_manifest(api):
    from agent_one_finance import runner
    from agent_one_finance.models import Case

    a, b = _books("APAC", 2)
    for book in (a, b):
        await _open(api, book)
    async with get_session() as s:
        rows = (await s.execute(select(Case).where(Case.team_group == FIC))).scalars().all()
    first, second = rows[0], rows[1]
    assert await runner.pinned(first) is await runner.pinned(second)
    # A snapshot that differs is checked on its own, never served from the cache.
    second.manifest = {**second.manifest, "name": "Changed"}
    assert (await runner.pinned(second)).name == "Changed"
    assert (await runner.pinned(first)).name == "Helix FOBO Agent"
