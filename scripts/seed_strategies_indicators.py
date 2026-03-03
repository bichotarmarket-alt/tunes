#!/usr/bin/env python3
"""
Script para inserir estratégias e indicadores padrão no banco de dados
Execute: python scripts/seed_strategies_indicators.py
"""

import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import get_db_context
import json

# Indicadores padrão
DEFAULT_INDICATORS = [
    {
        "id": str(uuid.uuid4()),
        "name": "RSI Padrão",
        "type": "rsi",
        "description": "Índice de Força Relativa - identifica condições de sobrecompra/sobrevenda",
        "parameters": {"period": 14, "overbought": 70, "oversold": 30},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "MACD Padrão",
        "type": "macd",
        "description": "Convergência/Divergência de Médias Móveis - identifica tendências e reversões",
        "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Bollinger Bands",
        "type": "bollinger_bands",
        "description": "Bandas de Bollinger - identifica volatilidade e reversões de preço",
        "parameters": {"period": 20, "std_dev": 2},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "SMA 50",
        "type": "sma",
        "description": "Média Móvel Simples de 50 períodos - identifica tendência de longo prazo",
        "parameters": {"period": 50},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "EMA 20",
        "type": "ema",
        "description": "Média Móvel Exponencial de 20 períodos - identifica tendência de curto prazo",
        "parameters": {"period": 20},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Stochastic",
        "type": "stochastic",
        "description": "Oscilador Estocástico - identifica momentum e reversões",
        "parameters": {"k_period": 14, "d_period": 3, "slowing": 3, "overbought": 80, "oversold": 20},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "ATR",
        "type": "atr",
        "description": "Average True Range - mede volatilidade do mercado",
        "parameters": {"period": 14},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Zonas de Suporte/Resistência",
        "type": "zonas",
        "description": "Identifica zonas de suporte e resistência baseadas em máximas e mínimas históricas",
        "parameters": {"lookback_periods": 20, "zone_merge_distance": 0.001},
        "is_active": True,
        "is_default": True,
        "version": "1.0"
    }
]

# Buscar usuário e conta existentes
async def get_default_user_and_account(db):
    """Busca o primeiro usuário e conta existentes"""
    result = await db.execute(text("SELECT id FROM users LIMIT 1"))
    user_row = result.fetchone()
    
    result = await db.execute(text("SELECT id FROM accounts LIMIT 1"))
    account_row = result.fetchone()
    
    return user_row.id if user_row else None, account_row.id if account_row else None


