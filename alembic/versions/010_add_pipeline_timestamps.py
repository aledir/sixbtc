"""Add pipeline timestamp columns to strategies

Revision ID: 010_add_pipeline_timestamps
Revises: 009_fix_recent_result_fk_cascade
Create Date: 2026-01-04

Merges both migration branches:
- Branch 1: 009_fix_recent_result_fk_cascade
- Branch 2: (implicit merge)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_add_pipeline_timestamps'
down_revision = '009_fix_recent_result_fk_cascade'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add pipeline completion timestamp columns
    op.add_column('strategies', sa.Column('validation_completed_at', sa.DateTime(), nullable=True))
    op.add_column('strategies', sa.Column('backtest_completed_at', sa.DateTime(), nullable=True))
    op.add_column('strategies', sa.Column('processing_completed_at', sa.DateTime(), nullable=True))

    # Add indexes for performance (querying by completion time)
    op.create_index('idx_validation_completed', 'strategies', ['validation_completed_at'])
    op.create_index('idx_backtest_completed', 'strategies', ['backtest_completed_at'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_backtest_completed', table_name='strategies')
    op.drop_index('idx_validation_completed', table_name='strategies')

    # Remove columns
    op.drop_column('strategies', 'processing_completed_at')
    op.drop_column('strategies', 'backtest_completed_at')
    op.drop_column('strategies', 'validation_completed_at')
