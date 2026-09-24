from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db import models_workflow  # noqa: F401 — the workflow_version FK target


class InvestigationSession(Base):
    __tablename__ = "investigation_session"
    investigation_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reconciliation_id: Mapped[str] = mapped_column(String(64))
    master_book: Mapped[str] = mapped_column(String(64))
    business_date: Mapped[date] = mapped_column(Date)
    run_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    # The workflow version the run started with. Null: the run predates
    # versioning and is read as version 1.
    workflow_version: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_version.number"), nullable=True
    )
    created_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalysisVersion(Base):
    __tablename__ = "analysis_version"
    analysis_version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    supersedes: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB)
    confidence_tier: Mapped[str] = mapped_column(String(16))
    prompt_version: Mapped[str] = mapped_column(String(32))
    skill_version: Mapped[str] = mapped_column(String(32))
    model_identifier: Mapped[str] = mapped_column(String(64))
    created_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvidenceItem(Base):
    __tablename__ = "evidence_item"
    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    source_application: Mapped[str] = mapped_column(String(32))
    storage_mode: Mapped[str] = mapped_column(String(16))
    reference_uri: Mapped[str] = mapped_column(Text)
    integrity_hash: Mapped[str] = mapped_column(String(64))
    is_original_analysis: Mapped[bool] = mapped_column(Boolean)
    retrieved_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PatternGroupRow(Base):
    __tablename__ = "pattern_group"
    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    pattern_code: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(8))
    break_ids: Mapped[list] = mapped_column(JSONB)
    historical_approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class ControllerDecision(Base):
    __tablename__ = "controller_decision"
    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    group_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("pattern_group.group_id"), nullable=True
    )
    controller_user_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The breaks this decision covered: a group's breaks, or the ones a
    # controller selected. The activity feed and audit read them back.
    break_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    decided_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_decision_idem", "idempotency_key", unique=True),)


class SessionMessage(Base):
    """One turn of a Helix session's conversation, as the controller saw it.

    The analysis turn is not stored: it is derived from the investigation.
    Questions, answers and decision notes are, so a reload shows the same
    conversation and the audit trail keeps who asked what.
    """

    __tablename__ = "session_message"
    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    role: Mapped[str] = mapped_column(String(16))  # user | agent | system
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # source_call ids this answer retrieved, in call order.
    call_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Which path answered: "router:<intent>" or "reasoner:<adapter>".
    answered_by: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_message_session", "investigation_session_id", "created_ts"),
    )
