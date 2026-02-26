"""
Circuit Breaker - Sistema de proteção contra mercados laterais (ranging)

Implementa veto estatístico: quando ATR < threshold por N ticks consecutivos,
o score de confluência é zerado independente dos indicadores.

Características:
- Threshold configurável por ativo
- Contador de ticks consecutivos com baixa volatilidade
- Estado persistente em Redis
- Logs de auditoria para ticks bloqueados
- Reativação automática quando volatilidade retorna
"""

import asyncio
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CircuitBreakerState:
    """Estado do circuit breaker para persistência"""
    low_vol_count: int = 0
    is_active: bool = True  # True = permissivo, False = bloqueio
    last_atr: Optional[float] = None
    blocked_ticks: int = 0
    total_checks: int = 0
    last_block_time: Optional[str] = None
    asset: str = ""


class CircuitBreaker:
    """
    Circuit Breaker para proteção contra mercados laterais.
    
    Lógica:
    1. Monitora ATR (volatilidade)
    2. Se ATR < threshold por min_ticks consecutivos → ativa bloqueio
    3. Quando ATR volta ao normal → desativa bloqueio
    4. Persiste estado no Redis para sobreviver restart
    
    Args:
        symbol: Par de trading (ex: EURUSD_otc)
        atr_threshold: Threshold de ATR para considerar mercado lateral
        min_ticks: Número mínimo de ticks consecutivos com ATR baixo para bloquear
        redis_client: Cliente Redis para persistência
    """
    
    def __init__(
        self,
        symbol: str,
        atr_threshold: float = 0.0005,  # 0.05% para forex
        min_ticks: int = 5,
        redis_client=None
    ):
        self.symbol = symbol.upper()
        self.atr_threshold = atr_threshold
        self.min_ticks = min_ticks
        self.redis = redis_client
        
        # Estado
        self._state = CircuitBreakerState(asset=self.symbol)
        self._lock = asyncio.Lock()
        
        # Chave Redis
        self._redis_key = f"circuit_breaker:{self.symbol}"
    
    async def load_state(self) -> bool:
        """Carregar estado persistido do Redis."""
        if not self.redis:
            return False
        
        try:
            data = await self.redis.get(self._redis_key)
            if data:
                state_dict = json.loads(data)
                async with self._lock:
                    self._state.low_vol_count = state_dict.get('low_vol_count', 0)
                    self._state.is_active = state_dict.get('is_active', True)
                    self._state.blocked_ticks = state_dict.get('blocked_ticks', 0)
                    self._state.total_checks = state_dict.get('total_checks', 0)
                    self._state.last_block_time = state_dict.get('last_block_time')
                return True
        except Exception as e:
            print(f"[CircuitBreaker] Erro ao carregar estado {self.symbol}: {e}")
        
        return False
    
    async def save_state(self) -> bool:
        """Persistir estado no Redis."""
        if not self.redis:
            return False
        
        try:
            state_dict = {
                'low_vol_count': self._state.low_vol_count,
                'is_active': self._state.is_active,
                'last_atr': self._state.last_atr,
                'blocked_ticks': self._state.blocked_ticks,
                'total_checks': self._state.total_checks,
                'last_block_time': self._state.last_block_time,
                'asset': self.symbol,
                'updated_at': datetime.utcnow().isoformat()
            }
            await self.redis.set(self._redis_key, json.dumps(state_dict))
            return True
        except Exception as e:
            print(f"[CircuitBreaker] Erro ao salvar estado {self.symbol}: {e}")
            return False
    
    async def check(self, atr_value: Optional[float]) -> bool:
        """
        Verificar se circuit breaker permite operação.
        
        Args:
            atr_value: Valor atual do ATR (None se não disponível)
            
        Returns:
            True: Permissivo (pode operar)
            False: Bloqueado (mercado lateral)
        """
        async with self._lock:
            self._state.total_checks += 1
            self._state.last_atr = atr_value
            
            # Se não temos ATR, assumir permissivo (fallback seguro)
            if atr_value is None:
                self._state.low_vol_count = max(0, self._state.low_vol_count - 1)
                was_blocked = not self._state.is_active
                self._state.is_active = True
                
                if was_blocked:
                    print(f"[CircuitBreaker] {self.symbol}: DESBLOQUEADO (ATR indisponível)")
                
                await self.save_state()
                return True
            
            # Verificar volatilidade
            if atr_value < self.atr_threshold:
                self._state.low_vol_count += 1
                
                # Verificar se deve bloquear
                if self._state.low_vol_count >= self.min_ticks:
                    was_active = self._state.is_active
                    self._state.is_active = False
                    self._state.blocked_ticks += 1
                    
                    if was_active:
                        self._state.last_block_time = datetime.utcnow().isoformat()
                        print(f"[CircuitBreaker] 🚫 {self.symbol}: BLOQUEADO! "
                              f"ATR={atr_value:.6f} < {self.atr_threshold:.6f} "
                              f"({self._state.low_vol_count} ticks)")
                
                await self.save_state()
                return self._state.is_active
            
            else:
                # Volatilidade normal - resetar contador
                was_blocked = not self._state.is_active
                self._state.low_vol_count = 0
                self._state.is_active = True
                
                if was_blocked:
                    print(f"[CircuitBreaker] ✅ {self.symbol}: DESBLOQUEADO! "
                          f"ATR={atr_value:.6f} >= {self.atr_threshold:.6f}")
                
                await self.save_state()
                return True
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obter estatísticas do circuit breaker."""
        async with self._lock:
            return {
                'symbol': self.symbol,
                'is_active': self._state.is_active,
                'low_vol_count': self._state.low_vol_count,
                'atr_threshold': self.atr_threshold,
                'min_ticks': self.min_ticks,
                'blocked_ticks': self._state.blocked_ticks,
                'total_checks': self._state.total_checks,
                'block_rate': (self._state.blocked_ticks / max(1, self._state.total_checks)),
                'last_atr': self._state.last_atr,
                'last_block_time': self._state.last_block_time
            }
    
    async def force_open(self):
        """Forçar abertura do circuit (manual override)."""
        async with self._lock:
            was_blocked = not self._state.is_active
            self._state.is_active = True
            self._state.low_vol_count = 0
            
            if was_blocked:
                print(f"[CircuitBreaker] 🔓 {self.symbol}: FORÇADO ABERTO (manual)")
            
            await self.save_state()
    
    async def force_close(self, reason: str = "manual"):
        """Forçar fechamento do circuit (manual override)."""
        async with self._lock:
            was_active = self._state.is_active
            self._state.is_active = False
            self._state.last_block_time = datetime.utcnow().isoformat()
            
            if was_active:
                print(f"[CircuitBreaker] 🔒 {self.symbol}: FORÇADO FECHADO ({reason})")
            
            await self.save_state()
    
    async def reset(self):
        """Resetar estado do circuit breaker."""
        async with self._lock:
            self._state = CircuitBreakerState(asset=self.symbol)
            
            if self.redis:
                await self.redis.delete(self._redis_key)
    
    @property
    def is_blocked(self) -> bool:
        """Verificar se está bloqueado (sem async)."""
        return not self._state.is_active
    
    @property
    def is_open(self) -> bool:
        """Verificar se está aberto/permissivo (sem async)."""
        return self._state.is_active


class MultiAssetCircuitBreaker:
    """
    Gerenciador de Circuit Breakers para múltiplos ativos.
    Permite configurações diferentes por ativo.
    """
    
    def __init__(self, redis_client=None, default_config: Optional[Dict] = None):
        self.redis = redis_client
        self.default_config = default_config or {
            'atr_threshold': 0.0005,
            'min_ticks': 5
        }
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._configs: Dict[str, Dict] = {}
    
    def set_config(self, symbol: str, atr_threshold: float, min_ticks: int):
        """Configurar threshold específico para um ativo."""
        self._configs[symbol.upper()] = {
            'atr_threshold': atr_threshold,
            'min_ticks': min_ticks
        }
    
    async def get_breaker(self, symbol: str) -> CircuitBreaker:
        """Obter ou criar circuit breaker para um ativo."""
        symbol = symbol.upper()
        
        if symbol not in self._breakers:
            # Usar config específica ou default
            config = self._configs.get(symbol, self.default_config)
            
            self._breakers[symbol] = CircuitBreaker(
                symbol=symbol,
                atr_threshold=config['atr_threshold'],
                min_ticks=config['min_ticks'],
                redis_client=self.redis
            )
            
            # Carregar estado persistido
            await self._breakers[symbol].load_state()
        
        return self._breakers[symbol]
    
    async def check(self, symbol: str, atr_value: Optional[float]) -> bool:
        """Verificar se ativo pode operar."""
        breaker = await self.get_breaker(symbol)
        return await breaker.check(atr_value)
    
    async def get_all_stats(self) -> Dict[str, Dict]:
        """Obter estatísticas de todos os breakers."""
        stats = {}
        for symbol, breaker in self._breakers.items():
            stats[symbol] = await breaker.get_stats()
        return stats
    
    async def force_open_all(self):
        """Forçar abertura de todos os circuit breakers."""
        for breaker in self._breakers.values():
            await breaker.force_open()
    
    async def reset_all(self):
        """Resetar todos os circuit breakers."""
        for breaker in self._breakers.values():
            await breaker.reset()
        self._breakers.clear()
