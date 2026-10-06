"""Who may decide a group, and how many people: the authority matrix (with
review lanes) and decision boundaries (decisions reserved for named people).

Both are applied to every group's finding when it is proposed, so the case
shows them, and enforced when people decide:

  authority   review.authority tiers (first match wins), or the bank's
              delegated-authority system read as a data set
              (review.authority_dataset: rows with min_amount, max_amount,
              roles, approvals, lane, bulk). Sets the lane, the roles that may
              approve and how many different people must.
  boundaries  decisions reserved for named roles (credit, sanctions, AML, KYC,
              payment release…). If the model proposed a reserved outcome it
              may not propose, its proposal is withheld and the group goes to
              a person; only the named roles may decide it; never in bulk.
"""

from helix import rules
from helix.manifest import Manifest


def _env(m: Manifest, g: dict, finding: dict) -> dict:
    return {**g.get("group_key", {}), "total": g.get("total"), "count": g.get("count"),
            "policy": m.policy_values(), "verdict": finding.get("verdict"), "status": finding.get("status"),
            "category": finding.get("category"), "side": finding.get("side"),
            "max_risk": max((it.get("risk_score") or 0 for it in g.get("items_view", [])), default=0)}


def _truthy(expr: str | None, env: dict) -> bool:
    if not expr:
        return True
    try:
        return bool(rules.evaluate(expr, env))
    except rules.ExpressionError:
        return True          # cannot tell: the stricter reading (the tier or boundary applies)


def _as_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def tier(m: Manifest, g: dict, finding: dict, datasets: dict) -> dict | None:
    env = _env(m, g, finding)
    if m.review.authority_dataset:
        amount = abs(float(g.get("total") or 0))
        for row in datasets.get(m.review.authority_dataset, []):
            lo, hi = row.get("min_amount"), row.get("max_amount")
            if (lo is None or amount >= float(lo)) and (hi is None or amount < float(hi)):
                return {"label": row.get("label") or f"{lo or 0}–{hi or '∞'}", "roles": _as_list(row.get("roles")),
                        "approvals": int(row.get("approvals") or 1), "lane": row.get("lane") or "standard",
                        "bulk": bool(row.get("bulk", True)), "source": m.review.authority_dataset}
    for i, t in enumerate(m.review.authority):
        if _truthy(t.when, env):
            return {"label": t.label or t.when or f"tier {i + 1}", "roles": list(t.roles) or list(m.review.roles),
                    "approvals": t.approvals, "lane": t.lane, "bulk": t.bulk, "source": "configuration"}
    return None


def apply(m: Manifest, g: dict, finding: dict, datasets: dict | None = None) -> dict:
    """The finding with its authority tier and any reserved decision."""
    if not m.review.authority and not m.review.authority_dataset and not m.boundaries:
        return finding
    out = dict(finding)
    if t := tier(m, g, out, datasets or {}):
        out["authority"] = t
    env = _env(m, g, out)
    for b in m.boundaries:
        hit = (out.get("verdict") in b.verdicts) if b.verdicts else False
        if b.when:
            hit = hit or _truthy(b.when, env)
        if not hit:
            continue
        out["reserved"] = {"roles": list(b.roles), "reason": b.reason or "a decision reserved for named people"}
        if not b.model_may_propose and str(out.get("decided_by", "")).startswith("llm"):
            out["withheld_proposal"] = out.get("verdict")
            out["verdict"] = None
            out["status"] = "escalated"
            out["reason"] = f"RESERVED: {out['reserved']['reason']}"
        break
    return out


def may_decide(finding: dict | None, caller) -> str | None:
    """Why this caller may not decide the group (None: they may)."""
    f = finding or {}
    if (r := f.get("reserved")) and not caller.has_any_role(r["roles"]):
        return f"reserved for {', '.join(r['roles'])}: {r['reason']}"
    if (t := f.get("authority")) and t.get("roles") and not caller.has_any_role(t["roles"]):
        return f"above your authority: {t['label']} needs one of {', '.join(t['roles'])}"
    return None


def approvals_needed(finding: dict | None) -> int:
    return int(((finding or {}).get("authority") or {}).get("approvals") or 1)
