import sqlite3

conn = sqlite3.connect('data/database.db')
cursor = conn.cursor()

# Verificar colunas da tabela autotrade_configs
cursor.execute('PRAGMA table_info(autotrade_configs)')
columns = cursor.fetchall()

print("Colunas da tabela autotrade_configs:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Verificar se all_win_percentage existe
all_win_exists = any(col[1] == 'all_win_percentage' for col in columns)
if all_win_exists:
    print("\n✓ Campo all_win_percentage existe!")
else:
    print("\n✗ Campo all_win_percentage NÃO existe!")

conn.close()
