from app.reasoning.guards import (
    CORRECT_AND_REPOST,
    DO_NOT_POST,
    ESCALATE,
    POST,
    guard_verdict,
)


def test_an_unevidenced_post_is_escalated():
    """R6: unknown root cause is an escalation outcome, not a posting one."""
    g = guard_verdict(POST, root_cause_established=False, side="BO")
    assert g.verdict == ESCALATE
    assert g.overridden is True
    assert any("R6" in r for r in g.reasons)


def test_a_front_office_cause_never_posts():
    """R2 and Appendix A: posting masks the CATS failure."""
    g = guard_verdict(POST, root_cause_established=True, side="FO")
    assert g.verdict == DO_NOT_POST
    assert any("R2" in r for r in g.reasons)


def test_a_back_office_cause_may_post():
    g = guard_verdict(POST, root_cause_established=True, side="BO")
    assert g.verdict == POST
    assert g.overridden is False
    assert g.reasons == ()


def test_a_motif_rejection_is_always_correct_and_repost():
    """§8: a mechanical failure, not a 'should we post?' question — even if
    the reasoner proposed something else."""
    g = guard_verdict(DO_NOT_POST, root_cause_established=True, side="BO",
                      motif_rejected=True)
    assert g.verdict == CORRECT_AND_REPOST
    assert g.overridden is True


def test_no_proposed_verdict_escalates_rather_than_defaulting_to_post():
    g = guard_verdict(None, root_cause_established=True, side="BO")
    assert g.verdict == ESCALATE


def test_a_post_resting_on_an_unset_threshold_needs_confirmation():
    """P1: never invent a threshold — state the dependency instead."""
    g = guard_verdict(POST, root_cause_established=True, side="BO",
                      unset_parameters=["materiality_threshold"])
    assert g.verdict == POST
    assert g.requires_controller_confirmation is True
    assert g.conditional_on == ("materiality_threshold",)


def test_unset_parameters_do_not_matter_when_not_posting():
    g = guard_verdict(DO_NOT_POST, root_cause_established=True, side="FO",
                      unset_parameters=["materiality_threshold"])
    assert g.requires_controller_confirmation is False
    assert g.conditional_on == ()


def test_the_reasoner_cannot_talk_its_way_past_r2():
    """The point of a guard: the model's output is corrected by construction,
    not by prompt compliance."""
    for proposed in (POST, POST, POST):
        g = guard_verdict(proposed, root_cause_established=True, side="FO")
        assert g.verdict != POST
