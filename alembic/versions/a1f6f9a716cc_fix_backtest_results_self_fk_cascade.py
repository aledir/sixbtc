"""fix_backtest_results_self_fk_cascade

Revision ID: a1f6f9a716cc
Revises: a066baad48f7
Create Date: 2026-01-04 22:54:02.307846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f6f9a716cc'
down_revision: Union[str, Sequence[str], None] = 'a066baad48f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fix self-referencing FK to use ON DELETE SET NULL."""
    # Drop the existing constraint
    op.drop_constraint(
        'backtest_results_recent_result_id_fkey',
        'backtest_results',
        type_='foreignkey'
    )

    # Recreate with ON DELETE SET NULL
    op.create_foreign_key(
        'backtest_results_recent_result_id_fkey',
        'backtest_results',
        'backtest_results',
        ['recent_result_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Revert to original constraint without cascade."""
    op.drop_constraint(
        'backtest_results_recent_result_id_fkey',
        'backtest_results',
        type_='foreignkey'
    )

    op.create_foreign_key(
        'backtest_results_recent_result_id_fkey',
        'backtest_results',
        'backtest_results',
        ['recent_result_id'],
        ['id']
    )
