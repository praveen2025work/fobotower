"""Write the FI Credit master books as reference data, from the stub's book list.

    .venv/bin/python scripts/write_fi_credit_books.py

Writes config/agent-one-finance/knowledge/fobo-books-fi-credit.yaml: one node per book
(business, region, desk, product, label), its desk and the team the desk escalates
to. The books are agent_one_finance/stub_connectors/fi_credit.py's, so CATS, MOTIF and
the reference data agree; a test fails if the file is out of date.
"""

from pathlib import Path

from agent_one_finance.stub_connectors import fi_credit

OUT = Path(__file__).resolve().parents[3] / "config/agent-one-finance/knowledge/fobo-books-fi-credit.yaml"
VALID_FROM = "2026-10-13"


def render() -> str:
    desks = sorted({b["desk"]: b["region"] for b in fi_credit.BOOKS.values()}.items())
    lines = [
        "# FI Credit master books in APAC, EMEA and the Americas, in FOBO's reference data",
        "# (the namespace of fobo-reference.yaml): each book's business, region, desk and",
        "# product, and the label tasks are named by — e.g. \"FI Credit APAC · Asia IG bonds",
        "# (FIC-APAC-0001)\". Generated from the stub's books by",
        "# apps/backend/scripts/write_fi_credit_books.py; do not edit by hand.",
        "",
        "namespace: fobo-reference",
        f"valid_from: {VALID_FROM}",
        "",
        "nodes:",
        '  - { id: "team:FI Credit desk", kind: team, attrs: { name: FI Credit desk } }',
    ]
    for desk, region in desks:
        lines.append(f'  - {{ id: "desk:{desk}", kind: desk, attrs: {{ name: {desk}, business: {fi_credit.BUSINESS}, '
                     f'region: {region}, owner_team: FI Credit desk }} }}')
    for b in fi_credit.BOOKS.values():
        lines.append(f'  - {{ id: "book:{b["book"]}", kind: book, attrs: {{ name: {b["book"]}, legal_entity: {b["legal_entity"]}, '
                     f'business: {b["business"]}, region: {b["region"]}, desk: {b["desk"]}, product: "{b["product"]}", '
                     f'label: "{b["label"]}" }} }}')
    lines += ["", "edges:"]
    for desk, _ in desks:
        lines.append(f'  - {{ from: "desk:{desk}", relation: escalates_to, to: "team:FI Credit desk" }}')
    for b in fi_credit.BOOKS.values():
        lines.append(f'  - {{ from: "book:{b["book"]}", relation: belongs_to, to: "desk:{b["desk"]}" }}')
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"{OUT}: {len(fi_credit.BOOKS)} books")
