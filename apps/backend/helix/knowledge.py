"""The knowledge graph: subjects and the decisions people made about them.

Namespaced per capability, bitemporal (valid_from / valid_to): a node is
never updated in place, it is closed and a new one opened, so a read "as of"
a date sees what was known then. Approved decisions are written by `record`
and read back as priors by `group` — that is how a capability learns.
"""

import json
from datetime import datetime, timezone

from sqlalchemy import and_, select

from helix.db import get_session
from helix.models import KgEdge, KgNode


def subject_id(group_key: dict) -> str:
    return "subject:" + json.dumps(group_key, sort_keys=True, separators=(",", ":"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def record_decision(namespace: str, group_key: dict, *, case_id: str, group_id: str,
                          action: str, comment: str, decided_by: str) -> None:
    subject = subject_id(group_key)
    decision = f"decision:{case_id}:{group_id}"
    async with get_session() as s:
        if await s.get(KgNode, (namespace, subject)) is None:
            s.add(KgNode(namespace=namespace, node_id=subject, kind="subject", attrs=group_key))
        if await s.get(KgNode, (namespace, decision)) is None:
            s.add(KgNode(namespace=namespace, node_id=decision, kind="decision", attrs={
                "case_id": case_id, "group_id": group_id, "action": action,
                "comment": comment, "decided_by": decided_by, "at": _now().isoformat(),
            }))
            s.add(KgEdge(namespace=namespace, from_id=decision, relation="explains", to_id=subject))
        await s.commit()


async def similar_decisions(namespace: str, group_key: dict, *, limit: int = 3,
                            as_of: datetime | None = None,
                            exclude_case: str | None = None) -> list[dict]:
    """Approved decisions about the same subject, newest first."""
    at = as_of or _now()
    live = lambda t: and_(t.valid_from <= at, (t.valid_to.is_(None)) | (t.valid_to > at))  # noqa: E731
    async with get_session() as s:
        rows = (await s.execute(
            select(KgNode)
            .join(KgEdge, and_(KgEdge.namespace == KgNode.namespace, KgEdge.from_id == KgNode.node_id))
            .where(KgNode.namespace == namespace, KgNode.kind == "decision",
                   KgEdge.relation == "explains", KgEdge.to_id == subject_id(group_key),
                   live(KgNode), live(KgEdge))
            .order_by(KgNode.valid_from.desc())
        )).scalars().all()
    out = [r.attrs for r in rows
           if r.attrs.get("action") == "approve" and r.attrs.get("case_id") != exclude_case]
    return out[:limit]
