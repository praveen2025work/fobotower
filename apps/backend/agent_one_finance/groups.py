"""Groups: each team's configuration of an agent.

An agent is the shared use case (e.g. reconciliation investigation); a
group is one team's way of running it (e.g. the CATS vs MOTIF rec group, or
cash bank-vs-ledger). FOBO's rec groups are exactly this. The agent's
owners decide WHAT may vary (`configurable`); each group's owners decide HOW
their team runs it (`set`), and approve each other's changes (four-eyes).

    config/agent-one-finance/groups/<agent_id>/<group>.yaml   seeds version 1

A task runs on the agent manifest merged with its group's `set` —
validated by the same checks as any manifest — and keeps that merged manifest
as its own record.
"""

import logging
from datetime import datetime, timezone
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from agent_one_finance import agents
from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest, Owners, problems
from agent_one_finance.models import GroupVersion

log = logging.getLogger("agent_one_finance.groups")

SEED_USER = "system:seed"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GroupConfig(Strict):
    group: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str
    description: str = ""
    owners: Owners
    set: dict[str, Any] = Field(default_factory=dict)   # manifest fields this team sets


def read_file(path) -> dict:
    """A group file, with a skill file it names under `set.reasoning` read in."""
    data = yaml.safe_load(path.read_text()) or {}
    reasoning = (data.get("set") or {}).get("reasoning")
    if reasoning:
        data["set"]["reasoning"] = agents.with_skill_file(reasoning)
    return data


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
    agent's value there (a group setting task.scopes gets exactly its
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
    """The manifest a group's tasks run on, and everything wrong with it."""
    _, refused = set_paths(cfg.set, base.configurable)
    found = [f"`{p}` is not configurable for {base.id} (allowed: {', '.join(base.configurable) or 'nothing'})"
             for p in refused]
    if found:
        return None, found
    try:
        m = Manifest.model_validate(merge(base.model_dump(by_alias=True), cfg.set, base.configurable))
    except ValueError as e:
        return None, agents.schema_problems(e)
    return m, problems(m)


def check(base: Manifest, config: dict) -> list[str]:
    """Everything wrong with a proposed group, without storing it."""
    try:
        cfg = GroupConfig.model_validate(config)
    except ValueError as e:
        return agents.schema_problems(e)
    return effective(base, cfg)[1]


def is_group_owner(caller: Caller, cfg: GroupConfig) -> bool:
    o = cfg.owners
    return caller.user_id in o.people or (o.role is not None and o.role in caller.roles)


# ---------- storage ----------

def _from_file(agent_id: str) -> Manifest | None:
    return next((m for m in agents.seed_files() if m.id == agent_id), None)


async def seed() -> list[str]:
    seeded = []
    root = settings().config_dir / "groups"
    if not root.exists():
        return seeded
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        agent_id = folder.name
        _, base = await agents.active(agent_id)
        for path in sorted(folder.glob("*.yaml")):
            cfg = GroupConfig.model_validate(read_file(path))
            async with get_session() as s:
                if await s.get(GroupVersion, (agent_id, cfg.group, 1)) is None:
                    # Only a new group is seeded (and checked) from its file; a
                    # live group changes through drafts (agent_one_finance.config_sync).
                    _, found = effective(base, cfg)
                    if found and not effective(_from_file(agent_id) or base, cfg)[1]:
                        # Valid on the agent's file, which is not approved yet: it
                        # waits, and config_sync drafts it once that version is live.
                        log.warning("%s/%s waits for a newer %s version: %s", agent_id, cfg.group,
                                    agent_id, "; ".join(found[:3]))
                        continue
                    if found:
                        raise GroupError(f"{agent_id}/{cfg.group}: invalid group", found)
                    s.add(GroupVersion(agent_id=agent_id, group_id=cfg.group, version=1,
                                       config=cfg.model_dump(), status="active",
                                       note="seeded from config", drafted_by=SEED_USER,
                                       decided_by=SEED_USER, decided_at=datetime.now(timezone.utc)))
                    await s.commit()
                    seeded.append(f"{agent_id}/{cfg.group}")
    return seeded


