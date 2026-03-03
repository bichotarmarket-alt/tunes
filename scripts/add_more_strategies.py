#!/usr/bin/env python3
"""
Script para adicionar mais estratégias (total 23)
Execute: python scripts/add_more_strategies.py
"""

import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import get_db_context
import json

# 15 estratégias adicionais
ADDITIONAL_STRATEGIES = [
    {
        "name": "Parabolic SAR Trend",
        "type": "trend_following",
        "description": "Estratégia de seguimento de tendência usando Parabolic SAR",
        "parameters": {"initial_af": 0.02, "max_af": 0.2, "step_af": 0.02, "trend_confirmation": True},
        "assets": ["EURUSD", "GBPUSD", "AUDUSD"],
        "indicator_types": ["parabolic_sar"]
    },
    {
        "name": "Ichimoku Cloud Break",
        "type": "breakout",
        "description": "Estratégia baseada em quebras do Ichimoku Cloud",
        "parameters": {"tenkan_period": 9, "kijun_period": 26, "senkou_span_b_period": 52, "confirmation_candles": 2},
        "assets": ["EURUSD", "USDJPY", "XAUUSD"],
        "indicator_types": ["ichimoku_cloud"]
    },
    {
        "name": "MFI Volume Momentum",
        "type": "momentum",
        "description": "Estratégia de momentum usando Money Flow Index com volume",
        "parameters": {"period": 14, "overbought": 80, "oversold": 20},
        "assets": ["EURUSD", "GBPUSD", "USDCHF"],
        "indicator_types": ["money_flow_index"]
    },
    {
        "name": "ADX Trend Strength",
        "type": "trend_following",
        "description": "Estratégia baseada na força da tendência com ADX",
        "parameters": {"period": 14, "adx_threshold": 25, "di_period": 14},
        "assets": ["EURUSD", "AUDJPY", "GBPJPY"],
        "indicator_types": ["average_directional_index"]
    },
    {
        "name": "Keltner Channel Break",
        "type": "breakout",
        "description": "Estratégia de breakout usando canais de Keltner",
        "parameters": {"ema_period": 20, "atr_period": 20, "multiplier": 2.0, "confirmation": True},
        "assets": ["EURUSD", "GBPUSD", "USDCAD"],
        "indicator_types": ["keltner_channels"]
    },
    {
        "name": "Donchian Channel Trend",
        "type": "trend_following",
        "description": "Estratégia de seguimento de tendência com canais de Donchian",
        "parameters": {"period": 20, "breakout_confirmation": True},
        "assets": ["EURUSD", "XAUUSD", "USDJPY"],
        "indicator_types": ["donchian_channels"]
    },
    {
        "name": "Heiken Ashi Smooth",
        "type": "trend_following",
        "description": "Estratégia usando candles Heiken Ashi para suavização de preço",
        "parameters": {"confirmation_candles": 2, "trend_filter": True},
        "assets": ["EURUSD", "GBPUSD", "AUDUSD"],
        "indicator_types": ["heiken_ashi"]
    },
    {
        "name": "Pivot Points Reversal",
        "type": "mean_reversion",
        "description": "Estratégia de reversão em pontos de pivô",
        "parameters": {"pivot_type": "standard", "support_resistance_buffer": 0.001},
        "assets": ["EURUSD", "USDJPY", "GBPUSD"],
        "indicator_types": ["pivot_points"]
    },
    {
        "name": "Supertrend Signals",
        "type": "trend_following",
        "description": "Estratégia de sinais usando indicador Supertrend",
        "parameters": {"atr_period": 10, "multiplier": 3.0, "confirmation": True},
        "assets": ["EURUSD", "GBPJPY", "XAUUSD"],
        "indicator_types": ["supertrend"]
    },
    {
        "name": "Fibonacci Retracement",
        "type": "mean_reversion",
        "description": "Estratégia de reversão em níveis de Fibonacci",
        "parameters": {"lookback": 50, "levels": [0.382, 0.5, 0.618], "confirmation": True},
        "assets": ["EURUSD", "GBPUSD", "XAUUSD"],
        "indicator_types": ["fibonacci_retracement"]
    },
    {
        "name": "RSI + Stochastic Combo",
        "type": "confluence",
        "description": "Combinação de RSI e Estocástico para alta confiança",
        "parameters": {"rsi_period": 14, "stoch_period": 14, "min_confluence": 70},
        "assets": ["EURUSD", "GBPUSD", "USDJPY"],
        "indicator_types": ["rsi", "stochastic"]
    },
    {
        "name": "MACD + ADX Power",
        "type": "confluence",
        "description": "MACD com confirmação de força via ADX",
        "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9, "adx_threshold": 25},
        "assets": ["EURUSD", "AUDUSD", "USDCAD"],
        "indicator_types": ["macd", "average_directional_index"]
    },
    {
        "name": "Bollinger + RSI Squeeze",
        "type": "confluence",
        "description": "Squeeze de Bollinger com confirmação de RSI",
        "parameters": {"bb_period": 20, "std_dev": 2, "rsi_period": 14, "rsi_confirmation": True},
        "assets": ["EURUSD", "GBPJPY", "XAUUSD"],
        "indicator_types": ["bollinger_bands", "rsi"]
    },
    {
        "name": "Parabolic + Supertrend",
        "type": "trend_following",
        "description": "Confirmação dupla de tendência com Parabolic SAR e Supertrend",
        "parameters": {"sar_af": 0.02, "supertrend_multiplier": 3.0, "confirmation": True},
        "assets": ["EURUSD", "GBPUSD", "USDJPY"],
        "indicator_types": ["parabolic_sar", "supertrend"]
    },
    {
        "name": "Ichimoku + Keltner Hybrid",
        "type": "confluence",
        "description": "Estratégia híbrida usando Ichimoku e Keltner Channels",
        "parameters": {"tenkan": 9, "kijun": 26, "keltner_ema": 20, "keltner_multiplier": 2.0},
        "assets": ["EURUSD", "XAUUSD", "AUDJPY"],
        "indicator_types": ["ichimoku_cloud", "keltner_channels"]
    }
]


