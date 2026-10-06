"""The capability manifest: everything a use case is, as configuration.

`Manifest.model_validate` checks shape; `problems(manifest)` checks meaning —
every step exists, the gates are present and in order, every step's inputs
are produced earlier, every tool is an onboarded connector tool, every
expression parses. A manifest with problems is never stored as active.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from helix import rules


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Owners(Strict):
    people: list[str] = Field(default_factory=list)
    role: str | None = None   # a bank role from central entitlements
    four_eyes: bool = True    # the drafter of a change cannot approve it


class DueSpec(Strict):
    from_: str = Field(default="opened", alias="from")   # "opened" or a case-key date field (e.g. cob)
    business_days: int = Field(default=0, ge=0, le=60)
    hours: float = Field(default=0, ge=0, le=24 * 30)
    at: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # time of day, HH:MM (schedule time zone)
    warn_hours: float = Field(default=2, ge=0, le=72)    # "due soon" this long before


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
    # When a case is due: from the moment it opened (or a date in its key),
    # plus business days and hours, optionally at a time of day. Inboxes count
    # down to it; owners and reviewers are told when it is near and when missed.
    due: DueSpec | None = None
    # When an event arrives for a key that already has a case (e.g. MB Rec
    # notifies late exceptions for a book and COB already being worked):
    #   ignore     the existing case is the answer; nothing new is read
    #   follow_up  a follow-up case linked to it reads the source again and
    #              takes only the items no case for that key has yet
    late_items: Literal["ignore", "follow_up"] = "ignore"


class ToolCallSpec(Strict):
    tool: str                          # "connector.tool"
    # literal values, or "$case.<field>" taken from the case key
    args: dict[str, Any] = Field(default_factory=dict)


class ItemsSpec(Strict):
    load: ToolCallSpec | None = None   # used by the `load` step
    id_field: str
    amount_field: str | None = None
    amount_unit: str | None = None     # e.g. GBP: how amounts and exposure are labelled
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
    # Settled by the table whatever the side, proven or not — for a category that
    # is not about a side at all (e.g. books not complete). Its table must give
    # one verdict for every side. Off by default: an unproven side goes to the
    # model and an SME (FOBO R2).
    any_side: bool = False


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
    # Business words for each side, used in labels ("side_name"), e.g. FO: front office.
    side_names: dict[str, str] = Field(default_factory=dict)

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


class SpecialistSpec(Strict):
    """A subagent the model may hand part of a group to (e.g. an FX specialist).
    Its tools are a subset of the capability's reasoning tools, served by the
    same gateway — a specialist can do no more than the capability can."""
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,40}$")
    description: str                   # when to use it — the main agent reads this
    instructions: str
    tools: list[str] = Field(default_factory=list)


class SectionSpec(Strict):
    """One part of the model's answer, returned as its own field (e.g. root
    cause, remediation, end state) so the case shows it, a reviewer can check
    it and it can be reported on."""
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    label: str
    # What the section must say, given to the model.
    hint: str = ""
    # An answer without it is escalated to a person (like an ungrounded figure).
    required: bool = False


class ReasoningSpec(Strict):
    reasoner: Literal["llm", "none"] = "llm"
    skill: str = ""                    # instructions to the model
    tools: list[str] = Field(default_factory=list)   # tools the model may call
    specialists: list[SpecialistSpec] = Field(default_factory=list)
    output: Literal["verdict", "commentary", "classification"] = "commentary"
    # The parts the model's answer is returned in; empty = one free-text comment.
    sections: list[SectionSpec] = Field(default_factory=list)


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


class RequestTarget(Strict):
    """Someone a reviewer may ask for evidence: a desk, a trader, Operations…"""
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,40}$")
    name: str                          # shown to the reviewer, e.g. "Desk (trader)"
    roles: list[str] = Field(default_factory=list)   # who answers: anyone with one of these roles
    users: list[str] = Field(default_factory=list)   # …or these people


class RequestsSpec(Strict):
    """Asking for evidence instead of assuming it (FOBO skill §13). A reviewer
    asks a target a question about a group (or the case); they are notified and
    answer in Helix (or a bot answers for them through the API). The answer is
    kept on the case and reaches the model as context."""
    targets: list[RequestTarget] = Field(default_factory=list)
    # A group with an open question waits for the answer before it is decided.
    hold_decision: bool = True
    # During review, an answer sends its group back to the model with it.
    reinvestigate_on_answer: bool = True
    # Remind the people asked after this many hours without an answer…
    remind_after_hours: float | None = Field(default=None, gt=0)
    # …and tell the reviewers (and whoever asked) after this many.
    escalate_after_hours: float | None = Field(default=None, gt=0)
    # May an answer come with a file (kept as the case's evidence)?
    allow_attachments: bool = True


class TollgateSpec(Strict):
    """A person approves the run's work so far before it goes on — e.g. the
    matched breaks before the model investigates them. The run waits at the
    gate (pause_before) until someone continues it or stops it."""
    # Who may pass it; empty = the capability's reviewers.
    roles: list[str] = Field(default_factory=list)
    # What the person checks, shown at the gate, e.g. "Are both sides complete?"
    check: str = ""
    # Stopping the run needs the person's reason.
    stop_needs_comment: bool = True


class ChecklistItem(Strict):
    """One question a reviewer answers before approving (e.g. FOBO skill §14:
    "Has every applicable FO test been performed or marked unable to test?")."""
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    label: str
    # Must be answered yes (or n/a) to approve; otherwise answering is optional.
    required: bool = True
    # What Helix already knows, shown next to the question: tests (the tests
    # run, failed and not run), evidence (evidence and answers on the case),
    # verdict, category, or a reasoning section id.
    prefill: str | None = None


class FollowThroughSpec(Strict):
    """Check each decision in the next run of the same series: an item that is
    gone has cleared; one still there carries what was decided
    (carried_verdict, carried_from, carried_runs) for the rules to act on —
    e.g. after an adjustment, BO + adjustments must equal FO on the next COB."""
    # Case-key fields that stay the same run to run, e.g. [book].
    series: list[str]
    # The case-key field that advances, e.g. cob.
    order_by: str
    # Verdicts to follow; empty = every approved group.
    verdicts: list[str] = Field(default_factory=list)


class AuthorityTier(Strict):
    """One row of an authority matrix: for groups it matches (first match
    wins), who may approve, how many different people, the review lane, and
    whether "Approve all" may include them."""
    # Expression over a group: total, count, its key fields, verdict, category,
    # side, risk_band, policy. Absent = every group (a last, catch-all row).
    when: str | None = None
    label: str = ""
    roles: list[str] = Field(default_factory=list)   # empty = the reviewers
    approvals: int = Field(default=1, ge=1, le=5)
    lane: str = "standard"
    bulk: bool = True


class Boundary(Strict):
    """A decision reserved for named people (E7): credit, sanctions, AML,
    KYC acceptance, payment release, redress above a limit… Enforced in code
    after the model and at review."""
    # The verdicts (or statuses) it covers, e.g. [CLOSE_ALERT, ACCEPT_CLIENT].
    verdicts: list[str] = Field(default_factory=list)
    # …or an expression over a group (as in the authority matrix).
    when: str | None = None
    roles: list[str] = Field(min_length=1)          # only these may decide it
    # The model may not propose it: its proposal becomes ESCALATE, for a person.
    model_may_propose: bool = False
    reason: str = ""


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
    # Groups "Approve all" leaves for one-by-one review:
    #   confirmation  a verdict flagged "requires controller confirmation"
    #   judgement     a judgement call (the model investigated; an SME decides)
    #   escalated     escalated by a rule, the playbook or the model
    #   model         any group the model proposed
    bulk_exclude: list[Literal["confirmation", "judgement", "escalated", "model"]] = Field(
        default_factory=lambda: ["confirmation", "judgement"])
    # Approving a group flagged "requires controller confirmation" needs:
    # tick (an explicit confirmation), tick_and_comment (and the reviewer's words), none.
    confirm: Literal["none", "tick", "tick_and_comment"] = "tick_and_comment"
    # May a reviewer hand their reviews to a colleague while away? The colleague
    # decides on their behalf, within the absent reviewer's data scope; both are recorded.
    allow_delegation: bool = False
    # Questions a reviewer answers before approving a group (sign-off checklist).
    checklist: list[ChecklistItem] = Field(default_factory=list)
    # Authority matrix (and review lanes): who may approve which groups, and how
    # many people. In this configuration, or read from the bank's delegated-
    # authority system as a data set (`authority_dataset`: rows with min_amount,
    # max_amount, roles, approvals, lane; a `dataset` step reads it).
    authority: list[AuthorityTier] = Field(default_factory=list)
    authority_dataset: str | None = None


class RecurringSpec(Strict):
    """Items that keep coming back: the same item id in earlier cases of the
    same capability (and group) whose `same` key fields match this case's."""
    same: list[str] = Field(default_factory=list)    # e.g. [book]: the same book, earlier COBs
    lookback_cases: int = Field(default=10, ge=1, le=100)
    min_runs: int = Field(default=2, ge=2, le=100)   # seen in at least this many runs, this one included


