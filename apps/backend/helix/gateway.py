"""The MCP gateway: the only path from Helix (steps and the model) to a connector.

Connectors are what the Helix team onboards: config/helix/connectors.yaml
lists each MCP server, how to reach it, and which of its tools are
allow-listed, with the argument that carries the data scope. Per call:

  1. the tool is registered and allow-listed for this capability's manifest
  2. the caller is entitled to the data-scope value in the arguments
  3. the call goes to the connector over MCP (in-process or streamable HTTP)
  4. a helix_tool_call row is written — allowed or refused — and a span emitted

Refusals raise ToolDenied; the row is written first, so an audit of who
tried to read what is complete either way.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

import yaml
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from pydantic import BaseModel, ConfigDict, Field, model_validator

from helix import plugins
from helix.config import settings
from helix.db import get_session
from helix.entitlement import Caller
from helix.governance import Protector
from helix.models import ToolCall
from helix.observability import TOOL, set_output, span


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeRule(Strict):
    arg: str   # the tool argument holding the scoped value, e.g. "entity"
    key: str   # the entitlement data-scope it is checked against


class ToolSpec(Strict):
    description: str = ""
    scope: ScopeRule | None = None
    # write tools change a bank system: never offered to the model, callable
    # only by the `publish` step after a second person approved it
    access: Literal["read", "write"] = "read"


class ConnectorSpec(Strict):
    name: str
    transport: Literal["inproc", "http"]
    target: str | None = None         # inproc: "module:factory" returning an MCPServer
    url: str | None = None            # http: the connector's MCP endpoint
    headers_env: dict[str, str] = Field(default_factory=dict)  # header -> env var holding its value
    classification: str = "internal"
    tools: dict[str, ToolSpec]

    @model_validator(mode="after")
    def _reachable(self):
        if self.transport == "inproc" and not self.target:
            raise ValueError("an inproc connector needs `target`")
        if self.transport == "http" and not self.url:
            raise ValueError("an http connector needs `url`")
        return self


class ConnectorRegistry(Strict):
    connectors: dict[str, ConnectorSpec]

    def tool(self, qualified: str) -> tuple[str, str, ToolSpec] | None:
        connector_id, _, tool = qualified.partition(".")
        spec = self.connectors.get(connector_id)
        if spec is None or tool not in spec.tools:
            return None
        return connector_id, tool, spec.tools[tool]

    def all_tools(self) -> list[str]:
        return [f"{c}.{t}" for c, s in self.connectors.items() for t in s.tools]


@lru_cache
def registry() -> ConnectorRegistry:
    path = settings().config_dir / "connectors.yaml"
    return ConnectorRegistry.model_validate(yaml.safe_load(path.read_text()))


class ToolDenied(PermissionError):
    pass


class ToolFailed(RuntimeError):
    pass


@dataclass
class CallContext:
    capability_id: str
    caller: Caller
    allowed_tools: frozenset[str]
    case_id: str | None = None
    requested_by: str = "step"
    calls: list[str] = field(default_factory=list)  # call ids made in this context
    # set only by the publish step, from the recorded publish approval
    write_approved_by: str | None = None
    # Data protection for this case (helix/governance.py). Built from the
    # allowed tools when not given, so every call is protected by default.
    protector: Protector | None = None

    def __post_init__(self):
        if self.protector is None:
            self.protector = Protector.for_tools(self.allowed_tools, self.case_id or "")


@lru_cache
def _inproc_server(target: str):
    return plugins.load(target)()


def _client(spec: ConnectorSpec) -> Client:
    if spec.transport == "inproc":
        return Client(_inproc_server(spec.target))
    headers = {h: os.environ.get(env, "") for h, env in spec.headers_env.items()}
    return Client(streamable_http_client(spec.url, http_client=create_mcp_http_client(headers=headers)))


def _result_of(res) -> dict:
    """Structured content when the connector sends it; else JSON in its text.
    Connectors differ, so both are accepted; anything else is kept as text."""
    if res.structured_content is not None:
        return res.structured_content
    text = "".join(getattr(c, "text", "") for c in res.content)
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"rows": parsed} if isinstance(parsed, list) else {"value": parsed}


async def _record(**row) -> None:
    async with get_session() as s:
        s.add(ToolCall(**row))
        await s.commit()


async def call(ctx: CallContext, qualified_tool: str, arguments: dict) -> dict:
    """Call a connector tool for a step or the model.

    The model works with protected data: its arguments may carry pseudonym
    tokens (revealed here, before the scope check and the connector), and the
    result it gets back is masked and re-tokenized. Steps get real values.
    The audit row keeps real values minus masked fields; the span carries the
    model's view only.
    """
    call_id = uuid.uuid4().hex
    ctx.calls.append(call_id)
    connector_id = qualified_tool.partition(".")[0]
    guard = ctx.protector
    for_model = ctx.requested_by == "llm"
    if for_model:
        arguments = guard.reveal(arguments)
    base = dict(
        call_id=call_id, case_id=ctx.case_id, capability_id=ctx.capability_id,
        connector_id=connector_id, tool=qualified_tool, requested_by=ctx.requested_by,
        caller=ctx.caller.user_id, arguments=guard.protect(arguments, pseudonymize=False),
    )
    with span("mcp.call", kind=TOOL, input=guard.protect(arguments), tool=qualified_tool,
              connector_id=connector_id,
              case_id=ctx.case_id, capability_id=ctx.capability_id,
              requested_by=ctx.requested_by, user=ctx.caller.user_id) as sp:
        found = registry().tool(qualified_tool)
        denied = None
        if found is None:
            denied = f"{qualified_tool} is not an onboarded connector tool"
        elif qualified_tool not in ctx.allowed_tools:
            denied = f"{qualified_tool} is not allowed for capability {ctx.capability_id}"
        elif found[2].access == "write" and (for_model or ctx.requested_by != "publish"
                                              or not ctx.write_approved_by):
            denied = (f"{qualified_tool} writes to a bank system: only the publish step may "
                      "call it, after a second person approves")
        elif found[2].scope is not None:
            rule = found[2].scope
            value = arguments.get(rule.arg)
            if value is None:
                denied = f"{qualified_tool} needs `{rule.arg}` (its data scope)"
            elif not ctx.caller.may_see(rule.key, value):
                denied = f"{ctx.caller.user_id} is not entitled to {rule.key}={value}"
        if denied:
            sp.set_attribute("helix.allowed", False)
            await _record(**base, allowed=False, denied_reason=denied)
            raise ToolDenied(denied)

        connector_id, tool, _ = found
        spec = registry().connectors[connector_id]
        started = time.monotonic()
        error, result = None, None
        try:
            async with _client(spec) as client:
                res = await client.call_tool(tool, arguments)
            if res.is_error:
                error = " ".join(getattr(c, "text", "") for c in res.content) or "tool error"
            else:
                result = _result_of(res)
        except Exception as e:  # connector down, timeout, protocol error
            error = f"{type(e).__name__}: {e}"
        latency = int((time.monotonic() - started) * 1000)
        rows = result.get("rows") if isinstance(result, dict) else None
        row_count = len(rows) if isinstance(rows, list) else None
        sp.set_attribute("helix.allowed", True)
        sp.set_attribute("helix.latency_ms", latency)
        if row_count is not None:
            sp.set_attribute("helix.row_count", row_count)
        await _record(**base, allowed=True, row_count=row_count, error=error, latency_ms=latency,
                      result=guard.protect(result, pseudonymize=False) if result is not None else None)
        if result is not None:
            set_output(sp, guard.protect(result))
        if error:
            sp.set_attribute("helix.error", error)
            raise ToolFailed(f"{qualified_tool}: {error}")
        return guard.protect(result) if for_model else result


def invoker(ctx: CallContext):
    """A ToolInvoker for the LLM adapter: same gateway, marked as the model's call."""
    async def invoke(tool: str, arguments: dict) -> dict:
        model_ctx = CallContext(
            capability_id=ctx.capability_id, caller=ctx.caller,
            allowed_tools=ctx.allowed_tools, case_id=ctx.case_id,
            requested_by="llm", calls=ctx.calls, protector=ctx.protector,
        )
        return await call(model_ctx, tool, arguments)
    return invoke


_schemas: dict[str, dict] = {}


async def tool_schema(qualified_tool: str) -> dict:
    """The connector tool's input JSON schema, as its MCP server lists it.

    Lets an LLM adapter offer the tool with the right argument names. Read
    once per process; a connector that cannot be reached yields an open
    object schema rather than failing the run.
    """
    if qualified_tool in _schemas:
        return _schemas[qualified_tool]
    found = registry().tool(qualified_tool)
    if found is None:
        raise ToolDenied(f"{qualified_tool} is not an onboarded connector tool")
    connector_id, tool, spec = found
    schema: dict = {"type": "object", "properties": {}}
    try:
        async with _client(registry().connectors[connector_id]) as client:
            listed = await client.list_tools()
        for t in listed.tools:
            if t.name == tool:
                schema = dict(t.input_schema or schema)
                break
    except Exception:  # unreachable connector: degrade, the call itself will fail loudly
        return schema
    _schemas[qualified_tool] = schema
    return schema
