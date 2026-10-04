"""LLM connectivity: one port, adapters chosen by HELIX_LLM_ADAPTER.

  none   no model; anything the rules cannot settle escalates to a person
  stub   deterministic stand-in: reads evidence through the tools it is
         given and writes a comment citing only figures those tools returned
  agent_sdk  the Claude Agent SDK (helix/llm_agent_sdk.py) — the office path
  "module:attr"  your office LLM connector: an object (or zero-argument
         factory) with `name` and `async reason(request, tools)`

The model never sees a connector directly. `tools` is a ToolInvoker bound to
the case: every call it makes goes through the MCP gateway, which checks the
tool is allowed for the capability, enforces the caller's data scope, and
writes a helix_tool_call row — so whatever the model cites can be validated.
Guards and validation run after, in code; the model's answer is a proposal.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from helix import plugins
from helix.config import settings


@dataclass(frozen=True)
class ReasonRequest:
    capability_id: str
    case_id: str
    case_key: dict
    skill: str                 # the capability's instructions to the model
    group: dict                # {group_id, label, group_key, items: [...], priors: [...]}
    allowed_tools: list[str]   # "connector.tool" names the model may call
    output: str                # verdict | commentary | classification
    # A reviewer sent the group back: what they asked, and what was proposed before.
    reviewer_note: str | None = None
    previous_finding: dict | None = None
    # A playbook's verdicts the model may propose (e.g. POST, DO_NOT_POST, ESCALATE).
    verdicts: list[str] | None = None


@dataclass(frozen=True)
class ReasonResult:
    status: Literal["proposed", "escalated"]
    comment: str = ""
    reason: str | None = None              # why escalated
    model: str | None = None
    usage: dict = field(default_factory=dict)  # tokens, cost — for tracing
    verdict: str | None = None             # when the request offered verdicts


@dataclass(frozen=True)
class AskRequest:
    """A question about one case, answered from its data and tools."""
    capability_id: str
    case_id: str
    case_key: dict
    skill: str
    question: str
    context: dict              # {subject, status, headline, groups: [...], items: [...]}
    history: list[dict]        # earlier turns: [{role, text}]
    allowed_tools: list[str]


@dataclass(frozen=True)
class AskResult:
    answer: str
    model: str | None = None
    usage: dict = field(default_factory=dict)


class ToolInvoker(Protocol):
    async def __call__(self, tool: str, arguments: dict) -> dict: ...


class LlmAdapter(Protocol):
    name: str

    async def reason(self, request: ReasonRequest, tools: ToolInvoker) -> ReasonResult: ...

    async def ask(self, request: AskRequest, tools: ToolInvoker) -> AskResult: ...


class NoLlm:
    name = "none"

    async def reason(self, request, tools):
        return ReasonResult(status="escalated", reason="NO_REASONER")

    async def ask(self, request, tools):
        return AskResult(answer=_from_case(request) + " (No model is configured; this is the case's own record.)")


def _mentioned(request: "AskRequest") -> list[dict]:
    """Groups the question names: by label, key value or one of its item ids."""
    q = request.question.lower()
    out = []
    for g in request.context.get("groups", []):
        f = g.get("finding") or {}
        words = [g["label"], f.get("category_name"), *map(str, g["group_key"].values()),
                 *map(str, g.get("items", []))]
        # whole words only: "H" (a category) must not match the h in "why"
        if any(w and re.search(rf"(?<!\w){re.escape(str(w).lower())}(?!\w)", q) for w in words):
            out.append(g)
    return out


def _from_case(request: "AskRequest") -> str:
    """An answer built only from the case's record — no model involved."""
    ctx = request.context
    groups = _mentioned(request) or ctx.get("groups", [])
    lines = [ctx.get("headline") or f"{ctx.get('subject')}: {ctx.get('status')}."]
    for g in groups[:10]:
        f = g.get("finding") or {}
        verdict = f" Verdict {f['verdict']}." if f.get("verdict") else ""
        owner = f" Owner: {f['escalate_to']}." if f.get("escalate_to") else ""
        decided = (f" Decided: {g['decision']['action']} by {g['decision']['decided_by']}."
                   if g.get("decision") else " Not decided yet.")
        lines.append(f"{g['label']}: {f.get('status', 'pending')}.{verdict}{owner} "
                     f"{f.get('comment') or f.get('reason') or ''}".rstrip() + decided)
    return " ".join(lines)