class UnexplainedSpec(Strict):
    """Items nothing explained: no check was positive (playbook), or the
    category is one of these (e.g. FOBO's H Novel). Listed across cases for
    the playbook's owners to turn into new checks."""
    categories: list[str] = Field(default_factory=list)
    lookback_days: int = Field(default=30, ge=1, le=365)


class InsightsSpec(Strict):
    recurring: RecurringSpec | None = None
    unexplained: UnexplainedSpec | None = None
    # A judgement category whose model-proposed verdict reviewers approved
    # unchanged this many times is listed as a candidate for a deterministic rule.
    automation_after: int = Field(default=5, ge=2, le=1000)


class EscalationSpec(Strict):
    """Raise a ticket for the team that owns a problem — after review, through
    a write tool on a ticketing connector (ServiceNow, Jira…). One call per
    group that matches `when`, idempotent per case and group."""
    tool: str                          # a connector tool with access: write
    # Expression over the group and its outcome: its key fields, total, count,
    # verdict, status (proposed|escalated), action (approve|reject), category,
    # side, escalate_to, policy.
    when: str
    # Argument values: literals, "$case.<field>", "$case_id", "$subject",
    # "$group.<field>", "$label", "$comment", "$verdict", "$escalate_to",
    # "$total", "$decided_by".
    args: dict[str, Any] = Field(default_factory=dict)


