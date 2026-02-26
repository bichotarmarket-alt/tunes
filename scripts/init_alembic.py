import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

# Criar tabela alembic_version
cursor.execute('''
    CREATE TABLE IF NOT EXISTS alembic_version (
        version_num VARCHAR(32) NOT NULL
    )
''')

# Inserir versão inicial
cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('c883b7582031')")

conn.commit()
conn.close()

print("Tabela alembic_version criada com sucesso")
