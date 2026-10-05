"""helix evidence requests (ask the desk, a trader, Operations)

Revision ID: a3b5c7d9e1f2
Revises: f2a9c1d7e3b4
Create Date: 2026-10-05 21:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3b5c7d9e1f2'
down_revision: Union[str, Sequence[str], None] = 'f2a9c1d7e3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'helix_info_request',
        sa.Column('request_id', sa.String(length=64), nullable=False),
        sa.Column('case_id', sa.String(length=128), nullable=False),
        sa.Column('group_id', sa.String(length=128), nullable=True),
        sa.Column('target', sa.String(length=64), nullable=False),
        sa.Column('target_name', sa.String(length=128), nullable=False),
        sa.Column('roles', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('users', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('asked_by', sa.String(length=64), nullable=False),
        sa.Column('asked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('answered_by', sa.String(length=64), nullable=True),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['helix_case.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('request_id'),
    )
    op.create_index(op.f('ix_helix_info_request_case_id'), 'helix_info_request', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_helix_info_request_case_id'), table_name='helix_info_request')
    op.drop_table('helix_info_request')
