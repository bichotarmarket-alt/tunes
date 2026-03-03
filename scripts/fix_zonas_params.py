#!/usr/bin/env python3
"""Corrigir parâmetros do indicador Zonas"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context

# Parâmetros corretos que o aplicativo espera
CORRECT_PARAMS = {
    "swing_period": 20,
    "zone_strength": 3,
    "zone_tolerance": 0.001,
    "min_zone_width": 0.001,
    "atr_multiplier": 1.0
}

async def fix_zonas_params():
    async with get_db_context() as db:
        result = await db.execute(text("SELECT id, parameters FROM indicators WHERE type = 'zonas'"))
        row = result.fetchone()
        
        if not row:
            print("❌ Indicador zonas não encontrado!")
            return
        
        print(f"ID: {row.id}")
        print(f"Parâmetros atuais: {row.parameters}")
        
        # Atualizar para os parâmetros corretos
        await db.execute(
            text("UPDATE indicators SET parameters = :params WHERE type = 'zonas'"),
            {"params": json.dumps(CORRECT_PARAMS)}
        )
        await db.commit()
        
        print(f"\n✅ Parâmetros atualizados para: {CORRECT_PARAMS}")
        print("\nParâmetros agora reconhecidos pelo app:")
        print("  - swing_period: Período para identificar topos/fundos")
        print("  - zone_strength: Mínimo de toques para validar zona")
        print("  - zone_tolerance: Tolerância para agrupar zonas")
        print("  - min_zone_width: Largura mínima da zona")
        print("  - atr_multiplier: Multiplicador do ATR")

if __name__ == "__main__":
    asyncio.run(fix_zonas_params())
