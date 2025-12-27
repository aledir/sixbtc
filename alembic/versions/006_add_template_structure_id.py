"""Add structure_id to strategy_templates table

Revision ID: 006_add_template_structure_id
Revises: 005_add_strategy_templates
Create Date: 2024-12-27

Adds structure_id column to strategy_templates table.
Structure ID maps to 21 valid template structures (1-21):
- 1-7: Long only structures
- 8-14: Short only structures
- 15-21: Bidirectional structures

Each structure defines which components are active:
- entry_long, entry_short
- take_profit, exit_indicator, time_exit
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_add_template_structure_id'
down_revision = '005_add_strategy_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add structure_id column to strategy_templates
    op.add_column('strategy_templates',
        sa.Column('structure_id', sa.Integer(), nullable=True)
    )

    # Create index for structure_id queries
    op.create_index(
        'idx_template_structure_id',
        'strategy_templates',
        ['structure_id']
    )

    # Create composite index for structure + type queries
    op.create_index(
        'idx_template_structure_type',
        'strategy_templates',
        ['structure_id', 'strategy_type']
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_template_structure_type', table_name='strategy_templates')
    op.drop_index('idx_template_structure_id', table_name='strategy_templates')

    # Drop column
    op.drop_column('strategy_templates', 'structure_id')
