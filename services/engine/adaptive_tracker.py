"""Adaptive Performance Tracker - Ajuste dinâmico de pesos por ativo"""
import asyncio
import json
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


@dataclass
class AssetPerformance:
    """Performance histórica de um ativo"""
    symbol: str
    timeframe: str
    
    # Histórico de trades (janela deslizante)
    wins: int = 0
    losses: int = 0
    total_trades: int = 0
    
    # Por indicador
    indicator_performance: Dict[str, Dict] = field(default_factory=dict)
    
    # Timestamp última atualização
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def winrate(self) -> float:
        """Taxa de acerto (0.0 a 1.0)"""
        if self.total_trades == 0:
            return 0.5  # Neutro
        return self.wins / self.total_trades
    
    @property
    def is_profitable(self) -> bool:
        """Ativo está performando acima de 50%"""
        return self.winrate > 0.55  # Threshold de lucratividade
    
    def record_trade(self, won: bool, indicator_signals: Dict[str, bool]):
        """Registrar resultado de um trade."""
        self.total_trades += 1
        if won:
            self.wins += 1
        else:
            self.losses += 1
        
        # Atualizar performance por indicador
        for indicator_name, participated in indicator_signals.items():
            if indicator_name not in self.indicator_performance:
                self.indicator_performance[indicator_name] = {
                    'wins': 0, 'losses': 0, 'total': 0
                }
            
            self.indicator_performance[indicator_name]['total'] += 1
            if won and participated:
                self.indicator_performance[indicator_name]['wins'] += 1
            elif participated:
                self.indicator_performance[indicator_name]['losses'] += 1
        
        self.last_updated = datetime.utcnow()
    
    def get_indicator_winrate(self, indicator_name: str) -> float:
        """Winrate de um indicador específico."""
        perf = self.indicator_performance.get(indicator_name, {})
        total = perf.get('total', 0)
        if total == 0:
            return 0.5
        return perf.get('wins', 0) / total


