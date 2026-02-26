import sqlite3

conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Verificar tabela alembic_version
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
table_exists = cursor.fetchone()
print(f'Tabela alembic_version existe: {table_exists}')

if table_exists:
    cursor.execute("SELECT * FROM alembic_version")
    versions = cursor.fetchall()
    print(f'Versões atuais: {versions}')
else:
    print('Tabela alembic_version não existe')

conn.close()
