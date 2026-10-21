"""The Agent One Finance API: `uvicorn agent_one_finance.web.main:app --port 8300`.

Identity comes from one request header (AOF_IDENTITY_HEADER, set by the
SSO proxy in the office; the console's user switcher in development); roles
and data scopes come from the entitlement service, never from the request.
"""

import asyncio
from datetime import datetime
import hmac
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from agent_one_finance import asks, authoring, agents, tasks, chat, controls, devtools, evals, evidence, knowledge, notify, retention, review, runner, scheduler, views
from agent_one_finance import groups as team_groups
from agent_one_finance.config import settings
from agent_one_finance.entitlement import Caller, EntitlementError, StubEntitlement, entitlements
from agent_one_finance.gateway import registry
from agent_one_finance.llm import llm
from agent_one_finance.observability import setup_tracing
from agent_one_finance.workflow import catalogue, setup_checkpointer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_tracing()
    await setup_checkpointer()
    await agents.seed()
    await team_groups.seed()
    await knowledge.seed_reference()
    await runner.recover()          # finish runs a stopped server left behind
    loop = asyncio.create_task(scheduler.run_forever()) if settings().scheduler else None
    yield
    if loop:
        loop.cancel()
    await runner.drain()


app = FastAPI(title="Agent One Finance API", description="Governed AI for Finance: agents, tasks, review and audit.",
              version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings().console_origin], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def trusted_proxy(request: Request, call_next):
    """With AOF_TRUSTED_PROXY_SECRET set, only requests that came through the
    SSO proxy (which adds the secret) reach the API: the identity header can
    then not be set by anyone who can merely reach the server."""
    secret = settings().trusted_proxy_secret
    if secret and request.url.path.startswith("/api/"):
        sent = request.headers.get(settings().proxy_secret_header, "")
        if not hmac.compare_digest(sent.encode(), secret.encode()):
            return JSONResponse({"detail": "request did not come through the trusted proxy"},
                                status_code=401)
    return await call_next(request)


class PathPrefix:
    """AOF_PATH_PREFIX (for example /finance): /finance/api/... and /finance/health are served as
    /api/... and /health, for a load balancer that sends /finance/* to AOF without rewriting
    paths. Only the path changes, so every check below sees the same path either way."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        prefix = settings().path_prefix
        if prefix and scope["type"] in ("http", "websocket"):
            path = scope["path"]
            if path == prefix or path.startswith(prefix + "/"):
                scope = {**scope, "path": path[len(prefix):] or "/"}
        await self.app(scope, receive, send)


app.add_middleware(PathPrefix)   # added last, so it runs first


async def caller(request: Request) -> Caller:
    user_id = request.headers.get(settings().identity_header, "").strip()
    if not user_id:
        raise HTTPException(401, f"missing {settings().identity_header}")
    try:
        return await entitlements().get(user_id)
    except EntitlementError as e:
        raise HTTPException(403, str(e)) from e


def _errors(fn):
    """Map domain errors to HTTP the same way on every route."""
    @wraps(fn)
    async def wrapped(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e
        except LookupError as e:
            raise HTTPException(404, f"not found: {e}") from e
        except (agents.AgentError, team_groups.GroupError) as e:
            raise HTTPException(422, {"message": str(e), "problems": e.problems}) from e
        except tasks.TaskError as e:
            raise HTTPException(409, str(e)) from e
        except review.ReviewError as e:
            raise HTTPException(422, str(e)) from e
        except asks.AskError as e:
            raise HTTPException(422, str(e)) from e
    return wrapped


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/me")
async def me(c: Caller = Depends(caller)) -> dict:
    return {**c.as_dict(), "llm": llm().name, "is_admin": settings().admin_role in c.roles,
            "covering_for": [a.user_id for a in await review.covering_for(c)]}


@app.get("/api/me/delegations")
@_errors
async def my_delegations(c: Caller = Depends(caller)) -> dict:
    return await review.mine(c)


class DelegationIn(BaseModel):
    to_user: str = Field(min_length=1, max_length=64)
    until: datetime
    starts_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)


@app.post("/api/me/delegations", status_code=201)
@_errors
async def delegate(body: DelegationIn, c: Caller = Depends(caller)) -> dict:
    """While I am away, this colleague decides on my behalf — only on tasks
    whose agent allows it (review.allow_delegation), within my scope."""
    await entitlements().get(body.to_user)            # a real user
    return await review.delegate(c, body.to_user, body.until, body.reason, body.starts_at)


@app.delete("/api/me/delegations/{delegation_id}", status_code=204)
@_errors
async def end_delegation(delegation_id: str, c: Caller = Depends(caller)) -> Response:
    await review.revoke(c, delegation_id)
    return Response(status_code=204)


@app.get("/api/dev/users")
async def dev_users() -> list[dict]:
    """Fixture users, for the console's switcher. Empty when a real entitlement service is configured."""
    if settings().entitlement_url:
        return []
    return [{"user_id": u, **body} for u, body in StubEntitlement().users().items()]


