"""add initial_balance field to autotrade_configs

Revision ID: add_initial_balance_field
Revises: rename_initial_to_highest
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_initial_balance_field'
down_revision = 'rename_initial_to_highest'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adicionar coluna initial_balance se não existir
    import sqlite3
    from sqlalchemy import inspect, text

    # Verificar se a coluna já existe
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('autotrade_configs')]

    if 'initial_balance' not in columns:
        op.add_column('autotrade_configs', sa.Column('initial_balance', sa.Float(), nullable=True))
    else:
        print("Coluna initial_balance já existe, pulando criação")


def downgrade() -> None:
    # Remove initial_balance column
    op.drop_column('autotrade_configs', 'initial_balance')
