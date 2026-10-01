"""The MCP server the agent harness calls during one L4 agent session.

Streamable HTTP, stateless, JSON responses. Every request carries the agent
session's bearer token; `AgentTokenAuth` resolves it to that session's
AgentContext before the SDK sees the request, so an unknown, missing or dead
token never reaches a tool. Each tool call gets a fresh database session and
goes through `audited`, so every call is one source_call row.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Annotated, Any
from urllib.parse import urlparse

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from fobo.db.base import SessionFactory
from fobo.mcp_server import tools
from fobo.mcp_server.audit import audited
from fobo.mcp_server.context import AgentContext, context_for_token
from fobo.mcp_server.tools import ROWS_KEY, ToolInputError

MCP_PATH = "/mcp"
UNAUTHORISED = {"error": "invalid or expired agent session token"}
LOCAL_HOSTS = ("localhost", "127.0.0.1")

# The context of the token on the request being served. Set by AgentTokenAuth
# only after the token resolved, so a tool that finds it empty was reached
# some other way and must refuse.
_agent_context: ContextVar[AgentContext | None] = ContextVar("fobo_agent_context", default=None)

Result = dict[str, Any]
BreakId = Annotated[str, Field(description="A break id from this session, e.g. B-001")]
TestId = Annotated[str, Field(description="A playbook test id, e.g. FO-6")]


class AgentTokenAuth:
    """401 unless the bearer token belongs to a starting or running agent session."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ctx = await _resolve(_bearer_token(Headers(scope=scope)))
        if ctx is None:
            await JSONResponse(UNAUTHORISED, status_code=401)(scope, receive, send)
            return
        reset = _agent_context.set(ctx)
        try:
            await self.app(scope, receive, send)
        finally:
            _agent_context.reset(reset)


def _bearer_token(headers: Headers) -> str | None:
    scheme, _, token = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def _resolve(token: str | None) -> AgentContext | None:
    if token is None:
        return None
    async with SessionFactory() as session:
        return await context_for_token(session, token)


async def _run(
    tool_name: str,
    params: dict[str, Any],
    call: Callable[..., Awaitable[dict]],
) -> Result:
    """One audited tool call; a ToolInputError becomes the agent's tool error."""
    ctx = _agent_context.get()
    if ctx is None:
        raise ToolError(UNAUTHORISED["error"])
    async with SessionFactory() as session:
        try:
            return await audited(
                session, ctx, tool_name, params,
                lambda: call(session, ctx, **params),
                rows_key=ROWS_KEY.get(tool_name),
            )
        except ToolInputError as exc:
            raise ToolError(str(exc)) from None


async def fobo_list_tests(
    side: Annotated[str, Field(description="Which side's tests: FO or BO")],
) -> Result:
    return await _run("fobo_list_tests", {"side": side}, tools.fobo_list_tests)


async def fobo_evidence_required(test_id: TestId) -> Result:
    return await _run("fobo_evidence_required", {"test_id": test_id}, tools.fobo_evidence_required)


async def fobo_required_on_fail(test_id: TestId) -> Result:
    return await _run("fobo_required_on_fail", {"test_id": test_id}, tools.fobo_required_on_fail)


async def fobo_unset_policies(
    params: Annotated[
        list[str] | None,
        Field(description="Policy parameter names to check; omit for the workflow's verdict policies"),
    ] = None,
) -> Result:
    return await _run("fobo_unset_policies", {"params": params}, tools.fobo_unset_policies)


async def fobo_book_context(
    book_ref: Annotated[str, Field(description="A book name or id, e.g. PRIME-MB-01")],
) -> Result:
    return await _run("fobo_book_context", {"book_ref": book_ref}, tools.fobo_book_context)


async def fobo_similar_breaks(break_id: BreakId) -> Result:
    return await _run("fobo_similar_breaks", {"break_id": break_id}, tools.fobo_similar_breaks)


async def fobo_list_breaks(
    pattern_code: Annotated[str | None, Field(description="Only breaks with this pattern code")] = None,
    page: Annotated[int, Field(description="Page number, from 1")] = 1,
    page_size: Annotated[int, Field(description="Breaks per page, 1 to 100")] = 50,
) -> Result:
    return await _run(
        "fobo_list_breaks",
        {"pattern_code": pattern_code, "page": page, "page_size": page_size},
        tools.fobo_list_breaks,
    )


async def fobo_break_detail(break_id: BreakId) -> Result:
    return await _run("fobo_break_detail", {"break_id": break_id}, tools.fobo_break_detail)


TOOLS: tuple[tuple[Callable[..., Awaitable[dict]], str], ...] = (
    (fobo_list_tests,
     "List the playbook tests for one side (FO or BO) with their ids and names."),
    (fobo_evidence_required,
     "List the evidence types a playbook test needs before its result can be trusted."),
    (fobo_required_on_fail,
     "List the playbook tests that must also run when the given test fails."),
    (fobo_unset_policies,
     "Report which verdict policy parameters have no value set, so a verdict cannot rely on them."),
    (fobo_book_context,
     "Resolve a book reference to its book id, desk, legal entity and upward lineage."),
    (fobo_similar_breaks,
     "List prior resolved breaks on the same book and line as one of this session's breaks."),
    (fobo_list_breaks,
     "List this session's unsettled breaks in compact form, paged, with the total count."),
    (fobo_break_detail,
     "Return the full evidence record for one of this session's breaks."),
)


def build_mcp_server() -> MCPServer:
    server = MCPServer(name="fobo", instructions="Read-only reconciliation evidence for one L4 agent session.")
    for fn, description in TOOLS:
        server.add_tool(fn, name=fn.__name__, description=description)
    return server


def _transport_security(mcp_url: str) -> TransportSecuritySettings:
    """Accept the host the harness was told to call, plus the local ones."""
    hosts = dict.fromkeys(h for h in (urlparse(mcp_url).hostname, *LOCAL_HOSTS) if h)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[p for h in hosts for p in (h, f"{h}:*")],
        allowed_origins=[
            p for h in hosts for scheme in ("http", "https")
            for p in (f"{scheme}://{h}", f"{scheme}://{h}:*")
        ],
    )


def mcp_http_app(server: MCPServer, mcp_url: str) -> ASGIApp:
    """The authenticated ASGI app serving `server` at exactly MCP_PATH.

    The caller must run `server.session_manager.run()` for its lifetime.
    """
    app = server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(mcp_url),
    )
    return AgentTokenAuth(app)
