"""The FI Credit master books (APAC, EMEA, the Americas) in the stand-in CATS and MOTIF
and in the reference data, and what loading reference data and reading many tasks need."""

from sqlalchemy import select, update

from agent_one_finance import knowledge
from agent_one_finance.db import get_session
from agent_one_finance.models import KgNode
from agent_one_finance.stub_connectors import fi_credit

RECON, FIC = "recon.investigation", "cats-motif-fi-credit"
COB = "2026-10-20"


async def _open(api, book, cob=COB, group=FIC):
    res = await api.post(f"/api/agents/{RECON}/tasks", headers=api.as_user("aof-scheduler"),
                         json={"task_key": {"book": book, "cob": cob}, "team_group": group})
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
    task = await _open(api, book)
    info = fi_credit.BOOKS[book]
    assert task["subject"] == f"FI Credit APAC · {info['product']} ({book}) · COB {COB}"
    assert task["labels"]["task"] == "CATS vs MOTIF"
    assert task["labels"]["agent"] == "Helix FOBO Agent"


async def test_most_fi_credit_books_reconcile_clean():
    clean = sum(fi_credit.clean(b, COB) and fi_credit.issue_instrument(b, COB) is None for b in fi_credit.BOOKS)
    assert clean / len(fi_credit.BOOKS) > 0.5


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
    from agent_one_finance.models import Task

    a, b = _books("APAC", 2)
    for book in (a, b):
        await _open(api, book)
    async with get_session() as s:
        rows = (await s.execute(select(Task).where(Task.team_group == FIC))).scalars().all()
    first, second = rows[0], rows[1]
    assert await runner.pinned(first) is await runner.pinned(second)
    # A snapshot that differs is checked on its own, never served from the cache.
    second.manifest = {**second.manifest, "name": "Changed"}
    assert (await runner.pinned(second)).name == "Changed"
    assert (await runner.pinned(first)).name == "Helix FOBO Agent"
