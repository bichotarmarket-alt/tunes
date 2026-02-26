"""Persistent Incremental ATR - Average True Range stateful"""
import asyncio
import json
from typing import Optional, Tuple
from datetime import datetime


class PersistentATR:
    """
    ATR (Average True Range) incremental com persistência Redis.
    
    O ATR mede volatilidade do mercado.
    
    Cálculo:
        TR = max(high - low, |high - prev_close|, |low - prev_close|)
        ATR = ((ATR_prev * (period-1)) + TR) / period
    
    Como usamos apenas ticks (não candles completos), aproximamos:
        - high/low do período = max/min dos ticks recebidos
        - Usamos o preço como proxy para close
    
    Características:
    - Cálculo O(1) por tick
    - Estado preservado em Redis
    - Async/await compatível
    """
    
    def __init__(self, symbol: str, period: int = 14, redis_client=None):
        self.symbol = symbol.upper()
        self.period = period
        self.redis = redis_client
        
        # Estado
        self.last_atr: Optional[float] = None
        self.last_price: Optional[float] = None
        self.period_high: Optional[float] = None
        self.period_low: Optional[float] = None
        self.prev_close: Optional[float] = None
        self.tick_count: int = 0
        
        # Chave Redis
        self._redis_key = f"atr_state:{self.symbol}:{self.period}"
        self._lock = asyncio.Lock()
    
    async def load_state(self) -> bool:
        """Carregar estado persistido."""
        if not self.redis:
            return False
        
        try:
            data = await self.redis.get(self._redis_key)
            if data:
                state = json.loads(data)
                async with self._lock:
                    self.last_atr = state.get("last_atr")
                    self.last_price = state.get("last_price")
                    self.period_high = state.get("period_high")
                    self.period_low = state.get("period_low")
                    self.prev_close = state.get("prev_close")
                    self.tick_count = state.get("tick_count", 0)
                return True
        except Exception as e:
            print(f"[PersistentATR] Erro ao carregar estado {self.symbol}: {e}")
        
        return False
    
    async def save_state(self) -> bool:
        """Persistir estado."""
        if not self.redis:
            return False
        
        try:
            state = {
                "last_atr": self.last_atr,
                "last_price": self.last_price,
                "period_high": self.period_high,
                "period_low": self.period_low,
                "prev_close": self.prev_close,
                "tick_count": self.tick_count,
                "updated_at": datetime.utcnow().isoformat()
            }
            await self.redis.set(self._redis_key, json.dumps(state))
            return True
        except Exception as e:
            print(f"[PersistentATR] Erro ao salvar estado {self.symbol}: {e}")
            return False
    
    async def update(self, price: float) -> Tuple[Optional[float], float]:
        """
        Atualizar ATR com novo preço.
        
        Returns:
            (ATR_value, confidence)
            - ATR_value: None se insuficiente dados
            - confidence: 0.0 a 1.0 (normalizado)
        """
        async with self._lock:
            self.tick_count += 1
            
            if self.last_price is None:
                # Primeiro tick
                self.last_price = price
                self.period_high = price
                self.period_low = price
                self.prev_close = price
                await self.save_state()
                return None, 0.0
            
            # Atualizar high/low do período
            if self.period_high is None or price > self.period_high:
                self.period_high = price
            if self.period_low is None or price < self.period_low:
                self.period_low = price
            
            # Calcular True Range
            # TR = max(high - low, |high - prev_close|, |low - prev_close|)
            tr1 = self.period_high - self.period_low if self.period_high and self.period_low else 0
            tr2 = abs(price - self.prev_close) if self.prev_close else 0
            tr3 = tr2  # Simplificação: low ≈ price em ticks
            
            true_range = max(tr1, tr2, tr3)
            
            # Calcular ATR com Wilder's smoothing
            if self.last_atr is None:
                # Inicialização: primeiro TR
                self.last_atr = true_range
            else:
                self.last_atr = (self.last_atr * (self.period - 1) + true_range) / self.period
            
            # Resetar high/low para próximo período (simplificado - em produção usar candles)
            if self.tick_count % self.period == 0:
                self.prev_close = price
                self.period_high = price
                self.period_low = price
            
            self.last_price = price
        
        await self.save_state()
        
        # Confiança baseada em consistência do ATR
        # ATR muito volátil = menor confiança
        if self.last_atr is not None and self.prev_close:
            atr_pct = self.last_atr / self.prev_close
            # ATR entre 0.1% e 2% = ideal
            if 0.001 <= atr_pct <= 0.02:
                confidence = 1.0
            else:
                confidence = max(0.0, 1.0 - abs(atr_pct - 0.01) * 50)
        else:
            confidence = 0.0
        
        return self.last_atr, confidence
    
    def get_volatility_signal(self) -> str:
        """
        Classificar volatilidade atual.
        
        Returns:
            'high', 'normal', 'low'
        """
        if self.last_atr is None or not self.prev_close:
            return 'normal'
        
        atr_pct = self.last_atr / self.prev_close
        
        if atr_pct > 0.02:  # > 2%
            return 'high'
        elif atr_pct < 0.005:  # < 0.5%
            return 'low'
        return 'normal'
    
    async def reset(self):
        """Resetar estado."""
        async with self._lock:
            self.last_atr = None
            self.last_price = None
            self.period_high = None
            self.period_low = None
            self.prev_close = None
            self.tick_count = 0
        
        if self.redis:
            await self.redis.delete(self._redis_key)
    
    @property
    def is_ready(self) -> bool:
        return self.last_atr is not None and self.tick_count >= self.period