@app.get("/api/overview")
async def overview(c: Caller = Depends(caller)) -> dict:
    return await views.overview(c)


@app.get("/api/operations")
async def operations(c: Caller = Depends(caller)) -> dict:
    """Run-the-bank view: platform health, connector probes, KPIs, fleet, incidents, tail."""
    return await views.operations(c)


@app.get("/api/inbox")
async def inbox(c: Caller = Depends(caller)) -> list[dict]:
    return await views.inbox(c)


@app.get("/api/audit")
async def audit(agent_id: str | None = None, limit: int = 200,
                c: Caller = Depends(caller)) -> list[dict]:
    return await views.audit(c, agent_id=agent_id, limit=min(limit, 1000))


@app.get("/api/agents")
async def list_agents(c: Caller = Depends(caller)) -> list[dict]:
    out = []
    for v, m in await agents.all_active():
        if not await team_groups.visible(c, m.id, m):
            continue
        groups = await team_groups.active_groups(m.id)
        out.append({
            "id": m.id, "name": m.name, "description": m.description, "version": v,
            "task_label": m.task.label, "item_label": m.task.item_label,
            "task_key": m.task.key, "steps": m.steps,
            "is_owner": agents.is_owner(c, m),
            "can_decide": c.has_any_role(m.review.roles)
            or any(c.has_any_role(gm.review.roles) for _, _, gm in groups),
            "configurable": m.configurable,
            "groups": [{"group": cfg.group, "name": cfg.name} for _, cfg, _ in groups],
        })
    return out


@app.get("/api/agents/{agent_id}")
@_errors
async def get_agent(agent_id: str, c: Caller = Depends(caller)) -> dict:
    version, m = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, m):
        raise LookupError(agent_id)
    return {"version": version, "manifest": m.model_dump(by_alias=True),
            "versions": await agents.versions(agent_id)}


def _group_view(c: Caller, base, version: int, cfg, m) -> dict:
    """A team group as the console shows it: who owns it, what it sets, who works its tasks."""
    return {
        "agent_id": base.id, "group": cfg.group, "name": cfg.name,
        "description": cfg.description, "version": version, "owners": cfg.owners.model_dump(),
        "sets": team_groups.set_paths(cfg.set, base.configurable)[0],
        "task_label": m.task.label, "item_label": m.task.item_label, "task_key": m.task.key,
        "review_roles": m.review.roles,
        "is_owner": team_groups.is_group_owner(c, cfg),
        "can_open": agents.can_see(c, m),
        "can_decide": c.has_any_role(m.review.roles),
    }


@app.get("/api/agents/{agent_id}/groups")
@_errors
async def list_groups(agent_id: str, c: Caller = Depends(caller)) -> list[dict]:
    _, base = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, base):
        raise LookupError(agent_id)
    return [_group_view(c, base, v, cfg, m)
            for v, cfg, m in await team_groups.active_groups(agent_id)]


@app.get("/api/agents/{agent_id}/groups/{group}")
@_errors
async def get_group(agent_id: str, group: str, c: Caller = Depends(caller)) -> dict:
    _, base = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, base):
        raise LookupError(agent_id)
    v, cfg, m = await team_groups.active_group(agent_id, group)
    return {**_group_view(c, base, v, cfg, m), "config": cfg.model_dump(),
            "manifest": m.model_dump(by_alias=True), "configurable": base.configurable,
            "versions": await team_groups.versions(agent_id, group)}


class GroupDraftIn(BaseModel):
    config: dict
    note: str = ""


