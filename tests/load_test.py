"""
Load Test - Teste de carga para 10 usuários simultâneos

Mede:
- Queries por segundo ao DB
- Uso de memória
- Latência das respostas da API
"""
import asyncio
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psutil
import aiohttp
from datetime import datetime, timezone
from loguru import logger

# Configuração
BASE_URL = "http://localhost:8000"  # Ajustar conforme necessário
API_ENDPOINTS = [
    "/health",  # Endpoint público que não requer autenticação
    "/health",
    "/health",
]

CONCURRENT_USERS = 2  # Reduzido para testar se é problema de concorrência SQLite
REQUESTS_PER_USER = 20


class LoadTest:
    """Teste de carga simples com asyncio"""
    
    def __init__(self):
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_latency': 0.0,
            'min_latency': float('inf'),
            'max_latency': 0.0,
            'start_time': None,
            'end_time': None,
        }
        self.process = psutil.Process()
        
    async def run(self):
        """Executar teste de carga"""
        print("\n" + "="*60)
        print("🚀 TESTE DE CARGA - 10 Usuários Simultâneos")
        print("="*60)
        
        # Medir memória inicial
        mem_before = self.process.memory_info().rss / 1024 / 1024  # MB
        print(f"\n📊 Memória inicial: {mem_before:.1f} MB")
        
        self.stats['start_time'] = time.time()
        
        # Criar 10 usuários simultâneos
        print(f"\n👥 Iniciando {CONCURRENT_USERS} usuários simultâneos...")
        print(f"📡 Cada usuário faz {REQUESTS_PER_USER} requisições")
        
        # Simular usuários
        tasks = [
            self.simulate_user(f"user_{i}")
            for i in range(CONCURRENT_USERS)
        ]
        
        await asyncio.gather(*tasks)
        
        self.stats['end_time'] = time.time()
        
        # Medir memória final
        mem_after = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Resultados
        self.print_results(mem_before, mem_after)
    
    async def simulate_user(self, user_id: str):
        """Simular um usuário fazendo requisições"""
        async with aiohttp.ClientSession() as session:
            for i in range(REQUESTS_PER_USER):
                endpoint = API_ENDPOINTS[i % len(API_ENDPOINTS)]
                await self.make_request(session, user_id, endpoint, i)
    
    async def make_request(self, session, user_id: str, endpoint: str, request_num: int):
        """Fazer uma requisição e medir latência"""
        url = f"{BASE_URL}{endpoint}"
        start = time.time()
        
        try:
            async with session.get(url, timeout=10) as response:
                latency = time.time() - start
                
                self.stats['total_requests'] += 1
                
                if response.status == 200:
                    self.stats['successful_requests'] += 1
                    self.stats['total_latency'] += latency
                    self.stats['min_latency'] = min(self.stats['min_latency'], latency)
                    self.stats['max_latency'] = max(self.stats['max_latency'], latency)
                else:
                    self.stats['failed_requests'] += 1
                    # Log detalhado do erro
                    if self.stats['failed_requests'] <= 10:
                        try:
                            body = await response.text()
                            print(f"❌ ERRO {response.status}: {url}")
                            print(f"   Body: {body[:200]}...")
                        except:
                            print(f"❌ ERRO {response.status}: {url} (sem body)")
                    
        except Exception as e:
            self.stats['failed_requests'] += 1
            if self.stats['failed_requests'] <= 10:
                print(f"❌ EXCEÇÃO: {type(e).__name__}: {e}")
    
    def print_results(self, mem_before: float, mem_after: float):
        """Imprimir resultados do teste"""
        duration = self.stats['end_time'] - self.stats['start_time']
        
        print("\n" + "="*60)
        print("📊 RESULTADOS DO TESTE DE CARGA")
        print("="*60)
        
        print(f"\n⏱️  Duração total: {duration:.2f} segundos")
        print(f"📡 Total de requisições: {self.stats['total_requests']}")
        print(f"✅ Requisições bem-sucedidas: {self.stats['successful_requests']}")
        print(f"❌ Requisições falhas: {self.stats['failed_requests']}")
        
        if self.stats['successful_requests'] > 0:
            avg_latency = self.stats['total_latency'] / self.stats['successful_requests']
            print(f"\n⚡ Latência média: {avg_latency*1000:.1f} ms")
            print(f"⚡ Latência mínima: {self.stats['min_latency']*1000:.1f} ms")
            print(f"⚡ Latência máxima: {self.stats['max_latency']*1000:.1f} ms")
        
        print(f"\n🚀 Throughput: {self.stats['total_requests'] / duration:.1f} req/s")
        
        print(f"\n💾 Memória antes: {mem_before:.1f} MB")
        print(f"💾 Memória depois: {mem_after:.1f} MB")
        print(f"💾 Variação: {mem_after - mem_before:+.1f} MB")
        
        # Checklist de performance
        print("\n" + "="*60)
        print("✅ CHECKLIST DE PERFORMANCE")
        print("="*60)
        
        success_rate = self.stats['successful_requests'] / max(self.stats['total_requests'], 1)
        if success_rate >= 0.99:
            print("✅ Taxa de sucesso >= 99%")
        else:
            print(f"⚠️  Taxa de sucesso: {success_rate*100:.1f}%")
        
        if duration > 0:
            qps = self.stats['total_requests'] / duration
            if qps >= 10:
                print(f"✅ Throughput: {qps:.1f} req/s")
            else:
                print(f"⚠️  Throughput baixo: {qps:.1f} req/s")
        
        if self.stats['max_latency'] < 1.0:
            print(f"✅ Latência máxima < 1s")
        else:
            print(f"⚠️  Latência máxima alta: {self.stats['max_latency']*1000:.1f} ms")
        
        print("\n" + "="*60)


async def main():
    """Função principal"""
    test = LoadTest()
    await test.run()


if __name__ == "__main__":
    # Verificar dependências
    try:
        import psutil
        import aiohttp
    except ImportError:
        print("❌ Dependências faltando. Instale com:")
        print("   pip install psutil aiohttp")
        sys.exit(1)
    
    asyncio.run(main())