async def add_more_strategies():
    """Adicionar mais estratégias ao banco"""
    print("=" * 60)
    print("ADICIONANDO MAIS ESTRATÉGIAS (15 novas)")
    print("=" * 60)
    
    async with get_db_context() as db:
        # Buscar usuário e conta
        result = await db.execute(text("SELECT id FROM users LIMIT 1"))
        user_row = result.fetchone()
        
        result = await db.execute(text("SELECT id FROM accounts LIMIT 1"))
        account_row = result.fetchone()
        
        if not user_row or not account_row:
            print("❌ Usuário ou conta não encontrados!")
            return
        
        user_id = user_row.id
        account_id = account_row.id
        
        print(f"Usuário: {user_id[:8]}... | Conta: {account_id[:8]}...")
        
        # Buscar indicadores
        result = await db.execute(text("SELECT id, type FROM indicators"))
        indicators = {row.type: row.id for row in result.fetchall()}
        print(f"\nIndicadores disponíveis: {len(indicators)}")
        
        added = 0
        skipped = 0
        
        for strategy in ADDITIONAL_STRATEGIES:
            # Verificar se já existe
            result = await db.execute(
                text("SELECT id FROM strategies WHERE name = :name"),
                {"name": strategy["name"]}
            )
            if result.fetchone():
                print(f"   ⚠️  '{strategy['name']}' já existe")
                skipped += 1
                continue
            
            # Buscar IDs dos indicadores
            indicator_ids = []
            for ind_type in strategy["indicator_types"]:
                if ind_type in indicators:
                    indicator_ids.append(indicators[ind_type])
            
            # Inserir estratégia
            strategy_id = str(uuid.uuid4())
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
                    "id": strategy_id,
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
            
            # Inserir relacionamentos
            for ind_id in indicator_ids:
                await db.execute(
                    text("""
                        INSERT OR IGNORE INTO strategy_indicators 
                        (strategy_id, indicator_id, parameters, created_at)
                        VALUES (:strategy_id, :indicator_id, '{}', :created_at)
                    """),
                    {
                        "strategy_id": strategy_id,
                        "indicator_id": ind_id,
                        "created_at": datetime.utcnow()
                    }
                )
            
            print(f"   ✅ {strategy['name']}")
            added += 1
        
        await db.commit()
        
        # Resumo
        print("\n" + "=" * 60)
        print("RESUMO")
        print("=" * 60)
        
        result = await db.execute(text("SELECT COUNT(*) FROM strategies"))
        total = result.scalar()
        
        print(f"📈 Estratégias adicionadas: {added}")
        print(f"⏭️  Estratégias puladas (já existiam): {skipped}")
        print(f"📊 Total de estratégias no banco: {total}")
        
        # Listar todas
        result = await db.execute(
            text("SELECT name, type FROM strategies ORDER BY name")
        )
        print(f"\nLista completa ({total} estratégias):")
        for row in result.fetchall():
            print(f"   • {row.name} ({row.type})")


if __name__ == "__main__":
    asyncio.run(add_more_strategies())
