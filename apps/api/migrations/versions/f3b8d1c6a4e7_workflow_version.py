"""workflow versions: the database decides which workflow runs

Revision ID: f3b8d1c6a4e7
Revises: e5a7c3d9f1b2
Create Date: 2026-09-24 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f3b8d1c6a4e7"
down_revision: Union[str, Sequence[str], None] = "e5a7c3d9f1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_version",
        sa.Column("number", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("based_on", sa.Integer(), sa.ForeignKey("workflow_version.number"), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("drafted_by", sa.String(64), nullable=False),
        sa.Column("drafted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("decision_key", sa.String(128), nullable=True, unique=True),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'rejected')",
            name="ck_workflow_version_status",
        ),
    )
    op.create_index(
        "uq_workflow_version_one_active", "workflow_version", ["status"],
        unique=True, postgresql_where=sa.text("status = 'active'"),
    )
    op.add_column(
        "investigation_session",
        sa.Column("workflow_version", sa.Integer(),
                  sa.ForeignKey("workflow_version.number"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("investigation_session", "workflow_version")
    op.drop_index("uq_workflow_version_one_active", table_name="workflow_version")
    op.drop_table("workflow_version")
