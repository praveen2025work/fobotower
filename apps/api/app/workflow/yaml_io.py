"""YAML in and out of the Workflow tab, in the same layout as the repo file."""

import yaml

from app.workflow.config import WorkflowConfig, dump_config

MAX_BYTES = 64 * 1024


class YamlError(ValueError):
    def __init__(self, message: str, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.line = line
        self.column = column


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())


def _decision(row) -> str:
    if not row.decided_by:
        return ""
    verb = "rejected" if row.status == "rejected" else "approved"
    return f"; {verb} by {row.decided_by}"


def to_yaml(row) -> str:
    # Through the model: JSONB does not keep key order, the model does.
    config = dump_config(WorkflowConfig.model_validate(row.config))
    header = [
        f"# FOBO investigation workflow, version {row.number} ({row.status})",
        f"# Drafted by {row.drafted_by}{_decision(row)}.",
        f"# Note: {_one_line(row.note)}",
        "#",
        "# Upload this file in the Workflow tab to propose it as a draft; a second",
        "# Product Control user must approve it before new runs use it.",
        "",
    ]
    body = yaml.safe_dump(config, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return "\n".join(header) + body


def parse_yaml(text: str) -> dict:
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise YamlError(f"the file is {size} bytes; the limit is 64 KB")
    try:
        raw = yaml.safe_load(text)
    except yaml.MarkedYAMLError as exc:
        mark = exc.problem_mark or exc.context_mark
        if mark is None:
            raise YamlError(str(exc)) from exc
        line, column = mark.line + 1, mark.column + 1
        problem = exc.problem or exc.context or "not valid YAML"
        raise YamlError(f"line {line}, column {column}: {problem}", line, column) from exc
    except yaml.YAMLError as exc:
        raise YamlError(str(exc)) from exc
    if not isinstance(raw, dict):
        raise YamlError("the file must be a YAML mapping with steps, pause_before and settings")
    return raw
