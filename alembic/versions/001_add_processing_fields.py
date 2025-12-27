"""Add processing_by and processing_started_at fields to strategies

Revision ID: 001_add_processing_fields
Revises:
Create Date: 2024-12-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_processing_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to strategies table
    op.add_column('strategies', sa.Column('processing_by', sa.String(100), nullable=True))
    op.add_column('strategies', sa.Column('processing_started_at', sa.DateTime(), nullable=True))

    # Add index for claim queries
    op.create_index('idx_status_processing', 'strategies', ['status', 'processing_by'])

    # Update strategy_status enum to include VALIDATED and FAILED
    # Note: PostgreSQL enum modification requires special handling
    # We need to add new values to the existing enum
    op.execute("ALTER TYPE strategy_status ADD VALUE IF NOT EXISTS 'VALIDATED' AFTER 'GENERATED'")
    op.execute("ALTER TYPE strategy_status ADD VALUE IF NOT EXISTS 'FAILED' AFTER 'RETIRED'")

    # Remove PENDING if it exists (merged into GENERATED workflow)
    # Note: Removing enum values is complex in PostgreSQL, skip for now


def downgrade() -> None:
    # Remove index
    op.drop_index('idx_status_processing', table_name='strategies')

    # Remove columns
    op.drop_column('strategies', 'processing_started_at')
    op.drop_column('strategies', 'processing_by')

    # Note: Removing enum values from PostgreSQL is complex and typically
    # requires recreating the type. For simplicity, we leave the enum values.
