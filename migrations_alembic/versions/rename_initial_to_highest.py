"""rename initial_balance to highest_balance

Revision ID: rename_initial_to_highest
Revises: 310e3b3a320c
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_initial_to_highest'
down_revision = '310e3b3a320c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adicionar coluna highest_balance se não existir
    from sqlalchemy import inspect

    # Verificar se a coluna já existe
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('autotrade_configs')]

    if 'highest_balance' not in columns:
        op.add_column('autotrade_configs', sa.Column('highest_balance', sa.Float(), nullable=True))
    else:
        print("Coluna highest_balance já existe, pulando criação")


def downgrade() -> None:
    # Remover coluna highest_balance
    op.drop_column('autotrade_configs', 'highest_balance')
