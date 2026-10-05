"""helix case follow-ups for late items

Revision ID: f2a9c1d7e3b4
Revises: e8f1a2b3c4d5
Create Date: 2026-10-05 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2a9c1d7e3b4'
down_revision: Union[str, Sequence[str], None] = 'e8f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('helix_case', sa.Column('follow_up_of', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_helix_case_follow_up_of'), 'helix_case', ['follow_up_of'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_helix_case_follow_up_of'), table_name='helix_case')
    op.drop_column('helix_case', 'follow_up_of')
