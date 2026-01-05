"""Rename TESTED to ACTIVE state, remove SELECTED, add last_backtested_at

Revision ID: 014_rename_tested_to_active
Revises: a1f6f9a716cc
Create Date: 2026-01-05

Pipeline restructuring:
- TESTED -> ACTIVE (pool-based with leaderboard logic)
- SELECTED removed (direct ACTIVE -> LIVE flow)
- Add last_backtested_at for re-backtest scheduling
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '014_rename_tested_to_active'
down_revision = 'a1f6f9a716cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add ACTIVE to the strategy_status enum
    # Must use connection.execute with COMMIT to make enum value available
    connection = op.get_bind()
    connection.execute(sa.text("COMMIT"))  # End current transaction
    connection.execute(sa.text("ALTER TYPE strategy_status ADD VALUE IF NOT EXISTS 'ACTIVE'"))

    # Step 2: Update all TESTED strategies to ACTIVE
    connection.execute(sa.text("UPDATE strategies SET status = 'ACTIVE' WHERE status = 'TESTED'"))

    # Step 3: Update all SELECTED strategies to ACTIVE (they were waiting for deployment)
    connection.execute(sa.text("UPDATE strategies SET status = 'ACTIVE' WHERE status = 'SELECTED'"))

    # Step 4: Add last_backtested_at column for re-backtest scheduling
    op.add_column('strategies', sa.Column('last_backtested_at', sa.DateTime(), nullable=True))

    # Step 5: Initialize last_backtested_at from tested_at for existing ACTIVE strategies
    connection.execute(sa.text("""
        UPDATE strategies
        SET last_backtested_at = tested_at
        WHERE status = 'ACTIVE' AND tested_at IS NOT NULL
    """))

    # Step 6: Add index for efficient re-backtest queries (FIFO order)
    op.create_index('idx_last_backtested', 'strategies', ['last_backtested_at'])

    # Step 7: Update pipeline_metrics_snapshots - add queue_active and utilization_active
    # Note: We're adding new columns and keeping the old ones for backwards compatibility
    op.add_column('pipeline_metrics_snapshots',
                  sa.Column('queue_active', sa.Integer(), nullable=True, default=0))
    op.add_column('pipeline_metrics_snapshots',
                  sa.Column('utilization_active', sa.Float(), nullable=True))

    # Copy data from old columns to new columns
    connection.execute(sa.text("UPDATE pipeline_metrics_snapshots SET queue_active = queue_tested"))
    connection.execute(sa.text("UPDATE pipeline_metrics_snapshots SET utilization_active = utilization_tested"))


def downgrade() -> None:
    connection = op.get_bind()

    # Revert ACTIVE -> TESTED
    connection.execute(sa.text("UPDATE strategies SET status = 'TESTED' WHERE status = 'ACTIVE'"))

    # Revert utilization_active and queue_active
    op.drop_column('pipeline_metrics_snapshots', 'utilization_active')
    op.drop_column('pipeline_metrics_snapshots', 'queue_active')

    # Revert index
    op.drop_index('idx_last_backtested', table_name='strategies')

    # Revert last_backtested_at column
    op.drop_column('strategies', 'last_backtested_at')

    # Note: Cannot remove enum values in PostgreSQL without recreating the type
    # The ACTIVE and old TESTED/SELECTED values will remain in the enum
