"""The capability manifest: everything a use case is, as configuration.

`Manifest.model_validate` checks shape; `problems(manifest)` checks meaning —
every step exists, the gates are present and in order, every step's inputs
are produced earlier, every tool is an onboarded connector tool, every
expression parses. A manifest with problems is never stored as active.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from helix import rules


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Owners(Strict):
    people: list[str] = Field(default_factory=list)
    role: str | None = None   # a bank role from central entitlements
    four_eyes: bool = True    # the drafter of a change cannot approve it


class CaseSpec(Strict):
    label: str = "Case"               # what the UI calls one unit of work
    item_label: str = "Item"
    key: list[str]                    # fields that identify a case, e.g. [entity, period]
    subject: str | None = None        # display template, e.g. "{entity} · {period}"
    # case-key field -> entitlement data scope it is checked against
    scopes: dict[str, str] = Field(default_factory=dict)
    opens_on: Literal["manual", "api", "schedule", "event"] = "manual"
    schedule: str | None = None       # cron, when opens_on = schedule


class ToolCallSpec(Strict):
    tool: str                          # "connector.tool"
    # literal values, or "$case.<field>" taken from the case key
    args: dict[str, Any] = Field(default_factory=dict)


class ItemsSpec(Strict):
    load: ToolCallSpec | None = None   # used by the `load` step
    id_field: str
    amount_field: str | None = None
    display: list[str] = Field(default_factory=list)  # columns in the generic UI
    in_scope: str | None = None        # expression over one item's fields + policy


class MatchSpec(Strict):
    """Two-sided reconciliation, used by the `match` step."""
    left: ToolCallSpec
    right: ToolCallSpec
    keys: list[str]
    amount_field: str
    tolerance: float = 0.0
    left_label: str = "left"
    right_label: str = "right"


class CompareSpec(Strict):
    """Actual vs baseline, used by the `compare` step: adds `as` to every item."""
    measure: str
    baseline: str
    as_: str = Field(default="variance", alias="as")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PolicyValue(Strict):
    value: Any
    unit: str | None = None


class RuleThen(Strict):
    status: Literal["proposed", "escalated"]
    comment: str = ""                  # template over the group's fields
    reason: str | None = None


class Rule(Strict):
    id: str
    when: str                          # expression over the group's fields
    then: RuleThen


class ReasoningSpec(Strict):
    reasoner: Literal["llm", "none"] = "llm"
    skill: str = ""                    # instructions to the model
    tools: list[str] = Field(default_factory=list)   # tools the model may call
    output: Literal["verdict", "commentary", "classification"] = "commentary"


class PublishSpec(Strict):
    """Write approved results back to a bank system, after a second approval."""
    tool: str                          # a connector tool with access: write
    # literals, "$case.<field>", "$group.<field>" (group key), "$comment" (the
    # approved explanation: the reviewer's comment, else the finding's)
    args: dict[str, Any] = Field(default_factory=dict)
    approver_roles: list[str]          # who may release the write-back


class ReviewSpec(Strict):
    roles: list[str]                   # who may decide
    approve_by: Literal["group"] = "group"


class Manifest(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,62}$")
    name: str
    description: str = ""
    owners: Owners
    case: CaseSpec
    items: ItemsSpec
    match: MatchSpec | None = None
    compare: CompareSpec | None = None
    policy: dict[str, PolicyValue] = Field(default_factory=dict)
    steps: list[str]
    pause_before: list[str] = Field(default_factory=lambda: ["review"])
    group_by: list[str] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    reasoning: ReasoningSpec = Field(default_factory=ReasoningSpec)
    review: ReviewSpec
    publish: PublishSpec | None = None
    # What a group (a team's configuration of this capability, e.g. one rec group)
    # may set: dotted paths; "x.*" = anything under x. Owners stay the capability's.
    configurable: list[str] = Field(default_factory=list)

    def policy_values(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.policy.items()}

    def tools_used(self) -> set[str]:
        used = set(self.reasoning.tools)
        if self.items.load:
            used.add(self.items.load.tool)
        if self.match:
            used |= {self.match.left.tool, self.match.right.tool}
        if self.publish:
            used.add(self.publish.tool)
        return used

    def read_tools(self) -> set[str]:
        return self.tools_used() - ({self.publish.tool} if self.publish else set())

    def visible_to_roles(self) -> set[str]:
        return set(self.review.roles) | ({self.owners.role} if self.owners.role else set())


def problems(m: Manifest) -> list[str]:
    """Everything wrong with a manifest, in plain words. Empty means valid."""
    from helix.gateway import registry
    from helix.workflow import order_problems

    out = order_problems(m.steps, m.pause_before)

    if "load" in m.steps and m.items.load is None:
        out.append("step `load` needs `items.load`")
    if "match" in m.steps and m.match is None:
        out.append("step `match` needs a `match` section")
    if "publish" in m.steps and m.publish is None:
        out.append("step `publish` needs a `publish` section")
    if m.publish and "publish" not in m.steps:
        out.append("a `publish` section needs the `publish` step")
    reg = registry()
    if m.publish and (found := reg.tool(m.publish.tool)) and found[2].access != "write":
        out.append(f"publish.tool `{m.publish.tool}` is not a write tool")
    for t in sorted(set(m.reasoning.tools) | ({m.items.load.tool} if m.items.load else set())):
        if (found := reg.tool(t)) and found[2].access == "write":
            out.append(f"tool `{t}` writes to a bank system; only `publish` may use it")
    if "compare" in m.steps and m.compare is None:
        out.append("step `compare` needs a `compare` section")
    if "load" not in m.steps and "match" not in m.steps:
        out.append("a workflow needs `load` or `match` to have items")

    onboarded = set(registry().all_tools())
    for tool in sorted(m.tools_used() - onboarded):
        out.append(f"tool `{tool}` is not an onboarded connector tool")

    for name, src in [("items.in_scope", m.items.in_scope),
                      *[(f"rules[{r.id}].when", r.when) for r in m.rules]]:
        if src:
            try:
                rules.compile_expr(src)
            except rules.ExpressionError as e:
                out.append(f"{name}: {e}")

    for field in m.case.scopes:
        if field not in m.case.key:
            out.append(f"case.scopes: `{field}` is not in case.key")
    if not m.owners.people and not m.owners.role:
        out.append("owners: name at least one person or a role")
    top = set(Manifest.model_fields)
    for path in m.configurable:
        head = path.split(".")[0]
        if head not in top:
            out.append(f"configurable: `{path}` is not a manifest field")
        if head in ("id", "owners", "configurable", "steps", "pause_before", "publish"):
            out.append(f"configurable: `{path}` cannot be set by a group "
                       "(identity, ownership, workflow gates and write-back stay with the capability)")
    if m.reasoning.reasoner == "llm" and not m.reasoning.skill.strip():
        out.append("reasoning.skill: an llm reasoner needs instructions")
    return out
