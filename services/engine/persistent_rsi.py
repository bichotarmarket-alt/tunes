"""Persistent Incremental RSI - Indicador stateful com persistência Redis"""
import asyncio
import json
from typing import Optional, Tuple
from datetime import datetime


class PersistentRSI:
    """
    RSI incremental com persistência de estado em Redis.
    
    Características:
    - Cálculo O(1) por tick (não recalcula histórico)
    - Estado preservado em Redis (sobrevive a reinicializações)
    - Async/await compatível
    - Wilder's smoothing correto
    
    Attributes:
        symbol: Par de trading (ex: EURUSD)
        period: Período RSI (default 14)
        redis_client: Cliente Redis async
        last_price: Último preço processado
        avg_gain: Média de ganhos (Wilder smoothing)
        avg_loss: Média de perdas (Wilder smoothing)
        rsi: Valor RSI atual
    """
    
    def __init__(self, symbol: str, period: int = 14, redis_client=None):
        self.symbol = symbol.upper()
        self.period = period
        self.redis = redis_client
        
        # Estado volátil (carregado de Redis)
        self.last_price: Optional[float] = None
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self.rsi: Optional[float] = None
        
        # Chave única no Redis
        self._redis_key = f"rsi_state:{self.symbol}:{self.period}"
        self._lock = asyncio.Lock()
        
    async def load_state(self) -> bool:
        """
        Carregar estado persistido do Redis.
        
        Returns:
            True se estado foi carregado, False se iniciando do zero
        """
        if not self.redis:
            return False
            
        try:
            data = await self.redis.get(self._redis_key)
            if data:
                state = json.loads(data)
                async with self._lock:
                    self.last_price = state.get("last_price")
                    self.avg_gain = state.get("avg_gain")
                    self.avg_loss = state.get("avg_loss")
                    self.rsi = state.get("rsi")
                return True
        except Exception as e:
            # Log erro mas não quebra - inicia do zero
            print(f"[PersistentRSI] Erro ao carregar estado {self.symbol}: {e}")
            
        return False
    
    async def save_state(self) -> bool:
        """
        Persistir estado atual no Redis.
        
        Returns:
            True se salvou com sucesso
        """
        if not self.redis:
            return False
            
        try:
            state = {
                "last_price": self.last_price,
                "avg_gain": self.avg_gain,
                "avg_loss": self.avg_loss,
                "rsi": self.rsi,
                "updated_at": datetime.utcnow().isoformat()
            }
            await self.redis.set(self._redis_key, json.dumps(state))
            return True
        except Exception as e:
            print(f"[PersistentRSI] Erro ao salvar estado {self.symbol}: {e}")
            return False
    
    async def update(self, price: float) -> Tuple[Optional[float], float]:
        """
        Atualizar RSI com novo preço.
        
        Args:
            price: Preço atual do ativo
            
        Returns:
            Tuple (RSI_value, confidence)
            - RSI_value: None se insuficiente dados, else 0-100
            - confidence: 0.0 a 1.0 (distância de 50)
        """
        async with self._lock:
            # Primeiro tick - apenas armazena
            if self.last_price is None:
                self.last_price = price
                await self.save_state()
                return None, 0.0
            
            # Calcular delta
            delta = price - self.last_price
            gain = max(delta, 0)
            loss = max(-delta, 0)
            
            # Inicialização (primeiros N períodos)
            if self.avg_gain is None:
                # Primeiro cálculo - inicializa
                self.avg_gain = gain
                self.avg_loss = loss
                # Precisa de mais dados para RSI válido
                self.last_price = price
                await self.save_state()
                return None, 0.0
            
            # Wilder's smoothing (média móvel exponencial)
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
            
            # Calcular RSI
            if self.avg_loss == 0:
                self.rsi = 100.0
            else:
                rs = self.avg_gain / self.avg_loss
                self.rsi = 100 - (100 / (1 + rs))
            
            self.last_price = price
            
            # Calcular confiança (distância de 50)
            confidence = abs(self.rsi - 50) / 50.0
            
        # Salvar estado (fora do lock para não bloquear)
        await self.save_state()
        
        return self.rsi, confidence
    
    async def reset(self):
        """Resetar estado do indicador."""
        async with self._lock:
            self.last_price = None
            self.avg_gain = None
            self.avg_loss = None
            self.rsi = None
        
        if self.redis:
            await self.redis.delete(self._redis_key)
    
    def get_signal_direction(self, oversold: float = 30, overbought: float = 70) -> str:
        """
        Determinar direção do sinal baseado em níveis.
        
        Returns:
            'buy', 'sell', ou 'hold'
        """
        if self.rsi is None:
            return 'hold'
        
        if self.rsi < oversold:
            return 'buy'
        elif self.rsi > overbought:
            return 'sell'
        return 'hold'
    
    @property
    def is_ready(self) -> bool:
        """Indicador tem dados suficientes para emitir sinais."""
        return self.rsi is not None
