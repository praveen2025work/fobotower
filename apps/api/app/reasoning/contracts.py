"""The structured verdict the skill's §12 output format requires.

Shaped to the skill document, not to what is convenient to render: a model
that cannot express "root cause not established" or "requires SME review"
would force the reasoner to assert something it does not know.
"""

from typing import Literal

from pydantic import BaseModel, Field

TestResult = Literal["Pass", "Fail", "Unable to test"]

Verdict = Literal["POST", "DO_NOT_POST", "ESCALATE", "CORRECT_AND_REPOST"]

CATEGORY_NAMES = {
    "A": "Price break",
    "B": "Pull factor break",
    "C": "Redemption break",
    "D": "Settlement break",
    "E": "Trade booking break",
    "F": "Data quality break",
    "G": "Corporate action break",
    "H": "Novel break",
}


class CheckPerformed(BaseModel):
    """One row of §12.2 — Checks performed."""

    test_id: str = Field(description="e.g. FO-3, BO-6")
    checked: str = Field(description="What was checked, in one phrase")
    result: TestResult
    evidence: str = Field(
        description="The evidence relied on, or why the test could not be run"
    )


class RootCause(BaseModel):
    established: bool = Field(
        description="False when the evidence does not support a single cause. "
        "R6: unknown root cause is an escalation outcome, not a posting outcome."
    )
    statement: str = Field(description="Single clear statement of the cause")
    contributing: list[str] = Field(
        default_factory=list,
        description="Ranked secondary causes, most significant first",
    )
    side: Literal["FO", "BO", "BOTH", "NEITHER", "UNKNOWN"] = Field(
        description="Which side the cause originates in"
    )


class Classification(BaseModel):
    category_code: Literal["A", "B", "C", "D", "E", "F", "G", "H"]
    category_name: str
    secondary_code: str | None = None
    deterministic: bool = Field(
        description="True applies a codified rule (R7); false routes to SME review"
    )


class Remediation(BaseModel):
    who_to_engage: list[str]
    what_to_raise: list[str]
    preventative_control: str | None = Field(
        default=None,
        description="A proposed MBREC or validation rule that would catch this earlier",
    )


class SkillVerdict(BaseModel):
    """The full §12 output."""

    break_summary: str
    checks_performed: list[CheckPerformed]
    root_cause: RootCause
    classification: Classification
    verdict: Verdict
    verdict_reason: str
    remediation: Remediation
    end_state_validation: str = Field(
        description="Confirm BO + Adjustments = FO, or state the investigation remains open"
    )
    requires_sme_review: bool = Field(
        description="R7: judgement-based findings are recommended, not asserted"
    )
    competing_hypotheses: list[str] = Field(
        default_factory=list,
        description="R7: for judgement-based breaks, the alternatives and their evidence",
    )
    unset_parameters: list[str] = Field(
        default_factory=list,
        description="Rule P1: local parameters this conclusion depends on that were "
        "not supplied. Never substitute a plausible-sounding number.",
    )
