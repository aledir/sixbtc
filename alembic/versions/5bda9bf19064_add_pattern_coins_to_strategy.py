"""add_pattern_coins_to_strategy

Revision ID: 5bda9bf19064
Revises: 008_trade_sync_fields
Create Date: 2025-12-28 17:36:49.283461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5bda9bf19064'
down_revision: Union[str, Sequence[str], None] = '008_trade_sync_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pattern_coins column to strategies table."""
    op.add_column('strategies', sa.Column('pattern_coins', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove pattern_coins column from strategies table."""
    op.drop_column('strategies', 'pattern_coins')
