"""Add strategy_templates table and template fields to strategies

Revision ID: 005_add_strategy_templates
Revises: 004_add_dual_period_backtest
Create Date: 2024-12-26

Adds:
- strategy_templates table for parameterized templates
- template_id, generation_mode, parameters fields to strategies table
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '005_add_strategy_templates'
down_revision = '004_add_dual_period_backtest'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create strategy_templates table
    op.create_table(
        'strategy_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('strategy_type', sa.String(50), nullable=False, index=True),
        sa.Column('timeframe', sa.String(10), nullable=False, index=True),
        sa.Column('code_template', sa.Text(), nullable=False),
        sa.Column('parameters_schema', postgresql.JSON(), nullable=False),
        sa.Column('ai_provider', sa.String(50), nullable=True),
        sa.Column('generation_prompt', sa.Text(), nullable=True),
        sa.Column('strategies_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('strategies_profitable', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create composite index for type + timeframe queries
    op.create_index(
        'idx_template_type_timeframe',
        'strategy_templates',
        ['strategy_type', 'timeframe']
    )

    # Add template-related columns to strategies table
    op.add_column('strategies',
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column('strategies',
        sa.Column('generation_mode', sa.String(20), nullable=True, server_default='ai')
    )
    op.add_column('strategies',
        sa.Column('parameters', postgresql.JSON(), nullable=True)
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_strategies_template',
        'strategies',
        'strategy_templates',
        ['template_id'],
        ['id']
    )

    # Create index on template_id for fast lookups
    op.create_index(
        'idx_strategies_template_id',
        'strategies',
        ['template_id']
    )

    # Set existing rows to 'ai' generation mode
    op.execute("UPDATE strategies SET generation_mode = 'ai' WHERE generation_mode IS NULL")


def downgrade() -> None:
    # Drop foreign key and index from strategies
    op.drop_constraint('fk_strategies_template', 'strategies', type_='foreignkey')
    op.drop_index('idx_strategies_template_id', table_name='strategies')

    # Drop columns from strategies
    op.drop_column('strategies', 'parameters')
    op.drop_column('strategies', 'generation_mode')
    op.drop_column('strategies', 'template_id')

    # Drop strategy_templates table
    op.drop_index('idx_template_type_timeframe', table_name='strategy_templates')
    op.drop_table('strategy_templates')
