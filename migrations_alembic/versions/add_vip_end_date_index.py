"""Add index for vip_end_date to improve VIP expiration queries

Revision ID: add_vip_end_date_index
Revises: 
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_vip_end_date_index'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create index on vip_end_date for fast expiration queries
    op.create_index(
        'ix_users_vip_end_date',
        'users',
        ['vip_end_date']
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_users_vip_end_date', table_name='users')
