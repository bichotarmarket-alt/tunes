"""Add smart_reduction_cascading columns to autotrade_configs

Revision ID: add_smart_reduction_cascading
Revises: add_last_activity_timestamp
Create Date: 2026-02-25 12:00:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_smart_reduction_cascading'
down_revision = 'add_last_activity_timestamp'
branch_labels = None
depends_on = None


def upgrade():
    # Add smart_reduction_cascading column
    op.add_column('autotrade_configs', sa.Column('smart_reduction_cascading', sa.Boolean(), nullable=True, default=False))
    # Add smart_reduction_cascade_level column
    op.add_column('autotrade_configs', sa.Column('smart_reduction_cascade_level', sa.Integer(), nullable=True, default=0))


def downgrade():
    # Remove columns
    op.drop_column('autotrade_configs', 'smart_reduction_cascading')
    op.drop_column('autotrade_configs', 'smart_reduction_cascade_level')
