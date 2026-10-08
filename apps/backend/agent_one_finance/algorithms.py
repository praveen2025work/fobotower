"""Algorithm steps: evidence a person (or the playbook) can act on.

Configured like every other step (`step_settings`), checked with the manifest,
run under the same gateway and audit. Each one only ADDS fields to the items
(and sometimes a small data set): nothing is matched, removed, posted or
decided by an algorithm. A playbook check or a person decides what the
evidence means. Every result is reproducible — the same inputs give the same
answer — and explains itself (what was paired, which rows sum, which peers).

  offsets        equal-and-opposite amounts (cancel and rebook, booked to the
                 wrong instrument, a reversal across the cut-off)
  subset_match   a few rows that together explain an item's amount (a split
                 or partial booking), searched within bounds
  trend          how an item moved over its own history: growing, shrinking,
                 flipping sign
  cluster        the same item breaking in several books or entities at once
                 (one systemic cause, not many)
  fuzzy_match    near-identical references (typos, formats) — candidates only
  benford        first-digit (Benford) and round-amount tests over a population
"""

import bisect
import itertools
import math
import re
from typing import Any, Literal

from pydantic import Field

from agent_one_finance import rules
from agent_one_finance.stepkit import Cfg, StepType, _args, _env, _keep_dataset, _save, ds, register


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _key(row: dict, fields: list[str]) -> tuple:
    return tuple(str(row.get(f)) for f in fields)


def _holds(expr: str | None, state: dict, item: dict) -> bool:
    if not expr:
        return True
    try:
        return bool(rules.evaluate(expr, _env(state, item)))
    except rules.ExpressionError:
        return False


def _pool(state: dict, name: str) -> list[dict]:
    return list(state["items"]) if name == "items" else list((state.get("datasets") or {}).get(name, []))


def _pool_refs(c) -> set[str]:
    return set() if c.pool == "items" else {c.pool}


# ---------------------------------------------------------------------
# offsets: equal and opposite
# ---------------------------------------------------------------------

