import sqlite3

def add_initial_balance_column():
    conn = sqlite3.connect('autotrade.db')
    cursor = conn.cursor()

    try:
        # Verificar se a coluna já existe
        cursor.execute("PRAGMA table_info(autotrade_configs)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'initial_balance' in columns:
            print('Coluna initial_balance já existe')
            return

        # Adicionar a coluna
        cursor.execute('ALTER TABLE autotrade_configs ADD COLUMN initial_balance FLOAT')
        conn.commit()
        print('✓ Coluna initial_balance adicionada com sucesso')

    except Exception as e:
        print(f'Erro: {e}')
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    add_initial_balance_column()
