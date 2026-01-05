"""add_weighted_max_drawdown_column

Revision ID: 4888110cfe92
Revises: 014_rename_tested_to_active
Create Date: 2026-01-05 16:53:53.961602

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4888110cfe92'
down_revision: Union[str, Sequence[str], None] = '014_rename_tested_to_active'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('backtest_results', sa.Column('weighted_max_drawdown', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('backtest_results', 'weighted_max_drawdown')
