"""Add parameters column to strategy_indicators table

Revision ID: add_parameters_to_strategy_indicators
Revises: 310e3b3a320c
Create Date: 2026-01-22 04:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_parameters_to_strategy_indicators'
down_revision = '310e3b3a320c'
branch_labels = None
depends_on = None


def upgrade():
    """Add parameters column to strategy_indicators table"""
    op.add_column('strategy_indicators',
                  sa.Column('parameters', sa.JSON(), nullable=True, server_default='{}'))


def downgrade():
    """Remove parameters column from strategy_indicators table"""
    op.drop_column('strategy_indicators', 'parameters')
