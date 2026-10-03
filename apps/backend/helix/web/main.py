"""The Helix API: `uvicorn helix.web.main:app --port 8300`.

Identity comes from one request header (HELIX_IDENTITY_HEADER, set by the
SSO proxy in the office; the console's user switcher in development); roles
and data scopes come from the entitlement service, never from the request.
"""

from contextlib import asynccontextmanager
from functools import wraps

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from helix import capabilities, cases
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
        except capabilities.CapabilityError as e:
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


@app.get("/api/capabilities")
async def list_capabilities(c: Caller = Depends(caller)) -> list[dict]:
    return [{"id": m.id, "name": m.name, "description": m.description, "version": v,
             "case_label": m.case.label, "item_label": m.case.item_label,
             "case_key": m.case.key, "steps": m.steps,
             "is_owner": capabilities.is_owner(c, m),
             "can_decide": c.has_any_role(m.review.roles)}
            for v, m in await capabilities.all_active() if capabilities.can_see(c, m)]


@app.get("/api/capabilities/{capability_id}")
@_errors
async def get_capability(capability_id: str, c: Caller = Depends(caller)) -> dict:
    version, m = await capabilities.active(capability_id)
    if not capabilities.can_see(c, m):
        raise LookupError(capability_id)
    return {"version": version, "manifest": m.model_dump(by_alias=True),
            "versions": await capabilities.versions(capability_id)}


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
async def list_cases(capability_id: str, c: Caller = Depends(caller)) -> list[dict]:
    return await cases.list_cases(capability_id, c)


class OpenIn(BaseModel):
    case_key: dict


@app.post("/api/capabilities/{capability_id}/cases", status_code=201)
@_errors
async def open_case(capability_id: str, body: OpenIn, c: Caller = Depends(caller)) -> dict:
    case_id = await cases.open_case(capability_id, body.case_key, c)
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


@app.get("/api/platform")
async def platform(c: Caller = Depends(caller)) -> dict:
    """What this Helix instance offers: steps, connector tools, adapters."""
    reg = registry()
    return {
        "steps": catalogue(),
        "connectors": [{"id": cid, "name": spec.name, "transport": spec.transport,
                        "classification": spec.classification,
                        "tools": [{"name": f"{cid}.{t}", "description": ts.description,
                                   "scope": ts.scope.model_dump() if ts.scope else None}
                                  for t, ts in spec.tools.items()]}
                       for cid, spec in reg.connectors.items()],
        "llm": llm().name,
        "entitlement": "central" if settings().entitlement_url else "dev-stub",
    }
