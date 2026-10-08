"""LLM connectivity: one port, adapters chosen by AOF_LLM_ADAPTER.

  none   no model; anything the rules cannot settle escalates to a person
  stub   deterministic stand-in: reads evidence through the tools it is
         given and writes a comment citing only figures those tools returned
  agent_sdk  the Claude Agent SDK (agent_one_finance/llm_agent_sdk.py) — the office path
  "module:attr"  your office LLM connector: an object (or zero-argument
         factory) with `name` and `async reason(request, tools)`

The model never sees a connector directly. `tools` is a ToolInvoker bound to
the case: every call it makes goes through the MCP gateway, which checks the
tool is allowed for the capability, enforces the caller's data scope, and
writes a aof_tool_call row — so whatever the model cites can be validated.
Guards and validation run after, in code; the model's answer is a proposal.
"""

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol

from agent_one_finance import plugins
from agent_one_finance.config import settings


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
    # What people added at tollgates before the model was asked (e.g. the desk's
    # explanation of a break): context, not instructions, and never figures it may cite.
    notes: list[str] = field(default_factory=list)
    previous_finding: dict | None = None
    # A playbook's verdicts the model may propose (e.g. POST, DO_NOT_POST, ESCALATE).
    verdicts: list[str] | None = None
    # Subagents the model may hand work to: [{name, description, instructions, tools}]
    specialists: list[dict] = field(default_factory=list)
    # The parts the answer is returned in: [{id, label, hint, required}]; empty = one comment.
    sections: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ReasonResult:
    status: Literal["proposed", "escalated"]
    comment: str = ""
    reason: str | None = None              # why escalated
    model: str | None = None
    usage: dict = field(default_factory=dict)  # tokens, cost — for tracing
    verdict: str | None = None             # when the request offered verdicts
    sections: dict = field(default_factory=dict)   # section id -> text, when the request named sections


@dataclass(frozen=True)
class SessionRequest:
    """One skill session (the `agent` step): the model gets the case key, the
    skill and the allowed tools, finds the data itself, and returns one result
    per item it investigated (e.g. per break), or none and a summary."""
    capability_id: str
    case_id: str
    case_key: dict
    skill: str
    allowed_tools: list[str]
    id_field: str              # what identifies a result, e.g. instrument
    item_label: str            # e.g. Break
    amount_field: str | None = None
    result_fields: list[str] = field(default_factory=list)   # fields each result carries
    verdicts: list[str] = field(default_factory=list)        # the verdicts it may give
    sections: list[dict] = field(default_factory=list)       # each result's answer, in parts
    specialists: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    max_turns: int | None = None


@dataclass(frozen=True)
class SessionResult:
    # [{id, status: proposed|escalated, comment, reason?, verdict?, sections?: {id: text},
    #   fields?: {name: value}}]
    results: list[dict]
    summary: str = ""
    model: str | None = None
    usage: dict = field(default_factory=dict)
    # The conversation, turn by turn: [{turn, role: user|model|tool, kind: prompt|text|tool_call|tool_result|answer,
    #   text?, tool?, input?, rows?, error?}] — what the model said, which tools it called with what, and what came back.
    transcript: list[dict] = field(default_factory=list)


