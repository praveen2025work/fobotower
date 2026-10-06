"""helix waiting, child cases and clocks (steps v2 phases 2–6)

Revision ID: d6e8f0a2b4c6
Revises: c5d7e9f1a3b5
Create Date: 2026-10-06 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd6e8f0a2b4c6'
down_revision: Union[str, Sequence[str], None] = 'c5d7e9f1a3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('helix_case', 'status', type_=sa.String(length=64), existing_type=sa.String(length=24))
    op.add_column('helix_case', sa.Column('parent_case_id', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_helix_case_parent_case_id'), 'helix_case', ['parent_case_id'], unique=False)
    op.add_column('helix_case', sa.Column('waiting_since', sa.DateTime(timezone=True), nullable=True))
    op.add_column('helix_case', sa.Column('clock_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('helix_case', 'clock_state')
    op.drop_column('helix_case', 'waiting_since')
    op.drop_index(op.f('ix_helix_case_parent_case_id'), table_name='helix_case')
    op.drop_column('helix_case', 'parent_case_id')
    op.alter_column('helix_case', 'status', type_=sa.String(length=24), existing_type=sa.String(length=64))