class OffsetsCfg(Cfg):
    amount: str = "amount"
    within: list[str] = Field(default_factory=list)   # both must share these (e.g. book)
    same: list[str] = Field(default_factory=list)     # …and these, when set (e.g. currency)
    tolerance: float = Field(default=0.01, ge=0)
    as_: str = Field(default="offset", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


async def _offsets(state, cfg: OffsetsCfg, step_id):
    """Pairs each positive amount with the closest unpaired negative of the same
    size (within the tolerance) in the same `within` group: the smallest
    difference first, then item order — so the pairing never changes."""
    a = cfg.as_
    items = [dict(it) for it in sorted(state["items"], key=lambda i: str(i.get("item_id")))]
    by_group: dict[tuple, list[dict]] = {}
    for it in items:
        it[a] = False
        it[f"{a}_with"] = None
        it[f"{a}_pair"] = None
        by_group.setdefault(_key(it, cfg.within + cfg.same), []).append(it)
    pairs = []
    for group in by_group.values():
        neg = sorted((abs(_num(i.get(cfg.amount))), str(i["item_id"]), i) for i in group
                     if (_num(i.get(cfg.amount)) or 0) < 0)
        keys = [n[0] for n in neg]
        used: set[str] = set()
        for it in group:
            v = _num(it.get(cfg.amount))
            if not v or v <= 0:
                continue
            lo, hi = bisect.bisect_left(keys, v - cfg.tolerance), bisect.bisect_right(keys, v + cfg.tolerance)
            best = min((n for n in neg[lo:hi] if n[1] not in used), key=lambda n: (abs(n[0] - v), n[1]), default=None)
            if best is None:
                continue
            used.add(best[1])
            other = best[2]
            pid = f"{a.upper()}-{len(pairs) + 1}"
            for x, y in ((it, other), (other, it)):
                x[a], x[f"{a}_with"], x[f"{a}_pair"] = True, y["item_id"], pid
            pairs.append({"pair": pid, "positive": it["item_id"], "negative": other["item_id"],
                          "amount": round(v, 2), "difference": round(v - best[0], 2),
                          **{f: it.get(f) for f in cfg.within}})
    order = {str(i["item_id"]): n for n, i in enumerate(state["items"])}
    items.sort(key=lambda i: order[str(i["item_id"])])
    await _save(state, items)
    await _keep_dataset(state, step_id, a, step_id, pairs)
    return {"items": items, "datasets": {**(state.get("datasets") or {}), a: pairs}}


register(StepType(
    "offsets", "Equal and opposite", "Pairs equal-and-opposite amounts (cancel and rebook, booked to the wrong instrument, a reversal across the cut-off); marks both, decides nothing.",
    OffsetsCfg, _offsets))


# ---------------------------------------------------------------------
# subset_match: a few rows that sum to the item
# ---------------------------------------------------------------------

class SubsetCfg(Cfg):
    target: str = "amount"                  # the item's figure to explain
    pool: str = "items"                     # "items" or a data set
    pool_value: str = "amount"
    pool_label: str = "item_id"             # what each member is called in the result
    within: list[str] = Field(default_factory=list)   # pool rows share these fields with the item
    when: str | None = None                 # only for items where…
    sign: Literal["same", "opposite"] = "same"   # rows sum to the target, or net it to zero
    max_size: int = Field(default=4, ge=1, le=5)
    max_pool: int = Field(default=20, ge=1, le=30)
    tolerance: float = Field(default=0.01, ge=0)
    as_: str = Field(default="subset", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


MAX_COMBINATIONS = 250_000      # per item: the search stops, and says so


def find_subsets(target: float, values: list[float], *, max_size: int, tolerance: float,
                 limit: int = MAX_COMBINATIONS) -> tuple[list[int] | None, int, bool]:
    """The smallest set of `values` (by index) whose sum is within `tolerance`
    of `target`; how many sets of that size work (stops at 2); whether the
    search finished. Smallest first, then index order: reproducible."""
    tried = 0
    for size in range(1, max_size + 1):
        found: list[int] | None = None
        count = 0
        for combo in itertools.combinations(range(len(values)), size):
            tried += 1
            if tried > limit:
                return found, count, False
            if abs(sum(values[i] for i in combo) - target) <= tolerance:
                count += 1
                if found is None:
                    found = list(combo)
                if count >= 2:
                    return found, count, True
        if found is not None:
            return found, count, True
    return None, 0, True


async def _subset(state, cfg: SubsetCfg, step_id):
    a = cfg.as_
    pool_rows = _pool(state, cfg.pool)
    items = []
    for it in state["items"]:
        new = dict(it)
        new.update({f"{a}_found": False, f"{a}_members": [], f"{a}_sum": None, f"{a}_unique": None,
                    f"{a}_complete": None})
        target = _num(it.get(cfg.target))
        if target and _holds(cfg.when, state, it):
            want = target if cfg.sign == "same" else -target
            cands = [r for r in pool_rows
                     if not (cfg.pool == "items" and r.get("item_id") == it.get("item_id"))
                     and all(str(r.get(f)) == str(it.get(f)) for f in cfg.within)
                     and _num(r.get(cfg.pool_value))]
            # nearest in size first: a split is made of parts no bigger than the whole
            cands.sort(key=lambda r: (abs(_num(r.get(cfg.pool_value))) > abs(want) + cfg.tolerance,
                                      abs(abs(_num(r.get(cfg.pool_value))) - abs(want)), str(r.get(cfg.pool_label))))
            cands = cands[:cfg.max_pool]
            vals = [_num(r.get(cfg.pool_value)) for r in cands]
            idx, count, complete = find_subsets(want, vals, max_size=cfg.max_size, tolerance=cfg.tolerance)
            new[f"{a}_complete"] = complete
            if idx is not None:
                new.update({f"{a}_found": True,
                            f"{a}_members": [{"label": cands[i].get(cfg.pool_label), "value": vals[i]} for i in idx],
                            f"{a}_sum": round(sum(vals[i] for i in idx), 2), f"{a}_unique": count == 1})
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "subset_match", "Parts that add up", "Finds a few rows (up to 5) that together explain an item's amount — a split or partial booking; the smallest set first, and says if another set also works.",
    SubsetCfg, _subset, needs=lambda c: {"items"} | ({ds(c.pool)} if c.pool != "items" else set()),
    expressions=lambda c: [("when", c.when)] if c.when else [], dataset_refs=_pool_refs))


