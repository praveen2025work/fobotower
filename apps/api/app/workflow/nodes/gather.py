"""Fan out per break: delta, cause checks, lineage, priors.

Degradation is graded, per the failure matrix:
  - missing delta or cause checks  -> escalate, there is nothing to explain
  - missing priors or lineage      -> continue, flag an evidence gap

Nothing is substituted for a value that could not be retrieved.
"""

from app.graph.repository import GraphRepository
from app.grounding.recorder import GroundingRecorder
from app.recon.checks import run_cause_checks
from app.workflow.state import InvestigationState

EXPECTED_CHECKS = 6

# Defaults stand in for the CATS and MOTIF adapters, which arrive in Phase 3.
SNAPSHOT_DEFAULTS = {
    "fo_booking_ts": "2026-08-03T22:00:00Z",
    "bo_cutoff_ts": "2026-08-03T23:30:00Z",
    "mapping_present": True,
    "fo_dataset_id": "EOD-2026-08-03",
    "bo_dataset_id": "EOD-2026-08-03",
    "fo_components": ["principal"],
    "bo_components": ["principal"],
    "fo_version": 1,
    "bo_version": 1,
    "fo_adjustments": [],
    "bo_adjustments": [],
}


def _snapshot(brk: dict) -> dict:
    snap = {"break_id": brk["break_id"]}
    for key, default in SNAPSHOT_DEFAULTS.items():
        snap[key] = brk.get(key, default)
    return snap


async def gather(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    recorder = GroundingRecorder(session, state["investigation_session_id"])
    as_of = state["as_of"]
    caller = state["caller"]

    deltas: dict[str, float] = {}
    candidates: dict[str, list] = {}
    priors: dict[str, list] = {}
    lineage: dict[str, list] = {}
    gaps = list(state.get("evidence_gaps", []))

    await recorder.record(
        application="RecFactory",
        tool="RecFactory.getBreaks",
        params={
            "rec": state["reconciliation_id"],
            "book": state["master_book"],
            "date": str(as_of),
        },
        row_count=len(state["breaks"]),
        summary=f"{len(state['breaks'])} breaks returned",
    )

    for brk in state["breaks"]:
        bid = brk["break_id"]
        book_id = state["book_resolutions"][bid]

        fo, bo = brk.get("fo_value"), brk.get("bo_value")
        if fo is None or bo is None:
            await recorder.record(
                application="CATS",
                tool="CATS.getCashMovements",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=None,
                summary="unavailable",
                error="delta unavailable",
            )
            return {"outcome": "escalated", "escalation_reason": "DELTA_UNAVAILABLE"}
        deltas[bid] = fo - bo

        candidates[bid] = run_cause_checks(_snapshot(brk))
        if len(candidates[bid]) != EXPECTED_CHECKS:
            return {"outcome": "escalated", "escalation_reason": "CHECKS_UNAVAILABLE"}

        try:
            lineage[bid] = await repo.lineage(book_id, "BELONGS_TO", 4, as_of, caller)
            await recorder.record(
                application="MOTIF",
                tool="MOTIF.getLedgerEntries",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=len(lineage[bid]),
                summary=f"{len(lineage[bid])} lineage nodes",
            )
        except Exception as exc:
            lineage[bid] = []
            gaps.append(f"lineage:{bid}")
            await recorder.record(
                application="MOTIF",
                tool="MOTIF.getLedgerEntries",
                params={"book": brk["book_ref"], "valueDate": str(as_of)},
                row_count=None,
                summary="unavailable",
                error=str(exc),
            )

        try:
            priors[bid] = await repo.similar_breaks(
                book_id, brk.get("line_code", "CASH"), as_of, 180, caller
            )
            await recorder.record(
                application="RecFactory",
                tool="RecFactory.getResolutionHistory",
                params={"book": brk["book_ref"], "lookback": "180d"},
                row_count=len(priors[bid]),
                summary=f"{len(priors[bid])} prior resolutions",
            )
        except Exception as exc:
            priors[bid] = []
            gaps.append(f"priors:{bid}")
            await recorder.record(
                application="RecFactory",
                tool="RecFactory.getResolutionHistory",
                params={"book": brk["book_ref"], "lookback": "180d"},
                row_count=None,
                summary="unavailable",
                error=str(exc),
            )

    await recorder.record(
        application="CATS",
        tool="CATS.getCashMovements",
        params={"book": state["master_book"], "valueDate": str(as_of)},
        row_count=len(deltas),
        summary=f"{len(deltas)} movements compared",
    )

    return {
        "deltas": deltas,
        "candidates": candidates,
        "priors": priors,
        "lineage": lineage,
        "evidence_gaps": gaps,
    }
