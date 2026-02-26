"""Gerenciador unificado de reconexão para todas as conexões WebSocket"""
import asyncio
import time
from typing import Dict, Optional, Callable, Any
from loguru import logger
from services.pocketoption.maintenance_checker import maintenance_checker


class ReconnectionManager:
    """Gerenciador unificado de reconexão para todas as conexões"""

    def __init__(self):
        self._connections: Dict[str, Dict[str, Any]] = {}  # {connection_id: {client, config, stats}}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_running = False

    def register_connection(
        self,
        connection_id: str,
        client: Any,
        connect_fn: Callable,
        disconnect_fn: Callable,
        check_connected_fn: Callable,
        config: Optional[Dict[str, Any]] = None,
        connection_type: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Registrar uma conexão para monitoramento

        Args:
            connection_id: ID único da conexão
            client: Cliente WebSocket
            connect_fn: Função para conectar
            disconnect_fn: Função para desconectar
            check_connected_fn: Função para verificar se está conectado
            config: Configuração da conexão (max_retries, backoff_delay, etc.)
            connection_type: Tipo de conexão (user, monitoring_payout, monitoring_ativos, etc.)
            description: Descrição da conexão (ex: nome do usuário, conta, etc.)
        """
        default_config = {
            'max_retries': 10,
            'initial_delay': 5,
            'max_delay': 60,
            'backoff_multiplier': 2,
            'should_reconnect': True
        }

        if config:
            default_config.update(config)

        self._connections[connection_id] = {
            'client': client,
            'connect_fn': connect_fn,
            'disconnect_fn': disconnect_fn,
            'check_connected_fn': check_connected_fn,
            'config': default_config,
            'connection_type': connection_type or 'unknown',
            'description': description or connection_id,
            'stats': {
                'total_reconnects': 0,
                'successful_reconnects': 0,
                'failed_reconnects': 0,
                'last_attempt_time': None,
                'last_success_time': None
            }
        }

        logger.info(
            "[OK] Conexão registrada: [%s] %s (id: %s)",
            connection_type or 'unknown',
            description or connection_id,
            connection_id,
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

    def unregister_connection(self, connection_id: str):
        """Remover uma conexão do monitoramento"""
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.info(
                "[OK] Conexão '%s' removida do monitoramento",
                connection_id,
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )

    async def start_monitoring(self):
        """Iniciar monitoramento de todas as conexões"""
        if self._is_running:
            logger.warning(
                "Monitoramento já está em execução",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
            return

        self._is_running = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.success(
            "[SUCCESS] Gerenciador de reconexão iniciado",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

    async def stop_monitoring(self):
        """Parar monitoramento de todas as conexões"""
        self._is_running = False

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.debug("Timeout ao aguardar finalização da task de monitoramento")
            except asyncio.CancelledError:
                pass

        logger.info(
            "Gerenciador de reconexão parado",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

    async def _monitor_loop(self):
        """Loop de monitoramento de conexões"""
        logger.info(
            "[SEARCH] Loop de monitoramento de conexões iniciado",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

        while self._is_running:
            try:
                await asyncio.sleep(5)  # Verificar a cada 5 segundos

                if not self._is_running:
                    break

                # Verificar cada conexão
                for connection_id in list(self._connections.keys()):
                    await self._check_and_reconnect(connection_id)

            except asyncio.CancelledError:
                logger.info(
                    "Loop de monitoramento cancelado",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )
                break
            except Exception as e:
                logger.error(
                f"[CRITICAL] Erro no loop de monitoramento: {e}",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
                await asyncio.sleep(5)

        logger.info(
            "Loop de monitoramento encerrado",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

    async def _check_and_reconnect(self, connection_id: str) -> None:
        """Verificar e reconectar uma conexão se necessário"""
        conn_data = self._connections.get(connection_id)
        if not conn_data:
            return

        # Extrair metadados da conexão
        connection_type = conn_data.get('connection_type', 'unknown')
        description = conn_data.get('description', connection_id)

        # Se o sistema está em manutenção, não tentar reconectar
        logger.debug(
            f"[SEARCH] [{connection_type}] {description} - Verificando manutenção: is_under_maintenance={maintenance_checker.is_under_maintenance}",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )
        if maintenance_checker.is_under_maintenance:
            logger.info(
                f"[PAUSED] [{connection_type}] {description} - Sistema em manutenção, não reconectando",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
            return

        client = conn_data['client']
        config = conn_data['config']
        stats = conn_data['stats']

        # Verificar se deve reconectar
        should_reconnect = config.get('should_reconnect', True)
        if callable(should_reconnect):
            try:
                should_reconnect = bool(should_reconnect())
            except Exception as e:
                logger.error(
                    f"[CRITICAL] [{connection_type}] {description} - Erro ao avaliar should_reconnect: {e}",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )
                should_reconnect = False

        if not should_reconnect:
            logger.debug(
                f"[PAUSED] [{connection_type}] {description} - Reconexão desativada",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
            return

        # Verificar se está conectado
        try:
            is_connected = conn_data['check_connected_fn'](client)
        except Exception as e:
            logger.error(
                f"[CRITICAL] [{connection_type}] {description} - Erro ao verificar conexão: {e}",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
            is_connected = False

        if is_connected:
            logger.debug(
                f"[OK] [{connection_type}] {description} - Conectado",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )
            return

        logger.warning(
            f"[WARNING] [{connection_type}] {description} - Desconectado, tentando reconectar...",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )

        # Calcular delay com backoff
        retry_count = stats['total_reconnects']

        # VERIFICAR SE A REDE RECUPEROU: Se temos muitas falhas consecutivas,
        # tentar uma reconexão imediata para testar se a rede voltou
        if retry_count >= config['max_retries']:
            # Verificar se já faz tempo desde a última tentativa (possível recuperação de rede)
            last_attempt = stats.get('last_attempt_time')
            if last_attempt and (time.time() - last_attempt) > config['max_delay']:
                logger.warning(
                    f"[RECOVERY] [{connection_type}] {description} - Máximo de tentativas atingido, "
                    f"mas última tentativa foi há {time.time() - last_attempt:.0f}s. "
                    f"Possível recuperação de rede detectada. Resetando contador e tentando novamente...",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )
                stats['total_reconnects'] = 0
                stats['failed_reconnects'] = 0
                retry_count = 0
            else:
                logger.error(
                    f"[CRITICAL] [{connection_type}] {description} - Máximo de tentativas ({config['max_retries']}) atingido",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )
                return

        delay = min(
            config['initial_delay'] * (config['backoff_multiplier'] ** retry_count),
            config['max_delay']
        )

        # Aguardar delay
        logger.info(
            f"[TIME] [{connection_type}] {description} - Aguardando {delay}s antes de reconectar...",
            extra={
                "user_name": "",
                "account_id": "",
                "account_type": ""
            }
        )
        await asyncio.sleep(delay)

        # Tentar reconectar
        stats['last_attempt_time'] = time.time()
        stats['total_reconnects'] += 1

        try:
            # Desconectar primeiro
            await conn_data['disconnect_fn']()

            # Conectar
            await conn_data['connect_fn']()

            # Verificar se conectou
            is_connected = conn_data['check_connected_fn'](client)

            if is_connected:
                stats['successful_reconnects'] += 1
                stats['last_success_time'] = time.time()
                # RESETAR contador de tentativas após sucesso para permitir futuras reconexões
                if stats['total_reconnects'] > 0:
                    logger.info(
                        f"[REBALANCE] [{connection_type}] {description} - Resetando contador de tentativas (estava em {stats['total_reconnects']})",
                        extra={
                            "user_name": "",
                            "account_id": "",
                            "account_type": ""
                        }
                    )
                    stats['total_reconnects'] = 0
                    stats['failed_reconnects'] = 0
                logger.success(
                    f"[SUCCESS] [{connection_type}] {description} - Reconexão bem-sucedida (tentativa {retry_count + 1})",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )
            else:
                stats['failed_reconnects'] += 1
                logger.error(
                    f"[CRITICAL] [{connection_type}] {description} - Reconexão falhou (tentativa {retry_count + 1})",
                    extra={
                        "user_name": "",
                        "account_id": "",
                        "account_type": ""
                    }
                )

        except Exception as e:
            stats['failed_reconnects'] += 1
            logger.error(
                f"[CRITICAL] [{connection_type}] {description} - Erro ao reconectar: {type(e).__name__}: {e}",
                extra={
                    "user_name": "",
                    "account_id": "",
                    "account_type": ""
                }
            )

    def get_stats(self, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Obter estatísticas de reconexão"""
        if connection_id:
            if connection_id in self._connections:
                return self._connections[connection_id]['stats']
            return {}

        # Retornar stats de todas as conexões
        return {
            conn_id: conn_data['stats']
            for conn_id, conn_data in self._connections.items()
        }

    def force_reconnect(self, connection_id: str):
        """Forçar reconexão imediata"""
        if connection_id in self._connections:
            conn_data = self._connections[connection_id]
            conn_data['stats']['total_reconnects'] = 0  # Resetar contador
            logger.info(f"[REBALANCE] [{connection_id}] Forçando reconexão...")
        else:
            logger.warning(f"[WARNING] Conexão '{connection_id}' não encontrada")


# Instância global do gerenciador
_reconnection_manager: Optional[ReconnectionManager] = None


def get_reconnection_manager() -> ReconnectionManager:
    """Obter instância global do gerenciador de reconexão"""
    global _reconnection_manager
    if _reconnection_manager is None:
        _reconnection_manager = ReconnectionManager()
    return _reconnection_manager