class ExportSpec(Strict):
    """The case's Excel download: item columns (default: items.display)."""
    columns: list[str] = Field(default_factory=list)


class StepSettings(Strict):
    """How one step of `steps` is set up, when it is not a core step with its
    own section (load, match, enrich…) or when it should run only sometimes:

        step_settings:
          fx:  {type: dataset, with: {name: fx, tool: refdata.fx_rates, args: {date: $case.date}}}
          age: {type: derive, when: "case.region == 'EU'", with: {fields: {...}}}
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    # The step type; default: the step's id (a core step).
    type: str | None = None
    # Run the step only when this holds: an expression over `case.<field>`,
    # `policy.<name>` and `count` (items so far). Absent = always.
    when: str | None = None
    label: str | None = None
    # The step type's own settings (see helix/stepkit.py).
    with_: dict[str, Any] = Field(default_factory=dict, alias="with")


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
    # Settings per step id: the type and settings of configurable steps
    # (dataset, derive, filter, convert, bucket, aggregate, dedupe, transform)
    # and `when` on any step. A type may appear more than once under different ids.
    step_settings: dict[str, StepSettings] = Field(default_factory=dict)
    pause_before: list[str] = Field(default_factory=lambda: ["review"])
    # Who passes each human stop other than review and publish, and what they check.
    # A stop without an entry here is passed by the reviewers.
    tollgates: dict[str, TollgateSpec] = Field(default_factory=dict)
    # Who reviewers may ask for evidence, and what an open question holds back.
    requests: RequestsSpec = Field(default_factory=RequestsSpec)
    group_by: list[str] = Field(default_factory=list)
    # How a group is named, a template over its key fields and, with a
    # playbook, category_name and side_name — e.g. "{category_name} · {side_name}".
    # Default: "field value, field value".
    group_label: str | None = None
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
    insights: InsightsSpec = Field(default_factory=InsightsSpec)
    escalation: EscalationSpec | None = None
    # Re-check decisions in the next run of the same series.
    follow_through: FollowThroughSpec | None = None
    # Decisions reserved for named people (credit, sanctions, AML, KYC, release…).
    boundaries: list[Boundary] = Field(default_factory=list)
    export: ExportSpec = Field(default_factory=ExportSpec)
    # What a group (a team's configuration of this capability, e.g. one rec group)
    # may set: dotted paths; "x.*" = anything under x. Owners stay the capability's.
    configurable: list[str] = Field(default_factory=list)

    def policy_values(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.policy.items()}

    def step_type(self, step_id: str) -> str:
        st = self.step_settings.get(step_id)
        return (st.type if st and st.type else step_id)

    def waits(self) -> list[str]:
        """Steps the run waits before for an event or child cases (`await`)."""
        return [s for s in self.steps if self.step_type(s) == "await"]

    def pauses(self) -> list[str]:
        return list(dict.fromkeys([*self.pause_before, *self.waits()]))

    def release_step(self) -> str | None:
        """The step that writes the decided outcome after a second person's release."""
        return next((s for s in self.steps if self.step_type(s) in ("publish", "post")), None)

    def release_roles(self) -> list[str]:
        r = self.release_step()
        if r is None:
            return []
        if r == "publish" and self.publish:
            return list(self.publish.approver_roles)
        cfg = self.step_config(r)
        return list(getattr(cfg, "approver_roles", []) or [])

    def step_types(self) -> dict[str, str]:
        return {s: self.step_type(s) for s in self.steps}

    def step_config(self, step_id: str):
        """The validated settings of a configurable step (None for a core step)."""
        from helix import stepkit
        t = self.step_type(step_id)
        if t not in stepkit.TYPES:
            return None
        return stepkit.parse(t, (self.step_settings.get(step_id) or StepSettings()).with_)

    def data_step_tools(self) -> set[str]:
        from helix import stepkit
        out: set[str] = set()
        for sid in self.steps:
            t = self.step_type(sid)
            if t in stepkit.TYPES:
                try:
                    out |= stepkit.TYPES[t].tools(self.step_config(sid))
                except ValueError:
                    pass
        return out

    def tools_used(self) -> set[str]:
        used = set(self.reasoning.tools) | self.data_step_tools()
        if self.items.load:
            used.add(self.items.load.tool)
        if self.match:
            used |= {self.match.left.tool, self.match.right.tool}
        used |= {e.tool for e in self.enrich}
        if self.publish:
            used.add(self.publish.tool)
        if self.escalation:
            used.add(self.escalation.tool)
        return used

    def write_tools(self) -> set[str]:
        from helix import stepkit
        out = ({self.publish.tool} if self.publish else set()) | (
            {self.escalation.tool} if self.escalation else set())
        for sid in self.steps:
            t = self.step_type(sid)
            if t in stepkit.TYPES and (writes := stepkit.TYPES[t].extra.get("writes")):
                try:
                    out |= writes(self.step_config(sid))
                except ValueError:
                    pass
        return out

    def read_tools(self) -> set[str]:
        return self.tools_used() - self.write_tools()

    def visible_to_roles(self) -> set[str]:
        return (set(self.review.roles) | ({self.owners.role} if self.owners.role else set())
                | {r for g in self.tollgates.values() for r in g.roles}
                | {r for s in self.pause_before for r in self.gate(s).roles}
                | set(self.release_roles())
                | {r for t in self.review.authority for r in t.roles}
                | {r for b in self.boundaries for r in b.roles})

    def gate(self, step: str) -> TollgateSpec:
        """The tollgate before `step` (the reviewers pass it unless it names others;
        an attestation or outreach step names its own people and what they check)."""
        g = self.tollgates.get(step) or TollgateSpec()
        try:
            cfg = self.step_config(step) if step in self.steps else None
        except ValueError:
            cfg = None
        if cfg is not None and getattr(cfg, "roles", None) and self.step_type(step) in ("attest", "outreach"):
            check = getattr(cfg, "statement", None) or g.check or "Approve sending the drafted messages"
            return g.model_copy(update={"roles": g.roles or list(cfg.roles), "check": check})
        return g if g.roles else g.model_copy(update={"roles": list(self.review.roles)})


