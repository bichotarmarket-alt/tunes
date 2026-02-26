"""
Trading Engine - Sistema HFT Async com indicadores incrementais e confluência categorizada

Módulos:
- persistent_rsi: RSI incremental stateful com persistência Redis
- persistent_ema: EMA incremental stateful
- persistent_atr: ATR incremental stateful
- persistent_macd: MACD incremental stateful
- confluence_categorized: Motor de confluência com agrupamento estatístico
- async_asset_processor: Processador de ativo com estado persistente
- async_trading_engine: Motor principal com fila de sinais desacoplada
- adaptive_tracker: Sistema adaptativo por ativo/timeframe
- hft_integration: Ponte de integração com sistema legado

Exemplo de uso:
    import asyncio
    from services.engine import AsyncTradingEngine
    
    async def main():
        engine = AsyncTradingEngine(
            redis_host='localhost',
            num_workers=2,
            signal_threshold=0.65
        )
        
        await engine.initialize()
        
        # Simular ticks
        await engine.on_price_update('EURUSD', 1.0850)
        await engine.on_price_update('EURUSD', 1.0855)
        
        # Stats
        stats = await engine.get_stats()
        print(stats)
        
        await engine.shutdown()
    
    asyncio.run(main())
"""

from .persistent_rsi import PersistentRSI
from .persistent_ema import PersistentEMA
from .persistent_atr import PersistentATR
from .persistent_macd import PersistentMACD
from .confluence_categorized import (
    ConfluenceCalculatorCategorized,
    IndicatorSignal,
    SignalDirection,
    IndicatorCategory,
    ConfluenceResult
)
from .circuit_breaker import CircuitBreaker, MultiAssetCircuitBreaker, CircuitBreakerState
from .async_asset_processor import AsyncAssetProcessor, Signal
from .async_asset_processor_v2 import AsyncAssetProcessorV2
from .async_trading_engine import AsyncTradingEngine, TradeOrder
from .adaptive_tracker import AdaptivePerformanceTracker, AssetPerformance
from .hft_execution_bridge import (
    HFTExecutionBridge,
    ExecutionSignal,
    Order,
    OrderStatus,
    ExecutionSide,
    ExecutionMetrics,
    get_execution_bridge,
    set_execution_bridge
)
from .hft_integration import (
    HFTIntegration,
    HFTComparisonResult,
    get_hft_integration,
    set_hft_integration
)

__all__ = [
    # Indicadores
    'PersistentRSI',
    'PersistentEMA',
    'PersistentATR',
    'PersistentMACD',
    
    # Confluência
    'ConfluenceCalculatorCategorized',
    'IndicatorSignal',
    'SignalDirection',
    'IndicatorCategory',
    'ConfluenceResult',
    
    # Circuit Breaker
    'CircuitBreaker',
    'MultiAssetCircuitBreaker',
    'CircuitBreakerState',
    
    # Execution Bridge
    'HFTExecutionBridge',
    'ExecutionSignal',
    'Order',
    'OrderStatus',
    'ExecutionSide',
    'ExecutionMetrics',
    'get_execution_bridge',
    'set_execution_bridge',
    
    # Processadores
    'AsyncAssetProcessor',
    'AsyncAssetProcessorV2',
    'Signal',
    
    # Engine
    'AsyncTradingEngine',
    'TradeOrder',
    
    # Adaptativo
    'AdaptivePerformanceTracker',
    'AssetPerformance',
    
    # Integração
    'HFTIntegration',
    'HFTComparisonResult',
    'get_hft_integration',
    'set_hft_integration',
]

__version__ = '1.0.0'
