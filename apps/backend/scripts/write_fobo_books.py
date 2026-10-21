"""Write the FOBO groups' master books as reference data, from the stub's book list.

    .venv/bin/python scripts/write_fobo_books.py

Writes config/agent-one-finance/knowledge/fobo-books-<group>.yaml for Rates and FI
Credit: the FOBO group (its id and name, which names the regional tasks), one node
per book (business, region, desk, product, label), its desk and the team the desk
escalates to. The books are agent_one_finance/stub_connectors/fobo_books.py's, so
CATS, MOTIF and the reference data agree; a test fails if a file is out of date.
"""

from pathlib import Path

from agent_one_finance.stub_connectors import fobo_books

KNOWLEDGE = Path(__file__).resolve().parents[3] / "config/agent-one-finance/knowledge"
VALID_FROM = "2026-10-13"


def path(biz: fobo_books.Business) -> Path:
    return KNOWLEDGE / f"fobo-books-{biz.name.lower().replace(' ', '-')}.yaml"


def render(biz: fobo_books.Business) -> str:
    books = [b for b in fobo_books.BOOKS.values() if b["group"] == biz.group]
    desks = sorted({b["desk"]: b["region"] for b in books}.items())
    team = f"{biz.name} desk"
    first = books[0]
    lines = [
        f"# {biz.name} master books (FOBO group {biz.group}) in APAC, EMEA and the Americas, in",
        "# FOBO's reference data (the namespace of fobo-reference.yaml): the group and its name,",
        "# each book's business, region, desk and product, and the label it is named by — e.g.",
        f"# \"{first['label']}\". Generated from the stub's books by",
        "# apps/backend/scripts/write_fobo_books.py; do not edit by hand.",
        "",
        "namespace: fobo-reference",
        f"valid_from: {VALID_FROM}",
        "",
        "nodes:",
        f'  - {{ id: "group:{biz.group}", kind: fobo_group, attrs: {{ name: {biz.name}, business: {biz.name} }} }}',
    ]
    if f'"team:{team}"' not in (KNOWLEDGE / "fobo-reference.yaml").read_text():     # Rates desk is already there
        lines.append(f'  - {{ id: "team:{team}", kind: team, attrs: {{ name: {team} }} }}')
    for desk, region in desks:
        lines.append(f'  - {{ id: "desk:{desk}", kind: desk, attrs: {{ name: {desk}, business: {biz.name}, '
                     f'region: {region}, owner_team: {team} }} }}')
    for b in books:
        lines.append(f'  - {{ id: "book:{b["book"]}", kind: book, attrs: {{ name: {b["book"]}, legal_entity: {b["legal_entity"]}, '
                     f'business: {b["business"]}, region: {b["region"]}, desk: {b["desk"]}, product: "{b["product"]}", '
                     f'label: "{b["label"]}" }} }}')
    lines += ["", "edges:"]
    for desk, _ in desks:
        lines.append(f'  - {{ from: "desk:{desk}", relation: escalates_to, to: "team:{team}" }}')
    for b in books:
        lines.append(f'  - {{ from: "book:{b["book"]}", relation: belongs_to, to: "desk:{b["desk"]}" }}')
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    for biz in fobo_books.BUSINESSES.values():
        path(biz).write_text(render(biz))
        print(f"{path(biz)}: {sum(b['group'] == biz.group for b in fobo_books.BOOKS.values())} books")
