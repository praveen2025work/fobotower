"""The knowledge graph: what a capability has learned, and the reference
data it reasons over.

Namespaced, bitemporal (valid_from / valid_to, part of the key): a node or
edge is never updated in place — one version is closed and the next opened —
so a read "as of" a date sees what was true then. Two kinds of knowledge:

  learned     `record` writes each approved decision, linked to the subject
              it explains (its group key) and to the entities it concerns
              (manifest `knowledge.entities`: accounts, books, counterparties…).
              `group` reads them back as priors: the same subject first, then
              decisions about the same entities, most shared first.

  reference   lineage and ownership — a book belongs to a desk, a desk
              escalates to a team — loaded from config/helix/knowledge/*.yaml
              with explicit validity dates, and walked by the `resolve` step.
"""

import json
from datetime import date, datetime, time, timedelta, timezone

import yaml
from sqlalchemy import and_, delete, select

from helix.config import settings
from helix.db import get_session
from helix.models import KgEdge, KgNode

EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def subject_id(group_key: dict) -> str:
    return "subject:" + json.dumps(group_key, sort_keys=True, separators=(",", ":"))


def entity_id(field: str, value) -> str:
    return f"entity:{field}:{value}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _live(t, at: datetime):
    return and_(t.valid_from <= at, (t.valid_to.is_(None)) | (t.valid_to > at))


async def _has_node(s, namespace: str, node_id: str) -> bool:
    return (await s.execute(select(KgNode.node_id).where(
        KgNode.namespace == namespace, KgNode.node_id == node_id).limit(1))).first() is not None


# ---------- learned ----------

async def record_decision(namespace: str, group_key: dict, *, case_id: str, group_id: str,
                          action: str, comment: str, decided_by: str,
                          entities: dict[str, set] | None = None) -> None:
    subject = subject_id(group_key)
    decision = f"decision:{case_id}:{group_id}"
    now = _now()
    async with get_session() as s:
        if await _has_node(s, namespace, decision):
            return
        if not await _has_node(s, namespace, subject):
            s.add(KgNode(namespace=namespace, node_id=subject, kind="subject", attrs=group_key,
                         valid_from=EPOCH))
        s.add(KgNode(namespace=namespace, node_id=decision, kind="decision", valid_from=now, attrs={
            "case_id": case_id, "group_id": group_id, "action": action,
            "comment": comment, "decided_by": decided_by, "at": now.isoformat(),
        }))
        s.add(KgEdge(namespace=namespace, from_id=decision, relation="explains", to_id=subject,
                     valid_from=now))
        for field, values in sorted((entities or {}).items()):
            for v in sorted(map(str, values)):
                eid = entity_id(field, v)
                if not await _has_node(s, namespace, eid):
                    s.add(KgNode(namespace=namespace, node_id=eid, kind="entity",
                                 attrs={"field": field, "value": v}, valid_from=EPOCH))
                    await s.flush()
                s.add(KgEdge(namespace=namespace, from_id=decision, relation="concerns", to_id=eid,
                             valid_from=now))
        await s.commit()


async def similar_decisions(namespace: str, group_key: dict, *, limit: int = 3,
                            as_of: datetime | None = None, exclude_case: str | None = None,
                            entities: dict[str, set] | None = None,
                            lookback_days: int | None = None) -> list[dict]:
    """Approved decisions to learn from: about the same subject first (newest
    first), then about the same entities (most shared first). Each says why
    it was chosen (`match`)."""
    at = as_of or _now()
    async with get_session() as s:
        same = (await s.execute(
            select(KgNode)
            .join(KgEdge, and_(KgEdge.namespace == KgNode.namespace, KgEdge.from_id == KgNode.node_id))
            .where(KgNode.namespace == namespace, KgNode.kind == "decision",
                   KgEdge.relation == "explains", KgEdge.to_id == subject_id(group_key),
                   _live(KgNode, at), _live(KgEdge, at))
            .order_by(KgNode.valid_from.desc())
        )).scalars().all()
        wanted = {entity_id(f, v): f for f, vs in (entities or {}).items() for v in map(str, vs)}
        shared: dict[str, set[str]] = {}
        if wanted:
            for from_id, to_id in (await s.execute(
                select(KgEdge.from_id, KgEdge.to_id).where(
                    KgEdge.namespace == namespace, KgEdge.relation == "concerns",
                    KgEdge.to_id.in_(list(wanted)), _live(KgEdge, at))
            )).all():
                shared.setdefault(from_id, set()).add(wanted[to_id])
            others = (await s.execute(select(KgNode).where(
                KgNode.namespace == namespace, KgNode.node_id.in_(list(shared)),
                _live(KgNode, at)))).scalars().all() if shared else []
        else:
            others = []

    since = at - timedelta(days=lookback_days) if lookback_days else None

    def usable(n: KgNode) -> bool:
        return (n.attrs.get("action") == "approve" and n.attrs.get("case_id") != exclude_case
                and (since is None or n.valid_from >= since))

    out = [{**n.attrs, "match": "same subject"} for n in same if usable(n)]
    seen = {n.node_id for n in same}
    ranked = sorted((n for n in others if n.node_id not in seen and usable(n)),
                    key=lambda n: (-len(shared[n.node_id]), -n.valid_from.timestamp()))
    out += [{**n.attrs, "match": "shared " + ", ".join(sorted(shared[n.node_id]))} for n in ranked]
    return out[:limit]


