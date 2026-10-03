"""agent_session: one agent-harness session per L4 rec run

Revision ID: a9c4e2f7b1d5
Revises: f3b8d1c6a4e7
Create Date: 2026-10-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9c4e2f7b1d5"
down_revision: Union[str, Sequence[str], None] = "f3b8d1c6a4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_session",
        sa.Column("agent_session_id", sa.String(64), primary_key=True),
        sa.Column(
            "investigation_session_id", sa.String(64),
            sa.ForeignKey("investigation_session.investigation_session_id"),
            nullable=False, unique=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("harness_session_id", sa.String(128), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("caller", postgresql.JSONB(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("breaks", postgresql.JSONB(), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_session_token_hash", "agent_session", ["token_hash"])


def downgrade() -> None:
    op.drop_index("ix_agent_session_token_hash", table_name="agent_session")
    op.drop_table("agent_session")
