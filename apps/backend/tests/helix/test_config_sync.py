"""Config files reach a running deployment as drafts, approved four-eyes."""

from sqlalchemy import select, update

from helix import capabilities, config_sync
from helix.db import get_session
from helix.entitlement import StubEntitlement
from helix.models import CapabilityVersion
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
