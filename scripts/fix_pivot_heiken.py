#!/usr/bin/env python3
"""Verificar e corrigir parâmetros de Pivot Points e Heiken Ashi"""
import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context

# Parâmetros corretos para o aplicativo
PIVOT_PARAMS = {
    "pivot_type": 0,  # 0=Standard, 1=Woodie, 2=Classic
    "support_resistance_buffer": 0.001
}

HEIKEN_ASHI_PARAMS = {
    "smooth_period": 2,
    "confirmation_candles": 1
}

async def fix_params():
    async with get_db_context() as db:
        # Verificar Pivot Points
        result = await db.execute(text("SELECT id, name, parameters FROM indicators WHERE type = 'pivot_points'"))
        row = result.fetchone()
        if row:
            print(f"PIVOT POINTS: {row.name}")
            print(f"  Parâmetros atuais: {row.parameters}")
            await db.execute(
                text("UPDATE indicators SET parameters = :params WHERE type = 'pivot_points'"),
                {"params": json.dumps(PIVOT_PARAMS)}
            )
            print(f"  ✅ Atualizado para: {PIVOT_PARAMS}")
        else:
            print("❌ Pivot Points não encontrado")

        # Verificar Heiken Ashi
        result = await db.execute(text("SELECT id, name, parameters FROM indicators WHERE type = 'heiken_ashi'"))
        row = result.fetchone()
        if row:
            print(f"\nHEIKEN ASHI: {row.name}")
            print(f"  Parâmetros atuais: {row.parameters}")
            await db.execute(
                text("UPDATE indicators SET parameters = :params WHERE type = 'heiken_ashi'"),
                {"params": json.dumps(HEIKEN_ASHI_PARAMS)}
            )
            print(f"  ✅ Atualizado para: {HEIKEN_ASHI_PARAMS}")
        else:
            print("\n❌ Heiken Ashi não encontrado")

        await db.commit()
        print("\n✅ Parâmetros corrigidos!")

if __name__ == "__main__":
    asyncio.run(fix_params())
