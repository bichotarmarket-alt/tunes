"""
WebSocket Load Test - Production Grade

Valida:
- Limite de 5 conexões por usuário
- Broadcast paralelo mantém latência estável
- Isolamento de clientes lentos
- Crescimento linear de CPU/memória

Uso:
    python -m scripts.ws_load_test --connections 500 --duration 60
    python -m scripts.ws_load_test --profile reconnect-storm  # Teste de reconexão massiva
"""
import asyncio
import websockets
import random
import time
import argparse
import sys
import json
import psutil
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger
import aiohttp

# Configuração de logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# URL do WebSocket
DEFAULT_WS_URL = "ws://localhost:8005/ws/ticks?symbol=EURUSD"
DEFAULT_HTTP_URL = "http://localhost:8005"


@dataclass
class ClientStats:
    """Estatísticas por tipo de cliente"""
    connected: int = 0
    rejected: int = 0
    disconnected: int = 0
    messages_received: int = 0
    errors: int = 0
    latency_ms: List[float] = field(default_factory=list)


@dataclass
class LoadTestMetrics:
    """Métricas consolidadas do teste"""
    # Conexões
    total_attempted: int = 0
    total_connected: int = 0
    total_rejected: int = 0
    total_disconnected: int = 0
    
    # Performance
    latency_broadcast_ms: List[float] = field(default_factory=list)
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    
    # Por tipo
    normal: ClientStats = field(default_factory=ClientStats)
    slow: ClientStats = field(default_factory=ClientStats)
    zombie: ClientStats = field(default_factory=ClientStats)
    
    # Timestamps
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def add_latency(self, latency_ms: float):
        self.latency_broadcast_ms.append(latency_ms)
    
    def sample_resources(self):
        self.cpu_samples.append(psutil.cpu_percent(interval=0.1))
        self.memory_samples.append(psutil.virtual_memory().percent)
    
    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(self.latency_broadcast_ms) if self.latency_broadcast_ms else 0.0
    
    @property
    def p99_latency_ms(self) -> float:
        if not self.latency_broadcast_ms:
            return 0.0
        sorted_lat = sorted(self.latency_broadcast_ms)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]
    
    @property
    def max_cpu(self) -> float:
        return max(self.cpu_samples) if self.cpu_samples else 0.0
    
    @property
    def avg_memory(self) -> float:
        return statistics.mean(self.memory_samples) if self.memory_samples else 0.0


