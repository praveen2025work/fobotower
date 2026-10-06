"""Agent One Finance tables. Every row carries capability_id; one shared database.

Audit is these rows: append-only facts about who decided what, on which data,
under which manifest version. Tracing (Phoenix) is separate and best effort.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agent_one_finance.db import AofBase


class CapabilityVersion(AofBase):
    """A capability's manifest, versioned. Owners approve; drafter cannot."""

    __tablename__ = "aof_capability_version"
    __table_args__ = (
        # One active version per capability is a database guarantee.
        Index(
            "uq_aof_capability_one_active", "capability_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    capability_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    manifest: Mapped[dict] = mapped_column(JSONB)
    # draft | active | superseded | rejected
    status: Mapped[str] = mapped_column(String(16))
    note: Mapped[str] = mapped_column(Text, default="")
    drafted_by: Mapped[str] = mapped_column(String(64))
    drafted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GroupVersion(AofBase):
    """A team's configuration of a capability (e.g. one rec group), versioned.
    The group's owners draft and approve it (four-eyes)."""

    __tablename__ = "aof_group_version"
    __table_args__ = (
        Index(
            "uq_aof_group_one_active", "capability_id", "group_id", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    capability_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    config: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))      # draft | active | superseded
    note: Mapped[str] = mapped_column(Text, default="")
    drafted_by: Mapped[str] = mapped_column(String(64))
    drafted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Case(AofBase):
    """One unit of a capability's work, e.g. one entity's month-end."""

    __tablename__ = "aof_case"
    __table_args__ = (
        Index("idx_aof_case_cap", "capability_id", "opened_at"),
        Index("idx_aof_case_scope", "scope", postgresql_using="gin"),
    )

    case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    capability_id: Mapped[str] = mapped_column(String(64))
    # The run is pinned to the manifest version active when it opened.
    manifest_version: Mapped[int] = mapped_column(Integer)
    # The group (team configuration) it runs under, and the exact manifest it ran
    # on — capability merged with that group version — kept for audit and replay.
    team_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team_group_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    case_key: Mapped[dict] = mapped_column(JSONB)
    subject: Mapped[str] = mapped_column(String(256))
    # running | awaiting_review | awaiting_publish | paused_before_<step> |
    # waiting_<step> | completed | escalated | failed | stopped
    status: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_by: Mapped[str] = mapped_column(String(64))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Joins this row to its trace in Phoenix. Null when tracing is off.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Who the run acts as (entitlements at open), so a restarted server can
    # finish a run it did not start.
    run_as: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Re-runs: attempt 2, 3… of the same key. Attempt 1's id is the root.
    root_case_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    rerun_of: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # A follow-up for late items: the case of the same key it follows (its root).
    follow_up_of: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Data-scope values (scope -> value) the case belongs to, for filtering in SQL.
    scope: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Trial runs: a hidden replay of a past case under another version, for an eval run.
    shadow_of: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eval_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    legal_hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When the case is due (manifest case.due), and which reminder went out
    # (soon | missed) so each is sent once.
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    due_notified: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # When the run first paused for people: the start of measured review time.
    review_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
    # A child case opened by a `spawn` step: its parent, which waits for its children.
    parent_case_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # When the run started waiting at an `await` step (for its timeout).
    waiting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Clocks (a `clock` step): {clock_id: {due_at, warned, breached}} — each notice sent once.
    clock_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CaseItem(AofBase):
    """What a case is about: one row per loaded item, payload as the connector returned it."""

    __tablename__ = "aof_case_item"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class ProposalGroup(AofBase):
    """Items collapsed into one decision, with what the run proposes for it."""

    __tablename__ = "aof_proposal_group"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(256))
    group_key: Mapped[dict] = mapped_column(JSONB)
    item_ids: Mapped[list] = mapped_column(JSONB)
    priors: Mapped[list] = mapped_column(JSONB, default=list)
    # {status: proposed|escalated, comment, decided_by: rule|llm|none, reason, rule}
    finding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ToolCall(AofBase):
    """Every call through the MCP gateway — allowed or refused. The grounding record."""

    __tablename__ = "aof_tool_call"
    __table_args__ = (Index("idx_aof_tool_call_case", "case_id", "called_at"),)

    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capability_id: Mapped[str] = mapped_column(String(64))
    connector_id: Mapped[str] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(128))
    # step name, or "llm" when the model asked for it
    requested_by: Mapped[str] = mapped_column(String(32))
    caller: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSONB)
    allowed: Mapped[bool] = mapped_column(Boolean)
    denied_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Write-backs: the key that makes a repeated write a no-op, and lets a
    # retry skip the writes that already landed.
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Decision(AofBase):
    """A person's sign-off on one proposal group. Idempotent on its key."""

    __tablename__ = "aof_decision"
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE")
    )
    group_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(16))  # approve | reject
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    # The reviewer explicitly confirmed a verdict flagged "requires confirmation".
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Decided under delegation: the absent reviewer this decision was made for.
    on_behalf_of: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Seconds the reviewer spent on the group before deciding, as the console
    # measured it (time on screen) — the measured side of "time saved".
    review_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The sign-off checklist (review.checklist) as the reviewer answered it:
    # [{id, label, answer: yes|no|n/a, note}].
    checklist: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InfoRequest(AofBase):
    """A reviewer asking someone (a desk, a trader, Operations) for evidence
    about a case or one of its groups, and their answer."""

    __tablename__ = "aof_info_request"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[str | None] = mapped_column(String(128), nullable=True)   # None = the whole case
    target: Mapped[str] = mapped_column(String(64))
    target_name: Mapped[str] = mapped_column(String(128))
    roles: Mapped[list] = mapped_column(JSONB, default=list)
    users: Mapped[list] = mapped_column(JSONB, default=list)
    question: Mapped[str] = mapped_column(Text)
    asked_by: Mapped[str] = mapped_column(String(64))
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16), default="open")   # open | answered | cancelled
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Evidence the answer came with (a case evidence document's name).
    attachment: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # When the addressees were reminded, and when it was escalated to the reviewers.
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CaseDataset(AofBase):
    """A named data set a case read or built beside its items (a `dataset` or
    `aggregate` step): FX rates, a budget, limits, a roll-up. Kept with the
    case so the reviewer and the auditor see exactly what the run used."""

    __tablename__ = "aof_case_dataset"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    step_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(256))
    rows: Mapped[list] = mapped_column(JSONB, default=list)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FollowThrough(AofBase):
    """What became of a decided item in the next run of the same series
    (follow_through): cleared (gone) or still_open (still there)."""

    __tablename__ = "aof_follow_through"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16))          # cleared | still_open
    checked_in: Mapped[str] = mapped_column(String(128))     # the case that checked it
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GateDecision(AofBase):
    """A person passing (or stopping a run at) a tollgate: a stop before a step
    other than review and publish. Idempotent on its key."""

    __tablename__ = "aof_gate_decision"
    gate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), index=True
    )
    step: Mapped[str] = mapped_column(String(32))     # the step it stopped before
    action: Mapped[str] = mapped_column(String(16))   # continue | stop
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PublishApproval(AofBase):
    """The second person releasing a case's write-back. One per case."""

    __tablename__ = "aof_publish_approval"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    approved_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KgNode(AofBase):
    """Knowledge graph node. Namespaced per capability; bitemporal by valid_from/valid_to."""

    __tablename__ = "aof_kg_node"
    __table_args__ = (Index("idx_aof_kg_node_kind", "namespace", "kind"),)

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Part of the key: a node changes by closing one version and opening the next.
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KgEdge(AofBase):
    __tablename__ = "aof_kg_edge"
    __table_args__ = (
        Index("idx_aof_kg_edge_to", "namespace", "to_id", "relation"),
        Index("idx_aof_kg_edge_from", "namespace", "from_id", "relation"),
    )

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    relation: Mapped[str] = mapped_column(String(32), primary_key=True)
    to_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Document(AofBase):
    """A document Agent One Finance wrote (e.g. a PDF report), kept in the shared database
    so every API instance can serve it."""

    __tablename__ = "aof_document"
    scope: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(64))
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # report: written by a publish step · evidence: uploaded into a case by a person
    kind: Mapped[str] = mapped_column(String(16), default="report", server_default="report")
    case_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CaseMessage(AofBase):
    """Ask-about-a-case: one question or answer. Answers keep what they cited."""

    __tablename__ = "aof_case_message"
    __table_args__ = (Index("idx_aof_case_message_case", "case_id", "created_at"),)

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))          # user | assistant
    author: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    # assistant only: tool calls, ungrounded figures, model
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RetentionEvent(AofBase):
    """A case removed under its capability's retention policy — the record that it was."""

    __tablename__ = "aof_retention_event"
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(128))
    capability_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(256))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retention_days: Mapped[int] = mapped_column(Integer)
    purged_by: Mapped[str] = mapped_column(String(64))
    purged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Notification(AofBase):
    """Something a person should know about a case — waiting on them, done,
    failed. Addressed to roles and/or people; shown only to those who may see
    the case."""

    __tablename__ = "aof_notification"
    __table_args__ = (Index("idx_aof_notification_at", "created_at"),)

    notification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capability_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text, default="")
    audience_roles: Mapped[list] = mapped_column(JSONB, default=list)
    audience_users: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NotificationRead(AofBase):
    __tablename__ = "aof_notification_read"
    notification_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("aof_notification.notification_id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Switch(AofBase):
    """An off switch: a capability, one team's group, or a connector, stopped
    until switched back on. Every change is kept (who, when, why)."""

    __tablename__ = "aof_switch"
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)       # capability | group | connector
    target: Mapped[str] = mapped_column(String(160), primary_key=True)    # id; group: "<capability>/<group>"
    off: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    set_by: Mapped[str] = mapped_column(String(64))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                             onupdate=func.now())
    history: Mapped[list] = mapped_column(JSONB, default=list)


