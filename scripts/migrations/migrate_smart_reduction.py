"""
Script de migration para adicionar colunas de Redução Inteligente na tabela autotrade_configs
"""
import sqlite3
import os
from pathlib import Path

# Caminho do banco de dados
db_path = Path(__file__).parent / "autotrade.db"

if not db_path.exists():
    print(f"Banco de dados não encontrado em: {db_path}")
    # Tentar outro nome
    db_path = Path(__file__).parent / "tunestrade.db"
    if not db_path.exists():
        print(f"Banco de dados não encontrado em: {db_path}")
        db_path = Path(__file__).parent / "database.db"
        if not db_path.exists():
            print("Nenhum banco de dados encontrado!")
            exit(1)

print(f"Usando banco de dados: {db_path}")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Verificar colunas existentes
cursor.execute("PRAGMA table_info(autotrade_configs)")
columns = [col[1] for col in cursor.fetchall()]
print(f"Colunas existentes: {columns}")

# Adicionar colunas se não existirem
columns_to_add = [
    ("smart_reduction_enabled", "BOOLEAN DEFAULT 0"),
    ("smart_reduction_loss_trigger", "INTEGER DEFAULT 3"),
    ("smart_reduction_win_restore", "INTEGER DEFAULT 2"),
    ("smart_reduction_percentage", "FLOAT DEFAULT 50.0"),
    ("smart_reduction_active", "BOOLEAN DEFAULT 0"),
    ("smart_reduction_base_amount", "FLOAT DEFAULT 0.0"),
]

for col_name, col_type in columns_to_add:
    if col_name not in columns:
        try:
            cursor.execute(f"ALTER TABLE autotrade_configs ADD COLUMN {col_name} {col_type}")
            print(f"✅ Coluna '{col_name}' adicionada com sucesso!")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"⚠️ Coluna '{col_name}' já existe")
            else:
                print(f"❌ Erro ao adicionar '{col_name}': {e}")
    else:
        print(f"⚠️ Coluna '{col_name}' já existe")

conn.commit()
conn.close()
print("\n✅ Migration concluída!")
