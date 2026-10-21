"""Agents: manifests, their versions, and who may change them.

config/agent-one-finance/agents/*.yaml seed version 1 of each agent on a
fresh database. After that the database is the source of truth: a change is
drafted as a new version by one owner and activated only when another owner
approves it (four-eyes). Runs pin the version active when they opened.
"""

from datetime import datetime, timezone

import yaml
from sqlalchemy import func, select, update

from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.models import AgentVersion

SEED_USER = "system:seed"


class AgentError(ValueError):
    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = problems or []


def with_skill_file(reasoning: dict | None) -> dict | None:
    """`reasoning.skill_file` read into `reasoning.skill`. The path is relative
    to the config folder and must stay inside it. A file that is missing leaves
    `skill` empty, which `problems` reports."""
    if not isinstance(reasoning, dict) or not reasoning.get("skill_file"):
        return reasoning
    root = settings().config_dir.resolve()
    path = (root / reasoning["skill_file"]).resolve()
    if root not in path.parents or not path.is_file():
        return {**reasoning, "skill": ""}
    return {**reasoning, "skill": path.read_text(encoding="utf-8")}


def read_file(path) -> dict:
    """An agent file, with its skill file (if it names one) read in."""
    data = yaml.safe_load(path.read_text()) or {}
    if "reasoning" in data:
        data["reasoning"] = with_skill_file(data["reasoning"])
    return data


def seed_files() -> list[Manifest]:
    folder = settings().config_dir / "agents"
    return [Manifest.model_validate(read_file(p)) for p in sorted(folder.glob("*.yaml"))]


async def seed() -> list[str]:
    """Insert version 1 for any agent the database does not know yet."""
    seeded = []
    for m in seed_files():
        found = problems(m)
        if found:
            raise AgentError(f"{m.id}: invalid manifest", found)
        async with get_session() as s:
            exists = (await s.execute(select(AgentVersion.version).where(
                AgentVersion.agent_id == m.id).limit(1))).first()
            if exists is None:
                s.add(AgentVersion(
                    agent_id=m.id, version=1, manifest=m.model_dump(by_alias=True),
                    status="active", note="seeded from config", drafted_by=SEED_USER,
                    decided_by=SEED_USER, decided_at=datetime.now(timezone.utc)))
                await s.commit()
                seeded.append(m.id)
    return seeded


async def active(agent_id: str) -> tuple[int, Manifest]:
    async with get_session() as s:
        row = (await s.execute(select(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.status == "active"))).scalar_one_or_none()
    if row is None:
        raise AgentError(f"no active agent {agent_id!r}")
    return row.version, Manifest.model_validate(row.manifest)


async def all_active() -> list[tuple[int, Manifest]]:
    async with get_session() as s:
        rows = (await s.execute(select(AgentVersion).where(
            AgentVersion.status == "active").order_by(AgentVersion.agent_id)
        )).scalars().all()
    return [(r.version, Manifest.model_validate(r.manifest)) for r in rows]


def can_see(caller: Caller, m: Manifest) -> bool:
    return caller.has_any_role(m.visible_to_roles()) or is_owner(caller, m)


def is_owner(caller: Caller, m: Manifest) -> bool:
    return caller.user_id in m.owners.people or (
        m.owners.role is not None and m.owners.role in caller.roles)


