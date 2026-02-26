"""Persistent Incremental MACD - Moving Average Convergence Divergence stateful"""
import asyncio
import json
from typing import Optional, Tuple, Dict
from datetime import datetime


class PersistentMACD:
    """
    MACD incremental com persistência Redis.
    
    Componentes:
    - MACD Line = EMA(12) - EMA(26)
    - Signal Line = EMA(9) do MACD Line
    - Histogram = MACD Line - Signal Line
    
    Implementação:
    - Usa 3 EMAs incrementais (fast, slow, signal)
    - Cálculo O(1) por tick
    - Estado preservado em Redis
    
    Attributes:
        symbol: Par de trading
        fast_period: Período EMA rápida (default 12)
        slow_period: Período EMA lenta (default 26)
        signal_period: Período sinal (default 9)
    """
    
    def __init__(
        self,
        symbol: str,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        redis_client=None
    ):
        self.symbol = symbol.upper()
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.redis = redis_client
        
        # Multipliers para EMAs
        self.fast_mult = 2.0 / (fast_period + 1)
        self.slow_mult = 2.0 / (slow_period + 1)
        self.signal_mult = 2.0 / (signal_period + 1)
        
        # Estado
        self.ema_fast: Optional[float] = None
        self.ema_slow: Optional[float] = None
        self.ema_signal: Optional[float] = None
        self.macd_line: Optional[float] = None
        self.histogram: Optional[float] = None
        self.last_price: Optional[float] = None
        self.initialized: bool = False
        
        # Chave Redis
        self._redis_key = f"macd_state:{self.symbol}:{fast_period}:{slow_period}:{signal_period}"
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
                    self.ema_fast = state.get("ema_fast")
                    self.ema_slow = state.get("ema_slow")
                    self.ema_signal = state.get("ema_signal")
                    self.macd_line = state.get("macd_line")
                    self.histogram = state.get("histogram")
                    self.last_price = state.get("last_price")
                    self.initialized = state.get("initialized", False)
                return True
        except Exception as e:
            print(f"[PersistentMACD] Erro ao carregar estado {self.symbol}: {e}")
        
        return False
    
    async def save_state(self) -> bool:
        """Persistir estado."""
        if not self.redis:
            return False
        
        try:
            state = {
                "ema_fast": self.ema_fast,
                "ema_slow": self.ema_slow,
                "ema_signal": self.ema_signal,
                "macd_line": self.macd_line,
                "histogram": self.histogram,
                "last_price": self.last_price,
                "initialized": self.initialized,
                "updated_at": datetime.utcnow().isoformat()
            }
            await self.redis.set(self._redis_key, json.dumps(state))
            return True
        except Exception as e:
            print(f"[PersistentMACD] Erro ao salvar estado {self.symbol}: {e}")
            return False
    
    async def update(self, price: float) -> Tuple[Optional[Dict], float]:
        """
        Atualizar MACD com novo preço.
        
        Returns:
            (macd_data, confidence)
            - macd_data: Dict com 'macd', 'signal', 'histogram' ou None
            - confidence: 0.0 a 1.0
        """
        async with self._lock:
            if not self.initialized:
                # Primeiro preço - inicializa ambos EMAs
                self.ema_fast = price
                self.ema_slow = price
                self.last_price = price
                self.initialized = True
                await self.save_state()
                return None, 0.0
            
            # Atualizar EMAs
            self.ema_fast = (price * self.fast_mult) + (self.ema_fast * (1 - self.fast_mult))
            self.ema_slow = (price * self.slow_mult) + (self.ema_slow * (1 - self.slow_mult))
            
            # Calcular MACD Line
            self.macd_line = self.ema_fast - self.ema_slow
            
            # Atualizar Signal Line (EMA do MACD)
            if self.ema_signal is None:
                self.ema_signal = self.macd_line
            else:
                self.ema_signal = (self.macd_line * self.signal_mult) + (self.ema_signal * (1 - self.signal_mult))
            
            # Calcular Histogram
            self.histogram = self.macd_line - self.ema_signal
            self.last_price = price
        
        await self.save_state()
        
        # Preparar resultado
        result = {
            'macd': self.macd_line,
            'signal': self.ema_signal,
            'histogram': self.histogram
        }
        
        # Confiança baseada em força do histograma
        # Histograma maior = sinal mais forte
        if self.histogram:
            hist_strength = abs(self.histogram)
            # Normalizar (assumindo range típico 0-0.01 para forex)
            confidence = min(1.0, hist_strength * 100)
        else:
            confidence = 0.0
        
        return result, confidence
    
    def get_signal_direction(self) -> str:
        """
        Determinar sinal baseado em cruzamento MACD/Signal.
        
        Returns:
            'buy' (MACD cruza acima do Signal), 'sell' (cruza abaixo), 'hold'
        """
        if self.macd_line is None or self.ema_signal is None:
            return 'hold'
        
        # MACD acima do sinal = bullish
        if self.macd_line > self.ema_signal:
            return 'buy'
        elif self.macd_line < self.ema_signal:
            return 'sell'
        return 'hold'
    
    def get_momentum(self) -> str:
        """
        Classificar momentum baseado no histograma.
        
        Returns:
            'strong_bullish', 'weak_bullish', 'neutral', 'weak_bearish', 'strong_bearish'
        """
        if self.histogram is None:
            return 'neutral'
        
        hist = self.histogram
        
        if hist > 0.005:
            return 'strong_bullish'
        elif hist > 0:
            return 'weak_bullish'
        elif hist > -0.005:
            return 'weak_bearish'
        else:
            return 'strong_bearish'
    
    async def reset(self):
        """Resetar estado."""
        async with self._lock:
            self.ema_fast = None
            self.ema_slow = None
            self.ema_signal = None
            self.macd_line = None
            self.histogram = None
            self.last_price = None
            self.initialized = False
        
        if self.redis:
            await self.redis.delete(self._redis_key)
    
    @property
    def is_ready(self) -> bool:
        return self.initialized and self.macd_line is not None
