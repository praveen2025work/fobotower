"""Development caller stub.

Constructs the same Caller object real auth would. Swapping to BAM plus the
entitlement service touches this module and nothing else — which is the
whole reason the Caller is built in one place.

In development (FOBO_ENV=dev) a request may act as another dev caller by
sending X-Dev-Caller. That exists so a workflow change drafted by one person
can be approved by a second; outside dev the header is ignored.
"""

import os
from contextvars import ContextVar

from fastapi.responses import JSONResponse

from app.contracts.models import Caller

DEV_CALLER = Caller(
    staff_id="praveen",
    roles=["FO", "PC"],
    entity_scope=["LE-APAC-01"],
    region="APAC",
)

DEV_CALLERS: dict[str, Caller] = {
    "praveen": DEV_CALLER,
    "asha": Caller(
        staff_id="asha",
        roles=["PC"],
        entity_scope=["LE-APAC-01"],
        region="APAC",
    ),
}

DEV_CALLER_HEADER = "X-Dev-Caller"

_caller: ContextVar[Caller | None] = ContextVar("fobo_caller", default=None)


def dev_mode() -> bool:
    return os.getenv("FOBO_ENV", "").strip().lower() == "dev"


def current_caller() -> Caller:
    return _caller.get() or DEV_CALLER


def dev_callers() -> list[dict] | None:
    """The callers the console may switch between; None outside dev."""
    if not dev_mode():
        return None
    return [{"id": c.staff_id, "roles": list(c.roles)} for c in DEV_CALLERS.values()]


async def dev_caller_middleware(request, call_next):
    """Act as another dev caller for this request, when FOBO_ENV=dev."""
    name = request.headers.get(DEV_CALLER_HEADER)
    if not name or not dev_mode():
        return await call_next(request)
    caller = DEV_CALLERS.get(name.strip().lower())
    if caller is None:
        return JSONResponse(
            status_code=400,
            content={"detail": f"unknown dev caller '{name}' — use one of: "
                               f"{', '.join(DEV_CALLERS)}"},
        )
    token = _caller.set(caller)
    try:
        return await call_next(request)
    finally:
        _caller.reset(token)
