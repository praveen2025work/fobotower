"""Expressions for manifests: `in_scope`, rule `when`, comment templates.

A capability is configuration, so its conditions are text. They are parsed
into a restricted AST — comparisons, arithmetic, and/or/not, `in`, names,
`policy.x` lookups, and a few functions — and evaluated without `eval`.
Anything else (imports, attribute access on objects, calls to other
functions) is refused when the manifest is validated, not at run time.

    abs(amount) >= policy.materiality
    account in ['7100', '7110'] and total < 0
    startswith(account, '61')
"""

import ast
import operator
import re
from typing import Any

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Mod: operator.mod}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
        ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}
_FUNCS = {
    "abs": abs, "min": min, "max": max, "len": len, "round": round,
    "float": float, "str": str,
    "startswith": lambda s, p: str(s).startswith(str(p)),
    "contains": lambda s, p: str(p) in str(s),
    # values present on one side only, e.g. components or adjustments
    "symdiff": lambda a, b: sorted(set(a or []) ^ set(b or [])),
    "is_null": lambda v: v is None,
}


class ExpressionError(ValueError):
    pass


def _check(node: ast.AST) -> None:
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
               ast.USub, ast.BinOp, ast.Compare, ast.Name, ast.Load, ast.Constant,
               ast.List, ast.Tuple, ast.Attribute, ast.Call, *_BIN, *_CMP)
    for n in ast.walk(node):
        if not isinstance(n, allowed):
            raise ExpressionError(f"`{type(n).__name__}` is not allowed")
        if isinstance(n, ast.Attribute) and not (
            isinstance(n.value, ast.Name) and n.value.id == "policy"
        ):
            raise ExpressionError("only `policy.<name>` lookups are allowed")
        if isinstance(n, ast.Call) and not (
            isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords
        ):
            raise ExpressionError(f"allowed functions: {', '.join(sorted(_FUNCS))}")


def compile_expr(source: str) -> ast.Expression:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as e:
        raise ExpressionError(f"cannot parse {source!r}: {e.msg}") from e
    _check(tree)
    return tree


def _eval(n: ast.AST, env: dict) -> Any:
    match n:
        case ast.Expression(body=b):
            return _eval(b, env)
        case ast.Constant(value=v):
            return v
        case ast.Name(id=name):
            if name not in env:
                raise ExpressionError(f"unknown name `{name}`")
            return env[name]
        case ast.Attribute(value=ast.Name(id="policy"), attr=attr):
            policy = env.get("policy", {})
            if attr not in policy:
                raise ExpressionError(f"unknown policy `{attr}`")
            return policy[attr]
        case ast.List(elts=e) | ast.Tuple(elts=e):
            return [_eval(x, env) for x in e]
        case ast.UnaryOp(op=ast.Not(), operand=o):
            return not _eval(o, env)
        case ast.UnaryOp(op=ast.USub(), operand=o):
            return -_eval(o, env)
        case ast.BoolOp(op=ast.And(), values=vs):
            return all(_eval(v, env) for v in vs)
        case ast.BoolOp(op=ast.Or(), values=vs):
            return any(_eval(v, env) for v in vs)
        case ast.BinOp(left=l, op=op, right=r):
            return _BIN[type(op)](_eval(l, env), _eval(r, env))
        case ast.Compare(left=l, ops=ops, comparators=cs):
            left = _eval(l, env)
            for op, c in zip(ops, cs):
                right = _eval(c, env)
                if not _CMP[type(op)](left, right):
                    return False
                left = right
            return True
        case ast.Call(func=ast.Name(id=fn), args=args):
            return _FUNCS[fn](*[_eval(a, env) for a in args])
    raise ExpressionError(f"cannot evaluate {ast.dump(n)}")


def evaluate(source: str, env: dict) -> Any:
    return _eval(compile_expr(source), env)


_FIELD = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render(template: str, env: dict) -> str:
    """`{name}` placeholders from env; numbers formatted as 1,234.56."""
    def sub(m):
        v = env.get(m.group(1), m.group(0))
        return f"{v:,.2f}" if isinstance(v, float) else str(v)
    return _FIELD.sub(sub, template)


def template_fields(template: str) -> list[str]:
    return _FIELD.findall(template)
