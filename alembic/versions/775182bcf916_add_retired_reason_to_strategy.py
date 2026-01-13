"""add_retired_reason_to_strategy

Revision ID: 775182bcf916
Revises: 016_rename_training_holdout_to_is_oos
Create Date: 2026-01-13 14:15:22.859536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '775182bcf916'
down_revision: Union[str, Sequence[str], None] = '016_rename_training_holdout_to_is_oos'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retired_reason column to strategies table."""
    op.add_column('strategies', sa.Column('retired_reason', sa.String(50), nullable=True))


def downgrade() -> None:
    """Remove retired_reason column from strategies table."""
    op.drop_column('strategies', 'retired_reason')
