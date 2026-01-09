"""Rename training/holdout to in_sample/out_of_sample in period_type

Revision ID: 016_rename_training_holdout_to_is_oos
Revises: b4312de95e92
Create Date: 2026-01-09

Terminology migration:
- 'training' -> 'in_sample' (IS)
- 'holdout' -> 'out_of_sample' (OOS)

This aligns with standard quantitative trading terminology.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '016_rename_training_holdout_to_is_oos'
down_revision = 'b4312de95e92'
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # Update period_type values in backtest_results table
    # 'training' -> 'in_sample'
    connection.execute(sa.text(
        "UPDATE backtest_results SET period_type = 'in_sample' WHERE period_type = 'training'"
    ))

    # 'holdout' -> 'out_of_sample'
    connection.execute(sa.text(
        "UPDATE backtest_results SET period_type = 'out_of_sample' WHERE period_type = 'holdout'"
    ))


def downgrade() -> None:
    connection = op.get_bind()

    # Revert: 'in_sample' -> 'training'
    connection.execute(sa.text(
        "UPDATE backtest_results SET period_type = 'training' WHERE period_type = 'in_sample'"
    ))

    # Revert: 'out_of_sample' -> 'holdout'
    connection.execute(sa.text(
        "UPDATE backtest_results SET period_type = 'holdout' WHERE period_type = 'out_of_sample'"
    ))
