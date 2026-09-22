"""Role-based node visibility.

Enforced by injecting a predicate into every query before execution.
Post-filtering is prohibited: it leaks through counts and timing, and a
prompt instruction is not an access control.
"""

from sqlalchemy import and_

from app.contracts.models import Caller
from app.db.models_graph import Node

VISIBILITY: dict[str, set[str]] = {
    "Trade": {"FO", "PC", "RISK"},
    "Position": {"FO", "RISK"},
    "LedgerEntry": {"BO", "PC", "REG"},
    "StaticMapping": {"BO", "REG"},
    "Adjustment": {"BO", "PC"},
    "RiskRun": {"FO", "RISK"},
    "Job": {"FO", "BO", "PC"},
    "Book": {"FO", "BO", "PC", "REG", "RISK"},
    "Desk": {"FO", "BO", "PC", "REG", "RISK"},
}


def visible_node_types(roles: list[str]) -> set[str]:
    return {nt for nt, allowed in VISIBILITY.items() if allowed & set(roles)}


def build_entitlement_predicate(caller: Caller):
    return and_(
        Node.node_type.in_(visible_node_types(caller.roles)),
        Node.legal_entity_id.in_(caller.entity_scope),
    )
