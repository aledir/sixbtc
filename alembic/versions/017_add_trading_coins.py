"""add_trading_coins

Revision ID: 017_add_trading_coins
Revises: 5f728cbb7dcf
Create Date: 2026-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = '017_add_trading_coins'
down_revision: Union[str, Sequence[str], None] = '5f728cbb7dcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trading_coins column and migrate existing data."""
    # Add trading_coins column
    op.add_column('strategies', sa.Column('trading_coins', JSON, nullable=True))

    # Migrate existing data: trading_coins = COALESCE(pattern_coins, backtest_pairs)
    op.execute("""
        UPDATE strategies
        SET trading_coins = COALESCE(pattern_coins, backtest_pairs)
        WHERE pattern_coins IS NOT NULL OR backtest_pairs IS NOT NULL
    """)


def downgrade() -> None:
    """Remove trading_coins column."""
    op.drop_column('strategies', 'trading_coins')
