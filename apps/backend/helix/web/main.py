"""The Helix API: `uvicorn helix.web.main:app --port 8300`.

Identity comes from one request header (HELIX_IDENTITY_HEADER, set by the
SSO proxy in the office; the console's user switcher in development); roles
and data scopes come from the entitlement service, never from the request.
"""

from contextlib import asynccontextmanager
from functools import wraps

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from helix import authoring, capabilities, cases, views
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
    yield


app = FastAPI(title="Helix API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=[settings().console_origin], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


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
    return wrapped


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/me")
async def me(c: Caller = Depends(caller)) -> dict:
    return {**c.as_dict(), "llm": llm().name}


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
async def list_cases(capability_id: str, team_group: str | None = None,
                     c: Caller = Depends(caller)) -> list[dict]:
    return await cases.list_cases(capability_id, c, team_group)


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


@app.post("/api/cases/{case_id}/decisions", status_code=201)
@_errors
async def decide(case_id: str, body: DecisionIn, c: Caller = Depends(caller)) -> dict:
    result = await cases.decide(case_id, body.group_id, body.action, body.comment,
                                body.idempotency_key, c)
    return {**result, "case": await cases.case_detail(case_id, c)}


class PublishIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)


@app.post("/api/cases/{case_id}/publish", status_code=201)
@_errors
async def release_publish(case_id: str, body: PublishIn, c: Caller = Depends(caller)) -> dict:
    result = await cases.approve_publish(case_id, body.idempotency_key, c)
    return {**result, "case": await cases.case_detail(case_id, c)}


@app.get("/api/cases/{case_id}/documents/{name}")
@_errors
async def case_document(case_id: str, name: str, c: Caller = Depends(caller)) -> FileResponse:
    """A report this case published (e.g. its PDF), for people who can see the case."""
    from helix.mcp_services.documents import DocumentError, report_path

    scope, name = await cases.published_document(case_id, name, c)
    try:
        path = report_path(scope, name)
    except DocumentError as e:
        raise LookupError(str(e)) from e
    return FileResponse(path, media_type="application/pdf" if name.lower().endswith(".pdf") else None,
                        filename=name)


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
