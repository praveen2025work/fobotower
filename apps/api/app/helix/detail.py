"""What the console shows for one break: cause, both legs, fix, checks.

Built from three sources only: the break's two legs as MB Rec reports them,
the reason node's finding (category, side, verdict, guards), and the
playbook's escalation route. A fix is proposed only where the playbook's
verdict is POST; everywhere else the console says no posting is proposed.
"""

from datetime import date

from app.helix.fmt import money

POSTING_VERDICTS = {"POST", "CORRECT_AND_REPOST"}


def _param(name: str) -> str:
    return name.replace("_", " ")


def cause_text(reason: str, finding: dict | None) -> str:
    if not finding:
        return f"{reason}."
    text = f"{reason}."
    root = finding.get("root_cause")
    if root and finding.get("established"):
        text += f" {root}."
    category = finding.get("category_name")
    side = finding.get("side")
    if category:
        where = f" on the {side} side" if side in ("FO", "BO") else ""
        text += f" The playbook files this as a {category.lower()}{where}."
    return text


def fix_text(verdict: str | None, delta: float, book: str, ccy: str,
             finding: dict | None) -> str | None:
    if verdict == "POST":
        text = f"Post an adjustment of {money(delta, ccy)} to {book} so MOTIF agrees with CATS."
    elif verdict == "CORRECT_AND_REPOST":
        text = f"Correct the rejected MOTIF entry on {book} and re-post {money(delta, ccy)}."
    else:
        return None
    unset = (finding or {}).get("conditional_on") or []
    if unset:
        text += f" The playbook has no {' or '.join(_param(p) for p in unset)} set, so a controller confirms it."
    return text


def verify_items(finding: dict | None, escalate_to: str | None, grounded: bool,
                 playbook_version: str | None) -> list[str]:
    items: list[str] = []
    if not grounded:
        items.append("Check the drafted figure against the CATS leg: it did not trace to an MB Rec value")
    if finding:
        version = f" v{playbook_version}" if playbook_version else ""
        for p in finding.get("conditional_on") or []:
            items.append(f"Confirm the {_param(p)}: it is not set in the playbook{version}")
        verdict = finding.get("verdict")
        if verdict not in POSTING_VERDICTS and escalate_to:
            items.append(f"Route to {escalate_to}: the fix belongs upstream, not in a MOTIF adjustment")
        for reason in finding.get("guard_reasons") or []:
            if not reason.startswith("P1"):  # P1 is the unset parameters above
                items.append(reason)
    if not items:
        items.append("Confirm the CATS and MOTIF legs match the figures above")
    return items


def legs(break_id: str, book: str, fo: float | None, bo: float | None,
         ccy: str, cob: date) -> dict:
    """Both sides as MB Rec holds them. A missing side is an empty list, not
    a zero-value entry."""
    when = cob.strftime("%d %b EOD")

    def entry(side: str, value: float | None, status: str) -> list[dict]:
        if value is None:
            return []
        return [{
            "ref": f"MBR-{break_id}-{side}",
            "time": when,
            "ccy": ccy,
            "amount": value,
            "type": "Position",
            "status": status,
        }]

    note = (
        f"MB Rec reports {money(fo, ccy)} in CATS and {money(bo, ccy)} in MOTIF "
        f"for {book}; the break is the difference."
    )
    return {
        "cats": entry("CATS", fo, "Reported"),
        "motif": entry("MOTIF", bo, "Reported"),
        "note": note,
    }


def break_detail(*, break_id: str, book: str, label: str, reason: str,
                 fo: float | None, bo: float | None, delta: float, ccy: str,
                 finding: dict | None, escalate_to: str | None, grounded: bool,
                 recorded_outcome: str | None = None) -> dict:
    verdict = (finding or {}).get("verdict")
    if recorded_outcome in ("posted", "approved"):
        # Resolved earlier today: say what happened rather than re-proposing.
        fix = (
            f"Posted {money(delta, ccy)} to {book} via FAS."
            if recorded_outcome == "posted"
            else f"Approved by a controller and released to FAS for {book}."
        )
    else:
        fix = fix_text(verdict, delta, book, ccy, finding)
    return {
        "ref": f"BRK-{break_id}",
        "type": label,
        "delta": money(delta, ccy),
        "cause": cause_text(reason, finding),
        "cats": {"label": "CATS leg", "value": money(fo, ccy), "note": f"{book}, as MB Rec reports it"},
        "motif": {"label": "MOTIF leg", "value": money(bo, ccy), "note": f"{book}, as MB Rec reports it"},
        "gap": {"label": "Difference", "value": money(delta, ccy), "note": "CATS minus MOTIF"},
        "fix": fix,
        "verify": (
            [] if recorded_outcome else verify_items(
                finding, escalate_to, grounded, (finding or {}).get("playbook_version")
            )
        ),
        "grounded": grounded,
        "verdict": verdict,
        "category": (finding or {}).get("category_name"),
        "escalateTo": escalate_to,
    }
