import sqlite3

def main():
    db_path = 'c:/Users/Leandro/Downloads/backend/data/autotrade.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print('Tabelas:')
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for row in cursor.fetchall():
        print(row[0])
        cursor.execute(f'PRAGMA table_info({row[0]})')
        for col in cursor.fetchall():
            print('   ', col)
    conn.close()

if __name__ == '__main__':
    main()