async def seed_indicators(db):
    """Inserir indicadores padrão"""
    print("\n📊 Inserindo indicadores padrão...")
    
    for indicator in DEFAULT_INDICATORS:
        # Verificar se já existe um indicador com o mesmo nome
        result = await db.execute(
            text("SELECT id FROM indicators WHERE name = :name"),
            {"name": indicator["name"]}
        )
        if result.fetchone():
            print(f"   ⚠️  Indicador '{indicator['name']}' já existe, pulando...")
            continue
        
        await db.execute(
            text("""
                INSERT INTO indicators 
                (id, name, type, description, parameters, is_active, is_default, version, created_at, updated_at)
                VALUES (:id, :name, :type, :description, :parameters, :is_active, :is_default, :version, :created_at, :updated_at)
            """),
            {
                "id": indicator["id"],
                "name": indicator["name"],
                "type": indicator["type"],
                "description": indicator["description"],
                "parameters": json.dumps(indicator["parameters"]),
                "is_active": indicator["is_active"],
                "is_default": indicator["is_default"],
                "version": indicator["version"],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        print(f"   ✅ {indicator['name']} ({indicator['type']})")
    
    await db.commit()
    print(f"\n✅ Indicadores inseridos com sucesso!")


async def seed_strategies(db, user_id, account_id):
    """Inserir estratégias padrão"""
    if not user_id or not account_id:
        print("\n❌ ERRO: Não foi possível encontrar usuário ou conta padrão!")
        print("   Certifique-se de que existam usuários e contas no banco.")
        return
    
    print(f"\n📈 Inserindo estratégias padrão...")
    print(f"   Usuário: {user_id[:8]}... | Conta: {account_id[:8]}...")
    
    # Buscar IDs dos indicadores recém-criados
    result = await db.execute(
        text("SELECT id, type FROM indicators WHERE is_default = 1")
    )
    indicators = {row.type: row.id for row in result.fetchall()}
    
    if not indicators:
        print("   ❌ Nenhum indicador padrão encontrado!")
        return
    
    strategies = [
        {
            "id": str(uuid.uuid4()),
            "name": "RSI Reversão",
            "type": "rsi",
            "description": "Estratégia baseada em reversões do RSI quando atinge níveis extremos",
            "parameters": {"rsi_period": 14, "overbought": 70, "oversold": 30, "confirmation_candles": 1},
            "assets": ["EURUSD", "GBPUSD", "USDJPY"],
            "indicators": [indicators.get("rsi")] if indicators.get("rsi") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "MACD Tendência",
            "type": "macd",
            "description": "Estratégia baseada em cruzamentos do MACD para seguir tendência",
            "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "trend_confirmation": True},
            "assets": ["EURUSD", "AUDUSD", "USDCAD"],
            "indicators": [indicators.get("macd")] if indicators.get("macd") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Bollinger Breakout",
            "type": "bollinger",
            "description": "Estratégia baseada em breakouts das bandas de Bollinger",
            "parameters": {"bb_period": 20, "std_dev": 2, "confirmation_candles": 2},
            "assets": ["EURUSD", "GBPJPY", "XAUUSD"],
            "indicators": [indicators.get("bollinger_bands")] if indicators.get("bollinger_bands") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Médias Cruzadas",
            "type": "trend_following",
            "description": "Estratégia baseada em cruzamento de médias móveis (SMA 50 e EMA 20)",
            "parameters": {"fast_ma": 20, "slow_ma": 50, "ma_type": "crossover"},
            "assets": ["EURUSD", "USDJPY", "GBPUSD"],
            "indicators": [indicators.get("sma"), indicators.get("ema")] if indicators.get("sma") and indicators.get("ema") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Estocástico Reversão",
            "type": "mean_reversion",
            "description": "Estratégia baseada em reversões do oscilador estocástico",
            "parameters": {"k_period": 14, "d_period": 3, "overbought": 80, "oversold": 20},
            "assets": ["EURUSD", "AUDJPY", "NZDUSD"],
            "indicators": [indicators.get("stochastic")] if indicators.get("stochastic") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Confluência Multi-Indicador",
            "type": "confluence",
            "description": "Estratégia que combina RSI, MACD e Bollinger para alta confiança",
            "parameters": {
                "rsi_weight": 0.3, "macd_weight": 0.4, "bb_weight": 0.3,
                "min_confluence": 70, "confirmation_candles": 1
            },
            "assets": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"],
            "indicators": [
                indicators.get("rsi"), 
                indicators.get("macd"), 
                indicators.get("bollinger_bands")
            ]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Volatilidade ATR",
            "type": "scalping",
            "description": "Estratégia de scalping baseada em expansão de volatilidade (ATR)",
            "parameters": {"atr_period": 14, "atr_multiplier": 1.5, "min_volatility": 0.0005},
            "assets": ["EURUSD", "GBPJPY", "USDJPY"],
            "indicators": [indicators.get("atr")] if indicators.get("atr") else []
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Zonas S/R",
            "type": "breakout",
            "description": "Estratégia baseada em quebra de zonas de suporte e resistência",
            "parameters": {"lookback": 20, "zone_merge": 0.001, "breakout_confirmation": True},
            "assets": ["EURUSD", "USDJPY", "XAUUSD"],
            "indicators": [indicators.get("zonas")] if indicators.get("zonas") else []
        }
    ]
    
    for strategy in strategies:
        # Verificar se já existe estratégia com mesmo nome
        result = await db.execute(
            text("SELECT id FROM strategies WHERE name = :name"),
            {"name": strategy["name"]}
        )
        if result.fetchone():
            print(f"   ⚠️  Estratégia '{strategy['name']}' já existe, pulando...")
            continue
        
        # Inserir estratégia
        await db.execute(
            text("""
                INSERT INTO strategies 
                (id, user_id, account_id, name, type, parameters, assets, 
                 is_active, total_trades, winning_trades, losing_trades, 
                 total_profit, total_loss, created_at, updated_at)
                VALUES (:id, :user_id, :account_id, :name, :type, :parameters, :assets,
                        1, 0, 0, 0, 0.0, 0.0, :created_at, :updated_at)
            """),
            {
                "id": strategy["id"],
                "user_id": user_id,
                "account_id": account_id,
                "name": strategy["name"],
                "type": strategy["type"],
                "parameters": json.dumps(strategy["parameters"]),
                "assets": json.dumps(strategy["assets"]),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        )
        
        # Inserir relacionamentos na tabela strategy_indicators
        for indicator_id in strategy["indicators"]:
            if indicator_id:
                await db.execute(
                    text("""
                        INSERT OR IGNORE INTO strategy_indicators 
                        (strategy_id, indicator_id, parameters, created_at)
                        VALUES (:strategy_id, :indicator_id, '{}', :created_at)
                    """),
                    {
                        "strategy_id": strategy["id"],
                        "indicator_id": indicator_id,
                        "created_at": datetime.utcnow()
                    }
                )
        
        print(f"   ✅ {strategy['name']} ({strategy['type']})")
    
    await db.commit()
    print(f"\n✅ Estratégias inseridas com sucesso!")


async def main():
    """Função principal"""
    print("=" * 60)
    print("SEED DE ESTRATÉGIAS E INDICADORES PADRÃO")
    print("=" * 60)
    
    async with get_db_context() as db:
        try:
            # Inserir indicadores
            await seed_indicators(db)
            
            # Buscar usuário e conta padrão
            user_id, account_id = await get_default_user_and_account(db)
            
            # Inserir estratégias
            await seed_strategies(db, user_id, account_id)
            
            # Resumo final
            print("\n" + "=" * 60)
            print("RESUMO")
            print("=" * 60)
            
            result = await db.execute(text("SELECT COUNT(*) FROM indicators"))
            print(f"📊 Total de indicadores: {result.scalar()}")
            
            result = await db.execute(text("SELECT COUNT(*) FROM strategies"))
            print(f"📈 Total de estratégias: {result.scalar()}")
            
            print("\n✅ SEED CONCLUÍDO COM SUCESSO!")
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
