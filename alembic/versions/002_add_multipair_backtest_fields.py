"""Add multi-pair backtest and TF optimization fields

Revision ID: 002_add_multipair_backtest_fields
Revises: 001_add_processing_fields
Create Date: 2024-12-22

Adds fields for:
- Strategy: optimal_timeframe, backtest_pairs, backtest_date
- BacktestResult: symbols_tested, timeframe_tested, is_optimal_tf
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '002_add_multipair_backtest_fields'
down_revision = '001_add_processing_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to strategies table
    op.add_column('strategies', sa.Column('optimal_timeframe', sa.String(10), nullable=True))
    op.add_column('strategies', sa.Column('backtest_pairs', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('strategies', sa.Column('backtest_date', sa.DateTime(), nullable=True))

    # Add new columns to backtest_results table
    op.add_column('backtest_results', sa.Column('symbols_tested', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('backtest_results', sa.Column('timeframe_tested', sa.String(10), nullable=True))
    op.add_column('backtest_results', sa.Column('is_optimal_tf', sa.Boolean(), nullable=True, default=False))


def downgrade() -> None:
    # Remove columns from backtest_results
    op.drop_column('backtest_results', 'is_optimal_tf')
    op.drop_column('backtest_results', 'timeframe_tested')
    op.drop_column('backtest_results', 'symbols_tested')

    # Remove columns from strategies
    op.drop_column('strategies', 'backtest_date')
    op.drop_column('strategies', 'backtest_pairs')
    op.drop_column('strategies', 'optimal_timeframe')
