"""Controller-facing wording for each cause.

The descriptions in checks.py explain the check. These explain the break to
the person signing it off, and they are what the adjustment rows render.
Wording is taken from the mock.
"""

CHECK_REASONS: dict[str, str] = {
    "C1": "Nostro statement received after 23:30 cutoff",
    "C2": "Reference does not resolve in static data",
    "C3": "FO and BO priced from different curve datasets",
    "C4": "Fee or funding component present on one side only",
    "C5": "Pending desk confirmation since the 11:00 run",
    "C6": "Two entries with identical settlement reference",
}

PATTERN_REASONS: dict[str, str] = {
    "P-204": CHECK_REASONS["C1"],
    "CPTY-REF": CHECK_REASONS["C2"],
    "VAL-DATASET": CHECK_REASONS["C3"],
    "COMP-ONESIDE": CHECK_REASONS["C4"],
    "LATE-BOOK": CHECK_REASONS["C5"],
    "DUP-SETTLE": CHECK_REASONS["C6"],
}


def reason_for(check_id: str) -> str:
    """Raises KeyError on an unknown check rather than returning a blank: a
    silent empty string renders as a missing cell nobody notices."""
    return CHECK_REASONS[check_id]
