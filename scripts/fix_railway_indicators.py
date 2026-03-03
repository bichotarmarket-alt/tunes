#!/usr/bin/env python3
"""
Script para popular a tabela 'indicators' com os 23 indicadores padrão do sistema
Uso: python scripts/fix_railway_indicators.py

Este script:
1. Insere os 23 indicadores padrão na tabela 'indicators'
2. Marca todos como is_default = true
"""
import asyncio
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context

# 23 Indicadores padrão do sistema
DEFAULT_INDICATORS = [
    {
        "name": "RSI - Relative Strength Index",
        "type": "rsi",
        "description": "Índice de Força Relativa - identifica condições de sobrecompra/sobrevenda",
        "parameters": {"period": 14, "overbought": 70, "oversold": 30},
    },
    {
        "name": "MACD - Moving Average Convergence Divergence",
        "type": "macd",
        "description": "Convergência/Divergência de Médias Móveis - identifica tendências e reversões",
        "parameters": {"fast_period": 12, "slow_period": 26, "signal_period": 9},
    },
    {
        "name": "Bollinger Bands",
        "type": "bollinger_bands",
        "description": "Bandas de Bollinger - identifica volatilidade e reversões de preço",
        "parameters": {"period": 20, "std_dev": 2},
    },
    {
        "name": "SMA - Simple Moving Average",
        "type": "sma",
        "description": "Média Móvel Simples - identifica tendência de longo prazo",
        "parameters": {"period": 50},
    },
    {
        "name": "EMA - Exponential Moving Average",
        "type": "ema",
        "description": "Média Móvel Exponencial - identifica tendência de curto prazo",
        "parameters": {"period": 20},
    },
    {
        "name": "Stochastic Oscillator",
        "type": "stochastic",
        "description": "Oscilador Estocástico - identifica momentum e reversões",
        "parameters": {"k_period": 14, "d_period": 3, "slowing": 3, "overbought": 80, "oversold": 20},
    },
    {
        "name": "ATR - Average True Range",
        "type": "atr",
        "description": "Average True Range - mede volatilidade do mercado",
        "parameters": {"period": 14},
    },
    {
        "name": "CCI - Commodity Channel Index",
        "type": "cci",
        "description": "Identifica ciclos de preço e condições de sobrecompra/sobrevenda",
        "parameters": {"period": 20, "overbought": 100, "oversold": -100},
    },
    {
        "name": "Williams %R",
        "type": "williams_r",
        "description": "Oscilador de momentum que mede níveis de sobrecompra/sobrevenda",
        "parameters": {"period": 14, "overbought": -20, "oversold": -80},
    },
    {
        "name": "ROC - Rate of Change",
        "type": "roc",
        "description": "Mede a velocidade de mudança do preço em um período",
        "parameters": {"period": 12, "overbought": 5, "oversold": -5},
    },
    {
        "name": "VWAP - Volume Weighted Average Price",
        "type": "vwap",
        "description": "Preço médio ponderado pelo volume, usado como suporte/resistência",
        "parameters": {"period": 14, "std_dev_multiplier": 1.0},
    },
    {
        "name": "OBV - On Balance Volume",
        "type": "obv",
        "description": "Indicador de fluxo de volume que relaciona volume com mudança de preço",
        "parameters": {"signal_period": 9},
    },
    {
        "name": "Parabolic SAR",
        "type": "parabolic_sar",
        "description": "Parabolic Stop and Reverse - trend reversal indicator",
        "parameters": {"initial_af": 0.02, "max_af": 0.2, "step_af": 0.02},
    },
    {
        "name": "Ichimoku Cloud",
        "type": "ichimoku_cloud",
        "description": "Ichimoku Kinko Hyo - comprehensive trend indicator",
        "parameters": {"tenkan_period": 9, "kijun_period": 26, "senkou_span_b_period": 52, "chikou_shift": 26},
    },
    {
        "name": "MFI - Money Flow Index",
        "type": "money_flow_index",
        "description": "MFI - momentum indicator with volume",
        "parameters": {"period": 14},
    },
    {
        "name": "ADX - Average Directional Index",
        "type": "average_directional_index",
        "description": "Average Directional Index - trend strength indicator",
        "parameters": {"period": 14},
    },
    {
        "name": "Keltner Channels",
        "type": "keltner_channels",
        "description": "Keltner Channels - volatility bands",
        "parameters": {"ema_period": 20, "atr_period": 20, "multiplier": 2.0},
    },
    {
        "name": "Donchian Channels",
        "type": "donchian_channels",
        "description": "Donchian Channels - price channel indicator",
        "parameters": {"period": 20},
    },
    {
        "name": "Heiken Ashi",
        "type": "heiken_ashi",
        "description": "Heiken Ashi - filtered price candles",
        "parameters": {},
    },
    {
        "name": "Pivot Points",
        "type": "pivot_points",
        "description": "Pivot Points - support and resistance levels",
        "parameters": {},
    },
    {
        "name": "Supertrend",
        "type": "supertrend",
        "description": "Supertrend - trend following indicator",
        "parameters": {"atr_period": 10, "multiplier": 3.0},
    },
    {
        "name": "Fibonacci Retracement",
        "type": "fibonacci_retracement",
        "description": "Fibonacci Retracement - support/resistance levels",
        "parameters": {"lookback": 50},
    },
    {
        "name": "Zonas de Suporte/Resistência",
        "type": "zonas",
        "description": "Identifica zonas de suporte e resistência baseadas em máximas e mínimas históricas",
        "parameters": {"lookback_periods": 20, "zone_merge_distance": 0.001},
    },
]


