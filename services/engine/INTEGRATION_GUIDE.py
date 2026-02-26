"""
Guia de Integração do Engine HFT com DataCollectorService

Este arquivo mostra EXATAMENTE como integrar o novo engine HFT no sistema existente.

==============================================
ETAPA 1: Modificar DataCollectorService.__init__
==============================================

No arquivo: services/data_collector/realtime.py

Adicione no final do __init__:

    # Integração com novo engine HFT
    from services.engine.hft_integration import HFTIntegration, set_hft_integration
    self.hft_bridge = HFTIntegration(
        redis_host='localhost',
        signal_threshold=0.65,
        enabled_assets=['EURUSD_otc'],  # Começar com 1 ativo
        enable_adaptive=True,
        comparison_mode=True  # Comparar com sistema legado
    )
    set_hft_integration(self.hft_bridge)

==============================================
ETAPA 2: Modificar _add_tick_to_buffer
==============================================

No arquivo: services/data_collector/realtime.py

Localize a função _add_tick_to_buffer e adicione no final:

    async def _add_tick_to_buffer(self, account_idx: int, symbol: str, price: float, timestamp: float):
        """Adicionar tick ao buffer com suporte a HFT"""
        try:
            # ... código existente ...
            
            # === INTEGRAÇÃO HFT ===
            # Enviar tick para o novo engine HFT
            if hasattr(self, 'hft_bridge') and self.hft_bridge:
                await self.hft_bridge.on_tick(symbol, price, timestamp)
            # ======================
            
        except Exception as e:
            logger.error(f"Erro ao adicionar tick ao buffer: {e}")

==============================================
ETAPA 3: Modificar initialize
==============================================

No arquivo: services/data_collector/realtime.py

Na função initialize(), adicione após self.is_running = True:

    async def initialize(self):
        """Inicializar serviço com suporte HFT"""
        self.is_running = True
        
        # ... código existente ...
        
        # === INTEGRAÇÃO HFT ===
        if hasattr(self, 'hft_bridge') and self.hft_bridge:
            await self.hft_bridge.initialize()
            logger.success("[DataCollector] Engine HFT inicializado")
        # ======================

==============================================
ETAPA 4: Modificar shutdown
==============================================

No arquivo: services/data_collector/realtime.py

Na função shutdown(), adicione:

    async def shutdown(self):
        """Desligar serviço com suporte HFT"""
        
        # === INTEGRAÇÃO HFT ===
        if hasattr(self, 'hft_bridge') and self.hft_bridge:
            await self.hft_bridge.shutdown()
            logger.info("[DataCollector] Engine HFT desligado")
        # ======================
        
        # ... código existente de shutdown ...

==============================================
ETAPA 5: Adicionar endpoint de métricas
==============================================

Em api/routers/ (ou onde estão seus endpoints), adicione:

    from fastapi import APIRouter
    from services.engine.hft_integration import get_hft_integration
    
    router = APIRouter()
    
    @router.get("/hft/metrics")
    async def get_hft_metrics():
        \"\"\"Obter métricas do engine HFT\"\"\"
        hft = get_hft_integration()
        if not hft:
            return {"error": "HFT not initialized"}
        
        metrics = await hft.get_metrics()
        return metrics
    
    @router.post("/hft/enable/{symbol}")
    async def enable_hft_asset(symbol: str):
        \"\"\"Habilitar modo HFT para um ativo\"\"\"
        hft = get_hft_integration()
        if not hft:
            return {"error": "HFT not initialized"}
        
        hft.enable_asset(symbol)
        return {"message": f"HFT enabled for {symbol}"}
    
    @router.post("/hft/disable/{symbol}")
    async def disable_hft_asset(symbol: str):
        \"\"\"Desabilitar modo HFT para um ativo\"\"\"
        hft = get_hft_integration()
        if not hft:
            return {"error": "HFT not initialized"}
        
        hft.disable_asset(symbol)
        return {"message": f"HFT disabled for {symbol}"}
    
    @router.get("/hft/performance/{symbol}")
    async def get_hft_performance(symbol: str, timeframe: str = 'M1'):
        \"\"\"Obter relatório de performance HFT\"\"\"
        hft = get_hft_integration()
        if not hft:
            return {"error": "HFT not initialized"}
        
        report = await hft.get_asset_performance(symbol, timeframe)
        return report or {"message": "No data yet"}

==============================================
ETAPA 6: Handler de sinais HFT
==============================================

Para receber sinais do engine HFT e executar trades, adicione no __init__:

    async def _on_hft_signal(self, signal):
        \"\"\"Handler para sinais do engine HFT\"\"\"
        logger.info(
            f"🚀 [HFT SIGNAL] {signal.symbol} {signal.direction.upper()} "
            f"@ {signal.price:.5f} | Score: {signal.score:.2%}"
        )
        
        # Integrar com trade_executor existente
        # Aqui você pode:
        # 1. Salvar no banco de dados
        # 2. Enviar notificação
        # 3. Executar trade
        
    # No __init__, registrar callback:
    self.hft_bridge.on_hft_signal(self._on_hft_signal)

==============================================
MIGRAÇÃO GRADUAL RECOMENDADA
==============================================

Fase 1 (Teste):
    - Habilitar HFT apenas para EURUSD_otc
    - Manter sistema legado para todos ativos
    - Comparison_mode = True
    - Monitorar métricas por 1 semana

Fase 2 (Expansão):
    - Adicionar GBPUSD_otc, USDJPY_otc
    - Ajustar threshold baseado em performance
    - Continuar comparison

Fase 3 (Otimização):
    - Habilitar adaptive para ativos com >20 trades
    - Ajustar pesos dinamicamente
    - Desativar indicadores ruins

Fase 4 (Produção):
    - Migrar todos ativos para HFT
    - Desativar comparison_mode
    - Sistema legado como backup

==============================================
CHECKLIST DE DEPENDÊNCIAS
==============================================

1. Redis instalado e rodando:
   - Windows: docker run -p 6379:6379 redis:latest
   - Linux: sudo apt install redis-server

2. Dependências Python:
   pip install redis asyncio aioredis

3. Arquivos criados:
   ✓ services/engine/persistent_rsi.py
   ✓ services/engine/confluence_categorized.py
   ✓ services/engine/async_asset_processor.py
   ✓ services/engine/async_trading_engine.py
   ✓ services/engine/adaptive_tracker.py
   ✓ services/engine/hft_integration.py
   ✓ services/engine/__init__.py

==============================================
EXEMPLO COMPLETO DE INICIALIZAÇÃO
==============================================
"""

