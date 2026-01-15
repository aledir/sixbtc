"""remove_deprecated_pattern_coins_backtest_pairs

Revision ID: 0b44290a73b2
Revises: 017_add_trading_coins
Create Date: 2026-01-14 13:10:01.215869

Remove deprecated columns pattern_coins and backtest_pairs.
All strategies now use the unified trading_coins field.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = '0b44290a73b2'
down_revision: Union[str, Sequence[str], None] = '017_add_trading_coins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove deprecated columns."""
    op.drop_column('strategies', 'pattern_coins')
    op.drop_column('strategies', 'backtest_pairs')


def downgrade() -> None:
    """Restore deprecated columns (for rollback only)."""
    op.add_column('strategies', sa.Column('backtest_pairs', JSON, nullable=True))
    op.add_column('strategies', sa.Column('pattern_coins', JSON, nullable=True))
