"""Collapse breaks into pattern groups.

This node is the efficiency lever: 14 breaks become 4 decisions. It clusters
by cause-check signature, then attaches a pattern label and the historical
approval rate derived from prior resolutions.

Neither the architecture doc nor the BRD contains this step, but the mock's
headline metric ("decisions saved 20 to 6") depends on it, so it needs an
owner. Phase 3 adds a pgvector rerank against historical resolution
narratives; the structural clustering below stays the deterministic core.
"""

from collections import defaultdict

from sqlalchemy import select

from app.contracts.models import PatternGroup
from app.db.models_graph import BreakEvent
from app.recon.reasons import reason_for
from app.workflow.state import InvestigationState

PATTERNS = {
    "C1": ("P-204", "FX timing lag", "auto"),
    "C2": ("CPTY-REF", "Unmatched counterparty reference", "manual"),
    "C3": ("VAL-DATASET", "Valuation dataset mismatch", "manual"),
    "C4": ("COMP-ONESIDE", "One-sided component", "manual"),
    "C5": ("LATE-BOOK", "Late trade booking", "manual"),
    "C6": ("DUP-SETTLE", "Duplicate settlement suspected", "manual"),
}

# Ties are broken in check order, so grouping is deterministic.
CHECK_ORDER = ["C1", "C2", "C3", "C4", "C5", "C6"]

UNGROUPED = "UNGROUPED"


def _signature(candidates) -> str | None:
    """The dominant positive check. None means no cause was found."""
    positives = {c.check_id for c in candidates if c.positive}
    for check in CHECK_ORDER:
        if check in positives:
            return check
    return None


def _distinct_priors(priors_by_break: dict[str, list[dict]]) -> list[dict]:
    """Deduplicate by break_id.

    A book can carry more than one break in the population, and each break
    pulls that book's priors. Flattening without deduplication double-counts
    those books and skews the approval rate.
    """
    seen: dict[str, dict] = {}
    for prior_list in priors_by_break.values():
        for prior in prior_list:
            seen[prior["break_id"]] = prior
    return list(seen.values())


def _approval_rate(priors: list[dict], pattern_code: str) -> float | None:
    relevant = [p for p in priors if p["pattern_code"] == pattern_code]
    if not relevant:
        return None
    approved = [p for p in relevant if p["outcome"] == "approved"]
    return round(len(approved) / len(relevant), 2)



async def _enrich_breaks(session, state, signatures: dict[str, str]) -> dict:
    """Write reason wording and first-seen run onto each break row, and read
    back the flags the group badges need.

    first_seen_run_id is written once and never overwritten: the span between
    it and the current run is what makes a break aged, and overwriting it
    would silently reset the age every run.
    """
    run_id = state["run_id"]
    reasons: dict[str, str] = {}
    ungrounded: set[str] = set()
    carried: dict[str, int] = {}

    for bid, check in signatures.items():
        reason = reason_for(check) if check is not None else "No cause identified"
        reasons[bid] = reason

        row = await session.scalar(
            select(BreakEvent).where(BreakEvent.break_id == bid)
        )
        if row is None:
            carried[bid] = 0
            continue

        row.reason_text = reason
        if row.first_seen_run_id is None:
            row.first_seen_run_id = run_id
        if row.is_ungrounded:
            ungrounded.add(bid)
        carried[bid] = 0 if row.first_seen_run_id == run_id else 1

    await session.commit()
    return {"reasons": reasons, "ungrounded": ungrounded, "carried": carried}


async def group(state: InvestigationState, *, session) -> dict:
    signatures: dict[str, str | None] = {}
    clusters: dict[str, list[str]] = defaultdict(list)
    for brk in state["breaks"]:
        bid = brk["break_id"]
        sig = _signature(state["candidates"][bid])
        signatures[bid] = sig
        clusters[sig if sig is not None else UNGROUPED].append(bid)

    enriched = await _enrich_breaks(session, state, signatures)
    priors = _distinct_priors(state.get("priors", {}))
    session_id = state["investigation_session_id"]

    groups: list[PatternGroup] = []
    for check in CHECK_ORDER:
        if check not in clusters:
            continue
        code, label, mode = PATTERNS[check]
        groups.append(
            PatternGroup(
                group_id=f"{session_id}:{code}",
                pattern_code=code,
                label=label,
                mode=mode,
                break_ids=clusters[check],
                historical_approval_rate=_approval_rate(priors, code),
            )
        )

    if UNGROUPED in clusters:
        groups.append(
            PatternGroup(
                group_id=f"{session_id}:{UNGROUPED}",
                pattern_code=UNGROUPED,
                label="No cause identified",
                mode="manual",
                break_ids=clusters[UNGROUPED],
                historical_approval_rate=None,
            )
        )

    group_meta = {
        g.group_id: {
            "ungrounded_count": sum(
                1 for b in g.break_ids if b in enriched["ungrounded"]
            ),
            "carried_runs": max(
                (enriched["carried"].get(b, 0) for b in g.break_ids), default=0
            ),
        }
        for g in groups
    }

    return {
        "pattern_groups": groups,
        "reasons": enriched["reasons"],
        "group_meta": group_meta,
    }
