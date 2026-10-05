"""Config files reach a running deployment as drafts, approved four-eyes."""

from sqlalchemy import delete, select, update

from helix import capabilities, config_sync
from helix.db import get_session
from helix.entitlement import StubEntitlement
from helix import groups as team_groups
from helix.models import CapabilityVersion, GroupVersion
from tests.helix.conftest import VARIANCE


async def _age_live_version():
    """As if the live version predates the current file."""
    async with get_session() as s:
        row = (await s.execute(select(CapabilityVersion).where(
            CapabilityVersion.capability_id == VARIANCE, CapabilityVersion.status == "active"))).scalar_one()
        await s.execute(update(CapabilityVersion).where(
            CapabilityVersion.capability_id == VARIANCE, CapabilityVersion.version == row.version)
            .values(manifest={**row.manifest, "description": "an older description"}))
        await s.commit()


async def test_everything_matches_after_seeding():
    assert await config_sync.sync(dry_run=True) == []


async def test_a_changed_file_becomes_a_draft_an_owner_approves():
    await _age_live_version()
    assert await config_sync.sync(dry_run=True) == [f"{VARIANCE}: would draft a new version — an owner approves it"]
    assert await config_sync.sync() == [f"{VARIANCE}: drafted a new version — an owner approves it"]
    assert await config_sync.sync() == [f"{VARIANCE}: a draft with this file is waiting for approval"]
    await capabilities.approve(VARIANCE, 2, await StubEntitlement().get("carol"))
    assert await config_sync.sync() == []


async def test_a_new_capability_file_and_its_groups_arrive_as_first_drafts():
    """A deployment that predates break.investigation: its file and its group's
    file become version 1 drafts, the group once the capability is live."""
    cap = "break.investigation"
    async with get_session() as s:
        await s.execute(delete(GroupVersion).where(GroupVersion.capability_id == cap))
        await s.execute(delete(CapabilityVersion).where(CapabilityVersion.capability_id == cap))
        await s.commit()
    assert await config_sync.sync() == [
        f"{cap}: drafted a new version — an owner approves it",
        f"{cap}/fobo-prime: waits for capability {cap} to be approved"]
    await capabilities.approve(cap, 1, await StubEntitlement().get("erin"))
    assert await config_sync.sync() == [f"{cap}/fobo-prime: drafted a new version — a group owner approves it"]
    await team_groups.approve(cap, "fobo-prime", 1, await StubEntitlement().get("frank"))
    assert await config_sync.sync() == []
