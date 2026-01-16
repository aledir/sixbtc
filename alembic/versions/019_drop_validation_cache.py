"""drop_validation_cache

Revision ID: 019_drop_validation_cache
Revises: 018_add_coin_data_coverage
Create Date: 2026-01-16

Removes the validation_caches table.
Shuffle test caching was removed because each base produces only one
winning strategy, making caching unnecessary complexity.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '019_drop_validation_cache'
down_revision: Union[str, Sequence[str], None] = '018_add_coin_data_coverage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop validation_caches table."""
    op.drop_table('validation_caches')


def downgrade() -> None:
    """Recreate validation_caches table."""
    op.create_table('validation_caches',
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('shuffle_passed', sa.Boolean(), nullable=True),
        sa.Column('multi_window_passed', sa.Boolean(), nullable=True),
        sa.Column('multi_window_reason', sa.String(length=200), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('code_hash')
    )
