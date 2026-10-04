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


@dataclass(frozen=True)
class ReasonResult:
    status: Literal["proposed", "escalated"]
    comment: str = ""
    reason: str | None = None              # why escalated
    model: str | None = None
    usage: dict = field(default_factory=dict)  # tokens, cost — for tracing


class ToolInvoker(Protocol):
    async def __call__(self, tool: str, arguments: dict) -> dict: ...


class LlmAdapter(Protocol):
    name: str

    async def reason(self, request: ReasonRequest, tools: ToolInvoker) -> ReasonResult: ...


class NoLlm:
    name = "none"

    async def reason(self, request, tools):
        return ReasonResult(status="escalated", reason="NO_REASONER")


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
            evidence.append((tool, len(result.get("rows", []))))
        total = sum(_num(i.get("amount")) for i in request.group["items"])
        seen = ", ".join(f"{n} rows from {t}" for t, n in evidence) or "no tool evidence"
        prior = request.group["priors"][0]["comment"] if request.group["priors"] else None
        comment = f"{request.group['label']}: net {_fmt(total)} across {len(request.group['items'])} item(s); reviewed {seen}."
        if prior:
            comment += f" Similar to a prior approved explanation: \"{prior}\""
        return ReasonResult(status="proposed", comment=comment, model="stub")


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
