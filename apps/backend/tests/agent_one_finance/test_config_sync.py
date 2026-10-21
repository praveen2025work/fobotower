"""Config files reach a running deployment as drafts, approved four-eyes."""

from sqlalchemy import delete, select, update

from agent_one_finance import agents, config_sync
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import StubEntitlement
from agent_one_finance import groups as team_groups
from agent_one_finance.models import AgentVersion, GroupVersion
from tests.agent_one_finance.conftest import VARIANCE


async def _age_live_version():
    """As if the live version predates the current file."""
    async with get_session() as s:
        row = (await s.execute(select(AgentVersion).where(
            AgentVersion.agent_id == VARIANCE, AgentVersion.status == "active"))).scalar_one()
        await s.execute(update(AgentVersion).where(
            AgentVersion.agent_id == VARIANCE, AgentVersion.version == row.version)
            .values(manifest={**row.manifest, "description": "an older description"}))
        await s.commit()


async def test_everything_matches_after_seeding():
    assert await config_sync.sync(dry_run=True) == []


async def test_a_changed_file_becomes_a_draft_an_owner_approves():
    await _age_live_version()
    assert await config_sync.sync(dry_run=True) == [f"{VARIANCE}: would draft a new version — an owner approves it"]
    assert await config_sync.sync() == [f"{VARIANCE}: drafted a new version — an owner approves it"]
    assert await config_sync.sync() == [f"{VARIANCE}: a draft with this file is waiting for approval"]
    await agents.approve(VARIANCE, 2, await StubEntitlement().get("carol"))
    assert await config_sync.sync() == []


async def test_a_new_agent_file_and_its_groups_arrive_as_first_drafts():
    """A deployment that predates break.investigation: its file and its group's
    file become version 1 drafts, the group once the agent is live."""
    cap = "break.investigation"
    async with get_session() as s:
        await s.execute(delete(GroupVersion).where(GroupVersion.agent_id == cap))
        await s.execute(delete(AgentVersion).where(AgentVersion.agent_id == cap))
        await s.commit()
    assert await config_sync.sync() == [
        f"{cap}: drafted a new version — an owner approves it",
        f"{cap}/fobo-prime: waits for agent {cap} to be approved",
        f"{cap}/fobo-rates: waits for agent {cap} to be approved"]
    await agents.approve(cap, 1, await StubEntitlement().get("erin"))
    assert await config_sync.sync() == [f"{cap}/fobo-prime: drafted a new version — a group owner approves it",
                                        f"{cap}/fobo-rates: drafted a new version — a group owner approves it"]
    await team_groups.approve(cap, "fobo-prime", 1, await StubEntitlement().get("frank"))
    await team_groups.approve(cap, "fobo-rates", 1, await StubEntitlement().get("raj"))
    assert await config_sync.sync() == []
