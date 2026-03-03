"""
WebSocket Connection Logger - Logs individuais por conexão WS
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class WSConnectionLogger:
    """Logger dedicado para cada conexão WebSocket"""
    
    def __init__(self, connection_id: str, connection_type: str, log_dir: str = "logs/ws", rotation_lines: Optional[int] = None, user_name: Optional[str] = None):
        self.connection_id = connection_id
        self.connection_type = connection_type
        self.user_name = user_name or "Unknown"
        self.log_dir = Path(log_dir)
        self.log_file: Optional[Path] = None
        self._file_handle: Optional[Any] = None
        self._lock = asyncio.Lock()
        self._rotation_lines = rotation_lines  # Limite de linhas para rotação
        self._current_lines = 0  # Contador de linhas atuais
        
        # Estatísticas
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "reconnects": 0,
            "errors": 0,
            "created_at": datetime.now().isoformat(),
            "last_activity": None
        }
        
        self._ensure_log_dir()
        self._create_log_file()
    
    def _ensure_log_dir(self):
        """Garantir que diretório de logs existe"""
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _create_log_file(self):
        """Criar arquivo de log para esta conexão, reutilizando arquivo existente se houver"""
        # Extrair base_id (ID sem timestamp)
        base_id = self.connection_id.split('_2026')[0] if '_2026' in self.connection_id else self.connection_id
        safe_base_id = base_id.replace("/", "_").replace(":", "_")
        
        # Verificar se já existe um arquivo de log para este base_id
        existing_file = None
        safe_user = self.user_name.replace("/", "_").replace(":", "_").replace(" ", "_")
        if self.log_dir.exists():
            # Procurar arquivos que correspondam ao padrão {user_name}_{connection_type}_{safe_base_id}_*.log
            # Mas ignorar arquivos já rotacionados (que contêm _rotated_ no nome)
            pattern = f"{safe_user}_{self.connection_type}_{safe_base_id}_*.log"
            matching_files = [
                f for f in self.log_dir.glob(pattern)
                if '_rotated_' not in f.name
            ]
            matching_files = sorted(matching_files, key=lambda f: f.stat().st_mtime, reverse=True)
            if matching_files:
                existing_file = matching_files[0]  # Usar o arquivo mais recente
        
        if existing_file:
            # Reutilizar arquivo existente
            self.log_file = existing_file
            # Adicionar separador de nova sessão
            separator = f"""
\n{'='*80}
RECONNECTION SESSION
{'='*80}
Connection ID: {self.connection_id}
Session Started: {self.stats['created_at']}
{'='*80}

"""
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(separator)
            logger.info(f"[WS LOGGER] Usando arquivo de log existente: {self.log_file}")
        else:
            # Criar novo arquivo de log
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_user}_{self.connection_type}_{safe_base_id}_{timestamp}.log"
            self.log_file = self.log_dir / filename
            
            # Criar cabeçalho do log
            header = f"""{'='*80}
WebSocket Connection Log
Connection ID: {self.connection_id}
Connection Type: {self.connection_type}
User: {self.user_name}
Created: {self.stats['created_at']}
Log File: {self.log_file.name}
{'='*80}

