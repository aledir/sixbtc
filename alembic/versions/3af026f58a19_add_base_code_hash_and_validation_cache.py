"""add_base_code_hash_and_validation_cache

Revision ID: 3af026f58a19
Revises: 4888110cfe92
Create Date: 2026-01-06 11:28:00.155711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3af026f58a19'
down_revision: Union[str, Sequence[str], None] = '4888110cfe92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create ValidationCache table for shuffle test caching
    op.create_table('validation_caches',
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('shuffle_passed', sa.Boolean(), nullable=False),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('code_hash')
    )

    # Add base_code_hash column to strategies for batch processing
    op.add_column('strategies', sa.Column('base_code_hash', sa.String(length=64), nullable=True))

    # Create indexes for efficient batch claim queries
    op.create_index('idx_status_base_code_hash', 'strategies', ['status', 'base_code_hash'], unique=False)
    op.create_index(op.f('ix_strategies_base_code_hash'), 'strategies', ['base_code_hash'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_strategies_base_code_hash'), table_name='strategies')
    op.drop_index('idx_status_base_code_hash', table_name='strategies')

    # Remove base_code_hash column
    op.drop_column('strategies', 'base_code_hash')

    # Drop ValidationCache table
    op.drop_table('validation_caches')
