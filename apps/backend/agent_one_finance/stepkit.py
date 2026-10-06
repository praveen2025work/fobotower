"""Configurable step types: the step SDK, and the generic data steps.

A capability lists its steps by id (`steps: [load, fx, age, convert, group, …]`)
and configures each one that is not a core step under `step_settings`:

    step_settings:
      fx:      {type: dataset, with: {name: fx, tool: refdata.fx_rates, args: {date: $case.date}}}
      age:     {type: derive, with: {fields: {age_hours: "hours_between(received_at, case.date)"}}}
      convert: {type: convert, when: "case.entity != 'GB01'", with: {amounts: [amount], currency_field: currency, to: GBP, rates: fx}}

A step type declares a config schema (validated with the manifest), what it
needs and produces (so the platform checks the order), the tools it calls (so
the gateway allows exactly those) and its expressions (checked when the
manifest is). Every type here is generic: no team's logic lives in code; a
team's own logic lives behind a tool (`transform`), which the gateway governs
like any other.

Nothing is silently lost: an item a `filter` or `dedupe` removes stays on the
case with `excluded_by` and `excluded_reason`.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent_one_finance import rules


class Cfg(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


@dataclass(frozen=True)
class StepType:
    name: str
    label: str
    says: str                                    # one line for the editor and the flow view
    config: type[Cfg]
    run: Callable[..., Awaitable[dict]]          # async (state, cfg, step_id) -> state update
    needs: Callable[[Any], set[str]] = lambda cfg: {"items"}
    produces: Callable[[Any], set[str]] = lambda cfg: {"items"}
    tools: Callable[[Any], set[str]] = lambda cfg: set()
    expressions: Callable[[Any], list[tuple[str, str]]] = lambda cfg: []
    dataset_refs: Callable[[Any], set[str]] = lambda cfg: set()
    extra: dict = field(default_factory=dict)


TYPES: dict[str, StepType] = {}


def register(t: StepType) -> StepType:
    TYPES[t.name] = t
    return t


def ds(name: str) -> str:
    return f"dataset:{name}"


# ---------- helpers shared by the data steps ----------

def _ctx(state: dict, purpose: str, tools: set[str] | None = None):
    from agent_one_finance import steps
    return steps._ctx(state, purpose, tools)


def _env(state: dict, item: dict | None = None) -> dict:
    from agent_one_finance import steps
    m = steps._manifest(state)
    return {**(item or {}), "policy": m.policy_values(), "case": dict(state["case_key"]),
            "count": len(state.get("items") or [])}


async def _save(state: dict, items: list[dict]) -> None:
    from agent_one_finance import steps
    await steps._save_items(state["case_id"], items)


async def _exclude(state: dict, step_id: str, items: list[dict], reason: str) -> None:
    """Items a step removes stay on the case, marked — never silently lost."""
    await _save(state, [{**it, "excluded_by": step_id, "excluded_reason": reason} for it in items])


async def _keep_dataset(state: dict, step_id: str, name: str, source: str, rows: list[dict]) -> None:
    from sqlalchemy import delete

    from agent_one_finance.db import get_session
    from agent_one_finance.models import CaseDataset
    async with get_session() as s:
        await s.execute(delete(CaseDataset).where(CaseDataset.case_id == state["case_id"],
                                                  CaseDataset.name == name))
        s.add(CaseDataset(case_id=state["case_id"], name=name, step_id=step_id, source=source,
                          rows=rows, row_count=len(rows)))
        await s.commit()


def _args(args: dict, case_key: dict) -> dict:
    return {k: case_key.get(v[6:]) if isinstance(v, str) and v.startswith("$case.") else v
            for k, v in args.items()}


# ---------- dataset: a named reference set beside the items ----------

class DatasetCfg(Cfg):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


async def _dataset(state, cfg: DatasetCfg, step_id):
    from agent_one_finance import gateway, steps
    try:
        result = await gateway.call(_ctx(state, step_id, {cfg.tool}), cfg.tool, _args(cfg.args, state["case_key"]))
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return steps._escalate("DATASET_FAILED", f"{cfg.name}: {e}")
    rows = list(result.get("rows", []))
    await _keep_dataset(state, step_id, cfg.name, cfg.tool, rows)
    return {"datasets": {**(state.get("datasets") or {}), cfg.name: rows}}


register(StepType(
    "dataset", "Reference data", "Reads a named data set beside the items: FX rates, a budget, limits, prior periods.",
    DatasetCfg, _dataset, needs=lambda c: set(), produces=lambda c: {ds(c.name)}, tools=lambda c: {c.tool}))


# ---------- derive: computed fields ----------

class DeriveCfg(Cfg):
    # In order: a later field may use an earlier one. Expression over the
    # item's fields, `case.<field>` and `policy.<name>`.
    fields: dict[str, str]


async def _derive(state, cfg: DeriveCfg, step_id):
    items = []
    for it in state["items"]:
        new = dict(it)
        errors = []
        for name, expr in cfg.fields.items():
            try:
                new[name] = rules.evaluate(expr, _env(state, new))
            except Exception as e:   # a missing field or bad value: None, and why — never a guess
                new[name] = None
                errors.append(f"{name}: {e}")
        if errors:
            new["derive_errors"] = [*(it.get("derive_errors") or []), *errors]
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "derive", "Computed fields", "Adds fields computed from each item, the case and policy (age, ratios, flags).",
    DeriveCfg, _derive, expressions=lambda c: [(f"fields.{k}", v) for k, v in c.fields.items()]))


# ---------- filter: keep what is in scope; the rest stays visible ----------

class FilterCfg(Cfg):
    keep_when: str
    reason: str = "filtered out"


async def _filter(state, cfg: FilterCfg, step_id):
    keep, drop = [], []
    for it in state["items"]:
        try:
            ok = bool(rules.evaluate(cfg.keep_when, _env(state, it)))
        except Exception:
            ok = True            # cannot tell: keep it for a person rather than drop it
        (keep if ok else drop).append(it)
    await _exclude(state, step_id, drop, cfg.reason)
    return {"items": keep}


register(StepType(
    "filter", "Filter", "Keeps the items that match; the others stay on the case, marked with the reason.",
    FilterCfg, _filter, expressions=lambda c: [("keep_when", c.keep_when)]))


# ---------- convert: currency as of the case's rates ----------

class ConvertCfg(Cfg):
    amounts: list[str]
    currency_field: str
    to: str = Field(pattern=r"^[A-Z]{3}$")
    rates: str                       # a data set: one row per currency
    rate_currency_field: str = "currency"
    rate_field: str = "rate"         # value of one unit of the currency in `to`
    suffix: str | None = None        # default: _<to>, e.g. amount_gbp


async def _convert(state, cfg: ConvertCfg, step_id):
    rows = (state.get("datasets") or {}).get(cfg.rates, [])
    rate = {str(r.get(cfg.rate_currency_field)): r.get(cfg.rate_field) for r in rows}
    rate[cfg.to] = 1.0
    suffix = cfg.suffix if cfg.suffix is not None else f"_{cfg.to.lower()}"
    items = []
    for it in state["items"]:
        new = dict(it)
        r = rate.get(str(it.get(cfg.currency_field)))
        for f in cfg.amounts:
            v = it.get(f)
            new[f + suffix] = round(float(v) * float(r), 2) if (r is not None and v is not None) else None
        if r is None:
            new["fx_missing"] = it.get(cfg.currency_field)      # never assume a rate
        else:
            new["fx_rate"] = r
        items.append(new)
    await _save(state, items)
    return {"items": items}


register(StepType(
    "convert", "Currency conversion", "Converts amounts to one currency with the case's own rates; a missing rate is flagged, never assumed.",
    ConvertCfg, _convert, needs=lambda c: {"items", ds(c.rates)}, dataset_refs=lambda c: {c.rates}))


# ---------- bucket: bands (ageing, size, service level) ----------

class Band(Cfg):
    label: str
    upto: float | None = None        # inclusive upper bound; None = everything above


class BucketCfg(Cfg):
    field: str
    as_: str = Field(alias="as")
    bands: list[Band] = Field(min_length=1)
    missing: str = "unknown"


async def _bucket(state, cfg: BucketCfg, step_id):
    items = []
    for it in state["items"]:
        v = it.get(cfg.field)
        label = cfg.missing
        if isinstance(v, (int, float)):
            label = next((b.label for b in cfg.bands if b.upto is None or v <= b.upto), cfg.missing)
        items.append({**it, cfg.as_: label})
    await _save(state, items)
    return {"items": items}


register(StepType(
    "bucket", "Bands", "Puts each item in a band of a field: ageing 0–1 day, 2–5 days…; size; service level.",
    BucketCfg, _bucket))


# ---------- dedupe: duplicates found and set aside ----------

class DedupeCfg(Cfg):
    keys: list[str] = Field(min_length=1)
    drop: bool = True                # set duplicates aside (kept on the case), or only mark them


async def _dedupe(state, cfg: DedupeCfg, step_id):
    seen: dict[tuple, str] = {}
    keep, dupes = [], []
    for it in state["items"]:
        k = tuple(str(it.get(f)) for f in cfg.keys)
        if k in seen:
            d = {**it, "duplicate_of": seen[k]}
            (dupes if cfg.drop else keep).append(d)
        else:
            seen[k] = it["item_id"]
            keep.append(it)
    if cfg.drop:
        await _exclude(state, step_id, dupes, "duplicate of " + ", ".join(sorted({d["duplicate_of"] for d in dupes})))
    else:
        await _save(state, keep)
    return {"items": keep}


register(StepType(
    "dedupe", "Duplicates", "Finds items with the same key fields; duplicates are set aside (kept on the case) or marked.",
    DedupeCfg, _dedupe))


# ---------- aggregate: roll up ----------

class AggregateCfg(Cfg):
    by: list[str] = Field(min_length=1)
    sum: list[str] = Field(default_factory=list)
    count_as: str = "count"
    keep: list[str] = Field(default_factory=list)     # fields carried from the first member
    into: str = "items"                                # items (members kept, marked) or a data set name


async def _aggregate(state, cfg: AggregateCfg, step_id):
    buckets: dict[tuple, list[dict]] = {}
    for it in state["items"]:
        buckets.setdefault(tuple(str(it.get(f)) for f in cfg.by), []).append(it)
    rows = []
    for key, members in sorted(buckets.items()):
        row = {**{f: members[0].get(f) for f in cfg.keep}, **dict(zip(cfg.by, [members[0].get(f) for f in cfg.by])),
               cfg.count_as: len(members), "members": [m["item_id"] for m in members]}
        for f in cfg.sum:
            row[f] = round(sum(float(m.get(f) or 0) for m in members), 2)
        row["item_id"] = "|".join(key)
        rows.append(row)
    if cfg.into != "items":
        await _keep_dataset(state, step_id, cfg.into, step_id, rows)
        return {"datasets": {**(state.get("datasets") or {}), cfg.into: rows}}
    await _exclude(state, step_id, state["items"], "rolled up")
    await _save(state, rows)
    return {"items": rows}


register(StepType(
    "aggregate", "Roll up", "Rolls items up by key fields with totals and counts — into the items, or into a data set.",
    AggregateCfg, _aggregate,
    produces=lambda c: {"items"} if c.into == "items" else {ds(c.into)}))


# ---------- transform: a team's own logic, behind a governed tool ----------

class TransformCfg(Cfg):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    # Fields sent to the tool (data minimisation); empty = every field.
    send: list[str] = Field(default_factory=list)
    # fields: merge the returned fields onto the items by item_id;
    # items: the tool's rows become the items.
    returns: Literal["fields", "items"] = "fields"


async def _transform(state, cfg: TransformCfg, step_id):
    from agent_one_finance import gateway, steps
    send = [{"item_id": it["item_id"], **({f: it.get(f) for f in cfg.send} if cfg.send else it)}
            for it in state["items"]]
    try:
        result = await gateway.call(_ctx(state, step_id, {cfg.tool}), cfg.tool,
                                    {**_args(cfg.args, state["case_key"]), "items": send})
    except (gateway.ToolDenied, gateway.ToolFailed) as e:
        return steps._escalate("TRANSFORM_FAILED", str(e))
    rows = list(result.get("rows", []))
    if cfg.returns == "items":
        items = [{**r, "item_id": str(r.get("item_id"))} for r in rows if r.get("item_id") is not None]
        gone = {it["item_id"] for it in state["items"]} - {it["item_id"] for it in items}
        await _exclude(state, step_id, [it for it in state["items"] if it["item_id"] in gone], f"not returned by {cfg.tool}")
    else:
        by = {str(r.get("item_id")): r for r in rows}
        items = [{**it, **{k: v for k, v in by.get(it["item_id"], {}).items() if k != "item_id"}}
                 for it in state["items"]]
    await _save(state, items)
    return {"items": items}


register(StepType(
    "transform", "Team logic (tool)", "Sends the items to the team's own tool and uses what it returns — for logic expressions cannot hold.",
    TransformCfg, _transform, tools=lambda c: {c.tool}))


# ---------- validation and use by the engine ----------

def parse(type_name: str, raw: dict) -> Any:
    return TYPES[type_name].config.model_validate(raw or {})


def catalogue() -> list[dict]:
    return [{"name": t.name, "label": t.label, "says": t.says, "configurable": True,
             "schema": t.config.model_json_schema(by_alias=True)} for t in TYPES.values()]


# The step types of phases 2–6 register themselves (agent_one_finance/steps_v2.py).
from agent_one_finance import steps_v2  # noqa: E402,F401
