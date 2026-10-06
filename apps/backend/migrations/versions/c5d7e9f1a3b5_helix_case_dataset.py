"""helix case data sets (named reference data beside the items)

Revision ID: c5d7e9f1a3b5
Revises: b4c6d8e0f2a3
Create Date: 2026-10-06 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c5d7e9f1a3b5'
down_revision: Union[str, Sequence[str], None] = 'b4c6d8e0f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'helix_case_dataset',
        sa.Column('case_id', sa.String(length=128), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('step_id', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=256), nullable=False),
        sa.Column('rows', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['helix_case.case_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('case_id', 'name'),
    )


def downgrade() -> None:
    op.drop_table('helix_case_dataset')
