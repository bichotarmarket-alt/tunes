import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

# Adicionar coluna all_win_percentage à tabela autotrade_configs
try:
    cursor.execute('ALTER TABLE autotrade_configs ADD COLUMN all_win_percentage REAL DEFAULT 0.0 NOT NULL')
    conn.commit()
    print("Coluna all_win_percentage adicionada com sucesso")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Coluna all_win_percentage já existe")
    else:
        print(f"Erro: {e}")

conn.close()
