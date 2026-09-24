from app.recon.checks import run_cause_checks

BASE = {
    "break_id": "B-1",
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


def test_returns_all_six_checks_including_negatives():
    out = run_cause_checks(BASE)
    assert len(out) == 6
    assert [c.check_id for c in out] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    assert all(c.positive is False for c in out)


def test_c1_fires_when_booking_is_after_the_cutoff():
    snap = BASE | {"fo_booking_ts": "2026-08-04T00:15:00Z"}
    c1 = next(c for c in run_cause_checks(snap) if c.check_id == "C1")
    assert c1.positive is True


def test_c2_fires_when_the_mapping_is_missing():
    c2 = next(
        c for c in run_cause_checks(BASE | {"mapping_present": False})
        if c.check_id == "C2"
    )
    assert c2.positive is True


def test_c3_fires_on_different_datasets():
    c3 = next(
        c for c in run_cause_checks(BASE | {"bo_dataset_id": "EOD-2026-08-02"})
        if c.check_id == "C3"
    )
    assert c3.positive is True


def test_c4_fires_when_a_component_is_one_sided():
    c4 = next(
        c for c in run_cause_checks(BASE | {"fo_components": ["principal", "fee"]})
        if c.check_id == "C4"
    )
    assert c4.positive is True


def test_c5_fires_on_version_mismatch():
    c5 = next(c for c in run_cause_checks(BASE | {"fo_version": 2}) if c.check_id == "C5")
    assert c5.positive is True


def test_c6_fires_on_a_one_sided_adjustment():
    c6 = next(
        c for c in run_cause_checks(BASE | {"bo_adjustments": ["manual-1"]})
        if c.check_id == "C6"
    )
    assert c6.positive is True


def test_is_deterministic():
    """Same snapshot in, byte-identical output out."""
    a = [c.model_dump_json() for c in run_cause_checks(BASE)]
    b = [c.model_dump_json() for c in run_cause_checks(BASE)]
    assert a == b


def test_a_positive_check_carries_its_supporting_evidence():
    """A claim with no evidence reference cannot be cited in a draft."""
    snap = BASE | {"fo_booking_ts": "2026-08-04T00:15:00Z"}
    c1 = next(c for c in run_cause_checks(snap) if c.check_id == "C1")
    assert c1.supporting_ids == ["B-1"]


def test_a_negative_check_carries_no_evidence():
    c1 = next(c for c in run_cause_checks(BASE) if c.check_id == "C1")
    assert c1.supporting_ids == []
