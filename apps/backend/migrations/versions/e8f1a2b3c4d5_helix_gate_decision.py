"""helix tollgate decisions

Revision ID: e8f1a2b3c4d5
Revises: d224c0604a72
Create Date: 2026-10-05 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e8f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd224c0604a72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'helix_gate_decision',
        sa.Column('gate_id', sa.String(length=64), nullable=False),
        sa.Column('case_id', sa.String(length=128), nullable=False),
        sa.Column('step', sa.String(length=32), nullable=False),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('decided_by', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['helix_case.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('gate_id'),
        sa.UniqueConstraint('idempotency_key'),
    )
    op.create_index(op.f('ix_helix_gate_decision_case_id'), 'helix_gate_decision', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_helix_gate_decision_case_id'), table_name='helix_gate_decision')
    op.drop_table('helix_gate_decision')
