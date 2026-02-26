#!/usr/bin/env python3
"""
Script para remover scripts temporários e desnecessários da pasta scripts
"""

import os
from pathlib import Path

# Scripts temporários e desnecessários para remover
TEMPORARY_SCRIPTS = [
    'analyze_dirs.py',
    'backup.sh',
    'check_db.py',
    'clean_duplicates.py',
    'deploy.sh',
    'identify_unnecessary_dirs.py',
    'identify_unnecessary_files.py',
    'remove_all_temporary_scripts.py',
    'remove_cache_dirs.py',
    'remove_temporary_scripts.py',
    'remove_unnecessary_dirs.py',
    'restore.sh',
]

# Scripts essenciais que NÃO devem ser removidos
ESSENTIAL_SCRIPTS = [
    'init_db.py',
    'seed.py',
    '__init__.py',
]

def remove_temporary_scripts():
    """Remove scripts temporários e desnecessários"""
    scripts_dir = Path(__file__).parent
    
    print("=" * 80)
    print("REMOVENDO SCRIPTS TEMPORÁRIOS E DESNECESSÁRIOS")
    print("=" * 80)
    print(f"Diretório dos scripts: {scripts_dir}")
    print()
    
    removed_count = 0
    total_size = 0
    
    for script_name in TEMPORARY_SCRIPTS:
        script_path = scripts_dir / script_name
        
        if script_path.exists():
            try:
                size = script_path.stat().st_size
                script_path.unlink()
                removed_count += 1
                total_size += size
                print(f"✅ REMOVIDO: {script_name} ({size:,} bytes)")
            except Exception as e:
                print(f"❌ ERRO ao remover {script_name}: {e}")
        else:
            print(f"⏭️  NÃO ENCONTRADO: {script_name}")
    
    # Verificar scripts essenciais
    print("\n" + "-" * 80)
    print("SCRIPTS ESSENCIAIS (MANTIDOS):")
    print("-" * 80)
    
    for script_name in ESSENTIAL_SCRIPTS:
        script_path = scripts_dir / script_name
        if script_path.exists():
            print(f"✅ MANTIDO: {script_name}")
        else:
            print(f"⚠️  NÃO ENCONTRADO: {script_name}")
    
    print("\n" + "=" * 80)
    print("RESUMO")
    print("=" * 80)
    print(f"Arquivos removidos: {removed_count}")
    print(f"Espaço liberado: {total_size:,} bytes ({total_size / 1024:.2f} KB)")
    print("=" * 80)

if __name__ == '__main__':
    remove_temporary_scripts()
