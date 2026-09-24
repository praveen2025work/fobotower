"""Workflow configuration: which steps run, in what order, with what settings.

Loaded from config/workflow/fobo-investigation.yaml and validated against the
step registry before any run starts. The validator exists so the order can be
edited safely — a step placed before the step whose output it needs, or a
safety step removed, is refused with a message naming the problem.
"""

import os
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import get_origin

import yaml
from annotated_types import Ge, Gt, Le
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = REPO_ROOT / "config" / "workflow" / "fobo-investigation.yaml"

REASONERS = ("none", "session_service", "direct")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GatherSettings(Strict):
    priors_lookback_days: int = Field(
        180, ge=1, le=3650, description="How far back to look for prior resolutions, in days")
    # Recursion ceiling for the lineage walk.
    lineage_max_depth: int = Field(
        4, ge=1, le=4, description="Desk and entity hops to walk when tracing lineage")
    max_similar_breaks: int = Field(
        20, ge=1, le=500, description="Prior resolutions kept per book")


class ReasonSettings(Strict):
    reasoner: str = Field(
        "none",
        description="Who handles breaks the playbook cannot settle: none (a person), "
                    "session_service (the Agent SDK session service), direct (local development)")
    verdict_policy_params: list[str] = Field(
        default_factory=lambda: ["materiality_threshold", "posting_policy_reference"],
        description="Policy thresholds a POST verdict depends on; when any is unset the "
                    "POST needs controller confirmation (Rule P1)",
    )

    @model_validator(mode="after")
    def _known_reasoner(self) -> "ReasonSettings":
        if self.reasoner not in REASONERS:
            raise ValueError(
                f"reason.reasoner '{self.reasoner}' is not one of {', '.join(REASONERS)}"
            )
        return self


class ValidateSettings(Strict):
    max_hypothesis_attempts: int = Field(
        3, ge=1, le=10, description="Retries before RETRY_EXHAUSTED")


class ReviewSettings(Strict):
    max_review_cycles: int = Field(
        2, ge=1, le=10, description="Reject-and-redraft rounds before escalation")


class SessionServiceSettings(Strict):
    timeout_seconds: float = Field(
        120.0, gt=0, le=1800, description="Seconds allowed per judgement-based break")


class Settings(Strict):
    gather: GatherSettings = Field(default_factory=GatherSettings)
    reason: ReasonSettings = Field(default_factory=ReasonSettings)
    validate_: ValidateSettings = Field(default_factory=ValidateSettings, alias="validate")
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    session_service: SessionServiceSettings = Field(default_factory=SessionServiceSettings)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class WorkflowConfig(Strict):
    version: str
    name: str
    steps: list[str]
    pause_before: list[str]
    settings: Settings = Field(default_factory=Settings)

    @model_validator(mode="after")
    def _order_is_sound(self) -> "WorkflowConfig":
        # Imported here: the registry imports the step code, which reads this
        # module's settings — a module-level import would be circular.
        from app.workflow.registry import (
            INITIAL_INPUTS,
            PAUSE_REQUIRED,
            REQUIRED_STEPS,
            RESUME_INPUTS,
            STEPS,
        )

        errors: list[str] = []

        unknown = [s for s in self.steps if s not in STEPS]
        for s in unknown:
            errors.append(f"steps: '{s}' is not a known step "
                          f"(known: {', '.join(STEPS)})")

        seen: set[str] = set()
        for s in self.steps:
            if s in seen:
                errors.append(f"steps: '{s}' is listed more than once")
            seen.add(s)

        for s in sorted(REQUIRED_STEPS - set(self.steps)):
            errors.append(f"steps: '{s}' cannot be removed — {STEPS[s].required_because}")

        # Data dependencies: every input must be produced by an earlier step.
        # Resume inputs arrive with the controller's decision, which can only
        # happen after the pause, so they count once a paused step is passed.
        available = set(INITIAL_INPUTS)
        paused_yet = False
        for s in self.steps:
            if s not in STEPS:
                continue
            if s in self.pause_before:
                paused_yet = True
            if paused_yet:
                available |= RESUME_INPUTS
            missing = sorted(STEPS[s].needs - available)
            for need in missing:
                producers = [n for n, st in STEPS.items() if need in st.produces]
                hint = f" — produced by {', '.join(producers)}" if producers else ""
                errors.append(f"steps: '{s}' needs '{need}' before it runs{hint}")
            available |= STEPS[s].produces

        position = {s: i for i, s in enumerate(self.steps)}
        for s in self.steps:
            if s not in STEPS:
                continue
            for earlier in STEPS[s].must_follow:
                if earlier in position and position[earlier] > position[s]:
                    errors.append(f"steps: '{s}' must come after '{earlier}'")

        for p in self.pause_before:
            if p not in position:
                errors.append(f"pause_before: '{p}' is not one of the steps")
        for p in sorted(PAUSE_REQUIRED - set(self.pause_before)):
            errors.append(f"pause_before: must include '{p}' — no decision is "
                          "recorded without a person")

        if errors:
            raise ValueError("workflow is invalid:\n  - " + "\n  - ".join(errors))
        return self