async def populate_indicators():
    """Popula a tabela indicators com os 23 indicadores padrão"""
    print("=" * 60)
    print("POPULANDO TABELA 'indicators' COM 23 INDICADORES PADRÃO")
    print("Railway Production")
    print("=" * 60)
    
    async with get_db_context() as db:
        added = 0
        skipped = 0
        
        for indicator in DEFAULT_INDICATORS:
            # Verificar se já existe por tipo
            result = await db.execute(
                text("SELECT id FROM indicators WHERE type = :type"),
                {"type": indicator["type"]}
            )
            existing = result.fetchone()
            
            if existing:
                # Atualizar para garantir is_default = true
                await db.execute(
                    text("""
                        UPDATE indicators 
                        SET is_default = true, 
                            is_active = true,
                            name = :name,
                            description = :description,
                            parameters = :parameters,
                            updated_at = :updated_at
                        WHERE type = :type
                    """),
                    {
                        "type": indicator["type"],
                        "name": indicator["name"],
                        "description": indicator["description"],
                        "parameters": json.dumps(indicator["parameters"]),
                        "updated_at": datetime.utcnow()
                    }
                )
                print(f"   🔄 Atualizado: {indicator['name']}")
                skipped += 1
            else:
                # Inserir novo
                ind_id = str(uuid.uuid4())
                await db.execute(
                    text("""
                        INSERT INTO indicators 
                        (id, name, type, description, parameters, is_active, is_default, version, created_at, updated_at)
                        VALUES (:id, :name, :type, :description, :parameters, true, true, '1.0', :created_at, :updated_at)
                    """),
                    {
                        "id": ind_id,
                        "name": indicator["name"],
                        "type": indicator["type"],
                        "description": indicator["description"],
                        "parameters": json.dumps(indicator["parameters"]),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
                print(f"   ✅ Inserido: {indicator['name']}")
                added += 1
        
        await db.commit()
        
        # Resumo
        print("\n" + "=" * 60)
        print("RESUMO")
        print("=" * 60)
        
        result = await db.execute(text("SELECT COUNT(*) FROM indicators WHERE is_default = true"))
        default_count = result.scalar()
        
        result = await db.execute(text("SELECT COUNT(*) FROM indicators"))
        total_count = result.scalar()
        
        print(f"📈 Novos indicadores adicionados: {added}")
        print(f"🔄 Indicadores atualizados: {skipped}")
        print(f"📊 Total de indicadores padrão: {default_count}")
        print(f"📊 Total geral de indicadores: {total_count}")
        
        if default_count == 23:
            print("\n✅ SUCESSO: Todos os 23 indicadores padrão estão no banco!")
        else:
            print(f"\n⚠️  ATENÇÃO: Esperado 23 indicadores, encontrados {default_count}")


if __name__ == "__main__":
    asyncio.run(populate_indicators())
