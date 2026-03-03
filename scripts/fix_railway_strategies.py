#!/usr/bin/env python3
"""
Script para limpar a tabela 'strategies' no Railway
Uso: python scripts/fix_railway_strategies.py

Este script:
1. Remove TODAS as estratégias da tabela 'strategies'
2. Limpa a tabela de junção 'strategy_indicators'

⚠️  ATENÇÃO: Este script apaga dados! Use com cuidado!
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context


async def clean_strategies():
    """Limpa todas as estratégias do banco"""
    print("=" * 60)
    print("LIMPANDO TABELA 'strategies' - Railway Production")
    print("=" * 60)
    print("⚠️  ATENÇÃO: Este script irá apagar TODAS as estratégias!")
    print()
    
    async with get_db_context() as db:
        # Verificar o que existe antes
        print("Verificando dados atuais...")
        
        result = await db.execute(text("SELECT COUNT(*) FROM strategies"))
        strategy_count = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) FROM strategy_indicators"))
        link_count = result.scalar()
        
        print(f"📊 Estratégias encontradas: {strategy_count}")
        print(f"📊 Ligações strategy_indicators: {link_count}")
        
        if strategy_count == 0 and link_count == 0:
            print("\n✅ Tabelas já estão vazias. Nada a fazer.")
            return
        
        # Listar estratégias que serão removidas
        if strategy_count > 0:
            print("\nEstratégias que serão removidas:")
            result = await db.execute(
                text("SELECT name, type, user_id FROM strategies ORDER BY name")
            )
            for row in result.fetchall():
                user_short = row.user_id[:8] + "..." if row.user_id else "NULL"
                print(f"   ❌ {row.name} (type={row.type}, user={user_short})")
        
        # Remover ligações primeiro (foreign key constraint)
        print("\n" + "=" * 60)
        print("EXECUTANDO LIMPEZA...")
        print("=" * 60)
        
        if link_count > 0:
            await db.execute(text("DELETE FROM strategy_indicators"))
            print(f"   ✅ Removidas {link_count} ligações de strategy_indicators")
        
        # Remover estratégias
        if strategy_count > 0:
            await db.execute(text("DELETE FROM strategies"))
            print(f"   ✅ Removidas {strategy_count} estratégias")
        
        await db.commit()
        
        # Verificar resultado
        print("\n" + "=" * 60)
        print("VERIFICAÇÃO FINAL")
        print("=" * 60)
        
        result = await db.execute(text("SELECT COUNT(*) FROM strategies"))
        final_strategies = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) FROM strategy_indicators"))
        final_links = result.scalar()
        
        print(f"📊 Estratégias restantes: {final_strategies}")
        print(f"📊 Ligações restantes: {final_links}")
        
        if final_strategies == 0 and final_links == 0:
            print("\n✅ SUCESSO: Tabela 'strategies' foi limpa completamente!")
        else:
            print(f"\n⚠️  ATENÇÃO: Ainda existem {final_strategies} estratégias no banco")


if __name__ == "__main__":
    asyncio.run(clean_strategies())
