"""add_execute_all_signals_to_autotrade_config

Revision ID: add_execute_all_signals
Revises: add_trade_timing
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_execute_all_signals'
down_revision = 'add_trade_timing'
branch_labels = None
depends_on = None


def upgrade():
    """Adicionar coluna execute_all_signals à tabela autotrade_configs"""
    # Adicionar a coluna com valor padrão False
    op.add_column('autotrade_configs',
                  sa.Column('execute_all_signals', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    """Remover coluna execute_all_signals da tabela autotrade_configs"""
    op.drop_column('autotrade_configs', 'execute_all_signals')
