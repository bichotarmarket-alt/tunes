"""
HFT Execution Bridge - Ponte de execução de ordens para HFT

Responsabilidades:
- Receber sinais do AsyncAssetProcessor (via fila assíncrona)
- Garantir idempotência (não executar múltiplas ordens para mesmo ativo)
- Executar ordens na PocketOption com retry e backoff
- Registrar métricas de latência e sucesso/falha
- Desacoplar análise da execução

Características:
- Fila asyncio.Queue para desacoplamento
- Workers paralelos configuráveis
- Circuit breaker de execução (para não repetir em falha crítica)
- Persistência de estado no Redis
- Logs estruturados para auditoria
"""

import asyncio
import json
import time
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import traceback


class OrderStatus(Enum):
    """Status da ordem"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    EXECUTED = "executed"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ERROR = "error"


class ExecutionSide(Enum):
    """Lado da execução"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class ExecutionSignal:
    """Sinal de execução recebido do AsyncAssetProcessor"""
    symbol: str
    direction: str  # 'buy' ou 'sell'
    price: float
    score: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    timeframe: int = 60  # segundos (default 1min)
    amount: float = 1.0  # valor da ordem
    strategy_id: Optional[str] = None
    account_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    """Representação de uma ordem"""
    order_id: str
    symbol: str
    side: ExecutionSide
    amount: float
    entry_price: float
    status: OrderStatus
    created_at: datetime
    signal_score: float
    retry_count: int = 0
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    api_response: Optional[Dict] = None


@dataclass
class ExecutionMetrics:
    """Métricas de execução"""
    total_signals_received: int = 0
    total_orders_submitted: int = 0
    total_orders_executed: int = 0
    total_orders_rejected: int = 0
    total_errors: int = 0
    total_retries: int = 0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    signals_deduplicated: int = 0  # Sinais ignorados por idempotência
    
    def to_dict(self) -> Dict:
        return {
            'total_signals': self.total_signals_received,
            'orders_submitted': self.total_orders_submitted,
            'orders_executed': self.total_orders_executed,
            'orders_rejected': self.total_orders_rejected,
            'errors': self.total_errors,
            'retries': self.total_retries,
            'avg_latency_ms': round(self.avg_latency_ms, 3),
            'max_latency_ms': round(self.max_latency_ms, 3),
            'deduplicated': self.signals_deduplicated
        }


