"""The Helix API: `uvicorn helix.web.main:app --port 8300`.

Identity comes from one request header (HELIX_IDENTITY_HEADER, set by the
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

from helix import authoring, capabilities, cases, chat, controls, devtools, evals, evidence, knowledge, notify, retention, review, runner, scheduler, views
from helix import groups as team_groups
from helix.config import settings
from helix.entitlement import Caller, EntitlementError, StubEntitlement, entitlements
from helix.gateway import registry
from helix.llm import llm
from helix.observability import setup_tracing
from helix.workflow import catalogue, setup_checkpointer


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_tracing()
    await setup_checkpointer()
    await capabilities.seed()
    await team_groups.seed()
    await knowledge.seed_reference()
    await runner.recover()          # finish runs a stopped server left behind
    loop = asyncio.create_task(scheduler.run_forever()) if settings().scheduler else None
    yield
    if loop:
        loop.cancel()
    await runner.drain()


app = FastAPI(title="Helix API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings().console_origin], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def trusted_proxy(request: Request, call_next):
    """With HELIX_TRUSTED_PROXY_SECRET set, only requests that came through the
    SSO proxy (which adds the secret) reach the API: the identity header can
    then not be set by anyone who can merely reach the server."""
    secret = settings().trusted_proxy_secret
    if secret and request.url.path.startswith("/api/"):
        sent = request.headers.get(settings().proxy_secret_header, "")
        if not hmac.compare_digest(sent.encode(), secret.encode()):
            return JSONResponse({"detail": "request did not come through the trusted proxy"},
                                status_code=401)
    return await call_next(request)


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
        except (capabilities.CapabilityError, team_groups.GroupError) as e:
            raise HTTPException(422, {"message": str(e), "problems": e.problems}) from e
        except cases.CaseError as e:
            raise HTTPException(409, str(e)) from e
        except review.ReviewError as e:
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
    """While I am away, this colleague decides on my behalf — only on cases
    whose capability allows it (review.allow_delegation), within my scope."""
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
async def audit(capability_id: str | None = None, limit: int = 200,
                c: Caller = Depends(caller)) -> list[dict]:
    return await views.audit(c, capability_id=capability_id, limit=min(limit, 1000))


@app.get("/api/capabilities")
async def list_capabilities(c: Caller = Depends(caller)) -> list[dict]:
    out = []
    for v, m in await capabilities.all_active():
        if not await team_groups.visible(c, m.id, m):
            continue
        groups = await team_groups.active_groups(m.id)
        out.append({
            "id": m.id, "name": m.name, "description": m.description, "version": v,
            "case_label": m.case.label, "item_label": m.case.item_label,
            "case_key": m.case.key, "steps": m.steps,
            "is_owner": capabilities.is_owner(c, m),
            "can_decide": c.has_any_role(m.review.roles)
            or any(c.has_any_role(gm.review.roles) for _, _, gm in groups),
            "configurable": m.configurable,
            "groups": [{"group": cfg.group, "name": cfg.name} for _, cfg, _ in groups],
        })
    return out


@app.get("/api/capabilities/{capability_id}")
@_errors
async def get_capability(capability_id: str, c: Caller = Depends(caller)) -> dict:
    version, m = await capabilities.active(capability_id)
    if not await team_groups.visible(c, capability_id, m):
        raise LookupError(capability_id)
    return {"version": version, "manifest": m.model_dump(by_alias=True),
            "versions": await capabilities.versions(capability_id)}


def _group_view(c: Caller, base, version: int, cfg, m) -> dict:
    """A team group as the console shows it: who owns it, what it sets, who works its cases."""
    return {
        "capability_id": base.id, "group": cfg.group, "name": cfg.name,
        "description": cfg.description, "version": version, "owners": cfg.owners.model_dump(),
        "sets": team_groups.set_paths(cfg.set, base.configurable)[0],
        "case_label": m.case.label, "item_label": m.case.item_label, "case_key": m.case.key,
        "review_roles": m.review.roles,
        "is_owner": team_groups.is_group_owner(c, cfg),
        "can_open": capabilities.can_see(c, m),
        "can_decide": c.has_any_role(m.review.roles),
    }


@app.get("/api/capabilities/{capability_id}/groups")
@_errors
async def list_groups(capability_id: str, c: Caller = Depends(caller)) -> list[dict]:
    _, base = await capabilities.active(capability_id)
    if not await team_groups.visible(c, capability_id, base):
        raise LookupError(capability_id)
    return [_group_view(c, base, v, cfg, m)
            for v, cfg, m in await team_groups.active_groups(capability_id)]


@app.get("/api/capabilities/{capability_id}/groups/{group}")
@_errors
async def get_group(capability_id: str, group: str, c: Caller = Depends(caller)) -> dict:
    _, base = await capabilities.active(capability_id)
    if not await team_groups.visible(c, capability_id, base):
        raise LookupError(capability_id)
    v, cfg, m = await team_groups.active_group(capability_id, group)
    return {**_group_view(c, base, v, cfg, m), "config": cfg.model_dump(),
            "manifest": m.model_dump(by_alias=True), "configurable": base.configurable,
            "versions": await team_groups.versions(capability_id, group)}


class GroupDraftIn(BaseModel):
    config: dict
    note: str = ""


@app.post("/api/capabilities/{capability_id}/groups", status_code=201)
@_errors
async def draft_group(capability_id: str, body: GroupDraftIn, c: Caller = Depends(caller)) -> dict:
    """A new version of a group, or a new group. Live after another group owner approves."""
    return await team_groups.draft(capability_id, body.config, body.note, c)


@app.post("/api/capabilities/{capability_id}/groups/{group}/versions/{version}/approve")
@_errors
async def approve_group(capability_id: str, group: str, version: int,
                        c: Caller = Depends(caller)) -> dict:
    await team_groups.approve(capability_id, group, version, c)
    return {"group": group, "version": version, "status": "active"}


class DraftIn(BaseModel):
    manifest: dict
    note: str = ""


@app.post("/api/capabilities/{capability_id}/versions", status_code=201)
@_errors
async def draft_version(capability_id: str, body: DraftIn, c: Caller = Depends(caller)) -> dict:
    return {"version": await capabilities.draft(capability_id, body.manifest, body.note, c)}


@app.post("/api/capabilities/{capability_id}/versions/{version}/approve")
@_errors
async def approve_version(capability_id: str, version: int, c: Caller = Depends(caller)) -> dict:
    await capabilities.approve(capability_id, version, c)
    return {"version": version, "status": "active"}


@app.get("/api/capabilities/{capability_id}/cases")
@_errors
async def list_cases(capability_id: str, team_group: str | None = None, limit: int = 200,
                     offset: int = 0, c: Caller = Depends(caller)) -> list[dict]:
    return await cases.list_cases(capability_id, c, team_group,
                                  limit=max(1, min(limit, 1000)), offset=max(0, offset))


class OpenIn(BaseModel):
    case_key: dict
    team_group: str | None = None   # required when the capability has groups


@app.post("/api/capabilities/{capability_id}/cases", status_code=201)
@_errors
async def open_case(capability_id: str, body: OpenIn, c: Caller = Depends(caller)) -> dict:
    case_id = await cases.open_case(capability_id, body.case_key, c, body.team_group)
    return await cases.case_detail(case_id, c)


@app.get("/api/cases/{case_id}")
@_errors
async def get_case(case_id: str, c: Caller = Depends(caller)) -> dict:
    return await cases.case_detail(case_id, c)


class DecisionIn(BaseModel):
    group_id: str
    action: str
    comment: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    # The reviewer explicitly confirms a verdict flagged "requires confirmation".
    confirmed: bool = False
    # Time the reviewer spent on the group before deciding (the console measures it).
    review_seconds: int | None = Field(default=None, ge=0)


@app.post("/api/cases/{case_id}/decisions", status_code=201)
@_errors
async def decide(case_id: str, body: DecisionIn, c: Caller = Depends(caller)) -> dict:
    result = await cases.decide(case_id, body.group_id, body.action, body.comment,
                                body.idempotency_key, c, confirmed=body.confirmed,
                                review_seconds=body.review_seconds)
    return {**result, "case": await cases.case_detail(case_id, c)}


class BulkDecisionIn(BaseModel):
    group_ids: list[str] = Field(min_length=1, max_length=1000)
    action: str
    comment: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=96)
    review_seconds: int | None = Field(default=None, ge=0)


@app.post("/api/cases/{case_id}/decisions/bulk", status_code=201)
@_errors
async def decide_bulk(case_id: str, body: BulkDecisionIn, c: Caller = Depends(caller)) -> dict:
    result = await cases.bulk_decide(case_id, body.group_ids, body.action, body.comment,
                                     body.idempotency_key, c, review_seconds=body.review_seconds)
    return {**result, "case": await cases.case_detail(case_id, c)}


class ReinvestigateIn(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.post("/api/cases/{case_id}/groups/{group_id}/reinvestigate", status_code=201)
@_errors
async def reinvestigate(case_id: str, group_id: str, body: ReinvestigateIn,
                        c: Caller = Depends(caller)) -> dict:
    result = await cases.reinvestigate(case_id, group_id, body.note, body.idempotency_key, c)
    return {**result, "case": await cases.case_detail(case_id, c)}


@app.post("/api/cases/{case_id}/evidence", status_code=201)
@_errors
async def add_evidence(case_id: str, file: UploadFile = File(...), note: str | None = Form(None),
                       c: Caller = Depends(caller)) -> dict:
    content = await file.read(evidence.MAX_BYTES + 1)
    saved = await evidence.upload(case_id, file.filename or "evidence", content, note, c)
    return {**saved, "case": await cases.case_detail(case_id, c)}


@app.get("/api/cases/{case_id}/evidence/{name}")
@_errors
async def get_evidence(case_id: str, name: str, c: Caller = Depends(caller)) -> Response:
    content, content_type = await evidence.download(case_id, name, c)
    return Response(content, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/cases/{case_id}/evidence-pack")
@_errors
async def evidence_pack(case_id: str, c: Caller = Depends(caller)) -> Response:
    content, name = await evidence.pack(case_id, c)
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/cases/{case_id}/export.xlsx")
@_errors
async def export_case(case_id: str, c: Caller = Depends(caller)) -> Response:
    """The case as a workbook: items, groups and decisions, the case's facts."""
    from helix import export

    content, name = await export.workbook(case_id, c)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/capabilities/{capability_id}/recurring")
