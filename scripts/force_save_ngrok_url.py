"""
Script para forçar salvamento do URL do ngrok no Google Sheets
"""
import os
import sys
from pathlib import Path

# Adicionar diretório raiz ao sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from services.ngrok_manager import NgrokManager
from loguru import logger

# Carregar variáveis de ambiente
load_dotenv()

def force_save_ngrok_url():
    """Força salvamento do URL do ngrok no Google Sheets"""
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    
    if not sheet_id:
        logger.error("GOOGLE_SHEET_ID não encontrado no .env")
        return False
    
    manager = NgrokManager(sheet_id)
    
    # Capturar URL do ngrok
    url = manager.get_ngrok_url()
    
    if not url:
        logger.error("Não foi possível capturar URL do ngrok")
        return False
    
    logger.info(f"URL do ngrok capturado: {url}")
    
    # Salvar no Google Sheets
    success = manager.save_url_to_google_sheets(url)
    
    if success:
        logger.success(f"✓ URL salvo no Google Sheets: {url}")
        return True
    else:
        logger.error("✗ Falha ao salvar URL no Google Sheets")
        return False

if __name__ == "__main__":
    force_save_ngrok_url()
