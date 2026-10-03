"""helix catalogue: rec group, ready events, book stats, call rows

Revision ID: c4f2a9e1b7d3
Revises: 96ecd3baf0aa
Create Date: 2026-09-23 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c4f2a9e1b7d3"
down_revision: Union[str, Sequence[str], None] = "96ecd3baf0aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reconciliation", sa.Column("rec_group", sa.String(16), nullable=False, server_default="CATS-MOTIF"))
    op.add_column("reconciliation", sa.Column("l4", sa.String(64), nullable=False, server_default=""))
    op.add_column("reconciliation", sa.Column("ccy", sa.String(3), nullable=False, server_default="USD"))
    op.add_column("run", sa.Column("ready_event_id", sa.String(32), nullable=True))
    op.add_column("run", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("run", sa.Column("mb_available", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("run", sa.Column("mb_reported_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("run", sa.Column("book_stats", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.add_column("run", sa.Column("books_unlocked", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("source_call", sa.Column("result_rows", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("source_call", "result_rows")
    for col in ("books_unlocked", "book_stats", "mb_reported_at", "mb_available", "ready_at", "ready_event_id"):
        op.drop_column("run", col)
    for col in ("ccy", "l4", "rec_group"):
        op.drop_column("reconciliation", col)
