"""Fan out per break: delta, cause checks, lineage, priors.

Degradation is graded, per the failure matrix:
  - missing delta or cause checks  -> escalate, there is nothing to explain
  - missing priors or lineage      -> continue, flag an evidence gap

Nothing is substituted for a value that could not be retrieved.

Retrievals are recorded the way the Helix session shows them: one MCP call per
tool, carrying a row per break. Helix reads breaks from MB Rec, never from
CATS or MOTIF directly, and history and lineage from its own knowledge graph.
"""

import time

from app.graph.repository import GraphRepository
from app.grounding.recorder import GroundingRecorder
from app.recon.checks import run_cause_checks
from app.workflow.config import settings
from app.workflow.state import InvestigationState

EXPECTED_CHECKS = 6

MBREC = "MBRec"
KG = "HelixKG"

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


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _workspace(state: InvestigationState) -> dict:
    return {
        "rec": state["reconciliation_id"],
        "masterBook": state["master_book"],
        "cob": str(state["as_of"]),
    }


def _leg_rows(breaks: list[dict]) -> list[dict]:
    """Both sides of each break as MB Rec holds them: the CATS leg and the
    MOTIF leg. A side with no value is a missing leg, not a zero."""
    rows = []
    for brk in breaks:
        for leg, key in (("CATS", "fo_value"), ("MOTIF", "bo_value")):
            rows.append(
                {
                    "breakId": brk["break_id"],
                    "masterBook": brk["book_ref"],
                    "leg": leg,
                    "amount": brk.get(key),
                }
            )
    return rows


async def gather(state: InvestigationState, *, session) -> dict:
    repo = GraphRepository(session)
    recorder = GroundingRecorder(session, state["investigation_session_id"])
    cfg = settings().gather
    as_of = state["as_of"]
    caller = state["caller"]
    breaks = state["breaks"]

    deltas: dict[str, float] = {}
    candidates: dict[str, list] = {}
    priors: dict[str, list] = {}
    lineage: dict[str, list] = {}
    gaps = list(state.get("evidence_gaps", []))

    await recorder.record(
        application=MBREC,
        tool="mbrec.get_breaks",
        params=_workspace(state),
        row_count=len(breaks),
        summary=f"{len(breaks)} breaks",
        rows=[
            {
                "breakId": b["break_id"],
                "masterBook": b["book_ref"],
                "line": b.get("line_code", "CASH"),
                "delta": (
                    b["fo_value"] - b["bo_value"]
                    if b.get("fo_value") is not None and b.get("bo_value") is not None
                    else None
                ),
            }
            for b in breaks
        ],
    )

    started = time.perf_counter()
    for brk in breaks:
        bid = brk["break_id"]
        fo, bo = brk.get("fo_value"), brk.get("bo_value")
        if fo is None or bo is None:
            await recorder.record(
                application=MBREC,
                tool="mbrec.get_break_legs",
                params=_workspace(state) | {"breakIds": [bid]},
                row_count=None,
                summary="unavailable",
                error=f"{bid}: a leg is missing, so there is no delta to explain",
                latency_ms=_ms(started),
            )
            return {"outcome": "escalated", "escalation_reason": "DELTA_UNAVAILABLE"}
        deltas[bid] = fo - bo

        candidates[bid] = run_cause_checks(_snapshot(brk))
        if len(candidates[bid]) != EXPECTED_CHECKS:
            return {"outcome": "escalated", "escalation_reason": "CHECKS_UNAVAILABLE"}

    await recorder.record(
        application=MBREC,
        tool="mbrec.get_break_legs",
        params=_workspace(state) | {"breakIds": [b["break_id"] for b in breaks]},
        row_count=len(breaks) * 2,
        summary=f"{len(breaks) * 2} leg entries",
        latency_ms=_ms(started),
        rows=_leg_rows(breaks),
    )

    lineage_rows, lineage_errors = [], []
    started = time.perf_counter()
    for brk in breaks:
        bid = brk["break_id"]
        try:
            lineage[bid] = await repo.lineage(
                state["book_resolutions"][bid], "BELONGS_TO",
                cfg.lineage_max_depth, as_of, caller,
            )
            lineage_rows.append(
                {
                    "breakId": bid,
                    "masterBook": brk["book_ref"],
                    "path": " → ".join(
                        [brk["book_ref"]] + [n["natural_key"] for n in lineage[bid]]
                    ),
                }
            )
        except Exception as exc:
            lineage[bid] = []
            gaps.append(f"lineage:{bid}")
            lineage_errors.append(f"{bid}: {exc}")
    await recorder.record(
        application=KG,
        tool="helix.kg_lineage",
        params=_workspace(state) | {"edge": "BELONGS_TO", "asOf": str(as_of)},
        row_count=len(lineage_rows) if lineage_rows else None,
        summary=(
            f"{len(lineage_rows)} books resolved"
            if not lineage_errors
            else f"{len(lineage_errors)} lookups failed"
        ),
        error="; ".join(lineage_errors) or None,
        latency_ms=_ms(started),
        rows=lineage_rows,
    )

    prior_rows, prior_errors = [], []
    started = time.perf_counter()
    for brk in breaks:
        bid = brk["break_id"]
        try:
            priors[bid] = await repo.similar_breaks(
                state["book_resolutions"][bid], brk.get("line_code", "CASH"), as_of,
                cfg.priors_lookback_days, caller, limit=cfg.max_similar_breaks,
            )
            approved = sum(1 for p in priors[bid] if p.get("outcome") == "approved")
            prior_rows.append(
                {
                    "breakId": bid,
                    "masterBook": brk["book_ref"],
                    "priors": len(priors[bid]),
                    "approved": approved,
                }
            )
        except Exception as exc:
            priors[bid] = []
            gaps.append(f"priors:{bid}")
            prior_errors.append(f"{bid}: {exc}")
    await recorder.record(
        application=KG,
        tool="helix.similar_breaks",
        params=_workspace(state) | {"lookback": f"{cfg.priors_lookback_days}d"},
        row_count=len(prior_rows) if prior_rows else None,
        summary=(
            f"{sum(r['priors'] for r in prior_rows)} prior resolutions"
            if not prior_errors
            else f"{len(prior_errors)} lookups failed"
        ),
        error="; ".join(prior_errors) or None,
        latency_ms=_ms(started),
        rows=prior_rows,
    )

    return {
        "deltas": deltas,
        "candidates": candidates,
        "priors": priors,
        "lineage": lineage,
        "evidence_gaps": gaps,
    }
