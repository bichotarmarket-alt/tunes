"""
Endpoint de health check para métricas de resiliência
Exibe estado do circuit breaker, métricas de execução e chaos testing
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any

from core.resilience import (
    ResiliencePresets,
    ChaosInjector,
    ChaosConfig,
    chaos_injector
)
from core.security import require_admin

router = APIRouter(prefix="/health", tags=["health"])

# Cache dos executores para métricas
_executors = {}


def register_executor(name: str, executor):
    """Registra um executor para monitoramento"""
    _executors[name] = executor


@router.get("/resilience")
async def get_resilience_metrics(admin=Depends(require_admin)) -> Dict[str, Any]:
    """
    Retorna métricas completas de resiliência (requer admin)
    
    Inclui:
    - Estado do circuit breaker (CLOSED/OPEN/HALF_OPEN)
    - Taxa de sucesso/falha/timeout
    - Métricas de retry
    - Estado do chaos testing (se ativo)
    """
    metrics = {
        "presets": {},
        "registered_executors": {},
        "chaos": chaos_injector.get_metrics()
    }
    
    # Métricas dos presets
    presets = {
        "pocket_option": ResiliencePresets.pocket_option_client(),
        "trade_executor": ResiliencePresets.trade_executor(),
        "external_api": ResiliencePresets.external_api(),
        "telegram": ResiliencePresets.telegram_notification()
    }
    
    for name, executor in presets.items():
        metrics["presets"][name] = executor.get_metrics()
    
    # Métricas de executores registrados em runtime
    for name, executor in _executors.items():
        metrics["registered_executors"][name] = executor.get_metrics()
    
    return metrics


@router.post("/chaos/enable")
async def enable_chaos_testing(
    failure_rate: float = 0.3,
    scenario: str = "timeout",
    admin=Depends(require_admin)
) -> Dict[str, Any]:
    """
    Ativa modo de chaos testing com falhas simuladas
    
    Args:
        failure_rate: Taxa de falhas (0.0 a 1.0)
        scenario: Tipo de falha ('timeout', 'connection', 'mixed')
    """
    global chaos_injector
    
    config = ChaosConfig(
        enabled=True,
        failure_rate=failure_rate,
        delay_seconds=15.0 if scenario in ["timeout", "mixed"] else 0,
        timeout_scenario=scenario in ["timeout", "mixed"],
        connection_error_scenario=scenario in ["connection", "mixed"]
    )
    
    chaos_injector = ChaosInjector(config)
    
    return {
        "status": "enabled",
        "config": {
            "failure_rate": failure_rate,
            "scenario": scenario,
            "timeout_seconds": config.delay_seconds if config.timeout_scenario else None
        },
        "warning": "Chaos testing ativo - falhas serão injetadas intencionalmente!"
    }


@router.post("/chaos/disable")
async def disable_chaos_testing(admin=Depends(require_admin)) -> Dict[str, Any]:
    """Desativa modo de chaos testing"""
    global chaos_injector
    
    final_metrics = chaos_injector.get_metrics()
    chaos_injector = ChaosInjector(ChaosConfig(enabled=False))
    
    return {
        "status": "disabled",
        "final_metrics": final_metrics
    }


@router.get("/chaos/status")
async def get_chaos_status(admin=Depends(require_admin)) -> Dict[str, Any]:
    """Retorna status atual do chaos testing"""
    return {
        **chaos_injector.get_metrics(),
        "is_active": chaos_injector.config.enabled
    }
