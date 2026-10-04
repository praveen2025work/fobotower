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


class KnowledgeSpec(Strict):
    """What the capability learns from and looks up in the knowledge graph."""
    # Fields whose values link a decision to the things it concerns
    # (account, book, counterparty…), so priors come from related groups too.
    entities: list[str] = Field(default_factory=list)
    # The reference namespace (config/helix/knowledge/<file>.yaml) `resolve` reads.
    reference: str | None = None
    # The case-key field holding the business date reference data is read as of.
    as_of: str | None = None


class ResolveSpec(Strict):
    """One lookup the `resolve` step makes per item, e.g. a book's desk."""
    node: str                          # start node template, e.g. "book:{book}"
    path: list[str]                    # relations to follow, e.g. [belongs_to]
    as_: str = Field(alias="as")       # the item field to set
    take: str = "name"                 # an attribute of the node reached, or "id"
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RetentionSpec(Strict):
    """How long the capability's finished cases are kept (legal hold aside)."""
    days: int = Field(ge=1)


class ReasoningSpec(Strict):
    reasoner: Literal["llm", "none"] = "llm"
    skill: str = ""                    # instructions to the model
    tools: list[str] = Field(default_factory=list)   # tools the model may call
    output: Literal["verdict", "commentary", "classification"] = "commentary"


class PublishSpec(Strict):
    """Write approved results back to a bank system, after a second approval."""
    tool: str                          # a connector tool with access: write
    # group: one call per approved group (e.g. commentary per account);
    # case: one call for the whole case (e.g. one PDF report)
    per: Literal["group", "case"] = "group"
    # Argument values: literals, "$case.<field>", "$case_id", "$subject".
    # per group: "$group.<field>" (group key), "$comment" (the approved
    #   explanation: the reviewer's comment, else the finding's).
    # per case: "$approved" (one section per approved group: heading, body,
    #   columns, rows), "$sign_off" (who decided, who released, when).
    args: dict[str, Any] = Field(default_factory=dict)
    approver_roles: list[str]          # who may release the write-back

    def arg_problems(self) -> list[str]:
        only = {"group": ("$group.", "$comment"), "case": ("$approved", "$sign_off")}
        wrong = only["case" if self.per == "group" else "group"]
        return [f"publish.args.{k}: `{v}` cannot be used with per: {self.per}"
                for k, v in self.args.items() if isinstance(v, str) and v.startswith(wrong)]


class ReviewSpec(Strict):
    roles: list[str]                   # who may decide
    approve_by: Literal["group"] = "group"
    # When a decision must carry the reviewer's own words.
    require_comment: list[Literal["reject", "escalated"]] = Field(
        default_factory=lambda: ["reject", "escalated"])
    # Maker-checker: may whoever opened the case also sign it off?
    opener_may_decide: bool = True
    # Expression over a group (total, count, its key fields, policy): when it
    # holds, the group needs approvals from two different people.
    dual_review_when: str | None = None
    # How often a reviewer may send one group back to be investigated again.
    max_reinvestigations: int = Field(default=2, ge=0, le=10)


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
    knowledge: KnowledgeSpec = Field(default_factory=KnowledgeSpec)
    resolve: list[ResolveSpec] = Field(default_factory=list)
    retention: RetentionSpec | None = None
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


def _expressions(m: Manifest) -> list[tuple[str, str | None]]:
    """Every expression in a manifest, named for the error message."""
    return [("items.in_scope", m.items.in_scope),
            *[(f"rules[{r.id}].when", r.when) for r in m.rules],
            ("review.dual_review_when", m.review.dual_review_when)]


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
    if m.publish:
        out += m.publish.arg_problems()
    reads = set(m.reasoning.tools) | ({m.items.load.tool} if m.items.load else set())
    if m.match:
        reads |= {m.match.left.tool, m.match.right.tool}
    for t in sorted(reads):
        if (found := reg.tool(t)) and found[2].access == "write":
            out.append(f"tool `{t}` writes to a bank system; only `publish` may use it")
    if "resolve" in m.steps and not (m.resolve and m.knowledge.reference):
        out.append("step `resolve` needs `resolve` lookups and `knowledge.reference`")
    if m.knowledge.as_of and m.knowledge.as_of not in m.case.key:
        out.append(f"knowledge.as_of: `{m.knowledge.as_of}` is not in case.key")
    if "compare" in m.steps and m.compare is None:
        out.append("step `compare` needs a `compare` section")
    if "load" not in m.steps and "match" not in m.steps:
        out.append("a workflow needs `load` or `match` to have items")

    onboarded = set(registry().all_tools())
    for tool in sorted(m.tools_used() - onboarded):
        out.append(f"tool `{tool}` is not an onboarded connector tool")

    for name, src in _expressions(m):
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
        if head in ("id", "owners", "configurable", "steps", "pause_before", "publish", "retention"):
            out.append(f"configurable: `{path}` cannot be set by a group "
                       "(identity, ownership, workflow gates, write-back and retention stay with the capability)")
    if m.reasoning.reasoner == "llm" and not m.reasoning.skill.strip():
        out.append("reasoning.skill: an llm reasoner needs instructions")
    return out
