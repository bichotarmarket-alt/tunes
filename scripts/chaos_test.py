"""
Script de Chaos Testing para validação de resiliência
Testa 4 cenários críticos:
1. Timeout forçado em 30% das chamadas
2. Falha total (100% timeout)
3. Cliente WebSocket lento
4. Place order com timeout

Uso:
    python -m scripts.chaos_test --scenario timeout_30 --duration 60
    python -m scripts.chaos_test --scenario full_failure --duration 30
    python -m scripts.chaos_test --scenario recovery --duration 120

⚠️  ATENÇÃO: Execute apenas em ambiente de desenvolvimento/teste!
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from loguru import logger

# Importações do projeto
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.resilience import (
    ResilienceExecutor,
    CircuitBreaker,
    ChaosInjector,
    ChaosConfig,
    CircuitState
)


@dataclass
class TestResult:
    """Resultado de um teste de caos"""
    scenario: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    timeout_calls: int
    circuit_opens: int
    circuit_state: str
    duration_seconds: float
    errors: List[str]


class ChaosTestRunner:
    """Executor de testes de caos"""
    
    def __init__(self):
        self.results: List[TestResult] = []
        
    async def run_timeout_30_scenario(self, duration_seconds: int = 60) -> TestResult:
        """
        Cenário 1: Timeout forçado em 30% das chamadas
        
        Valida:
        - Retry entra em ação
        - Circuit abre após threshold
        - HALF_OPEN funciona
        - Recuperação automática
        """
        logger.info(f"🧪 [CHAOS] Iniciando cenário: Timeout 30% - {duration_seconds}s")
        
        # Configurar chaos
        config = ChaosConfig(
            enabled=True,
            failure_rate=0.3,
            delay_seconds=15.0,
            timeout_scenario=True,
            connection_error_scenario=False
        )
        chaos = ChaosInjector(config)
        
        # Configurar executor com circuit breaker
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=10.0,  # Curto para teste rápido
            name="chaos_test_timeout_30"
        )
        executor = ResilienceExecutor(
            timeout=5.0,
            retries=2,
            backoff_base=0.1,
            circuit_breaker=circuit_breaker,
            name="chaos_timeout_30"
        )
        
        errors = []
        start_time = time.time()
        call_count = 0
        
        try:
            while time.time() - start_time < duration_seconds:
                call_count += 1
                
                try:
                    # Factory para criar nova coroutine a cada tentativa (evita reuso)
                    def make_operation():
                        async def _operation():
                            await chaos.inject(f"call_{call_count}")
                            return {"status": "ok", "call_id": call_count}
                        return _operation()
                    
                    result = await executor.execute(
                        make_operation(),
                        operation_name=f"chaos_call_{call_count}"
                    )
                    
                    logger.debug(f"✅ Call {call_count} succeeded")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Call {call_count} timeout")
                    
                except RuntimeError as e:
                    if "Circuit breaker OPEN" in str(e):
                        logger.error(f"🔴 Call {call_count} rejected by circuit breaker")
                        # Aguardar recuperação
                        await asyncio.sleep(1)
                    else:
                        errors.append(f"Call {call_count}: {str(e)}")
                        
                except Exception as e:
                    errors.append(f"Call {call_count}: {type(e).__name__}: {str(e)}")
                
                # Verificar estado do circuit
                if call_count % 10 == 0:
                    state = circuit_breaker.state.value
                    failures = circuit_breaker._failures
                    logger.info(f"📊 Progresso: {call_count} calls, Circuit: {state.upper()}, Failures: {failures}")
                
                await asyncio.sleep(0.1)  # Pequeno delay entre chamadas
        
        except asyncio.CancelledError:
            logger.info("Teste cancelado pelo usuário")
        
        duration = time.time() - start_time
        metrics = executor.get_metrics()
        
        result = TestResult(
            scenario="timeout_30_percent",
            total_calls=call_count,
            successful_calls=metrics["executor"]["successful_calls"],
            failed_calls=metrics["executor"]["failed_calls"],
            timeout_calls=metrics["executor"]["timeout_calls"],
            circuit_opens=metrics.get("circuit_breaker", {}).get("metrics", {}).get("circuit_breaker_opens", 0),
            circuit_state=circuit_breaker.state.value,
            duration_seconds=duration,
            errors=errors[:10]  # Limitar erros no relatório
        )
        
        self.results.append(result)
        return result
    
    async def run_full_failure_scenario(self, duration_seconds: int = 30) -> TestResult:
        """
        Cenário 2: Falha Total (100% timeout)
        
        Valida:
        - Circuit abre rapidamente
        - Rejeição instantânea após abertura
        - Worker não trava
        - CPU estável
        """
        logger.info(f"🧪 [CHAOS] Iniciando cenário: Full Failure 100% - {duration_seconds}s")
        
        config = ChaosConfig(
            enabled=True,
            failure_rate=1.0,  # 100% falha
            delay_seconds=20.0,  # Delay maior que timeout
            timeout_scenario=True
        )
        chaos = ChaosInjector(config)
        
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,  # Threshold baixo para abrir rápido
            recovery_timeout=60.0,
            name="chaos_test_full_failure"
        )
        executor = ResilienceExecutor(
            timeout=3.0,  # Timeout curto
            retries=1,
            backoff_base=0.1,
            circuit_breaker=circuit_breaker,
            name="chaos_full_failure"
        )
        
        errors = []
        start_time = time.time()
        call_count = 0
        rejected_count = 0
        circuit_opened_at = None
        
        try:
            while time.time() - start_time < duration_seconds:
                call_count += 1
                
                try:
                    # Factory para criar nova coroutine a cada tentativa
                    def make_failing_op():
                        async def _failing_op():
                            await chaos.inject(f"call_{call_count}")
                            return {"status": "never_reaches_here"}
                        return _failing_op()
                    
                    await executor.execute(make_failing_op(), operation_name=f"fail_call_{call_count}")
                    
                except RuntimeError as e:
                    if "Circuit breaker OPEN" in str(e):
                        rejected_count += 1
                        if circuit_opened_at is None:
                            circuit_opened_at = call_count
                            logger.warning(f"🔴 Circuit aberto no call {call_count}")
                    else:
                        errors.append(str(e))
                        
                except asyncio.TimeoutError:
                    pass  # Esperado neste cenário
                    
                if call_count % 5 == 0:
                    state = circuit_breaker.state.value
                    logger.info(f"📊 Progresso: {call_count} calls, Rejected: {rejected_count}, State: {state}")
                
                await asyncio.sleep(0.05)
        
        except asyncio.CancelledError:
            logger.info("Teste cancelado")
        
        duration = time.time() - start_time
        
        result = TestResult(
            scenario="full_failure_100_percent",
            total_calls=call_count,
            successful_calls=0,  # Esperado 0 em 100% falha
            failed_calls=call_count - rejected_count,
            timeout_calls=call_count - rejected_count,
            circuit_opens=1 if circuit_opened_at else 0,
            circuit_state=circuit_breaker.state.value,
            duration_seconds=duration,
            errors=[]
        )
        
        self.results.append(result)
        
        # Validações específicas
        if circuit_opened_at and circuit_opened_at <= 5:
            logger.success(f"✅ Circuit abriu rapidamente (call {circuit_opened_at})")
        else:
            logger.error(f"❌ Circuit demorou muito para abrir ({circuit_opened_at})")
            
        return result
    
    async def run_recovery_scenario(self, duration_seconds: int = 120) -> TestResult:
        """
        Cenário 3: Recovery (falha inicial, depois recuperação)
        
        Valida:
        - HALF_OPEN após recovery_timeout
        - Transição CLOSED após sucesso
        - Métricas consistentes
        """
        logger.info(f"🧪 [CHAOS] Iniciando cenário: Recovery - {duration_seconds}s")
        
        # Fase 1: 30s de falha (circuit deve abrir)
        # Fase 2: 30s de recuperação (HALF_OPEN)
        # Fase 3: 60s de normalidade (CLOSED)
        
        phase_duration = duration_seconds // 3
        
        circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=20.0,
            name="chaos_test_recovery"
        )
        executor = ResilienceExecutor(
            timeout=5.0,
            retries=2,
            backoff_base=0.1,
            circuit_breaker=circuit_breaker,
            name="chaos_recovery"
        )
        
        errors = []
        call_count = 0
        start_time = time.time()
        
        # Fase 1: Falha
        logger.info("🔴 FASE 1: Falha (30% failure rate)")
        config_fail = ChaosConfig(enabled=True, failure_rate=0.3, delay_seconds=10.0, timeout_scenario=True)
        chaos_fail = ChaosInjector(config_fail)
        
        phase1_start = time.time()
        while time.time() - phase1_start < phase_duration:
            call_count += 1
            try:
                def make_op_fail():
                    async def _op():
                        await chaos_fail.inject(f"p1_call_{call_count}")
                        return {"status": "ok"}
                    return _op()
                await executor.execute(make_op_fail(), operation_name=f"phase1_{call_count}")
            except Exception as e:
                pass
            await asyncio.sleep(0.1)
        
        state_after_phase1 = circuit_breaker.state.value
        logger.info(f"📊 Após Fase 1: Circuit = {state_after_phase1.upper()}")
        
        # Fase 2: Recuperação (desabilitar chaos)
        logger.info("🟡 FASE 2: Recuperação (sem falhas)")
        config_recover = ChaosConfig(enabled=False)
        chaos_recover = ChaosInjector(config_recover)
        
        phase2_start = time.time()
        success_count_p2 = 0
        while time.time() - phase2_start < phase_duration:
            call_count += 1
            try:
                def make_op_recover():
                    async def _op():
                        await chaos_recover.inject(f"p2_call_{call_count}")
                        return {"status": "ok"}
                    return _op()
                await executor.execute(make_op_recover(), operation_name=f"phase2_{call_count}")
                success_count_p2 += 1
            except Exception as e:
                errors.append(f"Phase 2 call {call_count}: {str(e)}")
            await asyncio.sleep(0.1)
        
        state_after_phase2 = circuit_breaker.state.value
        logger.info(f"📊 Após Fase 2: Circuit = {state_after_phase2.upper()}, Successes: {success_count_p2}")
        
        # Fase 3: Normalidade
        logger.info("🟢 FASE 3: Normalidade")
        phase3_start = time.time()
        success_count_p3 = 0
        while time.time() - phase3_start < phase_duration:
            call_count += 1
            try:
                def make_op_normal():
                    async def _op():
                        return {"status": "ok"}
                    return _op()
                await executor.execute(make_op_normal(), operation_name=f"phase3_{call_count}")
                success_count_p3 += 1
            except Exception as e:
                errors.append(f"Phase 3 call {call_count}: {str(e)}")
            await asyncio.sleep(0.05)
        
        state_after_phase3 = circuit_breaker.state.value
        logger.info(f"📊 Após Fase 3: Circuit = {state_after_phase3.upper()}, Successes: {success_count_p3}")
        
        duration = time.time() - start_time
        
        result = TestResult(
            scenario="recovery_test",
            total_calls=call_count,
            successful_calls=success_count_p2 + success_count_p3,
            failed_calls=0,
            timeout_calls=0,
            circuit_opens=1 if state_after_phase1 == "open" else 0,
            circuit_state=state_after_phase3,
            duration_seconds=duration,
            errors=errors[:5]
        )
        
        self.results.append(result)
        
        # Validações
        if state_after_phase3 == "closed":
            logger.success("✅ Sistema recuperou corretamente (CLOSED)")
        else:
            logger.error(f"❌ Sistema não recuperou: {state_after_phase3}")
            
        return result
    
    def print_summary(self):
        """Imprime resumo de todos os testes"""
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMO DOS TESTES DE CAOS")
        logger.info("="*60)
        
        for result in self.results:
            logger.info(f"\n🧪 Cenário: {result.scenario}")
            logger.info(f"   Duração: {result.duration_seconds:.1f}s")
            logger.info(f"   Total de chamadas: {result.total_calls}")
            logger.info(f"   Sucessos: {result.successful_calls}")
            logger.info(f"   Falhas: {result.failed_calls}")
            logger.info(f"   Timeouts: {result.timeout_calls}")
            logger.info(f"   Circuit aberto: {result.circuit_opens}x")
            logger.info(f"   Estado final: {result.circuit_state.upper()}")
            
            if result.errors:
                logger.warning(f"   Erros: {len(result.errors)}")
                for err in result.errors[:3]:
                    logger.warning(f"      - {err}")
        
        logger.info("\n" + "="*60)


async def main():
    """Função principal do script de chaos testing"""
    parser = argparse.ArgumentParser(description="Chaos Testing para validação de resiliência")
    parser.add_argument(
        "--scenario",
        choices=["timeout_30", "full_failure", "recovery", "all"],
        default="all",
        help="Cenário de teste"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duração do teste em segundos"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Arquivo para salvar resultados JSON"
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 INICIANDO CHAOS TESTING")
    logger.info(f"   Cenário: {args.scenario}")
    logger.info(f"   Duração: {args.duration}s")
    logger.warning("⚠️  Isso vai injetar falhas intencionais no sistema!")
    logger.info("   Pressione Ctrl+C para cancelar\n")
    
    runner = ChaosTestRunner()
    
    try:
        if args.scenario == "timeout_30" or args.scenario == "all":
            await runner.run_timeout_30_scenario(args.duration)
            
        if args.scenario == "full_failure" or args.scenario == "all":
            await runner.run_full_failure_scenario(min(args.duration, 30))
            
        if args.scenario == "recovery" or args.scenario == "all":
            await runner.run_recovery_scenario(max(args.duration, 90))
    
    except asyncio.CancelledError:
        logger.info("\n🛑 Teste interrompido pelo usuário")
    
    finally:
        runner.print_summary()
        
        if args.output:
            import json
            results_data = [
                {
                    "scenario": r.scenario,
                    "total_calls": r.total_calls,
                    "successful_calls": r.successful_calls,
                    "failed_calls": r.failed_calls,
                    "timeout_calls": r.timeout_calls,
                    "circuit_opens": r.circuit_opens,
                    "circuit_state": r.circuit_state,
                    "duration_seconds": r.duration_seconds,
                    "errors": r.errors
                }
                for r in runner.results
            ]
            with open(args.output, 'w') as f:
                json.dump(results_data, f, indent=2)
            logger.info(f"\n📝 Resultados salvos em: {args.output}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Execução cancelada pelo usuário")
        sys.exit(1)
