"""A run keeps the workflow version it started with."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from api.deps import checkpointer
from api.main import create_app
from app.contracts.models import Caller
from app.db.base import get_session
from app.db.models_ops import SourceCall
from app.db.models_session import InvestigationSession
from app.workflow import versions
from app.workflow.config import (
    WorkflowConfig,
    dump_config,
    read_workflow,
    reset_workflow_cache,
    settings,
    use_workflow,
)
from app.workflow.graph import graph_for_session, pinned_for_session

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")
ASHA = Caller(staff_id="asha", roles=["PC"], entity_scope=["LE-APAC-01"], region="APAC")


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=create_app()),
                           base_url="http://test", timeout=120) as c:
        yield c


async def _activate_v2_without_rank_and_a_30_day_lookback():
    async with get_session() as s:
        raw = dump_config((await versions.active(s)).config)
        raw["steps"].remove("rank")
        raw["settings"]["gather"]["priors_lookback_days"] = 30
        draft = await versions.create_draft(
            s, raw=raw, note="drop rank, 30-day lookback", based_on=1, caller=PRAVEEN)
    async with get_session() as s:
        await versions.approve(s, draft.number, caller=ASHA, key="pin-test")


async def _lookbacks(session_id: str) -> list[str]:
    async with get_session() as s:
        params = await s.scalars(
            select(SourceCall.validated_parameters).where(
                SourceCall.investigation_session_id == session_id,
                SourceCall.tool_name == "helix.similar_breaks",
            ))
        return [p["lookback"] for p in params]


async def _trace(client, rec: str) -> dict:
    return (await client.get(f"/api/recs/{rec}/trace")).json()["trace"]


async def test_a_run_started_on_v1_keeps_v1_after_v2_goes_live(client):
    await client.get("/api/recs/R-1055")
    await _activate_v2_without_rank_and_a_30_day_lookback()
    trace = await _trace(client, "R-1055")
    assert trace["workflow_version"] == 1
    assert "rank" in [s["node"] for s in trace["steps"]]
    assert await _lookbacks("sess-r-1055") == ["180d"]


async def test_a_run_started_after_the_approval_runs_v2(client):
    await _activate_v2_without_rank_and_a_30_day_lookback()
    await client.get("/api/recs/R-2031")
    trace = await _trace(client, "R-2031")
    assert trace["workflow_version"] == 2
    assert "rank" not in [s["node"] for s in trace["steps"]]
    # gather reads settings() inside a LangGraph step: the ContextVar reached it.
    assert await _lookbacks("sess-r-2031") == ["30d"]


async def test_the_run_records_its_version_on_the_session_row(client):
    await client.get("/api/recs/R-1055")
    async with get_session() as s:
        row = await s.get(InvestigationSession, "sess-r-1055")
    assert row.workflow_version == 1


async def test_a_second_run_on_a_thread_re_pins_the_row_to_its_own_version(client):
    """The row records the version of the run that LAST started on this
    thread — not just the first one ever. Otherwise a re-run after an
    approval leaves the row and the checkpoints that run wrote disagreeing
    about which version produced them, and every later reader rebuilds the
    wrong graph over them."""
    sid = "sess-r-1055"
    await client.post(f"/api/sessions/{sid}/investigate")
    await _activate_v2_without_rank_and_a_30_day_lookback()
    await client.post(f"/api/sessions/{sid}/investigate")

    async with get_session() as s:
        row = await s.get(InvestigationSession, sid)
    assert row.workflow_version == 2

    async with get_session() as s, checkpointer() as cp:
        graph, _ = await graph_for_session(cp, s, sid)
        state = await graph.aget_state({"configurable": {"thread_id": sid}})
    assert state.values["workflow_version"] == 2

    trace = await _trace(client, "R-1055")
    assert trace["workflow_version"] == 2


async def test_a_run_from_before_versioning_is_read_as_v1(client):
    await client.get("/api/recs/R-1055")
    async with get_session() as s:
        await s.execute(update(InvestigationSession)
                        .where(InvestigationSession.investigation_session_id == "sess-r-1055")
                        .values(workflow_version=None))
        await s.commit()
    await _activate_v2_without_rank_and_a_30_day_lookback()
    trace = await _trace(client, "R-1055")
    assert trace["workflow_version"] == 1 and trace["status"] == "awaiting_signoff"


async def test_a_run_that_has_not_started_is_shown_with_the_active_workflow():
    await _activate_v2_without_rank_and_a_30_day_lookback()
    async with get_session() as s:
        assert (await pinned_for_session(s, "sess-never-ran")).number == 2


def test_outside_a_run_settings_come_from_the_file():
    assert settings() == read_workflow().settings


def test_inside_use_workflow_settings_are_the_bound_ones():
    raw = dump_config(read_workflow())
    raw["settings"]["gather"]["priors_lookback_days"] = 7
    with use_workflow(WorkflowConfig.model_validate(raw)):
        assert settings().gather.priors_lookback_days == 7
    assert settings().gather.priors_lookback_days == 180


async def test_the_worklist_reads_pinned_graphs_not_the_yaml_file(client, tmp_path, monkeypatch):
    """/api/worklist builds each rec's graph from its pinned version, not from
    build_graph's config-less fallback to the YAML file — so an invalid edit
    left in the file must not break the route once a version is seeded."""
    await client.get("/api/recs/R-1055")  # seeds workflow_version=1, a checkpoint

    bad = tmp_path / "bad-workflow.yaml"
    bad.write_text("not: [a, valid, workflow", encoding="utf-8")
    monkeypatch.setenv("FOBO_WORKFLOW_PATH", str(bad))
    reset_workflow_cache()
    try:
        resp = await client.get("/api/worklist")
        assert resp.status_code == 200
    finally:
        monkeypatch.delenv("FOBO_WORKFLOW_PATH", raising=False)
        reset_workflow_cache()
