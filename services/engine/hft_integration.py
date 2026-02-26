"""HFT Integration Bridge - Integração entre sistema legado e novo engine HFT

Esta ponte permite:
1. Rodar sistema legado e novo engine em paralelo
2. Ativar modo HFT por ativo individualmente
3. Comparar performance entre os dois sistemas
4. Migrar gradualmente sem risco

Uso:
    from services.engine.hft_integration import HFTIntegration
    
    # Inicializar integração no DataCollectorService
    self.hft_bridge = HFTIntegration(
        redis_host='localhost',
        signal_threshold=0.65,
        enabled_assets=['EURUSD_otc', 'GBPUSD_otc']  # Apenas estes usam HFT
    )
    await self.hft_bridge.initialize()
    
    # No handler de ticks, enviar para ambos sistemas
    await self._add_tick_to_buffer(...)  # Sistema legado
    await self.hft_bridge.on_tick(symbol, price)  # Novo sistema HFT
"""
import asyncio
import time
from typing import Dict, Optional, List, Callable, Any, Set
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from .async_trading_engine import AsyncTradingEngine
from .adaptive_tracker import AdaptivePerformanceTracker
from .async_asset_processor import Signal


@dataclass
class HFTComparisonResult:
    """Resultado de comparação entre sistemas"""
    symbol: str
    legacy_signal: Optional[Dict] = None
    hft_signal: Optional[Signal] = None
    latency_legacy_ms: float = 0.0
    latency_hft_ms: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class HFTIntegration:
    """
    Ponte de integração entre sistema legado e novo engine HFT.
    
    Permite ativação gradual do modo HFT por ativo,
    mantendo sistema legado como fallback.
    """
    
    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        signal_threshold: float = 0.65,
        enabled_assets: Optional[List[str]] = None,
        enable_adaptive: bool = True,
        comparison_mode: bool = False
    ):
        """
        Args:
            redis_host: Host do Redis para persistência
            redis_port: Porta do Redis
            signal_threshold: Threshold mínimo para emitir sinal
            enabled_assets: Lista de ativos que usam modo HFT (None = todos)
            enable_adaptive: Ativar sistema adaptativo de pesos
            comparison_mode: Registrar comparações entre sistemas
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.signal_threshold = signal_threshold
        self.enabled_assets: Set[str] = set(a.upper() for a in (enabled_assets or []))
        self.enable_adaptive = enable_adaptive
        self.comparison_mode = comparison_mode
        
        # Engine HFT
        self.engine: Optional[AsyncTradingEngine] = None
        self.adaptive_tracker: Optional[AdaptivePerformanceTracker] = None
        
        # Callbacks
        self._signal_callbacks: List[Callable[[Signal], Any]] = []
        self._comparison_callbacks: List[Callable[[HFTComparisonResult], Any]] = []
        
        # Métricas
        self._metrics: Dict[str, Dict] = {}
        self._comparison_results: List[HFTComparisonResult] = []
        self._lock = asyncio.Lock()
        
        self._is_initialized = False
    
    async def initialize(self):
        """Inicializar integração e engine HFT."""
        if self._is_initialized:
            return
        
        logger.info("[HFTIntegration] Inicializando ponte HFT...")
        
        # Inicializar engine
        self.engine = AsyncTradingEngine(
            redis_host=self.redis_host,
            redis_port=self.redis_port,
            num_workers=2,
            signal_threshold=self.signal_threshold
        )
        
        # Registrar callback de sinais
        self.engine.on_signal(self._on_hft_signal)
        self.engine.on_error(self._on_hft_error)
        
        await self.engine.initialize()
        
        # Inicializar adaptive tracker se habilitado
        if self.enable_adaptive:
            self.adaptive_tracker = AdaptivePerformanceTracker(
                redis_client=self.engine.redis_client if self.engine else None
            )
        
        self._is_initialized = True
        
        logger.success(
            f"[HFTIntegration] Ponte HFT inicializada | "
            f"Ativos HFT: {len(self.enabled_assets)} | "
            f"Adaptive: {self.enable_adaptive} | "
            f"Comparison: {self.comparison_mode}"
        )
    
    async def shutdown(self):
        """Desligar integração."""
        if not self._is_initialized:
            return
        
        logger.info("[HFTIntegration] Desligando ponte HFT...")
        
        if self.engine:
            await self.engine.shutdown()
        
        self._is_initialized = False
        logger.success("[HFTIntegration] Ponte HFT desligada")
    
    def enable_asset(self, symbol: str):
        """Habilitar modo HFT para um ativo."""
        self.enabled_assets.add(symbol.upper())
        logger.info(f"[HFTIntegration] Modo HFT habilitado para {symbol}")
    
    def disable_asset(self, symbol: str):
        """Desabilitar modo HFT para um ativo."""
        self.enabled_assets.discard(symbol.upper())
        logger.info(f"[HFTIntegration] Modo HFT desabilitado para {symbol}")
    
    def is_hft_enabled(self, symbol: str) -> bool:
        """Verificar se HFT está habilitado para um ativo."""
        if not self.enabled_assets:
            return True  # Todos habilitados se lista vazia
        return symbol.upper() in self.enabled_assets
    
    async def on_tick(self, symbol: str, price: float, timestamp: Optional[float] = None):
        """
        Processar tick no sistema HFT.
        
        Esta função deve ser chamada junto com o sistema legado
        para alimentar o engine HFT.
        
        Args:
            symbol: Par de trading
            price: Preço atual
            timestamp: Timestamp do tick (opcional)
        """
        if not self._is_initialized or not self.engine:
            return
        
        # Verificar se HFT está habilitado para este ativo
        if not self.is_hft_enabled(symbol):
            return
        
        # Enviar para engine HFT
        await self.engine.on_price_update(symbol, price)
    
    def _on_hft_signal(self, signal: Signal):
        """Handler interno para sinais HFT."""
        # Registrar métricas
        symbol = signal.symbol
        
        async def update_metrics():
            async with self._lock:
                if symbol not in self._metrics:
                    self._metrics[symbol] = {
                        'signals_count': 0,
                        'last_signal': None,
                        'avg_score': 0.0
                    }
                
                self._metrics[symbol]['signals_count'] += 1
                self._metrics[symbol]['last_signal'] = datetime.utcnow().isoformat()
                
                # Atualizar média móvel do score
                prev_avg = self._metrics[symbol]['avg_score']
                count = self._metrics[symbol]['signals_count']
                self._metrics[symbol]['avg_score'] = (prev_avg * (count - 1) + signal.score) / count
        
        # Criar task para não bloquear
        asyncio.create_task(update_metrics())
        
        # Notificar callbacks externos
        for callback in self._signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(signal))
                else:
                    callback(signal)
            except Exception as e:
                logger.error(f"[HFTIntegration] Erro em callback de sinal: {e}")
    
    def _on_hft_error(self, error: Exception, signal: Signal):
        """Handler interno para erros HFT."""
        logger.error(f"[HFTIntegration] Erro no processamento HFT: {error}")
    
    async def on_legacy_signal(
        self,
        symbol: str,
        signal_data: Dict,
        latency_ms: float = 0.0
    ):
        """
        Registrar sinal do sistema legado para comparação.
        
        Args:
            symbol: Par de trading
            signal_data: Dados do sinal do sistema legado
            latency_ms: Latência de processamento em ms
        """
        if not self.comparison_mode:
            return
        
        # Registrar para comparação
        result = HFTComparisonResult(
            symbol=symbol,
            legacy_signal=signal_data,
            latency_legacy_ms=latency_ms
        )
        
        async with self._lock:
            self._comparison_results.append(result)
            # Manter apenas últimos 1000 resultados
            if len(self._comparison_results) > 1000:
                self._comparison_results.pop(0)
        
        # Notificar callbacks
        for callback in self._comparison_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(result))
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"[HFTIntegration] Erro em callback de comparação: {e}")
    
    async def record_trade_result(
        self,
        symbol: str,
        timeframe: str,
        won: bool,
        system: str = 'hft',  # 'hft' ou 'legacy'
        indicator_signals: Optional[Dict[str, bool]] = None
    ):
        """
        Registrar resultado de trade para tracking adaptativo.
        
        Args:
            symbol: Par de trading
            timeframe: Timeframe do trade
            won: True se ganhou, False se perdeu
            system: Qual sistema gerou o sinal ('hft' ou 'legacy')
            indicator_signals: Participação de cada indicador
        """
        if not self.enable_adaptive or not self.adaptive_tracker:
            return
        
        await self.adaptive_tracker.record_trade_result(
            symbol=symbol,
            timefram=timeframe,
            won=won,
            indicator_signals=indicator_signals or {}
        )
        
        # Log
        action = "✅ WIN" if won else "❌ LOSS"
        logger.info(f"[HFTIntegration] [{system.upper()}] {action} em {symbol} {timeframe}")
    
    def on_hft_signal(self, callback: Callable[[Signal], Any]):
        """Registrar callback para sinais HFT."""
        self._signal_callbacks.append(callback)
    
    def on_comparison(self, callback: Callable[[HFTComparisonResult], Any]):
        """Registrar callback para resultados de comparação."""
        self._comparison_callbacks.append(callback)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Obter métricas da integração."""
        engine_stats = await self.engine.get_stats() if self.engine else {}
        
        async with self._lock:
            metrics = dict(self._metrics)
            comparisons = len(self._comparison_results)
        
        return {
            'hft_enabled_assets': list(self.enabled_assets),
            'engine_stats': engine_stats,
            'asset_metrics': metrics,
            'comparison_results_stored': comparisons,
            'comparison_mode': self.comparison_mode,
            'adaptive_enabled': self.enable_adaptive
        }
    
    async def get_asset_performance(self, symbol: str, timeframe: str = 'M1') -> Optional[Dict]:
        """Obter relatório de performance para um ativo."""
        if not self.enable_adaptive or not self.adaptive_tracker:
            return None
        
        return await self.adaptive_tracker.get_performance_report(symbol, timeframe)
    
    async def get_comparison_report(self, n_recent: int = 100) -> Dict[str, Any]:
        """Gerar relatório de comparação entre sistemas."""
        if not self.comparison_mode:
            return {'error': 'Comparison mode not enabled'}
        
        async with self._lock:
            results = self._comparison_results[-n_recent:]
        
        if not results:
            return {'message': 'No comparison data yet'}
        
        # Agrupar por ativo
        by_asset: Dict[str, List[HFTComparisonResult]] = {}
        for r in results:
            if r.symbol not in by_asset:
                by_asset[r.symbol] = []
            by_asset[r.symbol].append(r)
        
        # Calcular estatísticas
        stats = {
            'total_comparisons': len(results),
            'by_asset': {
                symbol: {
                    'count': len(comps),
                    'avg_latency_legacy_ms': sum(c.latency_legacy_ms for c in comps) / len(comps),
                    'signals_legacy': sum(1 for c in comps if c.legacy_signal is not None),
                    'signals_hft': sum(1 for c in comps if c.hft_signal is not None)
                }
                for symbol, comps in by_asset.items()
            }
        }
        
        return stats


# Singleton para acesso global
_hft_integration_instance: Optional[HFTIntegration] = None


def get_hft_integration() -> Optional[HFTIntegration]:
    """Obter instância global da integração HFT."""
    return _hft_integration_instance


def set_hft_integration(instance: HFTIntegration):
    """Definir instância global da integração HFT."""
    global _hft_integration_instance
    _hft_integration_instance = instance