# ---------------------------------------------------------------------
# trend: how the item moved over its own history
# ---------------------------------------------------------------------

class TrendCfg(Cfg):
    history: str                          # data set of past values
    key: str                              # the field on both the items and the history
    value: str                            # the item's figure (today)
    history_value: str = "value"
    order: str                            # the history's position field
    oldest_first: bool = False            # True if a larger `order` is newer (a date); False for "cobs ago"
    min_points: int = Field(default=3, ge=2, le=60)
    as_: str = Field(default="trend", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


def describe_trend(series: list[float], min_points: int) -> dict:
    """Least-squares slope per period, sign flips, and a direction word, over
    the series oldest to newest."""
    pts = [v for v in series if v is not None]
    if len(pts) < min_points:
        return {"points": len(pts), "slope": None, "flips": None, "direction": None, "growing": None}
    n = len(pts)
    xm, ym = (n - 1) / 2, sum(pts) / n
    den = sum((x - xm) ** 2 for x in range(n))
    slope = sum((x - xm) * (y - ym) for x, y in enumerate(pts)) / den if den else 0.0
    flips = sum(1 for p, q in zip(pts, pts[1:]) if p and q and (p > 0) != (q > 0))
    mags = [abs(v) for v in pts[-min_points:]]
    growing = all(q > p for p, q in zip(mags, mags[1:]))
    shrinking = all(q < p for p, q in zip(mags, mags[1:]))
    direction = ("flipping" if flips >= 2 else "growing" if growing else "shrinking" if shrinking else "steady")
    return {"points": n, "slope": round(slope, 2), "flips": flips, "direction": direction, "growing": growing}


async def _trend(state, cfg: TrendCfg, step_id):
    hist: dict[str, list[tuple[float, float]]] = {}
    for r in (state.get("datasets") or {}).get(cfg.history, []):
        v, o = _num(r.get(cfg.history_value)), _num(r.get(cfg.order))
        if v is not None and o is not None:
            hist.setdefault(str(r.get(cfg.key)), []).append((o, v))
    a = cfg.as_
    items = []
    for it in state["items"]:
        past = sorted(hist.get(str(it.get(cfg.key)), []), reverse=not cfg.oldest_first)
        series = [v for _, v in past] + [_num(it.get(cfg.value))]
        t = describe_trend(series, cfg.min_points)
        items.append({**it, **{f"{a}_{k}": v for k, v in t.items()}})
    await _save(state, items)
    return {"items": items}


register(StepType(
    "trend", "Trend over history", "Reads each item's own history: growing, shrinking, steady or flipping sign, with the slope — a timing difference fades, a feed problem grows.",
    TrendCfg, _trend, needs=lambda c: {"items", ds(c.history)}, dataset_refs=lambda c: {c.history}))


# ---------------------------------------------------------------------
# cluster: the same thing breaking in several places
# ---------------------------------------------------------------------

class ClusterCfg(Cfg):
    same: list[str] = Field(min_length=1)      # e.g. [instrument]
    across: str                                # the field that differs (book, entity)
    amount: str | None = None
    within_pct: float | None = Field(default=50, gt=0)   # amounts within this % of each other; None = any
    min_count: int = Field(default=3, ge=2)    # places, this one included
    peers_tool: str | None = None              # read the other places; None = the case's own items
    peers_args: dict[str, Any] = Field(default_factory=dict)
    peers_amount: str | None = None
    show_where: bool = False                   # list the other places (they may be outside the caller's scope)
    as_: str = Field(default="systemic", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


async def _cluster(state, cfg: ClusterCfg, step_id):
    from agent_one_finance import gateway, steps_v2
    if cfg.peers_tool:
        try:
            peers = (await steps_v2._call(state, step_id, cfg.peers_tool,
                                          _args(cfg.peers_args, state["case_key"]))).get("rows", [])
        except (gateway.ToolDenied, gateway.ToolFailed) as e:
            return steps_v2._failed("PEERS_FAILED", e)
    else:
        peers = list(state["items"])
    p_amount = cfg.peers_amount or cfg.amount
    by_key: dict[tuple, list[dict]] = {}
    for r in peers:
        by_key.setdefault(_key(r, cfg.same), []).append(r)
    a = cfg.as_
    items = []
    for it in state["items"]:
        mine, v = str(it.get(cfg.across)), _num(it.get(cfg.amount)) if cfg.amount else None
        where = set()
        for r in by_key.get(_key(it, cfg.same), []):
            if str(r.get(cfg.across)) == mine:
                continue
            if cfg.amount and cfg.within_pct is not None:
                w = _num(r.get(p_amount))
                if v is None or w is None or (v > 0) != (w > 0) or abs(w - v) > abs(v) * cfg.within_pct / 100:
                    continue
            where.add(str(r.get(cfg.across)))
        count = len(where) + 1
        items.append({**it, a: count >= cfg.min_count, f"{a}_count": count,
                      **({f"{a}_where": sorted(where)[:20]} if cfg.show_where else {})})
    await _save(state, items)
    return {"items": items}


register(StepType(
    "cluster", "Same break, several places", "Counts the other books or entities where the same item breaks the same way; three or more points to one systemic cause, not many.",
    ClusterCfg, _cluster, tools=lambda c: {c.peers_tool} if c.peers_tool else set()))


# ---------------------------------------------------------------------
# fuzzy_match: near-identical references (candidates only)
# ---------------------------------------------------------------------

def _clean(s: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s or "").upper())


def jaro_winkler(a: str, b: str) -> float:
    """Jaro–Winkler similarity, 0 to 1, of two strings as given."""
    if a == b:
        return 1.0 if a else 0.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    reach = max(la, lb) // 2 - 1
    ma, mb = [False] * la, [False] * lb
    m = 0
    for i, ch in enumerate(a):
        for j in range(max(0, i - reach), min(lb, i + reach + 1)):
            if not mb[j] and b[j] == ch:
                ma[i] = mb[j] = True
                m += 1
                break
    if not m:
        return 0.0
    sa = [c for c, f in zip(a, ma) if f]
    sb = [c for c, f in zip(b, mb) if f]
    t = sum(x != y for x, y in zip(sa, sb)) / 2
    jaro = (m / la + m / lb + (m - t) / m) / 3
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1 - jaro)


