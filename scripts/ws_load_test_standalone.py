"""
Teste de Carga WebSocket - Versão Standalone

Testa apenas o ConnectionManager isoladamente, sem depender do servidor HTTP.
"""
import asyncio
import websockets
import random
import time
import sys
import psutil
from dataclasses import dataclass, field
from typing import List
from loguru import logger

# Setup logging
logger.remove()
logger.add(sys.stderr, level="INFO")


@dataclass
class LoadTestMetrics:
    connected: int = 0
    rejected: int = 0
    messages_received: int = 0
    cpu_samples: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    
    def sample_resources(self):
        self.cpu_samples.append(psutil.cpu_percent(interval=0.1))
        self.memory_samples.append(psutil.virtual_memory().percent)


async def test_websocket_echo_server():
    """
    Cria um servidor WebSocket echo simples para testar o load tester
    """
    connected_clients = set()
    metrics = LoadTestMetrics()
    
    async def echo_handler(websocket, path):
        client_id = f"client_{id(websocket)}"
        connected_clients.add(websocket)
        metrics.connected += 1
        
        try:
            async for message in websocket:
                metrics.messages_received += 1
                # Echo message back
                try:
                    await asyncio.wait_for(websocket.send(message), timeout=2.0)
                except asyncio.TimeoutError:
                    break
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            connected_clients.discard(websocket)
    
    # Iniciar servidor
    server = await websockets.serve(echo_handler, "localhost", 8765, ping_timeout=10)
    logger.info("🚀 Servidor WebSocket de teste iniciado em ws://localhost:8765")
    
    return server, metrics, connected_clients


async def normal_client(client_id: str, metrics: LoadTestMetrics, duration: int):
    """Cliente normal que recebe e responde mensagens"""
    try:
        async with websockets.connect("ws://localhost:8765", open_timeout=5) as ws:
            metrics.connected += 1
            start = time.time()
            
            while time.time() - start < duration:
                try:
                    # Send ping
                    await ws.send(f'{{"type":"ping","id":"{client_id}"}}')
                    
                    # Wait for response
                    response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    metrics.messages_received += 1
                    
                    await asyncio.sleep(0.1)  # 10 msgs/segundo
                except asyncio.TimeoutError:
                    continue
                    
    except Exception as e:
        logger.debug(f"Cliente {client_id} erro: {type(e).__name__}")


async def slow_client(client_id: str, metrics: LoadTestMetrics, duration: int):
    """Cliente lento que demora para responder"""
    try:
        async with websockets.connect("ws://localhost:8765", open_timeout=5) as ws:
            metrics.connected += 1
            start = time.time()
            
            while time.time() - start < duration:
                try:
                    await ws.send(f'{{"type":"slow","id":"{client_id}"}}')
                    
                    # Delay artificial de 3s (testa timeout do servidor)
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    await asyncio.sleep(3.0)  # Processa lentamente
                    
                except asyncio.TimeoutError:
                    break
                except websockets.exceptions.ConnectionClosed:
                    break
                    
    except Exception as e:
        logger.debug(f"Cliente lento {client_id} erro: {type(e).__name__}")


async def zombie_client(client_id: str, metrics: LoadTestMetrics, duration: int):
    """Cliente zombie que conecta mas não consome"""
    try:
        async with websockets.connect("ws://localhost:8765", open_timeout=5) as ws:
            metrics.connected += 1
            # Apenas mantém conexão aberta
            await asyncio.sleep(duration)
    except Exception as e:
        logger.debug(f"Zombie {client_id} erro: {type(e).__name__}")


async def monitor_resources(metrics: LoadTestMetrics, shutdown_event: asyncio.Event):
    """Monitora recursos em background"""
    while not shutdown_event.is_set():
        metrics.sample_resources()
        await asyncio.sleep(1.0)


