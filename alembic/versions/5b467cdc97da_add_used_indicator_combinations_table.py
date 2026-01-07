"""add_used_indicator_combinations_table

Revision ID: 5b467cdc97da
Revises: 015_strategy_events
Create Date: 2026-01-06 19:06:45.142708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5b467cdc97da'
down_revision: Union[str, Sequence[str], None] = '015_strategy_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create used_indicator_combinations table for tracking AI strategy variety
    op.create_table('used_indicator_combinations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_type', sa.String(length=10), nullable=False),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('main_indicators', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('filter_indicators', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_type', 'timeframe', 'main_indicators', 'filter_indicators', name='uq_indicator_combination')
    )
    op.create_index('idx_combo_type_tf', 'used_indicator_combinations', ['strategy_type', 'timeframe'], unique=False)
    op.create_index(op.f('ix_used_indicator_combinations_strategy_type'), 'used_indicator_combinations', ['strategy_type'], unique=False)
    op.create_index(op.f('ix_used_indicator_combinations_timeframe'), 'used_indicator_combinations', ['timeframe'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop used_indicator_combinations table
    op.drop_index(op.f('ix_used_indicator_combinations_timeframe'), table_name='used_indicator_combinations')
    op.drop_index(op.f('ix_used_indicator_combinations_strategy_type'), table_name='used_indicator_combinations')
    op.drop_index('idx_combo_type_tf', table_name='used_indicator_combinations')
    op.drop_table('used_indicator_combinations')