class FuzzyCfg(Cfg):
    field: str                               # the item's reference
    pool: str = "items"                      # "items" or a data set
    pool_field: str | None = None            # default: the same name as `field`
    pool_label: str | None = None            # what to call a candidate; default: its reference
    when: str | None = None                  # only for items where… (e.g. one side is missing)
    amount: str | None = None
    pool_amount: str | None = None
    amount_within_pct: float | None = Field(default=None, gt=0)
    threshold: float = Field(default=0.88, gt=0, le=1)
    as_: str = Field(default="near", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


async def _fuzzy(state, cfg: FuzzyCfg, step_id):
    pf = cfg.pool_field or cfg.field
    pool_rows = _pool(state, cfg.pool)
    a = cfg.as_
    items = []
    for it in state["items"]:
        new = {**it, a: False, f"{a}_candidates": []}
        ref = _clean(it.get(cfg.field))
        if ref and _holds(cfg.when, state, it):
            v = _num(it.get(cfg.amount)) if cfg.amount else None
            cands = []
            for r in pool_rows:
                if cfg.pool == "items" and r.get("item_id") == it.get("item_id"):
                    continue
                raw = r.get(pf)
                other = _clean(raw)
                if not other or str(raw).strip().upper() == str(it.get(cfg.field)).strip().upper():
                    continue                       # the same reference is a match, not a near one
                score = jaro_winkler(ref, other)
                if score < cfg.threshold:
                    continue
                w = _num(r.get(cfg.pool_amount or cfg.amount)) if cfg.amount else None
                if cfg.amount_within_pct and (v is None or w is None or abs(w - v) > abs(v) * cfg.amount_within_pct / 100):
                    continue
                cands.append({"candidate": r.get(cfg.pool_label or pf), "reference": r.get(pf),
                              "score": round(score, 3), **({"amount": w} if w is not None else {})})
            cands.sort(key=lambda c: (-c["score"], str(c["reference"])))
            new.update({a: bool(cands), f"{a}_candidates": cands[:3]})
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "fuzzy_match", "Near-identical references", "Finds references that differ only by a typo or format (Jaro-Winkler) — optionally with a similar amount; candidates for a person, never a match.",
    FuzzyCfg, _fuzzy, needs=lambda c: {"items"} | ({ds(c.pool)} if c.pool != "items" else set()),
    expressions=lambda c: [("when", c.when)] if c.when else [], dataset_refs=_pool_refs))


