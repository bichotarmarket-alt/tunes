"""Candle Close Tracker - Rastreia o fechamento de velas para execução de trades"""
import time
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class CandleCloseEvent:
    """Evento de fechamento de vela"""
    symbol: str
    timeframe: int
    close_time: float
    candle_data: Dict


class CandleCloseTracker:
    """Rastreia o fechamento de velas e notifica callbacks"""
    
    def __init__(self):
        self.candle_close_callbacks: list[Callable] = []
        self.last_candle_close: Dict[str, float] = {}  # key: symbol_timeframe, value: close_time
        self._close_detection_threshold = 0.1  # 100ms antes do fechamento para execução mais precisa
    
    def add_candle_close_callback(self, callback: Callable):
        """Adicionar callback para fechamento de vela"""
        self.candle_close_callbacks.append(callback)
    
    def on_candle_update(self, symbol: str, timeframe: int, candle: Dict):
        """
        Chamado quando um candle é atualizado.
        Detecta quando uma vela está fechando.
        """
        current_time = time.time()
        
        # ✅ CORRETO: Usar 'close_time' do candle, não 'time'
        candle_close_time = candle.get('close_time', 0)
        
        if not candle_close_time:
            # Sem close_time válido, ignorar
            return
        
        timeframe_seconds = timeframe
        
        # Calcular tempo até o fechamento
        time_until_close = candle_close_time - current_time

        # Se estamos dentro da janela de 0.5 segundos APÓS o fechamento da vela
        # (não antes do fechamento)
        time_since_close = current_time - candle_close_time
        if 0 <= time_since_close <= 0.5:
            # Verificar se já notificamos este fechamento
            key = f"{symbol}_{timeframe}"
            last_close = self.last_candle_close.get(key, 0)

            # Se já notificamos este fechamento recentemente (dentro de 100ms), ignorar
            if current_time - last_close < 0.1:
                return

            # Notificar callbacks
            self.last_candle_close[key] = current_time

            logger.info(
                f"🕯️ Vela fechou: {symbol} {timeframe}s "
                f"em {datetime.fromtimestamp(candle_close_time).strftime('%H:%M:%S.%f')[:-3]} "
                f"(passaram {time_since_close*1000:.0f}ms)"
            )

            # Executar callbacks
            for callback in self.candle_close_callbacks:
                try:
                    callback(symbol, timeframe, candle_close_time)
                except Exception as e:
                    logger.error(f"Erro ao executar callback de fechamento de vela: {e}")
    
    def calculate_next_candle_close(self, current_time: float, timeframe: int) -> float:
        """Calcular timestamp do próximo fechamento da vela"""
        candle_start = (current_time // timeframe) * timeframe
        candle_end = candle_start + timeframe
        
        # Se current_time está exatamente no fechamento, calcula o próximo fechamento
        if abs(current_time - candle_end) < 0.1:
            candle_end = candle_start + (timeframe * 2)
        
        return candle_end
    
    def is_candle_closing_soon(self, current_time: float, timeframe: int, threshold: float = 0.1) -> bool:
        """Verificar se uma vela está prestes a fechar"""
        candle_start = (current_time // timeframe) * timeframe
        candle_end = candle_start + timeframe
        time_until_close = candle_end - current_time
        return 0 < time_until_close <= threshold
    
    def get_time_until_close(self, current_time: float, timeframe: int) -> float:
        """Obter tempo até o fechamento da vela"""
        candle_start = (current_time // timeframe) * timeframe
        candle_end = candle_start + timeframe
        time_until_close = candle_end - current_time
        
        if time_until_close < 0:
            # Já passou do fechamento, calcular próximo fechamento
            next_candle_start = candle_start + timeframe
            next_candle_end = next_candle_start + timeframe
            return next_candle_end - current_time
        
        return time_until_close
    
    def get_candle_info(self, current_time: float, timeframe: int) -> Dict:
        """Obter informações sobre a vela atual"""
        candle_start = (current_time // timeframe) * timeframe
        candle_end = candle_start + timeframe
        time_until_close = candle_end - current_time
        candle_progress = (current_time - candle_start) / timeframe
        
        return {
            'start_time': candle_start,
            'end_time': candle_end,
            'time_until_close': time_until_close,
            'candle_progress': candle_progress,
            'is_closing_soon': 0 < time_until_close <= self._close_detection_threshold
        }