class StubLlm:
    """Calls each allowed tool it can fill from the case and group keys once,
    then comments using the group's own figures. Deterministic, so tests and demos are stable."""

    name = "stub"

    async def reason(self, request, tools):
        from helix.gateway import tool_schema

        evidence = []
        args = {**request.case_key, **request.group["group_key"]}
        for tool in request.allowed_tools:
            # A model chooses its own arguments; the stub can only pass the keys
            # it has, so it skips tools that need more (e.g. a document name).
            if not set((await tool_schema(tool)).get("required", [])) <= set(args):
                continue
            result = await tools(tool, args)
            evidence.append((tool, result.get("rows", []) or []))
        total = sum(_num(i.get("amount")) for i in request.group["items"])
        seen = ", ".join(f"{len(rows)} rows from {t}" for t, rows in evidence) or "no tool evidence"
        prior = request.group["priors"][0]["comment"] if request.group["priors"] else None
        comment = f"{request.group['label']}: net {_fmt(total)} across {len(request.group['items'])} item(s); reviewed {seen}."
        largest = [h for h in (_highlight(t, rows) for t, rows in evidence) if h]
        if largest:
            comment += " Largest: " + "; ".join(largest) + "."
        if prior:
            comment += f" Similar to a prior approved explanation: \"{prior}\""
        if request.reviewer_note:
            comment += f" Re-checked as the reviewer asked: \"{request.reviewer_note}\"."
        return ReasonResult(status="proposed", comment=comment, model="stub")


    async def ask(self, request, tools):
        from helix.gateway import tool_schema

        evidence = []
        for g in _mentioned(request)[:3]:
            args = {**request.case_key, **g["group_key"]}
            for tool in request.allowed_tools:
                if set((await tool_schema(tool)).get("required", [])) <= set(args):
                    result = await tools(tool, args)
                    evidence.append(f"{len(result.get('rows', []))} rows from {tool} for {g['label']}")
        answer = _from_case(request)
        if evidence:
            answer += " I also looked at " + "; ".join(evidence) + "."
        return AskResult(answer=answer, model="stub")


def _highlight(tool: str, rows: list[dict]) -> str | None:
    """The biggest row a tool returned, in words: what it is and its amount —
    so a stub comment reads like an explanation and still cites only tool figures."""
    def amount(r: dict) -> tuple[str, float] | None:
        for k, v in r.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ("quantity", "version"):
                return k, float(v)
        return None
    scored = [(r, a) for r in rows if isinstance(r, dict) and (a := amount(r))]
    if not scored:
        return None
    row, (field, value) = max(scored, key=lambda ra: abs(ra[1][1]))
    words = [str(v) for k, v in row.items() if isinstance(v, str) and k not in ("book", "entity", "period")][:2]
    return f"{' · '.join(words) or tool} ({field} {_fmt(value)}, {tool})"


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


_adapter: LlmAdapter | None = None


def llm() -> LlmAdapter:
    global _adapter
    if _adapter is None:
        name = settings().llm_adapter
        if name == "none":
            _adapter = NoLlm()
        elif name == "stub":
            _adapter = StubLlm()
        elif name == "agent_sdk":
            from helix.llm_agent_sdk import ClaudeAgentSdkAdapter  # optional dependency
            _adapter = ClaudeAgentSdkAdapter()
        else:
            obj = plugins.load(name)
            # A class or factory is called once; a ready instance is used as is.
            _adapter = obj if hasattr(obj, "reason") and not isinstance(obj, type) else obj()
    return _adapter
