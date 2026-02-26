"""Persistent Incremental EMA - Média Móvel Exponencial stateful"""
import asyncio
import json
from typing import Optional, Tuple
from datetime import datetime


class PersistentEMA:
    """
    EMA (Exponential Moving Average) incremental com persistência Redis.
    
    Fórmula:
        multiplier = 2 / (period + 1)
        EMA = (price * multiplier) + (EMA_prev * (1 - multiplier))
    
    Características:
    - Cálculo O(1) por tick
    - Estado preservado em Redis
    - Async/await compatível
    
    Attributes:
        symbol: Par de trading
        period: Período EMA (default 20)
        last_ema: Valor EMA atual
        last_price: Último preço processado
    """
    
    def __init__(self, symbol: str, period: int = 20, redis_client=None):
        self.symbol = symbol.upper()
        self.period = period
        self.multiplier = 2.0 / (period + 1)
        self.redis = redis_client
        
        # Estado
        self.last_ema: Optional[float] = None
        self.last_price: Optional[float] = None
        self.initialized: bool = False
        
        # Chave Redis
        self._redis_key = f"ema_state:{self.symbol}:{self.period}"
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
                    self.last_ema = state.get("last_ema")
                    self.last_price = state.get("last_price")
                    self.initialized = state.get("initialized", False)
                return True
        except Exception as e:
            print(f"[PersistentEMA] Erro ao carregar estado {self.symbol}: {e}")
        
        return False
    
    async def save_state(self) -> bool:
        """Persistir estado."""
        if not self.redis:
            return False
        
        try:
            state = {
                "last_ema": self.last_ema,
                "last_price": self.last_price,
                "initialized": self.initialized,
                "updated_at": datetime.utcnow().isoformat()
            }
            await self.redis.set(self._redis_key, json.dumps(state))
            return True
        except Exception as e:
            print(f"[PersistentEMA] Erro ao salvar estado {self.symbol}: {e}")
            return False
    
    async def update(self, price: float) -> Tuple[Optional[float], float]:
        """
        Atualizar EMA com novo preço.
        
        Returns:
            (EMA_value, confidence)
        """
        async with self._lock:
            if not self.initialized:
                # Primeiro preço - inicializa EMA
                self.last_ema = price
                self.last_price = price
                self.initialized = True
                await self.save_state()
                return None, 0.0
            
            # Calcular novo EMA
            self.last_ema = (price * self.multiplier) + (self.last_ema * (1 - self.multiplier))
            self.last_price = price
        
        await self.save_state()
        
        # Confiança baseada em quão próximo o preço está do EMA
        if self.last_ema > 0:
            deviation = abs(price - self.last_ema) / self.last_ema
            confidence = max(0.0, 1.0 - deviation * 10)  # Normalizar
        else:
            confidence = 0.0
        
        return self.last_ema, confidence
    
    def get_signal_direction(self, price: float, threshold_pct: float = 0.001) -> str:
        """
        Determinar sinal baseado em cruzamento de preço com EMA.
        
        Args:
            price: Preço atual
            threshold_pct: Threshold percentual para sinal
            
        Returns:
            'buy' (preço > EMA), 'sell' (preço < EMA), 'hold'
        """
        if self.last_ema is None:
            return 'hold'
        
        diff_pct = (price - self.last_ema) / self.last_ema
        
        if diff_pct > threshold_pct:
            return 'buy'  # Preço acima do EMA = tendência de alta
        elif diff_pct < -threshold_pct:
            return 'sell'  # Preço abaixo do EMA = tendência de baixa
        return 'hold'
    
    async def reset(self):
        """Resetar estado."""
        async with self._lock:
            self.last_ema = None
            self.last_price = None
            self.initialized = False
        
        if self.redis:
            await self.redis.delete(self._redis_key)
    
    @property
    def is_ready(self) -> bool:
        return self.initialized and self.last_ema is not None
