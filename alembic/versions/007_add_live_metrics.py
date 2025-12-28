"""Add live performance metrics to strategies table

Revision ID: 006_add_live_metrics
Revises: 005_add_strategy_templates
Create Date: 2024-12-28

Adds live performance tracking fields to strategies table for dual-ranking system:
- score_backtest: Cached backtest score for ranking
- score_live: Composite score from live trades
- win_rate_live, expectancy_live, sharpe_live, max_drawdown_live
- total_trades_live, total_pnl_live
- last_live_update: Timestamp of last metrics update
- live_degradation_pct: Comparison of live vs backtest performance
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_live_metrics'
down_revision = '006_add_template_structure_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add backtest score (cached for ranking)
    op.add_column('strategies',
        sa.Column('score_backtest', sa.Float(), nullable=True)
    )

    # Add live performance metrics
    op.add_column('strategies',
        sa.Column('score_live', sa.Float(), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('win_rate_live', sa.Float(), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('expectancy_live', sa.Float(), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('sharpe_live', sa.Float(), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('max_drawdown_live', sa.Float(), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('total_trades_live', sa.Integer(), nullable=True, server_default='0')
    )
    op.add_column('strategies',
        sa.Column('total_pnl_live', sa.Float(), nullable=True, server_default='0.0')
    )
    op.add_column('strategies',
        sa.Column('last_live_update', sa.DateTime(), nullable=True)
    )

    # Add degradation tracking
    op.add_column('strategies',
        sa.Column('live_degradation_pct', sa.Float(), nullable=True)
    )

    # Create indexes for ranking queries
    op.create_index(
        'idx_strategies_score_backtest',
        'strategies',
        ['score_backtest'],
        postgresql_where=sa.text("status IN ('TESTED', 'SELECTED')")
    )
    op.create_index(
        'idx_strategies_score_live',
        'strategies',
        ['score_live'],
        postgresql_where=sa.text("status = 'LIVE'")
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_strategies_score_live', table_name='strategies')
    op.drop_index('idx_strategies_score_backtest', table_name='strategies')

    # Drop columns
    op.drop_column('strategies', 'live_degradation_pct')
    op.drop_column('strategies', 'last_live_update')
    op.drop_column('strategies', 'total_pnl_live')
    op.drop_column('strategies', 'total_trades_live')
    op.drop_column('strategies', 'max_drawdown_live')
    op.drop_column('strategies', 'sharpe_live')
    op.drop_column('strategies', 'expectancy_live')
    op.drop_column('strategies', 'win_rate_live')
    op.drop_column('strategies', 'score_live')
    op.drop_column('strategies', 'score_backtest')