async def versions(agent_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (await s.execute(select(AgentVersion).where(
            AgentVersion.agent_id == agent_id).order_by(
            AgentVersion.version.desc()))).scalars().all()
    return [{"version": r.version, "status": r.status, "note": r.note,
             "drafted_by": r.drafted_by, "drafted_at": r.drafted_at,
             "decided_by": r.decided_by, "decided_at": r.decided_at} for r in rows]


def schema_problems(e: ValueError) -> list[str]:
    """A schema error as one line per field: `path: message`."""
    errs = getattr(e, "errors", lambda: [])()
    return [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in errs] or [str(e)]


def check(agent_id: str, manifest: dict) -> list[str]:
    """Everything wrong with a proposed manifest, without storing it — what
    `draft` would refuse. The configuration screens call it as people edit."""
    try:
        m = Manifest.model_validate(manifest)
    except ValueError as e:
        return schema_problems(e)
    found = [] if m.id == agent_id else ["id: the manifest id does not match the agent"]
    return found + problems(m)


async def draft(agent_id: str, manifest: dict, note: str, caller: Caller) -> int:
    _, current = await active(agent_id)
    if not is_owner(caller, current):
        raise PermissionError(f"{caller.user_id} is not an owner of {agent_id}")
    try:
        m = Manifest.model_validate(manifest)
    except ValueError as e:
        raise AgentError("manifest does not match the schema", [str(e)]) from e
    if m.id != agent_id:
        raise AgentError("manifest id does not match the agent")
    found = problems(m)
    if found:
        raise AgentError("manifest has problems", found)
    async with get_session() as s:
        number = (await s.execute(select(func.max(AgentVersion.version)).where(
            AgentVersion.agent_id == agent_id))).scalar_one() + 1
        s.add(AgentVersion(agent_id=agent_id, version=number,
                                manifest=m.model_dump(by_alias=True), status="draft",
                                note=note, drafted_by=caller.user_id))
        await s.commit()
    return number


async def _active_or_none(agent_id: str) -> Manifest | None:
    try:
        return (await active(agent_id))[1]
    except AgentError:
        return None


async def approve(agent_id: str, version: int, caller: Caller) -> None:
    async with get_session() as s:
        row = await s.get(AgentVersion, (agent_id, version))
    if row is None or row.status != "draft":
        raise AgentError(f"version {version} is not a draft")
    # A change is approved by an owner of the live agent; a brand-new
    # agent by an owner its own draft names.
    current = await _active_or_none(agent_id) or Manifest.model_validate(row.manifest)
    if not is_owner(caller, current):
        raise PermissionError(f"{caller.user_id} is not an owner of {agent_id}")
    async with get_session() as s:
        row = await s.get(AgentVersion, (agent_id, version))
        if current.owners.four_eyes and row.drafted_by == caller.user_id:
            raise PermissionError("four-eyes: the drafter cannot approve their own change")
        await s.execute(update(AgentVersion).where(
            AgentVersion.agent_id == agent_id,
            AgentVersion.status == "active").values(status="superseded"))
        row.status, row.decided_by = "active", caller.user_id
        row.decided_at = datetime.now(timezone.utc)
        await s.commit()


async def draft_new(manifest: dict, note: str, caller: Caller) -> int:
    """Version 1 of an agent that does not exist yet, as a draft.
    Only someone the draft names as an owner may submit it."""
    try:
        m = Manifest.model_validate(manifest)
    except ValueError as e:
        raise AgentError("manifest does not match the schema", [str(e)]) from e
    found = problems(m)
    if found:
        raise AgentError("manifest has problems", found)
    if not is_owner(caller, m):
        raise PermissionError("name yourself (or one of your roles) as an owner to submit it")
    async with get_session() as s:
        exists = (await s.execute(select(AgentVersion.version).where(
            AgentVersion.agent_id == m.id).limit(1))).first()
        if exists is not None:
            raise AgentError(f"agent {m.id!r} already exists; draft a new version of it")
        s.add(AgentVersion(agent_id=m.id, version=1, manifest=m.model_dump(by_alias=True),
                                status="draft", note=note, drafted_by=caller.user_id))
        await s.commit()
    return 1


async def drafts_for(caller: Caller) -> list[dict]:
    """Draft versions the caller could approve or has drafted."""
    async with get_session() as s:
        rows = (await s.execute(select(AgentVersion).where(
            AgentVersion.status == "draft").order_by(AgentVersion.drafted_at.desc())
        )).scalars().all()
    out = []
    for r in rows:
        draft = Manifest.model_validate(r.manifest)
        live = await _active_or_none(r.agent_id)
        owners_of = live or draft
        if is_owner(caller, owners_of) or r.drafted_by == caller.user_id:
            out.append({"agent_id": r.agent_id, "version": r.version, "name": draft.name,
                        "note": r.note, "drafted_by": r.drafted_by, "drafted_at": r.drafted_at,
                        "new": live is None, "manifest": r.manifest,
                        "can_approve": is_owner(caller, owners_of) and (
                            r.drafted_by != caller.user_id or not owners_of.owners.four_eyes)})
    return out
