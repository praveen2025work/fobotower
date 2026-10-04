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
    schedule: str | None = None       # cron (min hour day month weekday), when opens_on = schedule
    # The keys a scheduled run opens, as templates over the run's date:
    # {today} {yesterday} {prev_business_day} {this_month} {prev_month}
    schedule_keys: list[dict[str, str]] = Field(default_factory=list)
    events: bool = False              # may other systems open cases (POST /api/events)?
    # The service user scheduled and event-opened cases run as — an account in
    # the entitlements system with the roles and data scopes they need.
    opens_as: str | None = None


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


class EnrichSpec(ToolCallSpec):
    """One read the `enrich` step makes per case; its rows are joined onto the
    items by `keys` (e.g. a break snapshot per instrument)."""
    keys: list[str]
    prefix: str = ""                   # put before every joined field name


class CheckSpec(Strict):
    """A deterministic cause check, run on every item by `classify`.
    All checks run; negatives are kept, so a reviewer sees what was ruled out."""
    id: str
    when: str                          # expression over the item: true = the cause is present
    reason: str                        # controller-facing wording (template)
    category: str                      # the category this cause indicates
    side: str = "UNKNOWN"              # which side it implicates; UNKNOWN = not proven


class ValidationTest(Strict):
    """A validation test from the playbook (e.g. FOBO's FO-1…FO-8, BO-1…BO-6),
    run on every item by `classify`: pass, fail, or not run — never guessed."""
    id: str
    side: str                          # FO | BO
    validates: str                     # the component, e.g. Position, Price
    check: str                         # what is checked, in words
    fails_when: str                    # expression over the item: true = the test fails
    on_fail: str = ""                  # what to do when it fails
    needs: list[str] = Field(default_factory=list)      # item fields that must be present
    evidence: list[str] = Field(default_factory=list)   # the evidence those fields come from
    policy: list[str] = Field(default_factory=list)     # thresholds it needs; unset = not run (P1)
    requires_on_fail: list[str] = Field(default_factory=list)  # tests that must have run if this fails
    blocks_post: bool = False          # a failure holds the adjustment


class TestFinding(Strict):
    """What a test's evidence shows (e.g. FO-6 findings A/B/C). A finding that
    indicates a category explains an item no cause check explained."""
    id: str
    test: str
    when: str                          # expression over the item
    description: str
    indicates: str | None = None       # a category, or None (e.g. "proceed to BO validation")
    side: str = "UNKNOWN"


class CategorySpec(Strict):
    name: str
    # deterministic: the verdict table settles it; judgement: the model
    # investigates and a person (SME) decides
    determinism: Literal["deterministic", "judgement"]
    escalate_to: str | None = None     # the team that owns this kind of break


class GuardSpec(Strict):
    """A verdict the code refuses whatever the table or the model says,
    e.g. never POST a cause that originates on the front-office side."""
    verdict: str
    when: str                          # expression over the group (side, category, …)
    instead: str
    reason: str


class PlaybookSpec(Strict):
    """Rules owned by the business: checks, categories, the verdict table and
    the guards over it. The FOBO CATS vs MOTIF playbook is one."""
    checks: list[CheckSpec] = Field(default_factory=list)
    tests: list[ValidationTest] = Field(default_factory=list)
    findings: list[TestFinding] = Field(default_factory=list)
    blocked_verdict: str = "ESCALATE"  # what a POST becomes when a blocking test failed
    categories: dict[str, CategorySpec]
    default_category: str              # when no check is positive (a novel break)
    sides: list[str] = Field(default_factory=lambda: ["FO", "BO"])   # proven sides
    verdicts: dict[str, dict[str, str]] = Field(default_factory=dict)  # category -> side -> verdict
    guards: list[GuardSpec] = Field(default_factory=list)
    escalate_verdicts: list[str] = Field(default_factory=lambda: ["ESCALATE"])
    # Verdicts that need a policy threshold: while any of `verdict_policy` is
    # unset (null), such a verdict is flagged "requires controller confirmation".
    confirm_verdicts: list[str] = Field(default_factory=lambda: ["POST"])
    verdict_policy: list[str] = Field(default_factory=list)
    comment: str = "{category_name}: {reasons}"   # template for a playbook finding

    def verdict_names(self) -> list[str]:
        names = {v for sides in self.verdicts.values() for v in sides.values()}
        names |= {g.instead for g in self.guards} | set(self.escalate_verdicts)
        if self.tests:
            names.add(self.blocked_verdict)
        return sorted(names)


class KnowledgeSpec(Strict):
    """What the capability learns from and looks up in the knowledge graph."""
    # Fields whose values link a decision to the things it concerns
    # (account, book, counterparty…), so priors come from related groups too.
    entities: list[str] = Field(default_factory=list)
    # The reference namespace (config/helix/knowledge/<file>.yaml) `resolve` reads.
    reference: str | None = None
    # The case-key field holding the business date reference data is read as of.
    as_of: str | None = None
    # Only decisions this recent are used as priors (FOBO: 180 days). None = all.
    priors_lookback_days: int | None = Field(default=None, ge=1)


