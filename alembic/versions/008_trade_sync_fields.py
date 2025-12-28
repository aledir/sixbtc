"""Add trade sync fields for Hyperliquid integration

Revision ID: 008_trade_sync_fields
Revises: 007_add_live_metrics
Create Date: 2025-12-28

Adds fields to Trade table for Hyperliquid sync:
- position_id: Hyperliquid exit_tid for dedup
- leverage: Actual leverage used
- entry_fee_usd, exit_fee_usd: Fee breakdown
- duration_minutes: Trade duration
- iteration, entry_iteration: Monitor cycle tracking
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008_trade_sync_fields'
down_revision = '007_add_live_metrics'
branch_labels = None
depends_on = None


def upgrade():
    # Add Hyperliquid sync fields to trades table
    op.add_column('trades', sa.Column('position_id', sa.String(255), nullable=True))
    op.add_column('trades', sa.Column('leverage', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('trades', sa.Column('entry_fee_usd', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('exit_fee_usd', sa.Float(), nullable=True))
    op.add_column('trades', sa.Column('duration_minutes', sa.Integer(), nullable=True))
    op.add_column('trades', sa.Column('iteration', sa.Integer(), nullable=True))
    op.add_column('trades', sa.Column('entry_iteration', sa.Integer(), nullable=True))

    # Create index on position_id for fast dedup lookups
    op.create_index('idx_trades_position_id', 'trades', ['position_id'])


def downgrade():
    # Remove index
    op.drop_index('idx_trades_position_id', table_name='trades')

    # Remove columns
    op.drop_column('trades', 'entry_iteration')
    op.drop_column('trades', 'iteration')
    op.drop_column('trades', 'duration_minutes')
    op.drop_column('trades', 'exit_fee_usd')
    op.drop_column('trades', 'entry_fee_usd')
    op.drop_column('trades', 'leverage')
    op.drop_column('trades', 'position_id')
