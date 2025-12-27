"""Add dual-period backtest fields to backtest_results

Revision ID: 004_add_dual_period_backtest
Revises: 003_add_coins_table
Create Date: 2024-12-24

Adds fields for dual-period backtesting:
- period_type: 'full' or 'recent'
- period_days: number of days in this backtest period
- weighted_sharpe, weighted_win_rate, weighted_expectancy
- recency_ratio: recent_sharpe / full_sharpe (measures if strategy is "in form")
- recency_penalty: 0-20% penalty for poor recent performance
- recent_result_id: FK to corresponding recent period result
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '004_add_dual_period_backtest'
down_revision = '003_add_coins_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add dual-period backtest fields
    op.add_column('backtest_results',
        sa.Column('period_type', sa.String(20), nullable=True, server_default='full')
    )
    op.add_column('backtest_results',
        sa.Column('period_days', sa.Integer(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('weighted_sharpe', sa.Float(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('weighted_win_rate', sa.Float(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('weighted_expectancy', sa.Float(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('recency_ratio', sa.Float(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('recency_penalty', sa.Float(), nullable=True)
    )
    op.add_column('backtest_results',
        sa.Column('recent_result_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraint for recent_result_id
    op.create_foreign_key(
        'fk_backtest_results_recent_result',
        'backtest_results',
        'backtest_results',
        ['recent_result_id'],
        ['id']
    )

    # Set existing rows to 'full' period type
    op.execute("UPDATE backtest_results SET period_type = 'full' WHERE period_type IS NULL")


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_backtest_results_recent_result', 'backtest_results', type_='foreignkey')

    # Drop columns
    op.drop_column('backtest_results', 'recent_result_id')
    op.drop_column('backtest_results', 'recency_penalty')
    op.drop_column('backtest_results', 'recency_ratio')
    op.drop_column('backtest_results', 'weighted_expectancy')
    op.drop_column('backtest_results', 'weighted_win_rate')
    op.drop_column('backtest_results', 'weighted_sharpe')
    op.drop_column('backtest_results', 'period_days')
    op.drop_column('backtest_results', 'period_type')
