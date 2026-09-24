"""Answer a question asked in a Helix session.

Deterministic first: each intent below is recognised by its wording and
answered from the rec's own data, and any data it needs is retrieved through
recorded tools. A question that matches no intent is not guessed at. It is
the reasoning service's to answer, and when none is configured the session
says so rather than improvising.
"""

import re
from collections import defaultdict

from app.helix.calls import SessionTools
from app.helix.fmt import money, money0, plural

# Words that name a pattern, for questions that do not use its code.
PATTERN_WORDS = [
    (r"p-204|p-118|timing|nostro|cutoff", ("P-204", "P-118")),
    (r"dup", ("DUP-SETTLE",)),
    (r"counterpart|cpty|static", ("CPTY-REF",)),
    (r"late|booking", ("LATE-BOOK",)),
    (r"dataset|curve|valuation", ("VAL-DATASET",)),
]


def _mentioned(rec: dict, t: str) -> list[dict]:
    """Adjustments named by id or book, in the order they appear on the rec."""
    adjs = rec["adjustments"]
    hits = [
        a for a in adjs
        if re.search(rf"(^|[^a-z0-9-]){re.escape(a['id'].lower())}($|[^0-9])", t)
        or a["book"].lower() in t
    ]
    if not hits and re.search(r"\bmanual\b", t):
        hits = [a for a in adjs if a["type"] == "Manual"]
    if not hits and re.search(r"\bauto\b", t):
        hits = [a for a in adjs if a["type"] == "Auto"]
    return hits


def _explain(a: dict) -> list[dict]:
    d = a["detail"]
    blocks = [
        {"type": "h", "text": f"{a['id']} on {a['book']}: {d['type']}"},
        {"type": "p", "text": d["cause"]},
        {"type": "kv", "items": [d["cats"], d["motif"], d["gap"]]},
        {"type": "ok", "text": (f"Proposed fix: {d['fix']}" if a["status"] == "Pending"
                                else d["fix"])} if d["fix"] else
        {"type": "warn", "text": "No posting proposed. Manual investigation is needed "
                                 "before any adjustment is made."},
    ]
    if not a["grounded"]:
        blocks.append({"type": "risk", "text": (
            f"The drafted figure for {a['id']} could not be traced back to the MB Rec "
            "source value (see grounding_check). Verify the amount against the CATS "
            "leg before approving.")})
    if d["verify"]:
        blocks.append({"type": "list", "title": "Before you approve, verify", "items": d["verify"]})
    pending = a["status"] == "Pending"
    blocks.append({"type": "note", "text": f"Current status: {a['status']}."
                   + (" Approving requires the two-step confirmation." if pending else "")})
    return blocks


def _total(adjs: list[dict]) -> float:
    return sum(a["delta"] for a in adjs)


async def _adjustments(rec, refs, tools: SessionTools) -> list[dict]:
    blocks = [b for a in refs[:3] for b in _explain(a)]
    await tools.break_legs(refs[:3])
    if any(not a["grounded"] for a in refs[:3]):
        await tools.grounding(refs[:3])
    return blocks


def _blocked(rec) -> list[dict]:
    an = rec["analysis"] or {}
    return [
        {"type": "p", "text": "This rec is blocked on source data, not on a decision. "
                              + (an.get("why") or "")},
        {"type": "list", "title": "Suggested next steps", "items": [
            an.get("action") or "Escalate to the source-system owner.",
            "Once the corrected data lands, One Fin UX raises a new MB Rec readiness "
            "event and Helix re-opens this session.",
        ]},
    ]


async def _grounding(rec, tools: SessionTools) -> list[dict]:
    adjs = rec["adjustments"]
    ug = [a for a in adjs if not a["grounded"]]
    if not adjs:
        return [{"type": "p", "text": "There are no drafted figures in this session yet."}]
    listed = ", ".join(f"{a['id']} ({a['book']}, {money(a['delta'], rec['ccy'])})" for a in ug)
    blocks = [{"type": "p", "text": (
        f"{len(ug)} of {len(adjs)} drafted figures could not be traced to an MB Rec "
        f"source value: {listed}. Everything else matched exactly."
        if ug else
        f"All {len(adjs)} drafted figures in this session trace back to MB Rec source values."
    )}]
    if ug:
        blocks.append({"type": "risk", "text": (
            "An ungrounded figure means the number in the draft does not equal any "
            "value returned by the MCP tools. Treat it as unverified until you check "
            "the CATS leg.")})
    await tools.grounding(adjs)
    return blocks


def _by_pattern(adjs: list[dict]) -> dict:
    groups: dict = {}
    for a in adjs:
        groups.setdefault(a["pattern"], {"label": a["patternLabel"], "items": []})["items"].append(a)
    return groups


def _safe(rec) -> list[dict]:
    pending = [a for a in rec["adjustments"] if a["status"] == "Pending"]
    safe, review, hold = [], [], []
    for code, g in _by_pattern(pending).items():
        items = g["items"]
        fix = all(a["detail"]["fix"] for a in items)
        grounded = all(a["grounded"] for a in items)
        line = (f"{code} {g['label']}: {plural(len(items), 'book')}, "
                f"{money0(_total(items), rec['ccy'])}")
        if fix and grounded and all(a["type"] == "Auto" for a in items):
            safe.append(line)
        elif fix:
            review.append(line)
        else:
            hold.append(line + (" (includes an ungrounded figure)" if not grounded else ""))
    blocks = [] if pending else [{"type": "p", "text": "Nothing is pending in this session."}]
    for items, tone, title in (
        (safe, "ok", "Grounded, single cause, fix proposed"),
        (review, "warn", "Fix proposed, review each book"),
        (hold, "risk", "Hold, no posting proposed yet"),
    ):
        if items:
            blocks.append({"type": "list", "tone": tone, "title": title, "items": items})
    blocks.append({"type": "note", "text": (
        "This is a recommendation only. Every approval still goes through the "
        "two-step confirmation before FAS posts to MOTIF.")})
    return blocks


