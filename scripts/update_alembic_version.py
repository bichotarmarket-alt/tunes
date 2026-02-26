import sqlite3

conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Atualizar a versão do alembic para add_initial_balance_field
cursor.execute("UPDATE alembic_version SET version_num = 'add_initial_balance_field'")
conn.commit()

# Verificar se foi atualizado
cursor.execute("SELECT * FROM alembic_version")
version = cursor.fetchone()
print(f'Versão atual do alembic após atualização: {version}')

conn.close()
