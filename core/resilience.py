"""
Infraestrutura centralizada de resiliência para operações assíncronas

Fornece:
- Timeout rigoroso para operações IO
- Retry com backoff exponencial
- Circuit Breaker para proteção contra falhas em cascata
- Chaos Testing para validação de resiliência
- Métricas e logging estruturado

Uso principal: PocketOption client, Trade Executor, APIs externas
"""

import asyncio
import random
import time
from typing import Callable, Any, Awaitable, Optional, TypeVar, List
from enum import Enum
from dataclasses import dataclass, field
from functools import wraps
from loguru import logger

T = TypeVar("T")


class CircuitState(str, Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"      # Funcionamento normal
    OPEN = "open"          # Falha detectada, rejeitando chamadas
    HALF_OPEN = "half_open"  # Testando se recuperou


@dataclass
class ResilienceMetrics:
    """Métricas de execução para monitoramento"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    circuit_breaker_opens: int = 0
    retry_attempts: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 100.0
        return (self.successful_calls / self.total_calls) * 100


class CircuitBreaker:
    """
    Circuit Breaker thread-safe para proteção contra falhas em cascata
    
    CLOSED: Funcionamento normal
    OPEN: Rejeita chamadas após threshold de falhas
    HALF_OPEN: Testa se serviço recuperou após timeout
    
    Thread-safe: Todas as operações são protegidas por asyncio.Lock
    
    Args:
        failure_threshold: Número de falhas para abrir circuito
        recovery_timeout: Segundos para tentar recuperação
        name: Identificador para logging
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitState.CLOSED
        self._metrics = ResilienceMetrics()
        self._lock = asyncio.Lock()  # Thread-safety
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def metrics(self) -> ResilienceMetrics:
        return self._metrics
    
    async def _can_attempt(self) -> bool:
        """Verifica se pode tentar execução baseado no estado atual (thread-safe)"""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Verificar se passou tempo suficiente para testar recuperação
                if self._last_failure_time and (time.time() - self._last_failure_time > self.recovery_timeout):
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"CircuitBreaker [{self.name}] → HALF_OPEN (testando recuperação)")
                    return True
                return False
            
            # HALF_OPEN: permite uma tentativa de teste
            return True
    
    async def record_success(self):
        """Registra execução bem-sucedida (thread-safe)"""
        async with self._lock:
            self._failures = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"CircuitBreaker [{self.name}] → CLOSED (recuperado)")
            
            self._metrics.successful_calls += 1
            self._metrics.total_calls += 1
    
    async def record_failure(self, error: Optional[Exception] = None):
        """Registra falha de execução (thread-safe)"""
        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Falhou no teste, voltar para OPEN
                self._state = CircuitState.OPEN
                logger.warning(f"CircuitBreaker [{self.name}] → OPEN (falha no teste de recuperação)")
                self._metrics.circuit_breaker_opens += 1
            
            elif self._state == CircuitState.CLOSED and self._failures >= self.failure_threshold:
                # Atingiu threshold, abrir circuito
                self._state = CircuitState.OPEN
                logger.error(f"CircuitBreaker [{self.name}] → OPEN ({self._failures} falhas consecutivas)")
                self._metrics.circuit_breaker_opens += 1
            
            self._metrics.failed_calls += 1
            self._metrics.total_calls += 1
    
    async def record_timeout(self):
        """Registra timeout específico (thread-safe)"""
        async with self._lock:
            self._metrics.timeout_calls += 1
            await self._do_record_failure(asyncio.TimeoutError("Operation timeout"))
    
    async def _do_record_failure(self, error: Optional[Exception] = None):
        """Internal: Registra falha já dentro do lock"""
        self._failures += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"CircuitBreaker [{self.name}] → OPEN (falha no teste)")
            self._metrics.circuit_breaker_opens += 1
        
        elif self._state == CircuitState.CLOSED and self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.error(f"CircuitBreaker [{self.name}] → OPEN ({self._failures} falhas)")
            self._metrics.circuit_breaker_opens += 1
        
        self._metrics.failed_calls += 1
        self._metrics.total_calls += 1


