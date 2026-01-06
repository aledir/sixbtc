"""add_multi_window_to_validation_cache

Revision ID: 0e81376af4a2
Revises: 3af026f58a19
Create Date: 2026-01-06 13:41:10.856656

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0e81376af4a2'
down_revision: Union[str, Sequence[str], None] = '3af026f58a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add multi_window columns to validation_caches table."""
    # Add multi_window_passed column
    op.add_column(
        'validation_caches',
        sa.Column('multi_window_passed', sa.Boolean(), nullable=True)
    )
    # Add multi_window_reason column
    op.add_column(
        'validation_caches',
        sa.Column('multi_window_reason', sa.String(200), nullable=True)
    )
    # Also make shuffle_passed nullable (it was NOT NULL before)
    op.alter_column(
        'validation_caches',
        'shuffle_passed',
        existing_type=sa.Boolean(),
        nullable=True
    )


def downgrade() -> None:
    """Remove multi_window columns from validation_caches table."""
    op.drop_column('validation_caches', 'multi_window_reason')
    op.drop_column('validation_caches', 'multi_window_passed')
    op.alter_column(
        'validation_caches',
        'shuffle_passed',
        existing_type=sa.Boolean(),
        nullable=False
    )
