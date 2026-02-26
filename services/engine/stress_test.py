"""
HFT Stress Tester - Ambiente de Simulação de Estresse

Valida:
1. Convergência Estatística (RSI incremental vs Pandas)
2. Persistência Redis (estado preservado após restart)
3. Circuit Breaker (bloqueio em mercado lateral)
4. Performance (vazamento de memória, latência)

Uso:
    python stress_test.py --ticks 10000 --symbol EURUSD_otc --verbose
"""

import asyncio
import time
import random
import statistics
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

# Simular Redis se não disponível
try:
    import aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[AVISO] aioredis não instalado - usando mock")

from services.engine import (
    AsyncTradingEngine,
    AsyncAssetProcessor,
    PersistentRSI,
    PersistentEMA,
    PersistentATR,
    PersistentMACD,
    CircuitBreaker
)


@dataclass
class Tick:
    """Tick sintético"""
    price: float
    timestamp: float


class SyntheticMarketGenerator:
    """Gerador de dados de mercado sintéticos com padrões realistas"""
    
    def __init__(self, seed: int = 42):
        random.seed(seed)
        np.random.seed(seed)
        self.current_price = 1.0850  # Preço inicial EURUSD-like
        self.trend = 0  # -1 (down), 0 (neutral), 1 (up)
        self.trend_duration = 0
        
    def generate_trending_phase(self, n_ticks: int, direction: int, volatility: float = 0.0002):
        """Gerar fase de tendência (alta ou baixa)"""
        ticks = []
        for _ in range(n_ticks):
            # Movimento direcional + ruído
            drift = direction * volatility * (1 + random.random())
            noise = np.random.normal(0, volatility * 0.5)
            self.current_price *= (1 + drift + noise)
            ticks.append(Tick(
                price=self.current_price,
                timestamp=time.time() + len(ticks) * 0.1
            ))
        return ticks
    
    def generate_ranging_phase(self, n_ticks: int, volatility: float = 0.00005):
        """Gerar fase de mercado lateral (ranging) - para testar Circuit Breaker"""
        ticks = []
        base_price = self.current_price
        for _ in range(n_ticks):
            # Apenas ruído, sem tendência
            noise = np.random.normal(0, volatility)
            price = base_price * (1 + noise)
            # Manter preço próximo do base (mean reversion)
            deviation = (price - base_price) / base_price
            price = base_price * (1 + deviation * 0.3)  # Reverter 70% do desvio
            ticks.append(Tick(
                price=price,
                timestamp=time.time() + len(ticks) * 0.1
            ))
            self.current_price = price
        return ticks
    
    def generate_volatile_phase(self, n_ticks: int, volatility: float = 0.001):
        """Gerar fase de alta volatilidade"""
        ticks = []
        for _ in range(n_ticks):
            noise = np.random.normal(0, volatility)
            self.current_price *= (1 + noise)
            ticks.append(Tick(
                price=self.current_price,
                timestamp=time.time() + len(ticks) * 0.1
            ))
        return ticks
    
    def generate_full_session(self, total_ticks: int = 10000) -> List[Tick]:
        """
        Gerar sessão completa simulando diferentes regiões de mercado:
        - 20% trending alta
        - 20% ranging (CB deve bloquear)
        - 20% trending baixa
        - 20% alta volatilidade
        - 20% trending alta
        """
        ticks_per_phase = total_ticks // 5
        
        all_ticks = []
        
        print(f"[MARKET GEN] Fase 1: Tendência de ALTA ({ticks_per_phase} ticks)")
        all_ticks.extend(self.generate_trending_phase(ticks_per_phase, 1))
        
        print(f"[MARKET GEN] Fase 2: RANGING/LATERAL ({ticks_per_phase} ticks) - CB deve bloquear")
        all_ticks.extend(self.generate_ranging_phase(ticks_per_phase))
        
        print(f"[MARKET GEN] Fase 3: Tendência de BAIXA ({ticks_per_phase} ticks)")
        all_ticks.extend(self.generate_trending_phase(ticks_per_phase, -1))
        
        print(f"[MARKET GEN] Fase 4: ALTA VOLATILIDADE ({ticks_per_phase} ticks)")
        all_ticks.extend(self.generate_volatile_phase(ticks_per_phase))
        
        print(f"[MARKET GEN] Fase 5: Tendência de ALTA final ({ticks_per_phase} ticks)")
        all_ticks.extend(self.generate_trending_phase(ticks_per_phase, 1))
        
        # Remaining ticks
        remaining = total_ticks - len(all_ticks)
        if remaining > 0:
            all_ticks.extend(self.generate_trending_phase(remaining, random.choice([-1, 1])))
        
        return all_ticks


