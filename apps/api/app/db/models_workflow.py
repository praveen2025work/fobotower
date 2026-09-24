"""Workflow versions: which LangGraph workflow runs, and who decided it.

The database is the authority. The checked-in YAML seeds version 1; after
that a version changes only through a draft that a second Product Control
user approves (app/workflow/versions.py). Nothing is ever deleted.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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

from app.db.base import Base

STATUSES = ("draft", "active", "superseded", "rejected")


class WorkflowVersion(Base):
    __tablename__ = "workflow_version"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'rejected')",
            name="ck_workflow_version_status",
        ),
        # Exactly one active version is a database guarantee, not a convention.
        Index(
            "uq_workflow_version_one_active", "status", unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    config: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16))
    based_on: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("workflow_version.number"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text)
    drafted_by: Mapped[str] = mapped_column(String(64))
    drafted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
