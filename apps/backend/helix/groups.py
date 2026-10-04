"""Groups: each team's configuration of a capability.

A capability is the shared use case (e.g. reconciliation investigation); a
group is one team's way of running it (e.g. the CATS vs MOTIF rec group, or
cash bank-vs-ledger). FOBO's rec groups are exactly this. The capability's
owners decide WHAT may vary (`configurable`); each group's owners decide HOW
their team runs it (`set`), and approve each other's changes (four-eyes).

    config/helix/groups/<capability_id>/<group>.yaml   seeds version 1

A case runs on the capability manifest merged with its group's `set` —
validated by the same checks as any manifest — and keeps that merged manifest
as its own record.
"""

from datetime import datetime, timezone
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from helix import capabilities
from helix.config import settings
from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest, Owners, problems
from helix.models import GroupVersion

SEED_USER = "system:seed"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GroupConfig(Strict):
    group: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str
    description: str = ""
    owners: Owners
    set: dict[str, Any] = Field(default_factory=dict)   # manifest fields this team sets


class GroupError(ValueError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems or []


def _allowed(path: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p.endswith(".*"):
            if path.startswith(p[:-1]):
                return True
        elif path == p or path.startswith(p + "."):
            return True
    return False


def set_paths(values: dict, patterns: list[str], prefix: str = "") -> tuple[list[str], list[str]]:
    """(allowed, refused) dotted paths a group's `set` touches."""
    ok, refused = [], []
    for k, v in values.items():
        path = f"{prefix}{k}"
        if _allowed(path, patterns):
            ok.append(path)
        elif isinstance(v, dict) and v:
            a, r = set_paths(v, patterns, path + ".")
            ok += a
            refused += r
        else:
            refused.append(path)
    return ok, refused


def merge(base: dict, changes: dict, patterns: list[str], prefix: str = "") -> dict:
    """Apply a group's `set`: the value at a configurable path REPLACES the
    capability's value there (a group setting case.scopes gets exactly its
    scopes); above that path, dicts merge (policy.* sets one policy at a time)."""
    out = dict(base)
    for k, v in changes.items():
        path = f"{prefix}{k}"
        if not _allowed(path, patterns) and isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v, patterns, path + ".")
        else:
            out[k] = v
    return out


def effective(base: Manifest, cfg: GroupConfig) -> tuple[Manifest | None, list[str]]:
    """The manifest a group's cases run on, and everything wrong with it."""
    _, refused = set_paths(cfg.set, base.configurable)
    found = [f"`{p}` is not configurable for {base.id} (allowed: {', '.join(base.configurable) or 'nothing'})"
             for p in refused]
    if found:
        return None, found
    try:
        m = Manifest.model_validate(merge(base.model_dump(by_alias=True), cfg.set, base.configurable))
    except ValueError as e:
        errs = getattr(e, "errors", lambda: [])()
        return None, [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in errs] or [str(e)]
    return m, problems(m)


def is_group_owner(caller: Caller, cfg: GroupConfig) -> bool:
    o = cfg.owners
    return caller.user_id in o.people or (o.role is not None and o.role in caller.roles)


# ---------- storage ----------

async def seed() -> list[str]:
    seeded = []
    root = settings().config_dir / "groups"
    if not root.exists():
        return seeded
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        capability_id = folder.name
        _, base = await capabilities.active(capability_id)
        for path in sorted(folder.glob("*.yaml")):
            cfg = GroupConfig.model_validate(yaml.safe_load(path.read_text()))
            _, found = effective(base, cfg)
            if found:
                raise GroupError(f"{capability_id}/{cfg.group}: invalid group", found)
            async with get_session() as s:
                if await s.get(GroupVersion, (capability_id, cfg.group, 1)) is None:
                    s.add(GroupVersion(capability_id=capability_id, group_id=cfg.group, version=1,
                                       config=cfg.model_dump(), status="active",
                                       note="seeded from config", drafted_by=SEED_USER,
                                       decided_by=SEED_USER, decided_at=datetime.now(timezone.utc)))
                    await s.commit()
                    seeded.append(f"{capability_id}/{cfg.group}")
    return seeded


async def active_groups(capability_id: str) -> list[tuple[int, GroupConfig, Manifest]]:
    """Every active group with its effective manifest (on the capability's active version)."""
    _, base = await capabilities.active(capability_id)
    async with get_session() as s:
        rows = (await s.execute(select(GroupVersion).where(
            GroupVersion.capability_id == capability_id, GroupVersion.status == "active")
            .order_by(GroupVersion.group_id))).scalars().all()
    out = []
    for r in rows:
        cfg = GroupConfig.model_validate(r.config)
        m, found = effective(base, cfg)
        if m is not None and not found:      # a group broken by a capability change is skipped
            out.append((r.version, cfg, m))
    return out


async def active_group(capability_id: str, group_id: str) -> tuple[int, GroupConfig, Manifest]:
    for version, cfg, m in await active_groups(capability_id):
        if cfg.group == group_id:
            return version, cfg, m
    raise LookupError(f"{capability_id}/{group_id}")


async def visible(caller: Caller, capability_id: str, base: Manifest) -> bool:
    """A capability is visible to its own roles and to every role of any of its groups."""
    if capabilities.can_see(caller, base):
        return True
    return any(capabilities.can_see(caller, m) or is_group_owner(caller, cfg)
               for _, cfg, m in await active_groups(capability_id))


async def versions(capability_id: str, group_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(GroupVersion).where(
            GroupVersion.capability_id == capability_id, GroupVersion.group_id == group_id)
            .order_by(GroupVersion.version.desc()))).scalars().all()
    return [{"version": r.version, "status": r.status, "note": r.note, "drafted_by": r.drafted_by,
             "drafted_at": r.drafted_at, "decided_by": r.decided_by, "decided_at": r.decided_at,
             "config": r.config} for r in rows]


