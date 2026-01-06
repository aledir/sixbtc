"""add_strategy_events

Revision ID: 015_strategy_events
Revises: 0e81376af4a2
Create Date: 2026-01-06

Add strategy_events table for immutable pipeline event tracking.
Events persist even when strategies are deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = '015_strategy_events'
down_revision: Union[str, Sequence[str], None] = '0e81376af4a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create strategy_events table."""
    op.create_table(
        'strategy_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('strategy_id', UUID(as_uuid=True), nullable=True),
        sa.Column('strategy_name', sa.String(100), nullable=False, index=True),
        sa.Column('base_code_hash', sa.String(64), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('stage', sa.String(30), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('event_data', JSON(), nullable=True),
    )

    # Create indexes for efficient queries
    op.create_index('idx_events_timestamp', 'strategy_events', ['timestamp'])
    op.create_index('idx_events_stage_status', 'strategy_events', ['stage', 'status'])
    op.create_index('idx_events_type_time', 'strategy_events', ['event_type', 'timestamp'])
    op.create_index('idx_events_strategy_time', 'strategy_events', ['strategy_name', 'timestamp'])


def downgrade() -> None:
    """Drop strategy_events table."""
    op.drop_index('idx_events_strategy_time', table_name='strategy_events')
    op.drop_index('idx_events_type_time', table_name='strategy_events')
    op.drop_index('idx_events_stage_status', table_name='strategy_events')
    op.drop_index('idx_events_timestamp', table_name='strategy_events')
    op.drop_table('strategy_events')
