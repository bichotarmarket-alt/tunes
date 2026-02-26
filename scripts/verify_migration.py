import sqlite3

conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Verificar colunas da tabela autotrade_configs
cursor.execute("PRAGMA table_info(autotrade_configs)")
columns = cursor.fetchall()
print('Colunas da tabela autotrade_configs:')
for col in columns:
    print(f'  - {col[1]} ({col[2]})')

# Verificar versão atual do alembic
cursor.execute("SELECT * FROM alembic_version")
version = cursor.fetchone()
print(f'\nVersão atual do alembic: {version}')

conn.close()