@app.post("/api/agents/{agent_id}/groups", status_code=201)
@_errors
async def draft_group(agent_id: str, body: GroupDraftIn, c: Caller = Depends(caller)) -> dict:
    """A new version of a group, or a new group. Live after another group owner approves."""
    return await team_groups.draft(agent_id, body.config, body.note, c)


@app.post("/api/agents/{agent_id}/groups/{group}/versions/{version}/approve")
@_errors
async def approve_group(agent_id: str, group: str, version: int,
                        c: Caller = Depends(caller)) -> dict:
    await team_groups.approve(agent_id, group, version, c)
    return {"group": group, "version": version, "status": "active"}


class DraftIn(BaseModel):
    manifest: dict
    note: str = ""


@app.post("/api/agents/{agent_id}/versions", status_code=201)
@_errors
async def draft_version(agent_id: str, body: DraftIn, c: Caller = Depends(caller)) -> dict:
    return {"version": await agents.draft(agent_id, body.manifest, body.note, c)}


class CheckIn(BaseModel):
    manifest: dict | None = None    # a whole agent manifest, or…
    config: dict | None = None      # …a group's configuration


@app.post("/api/agents/{agent_id}/check")
@_errors
async def check_configuration(agent_id: str, body: CheckIn, c: Caller = Depends(caller)) -> dict:
    """What a draft would be refused for, without storing anything: the
    configuration screens check each edit as it is made."""
    _, base = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, base):
        raise LookupError(agent_id)
    if (body.manifest is None) == (body.config is None):
        raise HTTPException(422, "send either a manifest or a group config")
    found = (agents.check(agent_id, body.manifest) if body.manifest is not None
             else team_groups.check(base, body.config))
    return {"ok": not found, "problems": found}


@app.post("/api/agents/{agent_id}/versions/{version}/approve")
@_errors
async def approve_version(agent_id: str, version: int, c: Caller = Depends(caller)) -> dict:
    await agents.approve(agent_id, version, c)
    return {"version": version, "status": "active"}


@app.get("/api/agents/{agent_id}/tasks")
@_errors
async def list_tasks(agent_id: str, team_group: str | None = None, limit: int = 200,
                     offset: int = 0, c: Caller = Depends(caller)) -> list[dict]:
    return await tasks.list_tasks(agent_id, c, team_group,
                                  limit=max(1, min(limit, 1000)), offset=max(0, offset))


class OpenIn(BaseModel):
    task_key: dict
    team_group: str | None = None   # required when the agent has groups


@app.post("/api/agents/{agent_id}/tasks", status_code=201)
@_errors
async def open_task(agent_id: str, body: OpenIn, c: Caller = Depends(caller)) -> dict:
    task_id = await tasks.open_task(agent_id, body.task_key, c, body.team_group)
    return await tasks.task_detail(task_id, c)


@app.get("/api/tasks/{task_id}")
@_errors
async def get_task(task_id: str, c: Caller = Depends(caller)) -> dict:
    return await tasks.task_detail(task_id, c)


@app.get("/api/tasks/{task_id}/summary")
@_errors
async def get_task_summary(task_id: str, c: Caller = Depends(caller)) -> dict:
    """The task's Summary tab: sources read, its items broken down by task.summarize_by,
    its proposals across them, and the model session behind it."""
    from agent_one_finance import summary
    return await summary.task_summary(task_id, c)


class DecisionIn(BaseModel):
    group_id: str
    action: str
    comment: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    # The reviewer explicitly confirms a verdict flagged "requires confirmation".
    confirmed: bool = False
    # Time the reviewer spent on the group before deciding (the console measures it).
    review_seconds: int | None = Field(default=None, ge=0)
    # The sign-off checklist: [{id, answer: yes|no|n/a, note}].
    checklist: list[dict] | None = None


@app.post("/api/tasks/{task_id}/decisions", status_code=201)
@_errors
async def decide(task_id: str, body: DecisionIn, c: Caller = Depends(caller)) -> dict:
    result = await tasks.decide(task_id, body.group_id, body.action, body.comment,
                                body.idempotency_key, c, confirmed=body.confirmed,
                                review_seconds=body.review_seconds, checklist=body.checklist)
    return {**result, "task": await tasks.task_detail(task_id, c)}


