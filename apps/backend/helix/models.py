"""Helix tables. Every row carries capability_id; one shared database.

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
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from helix.db import HelixBase


class CapabilityVersion(HelixBase):
    """A capability's manifest, versioned. Owners approve; drafter cannot."""

    __tablename__ = "helix_capability_version"
    __table_args__ = (
        # One active version per capability is a database guarantee.
        Index(
            "uq_helix_capability_one_active", "capability_id", unique=True,
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


class GroupVersion(HelixBase):
    """A team's configuration of a capability (e.g. one rec group), versioned.
    The group's owners draft and approve it (four-eyes)."""

    __tablename__ = "helix_group_version"
    __table_args__ = (
        Index(
            "uq_helix_group_one_active", "capability_id", "group_id", unique=True,
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


class Case(HelixBase):
    """One unit of a capability's work, e.g. one entity's month-end."""

    __tablename__ = "helix_case"
    __table_args__ = (Index("idx_helix_case_cap", "capability_id", "opened_at"),)

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
    # running | awaiting_review | completed | escalated | failed
    status: Mapped[str] = mapped_column(String(24))
    outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    draft: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_by: Mapped[str] = mapped_column(String(64))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Joins this row to its trace in Phoenix. Null when tracing is off.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class CaseItem(HelixBase):
    """What a case is about: one row per loaded item, payload as the connector returned it."""

    __tablename__ = "helix_case_item"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("helix_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class ProposalGroup(HelixBase):
    """Items collapsed into one decision, with what the run proposes for it."""

    __tablename__ = "helix_proposal_group"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("helix_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(256))
    group_key: Mapped[dict] = mapped_column(JSONB)
    item_ids: Mapped[list] = mapped_column(JSONB)
    priors: Mapped[list] = mapped_column(JSONB, default=list)
    # {status: proposed|escalated, comment, decided_by: rule|llm|none, reason, rule}
    finding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ToolCall(HelixBase):
    """Every call through the MCP gateway — allowed or refused. The grounding record."""

    __tablename__ = "helix_tool_call"
    __table_args__ = (Index("idx_helix_tool_call_case", "case_id", "called_at"),)

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
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Decision(HelixBase):
    """A person's sign-off on one proposal group. Idempotent on its key."""

    __tablename__ = "helix_decision"
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("helix_case.case_id", ondelete="CASCADE")
    )
    group_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(16))  # approve | reject
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PublishApproval(HelixBase):
    """The second person releasing a case's write-back. One per case."""

    __tablename__ = "helix_publish_approval"
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("helix_case.case_id", ondelete="CASCADE"), primary_key=True
    )
    approved_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KgNode(HelixBase):
    """Knowledge graph node. Namespaced per capability; bitemporal by valid_from/valid_to."""

    __tablename__ = "helix_kg_node"
    __table_args__ = (Index("idx_helix_kg_node_kind", "namespace", "kind"),)

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KgEdge(HelixBase):
    __tablename__ = "helix_kg_edge"
    __table_args__ = (Index("idx_helix_kg_edge_to", "namespace", "to_id", "relation"),)

    namespace: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    relation: Mapped[str] = mapped_column(String(32), primary_key=True)
    to_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


HELIX_TABLES = [  # child tables first, for truncation in tests
    "helix_publish_approval", "helix_decision", "helix_proposal_group", "helix_case_item", "helix_tool_call",
    "helix_case", "helix_group_version", "helix_capability_version", "helix_kg_edge", "helix_kg_node",
]
