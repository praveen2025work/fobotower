"""Run one investigation end to end and print what a controller would see.

    .venv/bin/python scripts/demo_investigation.py

Loads fixtures, runs the workflow to the human interrupt, prints the drafted
analysis and pattern groups, then resumes with per-group approvals and shows
the recorded outcome.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa: E402

from app.contracts.models import Caller  # noqa: E402
from app.db.base import DATABASE_URL, get_session  # noqa: E402
from app.workflow.graph import (  # noqa: E402
    build_graph,
    resume_investigation,
    run_investigation,
)
from fixtures.loader import load_all, read_breaks  # noqa: E402

DSN = DATABASE_URL.replace("+asyncpg", "")
SESSION_ID = "demo-r1055"

CAUSE_TO_SNAPSHOT = {
    "C1": {"fo_booking_ts": "2026-08-04T00:15:00Z"},
    "C2": {"mapping_present": False},
    "C5": {"fo_version": 2},
    "C6": {"bo_adjustments": ["manual-1"]},
}

CALLER = Caller(
    staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC"
)


def rule(title: str) -> None:
    print(f"\n{'─' * 72}\n{title}\n{'─' * 72}")


async def main() -> None:
    state = {
        "investigation_session_id": SESSION_ID,
        "reconciliation_id": "R-1055",
        "master_book": "APAC-CASH",
        "business_date": date(2026, 8, 3),
        "run_id": "run-1100",
        "caller": CALLER,
        "breaks": [r | CAUSE_TO_SNAPSHOT[r["cause"]] for r in read_breaks()],
        "book_resolutions": {},
        "evidence_gaps": [],
        "hypothesis_attempts": 0,
        "review_cycles": 0,
    }

    async with get_session() as s:
        await load_all(s)
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp:
            await cp.setup()
            await run_investigation(
                state, thread_id=SESSION_ID, session=s, checkpointer=cp
            )

    # Fresh connections, as a restarted worker would have.
    async with get_session() as s2:
        async with AsyncPostgresSaver.from_conn_string(DSN) as cp2:
            snap = await build_graph(cp2, session=s2).aget_state(
                {"configurable": {"thread_id": SESSION_ID}}
            )
            v = snap.values

            rule(f"R-1055  ·  APAC-CASH  ·  COB {v['business_date']}")
            print(f"parked at   : {snap.next}")
            print(f"breaks      : {len(v['breaks'])}")
            print(f"model calls : {'0 (fast path)' if v['model_skipped'] else 'needed'}")
            gaps = v["evidence_gaps"]
            print(f"evidence gaps: {gaps if gaps else 'none'}")

            d = v["draft"]
            rule("AGENT ANALYSIS")
            for heading, body in (
                ("WHAT HAPPENED", d.what_happened),
                ("WHY", d.why),
                ("WHAT TO DO", d.what_to_do),
                ("RISK", d.risk),
            ):
                print(f"\n{heading}\n  {body}")
            print(f"\nConfidence basis\n  {d.confidence_basis}")

            rule(f"DRAFTED ADJUSTMENTS  ·  {len(v['pattern_groups'])} decisions")
            for g in v["pattern_groups"]:
                total = sum(v["deltas"][b] for b in g.break_ids)
                rate = (
                    f"{g.historical_approval_rate:.0%} prior approval"
                    if g.historical_approval_rate is not None
                    else "no priors"
                )
                print(
                    f"\n  [{g.mode.upper():6}] {g.label}  ({g.pattern_code})"
                    f"  ·  {len(g.break_ids)} books  ·  {rate}"
                )
                for bid in g.break_ids:
                    book = next(
                        b["book_ref"] for b in v["breaks"] if b["break_id"] == bid
                    )
                    print(f"           {book:16} ${v['deltas'][bid]:>10,.2f}")
                print(f"           {'TOTAL':16} ${total:>10,.2f}")

            errors = v["validation_errors"]
            rule("VALIDATION")
            print(f"  {'PASS — every figure traces to a delta' if not errors else errors}")

            rule("HUMAN SIGN-OFF  ·  approving all groups")
            final = await resume_investigation(
                SESSION_ID,
                decisions=[
                    {"group_id": g.group_id, "action": "approve"}
                    for g in v["pattern_groups"]
                ],
                session=s2,
                checkpointer=cp2,
            )
            print(f"  outcome       : {final['outcome']}")
            print(f"  review cycles : {final['review_cycles']}")
            print("  breaks stamped with pattern + outcome for tomorrow's priors\n")


if __name__ == "__main__":
    asyncio.run(main())
