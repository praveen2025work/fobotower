from app.contracts.models import AnalysisDraft, CandidateCause, PatternGroup
from app.workflow.nodes.draft import draft
from app.workflow.nodes.rank import rank
from app.workflow.nodes.validate import validate


def _pos(check_id):
    return CandidateCause(
        check_id=check_id,
        positive=True,
        description="d",
        supporting_ids=["b-01"],
        estimated_value=2340.0,
    )


def _neg(check_id):
    return CandidateCause(check_id=check_id, positive=False, description="d")


BASE = {
    "investigation_session_id": "sess-1",
    "breaks": [
        {"break_id": "b-01", "book_ref": "APAC-CASH-01", "line_code": "CASH"}
    ],
    "candidates": {
        "b-01": [_pos("C1")] + [_neg(c) for c in ("C2", "C3", "C4", "C5", "C6")]
    },
    "deltas": {"b-01": 2340.0},
    "pattern_groups": [
        PatternGroup(
            group_id="g1",
            pattern_code="P-204",
            label="FX timing lag",
            mode="auto",
            break_ids=["b-01"],
            historical_approval_rate=0.88,
        )
    ],
    "evidence_gaps": [],
    "hypothesis_attempts": 0,
}


async def test_single_candidate_takes_the_fast_path_and_skips_the_model():
    out = await rank(BASE, session=None)
    assert out["ranking"]["b-01"][0]["share_bps"] == 10000
    assert out["ranking"]["b-01"][0]["candidate_id"] == "C1"
    assert out["model_skipped"] is True


async def test_the_fast_path_carries_evidence_references():
    out = await rank(BASE, session=None)
    assert out["ranking"]["b-01"][0]["evidence_ids"] == ["b-01"]


async def test_multiple_candidates_are_flagged_for_the_model():
    st = BASE | {
        "candidates": {
            "b-01": [_pos("C1"), _pos("C5")]
            + [_neg(c) for c in ("C2", "C3", "C4", "C6")]
        }
    }
    out = await rank(st, session=None)
    assert out["model_skipped"] is False
    assert out["ranking"]["b-01"] == "needs_model"


async def test_draft_produces_the_four_part_narrative():
    st = BASE | await rank(BASE, session=None)
    out = await draft(st, session=None)
    d = out["draft"]
    assert isinstance(d, AnalysisDraft)
    assert "1 break across 1 book" in d.what_happened
    assert "P-204" in d.why
    assert d.confidence_basis


async def test_draft_pluralises_correctly():
    st = BASE | {
        "breaks": [
            {"break_id": "b-01", "book_ref": "APAC-CASH-01"},
            {"break_id": "b-02", "book_ref": "APAC-CASH-02"},
        ],
        "candidates": {
            "b-01": BASE["candidates"]["b-01"],
            "b-02": BASE["candidates"]["b-01"],
        },
        "deltas": {"b-01": 2340.0, "b-02": 1880.0},
        "pattern_groups": [
            PatternGroup(
                group_id="g1",
                pattern_code="P-204",
                label="FX timing lag",
                mode="auto",
                break_ids=["b-01", "b-02"],
                historical_approval_rate=0.88,
            )
        ],
    }
    st |= await rank(st, session=None)
    d = (await draft(st, session=None))["draft"]
    assert "2 breaks across 2 books" in d.what_happened
    assert "1 distinct root cause." in d.what_happened


async def test_validate_passes_a_grounded_draft():
    st = BASE | await rank(BASE, session=None)
    st |= await draft(st, session=None)
    out = await validate(st, session=None)
    assert out["validation_errors"] == []


async def test_validate_rejects_an_ungrounded_figure():
    """Every figure must trace to a delta. 9999.00 does not."""
    st = BASE | await rank(BASE, session=None)
    st |= await draft(st, session=None)
    st["draft"] = st["draft"].model_copy(
        update={"why": "The difference of $9,999.00 arose from a timing lag."}
    )
    out = await validate(st, session=None)
    assert any("ungrounded" in e for e in out["validation_errors"])


async def test_validate_reports_evidence_gaps():
    st = BASE | {"evidence_gaps": ["priors:b-01"]}
    st |= await rank(st, session=None)
    st |= await draft(st, session=None)
    out = await validate(st, session=None)
    assert any("evidence_gap" in e for e in out["validation_errors"])


async def test_validate_flags_retry_exhaustion():
    st = BASE | {"hypothesis_attempts": 3}
    st |= await rank(st, session=None)
    st |= await draft(st, session=None)
    out = await validate(st, session=None)
    assert "RETRY_EXHAUSTED" in out["validation_errors"]


async def test_validate_rejects_a_missing_draft():
    out = await validate(BASE | {"draft": None}, session=None)
    assert out["validation_errors"] == ["no draft produced"]
