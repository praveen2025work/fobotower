"""Reasoning node — determinism first, the reasoner for the residue.

1. Every break is offered to the deterministic classifier. What it settles
   never reaches a model.
2. What it cannot settle goes through the reasoning port — whatever is
   configured: the session service, a direct call, or nothing.
3. Every verdict, from either path, passes the hard guards. No model output
   can override R2, R6 or the posting-failure rule.

The coverage figure it returns is the orchestrator's headline metric: the
share of the run that needed no model at all.
"""

from app.graph.ontology import OntologyRepository
from app.reasoning.determinism import classify, coverage
from app.reasoning.guards import guard_verdict
from app.reasoning.port import ReasoningUnavailable
from app.reasoning.registry import get_reasoner
from app.workflow.state import InvestigationState

# Parameters a verdict may depend on. P1 checks whether each has a value.
VERDICT_POLICY_PARAMS = ["materiality_threshold", "posting_policy_reference"]


def _evidence(state: InvestigationState, brk: dict) -> dict:
    bid = brk["break_id"]
    return {
        "break_id": bid,
        "book": brk["book_ref"],
        "line_code": brk.get("line_code"),
        "cob_date": str(state["business_date"]),
        "fo_value": brk.get("fo_value"),
        "bo_value": brk.get("bo_value"),
        "break_amount": state["deltas"].get(bid),
        "checks": [c.model_dump() for c in state["candidates"][bid]],
        "prior_resolutions": state.get("priors", {}).get(bid, []),
        "lineage": state.get("lineage", {}).get(bid, []),
    }


async def reason(state: InvestigationState, *, session, reasoner=None) -> dict:
    as_of = state["business_date"]
    ontology = OntologyRepository(session) if session is not None else None
    unset = (
        await ontology.unset_policies(VERDICT_POLICY_PARAMS, as_of)
        if ontology is not None
        else list(VERDICT_POLICY_PARAMS)
    )

    determinations = {}
    findings: dict[str, dict] = {}
    gaps = list(state.get("evidence_gaps", []))
    reasoning_error: str | None = None
    active = reasoner

    for brk in state["breaks"]:
        bid = brk["break_id"]
        det = classify(
            brk,
            state["candidates"][bid],
            delta=state["deltas"].get(bid),
            priors=state.get("priors", {}).get(bid, []),
        )
        determinations[bid] = det

        if det.resolved:
            finding = det.as_finding(state.get("reasons", {}).get(bid))
            side = "BO" if det.verdict == "POST" else None
            proposed = det.verdict
            established = True
        else:
            if active is None:
                try:
                    active = get_reasoner()
                except ReasoningUnavailable as exc:
                    active = None
                    reasoning_error = str(exc)
            try:
                if active is None:
                    raise ReasoningUnavailable(reasoning_error or "no reasoner")
                verdict = await active.investigate(_evidence(state, brk))
                finding = {
                    "root_cause": verdict.root_cause.statement,
                    "established": verdict.root_cause.established,
                    "category_code": verdict.classification.category_code,
                    "category_name": verdict.classification.category_name,
                    "deterministic": False,
                    "pattern": None,
                    "rule_applied": None,
                    "requires_sme_review": True,
                    "competing_hypotheses": verdict.competing_hypotheses,
                    "unset_parameters": verdict.unset_parameters,
                    "reasoner": active.name,
                    "unresolved_reason": det.unresolved_reason,
                }
                side = verdict.root_cause.side
                proposed = verdict.verdict
                established = verdict.root_cause.established
            except ReasoningUnavailable as exc:
                reasoning_error = str(exc)
                gaps.append(f"reasoning:{bid}")
                finding = {
                    "root_cause": "Not established — " + (det.unresolved_reason or ""),
                    "established": False,
                    "category_code": "H",
                    "category_name": "Novel break",
                    "deterministic": False,
                    "pattern": None,
                    "rule_applied": None,
                    "requires_sme_review": True,
                    "competing_hypotheses": [],
                    "unset_parameters": [],
                    "reasoner": getattr(active, "name", "none"),
                    "unresolved_reason": det.unresolved_reason,
                }
                side, proposed, established = None, None, False

        guarded = guard_verdict(
            proposed,
            root_cause_established=established,
            side=side,
            unset_parameters=unset,
            motif_rejected=bool(brk.get("motif_rejected")),
        )
        finding["verdict"] = guarded.verdict
        finding["verdict_proposed"] = guarded.proposed
        finding["verdict_overridden"] = guarded.overridden
        finding["guard_reasons"] = list(guarded.reasons)
        finding["requires_controller_confirmation"] = (
            guarded.requires_controller_confirmation
        )
        finding["conditional_on"] = list(guarded.conditional_on)
        findings[bid] = finding

    return {
        "findings": findings,
        "evidence_gaps": gaps,
        "reasoning_error": reasoning_error,
        "determinism": coverage(determinations),
    }
