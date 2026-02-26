"""
HFT Integration Module - Código Pronto para Integração no DataCollectorService

Este arquivo contém o código completo para integrar o HFT Engine ao DataCollectorService.
Copie as seções abaixo para os locais indicados no realtime.py

================================================================================
SEÇÃO 1: IMPORTS (Adicionar no topo do realtime.py)
================================================================================
"""

# HFT Engine Imports - Adicionar após os imports existentes
from services.engine import (
    AsyncAssetProcessorV2,
    HFTExecutionBridge,
    set_execution_bridge,
    get_execution_bridge,
    CircuitBreaker,
    ExecutionSignal
)


"""
================================================================================
SEÇÃO 2: INICIALIZAÇÃO NO __init__ (Adicionar no final do __init__)
================================================================================
"""

def init_hft_engine(self):
    """Inicializar HFT Engine - Adicionar ao final do __init__"""
    # HFT Components
    self.hft_enabled: bool = True  # Toggle para ativar/desativar HFT
    self.hft_symbols: List[str] = ['EURUSD_otc']  # Ativos HFT (começar com 1)
    self.hft_processors: Dict[str, AsyncAssetProcessorV2] = {}
    self.hft_execution_bridge: Optional[HFTExecutionBridge] = None
    self.hft_redis_client = None
    
    # Métricas HFT
    self.hft_metrics = {
        'ticks_processed': 0,
        'signals_generated': 0,
        'signals_blocked_by_cb': 0,
        'orders_executed': 0,
        'errors': 0
    }
    
    logger.info("[HFT] Estrutura inicializada (não ativo ainda)")


"""
================================================================================
SEÇÃO 3: MÉTODO DE START (Adicionar no final do método start())
================================================================================
"""

async def start_hft_engine(self):
    """Iniciar HFT Engine - Adicionar ao final do start()"""
    if not self.hft_enabled:
        logger.info("[HFT] Desativado pelo toggle")
        return
    
    try:
        logger.info("[HFT] 🚀 Iniciando HFT Engine...")
        
        # 1. Conectar Redis
        try:
            import redis.asyncio as aioredis
            self.hft_redis_client = await aioredis.from_url(
                "redis://localhost:6379",
                decode_responses=True
            )
            await self.hft_redis_client.ping()
            logger.info("[HFT] ✅ Redis conectado")
        except Exception as e:
            logger.warning(f"[HFT] ⚠️ Redis não disponível: {e}")
            logger.info("[HFT] Continuando sem persistência Redis")
            self.hft_redis_client = None
        
        # 2. Inicializar Execution Bridge
        self.hft_execution_bridge = HFTExecutionBridge(
            api_client=None,  # TODO: Substituir por cliente real da PocketOption
            redis_client=self.hft_redis_client,
            num_workers=2,
            max_retries=2,
            retry_backoff_base=1.0,
            enable_circuit_breaker=True,
            circuit_breaker_threshold=5
        )
        await self.hft_execution_bridge.start()
        set_execution_bridge(self.hft_execution_bridge)
        
        # Callbacks para monitoramento
        def on_order_filled(order):
            self.hft_metrics['orders_executed'] += 1
            logger.success(f"[HFT] 🎯 Ordem executada: {order.symbol} {order.side.value.upper()}")
        
        def on_order_error(order, error):
            self.hft_metrics['errors'] += 1
            logger.error(f"[HFT] ❌ Erro na ordem {order.symbol}: {error}")
        
        self.hft_execution_bridge.set_callbacks(on_order_filled, on_order_error)
        
        # 3. Inicializar Processors por ativo
        for symbol in self.hft_symbols:
            processor = AsyncAssetProcessorV2(
                symbol=symbol,
                redis_client=self.hft_redis_client,
                execution_bridge=self.hft_execution_bridge,
                threshold=0.65,
                indicators_config={
                    'rsi': {'period': 14, 'enabled': True},
                    'ema': {'period': 20, 'enabled': True},
                    'atr': {'period': 14, 'enabled': True},
                    'macd': {'fast': 12, 'slow': 26, 'signal': 9, 'enabled': True}
                },
                circuit_breaker_config={
                    'atr_threshold': 0.0005,  # 0.05% para forex
                    'min_ticks': 5
                }
            )
            await processor.initialize()
            self.hft_processors[symbol] = processor
            logger.info(f"[HFT] ✅ Processor inicializado: {symbol}")
        
        # 4. Task de métricas periódicas
        asyncio.create_task(self._hft_metrics_reporter())
        
        logger.success(f"[HFT] ✅ Engine ativo para: {', '.join(self.hft_symbols)}")
        
    except Exception as e:
        logger.error(f"[HFT] ❌ Falha ao iniciar: {e}")
        import traceback
        logger.error(traceback.format_exc())
        self.hft_enabled = False