# ---------- reference ----------

def _when(v) -> datetime | None:
    if v is None:
        return None
    d = v if isinstance(v, date) else date.fromisoformat(str(v))
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


async def seed_reference() -> list[str]:
    """Load config/helix/knowledge/*.yaml. Each node and edge version is keyed
    by its valid_from, so loading again adds only what is new."""
    loaded = []
    folder = settings().config_dir / "knowledge"
    if not folder.exists():
        return loaded
    for path in sorted(folder.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        ns = doc["namespace"]
        default_from = _when(doc.get("valid_from")) or EPOCH
        async with get_session() as s:
            for n in doc.get("nodes", []):
                vf = _when(n.get("valid_from")) or default_from
                if await s.get(KgNode, (ns, n["id"], vf)) is None:
                    s.add(KgNode(namespace=ns, node_id=n["id"], kind=n.get("kind", "thing"),
                                 attrs=n.get("attrs", {}), valid_from=vf,
                                 valid_to=_when(n.get("valid_to"))))
            await s.flush()
            for e in doc.get("edges", []):
                vf = _when(e.get("valid_from")) or default_from
                if await s.get(KgEdge, (ns, e["from"], e["relation"], e["to"], vf)) is None:
                    s.add(KgEdge(namespace=ns, from_id=e["from"], relation=e["relation"], to_id=e["to"],
                                 attrs=e.get("attrs", {}), valid_from=vf,
                                 valid_to=_when(e.get("valid_to"))))
            await s.commit()
        loaded.append(ns)
    return loaded


def _as_of_day(value) -> datetime:
    """A reference read for a business date sees what held at any time that day."""
    d = _when(value) if value is not None else None
    return d.replace(hour=12) if d else _now()


async def walk(namespace: str, start_ids: set[str], path: list[str], *, as_of=None) -> dict[str, KgNode]:
    """For each start node, the node reached by following `path` (relations,
    in order) as of a date. Starts with no such path are left out."""
    at = _as_of_day(as_of)
    current = {sid: sid for sid in start_ids}          # start -> where it is now
    async with get_session() as s:
        for relation in path:
            if not current:
                break
            rows = (await s.execute(select(KgEdge.from_id, KgEdge.to_id).where(
                KgEdge.namespace == namespace, KgEdge.relation == relation,
                KgEdge.from_id.in_(set(current.values())), _live(KgEdge, at)))).all()
            step = dict(rows)
            current = {sid: step[at_id] for sid, at_id in current.items() if at_id in step}
        nodes = {n.node_id: n for n in (await s.execute(select(KgNode).where(
            KgNode.namespace == namespace, KgNode.node_id.in_(set(current.values())),
            _live(KgNode, at)))).scalars()} if current else {}
    return {sid: nodes[end] for sid, end in current.items() if end in nodes}


async def forget_case(namespace: str, case_id: str) -> int:
    """Remove what a case taught (retention). Subjects and entities stay."""
    prefix = f"decision:{case_id}:"
    async with get_session() as s:
        await s.execute(delete(KgEdge).where(KgEdge.namespace == namespace,
                                             KgEdge.from_id.startswith(prefix)))
        res = await s.execute(delete(KgNode).where(KgNode.namespace == namespace,
                                                   KgNode.node_id.startswith(prefix)))
        await s.commit()
    return res.rowcount or 0


def entity_values(fields: list[str], group_key: dict, items: list[dict]) -> dict[str, set]:
    """The entity values a group concerns: from its key, else from its items."""
    out: dict[str, set] = {}
    for f in fields:
        if f in group_key and group_key[f] not in (None, ""):
            out[f] = {group_key[f]}
        else:
            vals = {it.get(f) for it in items if it.get(f) not in (None, "")}
            if vals:
                out[f] = vals
    return out

