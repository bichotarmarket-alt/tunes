"""
Script para limpar registros duplicados na tabela daily_signal_summary

Execute este script antes de iniciar a aplicação para corrigir o erro:
"UPDATE statement on table 'daily_signal_summary' expected to update 1 row(s); 2 were matched"
"""
import asyncio
import aiosqlite
from datetime import datetime


async def cleanup_duplicates():
    """Remover registros duplicados da tabela daily_signal_summary"""
    db_path = "./autotrade.db"
    
    print("[CLEANUP] Conectando ao banco de dados...")
    async with aiosqlite.connect(db_path) as db:
        # Verificar duplicatas
        print("[CLEANUP] Verificando duplicatas...")
        cursor = await db.execute("""
            SELECT id, COUNT(*) as count 
            FROM daily_signal_summary 
            GROUP BY id 
            HAVING count > 1
        """)
        duplicates = await cursor.fetchall()
        
        if not duplicates:
            print("[CLEANUP] Nenhuma duplicata encontrada.")
            return
        
        print(f"[CLEANUP] Encontrados {len(duplicates)} IDs duplicados:")
        for dup_id, count in duplicates:
            print(f"  - ID: {dup_id} ({count} registros)")
        
        # Remover duplicatas mantendo apenas o mais recente (ou o primeiro)
        print("[CLEANUP] Removendo duplicatas...")
        for dup_id, count in duplicates:
            # Deletar todos exceto o primeiro (menor rowid)
            await db.execute("""
                DELETE FROM daily_signal_summary 
                WHERE id = ? AND rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM daily_signal_summary 
                    WHERE id = ?
                )
            """, (dup_id, dup_id))
            print(f"  - Removidos {count-1} duplicados para ID: {dup_id}")
        
        await db.commit()
        
        # Verificar resultado
        cursor = await db.execute("""
            SELECT COUNT(*) FROM daily_signal_summary
        """)
        total = await cursor.fetchone()
        print(f"[CLEANUP] Total de registros após limpeza: {total[0]}")
        
        # Criar índice único se não existir (para prevenir futuras duplicatas)
        try:
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_summary_id_unique 
                ON daily_signal_summary(id)
            """)
            print("[CLEANUP] Índice único criado/verificado com sucesso")
        except Exception as e:
            print(f"[CLEANUP] Aviso: Não foi possível criar índice único: {e}")
        
        await db.commit()
    
    print("[CLEANUP] Limpeza concluída!")


if __name__ == "__main__":
    print("=" * 60)
    print("LIMPEZA DE DUPLICATAS - daily_signal_summary")
    print("=" * 60)
    asyncio.run(cleanup_duplicates())
