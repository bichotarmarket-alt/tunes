#!/usr/bin/env python3
"""Verificar indicador zonas"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_db_context

async def check():
    async with get_db_context() as db:
        result = await db.execute(text("SELECT id, name, type, parameters FROM indicators WHERE type = 'zonas'"))
        row = result.fetchone()
        if row:
            print(f"ID: {row.id}")
            print(f"Nome: {row.name}")
            print(f"Tipo: {row.type}")
            print(f"Parametros no banco: {row.parameters}")
            print(f"Tipo dos parametros: {type(row.parameters)}")
        else:
            print("Indicador zonas NAO ENCONTRADO no banco!")

if __name__ == "__main__":
    asyncio.run(check())
