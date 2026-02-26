import sqlite3

conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Verificar todas as versões na tabela
cursor.execute("SELECT * FROM alembic_version")
versions = cursor.fetchall()
print(f'Versões na tabela alembic_version: {versions}')

# Limpar todas as versões
cursor.execute("DELETE FROM alembic_version")
conn.commit()

# Inserir a versão correta
cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('add_initial_balance_field')")
conn.commit()

# Verificar se foi atualizado
cursor.execute("SELECT * FROM alembic_version")
version = cursor.fetchone()
print(f'Versão atual do alembic após atualização: {version}')

conn.close()
