"""Tools for the people who build and change agents.

  diff         what changed between two versions (agent or group), as a
               YAML diff and the list of changed paths — what an approver reads
  instructions draft a new version that changes only the model's instructions
               (reasoning.skill) — the skill editor; history is the versions
  flow         an agent's (or group's) workflow as a graph: steps, gates and
               pauses, the tools each step uses, the people who decide
  templates    starting points for new agents (config/agent-one-finance/templates)
  promotion    export a version as a bundle (checksummed; signed with
               AOF_PROMOTION_KEY when set) and import it in another
               environment as a draft — approved there four-eyes like any change
"""

import difflib
import hashlib
import hmac
import json
from datetime import datetime, timezone

import yaml
from sqlalchemy import select

from agent_one_finance import agents
from agent_one_finance import groups as team_groups
from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.entitlement import Caller
from agent_one_finance.manifest import Manifest
from agent_one_finance.models import AgentVersion, GroupVersion

BUNDLE_FORMAT = "aof-version/1"


def _yaml(d: dict) -> str:
    return yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=100)


def _paths(a, b, prefix="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            out += _paths(a.get(k), b.get(k), f"{prefix}{k}.")
        return out
    return [] if a == b else [prefix.rstrip(".")]


def _diff(a: dict, b: dict, a_label: str, b_label: str) -> dict:
    lines = difflib.unified_diff(_yaml(a).splitlines(), _yaml(b).splitlines(), a_label, b_label, lineterm="")
    return {"diff": "\n".join(lines), "changed": _paths(a, b)}


async def version_diff(agent_id: str, a: int, b: int) -> dict:
    async with get_session() as s:
        ra = await s.get(AgentVersion, (agent_id, a))
        rb = await s.get(AgentVersion, (agent_id, b))
    if ra is None or rb is None:
        raise LookupError(f"{agent_id} v{a}/v{b}")
    return _diff(ra.manifest, rb.manifest, f"{agent_id} v{a}", f"{agent_id} v{b}")


async def group_diff(agent_id: str, group: str, a: int, b: int) -> dict:
    async with get_session() as s:
        ra = await s.get(GroupVersion, (agent_id, group, a))
        rb = await s.get(GroupVersion, (agent_id, group, b))
    if ra is None or rb is None:
        raise LookupError(f"{agent_id}/{group} v{a}/v{b}")
    return _diff(ra.config, rb.config, f"{group} v{a}", f"{group} v{b}")


async def draft_instructions(agent_id: str, skill: str, note: str, caller: Caller,
                             team_group: str | None = None) -> dict:
    """A new draft that changes only reasoning.skill — of the agent, or of
    one team's group. Owners approve it four-eyes like any version."""
    skill = (skill or "").strip()
    if not skill:
        raise agents.AgentError("instructions cannot be empty")
    if team_group:
        _, cfg, _ = await team_groups.active_group(agent_id, team_group)
        body = cfg.model_dump()
        reasoning = dict(body["set"].get("reasoning") or {})
        reasoning["skill"] = skill
        reasoning.pop("skill_file", None)       # edited here: no longer the file's text
        body["set"] = {**body["set"], "reasoning": reasoning}
        out = await team_groups.draft(agent_id, body, note or "instructions changed", caller)
        return {"team_group": team_group, "version": out["version"]}
    _, m = await agents.active(agent_id)
    manifest = m.model_dump(by_alias=True)
    manifest["reasoning"] = {**manifest["reasoning"], "skill": skill, "skill_file": None}
    return {"version": await agents.draft(agent_id, manifest, note or "instructions changed", caller)}


def flow(m: Manifest) -> dict:
    """The workflow as nodes and edges, derived from the manifest — never drawn by hand."""
    tools: dict[str, list[str]] = {
        "load": [m.items.load.tool] if m.items.load else [],
        "match": [m.match.left.tool, m.match.right.tool] if m.match else [],
        "enrich": [e.tool for e in m.enrich],
        "reason": list(m.reasoning.tools),
        "publish": [m.publish.tool] if m.publish else [],
    }
    notes = {
        "resolve": [f"{r.node} → {' → '.join(r.path)} as {r.as_}" for r in m.resolve],
        "classify": ([f"{len(m.playbook.checks)} cause checks", f"{len(m.playbook.tests)} validation tests",
                      f"{len(m.playbook.categories)} categories"] if m.playbook else []),
        "group": [f"by {', '.join(m.group_by)}"] if m.group_by else [],
        "reason": ([f"{len(m.rules)} rule(s) first"] if m.rules else [])
                  + [f"specialist: {sp.name}" for sp in m.reasoning.specialists]
                  + ([f"model ({m.reasoning.reasoner})"] if m.reasoning.reasoner == "llm" else ["no model"]),
    }
    people = {"review": list(m.review.roles), "publish": list(m.publish.approver_roles) if m.publish else []}
    from agent_one_finance.workflow import GATES
    from agent_one_finance import stepkit
    for sid in m.steps:               # configurable steps: their tools and settings, in words
        t = m.step_type(sid)
        if t in stepkit.TYPES:
            cfg = m.step_config(sid)
            tools[sid] = sorted(stepkit.TYPES[t].tools(cfg))
            st = m.step_settings[sid]
            notes[sid] = [stepkit.TYPES[t].label] + ([f"only when {st.when}"] if st.when else [])
        elif sid in m.step_settings and m.step_settings[sid].when:
            notes.setdefault(sid, []).append(f"only when {m.step_settings[sid].when}")
    nodes = [{"id": s, "type": m.step_type(s), "label": (m.step_settings[s].label if s in m.step_settings else None),
              "gate": s in GATES, "pause": s in m.pause_before, "tools": tools.get(s, []),
              "notes": notes.get(s, []), "people": people.get(s, [])} for s in m.steps]
    edges = [{"from": a, "to": b} for a, b in zip(m.steps, m.steps[1:])]
    return {"agent_id": m.id, "name": m.name, "nodes": nodes, "edges": edges,
            "opens": {"on": m.task.opens_on, "schedule": m.task.schedule, "events": m.task.events}}


def templates() -> list[dict]:
    folder = settings().config_dir / "templates"
    out = []
    for p in sorted(folder.glob("*.yaml")) if folder.exists() else []:
        text = p.read_text()
        doc = yaml.safe_load(text)
        out.append({"id": p.stem, "name": doc.get("name", p.stem), "description": doc.get("description", ""),
                    "yaml": text})
    return out


# ---------- promotion across environments ----------

def _body(kind: str, agent_id: str, version: int, content: dict, group: str | None) -> dict:
    return {"format": BUNDLE_FORMAT, "kind": kind, "agent_id": agent_id, "group": group,
            "version": version, "content": content}


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _signature(digest: str) -> str | None:
    key = settings().promotion_key
    return hmac.new(key.encode(), digest.encode(), hashlib.sha256).hexdigest() if key else None


async def export(agent_id: str, version: int, caller: Caller, group: str | None = None) -> dict:
    async with get_session() as s:
        if group:
            row = await s.get(GroupVersion, (agent_id, group, version))
            content = row.config if row else None
        else:
            row = await s.get(AgentVersion, (agent_id, version))
            content = row.manifest if row else None
    if row is None:
        raise LookupError(f"{agent_id}{'/' + group if group else ''} v{version}")
    body = _body("group" if group else "agent", agent_id, version, content, group)
    digest = _digest(body)
    return {**body, "source_env": settings().env_name, "status_at_source": row.status,
            "exported_by": caller.user_id, "exported_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest, "signature": _signature(digest)}


async def import_bundle(bundle: dict, caller: Caller) -> dict:
    """A bundle from another environment becomes a draft here — never live."""
    if bundle.get("format") != BUNDLE_FORMAT:
        raise agents.AgentError(f"not a {BUNDLE_FORMAT} bundle")
    body = _body(bundle["kind"], bundle["agent_id"], bundle["version"], bundle["content"], bundle.get("group"))
    digest = _digest(body)
    if digest != bundle.get("sha256"):
        raise agents.AgentError("the bundle was changed after export (checksum mismatch)")
    expected = _signature(digest)
    if expected and not hmac.compare_digest(expected, bundle.get("signature") or ""):
        raise agents.AgentError("the bundle is not signed with this deployment's promotion key")
    note = (f"promoted from {bundle.get('source_env', '?')} v{bundle['version']} "
            f"(sha256 {digest[:12]}…, exported by {bundle.get('exported_by', '?')})")
    if bundle["kind"] == "group":
        out = await team_groups.draft(bundle["agent_id"], bundle["content"], note, caller)
        return {"kind": "group", "agent_id": bundle["agent_id"], "group": out["group_id"],
                "version": out["version"], "note": note}
    try:
        await agents.active(bundle["agent_id"])
        exists = True
    except agents.AgentError:
        exists = False
    v = (await agents.draft(bundle["agent_id"], bundle["content"], note, caller) if exists
         else await agents.draft_new(bundle["content"], note, caller))
    return {"kind": "agent", "agent_id": bundle["agent_id"], "version": v, "note": note}


async def group_versions(agent_id: str, group: str) -> list[int]:
    async with get_session() as s:
        return list((await s.execute(select(GroupVersion.version).where(
            GroupVersion.agent_id == agent_id, GroupVersion.group_id == group))).scalars())