async def exemplo_inicializacao_completa():
    """Exemplo completo de como inicializar o sistema com HFT"""
    
    # 1. Criar DataCollectorService normalmente
    from services.data_collector.realtime import DataCollectorService
    
    service = DataCollectorService()
    
    # 2. O HFT é inicializado automaticamente no __init__
    # Mas se quiser configurar manualmente:
    
    from services.engine.hft_integration import HFTIntegration
    
    service.hft_bridge = HFTIntegration(
        redis_host='localhost',
        redis_port=6379,
        signal_threshold=0.65,
        enabled_assets=[
            'EURUSD_otc',
            # Adicione mais conforme validação
        ],
        enable_adaptive=True,      # Ajustar pesos dinamicamente
        comparison_mode=True       # Comparar com sistema legado
    )
    
    # 3. Registrar callback para sinais
    async def meu_handler_de_sinais(signal):
        print(f"🎯 Sinal recebido: {signal.symbol} {signal.direction}")
        # Aqui você integra com seu trade_executor
    
    service.hft_bridge.on_hft_signal(meu_handler_de_sinais)
    
    # 4. Inicializar
    await service.initialize()
    
    # 5. O sistema agora processa ticks em ambos:
    #    - Sistema legado (existente)
    #    - Novo engine HFT (incremental)
    
    # ... operação normal ...
    
    # 6. Métricas
    metrics = await service.hft_bridge.get_metrics()
    print(f"Sinais HFT: {metrics['engine_stats']['signals_executed']}")
    
    # 7. Performance por ativo
    perf = await service.hft_bridge.get_asset_performance('EURUSD_otc', 'M1')
    print(f"Winrate HFT: {perf['winrate']:.1%}")
    
    # 8. Shutdown
    await service.shutdown()


if __name__ == '__main__':
    import asyncio
    asyncio.run(exemplo_inicializacao_completa())
