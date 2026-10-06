import pytest

from helix import capabilities, rules
from helix.manifest import Manifest, problems
from helix.workflow import order_problems


def _variance() -> dict:
    m = next(m for m in capabilities.seed_files() if m.id == "fin.variance-commentary")
    return m.model_dump(by_alias=True)


def _problems(**changes) -> list[str]:
    return problems(Manifest.model_validate({**_variance(), **changes}))


def test_every_seeded_capability_is_valid():
    files = capabilities.seed_files()
    assert {m.id for m in files} == {"break.investigation", "fin.variance-commentary", "payments.exceptions", "recon.investigation", "report.validation"}
    for m in files:
        assert problems(m) == [], m.id


@pytest.mark.parametrize("gate", ["validate", "review", "record"])
def test_a_gate_cannot_be_dropped(gate):
    steps = [s for s in _variance()["steps"] if s != gate]
    assert f"`{gate}` is required" in _problems(steps=steps)


def test_gates_keep_their_order():
    out = order_problems(["load", "group", "reason", "draft", "review", "validate", "record"],
                         ["review"])
    assert "gates must run in the order validate → review → record" in out


def test_a_step_before_its_inputs_is_refused():
    out = order_problems(["load", "reason", "group", "draft", "validate", "review", "record"],
                         ["review"])
    assert "`reason` needs groups, produced by no earlier step" in out


def test_the_run_must_pause_for_people():
    assert "the run must pause before `review`" in _problems(pause_before=[])


def test_a_tool_that_was_never_onboarded_is_refused():
    reasoning = {**_variance()["reasoning"], "tools": ["crm.accounts"]}
    assert "tool `crm.accounts` is not an onboarded connector tool" in _problems(reasoning=reasoning)


def test_an_unsafe_expression_is_refused_at_validation():
    items = {**_variance()["items"], "in_scope": "__import__('os').system('x')"}
    out = _problems(items=items)
    assert any(p.startswith("items.in_scope:") for p in out)


def test_unknown_step():
    assert "unknown step `post_to_ledger`" in order_problems(["post_to_ledger"], ["review"])


def test_rule_expressions():
    env = {"account": "7100", "total": -60000.0, "count": 2, "policy": {"materiality": 50000}}
    assert rules.evaluate("startswith(account, '71') and abs(total) >= policy.materiality", env)
    assert rules.evaluate("account in ['6100', '7100']", env)
    assert not rules.evaluate("count == 1", env)
    assert rules.render("net {total} on {account}", env) == "net -60,000.00 on 7100"


@pytest.mark.parametrize("src", ["os.system('x')", "account.upper()", "open('f')",
                                 "[x for x in y]", "lambda: 1"])
def test_rule_expressions_refuse_anything_else(src):
    with pytest.raises(rules.ExpressionError):
        rules.compile_expr(src)