async def _current(capability_id: str, group_id: str) -> GroupConfig | None:
    async with get_session() as s:
        row = (await s.execute(select(GroupVersion).where(
            GroupVersion.capability_id == capability_id, GroupVersion.group_id == group_id,
            GroupVersion.status == "active"))).scalar_one_or_none()
    return GroupConfig.model_validate(row.config) if row else None


async def draft(capability_id: str, config: dict, note: str, caller: Caller) -> dict:
    """A new version of a group (or a new group). The group's current owners may
    change it; a new group may be proposed by anyone it names as an owner."""
    _, base = await capabilities.active(capability_id)
    try:
        cfg = GroupConfig.model_validate(config)
    except ValueError as e:
        raise GroupError("the group does not match the schema", [str(e)]) from e
    _, found = effective(base, cfg)
    if found:
        raise GroupError("the group has problems", found)
    current = await _current(capability_id, cfg.group)
    if not is_group_owner(caller, current or cfg):
        raise PermissionError(f"{caller.user_id} is not an owner of group {cfg.group}")
    async with get_session() as s:
        number = (await s.execute(select(func.max(GroupVersion.version)).where(
            GroupVersion.capability_id == capability_id,
            GroupVersion.group_id == cfg.group))).scalar_one() or 0
        s.add(GroupVersion(capability_id=capability_id, group_id=cfg.group, version=number + 1,
                           config=cfg.model_dump(), status="draft", note=note,
                           drafted_by=caller.user_id))
        await s.commit()
    return {"group_id": cfg.group, "version": number + 1}


async def approve(capability_id: str, group_id: str, version: int, caller: Caller) -> None:
    async with get_session() as s:
        row = await s.get(GroupVersion, (capability_id, group_id, version))
    if row is None or row.status != "draft":
        raise GroupError(f"version {version} of {group_id} is not a draft")
    owners_of = await _current(capability_id, group_id) or GroupConfig.model_validate(row.config)
    if not is_group_owner(caller, owners_of):
        raise PermissionError(f"{caller.user_id} is not an owner of group {group_id}")
    if owners_of.owners.four_eyes and row.drafted_by == caller.user_id:
        raise PermissionError("four-eyes: the drafter cannot approve their own change")
    _, base = await capabilities.active(capability_id)
    _, found = effective(base, GroupConfig.model_validate(row.config))
    if found:  # the capability may have changed since the draft
        raise GroupError("the group no longer fits the capability", found)
    async with get_session() as s:
        await s.execute(update(GroupVersion).where(
            GroupVersion.capability_id == capability_id, GroupVersion.group_id == group_id,
            GroupVersion.status == "active").values(status="superseded"))
        row = await s.get(GroupVersion, (capability_id, group_id, version))
        row.status, row.decided_by = "active", caller.user_id
        row.decided_at = datetime.now(timezone.utc)
        await s.commit()
