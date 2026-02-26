"""
Backend execution script
Run this file to start the FastAPI backend server
"""
import uvicorn
from api.main import app
from core.config import settings
import sys
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

if __name__ == "__main__":
    print("=" * 60)
    print("Iniciando Backend AutoTrade")
    print("=" * 60)
    print(f"API Host: {settings.API_HOST}")
    print(f"API Port: {settings.API_PORT}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"Data Collector: {'[X] Ativado' if settings.DATA_COLLECTOR_ENABLED else '[ ] Desativado'}")
    
    # Verificar configuracoes do ngrok
    ngrok_enabled = os.getenv('NGROK_ENABLED', 'false').lower() == 'true'
    ngrok_token = os.getenv('NGROK_TOKEN')
    
    if ngrok_enabled:
        print(f"Ngrok: [X] Ativado")
        if ngrok_token:
            print(f"   Token: {ngrok_token[:10]}...{ngrok_token[-10:]}")
        else:
            print(f"   WARNING: NGROK_TOKEN nao configurado!")
    else:
        print(f"Ngrok: [ ] Desativado")
        print(f"   Para ativar: NGROK_ENABLED=true no .env")
    
    print("=" * 60)
    
    # Disable uvicorn access logs for GET requests
    # access_log=False disables all access logs
    # log_level="warning" only shows warnings and errors
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        access_log=False,
        log_level="warning"
    )
    
    print("=" * 60)
    print("Backend AutoTrade parado")
    print("=" * 60)
