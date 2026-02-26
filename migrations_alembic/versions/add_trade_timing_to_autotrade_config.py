"""add_trade_timing_to_autotrade_config

Revision ID: add_trade_timing
Revises: 310e3b3a320c
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_trade_timing'
down_revision = '310e3b3a320c'
branch_labels = None
depends_on = None


def upgrade():
    """Adicionar coluna trade_timing à tabela autotrade_configs"""
    # Adicionar a coluna com valor padrão 'on_signal'
    op.add_column('autotrade_configs',
                  sa.Column('trade_timing', sa.String(), nullable=False, server_default='on_signal'))


def downgrade():
    """Remover coluna trade_timing da tabela autotrade_configs"""
    op.drop_column('autotrade_configs', 'trade_timing')
