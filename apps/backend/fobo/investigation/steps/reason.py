"""Reasoning node — determinism first, the reasoner for the residue.

1. Every break is offered to the deterministic classifier. What it settles
   never reaches a model.
2. What it cannot settle goes to ONE agent session for the whole rec run
   (fobo/investigation/agent_run.py), through whatever reasoner is
   configured: the session service, a direct call, or nothing. The agent
   answers per pattern, plus exceptions; a break it does not cover escalates.
3. Every verdict, from either path, passes the hard guards. No model output
   can override R2, R6 or the posting-failure rule.

The coverage figure it returns is the orchestrator's headline metric: the
share of the run that needed no model at all.
"""

from fobo.investigation.agent_run import (
    NOT_COVERED, UNGROUPED, map_verdicts, pattern_of, run_agent,
)
from fobo.knowledge_graph.ontology import OntologyRepository
from fobo.playbook.loader import loaded_version
from fobo.reasoning.determinism import classify, coverage
from fobo.reasoning.guards import guard_verdict
from fobo.reasoning.adapters.null import NO_REASONER_MESSAGE, NullReasoner
from fobo.reasoning.port import ReasoningUnavailable
from fobo.reasoning.registry import get_reasoner
from fobo.investigation.settings import settings
from fobo.investigation.state import InvestigationState


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


def _agent_finding(verdict, det, reasoner_name: str, harness_session_id, pattern_code) -> dict:
    return {
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
        "reasoner": reasoner_name,
        "unresolved_reason": det.unresolved_reason,
        "harness_session_id": harness_session_id,
        "pattern_code": pattern_code,
    }


def _failure_finding(det, reasoner_name: str) -> dict:
    return {
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
        "reasoner": reasoner_name,
        "unresolved_reason": det.unresolved_reason,
    }


def _resolve_reasoner(reasoner):
    """(reasoner, error). The null reasoner is reported as unavailable here,
    before any agent session row exists, so `reasoner: none` leaves no
    trace beyond today's escalations."""
    if reasoner is None:
        try:
            reasoner = get_reasoner()
        except ReasoningUnavailable as exc:
            return None, str(exc)
    if isinstance(reasoner, NullReasoner):
        return reasoner, NO_REASONER_MESSAGE
    return reasoner, None


async def _reason_unsettled(session, state, unsettled, determinations, reasoner):
    """Proposals for the unsettled breaks, the gaps they add, and the error."""
    active, error = _resolve_reasoner(reasoner)
    name = getattr(active, "name", "none")
    mapped = {bid: (None, None) for bid in unsettled}
    harness_session_id = None
    if error is None:
        outcome = await run_agent(session, state, unsettled, reasoner=active)
        harness_session_id, error = outcome.harness_session_id, outcome.error
        if outcome.rec_verdict is not None:
            mapped = map_verdicts(outcome.rec_verdict, unsettled)

    proposals, gaps, uncovered = {}, [], []
    for bid, (verdict, note) in mapped.items():
        det = determinations[bid]
        if verdict is None:
            gaps.append(f"reasoning:{bid}")
            if note is not None:
                uncovered.append(bid)
            proposals[bid] = (_failure_finding(det, name), None, None, False)
            continue
        finding = _agent_finding(
            verdict, det, name, harness_session_id, unsettled[bid]["pattern_code"]
        )
        proposals[bid] = (
            finding, verdict.root_cause.side, verdict.verdict,
            verdict.root_cause.established,
        )
    if error is None and uncovered:
        error = f"{NOT_COVERED}: {', '.join(uncovered)}"
    return proposals, gaps, error


async def reason(state: InvestigationState, *, session, reasoner=None) -> dict:
    as_of = state["business_date"]
    # Parameters a verdict may depend on; P1 checks each has a value.
    policy_params = settings().reason.verdict_policy_params
    ontology = OntologyRepository(session) if session is not None else None
    unset = (
        await ontology.unset_policies(policy_params, as_of)
        if ontology is not None
        else list(policy_params)
    )

    # Recorded on every finding: an audit must know which rules produced it.
    playbook_version = await loaded_version(session) if session is not None else None

    determinations = {}
    # break_id -> (finding, side, proposed verdict, root cause established)
    proposals: dict[str, tuple] = {}
    unsettled: dict[str, dict] = {}
    gaps = list(state.get("evidence_gaps", []))
    reasoning_error: str | None = None
    patterns = pattern_of(state.get("pattern_groups"))
    books = state.get("book_resolutions", {})

    for brk in state["breaks"]:
        bid = brk["break_id"]
        det = classify(
            brk,
            state["candidates"][bid],
            delta=state["deltas"].get(bid),
            priors=state.get("priors", {}).get(bid, []),
        )
        determinations[bid] = det
        if not det.resolved:
            unsettled[bid] = {
                **_evidence(state, brk),
                "pattern_code": patterns.get(bid, (UNGROUPED, None))[0],
                "book_id": books.get(bid),
            }
            continue
        finding = det.as_finding(state.get("reasons", {}).get(bid))
        side = det.side
        proposed = det.verdict
        # A rule that fixes category and side takes its verdict from the
        # playbook's default_verdicts table — read from the graph, as of
        # the business date, not from code.
        if proposed is None and ontology is not None and side in ("FO", "BO"):
            proposed = await ontology.default_verdict(det.category_code, side, as_of)
        finding["side"] = side
        proposals[bid] = (finding, side, proposed, True)

    if unsettled:
        agent_proposals, agent_gaps, reasoning_error = await _reason_unsettled(
            session, state, unsettled, determinations, reasoner
        )
        proposals.update(agent_proposals)
        gaps.extend(agent_gaps)

    findings: dict[str, dict] = {}
    for brk in state["breaks"]:
        bid = brk["break_id"]
        finding, side, proposed, established = proposals[bid]
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
        finding["playbook_version"] = playbook_version
        findings[bid] = finding

    return {
        "findings": findings,
        "evidence_gaps": gaps,
        "reasoning_error": reasoning_error,
        "determinism": coverage(determinations),
    }
