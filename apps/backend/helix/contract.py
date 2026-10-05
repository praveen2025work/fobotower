"""What a capability needs from its data, and what it is waiting for people
to confirm — derived from its configuration, never written by hand.

data       every item field the configuration reads, and what reads it: the
           item source and display, cause checks, validation tests (and the
           fields they need), findings, the in-scope filter, grouping,
           follow-through. A field missing at run time makes a check
           negative and a test "not run"; nothing is assumed.
parameters every policy value, where it is used, and whether it is set. An
           unset one (P1: never invent a threshold) is "to confirm": tests
           that need it do not run and verdicts that depend on it ask the
           reviewer for confirmation.

The same function serves a capability and a team group (its effective
manifest), so the FOBO Prime group, the cash group and variance commentary
each get their own contract.
"""

from helix import rules
from helix.manifest import Manifest

# Fields Helix itself adds to an item.
DERIVED = {"carried_verdict": "follow_through", "carried_from": "follow_through",
           "carried_runs": "follow_through", "category": "playbook", "side": "playbook",
           "cause": "playbook", "cause_reason": "playbook", "category_name": "playbook",
           "determinism": "playbook", "escalate_to": "playbook", "item_id": "Helix"}


def _add(out: dict, field: str, used_by: str) -> None:
    out.setdefault(field, []).append(used_by)


def contract(m: Manifest) -> dict:
    fields: dict[str, list[str]] = {}
    policy_uses: dict[str, list[str]] = {}

    def expr(source: str | None, used_by: str, item_level: bool = True, policies: bool = True) -> None:
        if not source:
            return
        try:
            f, p = rules.names(source)
        except rules.ExpressionError:
            return
        if item_level:   # a group-level expression reads group fields, not the data's
            for name in f:
                _add(fields, name, used_by)
        for name in p if policies else ():
            _add(policy_uses, name, used_by)

    _add(fields, m.items.id_field, "item id")
    if m.items.amount_field:
        _add(fields, m.items.amount_field, "amount")
    for f in m.items.display:
        _add(fields, f, "shown to reviewers")
    for f in m.group_by:
        _add(fields, f, "grouping")
    expr(m.items.in_scope, "in-scope filter")
    for r in m.rules:
        expr(r.when, f"rule {r.id}", item_level=False)
    expr(m.review.dual_review_when, "dual review", item_level=False)
    if m.escalation:
        expr(m.escalation.when, "tickets", item_level=False)
    if m.playbook:
        pb = m.playbook
        for c in pb.checks:
            expr(c.when, f"check {c.id}")
        for t in pb.tests:
            expr(t.fails_when, f"test {t.id}", policies=False)
            for f in t.needs:
                _add(fields, f, f"test {t.id}")
            for p in t.policy:
                _add(policy_uses, p, f"test {t.id} (not run while unset)")
        for f in pb.findings:
            expr(f.when, f"finding {f.id}")
        for g in pb.guards:
            expr(g.when, f"guard on {g.verdict}", item_level=False)
        for p in pb.verdict_policy:
            _add(policy_uses, p, "verdicts (a POST asks the reviewer to confirm while unset)")
    for e in m.enrich:
        for k in e.keys:
            _add(fields, k, f"join with {e.tool}")
    resolved = {r.as_: f"reference lookup from {r.node}" for r in m.resolve}
    if m.compare:
        resolved[m.compare.as_] = f"Helix: {m.compare.measure} − {m.compare.baseline}"
        for f in (m.compare.measure, m.compare.baseline):
            _add(fields, f, "compare")
    if m.match:
        for f in (f"{m.match.left_label}_amount", f"{m.match.right_label}_amount", "difference", "break_type"):
            resolved[f] = "Helix: the match"
        for f in [*m.match.keys, m.match.amount_field]:
            _add(fields, f, f"match {m.match.left.tool} with {m.match.right.tool}")
    for r in m.resolve:
        for f in rules.template_fields(r.node):
            _add(fields, f, f"reference lookup {r.as_}")

    data = []
    for name, used in sorted(fields.items()):
        derived = DERIVED.get(name) or resolved.get(name)
        data.append({"field": name, "used_by": sorted(set(used)),
                     "from": derived or (_source(m) if name in _source_fields(m) or not m.enrich
                                         else f"{_source(m)} or {', '.join(e.tool for e in m.enrich)}"),
                     "derived": bool(derived)})
    parameters = []
    for name, pv in sorted(m.policy.items()):
        parameters.append({"name": name, "value": pv.value, "unit": pv.unit,
                           "used_by": sorted(set(policy_uses.get(name, []))),
                           "to_confirm": pv.value is None})
    for name in sorted(set(policy_uses) - set(m.policy)):
        parameters.append({"name": name, "value": None, "unit": None, "used_by": sorted(set(policy_uses[name])),
                           "to_confirm": True, "missing": True})
    return {"source": _source(m), "enrich": [e.tool for e in m.enrich], "data": data,
            "parameters": parameters,
            "to_confirm": [p["name"] for p in parameters if p["to_confirm"]]}


def _source(m: Manifest) -> str:
    if m.items.load:
        return m.items.load.tool
    if m.match:
        return f"{m.match.left.tool} vs {m.match.right.tool}"
    return "—"


def _source_fields(m: Manifest) -> set[str]:
    """Fields the item source is known to provide: those it shows and keys on."""
    out = {m.items.id_field, *m.items.display}
    if m.items.amount_field:
        out.add(m.items.amount_field)
    if m.match:
        out |= set(m.match.keys)
    return out
