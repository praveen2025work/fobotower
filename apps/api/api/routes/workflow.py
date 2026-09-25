"""The Workflow tab: see the graph, draft a change, approve it as a second person.

Every rule is enforced in app/workflow/versions.py; this module only maps
HTTP onto it. Errors raised there become responses through the VersionError
handler in api/main.py.
"""

import os

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field

from api.auth import current_caller, dev_callers
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import REASONERS, dump_config, settings_schema
from app.workflow.diff import diff, rebase
from app.workflow.graph_view import graph_view
from app.workflow.registry import catalogue
from app.workflow.yaml_io import YamlError, parse_yaml, to_yaml

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class ConfigBody(BaseModel):
    config: dict


class DraftBody(BaseModel):
    config: dict
    note: str = ""
    based_on: int


class YamlBody(BaseModel):
    yaml: str = Field(max_length=70_000)
    note: str = ""


class RejectBody(BaseModel):
    reason: str = ""


def _overrides() -> dict:
    env = os.getenv("FOBO_REASONER", "").strip().lower()
    return {"reasoner": env} if env else {}


def _caller_view() -> dict:
    c = current_caller()
    return {"id": c.staff_id, "roles": list(c.roles)}


@router.get("")
async def overview() -> dict:
    async with get_session() as s:
        cur = await versions.active(s)
        body = {
            "active": versions.view(await versions.get(s, cur.number)),
            "steps": catalogue(),
            "settings_schema": settings_schema(),
            "reasoners": list(REASONERS),
            "overrides": _overrides(),
            "pending_drafts": await versions.pending_count(s),
            "caller": _caller_view(),
        }
    callers = dev_callers()
    if callers:
        body["dev_callers"] = callers
    return body


@router.get("/graph")
async def graph(version: int | None = None) -> dict:
    """The compiled graph and its decision logic, for a version (default:
    active). Everything the console shows about routing comes from here."""
    async with get_session() as s:
        pinned = await (versions.pinned(s, version) if version is not None
                        else versions.active(s))
        body = graph_view(pinned.config, pinned.number)
    return body | {"reasoner_override": _overrides().get("reasoner")}


@router.get("/versions")
async def history() -> list[dict]:
    async with get_session() as s:
        return [versions.view(r, with_config=False) for r in await versions.list_versions(s)]


@router.get("/versions/{number}")
async def one(number: int) -> dict:
    async with get_session() as s:
        # active() first: it seeds v1 when the table is still empty, which
        # get() (a plain primary-key lookup) does not do on its own.
        cur = await versions.active(s)
        row = await versions.get(s, number)
        body = versions.view(row)
    changes = diff(dump_config(cur.config), body["config"])
    return body | {"active_number": cur.number, "diff": [c.as_dict() for c in changes]}


@router.get("/versions/{number}/yaml")
async def as_yaml(number: int) -> Response:
    async with get_session() as s:
        await versions.ensure_seeded(s)
        row = await versions.get(s, number)
    return Response(
        to_yaml(row), media_type="text/yaml",
        headers={"Content-Disposition":
                 f'attachment; filename="fobo-investigation-v{number}.yaml"'},
    )


@router.get("/versions/{number}/rebased")
async def rebased(number: int) -> dict:
    async with get_session() as s:
        # active() first: see the note in one() above.
        cur = await versions.active(s)
        row = await versions.get(s, number)
        if row.status != "draft" or row.based_on is None:
            raise versions.Conflict(f"v{number} is {row.status}; only a draft can be redrafted")
        base = dump_config(versions.as_config((await versions.get(s, row.based_on)).config))
    merged, conflicts = rebase(base, dump_config(versions.as_config(row.config)),
                               dump_config(cur.config))
    return {"config": merged, "based_on": cur.number, "conflicts": conflicts,
            "errors": versions.validation_errors(merged)}


@router.post("/validate")
async def check(body: ConfigBody) -> dict:
    errors = versions.validation_errors(body.config)
    return {"ok": not errors, "errors": errors}


@router.post("/drafts", status_code=201)
async def draft(body: DraftBody) -> dict:
    async with get_session() as s:
        row = await versions.create_draft(
            s, raw=body.config, note=body.note, based_on=body.based_on, caller=current_caller())
        return versions.view(row)


@router.post("/drafts/yaml", status_code=201)
async def draft_from_yaml(body: YamlBody) -> dict:
    try:
        raw = parse_yaml(body.yaml)
    except YamlError as exc:
        raise versions.Invalid("the YAML could not be read", [str(exc)]) from exc
    async with get_session() as s:
        cur = await versions.active(s)
        row = await versions.create_draft(
            s, raw=raw, note=body.note, based_on=cur.number, caller=current_caller())
        return versions.view(row)


@router.post("/versions/{number}/approve")
async def approve(number: int, idempotency_key: str = Header(alias="Idempotency-Key")) -> dict:
    async with get_session() as s:
        row = await versions.approve(s, number, caller=current_caller(), key=idempotency_key)
        return versions.view(row)


@router.post("/versions/{number}/reject")
async def reject(number: int, body: RejectBody) -> dict:
    async with get_session() as s:
        row = await versions.reject(s, number, caller=current_caller(), reason=body.reason)
        return versions.view(row)
