"""Add all_win_percentage to autotrade_configs

Revision ID: add_all_win_percentage
Revises: add_trade_timing
Create Date: 2026-02-11 21:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_all_win_percentage'
down_revision = 'add_trade_timing'
branch_labels = None
depends_on = None


def upgrade():
    # Add all_win_percentage column to autotrade_configs table
    op.add_column('autotrade_configs', sa.Column('all_win_percentage', sa.Float(), nullable=False, server_default='0.0'))


def downgrade():
    # Remove all_win_percentage column from autotrade_configs table
    op.drop_column('autotrade_configs', 'all_win_percentage')