async def _pending(rec, tools: SessionTools) -> list[dict]:
    adjs = rec["adjustments"]
    rows = defaultdict(lambda: {"pending": 0, "decided": 0, "value": 0.0})
    for a in adjs:
        r = rows[(a["pattern"], a["patternLabel"])]
        if a["status"] == "Pending":
            r["pending"] += 1
            r["value"] += a["delta"]
        else:
            r["decided"] += 1
    await tools.session_state([
        {"pattern": code, "label": label, **counts} for (code, label), counts in rows.items()
    ])
    p = [a for a in adjs if a["status"] == "Pending"]
    return [{"type": "p", "text": (
        f"{len(p)} of {len(adjs)} adjustments are still pending, worth "
        f"{money0(_total(p), rec['ccy'])}. {len(adjs) - len(p)} have been decided in this session."
        if p else f"All {len(adjs)} adjustments in this session have been decided."
    )}]


def _chase(rec, cob: str) -> list[dict]:
    """Pending items the playbook will not post: they wait on someone upstream."""
    waiting = [a for a in rec["adjustments"] if a["status"] == "Pending" and not a["detail"]["fix"]]
    if not waiting:
        return [{"type": "p", "text": "There is nothing that needs a desk chase in this session."}]
    lines = "\n".join(
        f"• {a['book']} ({a['id']}) {money(a['delta'], rec['ccy'])}: {a['detail']['type']}. {a['reason']}."
        for a in waiting
    )
    return [
        {"type": "p", "text": f"Here is a chase note covering the {len(waiting)} items that "
                              "depend on the desk or static data:"},
        {"type": "pre", "text": (
            f"Subject: {rec['name']} — {plural(len(waiting), 'break')} need confirmation "
            f"(COB {cob})\n\n{lines}\n\nPlease confirm before EOD sign-off so these can be "
            f"adjusted or cleared.\nHelix session {rec['sessionId']}")},
    ]


def _patterns_named(rec, t: str) -> tuple[str, ...] | None:
    codes = {a["pattern"] for a in rec["adjustments"]}
    named = tuple(c for c in codes if c.lower() in t)
    if named:
        return named
    for pattern, wanted in PATTERN_WORDS:
        if re.search(pattern, t):
            return wanted
    return None


async def _pattern(rec, codes, tools: SessionTools) -> list[dict]:
    items = [a for a in rec["adjustments"] if a["pattern"] in codes]
    if not items:
        return [{"type": "p", "text": "That pattern does not appear in this session."}]
    d = items[0]["detail"]
    await tools.break_legs(items, pattern=",".join(codes))
    return [
        {"type": "h", "text": f"{items[0]['patternLabel']}: {plural(len(items), 'book')}, "
                              f"{money0(_total(items), rec['ccy'])}"},
        {"type": "p", "text": re.sub(r"[A-Z]{3} [\d,]+\.\d{2}", "the break amount", d["cause"])},
        {"type": "ok", "text": "Each book gets its own adjustment of the break amount; one "
                               "group decision covers all of them."} if d["fix"] else
        {"type": "warn", "text": "No posting is proposed for this pattern until the upstream "
                                 "item is confirmed."},
    ]


def _unmatched(rec, reasoner: str) -> list[dict]:
    first = rec["adjustments"][0]["id"] if rec["adjustments"] else "an adjustment id"
    return [
        {"type": "p", "text": (
            f"I can answer from this session's MB Rec data for {rec['name']}. Ask about a "
            f"specific adjustment (for example {first}), a pattern, grounding, what is safe "
            "to approve, what is still pending, or ask me to draft a chase note.")},
        {"type": "note", "text": (
            "Questions outside this session's data go to the reasoning service. "
            + ("None is configured (reasoner: none), so this one was not sent."
               if reasoner == "none" else f"This deployment uses '{reasoner}'."))},
    ]


async def answer(rec: dict, question: str, tools: SessionTools, *, cob: str,
                 analysis_call_ids: list[str], reasoner: str) -> tuple[str, list[dict]]:
    """(intent, blocks). Retrievals land in tools.call_ids as they run."""
    t = question.lower()
    refs = _mentioned(rec, t)
    if refs and not re.search(r"chase|email|draft note|message to", t):
        return "adjustment", await _adjustments(rec, refs, tools)
    if rec["status"] == "Blocked":
        return "blocked", _blocked(rec)
    if re.search(r"ground|trace|verif|trust|accurate", t):
        return "grounding", await _grounding(rec, tools)
    if re.search(r"safe|recommend|which.*approv|should i approv|can i approv", t):
        return "safe_to_approve", _safe(rec)
    if re.search(r"pending|summar|left|outstanding|status|progress|where are we", t):
        return "pending", await _pending(rec, tools)
    if re.search(r"chase|email|draft|desk|message", t):
        return "chase_note", _chase(rec, cob)
    if re.search(r"mcp|data|source|tool|call|query|evidence", t):
        tools.call_ids.extend(analysis_call_ids)
        return "mcp_data", [{"type": "p", "text": (
            "The analysis used these MCP calls. Investigation data comes from MB Rec and "
            "Helix's own knowledge graph, not read directly from CATS or MOTIF. Open any "
            "call to see the rows it returned.")}]
    codes = _patterns_named(rec, t)
    if codes:
        return "pattern", await _pattern(rec, codes, tools)
    return "unmatched", _unmatched(rec, reasoner)