class BulkDecisionIn(BaseModel):
    group_ids: list[str] = Field(min_length=1, max_length=1000)
    action: str
    comment: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=96)
    review_seconds: int | None = Field(default=None, ge=0)
    # One set of checklist answers for every group approved.
    checklist: list[dict] | None = None
    # The reviewer confirms the verdicts of the groups they selected that need it.
    confirmed: bool = False


@app.post("/api/tasks/{task_id}/decisions/bulk", status_code=201)
@_errors
async def decide_bulk(task_id: str, body: BulkDecisionIn, c: Caller = Depends(caller)) -> dict:
    result = await tasks.bulk_decide(task_id, body.group_ids, body.action, body.comment,
                                     body.idempotency_key, c, review_seconds=body.review_seconds,
                                     checklist=body.checklist, confirmed=body.confirmed)
    return {**result, "task": await tasks.task_detail(task_id, c)}


class ReinvestigateIn(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class AskIn(BaseModel):
    target: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4000)
    group_id: str | None = Field(default=None, max_length=128)   # None = about the whole task


@app.post("/api/tasks/{task_id}/requests", status_code=201)
@_errors
async def ask_for_evidence(task_id: str, body: AskIn, c: Caller = Depends(caller)) -> dict:
    """Ask a desk, a trader or Operations for evidence (FOBO skill §13)."""
    return await asks.ask(task_id, body.target, body.question, body.group_id, c)


@app.get("/api/requests")
@_errors
async def my_requests(c: Caller = Depends(caller)) -> list[dict]:
    """Open questions addressed to the caller."""
    return await asks.mine(c)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    answered_by: str | None = Field(default=None, max_length=64)   # a bot answering for someone


@app.post("/api/requests/{request_id}/answer")
@_errors
async def answer_request(request_id: str, body: AnswerIn, request: Request) -> dict:
    """The addressee answers; or a bot (Teams, email) answers for them with the
    event secret (X-AOF-Event-Secret) and `answered_by`."""
    secret = settings().event_secret
    sent = request.headers.get("X-AOF-Event-Secret")
    if sent is not None:
        if not secret or not hmac.compare_digest(sent.encode(), secret.encode()):
            raise HTTPException(401, "bad event secret")
        if not body.answered_by:
            raise HTTPException(422, "a bot answering says who for: answered_by")
        return await asks.answer(request_id, body.answer, None, on_behalf=body.answered_by)
    return await asks.answer(request_id, body.answer, await caller(request))


@app.post("/api/requests/{request_id}/answer-with-file")
@_errors
async def answer_request_with_file(request_id: str, request: Request, answer: str = Form(..., min_length=1, max_length=8000),
                                   file: UploadFile = File(...), answered_by: str | None = Form(None)) -> dict:
    """The same, with a file (PDF or workbook) kept as the task's evidence."""
    from agent_one_finance import evidence

    content = await file.read(evidence.MAX_BYTES + 1)
    upload = (file.filename or "evidence", content)
    sent = request.headers.get("X-AOF-Event-Secret")
    if sent is not None:
        secret = settings().event_secret
        if not secret or not hmac.compare_digest(sent.encode(), secret.encode()):
            raise HTTPException(401, "bad event secret")
        if not answered_by:
            raise HTTPException(422, "a bot answering says who for: answered_by")
        return await asks.answer(request_id, answer, None, on_behalf=answered_by, file=upload)
    return await asks.answer(request_id, answer, await caller(request), file=upload)


@app.post("/api/tasks/{task_id}/events/{step}")
@_errors
async def task_event(task_id: str, step: str, body: dict, request: Request) -> dict:
    """An event a waiting task continues with (a reply, a confirmation, a file
    received): from a system with the event secret, or from a person."""
    sent = request.headers.get("X-AOF-Event-Secret")
    payload = body.get("payload", body) if isinstance(body, dict) else {}
    if sent is not None:
        secret = settings().event_secret
        if not secret or not hmac.compare_digest(sent.encode(), secret.encode()):
            raise HTTPException(401, "bad event secret")
        return await tasks.deliver_event(task_id, step, payload, None)
    return await tasks.deliver_event(task_id, step, payload, await caller(request))


