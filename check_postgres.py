#!/usr/bin/env python3
"""Verificar tabelas do PostgreSQL local"""
import asyncio
import asyncpg
import json

async def check_database():
    DATABASE_URL = "postgresql://postgres:root@localhost:5432/tunestrade"
    
    print("="*60)
    print("Conectando ao PostgreSQL local...")
    print("="*60)
    
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Listar tabelas
        rows = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [r['table_name'] for r in rows]
        print("\nTABELAS NO BANCO:")
        for t in tables:
            print(f"  - {t}")
        
        # Verificar tabela indicators
        if 'indicators' in tables:
            print("\n" + "="*60)
            print("TABELA 'indicators' - Conteúdo:")
            print("="*60)
            rows = await conn.fetch("SELECT id, name, type, is_default FROM indicators ORDER BY name")
            print(f"Total de registros: {len(rows)}")
            for row in rows:
                print(f"  - {row['name']} (type={row['type']}, default={row['is_default']})")
        
        # Verificar tabela strategies
        if 'strategies' in tables:
            print("\n" + "="*60)
            print("TABELA 'strategies' - Conteúdo:")
            print("="*60)
            rows = await conn.fetch("SELECT id, name, type, user_id FROM strategies ORDER BY name")
            print(f"Total de registros: {len(rows)}")
            for row in rows:
                user_short = row['user_id'][:8] + "..." if row['user_id'] else "NULL"
                print(f"  - {row['name']} (type={row['type']}, user={user_short})")
        
        # Verificar tabela strategy_indicators
        if 'strategy_indicators' in tables:
            print("\n" + "="*60)
            print("TABELA 'strategy_indicators' - Conteúdo:")
            print("="*60)
            try:
                rows = await conn.fetch("SELECT strategy_id, indicator_id, parameters FROM strategy_indicators")
                print(f"Total de registros: {len(rows)}")
                for row in rows:
                    params = row['parameters'] if row['parameters'] else '{}'
                    print(f"  - strategy={row['strategy_id'][:8]}... indicator={row['indicator_id'][:8]}... params={params[:30]}")
            except Exception as e:
                print(f"Erro: {e}")
        
        # Verificar se há indicadores na tabela strategies (ERRO!)
        print("\n" + "="*60)
        print("VERIFICAÇÃO DE ERRO: Indicadores na tabela strategies?")
        print("="*60)
        rows = await conn.fetch("""
            SELECT s.name, s.type, s.user_id 
            FROM strategies s 
            WHERE s.type IN ('rsi', 'macd', 'bollinger_bands', 'sma', 'ema', 'stochastic', 'atr', 'cci', 'williams_r', 'roc', 'vwap', 'obv', 'parabolic_sar', 'ichimoku_cloud', 'money_flow_index', 'average_directional_index', 'keltner_channels', 'donchian_channels', 'heiken_ashi', 'pivot_points', 'supertrend', 'fibonacci_retracement', 'zonas')
            ORDER BY s.name
        """)
        if rows:
            print(f"❌ ERRO: Encontrados {len(rows)} 'indicadores' na tabela strategies:")
            for row in rows:
                user_short = row['user_id'][:8] + "..." if row['user_id'] else "NULL"
                print(f"   - {row['name']} (type={row['type']}, user={user_short}) ← DEVE SER REMOVIDO!")
        else:
            print("✅ OK: Nenhum indicador encontrado na tabela strategies")
        
        # Verificar total de indicadores na tabela indicators
        print("\n" + "="*60)
        print("TABELA 'indicators' - Total de indicadores do sistema:")
        print("="*60)
        rows = await conn.fetch("SELECT COUNT(*) as total FROM indicators WHERE is_default = true")
        default_count = rows[0]['total']
        rows = await conn.fetch("SELECT COUNT(*) as total FROM indicators")
        total_count = rows[0]['total']
        print(f"Indicadores padrão (is_default=true): {default_count}")
        print(f"Total de indicadores: {total_count}")
        if default_count < 23:
            print(f"❌ FALTAM {23 - default_count} INDICADORES PADRÃO!")
        elif default_count == 23:
            print("✅ OK: Temos exatamente 23 indicadores padrão")
        else:
            print(f"⚠️  ATENÇÃO: Temos {default_count} indicadores padrão (esperado: 23)")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())
