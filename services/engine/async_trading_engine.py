"""Async Trading Engine - Motor HFT com fila de sinais desacoplada"""
import asyncio
from typing import Dict, Optional, Callable, Any, List
from dataclasses import dataclass, field
from datetime import datetime
import redis.asyncio as aioredis

from .async_asset_processor import AsyncAssetProcessor, Signal


@dataclass
class TradeOrder:
    """Ordem de trade para execução"""
    signal: Signal
    priority: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attempt_count: int = 0
    max_attempts: int = 3


class AsyncTradingEngine:
    """
    Motor de trading assíncrono de alta performance.
    
    Arquitetura:
    - Processadores de ativo (AsyncAssetProcessor) - um por símbolo
    - Fila de sinais (asyncio.Queue) - desacopla análise da execução
    - Workers de execução - consomem fila e executam trades
    - Persistência Redis - estado compartilhado entre instâncias
    
    Features:
    - Processamento O(1) por tick
    - Escalável horizontalmente (multi-worker + Redis)
    - Resiliência a falhas (estado persistido)
    - Execução desacoplada (não bloqueia análise)
    
    Attributes:
        processors: Dict de AsyncAssetProcessor por símbolo
        signal_queue: Fila asyncio para sinais
        redis_client: Cliente Redis para estado compartilhado
        workers: Lista de tasks workers
        is_running: Flag de execução
    """
    
    def __init__(
        self,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_db: int = 0,
        num_workers: int = 2,
        signal_threshold: float = 0.65,
        max_queue_size: int = 1000
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_client: Optional[aioredis.Redis] = None
        
        self.processors: Dict[str, AsyncAssetProcessor] = {}
        self.signal_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.num_workers = num_workers
        self.signal_threshold = signal_threshold
        
        # Workers
        self._worker_tasks: List[asyncio.Task] = []
        self._is_running = False
        
        # Callbacks para execução de sinais
        self._signal_callbacks: List[Callable[[Signal], Any]] = []
        self._error_callbacks: List[Callable[[Exception, Signal], Any]] = []
        
        # Estatísticas
        self._stats = {
            'ticks_received': 0,
            'signals_queued': 0,
            'signals_executed': 0,
            'signals_failed': 0,
            'queue_drops': 0
        }
        self._stats_lock = asyncio.Lock()
    
    async def initialize(self):
        """Inicializar engine e conexões."""
        # Conectar ao Redis
        try:
            self.redis_client = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            await self.redis_client.ping()
            print(f"[AsyncTradingEngine] Redis conectado em {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"[AsyncTradingEngine] Aviso: Redis não disponível ({e}). Estado não persistirá.")
            self.redis_client = None
        
        # Iniciar workers
        self._is_running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(
                self._signal_worker(f"worker-{i}"),
                name=f"signal-worker-{i}"
            )
            self._worker_tasks.append(task)
        
        print(f"[AsyncTradingEngine] {self.num_workers} workers iniciados")
    
    async def shutdown(self):
        """Desligar engine graciosamente."""
        print("[AsyncTradingEngine] Iniciando shutdown...")
        self._is_running = False
        
        # Aguardar fila esvaziar (com timeout)
        try:
            await asyncio.wait_for(self.signal_queue.join(), timeout=30.0)
        except asyncio.TimeoutError:
            print("[AsyncTradingEngine] Timeout aguardando fila, cancelando workers...")
        
        # Cancelar workers
        for task in self._worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        # Fechar Redis
        if self.redis_client:
            await self.redis_client.close()
        
        print("[AsyncTradingEngine] Shutdown completo")
    
    async def on_price_update(self, symbol: str, price: float, timestamp: Optional[datetime] = None):
        """
        Receber atualização de preço (tick).
        
        Esta é a entrada principal do sistema. Deve ser chamada
        a cada tick recebido do WebSocket.
        
        Args:
            symbol: Par de trading (ex: EURUSD)
            price: Preço atual
            timestamp: Timestamp do tick (opcional)
        """
        async with self._stats_lock:
            self._stats['ticks_received'] += 1
        
        # Criar ou obter processor para este ativo
        if symbol not in self.processors:
            processor = AsyncAssetProcessor(
                symbol=symbol,
                redis_client=self.redis_client,
                threshold=self.signal_threshold
            )
            await processor.initialize()
            self.processors[symbol] = processor
            print(f"[AsyncTradingEngine] Novo processor criado para {symbol}")
        
        processor = self.processors[symbol]
        
        # Processar tick
        signal = await processor.process_tick(price)
        
        # Se gerou sinal, adicionar à fila
        if signal:
            try:
                # Usar put_nowait para não bloquear
                order = TradeOrder(signal=signal, priority=int(signal.score * 100))
                self.signal_queue.put_nowait(order)
                
                async with self._stats_lock:
                    self._stats['signals_queued'] += 1
                    
            except asyncio.QueueFull:
                # Fila cheia - descartar sinal
                async with self._stats_lock:
                    self._stats['queue_drops'] += 1
                print(f"[AsyncTradingEngine] Fila cheia, sinal descartado para {symbol}")
    
    async def _signal_worker(self, worker_id: str):
        """
        Worker que consome fila de sinais e executa trades.
        
        Args:
            worker_id: Identificador do worker
        """
        print(f"[AsyncTradingEngine] Worker {worker_id} iniciado")
        
        while self._is_running:
            try:
                # Aguardar sinal na fila (com timeout para verificar _is_running)
                order = await asyncio.wait_for(
                    self.signal_queue.get(), 
                    timeout=1.0
                )
                
                try:
                    # Executar o sinal
                    await self._execute_signal(order.signal)
                    
                    async with self._stats_lock:
                        self._stats['signals_executed'] += 1
                        
                except Exception as e:
                    # Falha na execução
                    async with self._stats_lock:
                        self._stats['signals_failed'] += 1
                    
                    order.attempt_count += 1
                    
                    # Retry se não atingiu max
                    if order.attempt_count < order.max_attempts:
                        # Re-enfileirar com delay
                        await asyncio.sleep(0.5 * order.attempt_count)
                        try:
                            self.signal_queue.put_nowait(order)
                        except asyncio.QueueFull:
                            pass
                    else:
                        # Notificar erro
                        for callback in self._error_callbacks:
                            try:
                                callback(e, order.signal)
                            except:
                                pass
                
                finally:
                    # Marcar como processado
                    self.signal_queue.task_done()
                    
            except asyncio.TimeoutError:
                # Timeout normal, continua loop
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AsyncTradingEngine] Worker {worker_id} erro: {e}")
    
    async def _execute_signal(self, signal: Signal):
        """
        Executar um sinal de trading.
        
        Esta é a integração com a API de execução.
        Substitua pela implementação real com PocketOption.
        
        Args:
            signal: Sinal a ser executado
        """
        # Notificar callbacks registrados
        for callback in self._signal_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                print(f"[AsyncTradingEngine] Erro em callback: {e}")
        
        # Log do sinal
        print(
            f"🚀 [SINAL] {signal.symbol} @ {signal.price:.5f} | "
            f"Score: {signal.score:.2%} | Dir: {signal.direction.upper()} | "
            f"Inds: {', '.join(signal.indicators_used)}"
        )
    
    def on_signal(self, callback: Callable[[Signal], Any]):
        """Registrar callback para sinais."""
        self._signal_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[Exception, Signal], Any]):
        """Registrar callback para erros."""
        self._error_callbacks.append(callback)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Obter estatísticas do engine."""
        async with self._stats_lock:
            stats = dict(self._stats)
        
        # Adicionar stats dos processors
        processor_stats = await asyncio.gather(
            *[p.get_stats() for p in self.processors.values()],
            return_exceptions=True
        )
        
        stats['processors'] = {
            p.symbol: s for p, s in zip(self.processors.values(), processor_stats)
            if not isinstance(s, Exception)
        }
        stats['queue_size'] = self.signal_queue.qsize()
        stats['active_processors'] = len(self.processors)
        
        return stats
    
    async def get_processor(self, symbol: str) -> Optional[AsyncAssetProcessor]:
        """Obter processor para um símbolo."""
        return self.processors.get(symbol)