async def run_session(adapter, request: SessionRequest, tools: "ToolInvoker") -> SessionResult:
    """The adapter's own session when it has one (`investigate`); otherwise its
    `reason` over the whole case as one group, so any office adapter works."""
    if hasattr(adapter, "investigate"):
        return await adapter.investigate(request, tools)
    res = await adapter.reason(ReasonRequest(
        capability_id=request.capability_id, case_id=request.case_id, case_key=request.case_key,
        skill=request.skill, group={"group_id": "all", "label": "Whole case", "group_key": {},
                                    "items": [], "priors": []},
        allowed_tools=request.allowed_tools, output="verdict" if request.verdicts else "commentary",
        notes=request.notes, verdicts=request.verdicts or None, specialists=request.specialists,
        sections=request.sections), tools)
    return SessionResult(results=[], summary=res.comment, model=res.model, usage=res.usage, transcript=[
        {"turn": 1, "role": "user", "kind": "prompt", "text": "The whole case as one group (the adapter has no session)."},
        {"turn": 1, "role": "model", "kind": "answer", "text": res.comment}]) if (
        res.status == "proposed" and not res.verdict and not res.sections) else SessionResult(
        results=[{"id": "all", "status": res.status, "comment": res.comment, "reason": res.reason,
                  "verdict": res.verdict, "sections": res.sections}], model=res.model, usage=res.usage)


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
class ExtractRequest:
    """Fields to read from a document's text (an `extract` step). The answer
    for each field is {value, quote, confidence}; the quote must be the
    document's own words — the step checks it is, and sends anything else to a person."""
    case_id: str
    text: str
    fields: list[dict]         # [{name, hint, required}]


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
        from agent_one_finance.gateway import tool_schema

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
        context = [n for n in request.notes if n.startswith("context · ")]
        notes = [n for n in request.notes if not n.startswith("context · ")]
        if notes:
            comment += f" Took into account {len(notes)} note(s) from the tollgate."
        if context:
            comment += " Read " + ", ".join(n[10:].split(":", 1)[0] for n in context) + "."
        sections = {s["id"]: _stub_section(s, request, comment, seen, prior) for s in request.sections}
        return ReasonResult(status="proposed", comment=comment, model="stub", sections=sections)


    async def investigate(self, request: "SessionRequest", tools) -> "SessionResult":
        """Reads every allowed tool it can fill from the case key; the first
        whose rows carry the id field gives one result per row. It cannot judge,
        so it gives the first verdict offered and cites only the row's figures."""
        from agent_one_finance.gateway import tool_schema

        read, rows = [], []
        transcript = [{"turn": 1, "role": "user", "kind": "prompt",
                       "text": f"Investigate each {request.item_label.lower()} for {request.case_key}."}]
        for tool in request.allowed_tools:
            if not set((await tool_schema(tool)).get("required", [])) <= set(request.case_key):
                continue
            turn = len(transcript) // 2 + 1
            transcript.append({"turn": turn, "role": "model", "kind": "tool_call", "tool": tool,
                               "input": dict(request.case_key)})
            got = (await tools(tool, dict(request.case_key))).get("rows", []) or []
            transcript.append({"turn": turn, "role": "tool", "kind": "tool_result", "tool": tool, "rows": len(got)})
            read.append(f"{len(got)} rows from {tool}")
            if not rows and any(isinstance(r, dict) and request.id_field in r for r in got):
                rows = [r for r in got if isinstance(r, dict) and request.id_field in r]
        seen = ", ".join(read) or "no tool evidence"
        results = []
        for r in rows:
            rid = str(r[request.id_field])
            amount = r.get(request.amount_field) if request.amount_field else None
            comment = f"{rid}: " + (f"{request.amount_field} {_fmt(_num(amount))}; " if amount is not None else "") \
                + f"reviewed {seen}."
            fake = ReasonRequest(capability_id=request.capability_id, case_id=request.case_id,
                                 case_key=request.case_key, skill="", group={}, allowed_tools=[], output="")
            results.append({
                "id": rid, "status": "proposed", "comment": comment,
                "verdict": request.verdicts[0] if request.verdicts else None,
                "sections": {sp["id"]: _stub_section(sp, fake, comment, seen, None) for sp in request.sections},
                "fields": {f: r.get(f) for f in request.result_fields if f in r}})
        summary = f"{len(results)} {request.item_label.lower()}(s) investigated; reviewed {seen}."
        transcript.append({"turn": len(transcript) // 2 + 1, "role": "model", "kind": "answer",
                           "text": f"{summary} {len(results)} result(s) returned."})
        return SessionResult(results=results, summary=summary, model="stub", transcript=transcript)

    async def extract(self, request: "ExtractRequest") -> dict:
        """The stub reads `name: value` lines only (a real model reads prose)."""
        out = {}
        for f in request.fields:
            label = f.get("hint") or f["name"].replace("_", " ")
            m = re.search(rf"(?im)^\s*{re.escape(label)}\s*[:=]\s*(.+?)\s*$", request.text)
            if m:
                out[f["name"]] = {"value": m.group(1), "quote": m.group(0).strip(), "confidence": 0.8}
        return out

    async def ask(self, request, tools):
        from agent_one_finance.gateway import tool_schema

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


def _stub_section(spec: dict, request: "ReasonRequest", comment: str, seen: str, prior: str | None) -> str:
    """A section the stub can fill without inventing anything: the comment for
    the conclusion, what it read for the evidence, and plain "not established"
    where only a real investigation could say (so a reviewer sees the gap)."""
    sid, label = spec["id"], spec["label"].lower()
    if any(w in sid or w in label for w in ("cause", "conclusion", "driver", "explanation", "summary")):
        return comment
    if any(w in sid or w in label for w in ("evidence", "checks", "tests", "sources")):
        return f"Reviewed {seen}."
    if any(w in sid or w in label for w in ("hypothes", "alternative")):
        return f"Similar to a prior approved explanation: \"{prior}\"" if prior else "None beyond the conclusion."
    if "not" in sid and "perform" in sid or "not performed" in label or "could not" in label:
        return "None: every test with evidence was run; tests without evidence are listed as not run."
    return "Not established from the evidence read; for the reviewer."


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
            from agent_one_finance.llm_agent_sdk import ClaudeAgentSdkAdapter  # optional dependency
            _adapter = ClaudeAgentSdkAdapter()
        else:
            obj = plugins.load(name)
            # A class or factory is called once; a ready instance is used as is.
            _adapter = obj if hasattr(obj, "reason") and not isinstance(obj, type) else obj()
    return _adapter