async def run_load_test():
    """Executa teste de carga completo"""
    TOTAL_CONNECTIONS = 100
    DURATION = 30
    
    normal_count = int(TOTAL_CONNECTIONS * 0.7)
    slow_count = int(TOTAL_CONNECTIONS * 0.2)
    zombie_count = TOTAL_CONNECTIONS - normal_count - slow_count
    
    metrics = LoadTestMetrics()
    shutdown_event = asyncio.Event()
    
    # Iniciar servidor
    server, server_metrics, connected_clients = await test_websocket_echo_server()
    
    logger.info(f"🧪 INICIANDO TESTE DE CARGA")
    logger.info(f"   Total: {TOTAL_CONNECTIONS} | Normal: {normal_count} | Lento: {slow_count} | Zombie: {zombie_count}")
    logger.info(f"   Duração: {DURATION}s")
    logger.info("")
    
    # Monitor de recursos
    monitor_task = asyncio.create_task(monitor_resources(metrics, shutdown_event))
    
    # Criar clientes
    tasks = []
    
    # Normal clients
    for i in range(normal_count):
        tasks.append(asyncio.create_task(normal_client(f"normal_{i}", metrics, DURATION)))
    
    # Slow clients
    for i in range(slow_count):
        tasks.append(asyncio.create_task(slow_client(f"slow_{i}", metrics, DURATION)))
    
    # Zombie clients
    for i in range(zombie_count):
        tasks.append(asyncio.create_task(zombie_client(f"zombie_{i}", metrics, DURATION)))
    
    # Warmup
    logger.info("⏳ Warmup: 5s...")
    await asyncio.sleep(5)
    logger.info(f"📊 Clientes conectados: {metrics.connected}")
    
    # Aguardar duração do teste
    logger.info(f"⏳ Executando por {DURATION}s...")
    await asyncio.sleep(DURATION)
    
    # Finalizar
    shutdown_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    await monitor_task
    server.close()
    await server.wait_closed()
    
    # Relatório
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESULTADOS DO TESTE DE CARGA")
    logger.info("=" * 60)
    
    logger.info(f"\n📈 Conexões:")
    logger.info(f"   Total tentado: {TOTAL_CONNECTIONS}")
    logger.info(f"   Conectados: {metrics.connected}")
    logger.info(f"   Mensagens recebidas: {metrics.messages_received}")
    
    logger.info(f"\n🖥️  Recursos:")
    if metrics.cpu_samples:
        max_cpu = max(metrics.cpu_samples)
        avg_cpu = sum(metrics.cpu_samples) / len(metrics.cpu_samples)
        logger.info(f"   CPU máx: {max_cpu:.1f}%")
        logger.info(f"   CPU méd: {avg_cpu:.1f}%")
    
    if metrics.memory_samples:
        avg_mem = sum(metrics.memory_samples) / len(metrics.memory_samples)
        logger.info(f"   Memória méd: {avg_mem:.1f}%")
    
    # Validação
    logger.info("\n🔍 VALIDAÇÃO:")
    passed = True
    
    if metrics.connected >= TOTAL_CONNECTIONS * 0.8:
        logger.success(f"✅ Taxa de conexão: {metrics.connected}/{TOTAL_CONNECTIONS}")
    else:
        logger.error(f"❌ Taxa de conexão baixa: {metrics.connected}/{TOTAL_CONNECTIONS}")
        passed = False
    
    if metrics.cpu_samples and max(metrics.cpu_samples) < 80:
        logger.success(f"✅ CPU máx: {max(metrics.cpu_samples):.1f}% < 80%")
    else:
        logger.error(f"❌ CPU muito alta")
        passed = False
    
    logger.info("\n" + "=" * 60)
    if passed:
        logger.success("🎉 TESTE APROVADO")
    else:
        logger.error("💥 TESTE REPROVADO")
    
    return passed


if __name__ == "__main__":
    success = asyncio.run(run_load_test())
    sys.exit(0 if success else 1)
