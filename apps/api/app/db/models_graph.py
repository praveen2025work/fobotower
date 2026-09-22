from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Node(Base):
    __tablename__ = "node"
    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32))
    natural_key: Mapped[str] = mapped_column(String(128))
    legal_entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    recorded_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_node_type_key", "node_type", "natural_key"),
        Index("idx_node_entity", "legal_entity_id", "node_type"),
    )


class Edge(Base):
    __tablename__ = "edge"
    edge_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    from_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    to_node_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    edge_type: Mapped[str] = mapped_column(String(32))
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    recorded_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("idx_edge_from", "from_node_id", "edge_type", "valid_from", "valid_to"),
        Index("idx_edge_to", "to_node_id", "edge_type", "valid_from", "valid_to"),
    )


class BreakEvent(Base):
    """Event layer. Deliberately not bitemporal."""

    __tablename__ = "break_event"
    break_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    book_id: Mapped[str] = mapped_column(String(64), ForeignKey("node.node_id"))
    line_code: Mapped[str] = mapped_column(String(32))
    cob_date: Mapped[date] = mapped_column(Date)
    fo_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    bo_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    pattern_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The wording a controller reads on the adjustment row, e.g.
    # "Nostro statement received after 23:30 cutoff".
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A figure in this break's draft could not be traced to source data.
    is_ungrounded: Mapped[bool] = mapped_column(Boolean, default=False)
    # The run this break first appeared in. Later runs carrying the same
    # break_id make it aged; that span is the "carried N runs" badge.
    first_seen_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recorded_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_similar_breaks", "book_id", "line_code", "cob_date"),)


class BreakEmbedding(Base):
    __tablename__ = "break_embedding"
    break_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("break_event.break_id"), primary_key=True
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    model_identifier: Mapped[str] = mapped_column(String(64))
    embedded_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