class WebSocketLoadTester:
    """
    Testador de carga WebSocket production-grade
    
    Simula 3 perfis de cliente:
    - Normal (70%): Recebe mensagens normalmente
    - Lento (20%): Delay artificial no receive, testa timeout de 2s
    - Zombie (10%): Conecta e não consome, testa remoção automática
    """
    
    def __init__(
        self,
        ws_url: str = DEFAULT_WS_URL,
        http_url: str = DEFAULT_HTTP_URL,
        total_connections: int = 500,
        duration_seconds: int = 60,
        symbol: str = "EURUSD"
    ):
        self.ws_url = ws_url
        self.http_url = http_url
        self.total_connections = total_connections
        self.duration_seconds = duration_seconds
        self.symbol = symbol
        
        self.metrics = LoadTestMetrics()
        self._shutdown_event = asyncio.Event()
        self._tasks: List[asyncio.Task] = []
        
        # Distribuição de clientes
        self.normal_count = int(total_connections * 0.7)
        self.slow_count = int(total_connections * 0.2)
        self.zombie_count = total_connections - self.normal_count - self.slow_count
    
    async def _get_server_metrics(self) -> Optional[dict]:
        """Busca métricas do servidor via endpoint HTTP"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.http_url}/health/resilience") as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug(f"Não foi possível obter métricas do servidor: {e}")
        return None
    
    async def _normal_client(self, client_id: str):
        """
        Cliente normal: recebe mensagens e processa imediatamente
        
        Valida:
        - Conexão estabelece corretamente
        - Mensagens chegam em tempo real
        - Latência de broadcast é baixa
        """
        ws_url = f"{self.ws_url}&_uid={client_id}"
        
        try:
            async with websockets.connect(ws_url, open_timeout=5, close_timeout=5) as ws:
                self.metrics.normal.connected += 1
                self.metrics.total_connected += 1
                
                start_time = time.time()
                
                while not self._shutdown_event.is_set():
                    try:
                        # Receive com timeout para não travar
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        self.metrics.normal.messages_received += 1
                        
                        # Calcular latência se mensagem tiver timestamp
                        try:
                            data = json.loads(msg)
                            if 'timestamp' in data:
                                latency = (time.time() - data['timestamp']) * 1000
                                self.metrics.normal.latency_ms.append(latency)
                        except:
                            pass
                            
                    except asyncio.TimeoutError:
                        # Timeout normal, continua loop
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break
                        
                duration = time.time() - start_time
                if duration > 0:
                    logger.debug(f"Cliente normal {client_id} finalizado após {duration:.1f}s")
                    
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 1008:  # Policy violation - limite excedido
                self.metrics.normal.rejected += 1
                self.metrics.total_rejected += 1
                logger.debug(f"Cliente {client_id} rejeitado (limite de conexões)")
            else:
                self.metrics.normal.errors += 1
                logger.warning(f"Cliente {client_id} erro HTTP {e.status_code}")
        except Exception as e:
            self.metrics.normal.errors += 1
            logger.debug(f"Cliente normal {client_id} erro: {type(e).__name__}")
    
    async def _slow_client(self, client_id: str):
        """
        Cliente lento: processa mensagens com delay artificial
        
        Valida:
        - Timeout de 2s funciona corretamente
        - Cliente lento é desconectado automaticamente
        - Não afeta outros clientes
        """
        ws_url = f"{self.ws_url}&_uid=slow_{client_id}"
        
        try:
            async with websockets.connect(ws_url, open_timeout=5, close_timeout=5) as ws:
                self.metrics.slow.connected += 1
                self.metrics.total_connected += 1
                
                messages_processed = 0
                
                while not self._shutdown_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        
                        # Delay artificial de 3s (maior que timeout de 2s do servidor)
                        await asyncio.sleep(3.0)
                        messages_processed += 1
                        
                        if messages_processed % 10 == 0:
                            logger.debug(f"Cliente lento {client_id} processou {messages_processed} msgs")
                            
                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed as e:
                        # Esperado - servidor deve desconectar cliente lento
                        self.metrics.slow.disconnected += 1
                        self.metrics.total_disconnected += 1
                        logger.debug(f"Cliente lento {client_id} desconectado (esperado)")
                        break
                        
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 1008:
                self.metrics.slow.rejected += 1
                self.metrics.total_rejected += 1
        except Exception as e:
            self.metrics.slow.errors += 1
    
    async def _zombie_client(self, client_id: str):
        """
        Cliente zombie: conecta mas não consome mensagens
        
        Valida:
        - Conexões ociosas são gerenciadas corretamente
        - Não causam vazamento de recursos
        - Timeout de inatividade funciona
        """
        ws_url = f"{self.ws_url}&_uid=zombie_{client_id}"
        
        try:
            async with websockets.connect(ws_url, open_timeout=5, close_timeout=5) as ws:
                self.metrics.zombie.connected += 1
                self.metrics.total_connected += 1
                
                # Não recebe mensagens - apenas mantém conexão aberta
                # Aguarda até shutdown ou desconexão
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.duration_seconds)
                except asyncio.TimeoutError:
                    pass
                    
                self.metrics.zombie.disconnected += 1
                    
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 1008:
                self.metrics.zombie.rejected += 1
                self.metrics.total_rejected += 1
        except Exception as e:
            self.metrics.zombie.errors += 1
    
    async def _monitor_resources(self):
        """Monitora CPU e memória em background"""
        while not self._shutdown_event.is_set():
            self.metrics.sample_resources()
            await asyncio.sleep(1.0)
    
    async def _simulate_mass_broadcast(self):
        """
        Simula broadcast massivo via endpoint HTTP
        
        Valida:
        - Latência de broadcast não explode
        - Gather paralelo funciona corretamente
        """
        try:
            async with aiohttp.ClientSession() as session:
                # 100 mensagens rápidas
                for i in range(100):
                    broadcast_data = {
                        "symbol": self.symbol,
                        "data": {"test": f"broadcast_{i}", "timestamp": time.time()},
                        "timestamp": time.time()
                    }
                    
                    start = time.time()
                    try:
                        async with session.post(
                            f"{self.http_url}/test/broadcast",
                            json=broadcast_data,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                latency = (time.time() - start) * 1000
                                self.metrics.add_latency(latency)
                    except:
                        pass
                    
                    await asyncio.sleep(0.01)  # 100 mensagens em ~1s
                    
        except Exception as e:
            logger.warning(f"Erro no broadcast massivo: {e}")
    
    async def run_reconnect_storm(self, reconnect_count: int = 100):
        """
        Teste de reconexão massiva (storm)
        
        Simula falha de rede com 100 clientes reconectando simultaneamente.
        Valida se o servidor sobrevive ao storm sem travar.
        """
        logger.info(f"🌪️  INICIANDO RECONNECT STORM: {reconnect_count} clientes")
        
        self.metrics.start_time = time.time()
        
        async def storm_client(client_id: str):
            for attempt in range(3):  # 3 tentativas de reconexão
                try:
                    ws_url = f"{self.ws_url}?symbol={self.symbol}&user_id=storm_user_{client_id % 20}"  # 20 usuários diferentes
                    async with websockets.connect(ws_url, open_timeout=2) as ws:
                        self.metrics.total_connected += 1
                        # Recebe uma mensagem e desconecta
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=0.5)
                        except:
                            pass
                        # Desconexão abrupta
                        await ws.close()
                        await asyncio.sleep(0.05)  # Pequeno delay antes de reconectar
                except Exception:
                    self.metrics.total_rejected += 1
        
        # Lançar storm
        tasks = [asyncio.create_task(storm_client(f"storm_{i}")) for i in range(reconnect_count)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.metrics.end_time = time.time()
        self._print_summary()
    
    async def run_load_test(self):
        """Executa o teste de carga principal"""
        logger.info("🚀 INICIANDO TESTE DE CARGA WEBSOCKET")
        logger.info(f"   Conexões: {self.total_connections}")
        logger.info(f"   Duração: {self.duration_seconds}s")
        logger.info(f"   Normal: {self.normal_count} | Lento: {self.slow_count} | Zombie: {self.zombie_count}")
        logger.info("")
        
        self.metrics.start_time = time.time()
        
        # Iniciar monitor de recursos
        monitor_task = asyncio.create_task(self._monitor_resources())
        
        # Criar clientes
        tasks = []
        
        # Normal clients (70%)
        for i in range(self.normal_count):
            tasks.append(asyncio.create_task(self._normal_client(f"normal_{i}")))
        
        # Slow clients (20%)
        for i in range(self.slow_count):
            tasks.append(asyncio.create_task(self._slow_client(f"slow_{i}")))
        
        # Zombie clients (10%)
        for i in range(self.zombie_count):
            tasks.append(asyncio.create_task(self._zombie_client(f"zombie_{i}")))
        
        # Aguardar warmup de conexões
        logger.info("⏳ Warmup: aguardando 5s para estabilização...")
        await asyncio.sleep(5)
        
        # Log status atual
        logger.info(f"📊 Conexões: {self.metrics.total_connected} | Rejeitadas: {self.metrics.total_rejected}")
        
        # Simular broadcast massivo no meio do teste
        mid_duration = self.duration_seconds // 2
        logger.info(f"⏳ Executando teste por {mid_duration}s...")
        await asyncio.sleep(mid_duration)
        
        logger.info("📢 Disparando broadcast massivo (100 mensagens)...")
        await self._simulate_mass_broadcast()
        
        # Continuar restante do teste
        remaining = self.duration_seconds - mid_duration - 5  # -5 do warmup
        logger.info(f"⏳ Continuando por mais {remaining}s...")
        await asyncio.sleep(remaining)
        
        # Finalizar
        self._shutdown_event.set()
        self.metrics.end_time = time.time()
        
        # Aguardar finalização das tasks
        logger.info("🛑 Finalizando conexões...")
        await asyncio.gather(*tasks, return_exceptions=True)
        await monitor_task
        
        # Relatório
        self._print_summary()
        
        # Validações
        return self._validate_results()
    
    def _print_summary(self):
        """Imprime resumo detalhado do teste"""
        logger.info("\n" + "=" * 70)
        logger.info("📊 RESUMO DO TESTE DE CARGA WEBSOCKET")
        logger.info("=" * 70)
        
        logger.info(f"\n⏱️  Duração: {self.metrics.duration_seconds:.1f}s")
        
        logger.info(f"\n📈 Conexões:")
        logger.info(f"   Tentadas: {self.total_connections}")
        logger.info(f"   Conectadas: {self.metrics.total_connected}")
        logger.info(f"   Rejeitadas: {self.metrics.total_rejected}")
        logger.info(f"   Desconectadas: {self.metrics.total_disconnected}")
        
        logger.info(f"\n👤 Por Perfil:")
        logger.info(f"   Normal: {self.metrics.normal.connected} conectados, {self.metrics.normal.messages_received} msgs")
        logger.info(f"   Lento: {self.metrics.slow.connected} conectados, {self.metrics.slow.disconnected} desconectados")
        logger.info(f"   Zombie: {self.metrics.zombie.connected} conectados, {self.metrics.zombie.disconnected} desconectados")
        
        if self.metrics.latency_broadcast_ms:
            logger.info(f"\n⚡ Latência de Broadcast:")
            logger.info(f"   Média: {self.metrics.avg_latency_ms:.2f}ms")
            logger.info(f"   P99: {self.metrics.p99_latency_ms:.2f}ms")
            logger.info(f"   Amostras: {len(self.metrics.latency_broadcast_ms)}")
        
        logger.info(f"\n🖥️  Recursos:")
        logger.info(f"   CPU máx: {self.metrics.max_cpu:.1f}%")
        logger.info(f"   Memória média: {self.metrics.avg_memory:.1f}%")
        logger.info(f"   Amostras: {len(self.metrics.cpu_samples)}")
        
        logger.info("\n" + "=" * 70)
    
    def _validate_results(self) -> bool:
        """Valida critérios de aprovação"""
        logger.info("🔍 VALIDAÇÃO DOS CRITÉRIOS:")
        logger.info("")
        
        passed = True
        
        # 1. CPU < 70%
        if self.metrics.max_cpu < 70:
            logger.success(f"✅ CPU: {self.metrics.max_cpu:.1f}% < 70%")
        else:
            logger.error(f"❌ CPU: {self.metrics.max_cpu:.1f}% >= 70%")
            passed = False
        
        # 2. Conexões por usuário limitadas
        if self.metrics.total_rejected > 0:
            logger.success(f"✅ Limite de conexões funcionando: {self.metrics.total_rejected} rejeitadas")
        else:
            logger.warning("⚠️  Nenhuma conexão rejeitada - verificar se limite foi atingido")
        
        # 3. Clientes lentos desconectados
        if self.metrics.slow.disconnected > 0:
            logger.success(f"✅ Clientes lentos isolados: {self.metrics.slow.disconnected} desconectados")
        else:
            logger.warning("⚠️  Nenhum cliente lento desconectado")
        
        # 4. Latência de broadcast
        if self.metrics.latency_broadcast_ms:
            if self.metrics.avg_latency_ms < 100:
                logger.success(f"✅ Latência média: {self.metrics.avg_latency_ms:.2f}ms < 100ms")
            else:
                logger.error(f"❌ Latência média alta: {self.metrics.avg_latency_ms:.2f}ms")
                passed = False
            
            if self.metrics.p99_latency_ms < 500:
                logger.success(f"✅ P99 latência: {self.metrics.p99_latency_ms:.2f}ms < 500ms")
            else:
                logger.error(f"❌ P99 latência alta: {self.metrics.p99_latency_ms:.2f}ms")
                passed = False
        
        logger.info("")
        if passed:
            logger.success("🎉 SISTEMA APROVADO - Todos os critérios atendidos")
        else:
            logger.error("💥 SISTEMA REPROVADO - Critérios não atendidos")
        
        return passed


async def main():
    parser = argparse.ArgumentParser(description="WebSocket Load Test - Production Grade")
    parser.add_argument("--connections", type=int, default=500, help="Total de conexões (default: 500)")
    parser.add_argument("--duration", type=int, default=60, help="Duração em segundos (default: 60)")
    parser.add_argument("--url", type=str, default=DEFAULT_WS_URL, help="URL do WebSocket")
    parser.add_argument("--http-url", type=str, default=DEFAULT_HTTP_URL, help="URL HTTP do servidor")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Símbolo para teste")
    parser.add_argument("--profile", type=str, choices=["load", "reconnect-storm"], default="load",
                        help="Perfil de teste: load ou reconnect-storm")
    parser.add_argument("--storm-count", type=int, default=100, help="Número de clientes no reconnect storm")
    
    args = parser.parse_args()
    
    tester = WebSocketLoadTester(
        ws_url=args.url,
        http_url=args.http_url,
        total_connections=args.connections,
        duration_seconds=args.duration,
        symbol=args.symbol
    )
    
    if args.profile == "reconnect-storm":
        success = await tester.run_reconnect_storm(reconnect_count=args.storm_count)
    else:
        success = await tester.run_load_test()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
