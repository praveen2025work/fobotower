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

    A row created earlier without a workflow version (a recorded session, or
    a run from before versioning) takes the version of the run starting now.
    Once set, a run's version never changes.
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
            where=InvestigationSession.workflow_version.is_(None),
        )
    )
    await session.execute(stmt)
    await session.commit()