@app.post("/api/requests/{request_id}/cancel")
@_errors
async def cancel_request(request_id: str, c: Caller = Depends(caller)) -> dict:
    return await asks.cancel(request_id, c)


class GateIn(BaseModel):
    action: str = Field(pattern="^(continue|stop)$")
    comment: str | None = Field(default=None, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.post("/api/tasks/{task_id}/gates/{step}")
@_errors
async def pass_gate(task_id: str, step: str, body: GateIn, c: Caller = Depends(caller)) -> dict:
    """A person at a tollgate: continue the run to `step`, or stop it there."""
    await tasks.pass_gate(task_id, step, body.action, body.comment, body.idempotency_key, c)
    return await tasks.task_detail(task_id, c)


@app.post("/api/tasks/{task_id}/groups/{group_id}/reinvestigate", status_code=201)
@_errors
async def reinvestigate(task_id: str, group_id: str, body: ReinvestigateIn,
                        c: Caller = Depends(caller)) -> dict:
    result = await tasks.reinvestigate(task_id, group_id, body.note, body.idempotency_key, c)
    return {**result, "task": await tasks.task_detail(task_id, c)}


@app.post("/api/tasks/{task_id}/evidence", status_code=201)
@_errors
async def add_evidence(task_id: str, file: UploadFile = File(...), note: str | None = Form(None),
                       c: Caller = Depends(caller)) -> dict:
    content = await file.read(evidence.MAX_BYTES + 1)
    saved = await evidence.upload(task_id, file.filename or "evidence", content, note, c)
    return {**saved, "task": await tasks.task_detail(task_id, c)}


@app.get("/api/tasks/{task_id}/evidence/{name}")
@_errors
async def get_evidence(task_id: str, name: str, c: Caller = Depends(caller)) -> Response:
    content, content_type = await evidence.download(task_id, name, c)
    return Response(content, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/tasks/{task_id}/evidence-pack")
@_errors
async def evidence_pack(task_id: str, c: Caller = Depends(caller)) -> Response:
    content, name = await evidence.pack(task_id, c)
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/tasks/{task_id}/export.xlsx")
@_errors
async def export_task(task_id: str, c: Caller = Depends(caller)) -> Response:
    """The task as a workbook: items, groups and decisions, the task's facts."""
    from agent_one_finance import export

    content, name = await export.workbook(task_id, c)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/agents/{agent_id}/recurring")
@_errors
async def recurring(agent_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> list[dict]:
    """Items that keep coming back across the caller's tasks (insights.recurring)."""
    from agent_one_finance import insights

    return await insights.recurring_overview(agent_id, c, team_group)


@app.get("/api/agents/{agent_id}/contract")
@_errors
async def data_contract(agent_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> dict:
    """The data the configuration reads and the parameters still to confirm
    (of the agent, or of one team group's effective configuration)."""
    from agent_one_finance import agents, contract
    from agent_one_finance import groups as team_groups

    _, m = await agents.active(agent_id)
    if team_group:
        _, _, m = await team_groups.active_group(agent_id, team_group)
    if not agents.can_see(c, m):
        raise PermissionError(f"{c.user_id} has no role for {agent_id}")
    return contract.contract(m)


@app.get("/api/agents/{agent_id}/learning")
@_errors
async def learning(agent_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> dict:
    """What nothing explained (insights.unexplained), and model-proposed groups
    reviewers keep approving unchanged: candidates for a rule."""
    from agent_one_finance import insights

    return await insights.learning(agent_id, c, team_group)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.get("/api/tasks/{task_id}/messages")
@_errors
async def task_messages(task_id: str, c: Caller = Depends(caller)) -> list[dict]:
    return await chat.messages(task_id, c)


@app.post("/api/tasks/{task_id}/ask", status_code=201)
@_errors
async def ask_task(task_id: str, body: AskIn, c: Caller = Depends(caller)) -> dict:
    return await chat.ask(task_id, body.question, c)


@app.get("/api/tasks/{task_id}/history")
@_errors
async def task_history(task_id: str, c: Caller = Depends(caller)) -> list[dict]:
    return await chat.history(task_id, c)


@app.get("/api/tasks/{task_id}/history/{checkpoint_id}")
@_errors
async def task_state_at(task_id: str, checkpoint_id: str, c: Caller = Depends(caller)) -> dict:
    return await chat.state_at(task_id, checkpoint_id, c)


class LegalHoldIn(BaseModel):
    hold: bool
    reason: str | None = Field(default=None, max_length=1000)


@app.post("/api/tasks/{task_id}/legal-hold")
@_errors
async def legal_hold(task_id: str, body: LegalHoldIn, c: Caller = Depends(caller)) -> dict:
    await retention.set_legal_hold(task_id, body.hold, body.reason, c)
    return await tasks.task_detail(task_id, c)


@app.post("/api/tasks/{task_id}/rerun", status_code=201)
@_errors
async def rerun(task_id: str, c: Caller = Depends(caller)) -> dict:
    new_id = await tasks.rerun_task(task_id, c)
    return await tasks.task_detail(new_id, c)


class PublishIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.post("/api/tasks/{task_id}/publish", status_code=201)
@_errors
async def release_publish(task_id: str, body: PublishIn, c: Caller = Depends(caller)) -> dict:
    result = await tasks.approve_publish(task_id, body.idempotency_key, c)
    return {**result, "task": await tasks.task_detail(task_id, c)}


@app.get("/api/tasks/{task_id}/documents/{name}")
@_errors
async def task_document(task_id: str, name: str, c: Caller = Depends(caller)) -> Response:
    """A report this task published (e.g. its PDF), for people who can see the task."""
    from agent_one_finance.mcp_services.documents import DocumentError, load_report

    if kept := await tasks.task_report(task_id, name, c):
        return Response(kept[0], media_type=kept[1], headers={"Content-Disposition": f'attachment; filename="{name}"'})
    scope, name = await tasks.published_document(task_id, name, c)
    try:
        content, content_type = await load_report(scope, name)
    except DocumentError as e:
        raise LookupError(str(e)) from e
    return Response(content, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/tasks/{task_id}/publish/retry", status_code=201)
@_errors
async def retry_publish(task_id: str, c: Caller = Depends(caller)) -> dict:
    result = await tasks.retry_publish(task_id, c)
    return {**result, "task": await tasks.task_detail(task_id, c)}


class BrdIn(BaseModel):
    brd: str = Field(max_length=100_000)


@app.post("/api/authoring/draft")
async def authoring_draft(body: BrdIn, c: Caller = Depends(caller)) -> dict:
    """BRD → draft manifest YAML, judged by the platform validator. Saves nothing."""
    return await authoring.draft_from_brd(body.brd, c)


@app.get("/api/authoring/modes")
async def authoring_modes(c: Caller = Depends(caller)) -> dict:
    """Which ways of authoring are offered: guided (no model), templates, and
    drafting from a BRD (a model when one is connected)."""
    return authoring.available_modes()


@app.post("/api/authoring/guided")
async def authoring_guided(body: dict, c: Caller = Depends(caller)) -> dict:
    """A guided form's answers → a draft manifest, judged. No model. Saves nothing."""
    return await authoring.guided(body, c)


class SubmitIn(BaseModel):
    yaml: str = Field(max_length=200_000)
    note: str = ""


@app.post("/api/authoring/submit", status_code=201)
@_errors
async def authoring_submit(body: SubmitIn, c: Caller = Depends(caller)) -> dict:
    """Store a judged manifest as a draft: version 1 of a new agent, or the next
    version of an existing one (its owners only). Live only after another owner approves."""
    judged = authoring.judge(body.yaml)
    if judged["manifest"] is None or judged["problems"]:
        raise agents.AgentError("the manifest has problems", judged["problems"])
    m = judged["manifest"]
    try:
        await agents.active(m["id"])
        version = await agents.draft(m["id"], m, body.note, c)
    except agents.AgentError as e:
        if "no active agent" not in str(e):
            raise
        version = await agents.draft_new(m, body.note, c)
    return {"agent_id": m["id"], "version": version}


@app.get("/api/authoring/drafts")
async def authoring_drafts(c: Caller = Depends(caller)) -> list[dict]:
    return await agents.drafts_for(c)


@app.get("/api/notifications")
async def notifications(c: Caller = Depends(caller)) -> dict:
    return await notify.for_caller(c)


class ReadIn(BaseModel):
    ids: list[str] | None = None    # None: all


@app.post("/api/notifications/read")
async def notifications_read(body: ReadIn, c: Caller = Depends(caller)) -> dict:
    return {"marked": await notify.mark_read(c, body.ids)}


class EventIn(BaseModel):
    agent_id: str
    team_group: str | None = None
    task_key: dict
    event: str = Field(default="", max_length=500)     # what happened, for the record


@app.post("/api/events", status_code=201)
@_errors
async def event(body: EventIn, request: Request) -> dict:
    """Another system opens a task ("the file for UK01 2026-09 arrived"). The
    agent (or group) must allow events; the task runs as its `opens_as`
    service user. Disabled unless AOF_EVENT_SECRET is set."""
    secret = settings().event_secret
    if not secret:
        raise HTTPException(404, "not enabled")
    if not hmac.compare_digest(request.headers.get("X-AOF-Event-Secret", "").encode(), secret.encode()):
        raise HTTPException(401, "bad event secret")
    _, _, m = await tasks._resolve_unchecked(body.agent_id, body.team_group)
    if not m.task.events or not m.task.opens_as:
        raise PermissionError(f"{body.agent_id} does not take events")
    as_user = await entitlements().get(m.task.opens_as)
    task_id = await tasks.open_task(body.agent_id, body.task_key, as_user, body.team_group, late=True)
    return {"task_id": task_id, "opened_as": m.task.opens_as, "event": body.event}


@app.get("/api/schedules")
async def schedules(c: Caller = Depends(caller)) -> list[dict]:
    """Schedules in force for agents the caller can see."""
    from agent_one_finance import groups as team_groups

    out = []
    for s in await scheduler.scheduled():
        _, base = await agents.active(s["agent_id"])
        if s["team_group"]:
            # a team's schedule names its books or entities: only for that team
            _, cfg, gm = await team_groups.active_group(s["agent_id"], s["team_group"])
            if agents.can_see(c, gm) or team_groups.is_group_owner(c, cfg):
                out.append(s)
        elif agents.can_see(c, base):
            out.append(s)
    return out


@app.get("/api/switches")
async def switches(c: Caller = Depends(caller)) -> list[dict]:
    return [{**sw, "can_switch": await controls.can_switch(c, sw["kind"], sw["target"])}
            for sw in await controls.all_switches()]


class SwitchIn(BaseModel):
    kind: str
    target: str = Field(min_length=1, max_length=160)
    off: bool
    reason: str = Field(default="", max_length=1000)


@app.post("/api/switches")
@_errors
async def set_switch(body: SwitchIn, c: Caller = Depends(caller)) -> dict:
    try:
        return await controls.set_switch(c, body.kind, body.target, body.off, body.reason)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


class EvalIn(BaseModel):
    version: int | None = None
    team_group: str | None = None
    group_version: int | None = None
    limit: int = Field(default=20, ge=1, le=200)


@app.post("/api/agents/{agent_id}/evals", status_code=201)
@_errors
async def start_eval(agent_id: str, body: EvalIn, c: Caller = Depends(caller)) -> dict:
    try:
        run_id = await evals.start(agent_id, c, version=body.version, team_group=body.team_group,
                                   group_version=body.group_version, limit=body.limit)
    except evals.EvalError as e:
        raise HTTPException(409, str(e)) from e
    return await evals.get(run_id)


@app.get("/api/agents/{agent_id}/evals")
@_errors
async def list_evals(agent_id: str, c: Caller = Depends(caller)) -> list[dict]:
    from agent_one_finance import groups as team_groups
    _, m = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, m):
        raise PermissionError(f"{c.user_id} has no role for {agent_id}")
    return await evals.runs(agent_id)


@app.get("/api/agents/{agent_id}/evals/available")
@_errors
async def evals_available(agent_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> dict:
    """How many past tasks people settled an eval would replay (at most `limit`)."""
    from agent_one_finance import groups as team_groups
    _, m = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, m):
        raise PermissionError(f"{c.user_id} has no role for {agent_id}")
    limit = 20
    return {"tasks": len(await evals.test_set(agent_id, team_group, limit)), "limit": limit}


@app.get("/api/evals/{run_id}")
@_errors
async def get_eval(run_id: str, c: Caller = Depends(caller)) -> dict:
    from agent_one_finance import groups as team_groups
    run = await evals.get(run_id)
    _, m = await agents.active(run["agent_id"])
    if not await team_groups.visible(c, run["agent_id"], m):
        raise LookupError(run_id)
    return run


@app.get("/api/agents/{agent_id}/versions/{a}/diff/{b}")
@_errors
async def diff_versions(agent_id: str, a: int, b: int, c: Caller = Depends(caller)) -> dict:
    await _require_visible(agent_id, c)
    return await devtools.version_diff(agent_id, a, b)


@app.get("/api/agents/{agent_id}/groups/{group}/versions/{a}/diff/{b}")
@_errors
async def diff_group_versions(agent_id: str, group: str, a: int, b: int,
                              c: Caller = Depends(caller)) -> dict:
    await _require_visible(agent_id, c)
    return await devtools.group_diff(agent_id, group, a, b)


class InstructionsIn(BaseModel):
    skill: str = Field(min_length=1, max_length=50_000)
    note: str = Field(default="", max_length=1000)
    team_group: str | None = None


@app.post("/api/agents/{agent_id}/instructions", status_code=201)
@_errors
async def draft_instructions(agent_id: str, body: InstructionsIn, c: Caller = Depends(caller)) -> dict:
    return await devtools.draft_instructions(agent_id, body.skill, body.note, c, body.team_group)


@app.get("/api/agents/{agent_id}/flow")
@_errors
async def agent_flow(agent_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> dict:
    from agent_one_finance import groups as team_groups
    await _require_visible(agent_id, c)
    _, m = await agents.active(agent_id)
    if team_group:
        _, _, m = await team_groups.active_group(agent_id, team_group)
    return devtools.flow(m)


@app.get("/api/authoring/templates")
async def authoring_templates(c: Caller = Depends(caller)) -> list[dict]:
    return devtools.templates()


@app.get("/api/agents/{agent_id}/versions/{version}/export")
@_errors
async def export_version(agent_id: str, version: int, group: str | None = None,
                         c: Caller = Depends(caller)) -> dict:
    await _require_visible(agent_id, c)
    return await devtools.export(agent_id, version, c, group)


class ImportIn(BaseModel):
    bundle: dict


@app.post("/api/promotion/import", status_code=201)
@_errors
async def import_version(body: ImportIn, c: Caller = Depends(caller)) -> dict:
    return await devtools.import_bundle(body.bundle, c)


async def _require_visible(agent_id: str, c: Caller) -> None:
    from agent_one_finance import groups as team_groups
    _, m = await agents.active(agent_id)
    if not await team_groups.visible(c, agent_id, m):
        raise PermissionError(f"{c.user_id} has no role for {agent_id}")


class InvalidateIn(BaseModel):
    user_id: str | None = None      # None: everyone


@app.post("/api/entitlements/invalidate")
async def invalidate_entitlements(body: InvalidateIn, request: Request) -> dict:
    """Called by the entitlements service when someone's access changes, so the
    change applies now rather than when the cache expires. Disabled unless
    AOF_ENTITLEMENT_WEBHOOK_SECRET is set; the caller sends it as
    X-AOF-Webhook-Secret."""
    secret = settings().entitlement_webhook_secret
    if not secret:
        raise HTTPException(404, "not enabled")
    sent = request.headers.get("X-AOF-Webhook-Secret", "")
    if not hmac.compare_digest(sent.encode(), secret.encode()):
        raise HTTPException(401, "bad webhook secret")
    return {"invalidated": entitlements().invalidate(body.user_id)}


@app.get("/api/platform")
async def platform(c: Caller = Depends(caller)) -> dict:
    """What this Agent One Finance instance offers: steps, connector tools, adapters."""
    reg = registry()
    return {
        "steps": catalogue(),
        "connectors": [{"id": cid, "name": spec.name, "transport": spec.transport,
                        "classification": spec.classification,
                        "tools": [{"name": f"{cid}.{t}", "description": ts.description,
                                   "access": ts.access,
                                   "scope": ([r.model_dump() for r in ts.scope_rules()] or None)}
                                  for t, ts in spec.tools.items()]}
                       for cid, spec in reg.connectors.items()],
        "llm": llm().name,
        "entitlement": "central" if settings().entitlement_url else "dev-stub",
    }
