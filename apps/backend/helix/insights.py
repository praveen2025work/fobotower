"""Insights across cases: items that keep coming back.

Configured by `insights.recurring` in the manifest (capability or group):

    insights:
      recurring:
        same: [book]          # case-key fields that must match: the same book, earlier COBs
        lookback_cases: 10    # how many earlier runs to look at
        min_runs: 2           # flagged when seen in at least this many runs, this one included

An item recurs when the same item id was in a reviewed group (in scope) of
an earlier case of the same capability and team group whose `same` fields
match. Re-runs of one key count once. Only cases the caller may see count
on the capability-wide list.
"""

from sqlalchemy import select

from helix.db import get_session
from helix.entitlement import Caller
from helix.manifest import Manifest
from helix.models import Case, ProposalGroup


def _key_of(c: Case) -> str:
    return c.root_case_id or c.case_id


async def _in_scope_items(s, case_ids: list[str]) -> dict[str, set[str]]:
    rows = (await s.execute(select(ProposalGroup.case_id, ProposalGroup.item_ids).where(
        ProposalGroup.case_id.in_(case_ids)))).all() if case_ids else []
    out: dict[str, set[str]] = {}
    for case_id, item_ids in rows:
        out.setdefault(case_id, set()).update(item_ids or [])
    return out


async def recurring_for_case(case: Case, m: Manifest, item_ids: list[str]) -> dict[str, dict]:
    """item_id -> {runs, earlier: [{case_id, subject, opened_at}]} for this case's items."""
    spec = m.insights.recurring
    if not spec or not item_ids:
        return {}
    async with get_session() as s:
        q = select(Case).where(Case.capability_id == case.capability_id, Case.shadow_of.is_(None),
                               Case.case_id != case.case_id, Case.opened_at < case.opened_at)
        q = q.where(Case.team_group == case.team_group) if case.team_group else q.where(Case.team_group.is_(None))
        for f in spec.same:
            q = q.where(Case.case_key[f].astext == str(case.case_key.get(f)))
        earlier = [c for c in (await s.execute(q.order_by(Case.opened_at.desc()).limit(
            spec.lookback_cases * 3))).scalars() if _key_of(c) != _key_of(case)]
        # one run per case key (the latest attempt), newest first
        runs: dict[str, Case] = {}
        for c in earlier:
            k = str(sorted(c.case_key.items()))
            if k not in runs and str(sorted(c.case_key.items())) != str(sorted(case.case_key.items())):
                runs[k] = c
        runs_list = list(runs.values())[:spec.lookback_cases]
        seen = await _in_scope_items(s, [c.case_id for c in runs_list])
    out = {}
    for item_id in item_ids:
        hits = [c for c in runs_list if item_id in seen.get(c.case_id, set())]
        if len(hits) + 1 >= spec.min_runs:
            out[item_id] = {"runs": len(hits) + 1,
                            "earlier": [{"case_id": c.case_id, "subject": c.subject,
                                         "opened_at": c.opened_at} for c in hits]}
    return out


async def recurring_overview(capability_id: str, caller: Caller, team_group: str | None,
                             limit_cases: int = 300) -> list[dict]:
    """Items recurring across the caller's visible cases of a capability (or
    group), most frequent first, by the group's `same` fields."""
    from helix.cases import visible_cases

    rows = await visible_cases(caller, capability_id=capability_id, team_group=team_group,
                               limit=limit_cases)
    rows = [(c, m) for c, m in rows if m.insights.recurring]
    if not rows:
        return []
    latest: dict[str, tuple[Case, Manifest]] = {}
    for c, m in rows:                                 # newest first: keep the latest attempt per key
        latest.setdefault(str(sorted(c.case_key.items())) + (c.team_group or ""), (c, m))
    async with get_session() as s:
        seen = await _in_scope_items(s, [c.case_id for c, _ in latest.values()])
    tally: dict[tuple, dict] = {}
    for c, m in latest.values():
        same = tuple((f, c.case_key.get(f)) for f in m.insights.recurring.same)
        for item_id in seen.get(c.case_id, set()):
            t = tally.setdefault((c.team_group, same, item_id), {
                "item_id": item_id, "team_group": c.team_group, "same": dict(same),
                "runs": 0, "latest_case_id": c.case_id, "latest_subject": c.subject,
                "min_runs": m.insights.recurring.min_runs})
            t["runs"] += 1
    out = [t for t in tally.values() if t["runs"] >= t["min_runs"]]
    return sorted(out, key=lambda t: (-t["runs"], t["item_id"]))[:100]
