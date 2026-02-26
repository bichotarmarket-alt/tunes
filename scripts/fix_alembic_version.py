import sqlite3

conn = sqlite3.connect('autotrade.db')
cursor = conn.cursor()

# Limpar todas as versões
cursor.execute("DELETE FROM alembic_version")
conn.commit()

# Definir a única versão correta (a mais recente que existe)
# Usando a versão mais recente que existe: add_parameters_to_strategy_indicators
cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('add_parameters_to_strategy_indicators')")
conn.commit()

print('Tabela alembic_version limpa e versão definida para: add_parameters_to_strategy_indicators')

conn.close()
