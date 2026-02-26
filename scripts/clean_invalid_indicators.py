import sqlite3

INVALID_INDICATORS = ['momentum', 'adx']

def main():
    db_path = '../data/autotrade.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Remover indicadores inválidos da tabela strategy_indicators
    for ind in INVALID_INDICATORS:
        cursor.execute("DELETE FROM strategy_indicators WHERE indicator_id IN (SELECT id FROM indicator WHERE type = ?)", (ind,))
        cursor.execute("DELETE FROM indicator WHERE type = ?", (ind,))

    conn.commit()
    print('Indicadores inválidos removidos com sucesso.')
    conn.close()

if __name__ == '__main__':
    main()