"""
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(header)
            
            logger.info(f"[WS LOGGER] Arquivo de log criado: {self.log_file}")
    
    async def log_event(self, event_type: str, message: str, data: Optional[Dict] = None):
        """Logar evento da conexão"""
        async with self._lock:
            timestamp = datetime.now().isoformat()
            self.stats["last_activity"] = timestamp
            
            log_entry = f"[{timestamp}] [{event_type}] {message}"
            if data:
                import json
                log_entry += f"\n  Data: {json.dumps(data, default=str, ensure_ascii=False)}"
            log_entry += "\n"
            
            # Verificar se precisa rotacionar
            if self._rotation_lines and self._current_lines >= self._rotation_lines:
                await self._rotate_log()
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            self._current_lines += 1
    
    async def log_message_sent(self, message: str, preview: bool = True):
        """Logar mensagem enviada"""
        self.stats["messages_sent"] += 1
        msg_preview = message[:100] + "..." if preview and len(message) > 100 else message
        await self.log_event("SEND", f"Mensagem enviada ({len(message)} bytes): {msg_preview}")
    
    async def log_message_received(self, message: str, preview: bool = True):
        """Logar mensagem recebida"""
        self.stats["messages_received"] += 1
        msg_preview = message[:200] + "..." if preview and len(message) > 200 else message
        await self.log_event("RECV", f"Mensagem recebida ({len(message)} bytes): {msg_preview}")
    
    async def log_connect(self, url: str, region: Optional[str] = None):
        """Logar tentativa de conexão"""
        await self.log_event("CONNECT", f"Conectando a {url}", {"region": region, "url": url})
    
    async def log_connected(self, url: str, region: str):
        """Logar conexão estabelecida"""
        await self.log_event("CONNECTED", f"Conexão estabelecida em {region}", {
            "url": url,
            "region": region,
            "total_reconnects": self.stats["reconnects"]
        })
    
    async def log_disconnect(self, reason: str = "Desconhecido"):
        """Logar desconexão"""
        self.stats["reconnects"] += 1
        await self.log_event("DISCONNECT", f"Conexão encerrada: {reason}")
    
    async def log_error(self, error: Exception, context: str = ""):
        """Logar erro"""
        self.stats["errors"] += 1
        error_msg = f"{type(error).__name__}: {str(error)}"
        if context:
            error_msg = f"[{context}] {error_msg}"
        await self.log_event("ERROR", error_msg)
    
    async def log_authenticated(self, user_info: Optional[Dict] = None):
        """Logar autenticação bem-sucedida"""
        await self.log_event("AUTH", "Autenticação bem-sucedida", user_info)
    
    async def log_ping(self):
        """Logar ping enviado"""
        await self.log_event("PING", "Ping enviado")
    
    async def log_pong(self):
        """Logar pong recebido"""
        await self.log_event("PONG", "Pong recebido")
    
    async def log_reconnect_attempt(self, attempt: int, max_attempts: int, delay: float):
        """Logar tentativa de reconexão"""
        await self.log_event("RECONNECT", f"Tentativa {attempt}/{max_attempts} em {delay}s")
    
    async def log_callback_event(self, callback_type: str, data: Any):
        """Logar evento de callback (stream_update, json_data, etc)"""
        async with self._lock:
            timestamp = datetime.now().isoformat()
            
            # Extrair informações resumidas dos dados
            data_summary = ""
            if isinstance(data, list):
                if len(data) > 0 and isinstance(data[0], list) and len(data[0]) >= 3:
                    # Formato de ticks: [["symbol", timestamp, price], ...]
                    symbols = [item[0] for item in data if isinstance(item, list) and len(item) >= 3]
                    data_summary = f" | symbols: {symbols[:5]}" + (f" (+{len(symbols)-5} more)" if len(symbols) > 5 else "")
                elif len(data) > 0 and isinstance(data[0], str):
                    # Evento Socket.IO
                    data_summary = f" | event: {data[0]}"
            elif isinstance(data, dict):
                data_summary = f" | keys: {list(data.keys())[:5]}"
            
            log_entry = f"[{timestamp}] [CALLBACK:{callback_type}]{data_summary}\n"
            
            # Verificar se precisa rotacionar
            if self._rotation_lines and self._current_lines >= self._rotation_lines:
                await self._rotate_log()
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            self._current_lines += 1
    
    async def _rotate_log(self):
        """Truncar (resetar) arquivo de log quando atingir limite de linhas - mantém mesmo arquivo"""
        if not self.log_file or not self.log_file.exists():
            return
        
        # Truncar arquivo - apaga conteúdo mas mantém arquivo
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"{'='*80}\n")
            f.write(f"LOG TRUNCADO - NOVA SESSÃO\n")
            f.write(f"{'='*80}\n")
            f.write(f"Connection ID: {self.connection_id}\n")
            f.write(f"Truncado em: {timestamp}\n")
            f.write(f"Linhas anteriores: {self._current_lines}\n")
            f.write(f"{'='*80}\n\n")
        
        logger.info(f"[WS LOGGER] Log truncado: {self.log_file.name} (mantido mesmo arquivo)")
        
        # Resetar contador
        self._current_lines = 0
    
    async def log_tick_received(self, symbol: str, price: float, timestamp: float):
        """Logar tick recebido (resumido)"""
        async with self._lock:
            ts_iso = datetime.now().isoformat()
            
            log_entry = f"[{ts_iso}] [TICK] {symbol} @ {price}"
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\n")
    
    async def close(self):
        """Fechar logger e escrever estatísticas finais"""
        async with self._lock:
            if self.log_file and self.log_file.exists():
                summary = f"""
{'='*80}
CONNECTION CLOSED - SUMMARY
{'='*80}
Connection ID: {self.connection_id}
Total Messages Sent: {self.stats['messages_sent']}
Total Messages Received: {self.stats['messages_received']}
Total Reconnects: {self.stats['reconnects']}
Total Errors: {self.stats['errors']}
Closed At: {datetime.now().isoformat()}
{'='*80}
"""
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(summary)
                
                logger.info(f"[WS LOGGER] Log fechado: {self.log_file}")


# Gerenciador global de loggers
_connection_loggers: Dict[str, WSConnectionLogger] = {}


def get_connection_logger(connection_id: str, connection_type: str = "ws", rotation_lines: Optional[int] = None, user_name: Optional[str] = None) -> WSConnectionLogger:
    """Obter ou criar logger para uma conexão - reutiliza se já existir"""
    # Verificar se já existe um logger para esta conexão (mesmo prefixo de ID)
    # Extrair o ID base (sem timestamp) para reutilizar
    base_id = connection_id.split('_2026')[0] if '_2026' in connection_id else connection_id
    
    # Procurar logger existente com mesmo base_id
    for existing_id, logger in _connection_loggers.items():
        if existing_id.startswith(base_id):
            return logger
    
    # Criar novo logger se não encontrar (com rotação opcional)
    _connection_loggers[connection_id] = WSConnectionLogger(connection_id, connection_type, rotation_lines=rotation_lines, user_name=user_name)
    return _connection_loggers[connection_id]


def remove_connection_logger(connection_id: str) -> Optional[WSConnectionLogger]:
    """Remover logger de uma conexão - também procura por base_id"""
    # Primeiro tentar remoção exata
    if connection_id in _connection_loggers:
        return _connection_loggers.pop(connection_id)
    
    # Se não encontrou, procurar por base_id
    base_id = connection_id.split('_2026')[0] if '_2026' in connection_id else connection_id
    for existing_id in list(_connection_loggers.keys()):
        if existing_id.startswith(base_id):
            return _connection_loggers.pop(existing_id)
    
    return None


def cleanup_old_logs(max_age_hours: int = 1, log_dir: str = "logs/ws"):
    """Limpar arquivos de log mais antigos que max_age_hours (padrão: 1 hora)"""
    import os
    from datetime import datetime, timedelta
    
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    removed = 0
    
    for log_file in log_path.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()
                removed += 1
        except Exception as e:
            logger.error(f"Erro ao remover log antigo {log_file}: {e}")
    
    if removed > 0:
        logger.info(f"[WS LOGGER] {removed} arquivos de log antigos removidos")


def list_active_loggers() -> Dict[str, WSConnectionLogger]:
    """Listar todos os loggers ativos"""
    return _connection_loggers.copy()


# Funções auxiliares para limpeza de logs antigos
async def cleanup_old_logs(max_age_days: int = 7, log_dir: str = "logs/ws"):
    """Limpar arquivos de log mais antigos que max_age_days"""
    import os
    from datetime import datetime, timedelta
    
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed = 0
    
    for log_file in log_path.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            if mtime < cutoff:
                log_file.unlink()
                removed += 1
        except Exception as e:
            logger.error(f"Erro ao remover log antigo {log_file}: {e}")
    
    if removed > 0:
        logger.info(f"[WS LOGGER] {removed} arquivos de log antigos removidos")
