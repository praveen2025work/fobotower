"""The sign-off checklist (review.checklist): questions a reviewer answers
before approving a group — e.g. the FOBO skill's §14 completion checklist.

Each question may show what Helix already knows (`prefill`): the tests run on
the group's items, the evidence and answers on the case, the verdict, the
category, or one of the model's answer sections. Approving needs every
required question answered yes or n/a; the answers are kept on the decision.
"""

from collections import Counter

from helix.manifest import Manifest

ANSWERS = ("yes", "no", "n/a")


class ChecklistError(ValueError):
    pass


def _tests(items: list[dict]) -> str:
    rows = [t for it in items for t in (it.get("tests") or [])]
    if not rows:
        return ""
    n = Counter(t.get("status") for t in rows)
    out = f"{len(rows)} tests on {len(items)} item(s): {n['pass']} passed, {n['fail']} failed, {n['not_run']} not run"
    failed = sorted({t["id"] for t in rows if t.get("status") == "fail"})
    return out + (f" (failed: {', '.join(failed)})" if failed else "")


def _category(finding: dict, items: list[dict]) -> str:
    if not finding.get("category"):
        return ""
    reasons = sorted({it.get("cause_reason") for it in items if it.get("cause_reason")})
    return (f"{finding['category']} · {finding.get('category_name', '')} ({finding.get('determinism', '')})"
            + (f": {'; '.join(reasons[:3])}" if reasons else ""))


def _verdict(finding: dict) -> str:
    v = finding.get("verdict") or finding.get("status") or ""
    return f"{v.replace('_', ' ')}: {finding.get('comment') or finding.get('reason') or ''}".strip(": ")


def known(m: Manifest, finding: dict | None, items: list[dict], evidence: list[dict], answers: list[dict]) -> list[dict]:
    """The checklist for one group, with what Helix already knows next to each question."""
    finding = finding or {}
    sections = {x["id"]: x.get("text", "") for x in finding.get("sections") or []}
    out = []
    for q in m.review.checklist:
        k = ""
        if q.prefill == "tests":
            k = _tests(items)
        elif q.prefill == "evidence":
            parts = [f"{len(evidence)} file(s) on the case"] if evidence else []
            parts += [f"{a['target_name']}: {a['answer']}" for a in answers]
            k = "; ".join(parts)
        elif q.prefill == "verdict":
            k = _verdict(finding)
        elif q.prefill == "category":
            k = _category(finding, items)
        elif q.prefill:
            k = sections.get(q.prefill, "")
        out.append({"id": q.id, "label": q.label, "required": q.required, "known": k})
    return out


def answered(m: Manifest, action: str, given: list[dict] | None) -> list[dict] | None:
    """The reviewer's answers, checked: approving needs every required question
    answered yes or n/a. Rejecting needs none (answers given are kept)."""
    if not m.review.checklist:
        return None
    by = {a.get("id"): a for a in (given or []) if isinstance(a, dict)}
    unknown = sorted(set(by) - {q.id for q in m.review.checklist})
    if unknown:
        raise ChecklistError(f"not on the checklist: {', '.join(unknown)}")
    out, missing = [], []
    for q in m.review.checklist:
        a = by.get(q.id) or {}
        answer = a.get("answer")
        if answer is not None and answer not in ANSWERS:
            raise ChecklistError(f"{q.label}: answer yes, no or n/a")
        if action == "approve" and q.required and answer not in ("yes", "n/a"):
            missing.append(q.label)
        out.append({"id": q.id, "label": q.label, "answer": answer,
                    "note": (a.get("note") or "").strip() or None})
    if missing:
        raise ChecklistError("the sign-off checklist is not complete: " + "; ".join(missing))
    return out if action == "approve" or given else None
