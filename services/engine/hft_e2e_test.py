"""
HFT End-to-End Test - Teste Ponta a Ponta Completo

Valida todo o fluxo HFT:
1. AsyncAssetProcessorV2 (indicadores incrementais + CB)
2. HFTExecutionBridge (fila + workers + idempotência)
3. Simulação de mercado realista com fases (trending, ranging, volatile)

Execute:
    python hft_e2e_test.py --ticks 2000 --verbose
"""

import asyncio
import time
import random
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass
import argparse

# Mock Redis para testes
class MockRedis:
    def __init__(self):
        self._data: Dict[str, str] = {}
    
    async def get(self, key: str):
        return self._data.get(key)
    
    async def set(self, key: str, value: str):
        self._data[key] = value
    
    async def delete(self, key: str):
        self._data.pop(key, None)


@dataclass
class Tick:
    price: float
    timestamp: float


class MarketSimulator:
    """Simula fases de mercado realistas"""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)
        self.price = 1.0850
    
    def trending_up(self, n: int) -> List[Tick]:
        ticks = []
        for _ in range(n):
            self.price *= (1 + 0.0003 + np.random.normal(0, 0.0001))
            ticks.append(Tick(self.price, time.time()))
        return ticks
    
    def trending_down(self, n: int) -> List[Tick]:
        ticks = []
        for _ in range(n):
            self.price *= (1 - 0.0003 + np.random.normal(0, 0.0001))
            ticks.append(Tick(self.price, time.time()))
        return ticks
    
    def ranging(self, n: int) -> List[Tick]:
        """Mercado lateral - CB deve bloquear"""
        ticks = []
        base = self.price
        for _ in range(n):
            noise = np.random.normal(0, 0.00005)
            self.price = base * (1 + noise * 0.3)  # Mean reversion
            ticks.append(Tick(self.price, time.time()))
        return ticks
    
    def volatile(self, n: int) -> List[Tick]:
        ticks = []
        for _ in range(n):
            self.price *= (1 + np.random.normal(0, 0.001))
            ticks.append(Tick(self.price, time.time()))
        return ticks


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticks', type=int, default=2000)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    print("=" * 80)
    print("HFT END-TO-END TEST")
    print("AsyncAssetProcessorV2 + CircuitBreaker + HFTExecutionBridge")
    print("=" * 80)
    
    # Setup
    from services.engine import (
        AsyncAssetProcessorV2,
        HFTExecutionBridge,
        set_execution_bridge,
        CircuitBreaker
    )
    
    redis = MockRedis()
    symbol = "EURUSD_otc"
    
    # 1. Criar Execution Bridge
    print("\n[1] Inicializando HFTExecutionBridge...")
    bridge = HFTExecutionBridge(
        api_client=None,  # Modo simulado
        redis_client=redis,
        num_workers=2,
        max_retries=2,
        enable_circuit_breaker=True,
        circuit_breaker_threshold=3
    )
    await bridge.start()
    set_execution_bridge(bridge)
    
    # Callbacks para monitorar execuções
    def on_order_filled(order):
        print(f"    🎯 ORDEM EXECUTADA: {order.symbol} {order.side.value.upper()} @ {order.entry_price:.5f}")
    
    def on_order_error(order, error):
        print(f"    ❌ ERRO: {order.symbol} - {error}")
    
    bridge.set_callbacks(on_order_filled, on_order_error)
    
    # 2. Criar Asset Processor V2 com CircuitBreaker
    print("\n[2] Inicializando AsyncAssetProcessorV2...")
    processor = AsyncAssetProcessorV2(
        symbol=symbol,
        redis_client=redis,
        execution_bridge=bridge,
        threshold=0.65,
        circuit_breaker_config={
            'atr_threshold': 0.0005,
            'min_ticks': 5
        }
    )
    await processor.initialize()
    
    # 3. Gerar dados de mercado
    print(f"\n[3] Gerando {args.ticks} ticks de mercado simulado...")
    sim = MarketSimulator()
    ticks_per_phase = args.ticks // 4
    
    all_ticks = []
    phases = [
        ("🟢 TRENDING UP", sim.trending_up),
        ("🟡 RANGING (CB deve bloquear)", sim.ranging),
        ("🔴 TRENDING DOWN", sim.trending_down),
        ("🟣 VOLATILE", sim.volatile)
    ]
    
    for name, generator in phases:
        print(f"    {name}: {ticks_per_phase} ticks")
        all_ticks.extend(generator(ticks_per_phase))
    
    # 4. Processar todos os ticks
    print(f"\n[4] Processando {len(all_ticks)} ticks...")
    print("-" * 80)
    
    signals_generated = []
    start_time = time.perf_counter()
    
    for i, tick in enumerate(all_ticks):
        signal = await processor.process_tick(tick.price)
        
        if signal:
            signals_generated.append(signal)
            if args.verbose and len(signals_generated) <= 20:
                cb_status = "🚫 CB" if signal.circuit_breaker_blocked else "✅ OK"
                print(f"  Signal #{len(signals_generated)}: {signal.direction.upper()} "
                      f"@ {signal.price:.5f} (score: {signal.score:.2f}) {cb_status}")
        
        # Progresso
        if (i + 1) % 500 == 0:
            pct = (i + 1) / len(all_ticks) * 100
            print(f"  Progress: {pct:.0f}% ({i+1}/{len(all_ticks)})")
    
    processing_time = time.perf_counter() - start_time
    
    # 5. Aguardar execução das ordens
    print(f"\n[5] Aguardando execução das ordens...")
    await asyncio.sleep(2)  # Tempo para workers processarem fila
    
    # 6. Relatório
    print("\n" + "=" * 80)
    print("RESULTADO DO TESTE END-TO-END")
    print("=" * 80)
    
    # Métricas do processor
    proc_stats = await processor.get_stats()
    print(f"\n📊 PROCESSADOR:")
    print(f"  Ticks processados: {proc_stats['ticks_processed']}")
    print(f"  Sinais gerados: {proc_stats['signals_generated']}")
    print(f"  Bloqueados por CB: {proc_stats['signals_blocked_by_cb']}")
    print(f"  Ordens enfileiradas: {proc_stats['orders_enqueued']}")
    
    # Métricas do bridge
    bridge_metrics = await bridge.get_metrics()
    m = bridge_metrics['metrics']
    print(f"\n⚡ EXECUÇÃO:")
    print(f"  Sinais recebidos: {m['total_signals']}")
    print(f"  Ordens submetidas: {m['orders_submitted']}")
    print(f"  Ordens executadas: {m['orders_executed']}")
    print(f"  Ordens rejeitadas: {m['orders_rejected']}")
    print(f"  Erros: {m['errors']}")
    print(f"  Retries: {m['retries']}")
    print(f"  Deduplicados: {m['deduplicated']}")
    print(f"  Latência média: {m['avg_latency_ms']:.2f}ms")
    
    # Performance
    print(f"\n🚀 PERFORMANCE:")
    print(f"  Tempo total: {processing_time:.2f}s")
    print(f"  Ticks/segundo: {len(all_ticks)/processing_time:,.0f}")
    print(f"  Latência média/tick: {(processing_time/len(all_ticks))*1000:.3f}ms")
    
    # Análise de Circuit Breaker
    cb_stats = proc_stats.get('circuit_breaker', {})
    if cb_stats:
        print(f"\n🔒 CIRCUIT BREAKER:")
        print(f"  Bloqueios totais: {cb_stats.get('blocked_ticks', 0)}")
        print(f"  Checks realizados: {cb_stats.get('total_checks', 0)}")
        print(f"  Taxa de bloqueio: {cb_stats.get('block_rate', 0)*100:.1f}%")
        print(f"  Último ATR: {cb_stats.get('last_atr', 'N/A')}")
    
    # Validações
    print(f"\n✅ VALIDAÇÕES:")
    checks = [
        ("Sinais gerados > 0", proc_stats['signals_generated'] > 0),
        ("CB bloqueou ranging", proc_stats['signals_blocked_by_cb'] > 0),
        ("Ordens executadas", m['orders_executed'] > 0),
        ("Performance > 1000 tps", len(all_ticks)/processing_time > 1000),
        ("Latência bridge < 100ms", m['avg_latency_ms'] < 100)
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 TODAS AS VALIDAÇÕES PASSARAM!")
        print("Sistema HFT pronto para produção.")
    else:
        print("⚠️ ALGUMAS VALIDAÇÕES FALHARAM")
        print("Revisar configurações antes de ir para produção.")
    print("=" * 80)
    
    # Cleanup
    print("\n[CLEANUP] Finalizando...")
    await bridge.stop()
    await processor.reset()
    print("✅ Teste concluído!")


if __name__ == '__main__':
    asyncio.run(main())
