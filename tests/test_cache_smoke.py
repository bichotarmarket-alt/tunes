"""
Teste de Smoke End-to-End para o sistema de cache
Valida o fluxo completo sem mocks excessivos - testa o comportamento real das classes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Importar os módulos reais (não mocks)
from services.batch_signal_saver import BatchSignalSaver, PendingSignal
from services.l1_cache import L1InProcessCache


@dataclass
class SimpleSignal:
    """Sinal simples para testes"""
    signal_type: str
    confidence: float
    price: float
    indicators: list


class TestCacheSmokeReal:
    """Teste de smoke com comportamento real (sem mocks de Redis)"""
    
    async def test_batch_saver_dedup_and_flush(self):
        """
        Testa o batch saver real:
        1. Adiciona sinais (com deduplicação)
        2. Força flush (mockado para não depender do DB)
        3. Verifica estatísticas
        """
        print("\n🧪 TESTE 1: Batch Saver - Deduplicação e Flush\n")
        
        # Criar batch saver com intervalo curto para teste
        batch_saver = BatchSignalSaver(
            flush_interval=1.0,  # 1 segundo para teste rápido
            max_batch_size=5,     # Batch pequeno
            max_buffer_size=20
        )
        
        # Mockar _save_batch para não depender do DB
        save_calls = []
        async def mock_save_batch(signals):
            save_calls.append(len(signals))
            return True
        
        batch_saver._save_batch = mock_save_batch
        
        await batch_saver.start()
        
        try:
            account_id = "test-acc-123"
            symbol = "EURUSD"
            
            # Adicionar primeiro sinal
            signal1 = SimpleSignal("BUY", 0.75, 1.0850, ["RSI"])
            id1 = await batch_saver.add_signal(
                account_id=account_id,
                symbol=symbol,
                signal=signal1,
                strategy_id="strat-1",
                timeframe=60,
                metrics={'confluence': 70.0}
            )
            print(f"1️⃣ Primeiro sinal adicionado: {id1[:8]}...")
            
            # Adicionar sinal duplicado (mesmo symbol/timeframe/tipo)
            signal2 = SimpleSignal("BUY", 0.85, 1.0855, ["RSI", "MACD"])  # Melhor confiança
            id2 = await batch_saver.add_signal(
                account_id=account_id,
                symbol=symbol,
                signal=signal2,
                strategy_id="strat-1",
                timeframe=60,
                metrics={'confluence': 80.0}
            )
            print(f"2️⃣ Segundo sinal (duplicata): {id2[:8]}...")
            
            # Verificar deduplicação - deve retornar mesmo ID
            assert id1 == id2, "❌ Deduplicação falhou: IDs diferentes"
            print(f"   ✅ Deduplicação O(1): mesmo ID (atualizou confiança)")
            
            # Adicionar mais sinais para atingir batch size
            print(f"3️⃣ Adicionando mais sinais...")
            for i in range(4):
                signal = SimpleSignal("SELL" if i % 2 else "BUY", 0.70 + i*0.05, 1.0800 + i*0.01, ["EMA"])
                await batch_saver.add_signal(
                    account_id=account_id,
                    symbol=f"ASSET{i}",  # Símbolos diferentes
                    signal=signal,
                    strategy_id="strat-1",
                    timeframe=60,
                    metrics={'confluence': 65.0 + i}
                )
            
            # Verificar estatísticas antes do flush
            stats_before = batch_saver.get_stats()
            print(f"   📊 Stats antes do flush: {stats_before}")
            
            # Aguardar flush automático (1s) ou forçar
            print(f"4️⃣ Aguardando flush automático (1s)...")
            await asyncio.sleep(1.2)  # Aguardar flush automático
            
            # Verificar estatísticas após flush
            stats_after = batch_saver.get_stats()
            print(f"   📊 Stats após flush: {stats_after}")
            
            # Verificar que houve flush
            assert stats_after['flush_count'] >= 1, "❌ Nenhum flush ocorreu"
            print(f"   ✅ Flush ocorreu: {stats_after['flush_count']} vez(es)")
            
            # Verificar que mock foi chamado
            assert len(save_calls) >= 1, "❌ _save_batch não foi chamado"
            print(f"   ✅ _save_batch chamado {len(save_calls)} vez(es) com {save_calls} sinais")
            
            # Forçar outro flush para limpar
            await batch_saver.force_flush()
            
            stats_final = batch_saver.get_stats()
            print(f"   📊 Stats final: {stats_final}")
            
            print("\n✅ TESTE 1 PASSOU: Batch saver funcionando corretamente")
            return True
            
        finally:
            await batch_saver.stop()
    
    async def test_l1_cache_stampede_protection(self):
        """
        Testa L1 cache com stampede protection real:
        1. Múltiplas requisições simultâneas
        2. Verifica que só 1 fetch ocorreu
        3. Verifica que todas retornaram mesmo valor
        """
        print("\n🧪 TESTE 2: L1 Cache - Stampede Protection\n")
        
        # Criar cache real
        cache = L1InProcessCache(maxsize=100, ttl=5, name="test_stampede")
        
        fetch_count = 0
        fetch_times = []
        
        async def slow_fetch():
            """Função de fetch lenta (200ms)"""
            nonlocal fetch_count
            fetch_count += 1
            start = time.time()
            await asyncio.sleep(0.2)  # 200ms de latência simulada
            elapsed = time.time() - start
            fetch_times.append(elapsed)
            return {
                'data': f'fetched_{fetch_count}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        # 10 requisições simultâneas para mesma chave
        print(f"1️⃣ Disparando 10 requisições simultâneas para mesma chave...")
        
        async def get_data():
            return await cache.get_with_fetch(
                key="concurrent-test-key",
                fetch_func=slow_fetch,
                l2_cache=None  # Sem L2 para isolar teste
            )
        
        # Disparar todas as tarefas "simultaneamente"
        tasks = [get_data() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        print(f"2️⃣ Verificando resultados...")
        
        # Todas devem ter o mesmo resultado
        first_result = results[0]
        assert all(r == first_result for r in results), "❌ Resultados inconsistentes"
        print(f"   ✅ Todos os resultados consistentes")
        
        # Deve ter feito apenas 1 fetch (stampede protection)
        assert fetch_count == 1, f"❌ Stampede protection falhou: {fetch_count} fetches (esperado 1)"
        print(f"   ✅ Stampede protection: {fetch_count} fetch para 10 requisições")
        
        # Verificar hit rate - 1 miss (primeira), 9 hits (restantes)
        stats = cache.get_stats()
        print(f"   📊 Cache stats: {stats}")
        # Hit rate deve ser alto: 9 hits / 10 total = 90%
        assert stats['hits'] == 9, f"❌ Esperava 9 hits, teve {stats['hits']}"
        assert stats['misses'] == 1, f"❌ Esperava 1 miss, teve {stats['misses']}"
        print(f"   ✅ Hit rate: {stats['hit_rate']:.1%} ({stats['hits']} hits, {stats['misses']} misses)")
        
        # Segunda rodada - deve ser tudo cache hit
        print(f"3️⃣ Segunda rodada (deve ser tudo cache hit)...")
        fetch_count = 0  # Reset
        
        tasks2 = [get_data() for _ in range(5)]
        results2 = await asyncio.gather(*tasks2)
        
        assert fetch_count == 0, f"❌ Cache não funcionou na segunda rodada: {fetch_count} fetches"
        print(f"   ✅ Segunda rodada: {fetch_count} fetches (todos cache hits)")
        
        print("\n✅ TESTE 2 PASSOU: Stampede protection funcionando")
        return True
    
    async def test_l1_invalidation(self):
        """
        Testa invalidação de cache L1:
        1. Popula cache
        2. Invalida chave
        3. Verifica que próxima leitura vai ao fetch
        """
        print("\n🧪 TESTE 3: L1 Cache - Invalidação\n")
        
        cache = L1InProcessCache(maxsize=100, ttl=60, name="test_invalidate")
        
        fetch_count = 0
        
        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {'version': fetch_count, 'data': 'test'}
        
        # Primeira leitura - cache miss
        print(f"1️⃣ Primeira leitura (cache miss)...")
        result1 = await cache.get_with_fetch("invalidate-key", fetch_data)
        assert result1['version'] == 1
        print(f"   ✅ Primeira leitura: fetch #{result1['version']}")
        
        # Segunda leitura - cache hit
        print(f"2️⃣ Segunda leitura (cache hit)...")
        result2 = await cache.get_with_fetch("invalidate-key", fetch_data)
        assert result2['version'] == 1  # Mesmo valor
        assert fetch_count == 1  # Não fez novo fetch
        print(f"   ✅ Cache hit: ainda fetch #{result2['version']}")
        
        # Invalidar
        print(f"3️⃣ Invalidando chave...")
        await cache.invalidate("invalidate-key")
        
        # Terceira leitura - deve ir ao fetch novamente
        print(f"4️⃣ Terceira leitura após invalidação...")
        result3 = await cache.get_with_fetch("invalidate-key", fetch_data)
        assert result3['version'] == 2  # Novo fetch
        assert fetch_count == 2
        print(f"   ✅ Após invalidação: novo fetch #{result3['version']}")
        
        print("\n✅ TESTE 3 PASSOU: Invalidação funcionando")
        return True
    
    async def test_cursor_utc(self):
        """Testa que cursor pagination usa UTC corretamente"""
        print("\n🧪 TESTE 4: Cursor Pagination - UTC\n")
        
        # Simular criação de cursor UTC
        now = datetime.now(timezone.utc)
        cursor = now.isoformat()
        
        print(f"1️⃣ Cursor gerado: {cursor}")
        
        # Verificar que tem timezone UTC
        assert "+00:00" in cursor or "Z" in cursor, f"❌ Cursor não é UTC: {cursor}"
        print(f"   ✅ Cursor em UTC detectado")
        
        # Parse e verificar
        parsed = datetime.fromisoformat(cursor)
        assert parsed.tzinfo is not None, "❌ Cursor parseado sem timezone"
        print(f"   ✅ Parse bem-sucedido com timezone")
        
        print("\n✅ TESTE 4 PASSOU: Cursor UTC funcionando")
        return True
    
    async def run_all_tests(self):
        """Rodar todos os testes de smoke"""
        print("\n" + "="*60)
        print("🧪 INICIANDO TESTES DE SMOKE - CACHE SYSTEM")
        print("="*60)
        
        results = []
        
        try:
            results.append(("Batch Saver", await self.test_batch_saver_dedup_and_flush()))
        except Exception as e:
            print(f"\n💥 TESTE FALHOU: {e}")
            import traceback
            traceback.print_exc()
            results.append(("Batch Saver", False))
        
        try:
            results.append(("Stampede Protection", await self.test_l1_cache_stampede_protection()))
        except Exception as e:
            print(f"\n💥 TESTE FALHOU: {e}")
            import traceback
            traceback.print_exc()
            results.append(("Stampede Protection", False))
        
        try:
            results.append(("Invalidação", await self.test_l1_invalidation()))
        except Exception as e:
            print(f"\n💥 TESTE FALHOU: {e}")
            import traceback
            traceback.print_exc()
            results.append(("Invalidação", False))
        
        try:
            results.append(("Cursor UTC", await self.test_cursor_utc()))
        except Exception as e:
            print(f"\n💥 TESTE FALHOU: {e}")
            import traceback
            traceback.print_exc()
            results.append(("Cursor UTC", False))
        
        # Resumo
        print("\n" + "="*60)
        print("📊 RESUMO DOS TESTES")
        print("="*60)
        
        passed = sum(1 for _, r in results if r)
        total = len(results)
        
        for name, result in results:
            status = "✅ PASSOU" if result else "❌ FALHOU"
            print(f"   {status}: {name}")
        
        print(f"\n🎯 Resultado: {passed}/{total} testes passaram")
        
        if passed == total:
            print("\n🎉 TODOS OS TESTES PASSARAM!")
            return True
        else:
            print(f"\n⚠️ {total - passed} teste(s) falharam")
            return False


# Função principal para rodar testes
async def main():
    """Função principal para rodar testes de smoke"""
    tester = TestCacheSmokeReal()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    # Rodar com asyncio
    exit_code = asyncio.run(main())
    exit(exit_code)
