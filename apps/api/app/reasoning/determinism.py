"""Deterministic classification — the orchestrator's real job.

The skill states that ~80% of breaks are codifiable. Every break this module
resolves is one that never reaches the LLM, so coverage here is the lever:
it decides cost, latency and variance for the whole run.

Each rule states the evidence it relied on. A rule that cannot say why it
fired is not auditable, and R7 requires the applied rule be stated.
"""

from dataclasses import dataclass, field

from app.reasoning.contracts import CATEGORY_NAMES

# Cause check -> break classification (skill §9).
CHECK_TO_CATEGORY = {
    "C1": "C",  # late nostro against cutoff -> redemption/timing
    "C2": "F",  # reference unresolved in static -> data quality
    "C3": "A",  # differing curve datasets -> price
    "C4": "E",  # one-sided component -> trade booking
    "C5": "E",  # version mismatch -> trade booking
    "C6": "D",  # duplicate settlement
}

# The skill's named deterministic patterns (§9) that are decidable from the
# break record alone, without a model.
PATTERN_MISSING_SIDE = "missing_side"
PATTERN_SIDE_DOUBLE = "side_double"
PATTERN_MISSING_PRICE = "missing_price"
PATTERN_REAPPLICATION = "reapplication"
PATTERN_POSTING_FAILURE = "posting_failure"
PATTERN_SINGLE_CAUSE = "single_cause"


@dataclass
class Determination:
    """A deterministic finding, or the reason there isn't one."""

    resolved: bool
    pattern: str | None = None
    rule_applied: str | None = None
    category_code: str | None = None
    root_cause: str | None = None
    verdict: str | None = None
    evidence: list[str] = field(default_factory=list)
    unresolved_reason: str | None = None

    def as_finding(self, reason_text: str | None = None) -> dict:
        return {
            "root_cause": self.root_cause or reason_text or "",
            "established": True,
            "category_code": self.category_code,
            "category_name": CATEGORY_NAMES.get(self.category_code, "Novel break"),
            "deterministic": True,
            "pattern": self.pattern,
            "rule_applied": self.rule_applied,
            "requires_sme_review": False,
            "verdict": self.verdict,
            "evidence": self.evidence,
            "competing_hypotheses": [],
            "unset_parameters": [],
        }


def _positives(candidates) -> list:
    return [c for c in candidates if c.positive]


def classify(brk: dict, candidates: list, *, delta: float | None,
             priors: list | None = None) -> Determination:
    """Decide whether this break is codifiable.

    Ordered most-specific first: a posting failure is mechanical regardless
    of what else fired, and the skill is explicit that it is not a
    'should we post?' question.
    """
    priors = priors or []

    # Posting failure — MOTIF rejected a posting that should have occurred.
    if brk.get("motif_rejected"):
        return Determination(
            resolved=True,
            pattern=PATTERN_POSTING_FAILURE,
            rule_applied="§8 posting failure",
            category_code="F",
            root_cause="Posting was legitimate but rejected by MOTIF",
            verdict="CORRECT_AND_REPOST",
            evidence=[f"motif_rejection={brk.get('motif_rejection_reason', 'unknown')}"],
        )

    # Missing side — one side absent entirely.
    fo, bo = brk.get("fo_value"), brk.get("bo_value")
    if fo is None or bo is None:
        present, absent = ("FO", "BO") if fo is not None else ("BO", "FO")
        return Determination(
            resolved=True,
            pattern=PATTERN_MISSING_SIDE,
            rule_applied="§8 missing side",
            category_code="F",
            root_cause=f"{absent} side absent; {present} side present",
            verdict=None,  # §8: post only if evidence supports legitimacy
            evidence=[f"fo_value={fo}", f"bo_value={bo}"],
        )

    # Missing price — a zero price is ambiguous until evidenced (FO-7), so it
    # is deterministic only when the record says which it is.
    if brk.get("price") == 0 and brk.get("corporate_action_confirmed") is False:
        return Determination(
            resolved=True,
            pattern=PATTERN_MISSING_PRICE,
            rule_applied="FO-7",
            category_code="A",
            root_cause="Price is zero with no corporate action on file",
            verdict="DO_NOT_POST",
            evidence=["price=0", "corporate_action_confirmed=false"],
        )

    # Side double — the same side duplicated.
    if brk.get("duplicate_side_count", 0) > 1:
        return Determination(
            resolved=True,
            pattern=PATTERN_SIDE_DOUBLE,
            rule_applied="§9 side double",
            category_code="F",
            root_cause="One side duplicated; auto-posting exclusion",
            verdict="DO_NOT_POST",
            evidence=[f"duplicate_side_count={brk['duplicate_side_count']}"],
        )

    # Reapplication — today's break is a prior-day adjustment rolling forward.
    match = _matching_prior(delta, priors)
    if match is not None:
        return Determination(
            resolved=True,
            pattern=PATTERN_REAPPLICATION,
            rule_applied="§8 reapplication",
            category_code="F",
            root_cause="Prior-day adjustment reapplied as today's break",
            verdict="POST",
            evidence=[f"matches prior {match}"],
        )

    # Single firing cause — the codified rule applies (R7).
    positives = _positives(candidates)
    if len(positives) == 1:
        check = positives[0].check_id
        return Determination(
            resolved=True,
            pattern=PATTERN_SINGLE_CAUSE,
            rule_applied=check,
            category_code=CHECK_TO_CATEGORY.get(check, "H"),
            root_cause=positives[0].description,
            verdict=None,
            evidence=positives[0].supporting_ids,
        )

    if len(positives) > 1:
        return Determination(
            resolved=False,
            unresolved_reason=(
                "multiple simultaneous root causes: "
                + ", ".join(c.check_id for c in positives)
            ),
        )
    return Determination(
        resolved=False,
        unresolved_reason="no cause check fired; no existing playbook",
    )


def _matching_prior(delta: float | None, priors: list) -> str | None:
    """A prior resolution on the same book for the same amount.

    Exact match only. A tolerance here would be inventing a threshold,
    which Rule P1 forbids.
    """
    if delta is None:
        return None
    for prior in priors:
        if prior.get("outcome") != "approved":
            continue
        prior_delta = prior.get("delta")
        if prior_delta is not None and float(prior_delta) == float(delta):
            return str(prior.get("break_id"))
    return None


def coverage(determinations: dict[str, Determination]) -> dict:
    """What share of the run never needs the LLM."""
    total = len(determinations)
    resolved = sum(1 for d in determinations.values() if d.resolved)
    by_pattern: dict[str, int] = {}
    for d in determinations.values():
        if d.resolved and d.pattern:
            by_pattern[d.pattern] = by_pattern.get(d.pattern, 0) + 1
    return {
        "total": total,
        "deterministic": resolved,
        "escalated_to_reasoner": total - resolved,
        "share": round(resolved / total, 3) if total else None,
        "by_pattern": by_pattern,
    }
