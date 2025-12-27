"""Add coins table for max_leverage and trading pair data

Revision ID: 003_add_coins_table
Revises: 002_add_multipair_backtest_fields
Create Date: 2024-12-23

Adds:
- coins table: symbol, max_leverage, volume_24h, price, is_active, updated_at
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_add_coins_table'
down_revision = '002_add_multipair_backtest_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'coins',
        sa.Column('symbol', sa.String(20), primary_key=True),
        sa.Column('max_leverage', sa.Integer(), nullable=False),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # Index for active coins lookup
    op.create_index('idx_coins_is_active', 'coins', ['is_active'])


def downgrade() -> None:
    op.drop_index('idx_coins_is_active', table_name='coins')
    op.drop_table('coins')