class ResilienceExecutor:
    """
    Executor de operações com resiliência: timeout + retry + circuit breaker
    
    Args:
        timeout: Timeout em segundos para cada tentativa
        retries: Número de retries após falha (0 = sem retry)
        backoff_base: Base do backoff exponencial (multiplicador: 2^attempt)
        circuit_breaker: Instância do CircuitBreaker (opcional)
        name: Identificador para logging
        retry_exceptions: Lista de exceções que devem trigger retry (None = todas)
    
    Exemplo:
        executor = ResilienceExecutor(
            timeout=10.0,
            retries=2,
            circuit_breaker=CircuitBreaker(3, 60.0, "pocketoption")
        )
        
        result = await executor.execute(
            client.get_balance(),
            operation_name="get_balance"
        )
    """
    
    def __init__(
        self,
        timeout: float = 10.0,
        retries: int = 2,
        backoff_base: float = 0.5,
        circuit_breaker: Optional[CircuitBreaker] = None,
        name: str = "default",
        retry_exceptions: Optional[List[type]] = None
    ):
        self.timeout = timeout
        self.retries = retries
        self.backoff_base = backoff_base
        self.circuit_breaker = circuit_breaker
        self.name = name
        self.retry_exceptions = retry_exceptions or [Exception]
        self.metrics = ResilienceMetrics()
    
    async def execute(
        self,
        coro: Awaitable[T],
        operation_name: str = None
    ) -> T:
        """
        Executa coroutine com timeout, retry e circuit breaker
        
        Args:
            coro: Coroutine a ser executada
            operation_name: Nome da operação para logging
            
        Returns:
            Resultado da coroutine
            
        Raises:
            RuntimeError: Se circuit breaker estiver OPEN
            asyncio.TimeoutError: Se todas as tentativas timeout
            Exception: Última exceção após esgotar retries
        """
        op_name = operation_name or "unknown_operation"
        
        # Verificar circuit breaker (async)
        if self.circuit_breaker:
            can_attempt = await self.circuit_breaker._can_attempt()
            if not can_attempt:
                error_msg = f"Circuit breaker OPEN para [{self.circuit_breaker.name}] - rejeitando {op_name}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        
        last_exception: Optional[Exception] = None
        
        for attempt in range(self.retries + 1):
            try:
                logger.debug(f"[{self.name}] {op_name} - tentativa {attempt + 1}/{self.retries + 1}")
                
                # Executar com timeout
                result = await asyncio.wait_for(coro, timeout=self.timeout)
                
                # Sucesso: registrar e retornar (async)
                if self.circuit_breaker:
                    await self.circuit_breaker.record_success()
                
                self.metrics.successful_calls += 1
                self.metrics.total_calls += 1
                
                if attempt > 0:
                    logger.info(f"[{self.name}] {op_name} - sucesso após {attempt + 1} tentativas")
                
                return result
                
            except asyncio.TimeoutError as e:
                last_exception = e
                self.metrics.timeout_calls += 1
                
                # Registrar timeout (async)
                if self.circuit_breaker:
                    await self.circuit_breaker.record_timeout()
                
                if attempt < self.retries:
                    delay = self.backoff_base * (2 ** attempt)
                    logger.warning(
                        f"[{self.name}] {op_name} - timeout na tentativa {attempt + 1}, "
                        f"retry em {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                    self.metrics.retry_attempts += 1
                else:
                    logger.error(f"[{self.name}] {op_name} - timeout após {self.retries + 1} tentativas")
                    
            except Exception as e:
                last_exception = e
                
                # Verificar se deve fazer retry nesta exceção
                should_retry = any(isinstance(e, exc_type) for exc_type in self.retry_exceptions)
                
                if not should_retry or attempt >= self.retries:
                    # Última tentativa ou exceção não retryable
                    if self.circuit_breaker:
                        await self.circuit_breaker.record_failure(e)
                    
                    self.metrics.failed_calls += 1
                    self.metrics.total_calls += 1
                    
                    logger.error(f"[{self.name}] {op_name} - falha final: {type(e).__name__}: {e}")
                    raise
                
                # Retry com backoff
                delay = self.backoff_base * (2 ** attempt)
                logger.warning(
                    f"[{self.name}] {op_name} - falha na tentativa {attempt + 1}: "
                    f"{type(e).__name__}, retry em {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                self.metrics.retry_attempts += 1
        
        # Se chegou aqui, esgotou todas as tentativas
        if last_exception:
            raise last_exception
        
        raise RuntimeError(f"[{self.name}] {op_name} - falha inesperada após {self.retries + 1} tentativas")
    
    def get_metrics(self) -> dict:
        """Retorna métricas consolidadas do executor e circuit breaker"""
        metrics = {
            "executor": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "timeout_calls": self.metrics.timeout_calls,
                "retry_attempts": self.metrics.retry_attempts,
                "success_rate": f"{self.metrics.success_rate:.1f}%"
            },
            "config": {
                "timeout": self.timeout,
                "retries": self.retries,
                "backoff_base": self.backoff_base
            }
        }
        
        if self.circuit_breaker:
            metrics["circuit_breaker"] = {
                "name": self.circuit_breaker.name,
                "state": self.circuit_breaker.state.value,
                "failures": self.circuit_breaker._failures,
                "failure_threshold": self.circuit_breaker.failure_threshold,
                "recovery_timeout": self.circuit_breaker.recovery_timeout,
                "metrics": {
                    "total_calls": self.circuit_breaker.metrics.total_calls,
                    "successful_calls": self.circuit_breaker.metrics.successful_calls,
                    "failed_calls": self.circuit_breaker.metrics.failed_calls,
                    "circuit_breaker_opens": self.circuit_breaker.metrics.circuit_breaker_opens
                }
            }
        
        return metrics


# Instâncias pré-configuradas para uso comum

class ResiliencePresets:
    """Presets pré-configurados para cenários comuns"""
    
    @staticmethod
    def pocket_option_client() -> ResilienceExecutor:
        """Para operações do PocketOption (WebSocket)"""
        return ResilienceExecutor(
            timeout=10.0,
            retries=2,
            backoff_base=0.5,
            circuit_breaker=CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                name="pocketoption"
            ),
            name="pocketoption",
            retry_exceptions=[asyncio.TimeoutError, ConnectionError, OSError]
        )
    
    @staticmethod
    def trade_executor() -> ResilienceExecutor:
        """Para execução de trades (crítico)"""
        return ResilienceExecutor(
            timeout=15.0,
            retries=1,  # Poucos retries para não duplicar ordens
            backoff_base=1.0,
            circuit_breaker=CircuitBreaker(
                failure_threshold=2,
                recovery_timeout=30.0,
                name="trade_executor"
            ),
            name="trade_executor",
            retry_exceptions=[asyncio.TimeoutError]  # Só retry em timeout
        )
    
    @staticmethod
    def external_api() -> ResilienceExecutor:
        """Para APIs HTTP externas"""
        return ResilienceExecutor(
            timeout=10.0,
            retries=3,
            backoff_base=0.5,
            circuit_breaker=CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=120.0,
                name="external_api"
            ),
            name="external_api",
            retry_exceptions=[asyncio.TimeoutError, ConnectionError]
        )
    
    @staticmethod
    def telegram_notification() -> ResilienceExecutor:
        """Para notificações Telegram (não crítico)"""
        return ResilienceExecutor(
            timeout=5.0,
            retries=1,
            backoff_base=0.5,
            circuit_breaker=None,  # Sem circuit breaker para notificações
            name="telegram"
        )


