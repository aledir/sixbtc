"""add weighted metrics to backtest results

Revision ID: 011_add_weighted_metrics
Revises: 010_add_pipeline_timestamps
Create Date: 2026-01-04

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '013_add_weighted_metrics'
down_revision = '012_add_scheduled_tasks_tracking'
branch_labels = None
depends_on = None


def upgrade():
    # Add new weighted metric columns for accurate classifier ranking
    # These store training (40%) + holdout (60%) weighted values
    # Note: weighted_sharpe, weighted_win_rate, weighted_expectancy already exist
    op.add_column('backtest_results',
        sa.Column('weighted_sharpe_pure', sa.Float(), nullable=True,
                 comment='Sharpe ratio weighted: training*0.4 + holdout*0.6'))
    op.add_column('backtest_results',
        sa.Column('weighted_walk_forward_stability', sa.Float(), nullable=True,
                 comment='Walk-forward stability weighted: training*0.4 + holdout*0.6'))


def downgrade():
    op.drop_column('backtest_results', 'weighted_walk_forward_stability')
    op.drop_column('backtest_results', 'weighted_sharpe_pure')