"""
================================================================================
SEÇÃO 4: HOOK NO RECEBIMENTO DE TICKS (Modificar _on_ativos_stream_update)
================================================================================
"""

async def _on_ativos_stream_update_hft(self, data: Any, account_idx: int):
    """
    Versão HFT do _on_ativos_stream_update
    Substitua a chamada ao método original por esta versão
    """
    # Chamar método original primeiro (mantém compatibilidade)
    await self._on_ativos_stream_update_original(data, account_idx)
    
    # HFT Processing
    if not self.hft_enabled or not self.hft_processors:
        return
    
    try:
        # Processar ticks para HFT
        if isinstance(data, list) and len(data) > 0:
            for item in data:
                if isinstance(item, list) and len(item) >= 3:
                    symbol = item[0]
                    price = item[2]
                    
                    # Verificar se símbolo está no HFT
                    if symbol in self.hft_processors:
                        processor = self.hft_processors[symbol]
                        
                        # Processar tick (indicadores + CB + confluência + execução)
                        signal = await processor.process_tick(price)
                        
                        if signal:
                            self.hft_metrics['signals_generated'] += 1
                            
                            # Log periódico
                            if signal.circuit_breaker_blocked:
                                self.hft_metrics['signals_blocked_by_cb'] += 1
                                if self.hft_metrics['signals_blocked_by_cb'] % 50 == 0:
                                    logger.warning(
                                        f"[HFT] 🚫 {symbol}: "
                                        f"{self.hft_metrics['signals_blocked_by_cb']} "
                                        f"sinais bloqueados por CB"
                                    )
                            else:
                                # Sinal executado
                                if self.hft_metrics['signals_generated'] % 10 == 0:
                                    logger.info(
                                        f"[HFT] 📊 {symbol}: "
                                        f"{self.hft_metrics['signals_generated']} "
                                        f"sinais gerados, "
                                        f"{self.hft_metrics['orders_executed']} ordens"
                                    )
                        
                        self.hft_metrics['ticks_processed'] += 1
        
    except Exception as e:
        logger.error(f"[HFT] Erro no processamento: {e}")


"""
================================================================================
SEÇÃO 5: MÉTODO DE STOP (Adicionar no final do stop())
================================================================================
"""

async def stop_hft_engine(self):
    """Parar HFT Engine - Adicionar ao final do stop()"""
    if not self.hft_enabled:
        return
    
    logger.info("[HFT] 🛑 Parando HFT Engine...")
    
    try:
        # Parar execution bridge
        if self.hft_execution_bridge:
            await self.hft_execution_bridge.stop()
            logger.info("[HFT] ✅ Execution bridge parado")
        
        # Resetar processors
        for symbol, processor in self.hft_processors.items():
            await processor.reset()
            logger.info(f"[HFT] ✅ Processor resetado: {symbol}")
        
        self.hft_processors.clear()
        
        # Log final de métricas
        logger.info("[HFT] 📊 Métricas finais:")
        logger.info(f"  Ticks: {self.hft_metrics['ticks_processed']}")
        logger.info(f"  Sinais: {self.hft_metrics['signals_generated']}")
        logger.info(f"  Bloqueados CB: {self.hft_metrics['signals_blocked_by_cb']}")
        logger.info(f"  Ordens: {self.hft_metrics['orders_executed']}")
        logger.info(f"  Erros: {self.hft_metrics['errors']}")
        
        logger.success("[HFT] ✅ Engine parado com sucesso")
        
    except Exception as e:
        logger.error(f"[HFT] Erro ao parar: {e}")


"""
================================================================================
SEÇÃO 6: REPORTER DE MÉTRICAS (Adicionar como novo método)
================================================================================
"""