def resilient(
    timeout: float = 10.0,
    retries: int = 2,
    backoff_base: float = 0.5,
    circuit_breaker: Optional[CircuitBreaker] = None,
    name: str = None
):
    """
    Decorator para tornar funções resistentes automaticamente
    
    Exemplo:
        @resilient(timeout=10.0, retries=2)
        async def fetch_data():
            return await external_api.get_data()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        executor = ResilienceExecutor(
            timeout=timeout,
            retries=retries,
            backoff_base=backoff_base,
            circuit_breaker=circuit_breaker,
            name=name or func.__name__
        )
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await executor.execute(
                func(*args, **kwargs),
                operation_name=func.__name__
            )
        
        # Expor métricas na função
        wrapper.get_metrics = executor.get_metrics
        
        return wrapper
    
    return decorator


# Exports
__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "ResilienceExecutor",
    "ResiliencePresets",
    "ResilienceMetrics",
    "ChaosInjector",
    "ChaosConfig",
    "resilient"
]


@dataclass
class ChaosConfig:
    """Configuração para injeção de falhas (chaos testing)"""
    enabled: bool = False
    failure_rate: float = 0.3  # 30% de chance de falha
    delay_seconds: float = 15.0  # Delay para simular timeout
    error_message: str = "Chaos: Simulated failure"
    
    # Cenários específicos
    timeout_scenario: bool = True  # Simular timeouts
    connection_error_scenario: bool = True  # Simular erros de conexão
    random_delay_scenario: bool = False  # Delay aleatório (não deterministico)


class ChaosInjector:
    """
    Injetor de falhas para Chaos Testing
    
    Permite simular falhas controladas para validar:
    - Circuit breaker
    - Retry mechanisms
    - Timeout handling
    - Recuperação de falhas
    
    Uso:
        chaos = ChaosInjector(ChaosConfig(enabled=True, failure_rate=0.3))
        await chaos.inject()  # 30% chance de falha
        
        # Ou com operação específica:
        await chaos.inject_operation("get_balance")
    
    Args:
        config: Configuração de chaos
        operation_filter: Lista de operações afetadas (None = todas)
    """
    
    def __init__(
        self,
        config: Optional[ChaosConfig] = None,
        operation_filter: Optional[list] = None
    ):
        self.config = config or ChaosConfig()
        self.operation_filter = operation_filter
        self._injected_count = 0
        self._passed_count = 0
    
    async def inject(self, operation: str = None) -> None:
        """
        Injeta falha baseada na configuração
        
        Args:
            operation: Nome da operação (para filtragem)
            
        Raises:
            asyncio.TimeoutError: Se simulando timeout
            ConnectionError: Se simulando erro de conexão
            RuntimeError: Falha genérica
        """
        if not self.config.enabled:
            return
        
        # Verificar filtro de operação
        if self.operation_filter and operation not in self.operation_filter:
            return
        
        # Verificar probabilidade de falha
        if random.random() >= self.config.failure_rate:
            self._passed_count += 1
            return
        
        self._injected_count += 1
        
        # Escolher tipo de falha
        if self.config.timeout_scenario:
            logger.warning(f"[CHAOS] Injecting timeout ({self.config.delay_seconds}s)")
            await asyncio.sleep(self.config.delay_seconds)
            raise asyncio.TimeoutError(f"[CHAOS] Simulated timeout after {self.config.delay_seconds}s")
        
        elif self.config.connection_error_scenario:
            logger.warning("[CHAOS] Injecting connection error")
            raise ConnectionError("[CHAOS] Simulated connection error")
        
        else:
            logger.warning(f"[CHAOS] Injecting generic failure: {self.config.error_message}")
            raise RuntimeError(self.config.error_message)
    
    async def inject_delay(self, min_delay: float = 0.1, max_delay: float = 2.0) -> None:
        """Injeta delay aleatório para simular latência de rede"""
        if not self.config.enabled or not self.config.random_delay_scenario:
            return
        
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"[CHAOS] Injecting delay: {delay:.2f}s")
        await asyncio.sleep(delay)
    
    def get_metrics(self) -> dict:
        """Retorna métricas de injeção de falhas"""
        total = self._injected_count + self._passed_count
        return {
            "enabled": self.config.enabled,
            "failure_rate": self.config.failure_rate,
            "injected_failures": self._injected_count,
            "passed_calls": self._passed_count,
            "total_calls": total,
            "injection_rate": self._injected_count / total if total > 0 else 0
        }
    
    def reset_metrics(self):
        """Reseta métricas de chaos"""
        self._injected_count = 0
        self._passed_count = 0


# Instância global de chaos (desabilitada por padrão)
chaos_injector = ChaosInjector(ChaosConfig(enabled=False))