# ---------------------------------------------------------------------
# benford: first digits and round amounts over a population
# ---------------------------------------------------------------------

BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}
# Nigrini's first-digit conformity bands for the mean absolute deviation.
CONFORMITY = [(0.006, "close conformity"), (0.012, "acceptable conformity"),
              (0.015, "marginal conformity"), (math.inf, "nonconformity")]


def first_digit(v: float) -> int | None:
    v = abs(v)
    if v < 1:
        return None
    s = f"{v:.6e}"
    return int(s[0])


def benford_test(values: list[float]) -> dict:
    digits = [d for d in (first_digit(v) for v in values) if d]
    n = len(digits)
    rows = []
    mad = chi2 = 0.0
    for d in range(1, 10):
        obs = sum(1 for x in digits if x == d)
        p_obs, p_exp = (obs / n if n else 0.0), BENFORD[d]
        se = math.sqrt(p_exp * (1 - p_exp) / n) if n else 0.0
        z = (abs(p_obs - p_exp) - (1 / (2 * n) if n else 0)) / se if se else 0.0
        rows.append({"digit": d, "count": obs, "observed": round(p_obs, 4), "expected": round(p_exp, 4),
                     "z": round(max(z, 0.0), 2), "over": p_obs > p_exp and z > 1.96})
        mad += abs(p_obs - p_exp) / 9
        chi2 += (obs - n * p_exp) ** 2 / (n * p_exp) if n else 0.0
    verdict = next(label for limit, label in CONFORMITY if mad < limit) if n else None
    return {"n": n, "mad": round(mad, 4), "chi2": round(chi2, 2), "conformity": verdict, "digits": rows}


class BenfordCfg(Cfg):
    field: str = "amount"
    min_items: int = Field(default=100, ge=10)     # fewer: the test is "not run", never passed
    round_to: float | None = Field(default=1000, gt=0)
    as_: str = Field(default="benford", alias="as", pattern=r"^[a-z][a-z0-9_]{0,30}$")


async def _benford(state, cfg: BenfordCfg, step_id):
    a = cfg.as_
    values = [v for v in (_num(i.get(cfg.field)) for i in state["items"]) if v is not None]
    result = benford_test(values)
    ran = result["n"] >= cfg.min_items
    over = {r["digit"] for r in result["digits"] if r["over"]} if ran else set()
    items = []
    for it in state["items"]:
        v = _num(it.get(cfg.field))
        d = first_digit(v) if v is not None else None
        rnd = bool(cfg.round_to and v and abs(v) >= cfg.round_to and abs(v) % cfg.round_to == 0)
        items.append({**it, f"{a}_digit": d, f"{a}_over": bool(d in over), "round_amount": rnd})
    summary = [{"test": "first digit (Benford)", "status": "run" if ran else
                f"not run: {result['n']} amounts, fewer than {cfg.min_items}",
                "n": result["n"], "mad": result["mad"] if ran else None, "chi2": result["chi2"] if ran else None,
                "conformity": result["conformity"] if ran else None,
                "over_represented": sorted(over)},
               {"test": "round amounts", "status": "run" if cfg.round_to else "off", "round_to": cfg.round_to,
                "count": sum(1 for i in items if i["round_amount"]), "n": len(items)}]
    if ran:
        summary += [{"test": f"digit {r['digit']}", **r} for r in result["digits"]]
    await _save(state, items)
    await _keep_dataset(state, step_id, a, step_id, summary)
    return {"items": items, "datasets": {**(state.get("datasets") or {}), a: summary}}


register(StepType(
    "benford", "Benford and round amounts", "Tests the population's first digits against Benford's law (Nigrini's conformity bands) and flags round amounts — for journal and payment controls; too few amounts is \"not run\".",
    BenfordCfg, _benford))