async def active_groups(agent_id: str) -> list[tuple[int, GroupConfig, Manifest]]:
    """Every active group with its effective manifest (on the agent's active version)."""
    _, base = await agents.active(agent_id)
    async with get_session() as s:
        rows = (await s.execute(select(GroupVersion).where(
            GroupVersion.agent_id == agent_id, GroupVersion.status == "active")
            .order_by(GroupVersion.group_id))).scalars().all()
    out = []
    for r in rows:
        cfg = GroupConfig.model_validate(r.config)
        m, found = effective(base, cfg)
        if m is not None and not found:      # a group broken by an agent change is skipped
            out.append((r.version, cfg, m))
    return out


async def active_group(agent_id: str, group_id: str) -> tuple[int, GroupConfig, Manifest]:
    for version, cfg, m in await active_groups(agent_id):
        if cfg.group == group_id:
            return version, cfg, m
    raise LookupError(f"{agent_id}/{group_id}")


async def visible(caller: Caller, agent_id: str, base: Manifest) -> bool:
    """An agent is visible to its own roles and to every role of any of its groups."""
    if agents.can_see(caller, base):
        return True
    return any(agents.can_see(caller, m) or is_group_owner(caller, cfg)
               for _, cfg, m in await active_groups(agent_id))


async def versions(agent_id: str, group_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(GroupVersion).where(
            GroupVersion.agent_id == agent_id, GroupVersion.group_id == group_id)
            .order_by(GroupVersion.version.desc()))).scalars().all()
    return [{"version": r.version, "status": r.status, "note": r.note, "drafted_by": r.drafted_by,
             "drafted_at": r.drafted_at, "decided_by": r.decided_by, "decided_at": r.decided_at,
             "config": r.config} for r in rows]


async def _current(agent_id: str, group_id: str) -> GroupConfig | None:
    async with get_session() as s:
        row = (await s.execute(select(GroupVersion).where(
            GroupVersion.agent_id == agent_id, GroupVersion.group_id == group_id,
            GroupVersion.status == "active"))).scalar_one_or_none()
    return GroupConfig.model_validate(row.config) if row else None


async def draft(agent_id: str, config: dict, note: str, caller: Caller) -> dict:
    """A new version of a group (or a new group). The group's current owners may
    change it; a new group may be proposed by anyone it names as an owner."""
    _, base = await agents.active(agent_id)
    try:
        cfg = GroupConfig.model_validate(config)
    except ValueError as e:
        raise GroupError("the group does not match the schema", [str(e)]) from e
    _, found = effective(base, cfg)
    if found:
        raise GroupError("the group has problems", found)
    current = await _current(agent_id, cfg.group)
    if not is_group_owner(caller, current or cfg):
        raise PermissionError(f"{caller.user_id} is not an owner of group {cfg.group}")
    async with get_session() as s:
        number = (await s.execute(select(func.max(GroupVersion.version)).where(
            GroupVersion.agent_id == agent_id,
            GroupVersion.group_id == cfg.group))).scalar_one() or 0
        s.add(GroupVersion(agent_id=agent_id, group_id=cfg.group, version=number + 1,
                           config=cfg.model_dump(), status="draft", note=note,
                           drafted_by=caller.user_id))
        await s.commit()
    return {"group_id": cfg.group, "version": number + 1}


async def approve(agent_id: str, group_id: str, version: int, caller: Caller) -> None:
    async with get_session() as s:
        row = await s.get(GroupVersion, (agent_id, group_id, version))
    if row is None or row.status != "draft":
        raise GroupError(f"version {version} of {group_id} is not a draft")
    owners_of = await _current(agent_id, group_id) or GroupConfig.model_validate(row.config)
    if not is_group_owner(caller, owners_of):
        raise PermissionError(f"{caller.user_id} is not an owner of group {group_id}")
    if owners_of.owners.four_eyes and row.drafted_by == caller.user_id:
        raise PermissionError("four-eyes: the drafter cannot approve their own change")
    _, base = await agents.active(agent_id)
    _, found = effective(base, GroupConfig.model_validate(row.config))
    if found:  # the agent may have changed since the draft
        raise GroupError("the group no longer fits the agent", found)
    async with get_session() as s:
        await s.execute(update(GroupVersion).where(
            GroupVersion.agent_id == agent_id, GroupVersion.group_id == group_id,
            GroupVersion.status == "active").values(status="superseded"))
        row = await s.get(GroupVersion, (agent_id, group_id, version))
        row.status, row.decided_by = "active", caller.user_id
        row.decided_at = datetime.now(timezone.utc)
        await s.commit()
