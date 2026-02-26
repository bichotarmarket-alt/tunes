"""
Migração manual para adicionar colunas smart_reduction_cascading e smart_reduction_cascade_level
"""
import asyncio
import sqlite3
from pathlib import Path

# Encontrar arquivo do banco de dados
db_files = list(Path('.').glob('*.db'))
if not db_files:
    print("❌ Nenhum arquivo .db encontrado")
    exit(1)

db_path = db_files[0]
print(f"📁 Usando banco de dados: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar se colunas já existem
cursor.execute("PRAGMA table_info(autotrade_configs)")
columns = [col[1] for col in cursor.fetchall()]

print(f"📋 Colunas existentes em autotrade_configs: {len(columns)}")

# Adicionar smart_reduction_cascading se não existir
if 'smart_reduction_cascading' not in columns:
    print("➕ Adicionando coluna smart_reduction_cascading...")
    cursor.execute("""
        ALTER TABLE autotrade_configs 
        ADD COLUMN smart_reduction_cascading BOOLEAN DEFAULT 0
    """)
    print("✅ Coluna smart_reduction_cascading adicionada")
else:
    print("✓ Coluna smart_reduction_cascading já existe")

# Adicionar smart_reduction_cascade_level se não existir
if 'smart_reduction_cascade_level' not in columns:
    print("➕ Adicionando coluna smart_reduction_cascade_level...")
    cursor.execute("""
        ALTER TABLE autotrade_configs 
        ADD COLUMN smart_reduction_cascade_level INTEGER DEFAULT 0
    """)
    print("✅ Coluna smart_reduction_cascade_level adicionada")
else:
    print("✓ Coluna smart_reduction_cascade_level já existe")

conn.commit()
conn.close()

print("\n🎉 Migração concluída com sucesso!")
