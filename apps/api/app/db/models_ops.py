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


class Reconciliation(Base):
    """A rec definition: what it is, where it belongs, when it runs."""

    __tablename__ = "reconciliation"
    rec_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(8))
    master_book: Mapped[str] = mapped_column(String(64))
    scheduled_time: Mapped[time] = mapped_column(Time)
    books_total: Mapped[int] = mapped_column(Integer)

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
    called_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_call_session", "investigation_session_id", "called_ts"),
    )
