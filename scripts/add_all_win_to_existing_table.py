import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

# Verificar se o campo all_win_percentage existe
cursor.execute('PRAGMA table_info(autotrade_configs)')
columns = cursor.fetchall()
column_names = [col[1] for col in columns]

if 'all_win_percentage' not in column_names:
    print("Campo all_win_percentage não existe, adicionando...")
    cursor.execute('ALTER TABLE autotrade_configs ADD COLUMN all_win_percentage REAL DEFAULT 0.0 NOT NULL')
    conn.commit()
    print("✓ Campo all_win_percentage adicionado")
else:
    print("✓ Campo all_win_percentage já existe")

conn.close()