def _expressions(m: Manifest) -> list[tuple[str, str | None]]:
    """Every expression in a manifest, named for the error message."""
    return [("items.in_scope", m.items.in_scope),
            *[(f"rules[{r.id}].when", r.when) for r in m.rules],
            ("review.dual_review_when", m.review.dual_review_when),
            *[(f"review.authority[{i}].when", t.when) for i, t in enumerate(m.review.authority)],
            *[(f"boundaries[{i}].when", b.when) for i, b in enumerate(m.boundaries)],
            ("escalation.when", m.escalation.when if m.escalation else None),
            *[(f"playbook.checks[{c.id}].when", c.when) for c in (m.playbook.checks if m.playbook else [])],
            *[(f"playbook.guards[{g.verdict}].when", g.when) for g in (m.playbook.guards if m.playbook else [])],
            *[(f"playbook.tests[{t.id}].fails_when", t.fails_when) for t in (m.playbook.tests if m.playbook else [])],
            *[(f"playbook.findings[{f.id}].when", f.when) for f in (m.playbook.findings if m.playbook else [])]]


def problems(m: Manifest) -> list[str]:
    """Everything wrong with a manifest, in plain words. Empty means valid."""
    from helix.gateway import registry
    from helix.workflow import order_problems

    out = []
    from helix import stepkit
    from helix.workflow import STEPS as CORE
    configs: dict[str, Any] = {}
    for sid in m.steps:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", sid):
            out.append(f"steps: `{sid}` — a step id is lower case letters, digits and _")
    for sid, st in m.step_settings.items():
        if sid not in m.steps:
            out.append(f"step_settings.{sid}: `{sid}` is not in steps")
            continue
        t = m.step_type(sid)
        if t in CORE:
            if st.type and st.type != sid:
                out.append(f"step_settings.{sid}: a core step keeps its own name (`{st.type}`)")
            if st.with_:
                out.append(f"step_settings.{sid}: `{t}` is set up in its own section, not under `with`")
        elif t not in stepkit.TYPES:
            out.append(f"step_settings.{sid}: unknown step type `{t}` "
                       f"(configurable types: {', '.join(sorted(stepkit.TYPES))})")
        else:
            try:
                configs[sid] = stepkit.parse(t, st.with_)
            except ValueError as e:
                errs = getattr(e, "errors", lambda: [])()
                out += [f"step_settings.{sid}.with.{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                        for err in errs] or [f"step_settings.{sid}: {e}"]
                continue
            for name, src in stepkit.TYPES[t].expressions(configs[sid]):
                try:
                    rules.compile_expr(src)
                except rules.ExpressionError as e:
                    out.append(f"step_settings.{sid}.with.{name}: {e}")
        if st.when:
            try:
                rules.compile_expr(st.when)
            except rules.ExpressionError as e:
                out.append(f"step_settings.{sid}.when: {e}")
            if t in ("validate", "review", "record"):
                out.append(f"step_settings.{sid}.when: the gate `{t}` always runs")
    for sid in m.steps:
        t = m.step_type(sid)
        if t not in CORE and t not in stepkit.TYPES:
            out.append(f"steps: `{sid}` is not a core step; give it a type under step_settings")
    if out:
        return out
    from helix.gateway import registry as _registry
    reg_ = _registry()
    for sid, cfg in configs.items():
        st = stepkit.TYPES[m.step_type(sid)]
        writes = st.extra.get("writes", lambda c: set())(cfg)
        for tool in sorted(st.tools(cfg)):
            found = reg_.tool(tool)
            if found is None:
                continue        # reported below as not onboarded
            if tool in writes and found[2].access != "write":
                out.append(f"step_settings.{sid}: `{tool}` is not a write tool")
            elif tool not in writes and found[2].access == "write":
                out.append(f"step_settings.{sid}: `{tool}` writes to a bank system; this step only reads")
        if st.extra.get("person") and sid not in m.pause_before:
            out.append(f"pause_before: `{sid}` needs a person first — add it to pause_before (its tollgate)")
        if m.step_type(sid) == "spawn":
            later = m.steps[m.steps.index(sid) + 1:]
            if not any(m.step_type(x) == "await" and getattr(configs.get(x), "event", "") == "children" for x in later):
                out.append(f"`{sid}` opens child cases: add a later `await` step with event `children`")
            if cfg.capability == m.id and not cfg.team_group:
                pass
    out += order_problems(m.steps, m.pause_before, m.step_types(), configs)

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
    if m.escalation and (found := reg.tool(m.escalation.tool)) and found[2].access != "write":
        out.append(f"escalation.tool `{m.escalation.tool}` is not a write tool")
    if m.escalation and "record" not in m.steps:
        out.append("`escalation` raises tickets in the `record` step, which the workflow lacks")
    if m.case.due and m.case.due.from_ != "opened" and m.case.due.from_ not in m.case.key:
        out.append(f"case.due.from `{m.case.due.from_}` is not a case-key field (or `opened`)")
    if m.insights.recurring:
        out += [f"insights.recurring.same: `{f}` is not a case-key field"
                for f in m.insights.recurring.same if f not in m.case.key]
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
        for code, c in pb.categories.items():
            if c.any_side and (len(set(pb.verdicts.get(code, {}).values())) != 1
                               or set(pb.verdicts.get(code, {})) != set(pb.sides)):
                out.append(f"playbook.categories.{code}: any_side needs one verdict for every side in the table")
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
    ids = [t.id for t in m.requests.targets]
    if len(set(ids)) != len(ids):
        out.append("requests.targets: each target needs its own id")
    out += [f"requests.targets[{t.id}]: name the roles or the people who answer"
            for t in m.requests.targets if not t.roles and not t.users]
    for step in m.tollgates:
        if step in ("review", "publish"):
            out.append(f"tollgates.{step}: `{step}` has its own controls (review, publish)")
        elif step not in m.pause_before:
            out.append(f"tollgates.{step}: the run does not stop before `{step}` (add it to pause_before)")
    if m.steps and m.steps[0] in m.pause_before:
        out.append(f"pause_before: the run cannot stop before its first step `{m.steps[0]}`; there is nothing to check yet")
    if m.follow_through:
        ft = m.follow_through
        out += [f"follow_through.series: `{f}` is not in case.key" for f in ft.series if f not in m.case.key]
        if ft.order_by not in m.case.key:
            out.append(f"follow_through.order_by: `{ft.order_by}` is not in case.key")
        elif ft.order_by in ft.series:
            out.append(f"follow_through.order_by: `{ft.order_by}` advances run to run; it cannot also be in series")
    ids = [s.id for s in m.reasoning.sections]
    if len(set(ids)) != len(ids):
        out.append("reasoning.sections: each section needs its own id")
    ids = [c.id for c in m.review.checklist]
    if len(set(ids)) != len(ids):
        out.append("review.checklist: each question needs its own id")
    known = {"tests", "evidence", "verdict", "category"} | {s.id for s in m.reasoning.sections}
    out += [f"review.checklist[{c.id}].prefill: `{c.prefill}` is not tests, evidence, verdict, category or a reasoning section"
            for c in m.review.checklist if c.prefill and c.prefill not in known]
    if (m.requests.remind_after_hours and m.requests.escalate_after_hours
            and m.requests.escalate_after_hours <= m.requests.remind_after_hours):
        out.append("requests.escalate_after_hours: escalate after the reminder, not before it")
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
        if head in ("id", "owners", "configurable", "steps", "pause_before", "tollgates", "publish", "retention", "limits"):
            out.append(f"configurable: `{path}` cannot be set by a group "
                       "(identity, ownership, workflow gates, write-back, retention and spend limits stay with the capability)")
    for sp in m.reasoning.specialists:
        extra = sorted(set(sp.tools) - set(m.reasoning.tools))
        if extra:
            out.append(f"reasoning.specialists[{sp.name}]: tools not in reasoning.tools: {', '.join(extra)}")
    if m.reasoning.reasoner == "llm" and not m.reasoning.skill.strip():
        out.append("reasoning.skill: an llm reasoner needs instructions")
    return out
