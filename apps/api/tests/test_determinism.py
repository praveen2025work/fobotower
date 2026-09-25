"""classify() itself, pattern by pattern — the source of truth the Workflow
tab's "How it decides" panel claims to describe. Each test builds the
minimal break + candidates that triggers exactly one named pattern (or none)
and asserts what classify() actually returns: `pattern` and `verdict`,
including `None` for missing_side, and the exact cases that fall through to
the reasoner (a lone C3/C4, multiple simultaneous causes). These are the
facts final-fix-brief.md item 1 requires the server (and PATTERN_ORDER) to
state correctly; this file is what keeps them honest.
"""

from app.contracts.models import CandidateCause
from app.reasoning import determinism
from app.reasoning.determinism import (
    PATTERN_MISSING_PRICE, PATTERN_MISSING_SIDE, PATTERN_POSTING_FAILURE,
    PATTERN_REAPPLICATION, PATTERN_SIDE_DOUBLE, PATTERN_SINGLE_CAUSE,
    UNRESOLVED_WHEN, classify,
)

ALL_CHECKS = ("C1", "C2", "C3", "C4", "C5", "C6")


def _pos(check_id):
    return CandidateCause(check_id=check_id, positive=True, description="d", supporting_ids=["B-1"])


def _neg(check_id):
    return CandidateCause(check_id=check_id, positive=False, description="d")


def _candidates(*positive_checks):
    positives = set(positive_checks)
    return [_pos(c) if c in positives else _neg(c) for c in ALL_CHECKS]


BASE_BREAK = {"break_id": "B-1", "fo_value": 100.0, "bo_value": 90.0}


# --- posting_failure -------------------------------------------------------

def test_posting_failure_is_correct_and_repost():
    brk = BASE_BREAK | {"motif_rejected": True, "motif_rejection_reason": "duplicate"}
    det = classify(brk, _candidates(), delta=10.0)
    assert det.resolved is True
    assert det.pattern == PATTERN_POSTING_FAILURE
    assert det.verdict == "CORRECT_AND_REPOST"


# --- missing_side ------------------------------------------------------------

def test_missing_side_has_no_verdict():
    brk = {"break_id": "B-1", "fo_value": 100.0, "bo_value": None}
    det = classify(brk, _candidates(), delta=None)
    assert det.resolved is True
    assert det.pattern == PATTERN_MISSING_SIDE
    assert det.verdict is None


# --- missing_price -----------------------------------------------------------

def test_missing_price_is_do_not_post_only_when_corporate_action_confirmed_is_explicitly_false():
    brk = BASE_BREAK | {"price": 0, "corporate_action_confirmed": False}
    det = classify(brk, _candidates(), delta=10.0)
    assert det.resolved is True
    assert det.pattern == PATTERN_MISSING_PRICE
    assert det.verdict == "DO_NOT_POST"


def test_missing_price_does_not_match_when_the_flag_is_merely_absent():
    """§8 brief: an absent corporate_action_confirmed flag is not the same
    as it being False — a zero price is ambiguous, not deterministic, until
    the record says so explicitly."""
    brk = BASE_BREAK | {"price": 0}
    det = classify(brk, _candidates(), delta=None)
    assert det.resolved is False
    assert det.pattern is None


# --- side_double ---------------------------------------------------------------

def test_side_double_is_do_not_post():
    brk = BASE_BREAK | {"duplicate_side_count": 2}
    det = classify(brk, _candidates(), delta=10.0)
    assert det.resolved is True
    assert det.pattern == PATTERN_SIDE_DOUBLE
    assert det.verdict == "DO_NOT_POST"


# --- reapplication ---------------------------------------------------------------

def test_reapplication_is_post():
    priors = [{"break_id": "B-0", "outcome": "approved", "delta": 10.0}]
    det = classify(BASE_BREAK, _candidates(), delta=10.0, priors=priors)
    assert det.resolved is True
    assert det.pattern == PATTERN_REAPPLICATION
    assert det.verdict == "POST"


# --- single_cause: verdict comes from the playbook, not classify -----------------

def test_single_cause_with_a_bo_side_check_has_no_verdict_of_its_own():
    """C1 names BO (see config/playbook fixture in graph.json / the real
    playbook). classify() never assigns single_cause's verdict — the reason
    node looks it up from the playbook's default_verdicts by category+side."""
    det = classify(BASE_BREAK, _candidates("C1"), delta=10.0)
    assert det.resolved is True
    assert det.pattern == PATTERN_SINGLE_CAUSE
    assert det.side == "BO"
    assert det.verdict is None


def test_single_cause_with_an_fo_side_check():
    det = classify(BASE_BREAK, _candidates("C5"), delta=10.0)
    assert det.resolved is True
    assert det.pattern == PATTERN_SINGLE_CAUSE
    assert det.side == "FO"


# --- unresolved: goes to the reasoner ---------------------------------------------

def test_a_lone_c3_is_unresolved_not_single_cause():
    """C3's side is UNKNOWN — R2 forbids assuming a side, so a lone C3 is
    judgement, not a codified rule. This is the exact bug final-fix-brief.md
    item 1 flags: the old Step 2 wording implied C3 settles a verdict."""
    det = classify(BASE_BREAK, _candidates("C3"), delta=10.0)
    assert det.resolved is False
    assert det.pattern is None


def test_a_lone_c4_is_unresolved_not_single_cause():
    det = classify(BASE_BREAK, _candidates("C4"), delta=10.0)
    assert det.resolved is False
    assert det.pattern is None


def test_multiple_simultaneous_causes_are_unresolved():
    det = classify(BASE_BREAK, _candidates("C1", "C2"), delta=10.0)
    assert det.resolved is False
    assert "C1" in det.unresolved_reason
    assert "C2" in det.unresolved_reason


def test_no_pattern_and_no_cause_is_unresolved():
    det = classify(BASE_BREAK, _candidates(), delta=None)
    assert det.resolved is False
    assert det.pattern is None


# --- PATTERN_ORDER / UNRESOLVED_WHEN: the data the Workflow tab renders ----------

def test_pattern_order_covers_exactly_the_pattern_constants_with_a_verdict_each():
    constants = {
        v for k, v in vars(determinism).items()
        if k.startswith("PATTERN_") and isinstance(v, str)
    }
    assert {code for code, _meaning, _verdict in determinism.PATTERN_ORDER} == constants
    by_code = {code: verdict for code, _meaning, verdict in determinism.PATTERN_ORDER}
    assert by_code[PATTERN_POSTING_FAILURE] == "CORRECT_AND_REPOST"
    assert by_code[PATTERN_MISSING_SIDE] is None
    assert by_code[PATTERN_MISSING_PRICE] == "DO_NOT_POST"
    assert by_code[PATTERN_SIDE_DOUBLE] == "DO_NOT_POST"
    assert by_code[PATTERN_REAPPLICATION] == "POST"
    # single_cause's verdict is not a fixed literal — it comes from the
    # playbook's default_verdicts table, looked up by category+side.
    assert by_code[PATTERN_SINGLE_CAUSE] == "from playbook default_verdicts"


def test_unresolved_when_names_every_branch_that_reaches_the_reasoner():
    assert len(UNRESOLVED_WHEN) == 3
    joined = " ".join(UNRESOLVED_WHEN).lower()
    assert "no" in joined and "pattern" in joined
    assert "more than one" in joined or "multiple" in joined
    assert "fo" in joined and "bo" in joined
