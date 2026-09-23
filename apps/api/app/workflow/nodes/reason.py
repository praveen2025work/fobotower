"""Skill-driven reasoning node.

R7 routing. A deterministic break applies its codified rule and never
reaches the model — that is the ~80% the skill says is codifiable, and
paying a model to restate a rule adds cost, latency and variance for nothing.

A judgement-based break is sent to the model with the skill as its system
prompt, and comes back as a recommendation for SME review, never an
assertion.

When no credential is configured the node degrades: it flags an evidence
gap and escalates rather than presenting a deterministic guess as a
reasoned verdict.
"""

from app.reasoning.client import ReasoningUnavailable
from app.reasoning.contracts import CATEGORY_NAMES
from app.reasoning.reasoner import reason_over_break
from app.workflow.state import InvestigationState

# Cause check -> break classification, from the skill's §9 table.
CHECK_TO_CATEGORY = {
    "C1": "C",  # late nostro / redemption timing
    "C2": "F",  # unresolved reference -> data quality
    "C3": "A",  # differing curve datasets -> price
    "C4": "E",  # one-sided component -> trade booking
    "C5": "E",  # version mismatch -> trade booking
    "C6": "D",  # duplicate settlement
}


def _is_judgement_based(candidates) -> bool:
    """Judgement-based when more than one cause fires, or none does.

    The skill's ~20%: multiple simultaneous root causes, and novel breaks
    with no existing playbook.
    """
    positives = [c for c in candidates if c.positive]
    return len(positives) != 1


def _deterministic_verdict(check_id: str, reason: str) -> dict:
    """Apply the rule and state the rule applied (R7)."""
    category = CHECK_TO_CATEGORY.get(check_id, "H")
    return {
        "root_cause": reason,
        "established": True,
        "category_code": category,
        "category_name": CATEGORY_NAMES[category],
        "deterministic": True,
        "rule_applied": check_id,
        "requires_sme_review": False,
        "verdict": None,  # the controller still decides; §10 is their call
        "competing_hypotheses": [],
        "unset_parameters": [],
    }


async def reason(state: InvestigationState, *, session) -> dict:
    findings: dict[str, dict] = {}
    gaps = list(state.get("evidence_gaps", []))
    reasoning_failed: str | None = None

    for brk in state["breaks"]:
        bid = brk["break_id"]
        candidates = state["candidates"][bid]
        positives = [c for c in candidates if c.positive]

        if not _is_judgement_based(candidates):
            findings[bid] = _deterministic_verdict(
                positives[0].check_id, state["reasons"].get(bid, "")
            )
            continue

        # Judgement-based: the skill decides, not a rule.
        record = {
            "break_id": bid,
            "book": brk["book_ref"],
            "line_code": brk.get("line_code"),
            "cob_date": str(state["business_date"]),
            "fo_value": brk.get("fo_value"),
            "bo_value": brk.get("bo_value"),
            "break_amount": state["deltas"].get(bid),
            "checks": [c.model_dump() for c in candidates],
            "prior_resolutions": state.get("priors", {}).get(bid, []),
            "lineage": state.get("lineage", {}).get(bid, []),
        }
        try:
            verdict = await reason_over_break(record)
        except ReasoningUnavailable as exc:
            reasoning_failed = str(exc)
            gaps.append(f"reasoning:{bid}")
            findings[bid] = {
                "root_cause": "Not established — reasoning unavailable",
                "established": False,
                "category_code": "H",
                "category_name": CATEGORY_NAMES["H"],
                "deterministic": False,
                "rule_applied": None,
                "requires_sme_review": True,
                "verdict": "ESCALATE",
                "competing_hypotheses": [],
                "unset_parameters": [],
            }
            continue

        findings[bid] = {
            "root_cause": verdict.root_cause.statement,
            "established": verdict.root_cause.established,
            "side": verdict.root_cause.side,
            "category_code": verdict.classification.category_code,
            "category_name": verdict.classification.category_name,
            "deterministic": verdict.classification.deterministic,
            "rule_applied": None,
            "requires_sme_review": verdict.requires_sme_review,
            "verdict": verdict.verdict,
            "verdict_reason": verdict.verdict_reason,
            "competing_hypotheses": verdict.competing_hypotheses,
            "unset_parameters": verdict.unset_parameters,
            "checks_performed": [c.model_dump() for c in verdict.checks_performed],
            "remediation": verdict.remediation.model_dump(),
            "end_state_validation": verdict.end_state_validation,
        }

    return {
        "findings": findings,
        "evidence_gaps": gaps,
        "reasoning_error": reasoning_failed,
    }
