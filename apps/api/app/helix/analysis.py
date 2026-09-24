"""The four-part analysis a rec's session opens with.

A live investigation already wrote its narrative (the draft node), so this
reuses it and adds only what the console needs on top: a confidence level
and a risk line that names ungrounded figures. Recs with no live narrative
(running, blocked, cleared earlier) get the same four parts built from their
rows. Every count and figure is computed here, never typed in.
"""

from collections import Counter

from app.helix.fmt import money, plural


def _family(rec) -> str:
    """'CATS vs MOTIF — Prime' -> 'CATS vs MOTIF'."""
    return rec.name.split(" — ")[0]


def running(rec) -> dict:
    return {
        "what": f"Analysis running. {_family(rec)} breaks for {rec.l4} are being "
                "pulled from MB Rec and classified.",
        "why": None,
        "confidence": "RUNNING",
        "confidenceNote": None,
        "action": "No action needed yet. The session opens for questions when the "
                  "analysis finishes.",
        "risk": None,
    }


def _ungrounded_risk(adjs: list[dict]) -> str | None:
    ids = [a["id"] for a in adjs if not a["grounded"]]
    if not ids:
        return None
    subject = ids[0] if len(ids) == 1 else ", ".join(ids)
    verb = "has an ungrounded figure" if len(ids) == 1 else "have ungrounded figures"
    return (
        f"{subject} {verb}. A number in the drafted adjustment could not be traced "
        "back to MB Rec source data. Verify the amount manually before approving."
    )


def live(values: dict, adjs: list[dict]) -> dict:
    draft = values.get("draft")
    draft = draft.model_dump() if hasattr(draft, "model_dump") else (draft or {})
    no_fix = [a for a in adjs if not a["detail"]["fix"]]
    ungrounded = [a for a in adjs if not a["grounded"]]
    troubled = values.get("validation_errors") or values.get("evidence_gaps")

    if troubled:
        confidence = "LOW"
    elif ungrounded or no_fix:
        confidence = "MEDIUM"
    else:
        confidence = "HIGH"

    risk = _ungrounded_risk(adjs)
    if risk is None and draft.get("risk") and not draft["risk"].startswith("No evidence gaps"):
        risk = draft["risk"]
    return {
        "what": draft.get("what_happened"),
        "why": draft.get("why"),
        "confidence": confidence,
        "confidenceNote": draft.get("confidence_basis"),
        "action": draft.get("what_to_do"),
        "risk": risk,
    }


def blocked(rec, breaks: list[dict], findings: dict, aged: dict[str, int],
            reasons: dict[str, str], escalation: dict[str, str]) -> dict:
    """Nothing can be drafted, so the analysis says why and who can fix it."""
    first = breaks[0]
    bid, book = first["break_id"], first["book_ref"]
    finding = findings.get(bid, {})
    route = escalation.get(finding.get("category_code")) or "the source-system owner"
    carried = aged.get(bid, 0)
    why = reasons.get(bid, "No cause identified") + "."
    if carried:
        why += (
            f" The same break has appeared in {carried} consecutive sessions with the "
            "delta unchanged, which points to an upstream fix rather than an adjustment."
        )
    return {
        "what": f"{plural(len(breaks), 'unresolved break')} between CATS and MOTIF "
                f"on {book}, {money(first['fo_value'] - first['bo_value'], rec.ccy)}.",
        "why": why,
        "confidence": "BLOCKED",
        "confidenceNote": f"The playbook verdict is {finding.get('verdict', 'ESCALATE')}, "
                          "so no adjustment can be drafted until the source data is corrected.",
        "action": f"Escalate to {route} to correct the source data for {book}. "
                  "Do not post anything until it is fixed.",
        "risk": "If this is not resolved before EOD sign-off, it carries into tomorrow "
                f"and may hold up P&L sign-off for the {rec.l4} master books.",
    }


def recorded(rec, run, adjs: list[dict]) -> dict:
    by_pattern = Counter((a["pattern"], a["patternLabel"], a["type"]) for a in adjs)
    parts = []
    for (pattern, label, kind), n in by_pattern.items():
        how = "posted automatically" if kind == "Auto" else "approved by a controller"
        if pattern == "UNCLASSIFIED":
            books = ", ".join(a["book"] for a in adjs if a["pattern"] == pattern)
            parts.append(f"{n} did not match a known pattern ({books}) and was {how}.")
        else:
            parts.append(f"{n} {'was a' if n == 1 else 'were'} {label.lower()} "
                         f"({pattern}), {how}.")
    grounded = all(a["grounded"] for a in adjs)
    return {
        "what": f"{plural(len(adjs), 'break')} identified across {rec.l4} master books "
                "between CATS and MOTIF.",
        "why": " ".join(parts) or None,
        "confidence": "HIGH" if grounded else "MEDIUM",
        "confidenceNote": (
            "All figures were traced back to MB Rec source values before drafting."
            if grounded else "Some figures could not be traced to MB Rec source values."
        ),
        "action": "Nothing required. All adjustments were posted to MOTIF via FAS, and "
                  f"all {run.books_unlocked} books are unlocked.",
        "risk": None,
    }