class HFTExecutionBridge:
    """
    Ponte de execução HFT com fila assíncrona e workers.
    
    Args:
        api_client: Cliente da API PocketOption (deve ter método async send_order)
        redis_client: Cliente Redis para persistência
        num_workers: Número de workers paralelos
        max_retries: Máximo de tentativas por ordem
        enable_circuit_breaker: Se True, para de executar após N falhas consecutivas
    """
    
    def __init__(
        self,
        api_client=None,
        redis_client=None,
        num_workers: int = 2,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
        enable_circuit_breaker: bool = True,
        circuit_breaker_threshold: int = 5
    ):
        self.api_client = api_client
        self.redis = redis_client
        self.num_workers = num_workers
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self.enable_circuit_breaker = enable_circuit_breaker
        self.circuit_breaker_threshold = circuit_breaker_threshold
        
        # Estado
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_orders: Dict[str, Order] = {}  # symbol -> Order (ordens em execução)
        self.completed_orders: Dict[str, Order] = {}  # order_id -> Order (histórico)
        self.worker_tasks: List[asyncio.Task] = []
        self.is_running: bool = False
        self._lock = asyncio.Lock()
        
        # Métricas
        self.metrics = ExecutionMetrics()
        self._latency_samples: List[float] = []
        
        # Circuit breaker de execução
        self._consecutive_failures: int = 0
        self._circuit_open: bool = False
        self._circuit_open_until: Optional[float] = None
        
        # Callbacks
        self._on_order_filled: Optional[Callable[[Order], None]] = None
        self._on_order_error: Optional[Callable[[Order, Exception], None]] = None
        
        # Redis keys
        self._redis_orders_key = "hft:active_orders"
        self._redis_metrics_key = "hft:metrics"
    
    async def start(self):
        """Iniciar workers de execução"""
        if self.is_running:
            return
        
        self.is_running = True
        print(f"[HFTExecutionBridge] 🚀 Iniciando {self.num_workers} workers...")
        
        # Carregar ordens ativas do Redis (recuperação após restart)
        await self._load_active_orders()
        
        # Iniciar workers
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self.worker_tasks.append(task)
        
        # Iniciar task de métricas periódicas
        asyncio.create_task(self._metrics_reporter())
        
        print(f"[HFTExecutionBridge] ✅ {self.num_workers} workers iniciados")
    
    async def stop(self):
        """Parar workers e salvar estado"""
        print("[HFTExecutionBridge] 🛑 Parando...")
        self.is_running = False
        
        # Cancelar workers
        for task in self.worker_tasks:
            task.cancel()
        
        # Aguardar cancelamento
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        # Salvar ordens ativas no Redis
        await self._save_active_orders()
        
        # Salvar métricas
        await self._save_metrics()
        
        print("[HFTExecutionBridge] ✅ Parado")
    
    async def enqueue_signal(self, signal: ExecutionSignal) -> bool:
        """
        Enfileirar sinal para execução.
        
        Returns:
            True se enfileirado com sucesso
        """
        if not self.is_running:
            print(f"[HFTExecutionBridge] ⚠️ Bridge não está rodando, sinal descartado: {signal.symbol}")
            return False
        
        # Verificar se circuit breaker de execução está aberto
        if self._circuit_open:
            if time.time() < (self._circuit_open_until or 0):
                print(f"[HFTExecutionBridge] 🚫 Circuit breaker de execução ABERTO - sinal descartado")
                return False
            else:
                # Resetar circuit breaker
                self._circuit_open = False
                self._consecutive_failures = 0
                print(f"[HFTExecutionBridge] 🔓 Circuit breaker fechado, retomando execuções")
        
        async with self._lock:
            self.metrics.total_signals_received += 1
            
            # Idempotência: verificar se já existe ordem ativa para este ativo
            if signal.symbol in self.active_orders:
                existing_order = self.active_orders[signal.symbol]
                # Verificar se ordem já foi preenchida ou está muito antiga (> 2 min)
                if existing_order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                    # Remover ordem antiga
                    del self.active_orders[signal.symbol]
                elif (datetime.utcnow() - existing_order.created_at).seconds > 120:
                    # Ordem muito antiga, assumir que foi perdida
                    print(f"[HFTExecutionBridge] ⏰ Ordem antiga limpa: {signal.symbol}")
                    del self.active_orders[signal.symbol]
                else:
                    # Ordem ainda ativa, ignorar sinal (deduplicação)
                    self.metrics.signals_deduplicated += 1
                    if self.metrics.signals_deduplicated % 10 == 0:
                        print(f"[HFTExecutionBridge] 🔄 Deduplicação: {self.metrics.signals_deduplicated} sinais ignorados")
                    return False
        
        # Enfileirar sinal
        await self.queue.put(signal)
        return True
    
    async def _worker_loop(self, worker_id: int):
        """Loop de worker para processar sinais da fila"""
        print(f"[HFTExecutionBridge] Worker #{worker_id} iniciado")
        
        while self.is_running:
            try:
                # Aguardar sinal (com timeout para permitir verificação de is_running)
                signal = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                
                # Processar sinal
                await self._process_signal(signal)
                
                # Marcar tarefa como concluída
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                print(f"[HFTExecutionBridge] Worker #{worker_id} cancelado")
                break
            except Exception as e:
                print(f"[HFTExecutionBridge] Worker #{worker_id} erro: {e}")
                traceback.print_exc()
        
        print(f"[HFTExecutionBridge] Worker #{worker_id} encerrado")
    
    async def _process_signal(self, signal: ExecutionSignal):
        """Processar um sinal e executar ordem"""
        symbol = signal.symbol
        start_time = time.perf_counter()
        
        print(f"[HFTExecutionBridge] 📥 Processando sinal: {symbol} {signal.direction.upper()} @ {signal.price:.5f}")
        
        # Criar ordem
        order_id = f"hft_{symbol}_{int(time.time() * 1000)}"
        side = ExecutionSide.BUY if signal.direction == 'buy' else ExecutionSide.SELL
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            amount=signal.amount,
            entry_price=signal.price,
            status=OrderStatus.PENDING,
            created_at=datetime.utcnow(),
            signal_score=signal.score
        )
        
        # Registrar ordem como ativa
        async with self._lock:
            self.active_orders[symbol] = order
        
        # Tentar executar com retry
        success = False
        for attempt in range(self.max_retries + 1):
            try:
                order.retry_count = attempt
                
                if attempt > 0:
                    # Backoff exponencial entre tentativas
                    delay = self.retry_backoff_base * (2 ** (attempt - 1))
                    print(f"[HFTExecutionBridge] 🔄 Retry #{attempt} para {symbol} (delay: {delay}s)...")
                    await asyncio.sleep(delay)
                
                # Executar ordem na API
                order.status = OrderStatus.SUBMITTED
                api_result = await self._execute_order_api(order, signal)
                
                if api_result.get('success'):
                    order.status = OrderStatus.EXECUTED
                    order.executed_at = datetime.utcnow()
                    order.api_response = api_result
                    success = True
                    
                    # Resetar contador de falhas
                    self._consecutive_failures = 0
                    
                    print(f"[HFTExecutionBridge] ✅ Ordem executada: {order_id} - {symbol} {side.value}")
                    break
                else:
                    # API retornou erro
                    error_msg = api_result.get('error', 'Erro desconhecido da API')
                    raise Exception(error_msg)
                    
            except Exception as e:
                order.error_message = str(e)
                print(f"[HFTExecutionBridge] ❌ Tentativa {attempt + 1} falhou para {symbol}: {e}")
                
                if attempt == self.max_retries:
                    # Última tentativa falhou
                    order.status = OrderStatus.ERROR
                    self._consecutive_failures += 1
                    
                    # Verificar se deve abrir circuit breaker
                    if self.enable_circuit_breaker and self._consecutive_failures >= self.circuit_breaker_threshold:
                        self._circuit_open = True
                        self._circuit_open_until = time.time() + 60  # Fechar após 60s
                        print(f"[HFTExecutionBridge] 🚫 CIRCUIT BREAKER ABERTO! "
                              f"{self._consecutive_failures} falhas consecutivas. "
                              f"Pausando execuções por 60s.")
                    
                    # Callback de erro
                    if self._on_order_error:
                        try:
                            self._on_order_error(order, e)
                        except:
                            pass
        
        # Atualizar métricas
        latency_ms = (time.perf_counter() - start_time) * 1000
        self._latency_samples.append(latency_ms)
        
        async with self._lock:
            self.metrics.total_orders_submitted += 1
            if success:
                self.metrics.total_orders_executed += 1
            else:
                self.metrics.total_errors += 1
            
            # Manter apenas últimas 1000 amostras de latência
            if len(self._latency_samples) > 1000:
                self._latency_samples = self._latency_samples[-1000:]
            
            self.metrics.avg_latency_ms = sum(self._latency_samples) / len(self._latency_samples)
            self.metrics.max_latency_ms = max(self._latency_samples)
        
        # Mover para histórico
        async with self._lock:
            if symbol in self.active_orders:
                del self.active_orders[symbol]
            self.completed_orders[order_id] = order
        
        # Callback de sucesso
        if success and self._on_order_filled:
            try:
                self._on_order_filled(order)
            except:
                pass
    
    async def _execute_order_api(self, order: Order, signal: ExecutionSignal) -> Dict[str, Any]:
        """
        Executar ordem na API da PocketOption.
        
        Returns:
            Dict com 'success': bool e dados da resposta
        """
        if not self.api_client:
            # Modo simulado (para testes)
            await asyncio.sleep(0.001)  # Simular latência de rede
            
            # Simular 5% de falha aleatória
            import random
            if random.random() < 0.05:
                return {'success': False, 'error': 'Simulated API error'}
            
            return {
                'success': True,
                'order_id': order.order_id,
                'symbol': order.symbol,
                'side': order.side.value,
                'price': order.entry_price,
                'amount': order.amount,
                'timestamp': time.time()
            }
        
        # Integração real com API
        try:
            # Assumir que api_client tem método async send_order
            result = await self.api_client.send_order(
                symbol=order.symbol,
                side=order.side.value,
                amount=order.amount,
                price=order.entry_price,
                duration=signal.timeframe
            )
            return {'success': True, **result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def set_callbacks(
        self,
        on_order_filled: Optional[Callable[[Order], None]] = None,
        on_order_error: Optional[Callable[[Order, Exception], None]] = None
    ):
        """Configurar callbacks para eventos de ordem"""
        self._on_order_filled = on_order_filled
        self._on_order_error = on_order_error
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Obter métricas atuais"""
        async with self._lock:
            return {
                'metrics': self.metrics.to_dict(),
                'active_orders_count': len(self.active_orders),
                'queue_size': self.queue.qsize(),
                'circuit_breaker': {
                    'open': self._circuit_open,
                    'consecutive_failures': self._consecutive_failures,
                    'open_until': self._circuit_open_until
                }
            }
    
    async def _metrics_reporter(self):
        """Task para reportar métricas periodicamente"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Reportar a cada minuto
                
                if not self.is_running:
                    break
                
                metrics = await self.get_metrics()
                m = metrics['metrics']
                
                print(f"[HFTExecutionBridge] 📊 Métricas (1min): "
                      f"Signals: {m['total_signals']}, "
                      f"Orders: {m['orders_executed']}/{m['orders_submitted']}, "
                      f"Errors: {m['errors']}, "
                      f"Avg Latency: {m['avg_latency_ms']:.2f}ms, "
                      f"Deduplicated: {m['deduplicated']}")
                
                # Salvar no Redis
                await self._save_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[HFTExecutionBridge] Erro no reporter: {e}")
    
    async def _load_active_orders(self):
        """Carregar ordens ativas do Redis (recuperação após restart)"""
        if not self.redis:
            return
        
        try:
            data = await self.redis.get(self._redis_orders_key)
            if data:
                orders_dict = json.loads(data)
                async with self._lock:
                    for symbol, order_data in orders_dict.items():
                        # Recriar objeto Order
                        order = Order(
                            order_id=order_data['order_id'],
                            symbol=order_data['symbol'],
                            side=ExecutionSide(order_data['side']),
                            amount=order_data['amount'],
                            entry_price=order_data['entry_price'],
                            status=OrderStatus(order_data['status']),
                            created_at=datetime.fromisoformat(order_data['created_at']),
                            signal_score=order_data.get('signal_score', 0.0)
                        )
                        # Só restaurar se ainda relevante (< 2 min)
                        if (datetime.utcnow() - order.created_at).seconds < 120:
                            self.active_orders[symbol] = order
                
                print(f"[HFTExecutionBridge] 🔄 {len(self.active_orders)} ordens ativas recuperadas do Redis")
        except Exception as e:
            print(f"[HFTExecutionBridge] Erro ao carregar ordens: {e}")
    
    async def _save_active_orders(self):
        """Salvar ordens ativas no Redis"""
        if not self.redis:
            return
        
        try:
            async with self._lock:
                orders_dict = {}
                for symbol, order in self.active_orders.items():
                    orders_dict[symbol] = {
                        'order_id': order.order_id,
                        'symbol': order.symbol,
                        'side': order.side.value,
                        'amount': order.amount,
                        'entry_price': order.entry_price,
                        'status': order.status.value,
                        'created_at': order.created_at.isoformat(),
                        'signal_score': order.signal_score
                    }
                
                await self.redis.set(self._redis_orders_key, json.dumps(orders_dict))
        except Exception as e:
            print(f"[HFTExecutionBridge] Erro ao salvar ordens: {e}")
    
    async def _save_metrics(self):
        """Salvar métricas no Redis"""
        if not self.redis:
            return
        
        try:
            metrics_dict = {
                'timestamp': datetime.utcnow().isoformat(),
                **self.metrics.to_dict()
            }
            await self.redis.set(self._redis_metrics_key, json.dumps(metrics_dict))
        except Exception as e:
            print(f"[HFTExecutionBridge] Erro ao salvar métricas: {e}")
    
    def get_active_order_for_symbol(self, symbol: str) -> Optional[Order]:
        """Obter ordem ativa para um símbolo (para consulta externa)"""
        return self.active_orders.get(symbol)
    
    def is_order_active(self, symbol: str) -> bool:
        """Verificar se existe ordem ativa para um símbolo"""
        return symbol in self.active_orders


# Singleton global
_execution_bridge: Optional[HFTExecutionBridge] = None


def get_execution_bridge() -> Optional[HFTExecutionBridge]:
    """Obter instância global do execution bridge"""
    return _execution_bridge


def set_execution_bridge(bridge: HFTExecutionBridge):
    """Definir instância global do execution bridge"""
    global _execution_bridge
    _execution_bridge = bridge
