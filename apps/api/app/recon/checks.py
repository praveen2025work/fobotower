"""The six cause checks.

The architecture doc places these in a Java Spring Boot service. This is a
Python stand-in behind the same HTTP contract, so the Java service can
replace it without touching callers.

Pure functions over dated snapshots: the same (book, cob_date,
snapshot_version) must produce identical output. That is asserted in tests.
"""

from datetime import datetime

from app.contracts.models import CandidateCause


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _result(check_id: str, positive: bool, snapshot: dict, when_positive: str,
            when_negative: str) -> CandidateCause:
    return CandidateCause(
        check_id=check_id,
        positive=positive,
        description=when_positive if positive else when_negative,
        supporting_ids=[snapshot["break_id"]] if positive else [],
    )


def _c1(s: dict) -> CandidateCause:
    late = _ts(s["fo_booking_ts"]) > _ts(s["bo_cutoff_ts"])
    return _result(
        "C1", late, s,
        "FO booking timestamp is after the BO ledger cut-off",
        "FO booking is within the BO cut-off",
    )


def _c2(s: dict) -> CandidateCause:
    missing = not s["mapping_present"]
    return _result(
        "C2", missing, s,
        "Static mapping missing or newly effective",
        "Static mapping present",
    )


def _c3(s: dict) -> CandidateCause:
    differs = s["fo_dataset_id"] != s["bo_dataset_id"]
    return _result(
        "C3", differs, s,
        "FO and BO reference different rate or curve datasets",
        "FO and BO reference the same dataset",
    )


def _c4(s: dict) -> CandidateCause:
    one_sided = set(s["fo_components"]) ^ set(s["bo_components"])
    return _result(
        "C4", bool(one_sided), s,
        f"Components present on one side only: {sorted(one_sided)}",
        "Components match on both sides",
    )


def _c5(s: dict) -> CandidateCause:
    mismatch = s["fo_version"] != s["bo_version"]
    return _result(
        "C5", mismatch, s,
        "Trade version mismatch across snapshots",
        "Trade versions match",
    )


def _c6(s: dict) -> CandidateCause:
    one_sided = set(s["fo_adjustments"]) ^ set(s["bo_adjustments"])
    return _result(
        "C6", bool(one_sided), s,
        "Adjustment applied on one side, absent on the other",
        "Adjustments match on both sides",
    )


CHECKS = (_c1, _c2, _c3, _c4, _c5, _c6)


def run_cause_checks(snapshot: dict) -> list[CandidateCause]:
    """All six run and all six results are returned, negatives included.

    Negatives matter: a ranking that cannot see what was ruled out cannot
    be reviewed.
    """
    return [check(snapshot) for check in CHECKS]