class MetricsSpec(Strict):
    """Declared assumptions behind the efficiency figures — shown with them."""
    manual_minutes_per_item: float = Field(default=12, gt=0)   # one manual decision


class ResolveSpec(Strict):
    """One lookup the `resolve` step makes per item, e.g. a book's desk."""
    node: str                          # start node template, e.g. "book:{book}"
    path: list[str]                    # relations to follow, e.g. [belongs_to]
    as_: str = Field(alias="as")       # the item field to set
    take: str = "name"                 # an attribute of the node reached, or "id"
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class LimitsSpec(Strict):
    """Model spend the capability may not exceed. Over a limit, groups that
    would go to the model are escalated to a person instead."""
    max_cost_usd_per_case: float | None = Field(default=None, gt=0)
    max_cost_usd_per_day: float | None = Field(default=None, gt=0)


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
    enrich: list[EnrichSpec] = Field(default_factory=list)
    playbook: PlaybookSpec | None = None
    knowledge: KnowledgeSpec = Field(default_factory=KnowledgeSpec)
    resolve: list[ResolveSpec] = Field(default_factory=list)
    retention: RetentionSpec | None = None
    metrics: MetricsSpec = Field(default_factory=MetricsSpec)
    limits: LimitsSpec = Field(default_factory=LimitsSpec)
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
        used |= {e.tool for e in self.enrich}
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
            ("review.dual_review_when", m.review.dual_review_when),
            *[(f"playbook.checks[{c.id}].when", c.when) for c in (m.playbook.checks if m.playbook else [])],
            *[(f"playbook.guards[{g.verdict}].when", g.when) for g in (m.playbook.guards if m.playbook else [])],
            *[(f"playbook.tests[{t.id}].fails_when", t.fails_when) for t in (m.playbook.tests if m.playbook else [])],
            *[(f"playbook.findings[{f.id}].when", f.when) for f in (m.playbook.findings if m.playbook else [])]]


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
    reads |= {e.tool for e in m.enrich}
    for t in sorted(reads):
        if (found := reg.tool(t)) and found[2].access == "write":
            out.append(f"tool `{t}` writes to a bank system; only `publish` may use it")
    if m.resolve and not m.knowledge.reference:
        out.append("`resolve` lookups need `knowledge.reference` (the namespace to read)")
    for section, step in (("enrich", "enrich"), ("resolve", "resolve"), ("playbook", "classify")):
        if getattr(m, section) and step not in m.steps:
            out.append(f"`{section}` is set but the workflow has no `{step}` step")
    if m.playbook:
        pb = m.playbook
        if pb.default_category not in pb.categories:
            out.append(f"playbook.default_category `{pb.default_category}` is not a category")
        for c in pb.checks:
            if c.category not in pb.categories:
                out.append(f"playbook check {c.id}: unknown category `{c.category}`")
        for cat, sides in pb.verdicts.items():
            if cat not in pb.categories:
                out.append(f"playbook.verdicts: unknown category `{cat}`")
            out += [f"playbook.verdicts.{cat}: unknown side `{sd}`" for sd in sides if sd not in pb.sides]
        out += [f"playbook.verdict_policy: `{p}` is not a policy" for p in pb.verdict_policy
                if p not in m.policy]
        ids = {t.id for t in pb.tests}
        for t in pb.tests:
            out += [f"playbook test {t.id}: `{p}` is not a policy" for p in t.policy if p not in m.policy]
            out += [f"playbook test {t.id}: requires unknown test `{r}`" for r in t.requires_on_fail if r not in ids]
        for f in pb.findings:
            if f.test not in ids:
                out.append(f"playbook finding {f.id}: unknown test `{f.test}`")
            if f.indicates and f.indicates not in pb.categories:
                out.append(f"playbook finding {f.id}: unknown category `{f.indicates}`")
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

    if m.case.opens_on == "schedule":
        from helix.scheduler import CronError, parse_cron
        if not m.case.schedule:
            out.append("case.schedule: a scheduled capability needs a cron schedule")
        else:
            try:
                parse_cron(m.case.schedule)
            except CronError as e:
                out.append(f"case.schedule: {e}")
        if not m.case.schedule_keys:
            out.append("case.schedule_keys: say which cases a scheduled run opens")
    for k in m.case.schedule_keys:
        missing = [f for f in m.case.key if f not in k]
        if missing:
            out.append(f"case.schedule_keys: {k} misses {', '.join(missing)}")
    if (m.case.opens_on == "schedule" or m.case.events) and not m.case.opens_as:
        out.append("case.opens_as: scheduled or event-opened cases need a service user to run as")
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
        if head in ("id", "owners", "configurable", "steps", "pause_before", "publish", "retention", "limits"):
            out.append(f"configurable: `{path}` cannot be set by a group "
                       "(identity, ownership, workflow gates, write-back, retention and spend limits stay with the capability)")
    if m.reasoning.reasoner == "llm" and not m.reasoning.skill.strip():
        out.append("reasoning.skill: an llm reasoner needs instructions")
    return out
