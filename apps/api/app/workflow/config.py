"""Workflow configuration: which steps run, in what order, with what settings.

Loaded from config/workflow/fobo-investigation.yaml and validated against the
step registry before any run starts. The validator exists so the order can be
edited safely — a step placed before the step whose output it needs, or a
safety step removed, is refused with a message naming the problem.
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PATH = REPO_ROOT / "config" / "workflow" / "fobo-investigation.yaml"

REASONERS = ("none", "session_service", "direct")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GatherSettings(Strict):
    priors_lookback_days: int = Field(180, ge=1, le=3650)
    # Recursion ceiling for the lineage walk.
    lineage_max_depth: int = Field(4, ge=1, le=4)
    max_similar_breaks: int = Field(20, ge=1, le=500)


class ReasonSettings(Strict):
    reasoner: str = "none"
    verdict_policy_params: list[str] = Field(
        default_factory=lambda: ["materiality_threshold", "posting_policy_reference"]
    )

    @model_validator(mode="after")
    def _known_reasoner(self) -> "ReasonSettings":
        if self.reasoner not in REASONERS:
            raise ValueError(
                f"reason.reasoner '{self.reasoner}' is not one of {', '.join(REASONERS)}"
            )
        return self


class ValidateSettings(Strict):
    max_hypothesis_attempts: int = Field(3, ge=1, le=10)


class ReviewSettings(Strict):
    max_review_cycles: int = Field(2, ge=1, le=10)


class SessionServiceSettings(Strict):
    timeout_seconds: float = Field(120.0, gt=0, le=1800)


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
    """The active workflow, validated once per process."""
    return read_workflow()


def reset_workflow_cache() -> None:
    workflow.cache_clear()


def settings() -> Settings:
    return workflow().settings
