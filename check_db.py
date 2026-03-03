#!/usr/bin/env python3
"""Verificar tabelas do banco de dados"""
import sqlite3
import json

conn = sqlite3.connect('data/tunestrade.db')
cursor = conn.cursor()

# Verificar se banco tem dados
print(f"Banco: data/tunestrade.db")
import os
size = os.path.getsize('data/tunestrade.db')
print(f"Tamanho: {size} bytes")

# Listar tabelas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("="*60)
print("TABELAS NO BANCO:")
print("="*60)
for t in tables:
    print(f"  - {t}")

# Verificar tabela indicators
if 'indicators' in tables:
    print("\n" + "="*60)
    print("TABELA 'indicators' - Conteúdo:")
    print("="*60)
    cursor.execute("SELECT id, name, type, is_default FROM indicators ORDER BY name")
    rows = cursor.fetchall()
    print(f"Total de registros: {len(rows)}")
    for row in rows:
        print(f"  - {row[1]} (type={row[2]}, default={row[3]})")

# Verificar tabela strategies
if 'strategies' in tables:
    print("\n" + "="*60)
    print("TABELA 'strategies' - Conteúdo:")
    print("="*60)
    cursor.execute("SELECT id, name, type, user_id FROM strategies ORDER BY name")
    rows = cursor.fetchall()
    print(f"Total de registros: {len(rows)}")
    for row in rows:
        user_short = row[3][:8] + "..." if row[3] else "NULL"
        print(f"  - {row[1]} (type={row[2]}, user={user_short})")

# Verificar tabela strategy_indicators
if 'strategy_indicators' in tables:
    print("\n" + "="*60)
    print("TABELA 'strategy_indicators' - Conteúdo:")
    print("="*60)
    try:
        cursor.execute("SELECT strategy_id, indicator_id FROM strategy_indicators")
        rows = cursor.fetchall()
        print(f"Total de registros: {len(rows)}")
        for row in rows:
            print(f"  - strategy={row[0][:8]}... indicator={row[1][:8]}...")
    except Exception as e:
        print(f"Erro: {e}")

conn.close()
print("\n" + "="*60)
print("Verificação concluída!")
print("="*60)
