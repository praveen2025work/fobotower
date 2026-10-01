"""The MCP tools, as plain async functions over an AgentContext.

All read-only. Graph reads use the context's caller (entitlement predicate)
and business date (as-of), never anything the agent supplies. Asking for a
break outside the session is an error, not data. Results are JSON-safe so the
HTTP layer and the audit row can store them as they are.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from fobo.investigation.settings import settings
from fobo.knowledge_graph.errors import AmbiguousBook, UnresolvedBook
from fobo.knowledge_graph.ontology import OntologyRepository
from fobo.knowledge_graph.repository import GraphRepository
from fobo.mcp_server.context import AgentContext

SIDES = ("FO", "BO")
MAX_PAGE_SIZE = 100
LIST_FIELDS = ("break_id", "book", "pattern_code", "break_amount", "line_code")


class ToolInputError(ValueError):
    """The agent asked for something it may not have or that does not exist."""


def _session_break(ctx: AgentContext, break_id: str) -> dict:
    found = ctx.breaks.get(break_id)
    if found is None:
        raise ToolInputError(f"Break {break_id} is not one of this session's breaks")
    return found


async def fobo_list_tests(session: AsyncSession, ctx: AgentContext, *, side: str) -> dict:
    if side not in SIDES:
        raise ToolInputError(f"side must be one of {', '.join(SIDES)}")
    tests = await OntologyRepository(session).tests_for_side(side, ctx.business_date)
    return {"side": side, "tests": tests}


async def fobo_evidence_required(
    session: AsyncSession, ctx: AgentContext, *, test_id: str
) -> dict:
    evidence = await OntologyRepository(session).evidence_required(test_id, ctx.business_date)
    return {"test_id": test_id, "evidence": evidence}


async def fobo_required_on_fail(
    session: AsyncSession, ctx: AgentContext, *, test_id: str
) -> dict:
    tests = await OntologyRepository(session).required_on_fail(test_id, ctx.business_date)
    return {"test_id": test_id, "tests": tests}


async def fobo_unset_policies(
    session: AsyncSession, ctx: AgentContext, *, params: list[str] | None = None
) -> dict:
    wanted = list(params) if params is not None else list(settings().reason.verdict_policy_params)
    unset = await OntologyRepository(session).unset_policies(wanted, ctx.business_date)
    return {"params": wanted, "unset": unset}


async def fobo_book_context(session: AsyncSession, ctx: AgentContext, *, book_ref: str) -> dict:
    repo = GraphRepository(session)
    try:
        book_id = await repo.resolve_book(book_ref, ctx.business_date, ctx.caller)
    except UnresolvedBook:
        raise ToolInputError(f"No book matches {book_ref!r}") from None
    except AmbiguousBook:
        raise ToolInputError(f"More than one book matches {book_ref!r}") from None
    context = await repo.book_context(book_id, ctx.business_date, ctx.caller)
    lineage = await repo.lineage(
        book_id, "BELONGS_TO", settings().gather.lineage_max_depth,
        ctx.business_date, ctx.caller,
    )
    return {**context, "as_of": context["as_of"].isoformat(), "lineage": lineage}


async def fobo_similar_breaks(
    session: AsyncSession, ctx: AgentContext, *, break_id: str
) -> dict:
    evidence = _session_break(ctx, break_id)
    book_id = evidence.get("book_id")
    if not book_id:
        raise ToolInputError(f"Break {break_id} has no resolved book to look up")
    gather = settings().gather
    rows = await GraphRepository(session).similar_breaks(
        book_id, evidence["line_code"], ctx.business_date,
        gather.priors_lookback_days, ctx.caller, limit=gather.max_similar_breaks,
    )
    return {
        "break_id": break_id,
        "breaks": [{**r, "cob_date": r["cob_date"].isoformat()} for r in rows],
    }


async def fobo_list_breaks(
    session: AsyncSession,
    ctx: AgentContext,
    *,
    pattern_code: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    if page < 1:
        raise ToolInputError("page must be at least 1")
    if not 1 <= page_size <= MAX_PAGE_SIZE:
        raise ToolInputError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
    matching = sorted(
        (b for b in ctx.breaks.values()
         if pattern_code is None or b.get("pattern_code") == pattern_code),
        key=lambda b: b["break_id"],
    )
    start = (page - 1) * page_size
    return {
        "total": len(matching),
        "page": page,
        "page_size": page_size,
        "breaks": [{k: b.get(k) for k in LIST_FIELDS} for b in matching[start:start + page_size]],
    }


async def fobo_break_detail(session: AsyncSession, ctx: AgentContext, *, break_id: str) -> dict:
    return dict(_session_break(ctx, break_id))
