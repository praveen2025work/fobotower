"""The drafted adjustments a rec shows, one per break.

Two sources, one shape:
  - a live investigation: the checkpointed pattern groups, reasons and
    findings, with each break's status read back from break_event
  - a rec that cleared earlier today: the resolved break_event rows

Either way the console gets the same fields, so it cannot tell, and does not
need to know, which path produced them.
"""

from datetime import date

from app.helix.detail import break_detail, legs
from app.helix.fmt import amount
from app.helix.rec_state import ADJ_STATUS


def _as_dict(group) -> dict:
    return group.model_dump() if hasattr(group, "model_dump") else dict(group)


def _float(value) -> float | None:
    return None if value is None else float(value)


def _row(*, break_id: str, book: str, pattern: str, label: str, auto: bool,
         reason: str, delta: float, status: str, grounded: bool, aged: int,
         detail: dict, legs_: dict, ccy: str) -> dict:
    return {
        "id": break_id,
        "type": "Auto" if auto else "Manual",
        "book": book,
        "amount": amount(delta, ccy),
        "delta": delta,
        "pattern": pattern,
        "patternLabel": label,
        "reason": reason,
        "status": status,
        "grounded": grounded,
        "agedSessions": aged,
        "detail": detail,
        "legs": legs_,
    }


def live_adjustments(values: dict, rows: dict, aged: dict[str, int],
                     escalation: dict[str, str], ccy: str, cob: date) -> list[dict]:
    """Every break the investigation grouped, in break order.

    A break with no group, or one the playbook escalated, has nothing to
    draft, so it is not an adjustment; the rec's analysis reports it instead.
    """
    group_of = {}
    for g in values.get("pattern_groups", []):
        g = _as_dict(g)
        for bid in g["break_ids"]:
            group_of[bid] = g
    ungrounded = set(values.get("ungrounded_breaks", []))
    findings = values.get("findings", {})
    reasons = values.get("reasons", {})
    deltas = values.get("deltas", {})

    out = []
    for brk in values.get("breaks", []):
        bid = brk["break_id"]
        g = group_of.get(bid)
        if g is None or g["pattern_code"] == "UNGROUPED" or bid not in deltas:
            continue
        row = rows.get(bid)
        finding = findings.get(bid)
        if (finding or {}).get("verdict") == "ESCALATE":
            continue
        fo, bo = _float(brk.get("fo_value")), _float(brk.get("bo_value"))
        grounded = bid not in ungrounded
        reason = reasons.get(bid, g["label"])
        category = (finding or {}).get("category_code")
        out.append(_row(
            break_id=bid,
            book=brk["book_ref"],
            pattern=g["pattern_code"],
            label=g["label"],
            auto=g["mode"] == "auto",
            reason=reason,
            delta=deltas[bid],
            status=ADJ_STATUS.get(row.outcome if row else None, "Pending"),
            grounded=grounded,
            aged=aged.get(bid, 0),
            detail=break_detail(
                break_id=bid, book=brk["book_ref"], label=g["label"], reason=reason,
                fo=fo, bo=bo, delta=deltas[bid], ccy=ccy, finding=finding,
                escalate_to=escalation.get(category), grounded=grounded,
            ),
            legs_=legs(bid, brk["book_ref"], fo, bo, ccy, cob),
            ccy=ccy,
        ))
    return out


def recorded_adjustments(rows: list, aged: dict[str, int], ccy: str,
                         cob: date) -> list[dict]:
    """Breaks resolved earlier today. 'posted' went straight through FAS, so
    it reads as Auto; 'approved' needed a controller, so it reads as Manual."""
    out = []
    for row, book in rows:
        delta = float(row.delta)
        fo, bo = _float(row.fo_value), _float(row.bo_value)
        label = row.narrative or row.pattern_code
        reason = row.reason_text or label
        out.append(_row(
            break_id=row.break_id,
            book=book,
            pattern=row.pattern_code,
            label=label,
            auto=row.outcome == "posted",
            reason=reason,
            delta=delta,
            status=ADJ_STATUS.get(row.outcome, "Pending"),
            grounded=not row.is_ungrounded,
            aged=aged.get(row.break_id, 0),
            detail=break_detail(
                break_id=row.break_id, book=book, label=label, reason=reason,
                fo=fo, bo=bo, delta=delta, ccy=ccy, finding=None,
                escalate_to=None, grounded=not row.is_ungrounded,
                recorded_outcome=row.outcome,
            ),
            legs_=legs(row.break_id, book, fo, bo, ccy, cob),
            ccy=ccy,
        ))
    return out
