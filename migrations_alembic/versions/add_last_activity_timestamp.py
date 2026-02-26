"""Add last_activity_timestamp to autotrade_configs

Revision ID: add_last_activity_timestamp
Revises: f659278ada58
Create Date: 2026-02-01 06:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_last_activity_timestamp'
down_revision = 'f659278ada58'
branch_labels = None
depends_on = None


def upgrade():
    """Add last_activity_timestamp column to autotrade_configs table"""
    op.add_column('autotrade_configs', sa.Column('last_activity_timestamp', sa.DateTime(), nullable=True))


def downgrade():
    """Remove last_activity_timestamp column from autotrade_configs table"""
    op.drop_column('autotrade_configs', 'last_activity_timestamp')
