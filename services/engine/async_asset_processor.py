"""Async Asset Processor - Processamento de ticks por ativo com estado persistente"""
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

from .persistent_rsi import PersistentRSI
from .persistent_ema import PersistentEMA
from .persistent_atr import PersistentATR
from .persistent_macd import PersistentMACD
from .confluence_categorized import (
    ConfluenceCalculatorCategorized, 
    IndicatorSignal, 
    SignalDirection,
    IndicatorCategory
)


@dataclass
class Signal:
    """Sinal de trading emitido"""
    symbol: str
    direction: str  # 'buy' ou 'sell'
    price: float
    score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    breakdown: Dict = field(default_factory=dict)
    indicators_used: List[str] = field(default_factory=list)


class AsyncAssetProcessor:
    """
    Processador assíncrono de ticks para um ativo específico.
    
    Responsabilidades:
    - Manter estado de indicadores incrementais
    - Calcular sinais a cada tick (O(1))
    - Emitir sinais via confluência categorizada
    - Persistir estado em Redis
    
    Attributes:
        symbol: Par de trading
        indicators: Dict de indicadores stateful
        confluence: Motor de confluência
        threshold: Score mínimo para emitir sinal
        redis_client: Cliente Redis para persistência
    """
    
    def __init__(
        self,
        symbol: str,
        redis_client=None,
        threshold: float = 0.65,
        indicators_config: Optional[Dict] = None
    ):
        self.symbol = symbol.upper()
        self.redis = redis_client
        self.threshold = threshold
        
        # Indicadores configuráveis
        config = indicators_config or {
            'rsi': {'period': 14, 'enabled': True},
            'ema': {'period': 20, 'enabled': True},
            'atr': {'period': 14, 'enabled': True},
            'macd': {'fast': 12, 'slow': 26, 'signal': 9, 'enabled': True}
        }
        
        # Inicializar indicadores stateful
        self.indicators: Dict[str, Any] = {}
        self.indicator_config = config
        
        if config.get('rsi', {}).get('enabled', True):
            self.indicators['rsi'] = PersistentRSI(
                symbol=self.symbol,
                period=config['rsi'].get('period', 14),
                redis_client=redis_client
            )
        
        if config.get('ema', {}).get('enabled', True):
            self.indicators['ema'] = PersistentEMA(
                symbol=self.symbol,
                period=config['ema'].get('period', 20),
                redis_client=redis_client
            )
        
        if config.get('atr', {}).get('enabled', True):
            self.indicators['atr'] = PersistentATR(
                symbol=self.symbol,
                period=config['atr'].get('period', 14),
                redis_client=redis_client
            )
        
        if config.get('macd', {}).get('enabled', True):
            macd_cfg = config['macd']
            self.indicators['macd'] = PersistentMACD(
                symbol=self.symbol,
                fast_period=macd_cfg.get('fast', 12),
                slow_period=macd_cfg.get('slow', 26),
                signal_period=macd_cfg.get('signal', 9),
                redis_client=redis_client
            )
        
        # TODO: Adicionar mais indicadores incrementais:
        # - PersistentMACD
        # - PersistentATR
        # - PersistentEMA
        
        # Motor de confluência
        self.confluence = ConfluenceCalculatorCategorized(
            min_confluence=threshold,
            require_trend_confirmation=False  # Pode configurar
        )
        
        # Estatísticas
        self.ticks_processed = 0
        self.signals_generated = 0
        self.last_signal_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Inicializar carregando estados persistidos."""
        load_tasks = [
            ind.load_state() 
            for ind in self.indicators.values()
        ]
        await asyncio.gather(*load_tasks, return_exceptions=True)
        
        print(f"[AsyncAssetProcessor] {self.symbol} inicializado com {len(self.indicators)} indicadores")
    
    async def process_tick(self, price: float) -> Optional[Signal]:
        """
        Processar um tick de preço.
        
        Args:
            price: Preço atual
            
        Returns:
            Signal se confluência >= threshold, else None
        """
        async with self._lock:
            self.ticks_processed += 1
        
        # Atualizar todos indicadores em paralelo
        indicator_tasks = []
        for name, indicator in self.indicators.items():
            indicator_tasks.append(self._update_indicator(name, indicator, price))
        
        results = await asyncio.gather(*indicator_tasks, return_exceptions=True)
        
        # Coletar sinais válidos
        signals: List[IndicatorSignal] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            if result is not None:
                signals.append(result)
        
        if not signals:
            return None
        
        # Calcular confluência
        confluence_result = self.confluence.calculate_confluence(signals)
        
        if not confluence_result.should_trade:
            return None
        
        # Emitir sinal
        direction_str = 'buy' if confluence_result.direction == SignalDirection.BUY else 'sell'
        
        signal = Signal(
            symbol=self.symbol,
            direction=direction_str,
            price=price,
            score=confluence_result.final_score,
            breakdown=confluence_result.breakdown,
            indicators_used=[s.name for s in signals]
        )
        
        async with self._lock:
            self.signals_generated += 1
            self.last_signal_time = datetime.utcnow()
        
        return signal
    
    async def _update_indicator(
        self, 
        name: str, 
        indicator: Any, 
        price: float
    ) -> Optional[IndicatorSignal]:
        """
        Atualizar um indicador e retornar sinal formatado.
        
        Returns:
            IndicatorSignal ou None se indicador não pronto
        """
        try:
            if name == 'rsi':
                rsi_value, confidence = await indicator.update(price)
                
                if rsi_value is None:
                    return None
                
                # Determinar direção
                direction = SignalDirection.HOLD
                if rsi_value < 30:
                    direction = SignalDirection.BUY
                elif rsi_value > 70:
                    direction = SignalDirection.SELL
                
                return IndicatorSignal(
                    name='rsi',
                    category=IndicatorCategory.MOMENTUM,
                    direction=direction,
                    confidence=confidence,
                    value=rsi_value
                )
            
            elif name == 'ema':
                ema_value, confidence = await indicator.update(price)
                
                if ema_value is None:
                    return None
                
                # Sinal baseado em cruzamento de preço com EMA
                direction_str = indicator.get_signal_direction(price)
                direction = SignalDirection.HOLD
                if direction_str == 'buy':
                    direction = SignalDirection.BUY
                elif direction_str == 'sell':
                    direction = SignalDirection.SELL
                
                return IndicatorSignal(
                    name='ema',
                    category=IndicatorCategory.TREND,
                    direction=direction,
                    confidence=confidence,
                    value=ema_value
                )
            
            elif name == 'atr':
                atr_value, confidence = await indicator.update(price)
                
                if atr_value is None:
                    return None
                
                # ATR é volatilidade, não direção
                # Mas podemos usar para modificar confiança de outros sinais
                vol_signal = indicator.get_volatility_signal()
                
                # Em alta volatilidade, reduzir confiança (mais arriscado)
                if vol_signal == 'high':
                    confidence *= 0.7
                
                return IndicatorSignal(
                    name='atr',
                    category=IndicatorCategory.VOLATILITY,
                    direction=SignalDirection.HOLD,  # ATR não tem direção
                    confidence=confidence,
                    value=atr_value
                )
            
            elif name == 'macd':
                macd_data, confidence = await indicator.update(price)
                
                if macd_data is None:
                    return None
                
                direction_str = indicator.get_signal_direction()
                direction = SignalDirection.HOLD
                if direction_str == 'buy':
                    direction = SignalDirection.BUY
                elif direction_str == 'sell':
                    direction = SignalDirection.SELL
                
                return IndicatorSignal(
                    name='macd',
                    category=IndicatorCategory.TREND,
                    direction=direction,
                    confidence=confidence,
                    value=macd_data.get('histogram') if macd_data else None
                )
            
            return None
            
        except Exception as e:
            print(f"[AsyncAssetProcessor] Erro em {name} para {self.symbol}: {e}")
            return None
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obter estatísticas do processador."""
        async with self._lock:
            return {
                'symbol': self.symbol,
                'ticks_processed': self.ticks_processed,
                'signals_generated': self.signals_generated,
                'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None,
                'indicators_count': len(self.indicators),
                'indicator_states': {
                    name: {
                        'ready': ind.is_ready,
                        'current_value': getattr(ind, 'rsi', None) if hasattr(ind, 'rsi') else None
                    }
                    for name, ind in self.indicators.items()
                }
            }
    
    async def reset(self):
        """Resetar estado do processador."""
        async with self._lock:
            self.ticks_processed = 0
            self.signals_generated = 0
            self.last_signal_time = None
        
        reset_tasks = [ind.reset() for ind in self.indicators.values()]
        await asyncio.gather(*reset_tasks, return_exceptions=True)