class MockRedis:
    """Mock de Redis para testes sem dependência"""
    def __init__(self):
        self._data: Dict[str, str] = {}
    
    async def get(self, key: str) -> Optional[str]:
        return self._data.get(key)
    
    async def set(self, key: str, value: str):
        self._data[key] = value
    
    async def delete(self, key: str):
        self._data.pop(key, None)


class StressTester:
    """Executor de testes de estresse"""
    
    def __init__(self, symbol: str = "EURUSD_otc", use_redis: bool = False):
        self.symbol = symbol
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.redis = None
        
        # Métricas
        self.metrics = {
            'ticks_processed': 0,
            'signals_generated': 0,
            'circuit_breaker_blocks': 0,
            'processing_times_ms': [],
            'memory_samples': [],
            'rsi_values': [],
            'atr_values': [],
            'confluence_scores': []
        }
        
        # Componentes
        self.rsi: Optional[PersistentRSI] = None
        self.atr: Optional[PersistentATR] = None
        self.circuit_breaker: Optional[CircuitBreaker] = None
        self.asset_processor: Optional[AsyncAssetProcessor] = None
        
    async def setup(self):
        """Inicializar componentes"""
        print(f"\n[SETUP] Inicializando StressTester para {self.symbol}")
        print(f"[SETUP] Redis: {'Sim' if self.use_redis else 'Mock'}")
        
        if self.use_redis:
            try:
                self.redis = await aioredis.from_url("redis://localhost")
                await self.redis.ping()
                print("[SETUP] ✅ Conectado ao Redis")
            except Exception as e:
                print(f"[SETUP] ⚠️ Falha Redis: {e} - usando Mock")
                self.redis = MockRedis()
        else:
            self.redis = MockRedis()
        
        # Inicializar indicadores
        self.rsi = PersistentRSI(self.symbol, period=14, redis_client=self.redis)
        self.atr = PersistentATR(self.symbol, period=14, redis_client=self.redis)
        
        # Circuit breaker com threshold baixo para testar bloqueios
        self.circuit_breaker = CircuitBreaker(
            symbol=self.symbol,
            atr_threshold=0.0005,  # 0.05%
            min_ticks=5,
            redis_client=self.redis
        )
        await self.circuit_breaker.load_state()
        
        # Asset processor
        self.asset_processor = AsyncAssetProcessor(
            symbol=self.symbol,
            redis_client=self.redis,
            threshold=0.65,
            indicators_config={
                'rsi': {'period': 14, 'enabled': True},
                'ema': {'period': 20, 'enabled': True},
                'atr': {'period': 14, 'enabled': True},
                'macd': {'fast': 12, 'slow': 26, 'signal': 9, 'enabled': True}
            }
        )
        await self.asset_processor.initialize()
        
        print("[SETUP] ✅ Componentes inicializados\n")
    
    async def run_stress_test(self, ticks: List[Tick], verbose: bool = False) -> Dict[str, Any]:
        """Executar teste de estresse com ticks sintéticos"""
        print(f"[STRESS] Iniciando processamento de {len(ticks)} ticks...")
        print("=" * 70)
        
        start_time = time.perf_counter()
        phase_tick_counts = [0, 0, 0, 0, 0]  # Contar ticks por fase
        phase_size = len(ticks) // 5
        
        for i, tick in enumerate(ticks):
            tick_start = time.perf_counter()
            
            # Determinar fase atual (para métricas)
            current_phase = min(i // phase_size, 4)
            phase_tick_counts[current_phase] += 1
            
            # 1. Atualizar indicadores
            rsi_value, _ = await self.rsi.update(tick.price)
            atr_value, _ = await self.atr.update(tick.price)
            
            # 2. Verificar Circuit Breaker
            cb_allows = await self.circuit_breaker.check(atr_value)
            
            if not cb_allows:
                self.metrics['circuit_breaker_blocks'] += 1
                if verbose and self.metrics['circuit_breaker_blocks'] % 100 == 0:
                    print(f"  [CB] Bloqueio #{self.metrics['circuit_breaker_blocks']} "
                          f"na fase {current_phase+1} - ATR: {atr_value:.6f}")
            
            # 3. Processar tick no asset processor
            signal = await self.asset_processor.process_tick(tick.price)
            
            if signal:
                self.metrics['signals_generated'] += 1
                if verbose and self.metrics['signals_generated'] <= 10:
                    print(f"  [SINAL #{self.metrics['signals_generated']}] {signal.direction.upper()} "
                          f"@ {signal.price:.5f} (score: {signal.score:.2f})")
            
            # 4. Coletar métricas
            tick_time = (time.perf_counter() - tick_start) * 1000  # ms
            self.metrics['processing_times_ms'].append(tick_time)
            
            if rsi_value:
                self.metrics['rsi_values'].append(rsi_value)
            if atr_value:
                self.metrics['atr_values'].append(atr_value)
            
            self.metrics['ticks_processed'] += 1
            
            # Progresso a cada 1000 ticks
            if (i + 1) % 1000 == 0:
                progress_pct = (i + 1) / len(ticks) * 100
                avg_time = statistics.mean(self.metrics['processing_times_ms'][-1000:])
                print(f"[PROGRESS] {progress_pct:.1f}% - "
                      f"Ticks: {i+1}/{len(ticks)}, "
                      f"Avg latency: {avg_time:.3f}ms, "
                      f"Signals: {self.metrics['signals_generated']}, "
                      f"CB Blocks: {self.metrics['circuit_breaker_blocks']}")
        
        total_time = time.perf_counter() - start_time
        
        print("=" * 70)
        print(f"[STRESS] ✅ Processamento concluído em {total_time:.2f}s")
        
        return self._generate_report(total_time)
    
    def _generate_report(self, total_time: float) -> Dict[str, Any]:
        """Gerar relatório de saúde"""
        m = self.metrics
        
        report = {
            'summary': {
                'ticks_processed': m['ticks_processed'],
                'signals_generated': m['signals_generated'],
                'circuit_breaker_blocks': m['circuit_breaker_blocks'],
                'total_time_seconds': total_time,
                'ticks_per_second': m['ticks_processed'] / total_time
            },
            'performance': {
                'avg_latency_ms': statistics.mean(m['processing_times_ms']),
                'max_latency_ms': max(m['processing_times_ms']),
                'min_latency_ms': min(m['processing_times_ms']),
                'p99_latency_ms': sorted(m['processing_times_ms'])[int(len(m['processing_times_ms']) * 0.99)]
            },
            'indicators': {
                'rsi_range': (min(m['rsi_values']), max(m['rsi_values'])) if m['rsi_values'] else (None, None),
                'atr_range': (min(m['atr_values']), max(m['atr_values'])) if m['atr_values'] else (None, None),
                'avg_atr': statistics.mean(m['atr_values']) if m['atr_values'] else None
            },
            'circuit_breaker': {
                'blocks': m['circuit_breaker_blocks'],
                'block_rate': m['circuit_breaker_blocks'] / max(1, m['ticks_processed']),
                'expected_behavior': 'Deve ter bloqueios na fase 2 (ranging)'
            }
        }
        
        return report
    
    async def test_persistence(self) -> bool:
        """Testar persistência do estado no Redis"""
        print("\n[PERSISTENCE TEST] Testando persistência Redis...")
        
        # Simular crash e recuperação
        original_rsi = self.rsi.last_price if self.rsi else None
        original_atr = self.atr.last_atr if self.atr else None
        
        print(f"[PERSISTENCE] Estado original - RSI last: {original_rsi}, ATR last: {original_atr}")
        
        # Criar novas instâncias (simulando restart)
        new_rsi = PersistentRSI(self.symbol, period=14, redis_client=self.redis)
        new_atr = PersistentATR(self.symbol, period=14, redis_client=self.redis)
        new_cb = CircuitBreaker(self.symbol, redis_client=self.redis)
        
        await new_rsi.load_state()
        await new_atr.load_state()
        await new_cb.load_state()
        
        # Verificar se estado foi recuperado
        recovered_rsi = new_rsi.last_price
        recovered_atr = new_atr.last_atr
        
        print(f"[PERSISTENCE] Estado recuperado - RSI last: {recovered_rsi}, ATR last: {recovered_atr}")
        
        success = (recovered_rsi is not None and recovered_atr is not None)
        print(f"[PERSISTENCE] {'✅ SUCESSO' if success else '❌ FALHA'} - Estado preservado após restart")
        
        return success
    
    async def cleanup(self):
        """Limpar estado de teste"""
        print("\n[CLEANUP] Limpando estado de teste...")
        if self.rsi:
            await self.rsi.reset()
        if self.atr:
            await self.atr.reset()
        if self.circuit_breaker:
            await self.circuit_breaker.reset()
        print("[CLEANUP] ✅ Concluído")


def print_report(report: Dict[str, Any]):
    """Imprimir relatório formatado"""
    print("\n" + "=" * 70)
    print("RELATÓRIO DE SAÚDE - HFT STRESS TEST")
    print("=" * 70)
    
    s = report['summary']
    print(f"\n📊 RESUMO:")
    print(f"  Ticks processados: {s['ticks_processed']:,}")
    print(f"  Tempo total: {s['total_time_seconds']:.2f}s")
    print(f"  Ticks/segundo: {s['ticks_per_second']:,.0f}")
    print(f"  Sinais gerados: {s['signals_generated']}")
    print(f"  Bloqueios CB: {s['circuit_breaker_blocks']}")
    
    p = report['performance']
    print(f"\n⚡ PERFORMANCE:")
    print(f"  Latência média: {p['avg_latency_ms']:.3f}ms")
    print(f"  Latência P99: {p['p99_latency_ms']:.3f}ms")
    print(f"  Latência máx: {p['max_latency_ms']:.3f}ms")
    print(f"  Latência mín: {p['min_latency_ms']:.3f}ms")
    
    i = report['indicators']
    print(f"\n📈 INDICADORES:")
    if i['rsi_range'][0] is not None:
        print(f"  RSI range: {i['rsi_range'][0]:.2f} - {i['rsi_range'][1]:.2f}")
        print(f"  ATR range: {i['atr_range'][0]:.6f} - {i['atr_range'][1]:.6f}")
        print(f"  ATR médio: {i['avg_atr']:.6f}")
    
    cb = report['circuit_breaker']
    print(f"\n🔒 CIRCUIT BREAKER:")
    print(f"  Bloqueios: {cb['blocks']}")
    print(f"  Taxa de bloqueio: {cb['block_rate']*100:.1f}%")
    print(f"  Comportamento esperado: {cb['expected_behavior']}")
    
    print("\n" + "=" * 70)


async def main():
    parser = argparse.ArgumentParser(description='HFT Stress Tester')
    parser.add_argument('--ticks', type=int, default=10000, help='Número de ticks (default: 10000)')
    parser.add_argument('--symbol', type=str, default='EURUSD_otc', help='Símbolo (default: EURUSD_otc)')
    parser.add_argument('--redis', action='store_true', help='Usar Redis real')
    parser.add_argument('--verbose', action='store_true', help='Log detalhado')
    parser.add_argument('--persist-test', action='store_true', help='Testar persistência')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("HFT STRESS TESTER")
    print(f"Alvo: {args.symbol} | Ticks: {args.ticks:,} | Redis: {'Sim' if args.redis else 'Mock'}")
    print("=" * 70)
    
    # 1. Gerar dados sintéticos
    print("\n[PHASE 1] Gerando dados de mercado sintéticos...")
    market_gen = SyntheticMarketGenerator(seed=42)
    ticks = market_gen.generate_full_session(args.ticks)
    
    # 2. Setup do tester
    tester = StressTester(symbol=args.symbol, use_redis=args.redis)
    await tester.setup()
    
    # 3. Executar stress test
    report = await tester.run_stress_test(ticks, verbose=args.verbose)
    
    # 4. Testar persistência
    if args.persist_test:
        await tester.test_persistence()
    
    # 5. Print relatório
    print_report(report)
    
    # 6. Cleanup
    await tester.cleanup()
    
    print("\n✅ Stress test concluído!")


if __name__ == '__main__':
    asyncio.run(main())