def workflow_path() -> Path:
    return Path(os.getenv("FOBO_WORKFLOW_PATH", DEFAULT_PATH))


def read_workflow(path: Path | None = None) -> WorkflowConfig:
    raw = yaml.safe_load((path or workflow_path()).read_text(encoding="utf-8"))
    return WorkflowConfig.model_validate(raw)


@lru_cache(maxsize=1)
def workflow() -> WorkflowConfig:
    """The YAML file's workflow: the seed for version 1, and what settings()
    falls back to outside a run. The API runs whichever version is active in
    the database (app/workflow/versions.py)."""
    return read_workflow()


def reset_workflow_cache() -> None:
    workflow.cache_clear()


# The workflow of the run executing in this context. run_investigation binds
# the run's pinned version for the length of the run; LangGraph copies the
# context into the tasks that execute each step, so every step reads it.
_bound: ContextVar["WorkflowConfig | None"] = ContextVar("fobo_workflow", default=None)


@contextmanager
def use_workflow(cfg: "WorkflowConfig"):
    token = _bound.set(cfg)
    try:
        yield cfg
    finally:
        _bound.reset(token)


def settings() -> Settings:
    """The running workflow's settings: the run's pinned version inside a
    run; the YAML file's outside one (the CLI, and unit tests that call a
    step directly)."""
    return (_bound.get() or workflow()).settings


def dump_config(cfg: WorkflowConfig) -> dict:
    """The config as JSON-safe data, with YAML names (`validate`) and YAML order."""
    return cfg.model_dump(mode="json", by_alias=True)


def errors_of(exc: Exception) -> list[str]:
    """Every problem, one line each, in the validator's own words.

    The CLI, the API's validate endpoint and draft creation all report through
    this, so the file check and the Workflow tab can never disagree.
    """
    if not isinstance(exc, ValidationError):
        return [str(exc)]
    out: list[str] = []
    for e in exc.errors():
        msg = e["msg"].removeprefix("Value error, ")
        if msg.startswith("workflow is invalid:"):
            out += [line.strip().removeprefix("- ")
                    for line in msg.splitlines()[1:] if line.strip()]
            continue
        loc = ".".join(str(p) for p in e["loc"])
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


_TYPE_NAMES = {int: "integer", float: "number", str: "string"}


def _field_type(section: str, name: str, annotation) -> dict:
    if (section, name) == ("reason", "reasoner"):
        return {"type": "enum", "options": list(REASONERS)}
    if get_origin(annotation) is list:
        return {"type": "string_list"}
    return {"type": _TYPE_NAMES[annotation]}


def settings_schema() -> dict[str, dict[str, dict]]:
    """Each setting's type, bounds, default and description, by YAML section.

    Read from the models, so the form in the Workflow tab offers exactly the
    bounds the validator enforces.
    """
    out: dict[str, dict[str, dict]] = {}
    for attr, section_field in Settings.model_fields.items():
        section = section_field.alias or attr
        fields: dict[str, dict] = {}
        for name, f in section_field.annotation.model_fields.items():
            meta = _field_type(section, name, f.annotation) | {
                "default": f.get_default(call_default_factory=True),
                "description": f.description or "",
            }
            for m in f.metadata:
                if isinstance(m, Ge):
                    meta["min"] = m.ge
                elif isinstance(m, Gt):
                    meta["exclusive_min"] = m.gt
                elif isinstance(m, Le):
                    meta["max"] = m.le
            fields[name] = meta
        out[section] = fields
    return out
