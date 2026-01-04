"""Add scheduled tasks tracking tables

Revision ID: 012_add_scheduled_tasks_tracking
Revises: 5bda9bf19064
Create Date: 2026-01-04

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '012_add_scheduled_tasks_tracking'
down_revision: Union[str, Sequence[str], None] = '010_add_pipeline_timestamps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Scheduled task executions table
    op.create_table(
        'scheduled_task_executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_name', sa.String(100), nullable=False, index=True),
        sa.Column('task_type', sa.String(50), nullable=False, index=True),  # 'scheduler', 'data_update', 'manual'
        sa.Column('status', sa.String(20), nullable=False, index=True),  # 'RUNNING', 'SUCCESS', 'FAILED'

        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float, nullable=True),

        # Results
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('task_metadata', JSONB, nullable=True),  # Flexible JSON for task-specific data

        # Who triggered it
        sa.Column('triggered_by', sa.String(100), nullable=True),  # 'system', 'user:email', 'api'
    )

    # Composite index for common queries
    op.create_index(
        'idx_task_executions_lookup',
        'scheduled_task_executions',
        ['task_name', 'started_at']
    )

    # Pairs update detailed log table
    op.create_table(
        'pairs_update_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('execution_id', UUID(as_uuid=True),
                  sa.ForeignKey('scheduled_task_executions.id', ondelete='CASCADE'),
                  nullable=False, index=True),

        # Update summary
        sa.Column('total_pairs', sa.Integer, nullable=False),
        sa.Column('new_pairs', sa.Integer, nullable=False),
        sa.Column('updated_pairs', sa.Integer, nullable=False),
        sa.Column('deactivated_pairs', sa.Integer, nullable=False),

        # Top pairs snapshot
        sa.Column('top_10_symbols', JSONB, nullable=True),  # Array of symbols

        # Timestamp
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('pairs_update_log')
    op.drop_table('scheduled_task_executions')