@_errors
async def recurring(capability_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> list[dict]:
    """Items that keep coming back across the caller's cases (insights.recurring)."""
    from helix import insights

    return await insights.recurring_overview(capability_id, c, team_group)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


@app.get("/api/cases/{case_id}/messages")
@_errors
async def case_messages(case_id: str, c: Caller = Depends(caller)) -> list[dict]:
    return await chat.messages(case_id, c)


@app.post("/api/cases/{case_id}/ask", status_code=201)
@_errors
async def ask_case(case_id: str, body: AskIn, c: Caller = Depends(caller)) -> dict:
    return await chat.ask(case_id, body.question, c)


@app.get("/api/cases/{case_id}/history")
@_errors
async def case_history(case_id: str, c: Caller = Depends(caller)) -> list[dict]:
    return await chat.history(case_id, c)


@app.get("/api/cases/{case_id}/history/{checkpoint_id}")
@_errors
async def case_state_at(case_id: str, checkpoint_id: str, c: Caller = Depends(caller)) -> dict:
    return await chat.state_at(case_id, checkpoint_id, c)


class LegalHoldIn(BaseModel):
    hold: bool
    reason: str | None = Field(default=None, max_length=1000)


@app.post("/api/cases/{case_id}/legal-hold")
@_errors
async def legal_hold(case_id: str, body: LegalHoldIn, c: Caller = Depends(caller)) -> dict:
    await retention.set_legal_hold(case_id, body.hold, body.reason, c)
    return await cases.case_detail(case_id, c)


@app.post("/api/cases/{case_id}/rerun", status_code=201)
@_errors
async def rerun(case_id: str, c: Caller = Depends(caller)) -> dict:
    new_id = await cases.rerun_case(case_id, c)
    return await cases.case_detail(new_id, c)


class PublishIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.post("/api/cases/{case_id}/publish", status_code=201)
@_errors
async def release_publish(case_id: str, body: PublishIn, c: Caller = Depends(caller)) -> dict:
    result = await cases.approve_publish(case_id, body.idempotency_key, c)
    return {**result, "case": await cases.case_detail(case_id, c)}


@app.get("/api/cases/{case_id}/documents/{name}")
@_errors
async def case_document(case_id: str, name: str, c: Caller = Depends(caller)) -> Response:
    """A report this case published (e.g. its PDF), for people who can see the case."""
    from helix.mcp_services.documents import DocumentError, load_report

    scope, name = await cases.published_document(case_id, name, c)
    try:
        content, content_type = await load_report(scope, name)
    except DocumentError as e:
        raise LookupError(str(e)) from e
    return Response(content, media_type=content_type,
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/cases/{case_id}/publish/retry", status_code=201)
@_errors
async def retry_publish(case_id: str, c: Caller = Depends(caller)) -> dict:
    result = await cases.retry_publish(case_id, c)
    return {**result, "case": await cases.case_detail(case_id, c)}


class BrdIn(BaseModel):
    brd: str = Field(max_length=100_000)


@app.post("/api/authoring/draft")
async def authoring_draft(body: BrdIn, c: Caller = Depends(caller)) -> dict:
    """BRD → draft manifest YAML, judged by the platform validator. Saves nothing."""
    return await authoring.draft_from_brd(body.brd, c)


class SubmitIn(BaseModel):
    yaml: str = Field(max_length=200_000)
    note: str = ""


@app.post("/api/authoring/submit", status_code=201)
@_errors
async def authoring_submit(body: SubmitIn, c: Caller = Depends(caller)) -> dict:
    """Store a judged manifest as a draft: version 1 of a new capability, or the next
    version of an existing one (its owners only). Live only after another owner approves."""
    judged = authoring.judge(body.yaml)
    if judged["manifest"] is None or judged["problems"]:
        raise capabilities.CapabilityError("the manifest has problems", judged["problems"])
    m = judged["manifest"]
    try:
        await capabilities.active(m["id"])
        version = await capabilities.draft(m["id"], m, body.note, c)
    except capabilities.CapabilityError as e:
        if "no active capability" not in str(e):
            raise
        version = await capabilities.draft_new(m, body.note, c)
    return {"capability_id": m["id"], "version": version}


@app.get("/api/authoring/drafts")
async def authoring_drafts(c: Caller = Depends(caller)) -> list[dict]:
    return await capabilities.drafts_for(c)


@app.get("/api/notifications")
async def notifications(c: Caller = Depends(caller)) -> dict:
    return await notify.for_caller(c)


class ReadIn(BaseModel):
    ids: list[str] | None = None    # None: all


@app.post("/api/notifications/read")
async def notifications_read(body: ReadIn, c: Caller = Depends(caller)) -> dict:
    return {"marked": await notify.mark_read(c, body.ids)}


class EventIn(BaseModel):
    capability_id: str
    team_group: str | None = None
    case_key: dict
    event: str = Field(default="", max_length=500)     # what happened, for the record


@app.post("/api/events", status_code=201)
@_errors
async def event(body: EventIn, request: Request) -> dict:
    """Another system opens a case ("the file for UK01 2026-09 arrived"). The
    capability (or group) must allow events; the case runs as its `opens_as`
    service user. Disabled unless HELIX_EVENT_SECRET is set."""
    secret = settings().event_secret
    if not secret:
        raise HTTPException(404, "not enabled")
    if not hmac.compare_digest(request.headers.get("X-Helix-Event-Secret", "").encode(), secret.encode()):
        raise HTTPException(401, "bad event secret")
    _, _, m = await cases._resolve_unchecked(body.capability_id, body.team_group)
    if not m.case.events or not m.case.opens_as:
        raise PermissionError(f"{body.capability_id} does not take events")
    as_user = await entitlements().get(m.case.opens_as)
    case_id = await cases.open_case(body.capability_id, body.case_key, as_user, body.team_group)
    return {"case_id": case_id, "opened_as": m.case.opens_as, "event": body.event}


@app.get("/api/schedules")
async def schedules(c: Caller = Depends(caller)) -> list[dict]:
    """Schedules in force for capabilities the caller can see."""
    from helix import groups as team_groups

    out = []
    for s in await scheduler.scheduled():
        _, base = await capabilities.active(s["capability_id"])
        if s["team_group"]:
            # a team's schedule names its books or entities: only for that team
            _, cfg, gm = await team_groups.active_group(s["capability_id"], s["team_group"])
            if capabilities.can_see(c, gm) or team_groups.is_group_owner(c, cfg):
                out.append(s)
        elif capabilities.can_see(c, base):
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


@app.post("/api/capabilities/{capability_id}/evals", status_code=201)
@_errors
async def start_eval(capability_id: str, body: EvalIn, c: Caller = Depends(caller)) -> dict:
    try:
        run_id = await evals.start(capability_id, c, version=body.version, team_group=body.team_group,
                                   group_version=body.group_version, limit=body.limit)
    except evals.EvalError as e:
        raise HTTPException(409, str(e)) from e
    return await evals.get(run_id)


@app.get("/api/capabilities/{capability_id}/evals")
@_errors
async def list_evals(capability_id: str, c: Caller = Depends(caller)) -> list[dict]:
    from helix import groups as team_groups
    _, m = await capabilities.active(capability_id)
    if not await team_groups.visible(c, capability_id, m):
        raise PermissionError(f"{c.user_id} has no role for {capability_id}")
    return await evals.runs(capability_id)


@app.get("/api/evals/{run_id}")
@_errors
async def get_eval(run_id: str, c: Caller = Depends(caller)) -> dict:
    from helix import groups as team_groups
    run = await evals.get(run_id)
    _, m = await capabilities.active(run["capability_id"])
    if not await team_groups.visible(c, run["capability_id"], m):
        raise LookupError(run_id)
    return run


@app.get("/api/capabilities/{capability_id}/versions/{a}/diff/{b}")
@_errors
async def diff_versions(capability_id: str, a: int, b: int, c: Caller = Depends(caller)) -> dict:
    await _require_visible(capability_id, c)
    return await devtools.version_diff(capability_id, a, b)


@app.get("/api/capabilities/{capability_id}/groups/{group}/versions/{a}/diff/{b}")
@_errors
async def diff_group_versions(capability_id: str, group: str, a: int, b: int,
                              c: Caller = Depends(caller)) -> dict:
    await _require_visible(capability_id, c)
    return await devtools.group_diff(capability_id, group, a, b)


class InstructionsIn(BaseModel):
    skill: str = Field(min_length=1, max_length=50_000)
    note: str = Field(default="", max_length=1000)
    team_group: str | None = None


@app.post("/api/capabilities/{capability_id}/instructions", status_code=201)
@_errors
async def draft_instructions(capability_id: str, body: InstructionsIn, c: Caller = Depends(caller)) -> dict:
    return await devtools.draft_instructions(capability_id, body.skill, body.note, c, body.team_group)


@app.get("/api/capabilities/{capability_id}/flow")
@_errors
async def capability_flow(capability_id: str, team_group: str | None = None, c: Caller = Depends(caller)) -> dict:
    from helix import groups as team_groups
    await _require_visible(capability_id, c)
    _, m = await capabilities.active(capability_id)
    if team_group:
        _, _, m = await team_groups.active_group(capability_id, team_group)
    return devtools.flow(m)


@app.get("/api/authoring/templates")
async def authoring_templates(c: Caller = Depends(caller)) -> list[dict]:
    return devtools.templates()


@app.get("/api/capabilities/{capability_id}/versions/{version}/export")
@_errors
async def export_version(capability_id: str, version: int, group: str | None = None,
                         c: Caller = Depends(caller)) -> dict:
    await _require_visible(capability_id, c)
    return await devtools.export(capability_id, version, c, group)


class ImportIn(BaseModel):
    bundle: dict


@app.post("/api/promotion/import", status_code=201)
@_errors
async def import_version(body: ImportIn, c: Caller = Depends(caller)) -> dict:
    return await devtools.import_bundle(body.bundle, c)


async def _require_visible(capability_id: str, c: Caller) -> None:
    from helix import groups as team_groups
    _, m = await capabilities.active(capability_id)
    if not await team_groups.visible(c, capability_id, m):
        raise PermissionError(f"{c.user_id} has no role for {capability_id}")


class InvalidateIn(BaseModel):
    user_id: str | None = None      # None: everyone


@app.post("/api/entitlements/invalidate")
async def invalidate_entitlements(body: InvalidateIn, request: Request) -> dict:
    """Called by the entitlements service when someone's access changes, so the
    change applies now rather than when the cache expires. Disabled unless
    HELIX_ENTITLEMENT_WEBHOOK_SECRET is set; the caller sends it as
    X-Helix-Webhook-Secret."""
    secret = settings().entitlement_webhook_secret
    if not secret:
        raise HTTPException(404, "not enabled")
    sent = request.headers.get("X-Helix-Webhook-Secret", "")
    if not hmac.compare_digest(sent.encode(), secret.encode()):
        raise HTTPException(401, "bad webhook secret")
    return {"invalidated": entitlements().invalidate(body.user_id)}


@app.get("/api/platform")
async def platform(c: Caller = Depends(caller)) -> dict:
    """What this Helix instance offers: steps, connector tools, adapters."""
    reg = registry()
    return {
        "steps": catalogue(),
        "connectors": [{"id": cid, "name": spec.name, "transport": spec.transport,
                        "classification": spec.classification,
                        "tools": [{"name": f"{cid}.{t}", "description": ts.description,
                                   "access": ts.access,
                                   "scope": ts.scope.model_dump() if ts.scope else None}
                                  for t, ts in spec.tools.items()]}
                       for cid, spec in reg.connectors.items()],
        "llm": llm().name,
        "entitlement": "central" if settings().entitlement_url else "dev-stub",
    }
