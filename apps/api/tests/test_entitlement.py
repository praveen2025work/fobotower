import pytest

from app.graph.entitlement import visible_node_types

MATRIX = {
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


@pytest.mark.parametrize("role", ["FO", "BO", "PC", "REG", "RISK"])
def test_visibility_matrix_matches_the_spec(role):
    visible = visible_node_types([role])
    expected = {nt for nt, roles in MATRIX.items() if role in roles}
    assert visible == expected


def test_a_back_office_caller_cannot_see_trades():
    assert "Trade" not in visible_node_types(["BO"])


def test_a_front_office_caller_cannot_see_ledger_entries():
    assert "LedgerEntry" not in visible_node_types(["FO"])


def test_roles_union():
    assert "Trade" in visible_node_types(["BO", "FO"])
    assert "LedgerEntry" in visible_node_types(["BO", "FO"])


def test_unknown_role_grants_nothing():
    assert visible_node_types(["NOBODY"]) == set()
