"""Retention: finished cases are removed when their capability's
`retention.days` have passed, unless a legal hold is on the case.

Removing a case removes everything recorded for it — items, groups,
decisions, chat, tool calls, the reports it published, its LangGraph
checkpoints and what it taught the knowledge graph — and leaves one
aof_retention_event row saying that it existed and when it went.

    python -m agent_one_finance.retention              # purge what is due
    python -m agent_one_finance.retention --dry-run    # list what would go
"""

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text

from agent_one_finance import capabilities, knowledge
from agent_one_finance.db import engine, get_session
from agent_one_finance.models import Case, Document, RetentionEvent, ToolCall

FINISHED = ("completed", "failed", "escalated", "shadow")


async def due(now: datetime | None = None) -> list[tuple[Case, int]]:
    """(case, retention days) for every finished case past its retention."""
    now = now or datetime.now(timezone.utc)
    out = []
    for _, m in await capabilities.all_active():
        if m.retention is None:
            continue
        cutoff = now - timedelta(days=m.retention.days)
        async with get_session() as s:
            rows = (await s.execute(select(Case).where(
                Case.capability_id == m.id, Case.status.in_(FINISHED),
                Case.legal_hold.is_(False), Case.opened_at < cutoff))).scalars().all()
        out += [(c, m.retention.days) for c in rows]
    return out


async def purge(now: datetime | None = None, by: str = "system:retention",
                dry_run: bool = False) -> list[str]:
    cases = await due(now)
    if dry_run:
        return [c.case_id for c, _ in cases]
    for case, days in cases:
        async with get_session() as s:
            calls = (await s.execute(select(ToolCall).where(ToolCall.case_id == case.case_id))).scalars().all()
            for c in calls:
                r = c.result if isinstance(c.result, dict) else {}
                if c.requested_by == "publish" and r.get("document") and r.get("scope"):
                    await s.execute(delete(Document).where(Document.scope == r["scope"],
                                                           Document.name == r["document"]))
            await s.execute(delete(ToolCall).where(ToolCall.case_id == case.case_id))
            await s.execute(delete(Case).where(Case.case_id == case.case_id))   # cascades
            s.add(RetentionEvent(event_id=uuid.uuid4().hex, case_id=case.case_id,
                                 capability_id=case.capability_id, subject=case.subject,
                                 opened_at=case.opened_at, retention_days=days, purged_by=by))
            await s.commit()
        await knowledge.forget_case(case.capability_id, case.case_id)
        async with engine.begin() as conn:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                await conn.execute(text(f"DELETE FROM {table} WHERE thread_id = :t"),
                                   {"t": f"aof:{case.case_id}"})
    return [c.case_id for c, _ in cases]


async def set_legal_hold(case_id: str, hold: bool, reason: str | None, caller) -> dict:
    """Capability owners put a case on (or take it off) legal hold. A held
    case is never removed by retention."""
    from agent_one_finance.cases import CaseError, _pinned

    async with get_session() as s:
        case = await s.get(Case, case_id)
        if case is None:
            raise LookupError(case_id)
        m = await _pinned(case)
        _, current = await capabilities.active(case.capability_id)
        if not (capabilities.is_owner(caller, m) or capabilities.is_owner(caller, current)):
            raise PermissionError(f"{caller.user_id} does not own {case.capability_id}")
        if hold and not (reason or "").strip():
            raise CaseError("a legal hold needs a reason")
        case.legal_hold = hold
        case.legal_hold_reason = (reason or "").strip() or None if hold else None
        await s.commit()
        return {"legal_hold": case.legal_hold, "legal_hold_reason": case.legal_hold_reason}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    ids = asyncio.run(purge(dry_run=a.dry_run))
    print(("would remove" if a.dry_run else "removed"), len(ids), "case(s)")
    for i in ids:
        print(" ", i)


if __name__ == "__main__":
    main()