async def _hft_metrics_reporter(self):
    """Reporter periódico de métricas HFT"""
    while self.is_running and self.hft_enabled:
        try:
            await asyncio.sleep(60)  # A cada minuto
            
            if not self.is_running or not self.hft_enabled:
                break
            
            # Obter métricas do bridge
            if self.hft_execution_bridge:
                bridge_metrics = await self.hft_execution_bridge.get_metrics()
                m = bridge_metrics.get('metrics', {})
                
                logger.info(
                    f"[HFT] 📊 Métricas (1min): "
                    f"Signals: {m.get('total_signals', 0)}, "
                    f"Orders: {m.get('orders_executed', 0)}/{m.get('orders_submitted', 0)}, "
                    f"Latency: {m.get('avg_latency_ms', 0):.2f}ms, "
                    f"Deduplicated: {m.get('deduplicated', 0)}"
                )
            
            # Obter métricas dos processors
            for symbol, processor in self.hft_processors.items():
                stats = await processor.get_stats()
                cb_stats = stats.get('circuit_breaker', {})
                
                if cb_stats.get('blocked_ticks', 0) > 0:
                    logger.info(
                        f"[HFT] 🔒 {symbol} CB: "
                        f"{cb_stats.get('blocked_ticks', 0)} bloqueios, "
                        f"rate: {cb_stats.get('block_rate', 0)*100:.1f}%"
                    )
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[HFT] Erro no reporter: {e}")


"""
================================================================================
SEÇÃO 7: ENDPOINT API PARA MÉTRICAS (Adicionar ao router)
================================================================================
"""

# Adicionar em api/routers/monitoring.py ou similar:
"""
from fastapi import APIRouter, Depends
from services.engine import get_execution_bridge

@router.get("/hft/metrics")
async def get_hft_metrics():
    
    Retorna métricas em tempo real do HFT Engine.
    
    bridge = get_execution_bridge()
    if not bridge:
        return {"error": "HFT not running"}
    
    metrics = await bridge.get_metrics()
    return {
        "status": "running",
        "metrics": metrics['metrics'],
        "circuit_breaker": metrics['circuit_breaker'],
        "queue_size": metrics['queue_size'],
        "active_orders": metrics['active_orders_count']
    }

@router.get("/hft/health")
async def get_hft_health():
    
    Health check do HFT Engine.
    
    bridge = get_execution_bridge()
    if not bridge:
        return {"status": "stopped"}
    
    metrics = await bridge.get_metrics()
    return {
        "status": "healthy" if not metrics['circuit_breaker']['open'] else "circuit_open",
        "latency_ms": metrics['metrics']['avg_latency_ms'],
        "errors": metrics['metrics']['errors']
    }
"""


"""
================================================================================
INSTRUÇÕES DE INTEGRAÇÃO PASSO A PASSO
================================================================================

1. COPIAR CÓDIGO:
   - Seção 1 (imports) → Topo do realtime.py
   - Seção 2 (init) → Final do __init__
   - Seção 3 (start) → Final do start()
   - Seção 4 (hook) → Substituir/modificar _on_ativos_stream_update
   - Seção 5 (stop) → Final do stop()
   - Seção 6 (reporter) → Novo método da classe

2. MODIFICAR __init__:
   Adicionar chamada: self.init_hft_engine()

3. MODIFICAR start():
   Adicionar chamada: await self.start_hft_engine()

4. MODIFICAR stop():
   Adicionar chamada: await self.stop_hft_engine()

5. CONFIGURAR ATRIBUTOS:
   - self.hft_symbols = ['EURUSD_otc']  # Começar com 1 ativo
   - self.hft_enabled = True  # Toggle on/off

6. TESTAR:
   python run.py
   
   Verificar logs:
   - [HFT] ✅ Engine ativo para: EURUSD_otc
   - [HFT] 📊 Métricas (1min): Signals: X, Orders: Y/Z
   - [HFT] 🚫 EURUSD_otc: X sinais bloqueados por CB
   - [HFT] 🎯 Ordem executada: EURUSD_otc SELL/BUY

7. MONITORAR:
   Acesse: http://localhost:8000/api/v1/hft/metrics
   
8. ESCALAR (após validação):
   Adicionar mais ativos:
   self.hft_symbols = ['EURUSD_otc', 'GBPUSD_otc', 'USDJPY_otc']

================================================================================
CONFIGURAÇÕES RECOMENDADAS POR ATIVO
================================================================================

EURUSD_otc (Forex - baixa volatilidade):
    atr_threshold: 0.0005  # 0.05%
    min_ticks: 5
    threshold: 0.65

GBPUSD_otc (Forex - média volatilidade):
    atr_threshold: 0.0008  # 0.08%
    min_ticks: 5
    threshold: 0.68

USDJPY_otc (Forex - alta volatilidade):
    atr_threshold: 0.0010  # 0.10%
    min_ticks: 5
    threshold: 0.70

Crypto (BTC, ETH):
    atr_threshold: 0.0020  # 0.20%
    min_ticks: 3
    threshold: 0.72

Ações (#AAPL, #TSLA):
    atr_threshold: 0.0015  # 0.15%
    min_ticks: 4
    threshold: 0.70

================================================================================
"""