class AdaptivePerformanceTracker:
    """
    Sistema adaptativo que ajusta pesos dinamicamente baseado em performance.
    
    Features:
    - Tracking de winrate por ativo/timeframe
    - Ajuste dinâmico de pesos de indicadores
    - Desativação automática de indicadores com baixa performance
    - Persistência em Redis
    
    Estratégia de adaptação:
    - Indicador com winrate < 40%: peso reduzido em 50%
    - Indicador com winrate > 60%: peso aumentado em 25%
    - Ativo com winrate < 45%: threshold aumentado em 0.1
    - Ativo com winrate > 55%: threshold reduzido em 0.05
    """
    
    def __init__(
        self,
        redis_client=None,
        min_trades_for_adjustment: int = 10,
        lookback_trades: int = 50,
        adjustment_factor: float = 0.25
    ):
        self.redis = redis_client
        self.min_trades = min_trades_for_adjustment
        self.lookback = lookback_trades
        self.adjustment_factor = adjustment_factor
        
        # Cache local de performances
        self._performances: Dict[str, AssetPerformance] = {}
        self._lock = asyncio.Lock()
        
        # Pesos base
        self._base_weights = {
            'rsi': 1.0,
            'macd': 1.0,
            'bollinger': 0.9,
            'sma': 0.9,
            'ema': 0.9,
            'stochastic': 0.85,
            'adx': 0.8,
        }
    
    def _get_key(self, symbol: str, timeframe: str) -> str:
        """Gerar chave única para ativo/timeframe."""
        return f"{symbol.upper()}:{timeframe}"
    
    def _get_redis_key(self, symbol: str, timeframe: str) -> str:
        """Gerar chave Redis."""
        return f"perf:{symbol.upper()}:{timeframe}"
    
    async def load_performance(self, symbol: str, timeframe: str) -> AssetPerformance:
        """Carregar performance de um ativo."""
        key = self._get_key(symbol, timeframe)
        
        async with self._lock:
            if key in self._performances:
                return self._performances[key]
        
        # Tentar carregar do Redis
        if self.redis:
            try:
                data = await self.redis.get(self._get_redis_key(symbol, timeframe))
                if data:
                    perf_dict = json.loads(data)
                    perf = AssetPerformance(
                        symbol=symbol.upper(),
                        timeframe=timeframe,
                        wins=perf_dict.get('wins', 0),
                        losses=perf_dict.get('losses', 0),
                        total_trades=perf_dict.get('total_trades', 0),
                        indicator_performance=perf_dict.get('indicator_performance', {}),
                        last_updated=datetime.fromisoformat(perf_dict.get('last_updated', datetime.utcnow().isoformat()))
                    )
                    
                    async with self._lock:
                        self._performances[key] = perf
                    
                    return perf
            except Exception as e:
                print(f"[AdaptiveTracker] Erro ao carregar {key}: {e}")
        
        # Criar novo se não existir
        perf = AssetPerformance(symbol=symbol.upper(), timeframe=timeframe)
        
        async with self._lock:
            self._performances[key] = perf
        
        return perf
    
    async def save_performance(self, symbol: str, timeframe: str):
        """Salvar performance no Redis."""
        key = self._get_key(symbol, timeframe)
        
        async with self._lock:
            perf = self._performances.get(key)
            if not perf:
                return
            
            if self.redis:
                try:
                    data = {
                        'symbol': perf.symbol,
                        'timeframe': perf.timeframe,
                        'wins': perf.wins,
                        'losses': perf.losses,
                        'total_trades': perf.total_trades,
                        'indicator_performance': perf.indicator_performance,
                        'last_updated': perf.last_updated.isoformat()
                    }
                    await self.redis.set(
                        self._get_redis_key(symbol, timeframe),
                        json.dumps(data)
                    )
                except Exception as e:
                    print(f"[AdaptiveTracker] Erro ao salvar {key}: {e}")
    
    async def record_trade_result(
        self,
        symbol: str,
        timeframe: str,
        won: bool,
        indicator_signals: Optional[Dict[str, bool]] = None
    ):
        """
        Registrar resultado de um trade.
        
        Args:
            symbol: Par de trading
            timeframe: Timeframe do trade
            won: True se ganhou, False se perdeu
            indicator_signals: Dict {indicator_name: bool} participação
        """
        perf = await self.load_performance(symbol, timeframe)
        
        perf.record_trade(won, indicator_signals or {})
        
        # Salvar
        await self.save_performance(symbol, timeframe)
    
    async def get_adjusted_weights(
        self,
        symbol: str,
        timeframe: str,
        indicators: List[str]
    ) -> Tuple[Dict[str, float], float]:
        """
        Obter pesos ajustados e threshold recomendado.
        
        Returns:
            (weights_dict, recommended_threshold)
        """
        perf = await self.load_performance(symbol, timeframe)
        
        # Copiar pesos base
        weights = dict(self._base_weights)
        
        # Ajustar baseado em performance
        for indicator in indicators:
            if indicator not in weights:
                weights[indicator] = 1.0
            
            indicator_wr = perf.get_indicator_winrate(indicator)
            
            if perf.total_trades >= self.min_trades:
                # Ajustar peso baseado em winrate
                if indicator_wr < 0.40:
                    # Performance ruim - reduzir peso
                    weights[indicator] *= (1 - self.adjustment_factor)
                elif indicator_wr > 0.60:
                    # Performance boa - aumentar peso
                    weights[indicator] *= (1 + self.adjustment_factor * 0.5)
        
        # Calcular threshold recomendado
        base_threshold = 0.65
        
        if perf.total_trades >= self.min_trades:
            if perf.winrate < 0.45:
                # Performance ruil - aumentar threshold (mais conservador)
                recommended_threshold = base_threshold + 0.10
            elif perf.winrate > 0.55:
                # Performance boa - reduzir threshold (mais agressivo)
                recommended_threshold = base_threshold - 0.05
            else:
                recommended_threshold = base_threshold
        else:
            # Dados insuficientes - usar threshold base
            recommended_threshold = base_threshold
        
        # Clamp threshold
        recommended_threshold = max(0.50, min(0.80, recommended_threshold))
        
        return weights, recommended_threshold
    
    async def should_disable_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator: str,
        min_trades: int = 15
    ) -> bool:
        """
        Verificar se um indicador deve ser desativado.
        
        Returns:
            True se winrate < 35% após min_trades
        """
        perf = await self.load_performance(symbol, timeframe)
        
        ind_perf = perf.indicator_performance.get(indicator, {})
        total = ind_perf.get('total', 0)
        
        if total < min_trades:
            return False
        
        wins = ind_perf.get('wins', 0)
        winrate = wins / total
        
        return winrate < 0.35
    
    async def get_performance_report(self, symbol: str, timeframe: str) -> Dict:
        """Gerar relatório de performance."""
        perf = await self.load_performance(symbol, timeframe)
        
        weights, threshold = await self.get_adjusted_weights(
            symbol, timeframe, list(perf.indicator_performance.keys())
        )
        
        return {
            'symbol': perf.symbol,
            'timeframe': perf.timeframe,
            'winrate': perf.winrate,
            'total_trades': perf.total_trades,
            'wins': perf.wins,
            'losses': perf.losses,
            'is_profitable': perf.is_profitable,
            'indicator_winrates': {
                name: perf.get_indicator_winrate(name)
                for name in perf.indicator_performance.keys()
            },
            'adjusted_weights': weights,
            'recommended_threshold': threshold,
            'disabled_indicators': [
                ind for ind in perf.indicator_performance.keys()
                if await self.should_disable_indicator(symbol, timeframe, ind)
            ]
        }
    
    async def reset_performance(self, symbol: str, timeframe: str):
        """Resetar performance de um ativo."""
        key = self._get_key(symbol, timeframe)
        
        async with self._lock:
            if key in self._performances:
                del self._performances[key]
        
        if self.redis:
            await self.redis.delete(self._get_redis_key(symbol, timeframe))
