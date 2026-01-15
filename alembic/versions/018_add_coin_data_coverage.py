"""add_coin_data_coverage

Revision ID: 018_add_coin_data_coverage
Revises: 6d97260858eb
Create Date: 2026-01-15

Adds data_coverage_days column to coins table.
This tracks how many days of OHLCV data are available in cache,
allowing filtering of coins with insufficient data BEFORE strategy generation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '018_add_coin_data_coverage'
down_revision: Union[str, Sequence[str], None] = '6d97260858eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add data_coverage_days column to coins table."""
    op.add_column(
        'coins',
        sa.Column('data_coverage_days', sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    """Remove data_coverage_days column from coins table."""
    op.drop_column('coins', 'data_coverage_days')
