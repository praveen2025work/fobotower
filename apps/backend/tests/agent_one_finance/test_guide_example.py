"""The guide's example (docs/agent-one-finance/guide/example) is real configuration:
the capability and its group pass every platform check, as they did when the
example was set up, and the steps the README shows are the steps it runs."""

from pathlib import Path

import pytest
import yaml

from agent_one_finance import groups
from agent_one_finance.manifest import Manifest, problems

EXAMPLE = Path(__file__).resolve().parents[4] / "docs" / "agent-one-finance" / "guide" / "example"
# The example lives in the AOF repository's docs; a repo that takes only the code skips this file.
pytestmark = pytest.mark.skipif(not EXAMPLE.is_dir(), reason="no docs/agent-one-finance/guide/example here")


def _load(name: str) -> dict:
    return yaml.safe_load((EXAMPLE / name).read_text())


def test_the_example_capability_and_group_pass_every_check():
    m = Manifest.model_validate(_load("capability.yaml"))
    assert problems(m) == []
    assert groups.check(m, _load("group.yaml")) == []


def test_the_example_runs_the_steps_its_readme_shows():
    m = Manifest.model_validate(_load("capability.yaml"))
    assert m.steps == ["load", "enrich", "classify", "group", "reason", "draft", "validate", "review", "record"]
    assert m.pause_before == ["reason", "review"]
    assert m.owners.four_eyes
