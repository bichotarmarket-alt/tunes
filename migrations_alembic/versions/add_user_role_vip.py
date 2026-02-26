"""Add user role and VIP dates

Revision ID: add_user_role_vip
Revises: add_last_activity_timestamp
Create Date: 2026-02-01 06:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_role_vip'
down_revision = 'add_last_activity_timestamp'
branch_labels = None
depends_on = None


def upgrade():
    """Add role, vip_start_date and vip_end_date columns to users table"""
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='free'))
    op.add_column('users', sa.Column('vip_start_date', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('vip_end_date', sa.DateTime(), nullable=True))


def downgrade():
    """Remove role, vip_start_date and vip_end_date columns from users table"""
    op.drop_column('users', 'vip_end_date')
    op.drop_column('users', 'vip_start_date')
    op.drop_column('users', 'role')
