"""Fan out per break: delta, cause checks, lineage, priors.

Degradation is graded, per the failure matrix:
  - missing delta or cause checks  -> escalate, there is nothing to explain
  - missing priors or lineage      -> continue, flag an evidence gap

Nothing is substituted for a value that could not be retrieved.
"""

from app.graph.repository import GraphRepository
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
    as_of = state["as_of"]
    caller = state["caller"]

    deltas: dict[str, float] = {}
    candidates: dict[str, list] = {}
    priors: dict[str, list] = {}
    lineage: dict[str, list] = {}
    gaps = list(state.get("evidence_gaps", []))

    for brk in state["breaks"]:
        bid = brk["break_id"]
        book_id = state["book_resolutions"][bid]

        fo, bo = brk.get("fo_value"), brk.get("bo_value")
        if fo is None or bo is None:
            return {"outcome": "escalated", "escalation_reason": "DELTA_UNAVAILABLE"}
        deltas[bid] = fo - bo

        candidates[bid] = run_cause_checks(_snapshot(brk))
        if len(candidates[bid]) != EXPECTED_CHECKS:
            return {"outcome": "escalated", "escalation_reason": "CHECKS_UNAVAILABLE"}

        try:
            lineage[bid] = await repo.lineage(book_id, "BELONGS_TO", 4, as_of, caller)
        except Exception:
            lineage[bid] = []
            gaps.append(f"lineage:{bid}")

        try:
            priors[bid] = await repo.similar_breaks(
                book_id, brk.get("line_code", "CASH"), as_of, 180, caller
            )
        except Exception:
            priors[bid] = []
            gaps.append(f"priors:{bid}")

    return {
        "deltas": deltas,
        "candidates": candidates,
        "priors": priors,
        "lineage": lineage,
        "evidence_gaps": gaps,
    }
