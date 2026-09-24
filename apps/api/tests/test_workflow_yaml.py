"""Download a version as YAML, upload YAML as a draft."""

import pytest
import yaml

from app.contracts.models import Caller
from app.db.base import get_session
from app.workflow import versions
from app.workflow.config import dump_config, read_workflow
from app.workflow.yaml_io import MAX_BYTES, YamlError, parse_yaml, to_yaml

PRAVEEN = Caller(staff_id="praveen", roles=["FO", "PC"], entity_scope=["LE-APAC-01"], region="APAC")


async def _seed_row():
    async with get_session() as s:
        await versions.active(s)
        return await versions.get(s, 1)


async def test_a_version_round_trips_through_yaml():
    text = to_yaml(await _seed_row())
    assert parse_yaml(text) == dump_config(read_workflow())


async def test_the_export_keeps_the_repo_files_key_order_despite_jsonb():
    body = yaml.safe_load(to_yaml(await _seed_row()))
    assert list(body) == ["version", "name", "steps", "pause_before", "settings"]


async def test_the_export_says_which_version_and_who():
    text = to_yaml(await _seed_row())
    assert text.startswith("# FOBO investigation workflow, version 1 (active)")
    assert "approved by system" in text


async def test_a_multi_line_note_stays_one_comment_line():
    raw = dump_config(read_workflow())
    async with get_session() as s:
        row = await versions.create_draft(s, raw=raw, note="line one\nline two",
                                          based_on=1, caller=PRAVEEN)
    text = to_yaml(row)
    assert "# Note: line one line two" in text
    assert parse_yaml(text) == raw


def test_unreadable_yaml_names_the_line_and_column():
    with pytest.raises(YamlError) as exc:
        parse_yaml("steps: [resolve,\n  gather\nname: x: y\n")
    assert exc.value.line is not None
    assert str(exc.value).startswith(f"line {exc.value.line}, column ")


def test_a_list_is_not_a_workflow():
    with pytest.raises(YamlError, match="mapping"):
        parse_yaml("- resolve\n- gather\n")


def test_an_oversized_file_is_refused():
    with pytest.raises(YamlError, match="64 KB"):
        parse_yaml("#" * (MAX_BYTES + 1))
