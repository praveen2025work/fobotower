"""The Helix scenario: seven recs, and where each one stands today.

Pure data. history.py writes it into the reconciliation, run, node and
break_event tables; nothing reads these constants at request time.

Times are wall-clock IST, stored as they are shown, the convention the rest
of the fixtures use.
"""

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class RecDef:
    rec_id: str
    name: str
    group: str  # CATS-MOTIF | RF-CASHCOLL
    l4: str
    region: str
    master_book: str  # book prefix: PRIME-MB -> PRIME-MB-01, PRIME-MB-02, ...
    scheduled: time  # the expected window; the Ready event is what starts a run
    books_total: int
    ccy: str = "USD"


RECS = [
    RecDef("R-1042", "CATS vs MOTIF — Rates", "CATS-MOTIF", "Rates", "APAC", "RATES-MB", time(11, 0), 34),
    RecDef("R-1055", "CATS vs MOTIF — Prime", "CATS-MOTIF", "Prime", "APAC", "PRIME-MB", time(11, 0), 14),
    RecDef("R-2031", "CATS vs MOTIF — FI Credit", "CATS-MOTIF", "FI Credit", "EMEA", "FICR-MB", time(15, 0), 28),
    RecDef("R-2048", "Rec Factory — Collateral", "RF-CASHCOLL", "Collateral", "EMEA", "COLL-MB", time(15, 0), 9),
    RecDef("R-3019", "CATS vs MOTIF — Equity Derivatives", "CATS-MOTIF", "Equity Derivatives", "AMER", "EQD-MB", time(17, 0), 41),
    RecDef("R-3026", "Rec Factory — Cash", "RF-CASHCOLL", "Cash", "AMER", "CASH-MB", time(17, 0), 19),
    RecDef("R-1061", "CATS vs MOTIF — FX", "CATS-MOTIF", "FX", "APAC", "FX-MB", time(19, 0), 15),
]

REC_BY_ID = {r.rec_id: r for r in RECS}


def book_stats(total: int, **counts: int) -> dict:
    """Book states as One Fin UX reports them. Unlisted states are zero and
    whatever is not otherwise accounted for has not opened."""
    stats = {k: counts.get(k, 0) for k in ("autoPost", "cleared", "awaiting", "analysing", "blocked")}
    stats["notOpen"] = total - sum(stats.values())
    return {"total": total, **stats}


@dataclass(frozen=True)
class TodayRun:
    status: str  # cleared | awaiting | in_progress | blocked | scheduled
    mb_available: int
    mb_reported_at: time
    book_stats: dict
    ready_event_id: str | None = None
    ready_at: time | None = None
    completed: time | None = None
    books_unlocked: int = 0


TODAY = {
    "R-1042": TodayRun("cleared", 34, time(11, 38), book_stats(34, autoPost=31, cleared=3),
                       "EVT-RDY-80412", time(11, 40), time(11, 47), books_unlocked=34),
    "R-1055": TodayRun("awaiting", 14, time(11, 42), book_stats(14, autoPost=3, awaiting=9),
                       "EVT-RDY-80437", time(11, 44), time(11, 52)),
    "R-2031": TodayRun("in_progress", 28, time(15, 0), book_stats(28, autoPost=9, analysing=11),
                       "EVT-RDY-81190", time(15, 2)),
    "R-2048": TodayRun("blocked", 9, time(15, 1), book_stats(9, autoPost=2, blocked=1),
                       "EVT-RDY-81204", time(15, 3), time(15, 11)),
    "R-3019": TodayRun("scheduled", 12, time(17, 36), book_stats(41)),
    "R-3026": TodayRun("cleared", 19, time(17, 13), book_stats(19, autoPost=16, cleared=3),
                       "EVT-RDY-81977", time(17, 15), time(17, 22), books_unlocked=19),
    "R-1061": TodayRun("scheduled", 6, time(17, 31), book_stats(15)),
}


@dataclass(frozen=True)
class OpenBreak:
    """A break an investigation will analyse today."""

    break_id: str
    book_no: int
    cause: str  # the cause check whose snapshot fields make it fire
    delta: float
    first_seen_days_ago: int = 0


# R-1055's population lives in data/breaks_small.json, the file the graph
# tests share. These are the other recs with a live investigation.
OPEN_REC_BREAKS = {
    # Mid-flight: some settle by rule, the rest need judgement.
    "R-2031": [
        OpenBreak("F-1", 1, "C1", 4210.0), OpenBreak("F-2", 2, "C1", 1890.0),
        OpenBreak("F-3", 3, "C1", 2650.0), OpenBreak("F-4", 4, "C3", 11400.0),
        OpenBreak("F-5", 5, "C3", 7320.0), OpenBreak("F-6", 6, "C4", 980.0),
        OpenBreak("F-7", 7, "C4", 3115.0), OpenBreak("F-8", 8, "C4", 1745.0),
    ],
    # A custodian statement that never arrived: the BO dataset is a day
    # stale, so nothing can be drafted. Carried for four sessions.
    "R-2048": [OpenBreak("COLL-7781", 3, "C3", 214500.0, first_seen_days_ago=4)],
}


@dataclass(frozen=True)
class ResolvedBreak:
    """A break resolved earlier today on a rec that has since cleared.

    outcome "posted" went straight through FAS with no human decision;
    "approved" was signed off by a controller first.
    """

    break_id: str
    book_no: int
    delta: float
    pattern_code: str
    label: str
    reason: str
    outcome: str


RESOLVED_TODAY = {
    "R-1042": [
        ResolvedBreak("A-1", 4, 12400.0, "P-118", "FX timing lag",
                      "Nostro statement received after 23:30 cutoff", "posted"),
        ResolvedBreak("A-2", 11, 3150.0, "P-118", "FX timing lag",
                      "Nostro statement received after 23:30 cutoff", "posted"),
        ResolvedBreak("A-3", 2, 47900.0, "UNCLASSIFIED", "Unclassified",
                      "Unusual notional, flagged for review", "approved"),
    ],
    "R-3026": [
        ResolvedBreak("C-1", 2, 5600.0, "P-118", "Settlement timing",
                      "Matched pattern P-118", "posted"),
        ResolvedBreak("C-2", 5, 1980.0, "P-118", "Settlement timing",
                      "Matched pattern P-118", "posted"),
        ResolvedBreak("C-3", 8, 22300.0, "UNCLASSIFIED", "Unclassified",
                      "One-off booking error, confirmed with desk", "approved"),
    ],
}

# R-1055 breaks still waiting on the desk from earlier sessions: break id ->
# how many business days ago it first appeared.
PRIME_CARRIED = {"B-12": 3, "B-13": 3, "B-14": 2}

# A drafted figure on this break cannot be traced back to MB Rec source data.
PRIME_UNGROUNDED = {"B-9"}

# Completed P-204 resolutions per day for R-1055, approved/total. The last day
# is today's run, resolved earlier in the day.
P204_HISTORY_DAYS = [(4, 5), (3, 4), (2, 3), (2, 2), (8, 9), (8, 8), (7, 7)]

PATTERN_MIX = ["P-204", "CPTY-REF", "LATE-BOOK", "DUP-SETTLE"]

ENTITY = "LE-APAC-01"


def master_book_ref(rec: RecDef, book_no: int) -> str:
    return f"{rec.master_book}-{book_no:02d}"

