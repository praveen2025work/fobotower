"""decision break ids: which breaks each controller decision covered

Revision ID: e5a7c3d9f1b2
Revises: d81b3c5a2e90
Create Date: 2026-09-23 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5a7c3d9f1b2"
down_revision: Union[str, Sequence[str], None] = "d81b3c5a2e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("controller_decision", sa.Column("break_ids", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("controller_decision", "break_ids")
