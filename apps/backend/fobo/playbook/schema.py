"""The playbook's shape, and the cross-references it must satisfy.

Validation is the point of this module. Product Control edits the YAML by
hand; a test that names a component that does not exist, or a finding that
indicates category Z, must fail the load — not surface halfway through an
investigation as a KeyError, or worse, as a silently missing rule.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Side = Literal["FO", "BO"]
FindingSide = Literal["FO", "BO", "NEITHER"]
Verdict = Literal["POST", "DO_NOT_POST", "ESCALATE", "CORRECT_AND_REPOST"]
Determinism = Literal["deterministic", "judgement"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PolicyParam(Strict):
    value: float | int | str | None = None
    unit: str | None = None
    used_by: str


class TestDef(Strict):
    side: Side
    validates: str
    checks: str
    on_fail: str | None = None
    evidence: list[str] = Field(default_factory=list)
    requires_on_fail: list[str] = Field(default_factory=list)
    policy: list[str] = Field(default_factory=list)


class FindingDef(Strict):
    test: str
    side: FindingSide
    indicates: str | None = None
    description: str


class CategoryDef(Strict):
    name: str
    determinism: Determinism
    escalate_to: str


class CauseCheckDef(Strict):
    category: str
    # UNKNOWN: the check proves a difference, not which side is wrong.
    side: Literal["FO", "BO", "UNKNOWN"]
    reason: str


class Playbook(Strict):
    version: str
    effective_from: date
    source: str | None = None
    policy: dict[str, PolicyParam]
    components: dict[Side, list[str]]
    tests: dict[str, TestDef]
    findings: dict[str, FindingDef]
    categories: dict[str, CategoryDef]
    default_verdicts: dict[str, dict[Side, Verdict]]
    cause_checks: dict[str, CauseCheckDef]
    teams: list[str]

    @model_validator(mode="after")
    def _cross_references(self) -> "Playbook":
        errors: list[str] = []

        for tid, t in self.tests.items():
            if t.validates not in self.components.get(t.side, []):
                errors.append(f"test {tid}: validates '{t.validates}', not a {t.side} component")
            for dep in t.requires_on_fail:
                if dep not in self.tests:
                    errors.append(f"test {tid}: requires_on_fail names unknown test '{dep}'")
            for p in t.policy:
                if p not in self.policy:
                    errors.append(f"test {tid}: names unknown policy parameter '{p}'")

        for code, f in self.findings.items():
            if f.test not in self.tests:
                errors.append(f"finding {code}: belongs to unknown test '{f.test}'")
            if f.indicates is not None and f.indicates not in self.categories:
                errors.append(f"finding {code}: indicates unknown category '{f.indicates}'")

        for code, c in self.categories.items():
            if c.escalate_to not in self.teams:
                errors.append(f"category {code}: escalates to unknown team '{c.escalate_to}'")
            if code not in self.default_verdicts:
                errors.append(f"category {code}: has no default_verdicts entry")

        for code in self.default_verdicts:
            if code not in self.categories:
                errors.append(f"default_verdicts: unknown category '{code}'")

        for check, c in self.cause_checks.items():
            if c.category not in self.categories:
                errors.append(f"cause_check {check}: maps to unknown category '{c.category}'")

        # R2 in the data too: an FO cause must never default to POST. The
        # guards enforce this in code regardless, but a playbook that says
        # otherwise is wrong and should not load.
        for code, by_side in self.default_verdicts.items():
            if by_side.get("FO") == "POST":
                errors.append(
                    f"default_verdicts {code}: FO -> POST breaks R2 "
                    "(an FO-side cause must never post)"
                )

        if errors:
            raise ValueError("playbook is invalid:\n  - " + "\n  - ".join(errors))
        return self
