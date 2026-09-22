"""Development caller stub.

Constructs the same Caller object real auth would. Swapping to BAM plus the
entitlement service touches this function and nothing else — which is the
whole reason the Caller is built in one place.
"""

from app.contracts.models import Caller

DEV_CALLER = Caller(
    staff_id="praveen",
    roles=["FO", "PC"],
    entity_scope=["LE-APAC-01"],
    region="APAC",
)


def current_caller() -> Caller:
    return DEV_CALLER
