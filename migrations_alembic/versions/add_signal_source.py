"""add signal_source column to signals table

Revision ID: add_signal_source
Revises: 
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by alembic.
revision = 'add_signal_source'
down_revision = None  # Will be set based on latest migration
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('signals', sa.Column('signal_source', sa.String(), nullable=True, server_default='indicators'))


def downgrade():
    op.drop_column('signals', 'signal_source')
