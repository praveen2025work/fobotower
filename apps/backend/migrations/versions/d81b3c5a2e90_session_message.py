"""session message: the Helix session conversation

Revision ID: d81b3c5a2e90
Revises: c4f2a9e1b7d3
Create Date: 2026-09-23 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d81b3c5a2e90"
down_revision: Union[str, Sequence[str], None] = "c4f2a9e1b7d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_message",
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("investigation_session_id", sa.String(64),
                  sa.ForeignKey("investigation_session.investigation_session_id"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("blocks", postgresql.JSONB(), nullable=True),
        sa.Column("call_ids", postgresql.JSONB(), nullable=True),
        sa.Column("tone", sa.String(16), nullable=True),
        sa.Column("answered_by", sa.String(48), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_message_session", "session_message", ["investigation_session_id", "created_ts"])


def downgrade() -> None:
    op.drop_index("idx_message_session", table_name="session_message")
    op.drop_table("session_message")
