"""Trade Timing Manager - Gerencia execução de trades no sinal ou no fechamento da vela"""
import asyncio
import time
import logging
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PendingTrade:
    """Representa um trade agendado para execução no fechamento da vela"""
    signal: Dict[str, Any]
    symbol: str
    timeframe: int
    strategy_id: str
    account_id: str
    autotrade_config: Dict[str, Any]
    scheduled_for: float  # Timestamp do fechamento da vela
    created_at: float  # Timestamp quando o sinal foi criado
    key: str  # Chave única para identificar o trade pendente


class TradeTimingManager:
    """Gerencia o timing de execução de trades (no sinal ou no fechamento da vela)"""
    
    def __init__(self):
        self.pending_trades: Dict[str, PendingTrade] = {}  # key: PendingTrade
        self.candle_close_callbacks: list[Callable] = []
        self._lock = asyncio.Lock()
    
    def add_candle_close_callback(self, callback: Callable):
        """Adicionar callback para fechamento de vela"""
        self.candle_close_callbacks.append(callback)
    
    async def notify_candle_close(self, symbol: str, timeframe: int, close_time: float):
        """Notificar callbacks quando uma vela fecha"""
        for callback in self.candle_close_callbacks:
            try:
                await callback(symbol, timeframe, close_time)
            except Exception as e:
                logger.error(f"Erro ao executar callback de fechamento de vela: {e}")
    
    async def add_pending_trade(
        self,
        signal: Dict[str, Any],
        symbol: str,
        timeframe: int,
        strategy_id: str,
        account_id: str,
        autotrade_config: Dict[str, Any]
    ) -> Optional[PendingTrade]:
        """Adicionar trade agendado para execução no fechamento da vela"""
        async with self._lock:
            # Calcular timestamp do próximo fechamento da vela
            current_time = time.time()
            scheduled_for = self._calculate_next_candle_close(current_time, timeframe)
            
            # Criar chave única
            key = f"{symbol}_{timeframe}_{account_id}_{scheduled_for}"
            
            # Verificar se já existe um trade pendente para esta chave
            if key in self.pending_trades:
                logger.debug(f"Trade pendente já existe para {key}")
                return None
            
            # Criar trade pendente
            pending_trade = PendingTrade(
                signal=signal,
                symbol=symbol,
                timeframe=timeframe,
                strategy_id=strategy_id,
                account_id=account_id,
                autotrade_config=autotrade_config,
                scheduled_for=scheduled_for,
                created_at=current_time,
                key=key
            )
            
            self.pending_trades[key] = pending_trade
            
            logger.info(
                f"📅 Trade agendado para fechamento da vela: {symbol} {timeframe}s "
                f"em {datetime.fromtimestamp(scheduled_for).strftime('%H:%M:%S')} "
                f"(chave: {key[:20]}...)"
            )
            
            return pending_trade
    
    async def get_pending_trades_for_candle_close(
        self,
        symbol: str,
        timeframe: int,
        close_time: float
    ) -> list[PendingTrade]:
        """Obter trades pendentes para este fechamento de vela"""
        async with self._lock:
            trades = []
            for key, pending in self.pending_trades.items():
                # Reduzir tolerância para 1 segundo para execução mais precisa
                if (pending.symbol == symbol and
                    pending.timeframe == timeframe and
                    abs(pending.scheduled_for - close_time) < 1.0):
                    trades.append(pending)
            return trades
    
    async def remove_pending_trade(self, key: str):
        """Remover trade pendente"""
        async with self._lock:
            if key in self.pending_trades:
                del self.pending_trades[key]
                logger.debug(f"Trade pendente removido: {key[:20]}...")
    
    async def remove_pending_trades_for_account(self, account_id: str):
        """Remover todos os trades pendentes para uma conta"""
        async with self._lock:
            keys_to_remove = [
                key for key, pending in self.pending_trades.items()
                if pending.account_id == account_id
            ]
            for key in keys_to_remove:
                del self.pending_trades[key]
                logger.debug(f"Trade pendente removido para conta {account_id[:8]}: {key[:20]}...")
    
    async def cleanup_expired_trades(self):
        """Remover trades pendentes expirados (mais de 2 minutos após o fechamento agendado)"""
        async with self._lock:
            current_time = time.time()
            keys_to_remove = []
            
            for key, pending in self.pending_trades.items():
                # Se passou mais de 2 minutos do fechamento agendado, considera expirado
                if current_time - pending.scheduled_for > 120:
                    keys_to_remove.append(key)
                    logger.warning(
                        f"⏰ Trade pendente expirado: {pending.symbol} {pending.timeframe}s "
                        f"(agendado para {datetime.fromtimestamp(pending.scheduled_for).strftime('%H:%M:%S')})"
                    )
            
            for key in keys_to_remove:
                del self.pending_trades[key]
    
    def _calculate_next_candle_close(self, current_time: float, timeframe: int) -> float:
        """
        Calcular timestamp do próximo fechamento da vela.
        
        Lógica:
        - Calcula o início da vela atual: (current_time // timeframe) * timeframe
        - Próximo fechamento = início da vela atual + timeframe
        
        Exemplos:
        - Se current_time=10 e timeframe=5: candle_start=10, next_close=15
        - Se current_time=12 e timeframe=5: candle_start=10, next_close=15
        - Se current_time=15 e timeframe=5: candle_start=15, next_close=20
        
        Nota: Se current_time está exatamente no fechamento, calcula o próximo fechamento
        """
        candle_start = (current_time // timeframe) * timeframe
        next_close = candle_start + timeframe
        
        # Se current_time está exatamente no fechamento, calcula o próximo fechamento
        if abs(current_time - next_close) < 0.1:
            next_close = candle_start + (timeframe * 2)
        
        return next_close
    
    async def get_pending_trades_count(self) -> int:
        """Obter número de trades pendentes"""
        async with self._lock:
            return len(self.pending_trades)
    
    async def get_pending_trades_for_account(self, account_id: str) -> list[PendingTrade]:
        """Obter todos os trades pendentes para uma conta"""
        async with self._lock:
            return [
                pending for pending in self.pending_trades.values()
                if pending.account_id == account_id
            ]
