"""
Script para configurar .env com ngrok
"""
import os
from pathlib import Path

def configure_ngrok_env():
    """Adiciona configurações do ngrok ao .env"""
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Arquivo .env não encontrado")
        return False
    
    # Ler conteúdo atual do .env
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Configurações a adicionar
    ngrok_config = """
# Configuração do ngrok
NGROK_ENABLED=true
NGROK_TOKEN=39LwGmVglUTpHs7UcfGEuF57a65_4jZin6AMR6oxh73dkzy6z
GOOGLE_SHEET_ID=1Jd2Hyriq_L5g7G4jaT4bFIvkwi56JoBXuScM-BOoIbo
"""
    
    # Verificar se já existe
    if 'NGROK_ENABLED' in content:
        print("✓ Configurações do ngrok já existem no .env")
        return True
    
    # Adicionar configurações
    with open(env_path, 'a', encoding='utf-8') as f:
        f.write(ngrok_config)
    
    print("✓ Configurações do ngrok adicionadas ao .env")
    return True

if __name__ == "__main__":
    configure_ngrok_env()
