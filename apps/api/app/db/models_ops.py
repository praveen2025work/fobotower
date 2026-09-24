"""Operational entities: what is scheduled, what ran, and what it called.

Phase 1 served the run schedule from a static Python dict. These tables
replace it, so every figure the header and timeline show is a row.
"""

from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Registers investigation_session in the same metadata: source_call declares a
# foreign key to it, and SQLAlchemy resolves that by table name at mapper
# configuration time.
from app.db import models_session  # noqa: E402,F401


class Reconciliation(Base):
    """A rec definition: what it is, where it belongs, when it runs."""

    __tablename__ = "reconciliation"
    rec_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(8))
    master_book: Mapped[str] = mapped_column(String(64))
    scheduled_time: Mapped[time] = mapped_column(Time)
    books_total: Mapped[int] = mapped_column(Integer)
    # How the Helix console files a rec: its rec group (CATS-MOTIF or
    # RF-CASHCOLL), the L4 it covers, and the currency its figures are in.
    rec_group: Mapped[str] = mapped_column(String(16), default="CATS-MOTIF")
    l4: Mapped[str] = mapped_column(String(64), default="")
    ccy: Mapped[str] = mapped_column(String(3), default="USD")

    __table_args__ = (Index("idx_rec_region", "region", "scheduled_time"),)


class Run(Base):
    """One execution of a rec on one business date."""

    __tablename__ = "run"
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rec_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("reconciliation.rec_id")
    )
    business_date: Mapped[date] = mapped_column(Date)
    scheduled_time: Mapped[time] = mapped_column(Time)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16))
    books_open: Mapped[int] = mapped_column(Integer, default=0)
    # A Helix session starts when One Fin UX sends the rec's Ready event, not
    # at a fixed time. Until then only master-book readiness is known.
    ready_event_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mb_available: Mapped[int] = mapped_column(Integer, default=0)
    mb_reported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Book states as One Fin UX reports them for this run: total, autoPost,
    # cleared, awaiting, analysing, blocked, notOpen.
    book_stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    books_unlocked: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("idx_run_date", "business_date", "rec_id"),)


class SourceCall(Base):
    """One retrieval, as the Grounding panel lists it.

    Named in the BRD's data model and specced in Phase 1; this is where it
    finally lands. Every row is one line of 'Grounding — MCP calls'.
    """

    __tablename__ = "source_call"
    call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    investigation_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("investigation_session.investigation_session_id")
    )
    application_name: Mapped[str] = mapped_column(String(32))
    tool_name: Mapped[str] = mapped_column(String(64))
    validated_parameters: Mapped[dict] = mapped_column(JSONB)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str] = mapped_column(Text)
    entitlement_result: Mapped[str] = mapped_column(String(16))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What the tool returned, as returned. The MCP inspector shows these rows,
    # so a figure on screen can be traced to the retrieval that produced it.
    result_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    called_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_call_session", "investigation_session_id", "called_ts"),
    )
