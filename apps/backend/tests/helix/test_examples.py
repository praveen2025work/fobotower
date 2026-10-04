"""The worked examples in docs/helix/examples are real configuration: each
one validates, and the only problems allowed are connectors it says it needs."""

from pathlib import Path

import pytest
import yaml

from helix.capabilities import seed_files
from helix.groups import GroupConfig, effective
from helix.manifest import Manifest, problems

EXAMPLES = Path(__file__).resolve().parents[4] / "docs" / "helix" / "examples"
# example -> tools it needs onboarded (none = runs on today's connectors)
NEEDS = {
    "accruals-review.yaml": set(),
    "balance-sheet-substantiation.yaml": set(),
    "journal-entry-controls.yaml": {"gl.journal_entries"},
    "suspense-clearing.yaml": {"gl.suspense_items", "gl.post_journal"},
    "intercompany-recon.group.yaml": {"ic.receivables", "ic.payables"},
}


def _found(path: Path) -> list[str]:
    doc = yaml.safe_load(path.read_text())
    if path.name.endswith(".group.yaml"):
        base = next(m for m in seed_files() if m.id == "recon.investigation")
        _, found = effective(base, GroupConfig.model_validate(doc))
        return found
    return problems(Manifest.model_validate(doc))


@pytest.mark.parametrize("name", sorted(NEEDS))
def test_each_example_validates_except_for_the_connectors_it_names(name):
    found = _found(EXAMPLES / name)
    missing = {p.split("`")[1] for p in found if "is not an onboarded connector tool" in p}
    other = [p for p in found if "is not an onboarded connector tool" not in p
             and not p.startswith("publish.tool")]       # an un-onboarded write tool cannot be checked for access
    assert other == [] and missing == NEEDS[name]


def test_every_example_file_is_listed():
    assert {p.name for p in EXAMPLES.glob("*.yaml")} == set(NEEDS)
