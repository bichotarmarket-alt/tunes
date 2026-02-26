"""
Script para iniciar ngrok automaticamente quando o backend inicia
"""
import subprocess
import os
import time
import requests
import signal
from loguru import logger
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

# Variável global para guardar o processo do ngrok
_ngrok_process = None


def start_ngrok_if_enabled():
    """Inicia ngrok se estiver habilitado no .env e atualiza URL na planilha"""
    global _ngrok_process
    ngrok_enabled = os.getenv('NGROK_ENABLED', 'false').lower() == 'true'
    
    if not ngrok_enabled:
        logger.info("Ngrok não está habilitado")
        return False
    
    ngrok_token = os.getenv('NGROK_TOKEN')
    if not ngrok_token:
        logger.warning("NGROK_TOKEN não encontrado no .env")
        return False
    
    try:
        # Verificar se ngrok já está rodando
        ngrok_running = False
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=2)
            if response.status_code == 200:
                ngrok_running = True
                logger.info("[OK] Ngrok já está rodando")
        except:
            pass
        
        # Se ngrok não estiver rodando, iniciar
        if not ngrok_running:
            logger.info("[LAUNCH] Iniciando ngrok...")
            
            # Caminho do executável do ngrok (baixado pelo usuário)
            ngrok_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ngrok-v3-stable-windows-amd64', 'ngrok.exe')
            
            # Verificar se executável existe
            if not os.path.exists(ngrok_path):
                logger.error(f"✗ Executável do ngrok não encontrado: {ngrok_path}")
                return False
            
            # Comando para iniciar ngrok
            cmd = [
                ngrok_path, 'http', '8000',
                '--authtoken', ngrok_token,
                '--log=stdout'
            ]
            
            # Iniciar ngrok em background
            _ngrok_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Aguardar ngrok iniciar
            time.sleep(3)
        
        # Capturar URL do ngrok (seja novo ou existente)
        try:
            response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'tunnels' in data and len(data['tunnels']) > 0:
                    url = data['tunnels'][0]['public_url']
                    logger.success(f"[OK] Ngrok URL capturado: {url}")
                    
                    # Salvar URL no Google Sheets (sempre atualizar)
                    from services.ngrok_manager import NgrokManager
                    sheet_id = os.getenv('GOOGLE_SHEET_ID')
                    manager = NgrokManager(sheet_id)
                    manager.save_url_to_google_sheets(url)
                    
                    return True
        except Exception as e:
            logger.error(f"✗ Erro ao capturar/atualizar URL do ngrok: {e}")
            return False
        
        logger.error("✗ Ngrok não iniciou corretamente")
        return False
        
    except Exception as e:
        logger.error(f"✗ Erro ao iniciar ngrok: {e}")
        return False


def stop_ngrok():
    """Para o processo do ngrok se estiver rodando"""
    global _ngrok_process
    
    try:
        logger.info("[STOP] Parando ngrok...")
        
        # Tentar parar o processo armazenado
        if _ngrok_process is not None:
            try:
                _ngrok_process.terminate()
                try:
                    _ngrok_process.wait(timeout=5)
                    logger.info("[OK] Ngrok parado com sucesso")
                except subprocess.TimeoutExpired:
                    logger.warning("Ngrok não respondeu ao terminate, forçando kill...")
                    _ngrok_process.kill()
                    _ngrok_process.wait()
                    logger.info("[OK] Ngrok forçado a parar")
            except Exception as e:
                logger.warning(f"Erro ao parar processo ngrok: {e}")
        
        # Matar todos os processos ngrok (garantia)
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'ngrok.exe'],
                          capture_output=True, text=True, timeout=10)
            logger.info("[OK] Todos os processos ngrok foram finalizados")
        except Exception as e:
            logger.warning(f"Erro ao matar processos ngrok: {e}")
        
        _ngrok_process = None
        
    except Exception as e:
        logger.error(f"✗ Erro ao parar ngrok: {e}")
        _ngrok_process = None


if __name__ == "__main__":
    start_ngrok_if_enabled()
