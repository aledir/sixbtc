"""Fix recent_result_id FK to use SET NULL on delete

Revision ID: 009_fix_recent_result_fk_cascade
Revises: 008_trade_sync_fields
Create Date: 2026-01-02

Fixes the self-referencing FK on backtest_results.recent_result_id to use
ON DELETE SET NULL instead of NO ACTION. This prevents FK violations when
deleting BacktestResult records that are referenced by other records.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '009_fix_recent_result_fk_cascade'
down_revision = '5bda9bf19064'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old FK constraint
    op.drop_constraint('fk_backtest_results_recent_result', 'backtest_results', type_='foreignkey')

    # Re-create with ON DELETE SET NULL
    op.create_foreign_key(
        'fk_backtest_results_recent_result',
        'backtest_results',
        'backtest_results',
        ['recent_result_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop the new FK constraint
    op.drop_constraint('fk_backtest_results_recent_result', 'backtest_results', type_='foreignkey')

    # Re-create without ON DELETE clause (original behavior)
    op.create_foreign_key(
        'fk_backtest_results_recent_result',
        'backtest_results',
        'backtest_results',
        ['recent_result_id'],
        ['id']
    )
