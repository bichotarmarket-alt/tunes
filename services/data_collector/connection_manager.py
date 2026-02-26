"""Gerenciador de conexões WebSocket para múltiplos usuários"""
import asyncio
import json
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from services.pocketoption.client import AsyncPocketOptionClient
from core.database import get_db_context
from models import Account, AutoTradeConfig
from sqlalchemy import select, text, and_, or_, exists
from utils.retry import retry_on_db_lock


class UserConnection:
    """Representa uma conexão WebSocket de um usuário (demo ou real)"""

    def __init__(self, account_id: str, ssid: str, connection_type: str, user_name: str = None, account_role: str = "usuario"):
        self.account_id = account_id
        self.ssid = ssid
        self.connection_type = connection_type  # 'demo' ou 'real'
        self.user_name = user_name or "Usuário Desconhecido"
        self.account_role = account_role  # 'usuario', 'monitoramento_payout', 'monitoramento_ativos'
        self.is_demo = (connection_type == 'demo')  # Determinar se é demo baseado no tipo
        self.client: Optional[AsyncPocketOptionClient] = None
        self._is_connected = False
        self.subscribed_assets = set()

    def _get_log_prefix(self):
        """Gerar prefixo de log com nome do usuário ou tipo de monitoramento"""
        if self.account_role == "monitoramento_payout":
            return "[MONITORAMENTO: PAYOUT]"
        elif self.account_role == "monitoramento_ativos":
            return f"[MONITORAMENTO: ATIVOS - {self.user_name}]"
        else:
            return f"[USUÁRIO: {self.user_name}]"
    
    async def connect(self, trade_executor=None, max_retries=3):
        """Conectar ao WebSocket com retry com backoff"""
        retry_count = 0
        delay = 2  # Initial delay in seconds

        while retry_count < max_retries:
            try:
                # Criar cliente com o parâmetro is_demo correto
                self.client = AsyncPocketOptionClient(
                    ssid=self.ssid,
                    is_demo=self.is_demo,
                    persistent_connection=True,  # Usar conexão persistente para manter ativa
                    user_name=self.user_name
                )
                # Registrar handlers de balance antes da conexão para não perder eventos iniciais
                self.client.add_event_callback("balance_updated", self._on_balance_updated)
                self.client.add_event_callback("balance_data", self._on_balance_data)

                await self.client.connect()
                self.is_connected = True
                logger.info(f"{self._get_log_prefix()} [{self.account_id}] Conexão {self.connection_type} estabelecida", extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                })

                # Registrar handler para evento order_closed no trade_executor
                if trade_executor:
                    async def order_closed_wrapper(
                        data,
                        account_id=self.account_id,
                        connection_type=self.connection_type,
                    ):
                        await trade_executor._on_order_closed_event(
                            data,
                            account_id=account_id,
                            connection_type=connection_type,
                        )

                    self.client.add_event_callback("order_closed", order_closed_wrapper)
                    logger.info(
                        f"{self._get_log_prefix()} [{self.account_id}] Handler order_closed registrado para {self.connection_type}",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )

                logger.info(f"{self._get_log_prefix()} [{self.account_id}] Handlers de balance registrados para {self.connection_type}", extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                })
                return True

            except Exception as e:
                retry_count += 1
                logger.error(f"{self._get_log_prefix()} [{self.account_id}] Erro ao conectar {self.connection_type} (tentativa {retry_count}/{max_retries}): {e}", extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                })

                if retry_count < max_retries:
                    logger.info(f"{self._get_log_prefix()} [{self.account_id}] Aguardando {delay}s antes de tentar novamente...", extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    })
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 30)  # Exponential backoff, max 30s
                else:
                    logger.error(f"{self._get_log_prefix()} [{self.account_id}] Máximo de tentativas ({max_retries}) atingido", extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    })
                    self.is_connected = False
                    return False
    
    async def disconnect(self):
        """Desconectar do WebSocket"""
        try:
            if self.client:
                await self.client.disconnect()
                self.is_connected = False
                logger.info(f"{self._get_log_prefix()} [{self.account_id}] Conexão {self.connection_type} encerrada", extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                })
        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao desconectar {self.connection_type}: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )

    async def _handle_zero_balance(self, balance_value: float, is_demo: bool):
        """Lidar com saldo zero: desconectar, desligar estratégias e notificar"""
        try:
            logger.warning(
                f"{self._get_log_prefix()} [{self.account_id}] ⚠️ Saldo zero detectado! Desconectando e desligando estratégias...",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )

            # Desconectar a conexão
            await self.disconnect()

            # Desligar estratégias no banco de dados
            async with get_db_context() as db:
                # Desativar todas as configs de autotrade desta conta
                update_result = await db.execute(
                    text("""
                        UPDATE autotrade_configs 
                        SET is_active = 0, 
                            updated_at = datetime('now')
                        WHERE account_id = :account_id
                    """),
                    {"account_id": self.account_id}
                )
                await db.commit()
                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] {update_result.rowcount} estratégia(s) desligada(s)",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )

            # Enviar notificação via Telegram
            await self._send_zero_balance_notification(balance_value, is_demo)

        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao lidar com saldo zero: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            import traceback
            logger.error(traceback.format_exc())

    async def _send_zero_balance_notification(self, balance_value: float, is_demo: bool):
        """Enviar notificação via Telegram sobre saldo zero"""
        try:
            from services.notifications.telegram_v2 import telegram_service_v2

            account_type = "Demo" if is_demo else "Real"
            message = f"""[SALDO ZERO DETECTADO]

Conta: {self.user_name}
Tipo: {account_type}
Saldo atual: ${balance_value:.2f}

Sua conexão foi desconectada e todas as estratégias foram desligadas automaticamente.

Por favor, adicione saldo à sua conta para continuar usando o AutoTrade."""

            # Buscar chat_id do usuário
            async with get_db_context() as db:
                result = await db.execute(
                    text("SELECT telegram_chat_id FROM users WHERE id = (SELECT user_id FROM accounts WHERE id = :account_id)"),
                    {"account_id": self.account_id}
                )
                user_data = result.fetchone()

                if user_data and user_data[0]:
                    chat_id = user_data[0]
                    await telegram_service_v2.send_message(
                        chat_id=chat_id,
                        text=message,
                        priority=1  # Alta prioridade
                    )
                    logger.info(
                        f"{self._get_log_prefix()} [{self.account_id}] Notificação Telegram enviada para {chat_id}",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )
                else:
                    logger.warning(
                        f"{self._get_log_prefix()} [{self.account_id}] Chat ID do Telegram não encontrado para enviar notificação",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )

        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao enviar notificação Telegram: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            import traceback
            logger.error(traceback.format_exc())

    @property
    def is_connected(self) -> bool:
        """Sincroniza estado com o client para evitar conexão fantasma."""
        if self.client:
            self._is_connected = bool(self.client.is_connected)
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool):
        self._is_connected = bool(value)
    
    async def subscribe_asset(self, asset_symbol: str):
        """Inscrever em um asset"""
        try:
            if not self.client or not self.is_connected:
                return False
            
            # Usar changeSymbol para inscrever
            data = {
                "asset": asset_symbol,
                "period": 1
            }
            message_data = ["changeSymbol", data]
            message = f'42{json.dumps(message_data)}'
            
            if hasattr(self.client, '_keep_alive_manager') and self.client._keep_alive_manager:
                await self.client._keep_alive_manager.send_message(message)
            elif hasattr(self.client, '_websocket'):
                await self.client._websocket.send_message(message)
            
            self.subscribed_assets.add(asset_symbol)
            return True
        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao inscrever {asset_symbol}: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            return False
    
    @retry_on_db_lock(max_retries=3, retry_delay=1.0, timeout=15.0)
    async def _on_balance_updated(self, data: Dict[str, Any]):
        """Handler para evento de atualização de saldo com retry"""
        try:
            logger.debug(
                f"{self._get_log_prefix()} [{self.account_id}] Evento balance_updated recebido: {data}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            if "balance" in data:
                try:
                    balance_value = float(data["balance"])
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"{self._get_log_prefix()} [{self.account_id}] Erro ao converter balance para float: {e}",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )
                    return

                payload_is_demo = data.get("isDemo", data.get("is_demo"))
                is_demo = self.is_demo
                if payload_is_demo is not None and bool(payload_is_demo) != self.is_demo:
                    logger.warning(
                        f"{self._get_log_prefix()} [{self.account_id}] is_demo divergente no payload "
                        f"(payload={payload_is_demo}, conexao={self.is_demo}); usando conexao",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )

                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] Balance recebido: {balance_value}, is_demo: {is_demo}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )

                # Determinar qual coluna atualizar
                if is_demo:
                    column = "balance_demo"
                else:
                    column = "balance_real"

                # Atualizar no banco de dados
                async with get_db_context() as db:
                    await db.execute(
                        text(f"UPDATE accounts SET {column} = :balance, updated_at = datetime('now') WHERE id = :account_id"),
                        {"balance": balance_value, "account_id": self.account_id}
                    )

                    # Atualizar highest_balance nas configs ativas desta conta
                    from models import AutoTradeConfig
                    from sqlalchemy import select

                    result = await db.execute(
                        select(AutoTradeConfig).where(
                            AutoTradeConfig.account_id == self.account_id,
                            AutoTradeConfig.is_active == True
                        )
                    )
                    configs = result.scalars().all()

                    for config in configs:
                        # Inicializar initial_balance se ainda não foi definido (primeira vez que a estratégia é ligada)
                        if config.initial_balance is None:
                            config.initial_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 💰 initial_balance inicializado: ${balance_value:.2f} para config {config.id}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )
                        # Inicializar highest_balance se ainda não foi definido
                        if config.highest_balance is None:
                            config.highest_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 💰 highest_balance inicializado: ${balance_value:.2f} para config {config.id}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )
                        # Atualizar highest_balance se o saldo atual for maior
                        elif balance_value > config.highest_balance:
                            old_highest = config.highest_balance
                            config.highest_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 📈 highest_balance atualizado: ${old_highest:.2f} → ${balance_value:.2f}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )

                    await db.commit()

                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] Saldo {column} atualizado: {balance_value}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )
            else:
                logger.warning(
                    f"{self._get_log_prefix()} [{self.account_id}] Evento balance_updated sem campo 'balance': {data}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )
        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao atualizar saldo: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            import traceback
            logger.error(traceback.format_exc())
    
    @retry_on_db_lock(max_retries=3, retry_delay=1.0, timeout=15.0)
    async def _on_balance_data(self, data: Dict[str, Any]):
        """Handler para evento de dados de saldo (bytes message) com retry"""
        try:
            logger.info(
                "Evento balance_data recebido",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            if "balance" in data:
                try:
                    balance_value = float(data["balance"])
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"{self._get_log_prefix()} [{self.account_id}] Erro ao converter balance para float: {e}",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )
                    return
                
                payload_is_demo = data.get("isDemo", data.get("is_demo"))
                is_demo = self.is_demo
                if payload_is_demo is not None and bool(payload_is_demo) != self.is_demo:
                    logger.warning(
                        f"{self._get_log_prefix()} [{self.account_id}] is_demo divergente no payload "
                        f"(payload={payload_is_demo}, conexao={self.is_demo}); usando conexao",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )

                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] *** Balance recebido (balance_data): {balance_value}, is_demo: {is_demo}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )
                
                # Determinar qual coluna atualizar
                if is_demo:
                    column = "balance_demo"
                else:
                    column = "balance_real"
                
                # Atualizar no banco de dados
                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] *** Atualizando saldo no banco: {column} = {balance_value}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )
                async with get_db_context() as db:
                    result = await db.execute(
                        text(f"UPDATE accounts SET {column} = :balance, updated_at = datetime('now') WHERE id = :account_id"),
                        {"balance": balance_value, "account_id": self.account_id}
                    )

                    # Atualizar highest_balance nas configs ativas desta conta
                    from models import AutoTradeConfig
                    from sqlalchemy import select

                    configs_result = await db.execute(
                        select(AutoTradeConfig).where(
                            AutoTradeConfig.account_id == self.account_id,
                            AutoTradeConfig.is_active == True
                        )
                    )
                    configs = configs_result.scalars().all()

                    for config in configs:
                        # Inicializar initial_balance se ainda não foi definido (primeira vez que a estratégia é ligada)
                        if config.initial_balance is None:
                            config.initial_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 💰 initial_balance inicializado: ${balance_value:.2f} para config {config.id}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )
                        # Inicializar highest_balance se ainda não foi definido
                        if config.highest_balance is None:
                            config.highest_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 💰 highest_balance inicializado: ${balance_value:.2f} para config {config.id}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )
                        # Atualizar highest_balance se o saldo atual for maior
                        elif balance_value > config.highest_balance:
                            old_highest = config.highest_balance
                            config.highest_balance = balance_value
                            logger.info(
                                f"{self._get_log_prefix()} [{self.account_id}] 📈 highest_balance atualizado: ${old_highest:.2f} → ${balance_value:.2f}",
                                extra={
                                    "user_name": self.user_name,
                                    "account_id": self.account_id[:8] if self.account_id else "",
                                    "account_type": self.connection_type
                                }
                            )

                    await db.commit()
                    logger.info(
                        f"{self._get_log_prefix()} [{self.account_id}] *** Resultado UPDATE: {result.rowcount} linhas afetadas",
                        extra={
                            "user_name": self.user_name,
                            "account_id": self.account_id[:8] if self.account_id else "",
                            "account_type": self.connection_type
                        }
                    )

                logger.info(
                    f"{self._get_log_prefix()} [{self.account_id}] *** Saldo {column} atualizado (balance_data): {balance_value}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )

                # Verificar se o saldo é zero e desconectar se necessário
                if balance_value == 0:
                    await self._handle_zero_balance(balance_value, is_demo)
            else:
                logger.warning(
                    f"{self._get_log_prefix()} [{self.account_id}] Evento balance_data sem campo 'balance': {data}",
                    extra={
                        "user_name": self.user_name,
                        "account_id": self.account_id[:8] if self.account_id else "",
                        "account_type": self.connection_type
                    }
                )
        except Exception as e:
            logger.error(
                f"{self._get_log_prefix()} [{self.account_id}] Erro ao processar evento balance_data: {e}",
                extra={
                    "user_name": self.user_name,
                    "account_id": self.account_id[:8] if self.account_id else "",
                    "account_type": self.connection_type
                }
            )
            import traceback
            logger.error(traceback.format_exc())


class UserConnectionManager:
    """Gerencia conexões WebSocket de múltiplos usuários"""

    def __init__(self, trade_executor=None):
        self.connections: Dict[str, UserConnection] = {}  # key: account_id_type (ex: "abc123_demo")
        self._monitoring_task = None
        self._is_running = False
        self.trade_executor = trade_executor
    
    def _get_connection_key(self, account_id: str, connection_type: str) -> str:
        """Gerar chave única para a conexão"""
        return f"{account_id}_{connection_type}"
    
    async def start_monitoring(self):
        """Iniciar monitoramento constante de conexões"""
        self._is_running = True
        self._monitoring_task = asyncio.create_task(self._monitor_loop())
        logger.info("Gerenciador de conexões iniciado", extra={
            "user_name": "SISTEMA",
            "account_id": "",
            "account_type": ""
        })
    
    async def stop_monitoring(self):
        """Parar monitoramento e desconectar todas as conexões"""
        self._is_running = False
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.debug("Timeout ao aguardar finalização da task de monitoramento")
            except asyncio.CancelledError:
                pass
        
        # Desconectar todas as conexões
        for connection in list(self.connections.values()):
            await connection.disconnect()
        
        self.connections.clear()
        logger.info("Gerenciador de conexões parado", extra={
            "user_name": "SISTEMA",
            "account_id": "",
            "account_type": ""
        })
    
    async def _monitor_loop(self):
        """Loop de monitoramento para conectar/desconectar dinamicamente"""
        from core.database import get_db_context
        from models import Account
        from sqlalchemy import select, text
        from datetime import datetime, timedelta

        logger.info("Loop de monitoramento de conexões iniciado", extra={
            "user_name": "SISTEMA",
            "account_id": "",
            "account_type": ""
        })
        logger.info(f"_is_running = {self._is_running}", extra={
            "user_name": "SISTEMA",
            "account_id": "",
            "account_type": ""
        })

        while self._is_running:
            logger.info("Entrando no loop de monitoramento...", extra={
                "user_name": "SISTEMA",
                "account_id": "",
                "account_type": ""
            })
            try:
                logger.info("Dormindo por 5 segundos...", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })
                await asyncio.sleep(5)  # Verificar a cada 5 segundos
                logger.info("Acordou do sono", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })

                if not self._is_running:
                    logger.info("Loop encerrado: _is_running=False", extra={
                        "user_name": "SISTEMA",
                        "account_id": "",
                        "account_type": ""
                    })
                    break

                logger.info("Verificando conexões...", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })

                # Criar nova sessão para cada iteração para evitar cache
                logger.info("Abrindo conexão com banco de dados...", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })
                try:
                    async with get_db_context() as db:
                        logger.info("Conexão com banco de dados aberta", extra={
                            "user_name": "SISTEMA",
                            "account_id": "",
                            "account_type": ""
                        })
                        # Buscar todas as contas ativas OU com configs de autotrade ativas
                        result = await db.execute(
                            select(Account).where(
                                or_(
                                    Account.is_active == True,
                                    exists().where(
                                        and_(
                                            AutoTradeConfig.account_id == Account.id,
                                            AutoTradeConfig.is_active == True
                                        )
                                    )
                                )
                            )
                        )
                        accounts = result.scalars().all()

                        logger.info(f"Encontradas {len(accounts)} contas ativas", extra={
                            "user_name": "SISTEMA",
                            "account_id": "",
                            "account_type": ""
                        })

                        now = datetime.now()  # Usar tempo local para comparar com timestamps do banco
                        inactivity_threshold = timedelta(minutes=10)  # 10 minutos de inatividade

                        # Se não houver contas, pular o restante do loop
                        if not accounts:
                            logger.debug("Nenhuma conta encontrada, pulando verificação de conexões", extra={
                                "user_name": "SISTEMA",
                                "account_id": "",
                                "account_type": ""
                            })
                            continue

                        # Limite de concorrência: 10 conexões simultâneas
                        sem = asyncio.Semaphore(10)
                        async def connect_account(account):
                            async with sem:
                                await self._handle_account_connection(account, now, inactivity_threshold)
                        await asyncio.gather(*(connect_account(acc) for acc in accounts))
                except Exception as e:
                    logger.error(f"Erro ao acessar banco de dados: {e}", extra={
                        "user_name": "SISTEMA",
                        "account_id": "",
                        "account_type": ""
                    })
                    import traceback
                    logger.error(traceback.format_exc())
                    # Aguardar antes de tentar novamente para evitar spam de logs
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("Loop cancelado (CancelledError)", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })
                break
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento de conexões: {e}", extra={
                    "user_name": "SISTEMA",
                    "account_id": "",
                    "account_type": ""
                })
                import traceback
                logger.error(traceback.format_exc())
                await asyncio.sleep(5)

        logger.info("Loop de monitoramento de conexões encerrado", extra={
            "user_name": "SISTEMA",
            "account_id": "",
            "account_type": ""
        })

    async def _handle_account_connection(self, account, now, inactivity_threshold):
        """Gerencia a conexão de uma única conta"""
        from core.database import get_db_context
        from sqlalchemy import text

        async with get_db_context() as db:
            # Buscar configurações de autotrade da conta
            result = await db.execute(
                text("""
                    SELECT
                        MAX(ac.is_active) as any_active,
                        COUNT(ac.id) as configs_count,
                        MAX(a.autotrade_demo) as autotrade_demo,
                        MAX(a.autotrade_real) as autotrade_real,
                        MAX(a.ssid_demo) as ssid_demo,
                        MAX(a.ssid_real) as ssid_real,
                        MAX(ac.last_activity_timestamp) as last_activity_timestamp,
                        u.name as user_name
                    FROM accounts a
                    LEFT JOIN autotrade_configs ac ON a.id = ac.account_id
                    LEFT JOIN users u ON a.user_id = u.id
                    WHERE a.id = :account_id
                    GROUP BY a.id, a.autotrade_demo, a.autotrade_real, a.ssid_demo, a.ssid_real, u.name
                """),
                {"account_id": account.id}
            )
            row = result.fetchone()

            if not row or len(row) < 8:
                logger.debug(f"Conta {account.id[:8]}...: Nenhuma configuração encontrada")
                return

            any_active, configs_count, autotrade_demo, autotrade_real, ssid_demo, ssid_real, last_activity_timestamp, user_name = row
            is_active = bool(any_active)
            has_configs = bool(configs_count and configs_count > 0)

            logger.debug(
                f"Conta {account.id[:8]}...: has_configs={has_configs}, is_active={is_active}, "
                f"autotrade_demo={autotrade_demo}, autotrade_real={autotrade_real}, "
                f"ssid_demo={'***' if ssid_demo else 'N/A'}, ssid_real={'***' if ssid_real else 'N/A'}",
                extra={
                    "user_name": user_name,
                    "account_id": account.id[:8] if account.id else "",
                    "account_type": ""
                }
            )

            if not has_configs:
                logger.debug(
                    f"Conta {account.id[:8]}...: Sem estratégias, pulando conexões",
                    extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": ""
                    }
                )
                # Desconectar se estiver conectado
                demo_key = self._get_connection_key(account.id, 'demo')
                real_key = self._get_connection_key(account.id, 'real')
                if demo_key in self.connections:
                    await self.connections[demo_key].disconnect()
                    del self.connections[demo_key]
                if real_key in self.connections:
                    await self.connections[real_key].disconnect()
                    del self.connections[real_key]
                return

            parsed_last_activity = None
            if last_activity_timestamp:
                # Converter string para datetime se necessário
                if isinstance(last_activity_timestamp, str):
                    try:
                        parsed_last_activity = datetime.fromisoformat(last_activity_timestamp)
                    except (ValueError, TypeError):
                        logger.warning(
                            f"[{account.id[:8]}...] last_activity_timestamp inválido, ignorando",
                            extra={
                                "user_name": user_name,
                                "account_id": account.id[:8] if account.id else "",
                                "account_type": ""
                            }
                        )
                else:
                    parsed_last_activity = last_activity_timestamp

            if not is_active:
                if parsed_last_activity:
                    time_inactive = now - parsed_last_activity
                    if time_inactive > inactivity_threshold:
                        demo_key = self._get_connection_key(account.id, 'demo')
                        real_key = self._get_connection_key(account.id, 'real')
                        has_connection = demo_key in self.connections or real_key in self.connections
                        if has_connection:
                            logger.info(
                                f"[{account.id[:8]}...] Estratégia não ativada há "
                                f"{time_inactive.total_seconds()/60:.1f} minutos, desconectando websocket...",
                                extra={
                                    "user_name": user_name,
                                    "account_id": account.id[:8] if account.id else "",
                                    "account_type": ""
                                }
                            )
                            if demo_key in self.connections:
                                await self.connections[demo_key].disconnect()
                                del self.connections[demo_key]
                            if real_key in self.connections:
                                await self.connections[real_key].disconnect()
                                del self.connections[real_key]
                return

            if is_active and parsed_last_activity:
                time_inactive = now - parsed_last_activity
                # Se o timestamp está no futuro, considerar como atividade recente
                if time_inactive.total_seconds() < 0:
                    time_inactive = timedelta(seconds=0)
                if time_inactive > inactivity_threshold:
                    logger.info(
                        f"[{account.id[:8]}...] Conta inativa por {time_inactive.total_seconds()/60:.1f} "
                        "minutos, desconectando websocket (autotrade permanece ativo)",
                        extra={
                            "user_name": user_name,
                            "account_id": account.id[:8] if account.id else "",
                            "account_type": ""
                        }
                    )
                    # Desconectar todas as conexões desta conta
                    demo_key = self._get_connection_key(account.id, 'demo')
                    real_key = self._get_connection_key(account.id, 'real')
                    if demo_key in self.connections:
                        await self.connections[demo_key].disconnect()
                        del self.connections[demo_key]
                    if real_key in self.connections:
                        await self.connections[real_key].disconnect()
                        del self.connections[real_key]
                    return

            should_connect_demo = bool(autotrade_demo)
            should_connect_real = bool(autotrade_real)

            # Se não há flags de autotrade definidos mas há SSID, tentar conectar
            if not should_connect_demo and not should_connect_real and has_configs:
                if ssid_demo:
                    should_connect_demo = True
                    logger.debug(f"[{account.id[:8]}...] Conectando demo (SSID disponível)", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "demo"
                    })
                elif ssid_real:
                    should_connect_real = True
                    logger.debug(f"[{account.id[:8]}...] Conectando real (SSID disponível)", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "real"
                    })

            # Se autotrade está ativo mas não há flags definidos, forçar conexão
            if is_active and not should_connect_demo and not should_connect_real and has_configs:
                if ssid_demo:
                    should_connect_demo = True
                    logger.info(f"[{account.id[:8]}...] Autotrade ativo, conectando demo...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "demo"
                    })
                elif ssid_real:
                    should_connect_real = True
                    logger.info(f"[{account.id[:8]}...] Autotrade ativo, conectando real...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "real"
                    })

            # Verificar conexão demo
            demo_key = self._get_connection_key(account.id, 'demo')
            if should_connect_demo and ssid_demo:
                if demo_key not in self.connections or not self.connections[demo_key].is_connected:
                    logger.info(f"[{account.id[:8]}...] Iniciando conexão demo para usuário...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "demo"
                    })
                    connection = UserConnection(account.id, ssid_demo, 'demo', user_name, account_role='usuario')
                    await connection.connect(self.trade_executor)
                    self.connections[demo_key] = connection
            else:
                if demo_key in self.connections:
                    logger.info(f"[{account.id[:8]}...] Desconectando conexão demo...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "demo"
                    })
                    await self.connections[demo_key].disconnect()
                    del self.connections[demo_key]

            # Verificar conexão real
            real_key = self._get_connection_key(account.id, 'real')
            if should_connect_real and ssid_real:
                if real_key not in self.connections or not self.connections[real_key].is_connected:
                    logger.info(f"[{account.id[:8]}...] Iniciando conexão real para usuário...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "real"
                    })
                    connection = UserConnection(account.id, ssid_real, 'real', user_name, account_role='usuario')
                    await connection.connect(self.trade_executor)
                    self.connections[real_key] = connection
            else:
                if real_key in self.connections:
                    logger.info(f"[{account.id[:8]}...] Desconectando conexão real...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "real"
                    })
                    await self.connections[real_key].disconnect()
                    del self.connections[real_key]

            # Garantir que pelo menos uma conexão esteja ativa quando há estratégia ligada
            if is_active and not autotrade_demo and not autotrade_real:
                logger.warning(f"[{account.id[:8]}...] Nenhuma conexão ativa! Verificando autotrade_configs.is_active...", extra={
                    "user_name": user_name,
                    "account_id": account.id[:8] if account.id else "",
                    "account_type": ""
                })
                # Se autotrade_configs.is_active estiver ativo, forçar conexão demo
                if is_active and ssid_demo:
                    logger.info(f"[{account.id[:8]}...] Forçando conexão demo para usuário...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "demo"
                    })
                    connection = UserConnection(account.id, ssid_demo, 'demo', user_name, account_role='usuario')
                    await connection.connect(self.trade_executor)
                    self.connections[demo_key] = connection
                elif is_active and ssid_real:
                    logger.info(f"[{account.id[:8]}...] Forçando conexão real para usuário...", extra={
                        "user_name": user_name,
                        "account_id": account.id[:8] if account.id else "",
                        "account_type": "real"
                    })
                    connection = UserConnection(account.id, ssid_real, 'real', user_name, account_role='usuario')
                    await connection.connect(self.trade_executor)
                    self.connections[real_key] = connection

    def get_connection(self, account_id: str, connection_type: str) -> Optional[UserConnection]:
        """Obter conexão de um usuário"""
        key = self._get_connection_key(account_id, connection_type)
        return self.connections.get(key)
    
    def get_all_connections(self) -> list[UserConnection]:
        """Obter todas as conexões ativas"""
        return list(self.connections.values())
    
    async def disconnect_connection(self, account_id: str, connection_type: str):
        """Desconectar imediatamente uma conexão específica"""
        key = self._get_connection_key(account_id, connection_type)
        if key in self.connections:
            logger.info(f"[{account_id[:8]}...] Desconectando conexão {connection_type} imediatamente...", extra={
                "user_name": self.connections[key].user_name if key in self.connections else "",
                "account_id": account_id[:8] if account_id else "",
                "account_type": connection_type
            })
            await self.connections[key].disconnect()
            del self.connections[key]

    async def ensure_connection(self, account_id: str, connection_type: str, ssid: Optional[str]) -> bool:
        """Garantir que a conexão solicitada esteja ativa antes de prosseguir."""
        if not connection_type or not ssid:
            logger.warning(f"[{account_id[:8]}...] Conexão {connection_type} sem SSID, abortando", extra={
                "user_name": "",
                "account_id": account_id[:8] if account_id else "",
                "account_type": connection_type or ""
            })
            return False

        key = self._get_connection_key(account_id, connection_type)
        existing = self.connections.get(key)
        if existing and existing.is_connected:
            return True

        if existing:
            await existing.disconnect()
            del self.connections[key]

        logger.info(f"[{account_id[:8]}...] Conectando {connection_type} sob demanda para usuário...", extra={
            "user_name": "",
            "account_id": account_id[:8] if account_id else "",
            "account_type": connection_type
        })
        
        # Buscar nome do usuário do banco
        user_name = None
        try:
            async with get_db_context() as db:
                result = await db.execute(
                    text("""
                        SELECT u.name 
                        FROM users u 
                        JOIN accounts a ON a.user_id = u.id 
                        WHERE a.id = :account_id
                    """),
                    {"account_id": account_id}
                )
                row = result.fetchone()
                if row:
                    user_name = row[0]
        except Exception as e:
            logger.warning(f"[{account_id[:8]}...] Erro ao buscar nome do usuário: {e}")
        
        connection = UserConnection(account_id, ssid, connection_type, user_name=user_name, account_role='usuario')
        connected = await connection.connect(self.trade_executor)
        if connected:
            self.connections[key] = connection
            return True

        logger.warning(f"[{account_id[:8]}...] Falha ao conectar {connection_type} sob demanda", extra={
            "user_name": "",
            "account_id": account_id[:8] if account_id else "",
            "account_type": connection_type
        })
        return False
    
    async def switch_connection(self, account_id: str, from_type: str, to_type: str, ssid: str):
        """Alternar entre conexões demo e real, conectando a nova PRIMEIRO antes de desconectar a anterior"""
        import asyncio
        
        # Conectar a nova conexão PRIMEIRO (evita gap sem conexão ativa)
        if to_type and ssid:
            logger.info(f"[{account_id[:8]}...] Conectando nova conexão {to_type} para usuário...", extra={
                "user_name": "",
                "account_id": account_id[:8] if account_id else "",
                "account_type": to_type
            })
            
            # Buscar nome do usuário do banco
            user_name = None
            try:
                async with get_db_context() as db:
                    result = await db.execute(
                        text("""
                            SELECT u.name 
                            FROM users u 
                            JOIN accounts a ON a.user_id = u.id 
                            WHERE a.id = :account_id
                        """),
                        {"account_id": account_id}
                    )
                    row = result.fetchone()
                    if row:
                        user_name = row[0]
            except Exception as e:
                logger.warning(f"[{account_id[:8]}...] Erro ao buscar nome do usuário: {e}")
            
            connection = UserConnection(account_id, ssid, to_type, user_name=user_name, account_role='usuario')
            await connection.connect(self.trade_executor)
            self.connections[self._get_connection_key(account_id, to_type)] = connection
            
            # Adicionar cooldown de 3 segundos após estabelecer a conexão
            logger.info(f"[{account_id[:8]}...] Aguardando 3 segundos para estabilização da conexão...", extra={
                "user_name": "",
                "account_id": account_id[:8] if account_id else "",
                "account_type": to_type
            })
            await asyncio.sleep(3)
            logger.info(f"[{account_id[:8]}...] Conexão estabilizada, pronto para operações", extra={
                "user_name": "",
                "account_id": account_id[:8] if account_id else "",
                "account_type": to_type
            })
        
        # Desconectar a conexão anterior DEPOIS que a nova está conectada
        if from_type:
            await self.disconnect_connection(account_id, from_type)
