import sqlite3

db_path = "autotrade.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Verificar se a coluna existe
cursor.execute("PRAGMA table_info(autotrade_configs)")
columns = cursor.fetchall()
print("Colunas da tabela autotrade_configs:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

# Verificar os dados da tabela
cursor.execute("SELECT * FROM autotrade_configs LIMIT 1")
row = cursor.fetchone()
if row:
    print("\nDados da primeira configuração:")
    cursor.execute("PRAGMA table_info(autotrade_configs)")
    columns = cursor.fetchall()
    for i, col in enumerate(columns):
        print(f"  {col[1]}: {row[i]}")
else:
    print("\nNenhuma configuração encontrada")

conn.close()
