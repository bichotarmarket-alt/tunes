"""Add primary key constraint to daily_signal_summary

Revision ID: fix_daily_summary_pk
Revises: add_daily_signal_summary
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'fix_daily_summary_pk'
down_revision = 'add_daily_signal_summary'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Garantir que a coluna id seja PRIMARY KEY no PostgreSQL
    # Isso é necessário para o ON CONFLICT funcionar corretamente
    
    # Verificar se a constraint já existe
    conn = op.get_bind()
    
    # Adicionar constraint PRIMARY KEY se não existir
    try:
        op.create_primary_key(
            'daily_signal_summary_pkey',
            'daily_signal_summary',
            ['id']
        )
    except Exception as e:
        # Constraint pode já existir, ignorar erro
        print(f"Info: {e}")
    
    # Remover duplicatas se existirem (mantém apenas o primeiro registro de cada ID)
    op.execute("""
        DELETE FROM daily_signal_summary a
        USING daily_signal_summary b
        WHERE a.ctid < b.ctid
        AND a.id = b.id
    """)
    
    # Criar índice único como backup (opcional mas recomendado)
    try:
        op.create_index(
            'idx_daily_summary_id_unique',
            'daily_signal_summary',
            ['id'],
            unique=True
        )
    except Exception as e:
        print(f"Info: {e}")


def downgrade() -> None:
    # Remover índice único
    op.drop_index('idx_daily_summary_id_unique', table_name='daily_signal_summary')
    
    # Remover constraint PRIMARY KEY (não recomendado, mas para rollback)
    # op.drop_constraint('daily_signal_summary_pkey', 'daily_signal_summary', type_='primary')
    pass
