"""Investigation session row lifecycle.

The row must exist before `gather` runs: source_call carries a foreign key
to it, and gather records its retrievals as it makes them. Phase 1 created
the row in `record`, at the end, which is too late.
"""

from sqlalchemy.dialects.postgresql import insert

from app.db.models_session import InvestigationSession
from app.workflow.state import InvestigationState


async def ensure_investigation_session(session, state: InvestigationState) -> None:
    """Idempotent insert.

    ON CONFLICT rather than a read-then-write: the console fires two
    investigates at once in dev (React StrictMode), and a check-then-act
    lets both see no row and both insert. The primary key is the authority.

    The row records the version of the run that last started on this
    thread: a run starting now always takes it, whether the row is new, is
    from before versioning, or was last written by an earlier run on an
    older version. It does not change again while that run is paused —
    resuming it never calls this — only a new run (a fresh POST /investigate
    on the thread) does.
    """
    version = state.get("workflow_version")
    stmt = (
        insert(InvestigationSession)
        .values(
            investigation_session_id=state["investigation_session_id"],
            reconciliation_id=state["reconciliation_id"],
            master_book=state["master_book"],
            business_date=state["business_date"],
            run_id=state["run_id"],
            status="analysing",
            workflow_version=version,
        )
        .on_conflict_do_update(
            index_elements=["investigation_session_id"],
            set_={"workflow_version": version},
        )
    )
    await session.execute(stmt)
    await session.commit()
