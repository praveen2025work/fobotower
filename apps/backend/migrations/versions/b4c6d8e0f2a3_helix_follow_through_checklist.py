"""helix follow-through, sign-off checklist, question reminders and attachments

Revision ID: b4c6d8e0f2a3
Revises: a3b5c7d9e1f2
Create Date: 2026-10-05 23:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b4c6d8e0f2a3'
down_revision: Union[str, Sequence[str], None] = 'a3b5c7d9e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'helix_follow_through',
        sa.Column('case_id', sa.String(length=128), nullable=False),
        sa.Column('item_id', sa.String(length=256), nullable=False),
        sa.Column('verdict', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('checked_in', sa.String(length=128), nullable=False),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['helix_case.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('case_id', 'item_id'),
    )
    op.add_column('helix_decision', sa.Column('checklist', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('helix_info_request', sa.Column('attachment', sa.String(length=256), nullable=True))
    op.add_column('helix_info_request', sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('helix_info_request', sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('helix_info_request', 'escalated_at')
    op.drop_column('helix_info_request', 'reminded_at')
    op.drop_column('helix_info_request', 'attachment')
    op.drop_column('helix_decision', 'checklist')
    op.drop_table('helix_follow_through')
