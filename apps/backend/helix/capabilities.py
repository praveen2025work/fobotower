"""Capabilities: manifests, their versions, and who may change them.

config/helix/capabilities/*.yaml seed version 1 of each capability on a
fresh database. After that the database is the source of truth: a change is
drafted as a new version by one owner and activated only when another owner
approves it (four-eyes). Runs pin the version active when they opened.
"""

from datetime import datetime, timezone

import yaml
from sqlalchemy import func, select, update

from helix.config import settings
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest, problems
from helix.models import CapabilityVersion

SEED_USER = "system:seed"


class CapabilityError(ValueError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems or []


def seed_files() -> list[Manifest]:
    folder = settings().config_dir / "capabilities"
    return [Manifest.model_validate(yaml.safe_load(p.read_text()))
            for p in sorted(folder.glob("*.yaml"))]


async def seed() -> list[str]:
    """Insert version 1 for any capability the database does not know yet."""
    seeded = []
    for m in seed_files():
        found = problems(m)
        if found:
            raise CapabilityError(f"{m.id}: invalid manifest", found)
        async with get_session() as s:
            exists = (await s.execute(select(CapabilityVersion.version).where(
                CapabilityVersion.capability_id == m.id).limit(1))).first()
            if exists is None:
                s.add(CapabilityVersion(
                    capability_id=m.id, version=1, manifest=m.model_dump(by_alias=True),
                    status="active", note="seeded from config", drafted_by=SEED_USER,
                    decided_by=SEED_USER, decided_at=datetime.now(timezone.utc)))
                await s.commit()
                seeded.append(m.id)
    return seeded


async def active(capability_id: str) -> tuple[int, Manifest]:
    async with get_session() as s:
        row = (await s.execute(select(CapabilityVersion).where(
            CapabilityVersion.capability_id == capability_id,
            CapabilityVersion.status == "active"))).scalar_one_or_none()
    if row is None:
        raise CapabilityError(f"no active capability {capability_id!r}")
    return row.version, Manifest.model_validate(row.manifest)


async def all_active() -> list[tuple[int, Manifest]]:
    async with get_session() as s:
        rows = (await s.execute(select(CapabilityVersion).where(
            CapabilityVersion.status == "active").order_by(CapabilityVersion.capability_id)
        )).scalars().all()
    return [(r.version, Manifest.model_validate(r.manifest)) for r in rows]


def can_see(caller: Caller, m: Manifest) -> bool:
    return caller.has_any_role(m.visible_to_roles()) or is_owner(caller, m)


def is_owner(caller: Caller, m: Manifest) -> bool:
    return caller.user_id in m.owners.people or (
        m.owners.role is not None and m.owners.role in caller.roles)


async def versions(capability_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(CapabilityVersion).where(
            CapabilityVersion.capability_id == capability_id).order_by(
            CapabilityVersion.version.desc()))).scalars().all()
    return [{"version": r.version, "status": r.status, "note": r.note,
             "drafted_by": r.drafted_by, "drafted_at": r.drafted_at,
             "decided_by": r.decided_by, "decided_at": r.decided_at} for r in rows]


async def draft(capability_id: str, manifest: dict, note: str, caller: Caller) -> int:
    _, current = await active(capability_id)
    if not is_owner(caller, current):
        raise PermissionError(f"{caller.user_id} is not an owner of {capability_id}")
    try:
        m = Manifest.model_validate(manifest)
    except ValueError as e:
        raise CapabilityError("manifest does not match the schema", [str(e)]) from e
    if m.id != capability_id:
        raise CapabilityError("manifest id does not match the capability")
    found = problems(m)
    if found:
        raise CapabilityError("manifest has problems", found)
    async with get_session() as s:
        number = (await s.execute(select(func.max(CapabilityVersion.version)).where(
            CapabilityVersion.capability_id == capability_id))).scalar_one() + 1
        s.add(CapabilityVersion(capability_id=capability_id, version=number,
                                manifest=m.model_dump(by_alias=True), status="draft",
                                note=note, drafted_by=caller.user_id))
        await s.commit()
    return number


async def _active_or_none(capability_id: str) -> Manifest | None:
    try:
        return (await active(capability_id))[1]
    except CapabilityError:
        return None


async def approve(capability_id: str, version: int, caller: Caller) -> None:
    async with get_session() as s:
        row = await s.get(CapabilityVersion, (capability_id, version))
    if row is None or row.status != "draft":
        raise CapabilityError(f"version {version} is not a draft")
    # A change is approved by an owner of the live capability; a brand-new
    # capability by an owner its own draft names.
    current = await _active_or_none(capability_id) or Manifest.model_validate(row.manifest)
    if not is_owner(caller, current):
        raise PermissionError(f"{caller.user_id} is not an owner of {capability_id}")
    async with get_session() as s:
        row = await s.get(CapabilityVersion, (capability_id, version))
        if current.owners.four_eyes and row.drafted_by == caller.user_id:
            raise PermissionError("four-eyes: the drafter cannot approve their own change")
        await s.execute(update(CapabilityVersion).where(
            CapabilityVersion.capability_id == capability_id,
            CapabilityVersion.status == "active").values(status="superseded"))
        row.status, row.decided_by = "active", caller.user_id
        row.decided_at = datetime.now(timezone.utc)
        await s.commit()


async def draft_new(manifest: dict, note: str, caller: Caller) -> int:
    """Version 1 of a capability that does not exist yet, as a draft.
    Only someone the draft names as an owner may submit it."""
    try:
        m = Manifest.model_validate(manifest)
    except ValueError as e:
        raise CapabilityError("manifest does not match the schema", [str(e)]) from e
    found = problems(m)
    if found:
        raise CapabilityError("manifest has problems", found)
    if not is_owner(caller, m):
        raise PermissionError("name yourself (or one of your roles) as an owner to submit it")
    async with get_session() as s:
        exists = (await s.execute(select(CapabilityVersion.version).where(
            CapabilityVersion.capability_id == m.id).limit(1))).first()
        if exists is not None:
            raise CapabilityError(f"capability {m.id!r} already exists; draft a new version of it")
        s.add(CapabilityVersion(capability_id=m.id, version=1, manifest=m.model_dump(by_alias=True),
                                status="draft", note=note, drafted_by=caller.user_id))
        await s.commit()
    return 1


async def drafts_for(caller: Caller) -> list[dict]:
    """Draft versions the caller could approve or has drafted."""
    async with get_session() as s:
        rows = (await s.execute(select(CapabilityVersion).where(
            CapabilityVersion.status == "draft").order_by(CapabilityVersion.drafted_at.desc())
        )).scalars().all()
    out = []
    for r in rows:
        draft = Manifest.model_validate(r.manifest)
        live = await _active_or_none(r.capability_id)
        owners_of = live or draft
        if is_owner(caller, owners_of) or r.drafted_by == caller.user_id:
            out.append({"capability_id": r.capability_id, "version": r.version, "name": draft.name,
                        "note": r.note, "drafted_by": r.drafted_by, "drafted_at": r.drafted_at,
                        "new": live is None, "manifest": r.manifest,
                        "can_approve": is_owner(caller, owners_of) and (
                            r.drafted_by != caller.user_id or not owners_of.owners.four_eyes)})
    return out