class EvalRun(AofBase):
    """A trial of one capability (or group) version against people's past
    decisions: the shadow runs it made, and how often it agreed."""

    __tablename__ = "aof_eval_run"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    capability_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    team_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    group_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16))            # running | done | failed
    started_by: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchedulerTick(AofBase):
    """A minute the scheduler has run — so only one API instance runs it."""

    __tablename__ = "aof_scheduler_tick"
    minute: Mapped[str] = mapped_column(String(16), primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


AOF_TABLES = [  # child tables first, for truncation in tests
    "aof_ticket", "aof_delegation",
    "aof_eval_run", "aof_switch", "aof_scheduler_tick",
    "aof_notification_read", "aof_notification",
    "aof_case_message", "aof_document", "aof_retention_event",
    "aof_publish_approval", "aof_decision", "aof_proposal_group", "aof_case_item", "aof_tool_call",
    "aof_case", "aof_group_version", "aof_capability_version", "aof_kg_edge", "aof_kg_node",
]


class Ticket(AofBase):
    """A ticket raised for the team that owns a problem (manifest `escalation`)."""

    __tablename__ = "aof_ticket"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("aof_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tool: Mapped[str] = mapped_column(String(128))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16))        # raised | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Delegation(AofBase):
    """A reviewer away: a colleague decides on their behalf until `until`."""

    __tablename__ = "aof_delegation"
    delegation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_user: Mapped[str] = mapped_column(String(64), index=True)
    to_user: Mapped[str] = mapped_column(String(64), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The absent reviewer as entitlements saw them when they delegated: the
    # roles and data scopes the colleague acts within.
    from_entitlement: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
