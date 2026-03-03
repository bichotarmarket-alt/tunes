#!/usr/bin/env python3
"""Adicionar indicadores faltantes para totalizar 23"""
import asyncio
import sys
import uuid
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context

# 5 indicadores adicionais para chegar a 23
ADDITIONAL_INDICATORS = [
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
        "name": "Rate of Change (ROC)",
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
]

async def add_missing_indicators():
    print("=" * 60)
    print("ADICIONANDO INDICADORES FALTANTES (5 novos)")
    print("=" * 60)
    
    async with get_db_context() as db:
        added = 0
        skipped = 0
        
        for indicator in ADDITIONAL_INDICATORS:
            # Verificar se já existe
            result = await db.execute(
                text("SELECT id FROM indicators WHERE type = :type"),
                {"type": indicator["type"]}
            )
            if result.fetchone():
                print(f"   ⚠️  '{indicator['name']}' já existe")
                skipped += 1
                continue
            
            # Inserir indicador
            ind_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO indicators 
                    (id, name, type, description, parameters, is_active, is_default, version, created_at, updated_at)
                    VALUES (:id, :name, :type, :description, :parameters, 1, 1, '1.0', :created_at, :updated_at)
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
            print(f"   ✅ {indicator['name']}")
            added += 1
        
        await db.commit()
        
        # Resumo
        print("\n" + "=" * 60)
        print("RESUMO")
        print("=" * 60)
        
        result = await db.execute(text("SELECT COUNT(*) FROM indicators"))
        total = result.scalar()
        
        print(f"📈 Indicadores adicionados: {added}")
        print(f"⏭️  Indicadores pulados (já existiam): {skipped}")
        print(f"📊 Total de indicadores no banco: {total}")

if __name__ == "__main__":
    asyncio.run(add_missing_indicators())
