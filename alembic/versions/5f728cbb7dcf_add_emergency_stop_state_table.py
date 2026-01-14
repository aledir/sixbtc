"""add_emergency_stop_state_table

Revision ID: 5f728cbb7dcf
Revises: 775182bcf916
Create Date: 2026-01-13 17:50:00.979358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f728cbb7dcf'
down_revision: Union[str, Sequence[str], None] = '775182bcf916'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create emergency_stop_states table
    op.create_table(
        'emergency_stop_states',
        sa.Column('scope', sa.String(20), primary_key=True),
        sa.Column('scope_id', sa.String(50), primary_key=True),
        sa.Column('is_stopped', sa.Boolean(), nullable=False, default=False),
        sa.Column('stop_reason', sa.String(200), nullable=True),
        sa.Column('stop_action', sa.String(20), nullable=True),
        sa.Column('stopped_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cooldown_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_trigger', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Create indexes
    op.create_index('idx_emergency_stop_is_stopped', 'emergency_stop_states', ['is_stopped'])
    op.create_index('idx_emergency_stop_scope', 'emergency_stop_states', ['scope'])

    # Add new columns to subaccounts table for emergency stop tracking
    op.add_column('subaccounts', sa.Column('peak_balance', sa.Float(), nullable=True))
    op.add_column('subaccounts', sa.Column('peak_balance_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subaccounts', sa.Column('daily_pnl_usd', sa.Float(), default=0.0, nullable=True))
    op.add_column('subaccounts', sa.Column('daily_pnl_reset_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from subaccounts
    op.drop_column('subaccounts', 'daily_pnl_reset_date')
    op.drop_column('subaccounts', 'daily_pnl_usd')
    op.drop_column('subaccounts', 'peak_balance_updated_at')
    op.drop_column('subaccounts', 'peak_balance')

    # Drop indexes and table
    op.drop_index('idx_emergency_stop_scope', 'emergency_stop_states')
    op.drop_index('idx_emergency_stop_is_stopped', 'emergency_stop_states')
    op.drop_table('emergency_stop_states')
