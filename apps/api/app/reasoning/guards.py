"""Verdict guards — graph code, not model judgement.

These are the rules the skill states as non-negotiable. Encoding them here
means no model output can override them: a reasoner that returns POST for an
FO-side cause is corrected by construction, not by prompt compliance.

Each guard reports why it fired, so an overridden verdict is auditable.
"""

from dataclasses import dataclass, field

POST = "POST"
DO_NOT_POST = "DO_NOT_POST"
ESCALATE = "ESCALATE"
CORRECT_AND_REPOST = "CORRECT_AND_REPOST"

# (rule id, the rule in plain words), in the order guard_verdict() applies
# them below. Kept next to the code it describes so the Workflow tab cannot
# show an order the function does not actually use.
GUARD_RULES: tuple[tuple[str, str], ...] = (
    ("§8", "A rejected legitimate posting is corrected and re-posted, not judged"),
    ("R6", "No evidenced root cause: escalate, do not post"),
    ("R2", "A Front Office cause never posts a FOBO adjustment: do not post"),
    ("none", "No verdict proposed at all is an escalation, never an implicit POST"),
    ("P1", "A POST that depends on an unset policy threshold requires controller confirmation"),
)


@dataclass(frozen=True)
class GuardedVerdict:
    verdict: str
    proposed: str | None
    overridden: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    conditional_on: tuple[str, ...] = field(default_factory=tuple)
    requires_controller_confirmation: bool = False


def guard_verdict(
    proposed: str | None,
    *,
    root_cause_established: bool,
    side: str | None,
    unset_parameters: list[str] | None = None,
    motif_rejected: bool = False,
) -> GuardedVerdict:
    """Apply the skill's hard rules to a proposed verdict.

    Order matters: a MOTIF rejection is mechanical and settles first; then
    evidence (R6); then side (R2); then unset policy (P1).
    """
    unset = tuple(unset_parameters or [])
    reasons: list[str] = []

    # §8: a rejected legitimate posting is not a judgement call.
    if motif_rejected:
        return GuardedVerdict(
            verdict=CORRECT_AND_REPOST,
            proposed=proposed,
            overridden=proposed != CORRECT_AND_REPOST,
            reasons=("§8 posting failure — correct and re-post",),
        )

    verdict = proposed

    # R6: no evidenced root cause, no posting.
    if not root_cause_established:
        if verdict != ESCALATE:
            reasons.append("R6: root cause not evidenced — escalate, do not post")
        verdict = ESCALATE

    # R2: a Front Office cause never posts a FOBO adjustment. Posting would
    # mask the CATS failure and need a later reversal (Appendix A).
    elif side == "FO" and verdict == POST:
        reasons.append("R2: cause originates in Front Office — do not post")
        verdict = DO_NOT_POST

    # No verdict proposed at all is an escalation, never an implicit POST.
    if verdict is None:
        reasons.append("no verdict proposed — escalate")
        verdict = ESCALATE

    # P1: a POST that depends on an unset threshold is conditional.
    needs_confirmation = bool(unset) and verdict == POST
    if needs_confirmation:
        reasons.append(
            "P1: depends on unset parameters — requires controller confirmation"
        )

    return GuardedVerdict(
        verdict=verdict,
        proposed=proposed,
        overridden=verdict != proposed,
        reasons=tuple(reasons),
        conditional_on=unset if needs_confirmation else (),
        requires_controller_confirmation=needs_confirmation,
    )
