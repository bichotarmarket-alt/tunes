"""
================================================================================
CHECKLIST DE IMPLANTAÇÃO HFT - PRODUÇÃO SEGURA
================================================================================

Objetivo: Colocar o HFT Engine em produção sem risco de erro humano.
Timeline: 24-48h por fase, começando com 1 ativo.

================================================================================
FASE 1: PREPARAÇÃO DO AMBIENTE (Antes de tocar no código)
================================================================================

□ 1.1 Backup do sistema atual
    $ git status  # Verificar se está limpo
    $ git commit -m "Backup antes HFT"  # Commitar estado atual
    $ git tag pre-hft-$(date +%Y%m%d)

□ 1.2 Verificar Redis
    $ docker ps | grep redis
    # Se não tiver:
    $ docker run -d -p 6379:6379 --name redis-hft redis:latest
    $ redis-cli ping  # Deve retornar PONG

□ 1.3 Verificar dependências Python
    $ pip list | grep -E "aioredis|redis|numpy"
    # Se faltar:
    $ pip install aioredis redis numpy

□ 1.4 Preparar ambiente de teste
    - Criar conta demo PocketOption
    - Saldo inicial: $1000 (apenas para teste)
    - Ativar log detalhado: export LOG_LEVEL=DEBUG

□ 1.5 Criar diretório de logs HFT
    $ mkdir -p logs/hft
    $ touch logs/hft/README.md

================================================================================
FASE 2: INTEGRAÇÃO NO CÓDIGO (Copiar seções do HFT_INTEGRATION_CODE.py)
================================================================================

□ 2.1 Abrir realtime.py
    $ code services/data_collector/realtime.py

□ 2.2 Copiar IMPORTS (Topo do arquivo, após imports existentes)
    Linha ~30-40: Adicionar imports do HFT
    
□ 2.3 Copiar init_hft_engine() (Dentro do __init__)
    Linha ~140: Adicionar após self._storage_initialized = False
    NÃO ESQUECER: self.init_hft_engine()

□ 2.4 Copiar start_hft_engine() (Dentro do start())
    Linha ~430: Adicionar após self._start_ativos_monitoring()
    NÃO ESQUECER: await self.start_hft_engine()

□ 2.5 Copiar hook HFT (Modificar _on_ativos_stream_update)
    Encontrar método _on_ativos_stream_update (~linha 2770)
    Adicionar chamada ao processamento HFT no final

□ 2.6 Copiar stop_hft_engine() (Dentro do stop())
    Linha ~480: Adicionar antes do loop de disconnect dos clients
    NÃO ESQUECER: await self.stop_hft_engine()

□ 2.7 Copiar _hft_metrics_reporter() (Novo método)
    Adicionar após o último método da classe

□ 2.8 Configurar ativos HFT (No __init__)
    self.hft_symbols = ['EURUSD_otc']  # COMEÇAR COM 1!
    self.hft_enabled = True

□ 2.9 Adicionar endpoints API (No router)
    Editar: api/routers/monitoring.py
    Adicionar imports e endpoints @router.get("/hft/*")

================================================================================
FASE 3: TESTES LOCAIS (Antes de subir)
================================================================================

□ 3.1 Teste de importação
    $ python -c "from services.engine import AsyncAssetProcessorV2, HFTExecutionBridge"
    # Deve retornar sem erro

□ 3.2 Teste de sintaxe
    $ python -m py_compile services/data_collector/realtime.py
    # Deve retornar sem erro

□ 3.3 Teste de inicialização
    $ python -c "
    from services.data_collector.realtime import DataCollectorService
    dc = DataCollectorService()
    print('HFT symbols:', dc.hft_symbols)
    print('HFT enabled:', dc.hft_enabled)
    "
    # Deve mostrar ['EURUSD_otc'] e True

□ 3.4 Teste de stress (isolated)
    $ python -m services.engine.stress_test --ticks 1000
    # Deve passar todas validações

□ 3.5 Teste end-to-end (isolated)
    $ python -m services.engine.hft_e2e_test --ticks 1000
    # Deve mostrar "Sinais gerados > 0" e "CB bloqueou"

================================================================================
FASE 4: DEPLOYMENT EM DEMO (Com conta de teste)
================================================================================

□ 4.1 Iniciar sistema
    $ python run.py

□ 4.2 Verificar logs de inicialização
    Esperar ver:
    [HFT] 🚀 Inicializando HFT Engine...
    [HFT] ✅ Redis conectado
    [HFT] ✅ Execution bridge iniciado
    [HFT] ✅ Processor inicializado: EURUSD_otc
    [HFT] ✅ Engine ativo para: EURUSD_otc

□ 4.3 Verificar endpoints API
    $ curl http://localhost:8000/api/v1/hft/health
    {"status": "healthy"}
    
    $ curl http://localhost:8000/api/v1/hft/metrics
    {"status": "running", "metrics": {...}}

□ 4.4 Monitorar logs por 30 minutos
    $ tail -f logs/app.log | grep "\[HFT\]"
    
    Procurar:
    ✅ [HFT] 📊 Métricas (1min): Signals: X, Orders: Y
    ✅ [HFT] 🔒 EURUSD_otc CB: bloqueios, rate: Z%
    ✅ [HFT] 🎯 Ordem executada: EURUSD_otc
    
    ALERTAR se ver:
    ❌ [HFT] ❌ Erro na ordem
    ❌ [HFT] 🚫 CIRCUIT BREAKER ABERTO!

□ 4.5 Verificar métricas após 1h
    Sinais gerados: > 100
    Bloqueios CB: 10-30% (esperado)
    Ordens executadas: > 0
    Erros: < 5

□ 4.6 Verificar persistência Redis
    $ redis-cli keys "*EURUSD*"
    Deve mostrar chaves de estado persistido

================================================================================
FASE 5: VALIDAÇÃO 24-48H (Demo, 1 ativo)
================================================================================

□ 5.1 Criar planilha de acompanhamento
    Colunas: Hora, Sinais, Bloqueios CB, Ordens, P&L, Observações

□ 5.2 Coletar métricas a cada 6h
    $ curl http://localhost:8000/api/v1/hft/metrics >> logs/hft/metrics_$(date +%Y%m%d).json

□ 5.3 Verificar comportamento do CB
    - Mercado lateral → CB deve bloquear (ATR < 0.0005)
    - Tendência forte → CB deve liberar (ATR > 0.0005)

□ 5.4 Verificar idempotência
    - Mesmo sinal não deve gerar 2 ordens
    - Log: "Deduplicação: X sinais ignorados"

□ 5.5 Verificar latência
    Avg latency < 10ms por tick
    Bridge latency < 500ms por ordem

□ 5.6 Validar P&L (se houver execuções)
    Win rate > 55% (esperado)
    Nenhuma ordem duplicada

□ 5.7 Decisão GO/NO-GO
    ✅ GO se: < 5% erros, > 50% win rate, CB funcionando
    ❌ NO-GO se: > 10% erros, drift no saldo, CB sempre bloqueado

================================================================================
FASE 6: EXPANSÃO (Se GO na Fase 5)
================================================================================

□ 6.1 Adicionar 2º ativo
    Editar realtime.py:
    self.hft_symbols = ['EURUSD_otc', 'GBPUSD_otc']
    
□ 6.2 Configurar thresholds específicos
    No init_hft_engine, adicionar config por ativo:
    
    configs = {
        'EURUSD_otc': {'atr_threshold': 0.0005, 'threshold': 0.65},
        'GBPUSD_otc': {'atr_threshold': 0.0008, 'threshold': 0.68}
    }

□ 6.3 Reiniciar e monitorar (6h)
    Verificar logs de ambos os ativos
    Métricas por ativo separadas

□ 6.4 Adicionar 3º e 4º ativos (USDJPY, AUDUSD)
    Repetir 6.1-6.3

□ 6.5 Testar com Crypto (se desejado)
    configs['BTC_otc'] = {'atr_threshold': 0.0020, 'threshold': 0.72}

================================================================================
FASE 7: ROLLBACK (Se necessário)
================================================================================

□ 7.1 Identificar problema
    - Métricas degradando
    - Erros aumentando
    - P&L negativo consistente

□ 7.2 Desativar HFT imediatamente (sem restart)
    $ redis-cli set hft:emergency_stop "true"
    # Ou via API: POST /api/v1/hft/disable

□ 7.3 Parar sistema
    Ctrl+C ou docker stop

□ 7.4 Reverter código
    $ git checkout pre-hft-$(date +%Y%m%d)
    # Ou:
    $ git revert HEAD

□ 7.5 Restaurar Redis (se necessário)
    $ redis-cli FLUSHDB  # Limpa estado HFT

□ 7.6 Reiniciar sistema (sem HFT)
    $ python run.py

□ 7.7 Post-mortem
    Analisar logs/hft/metrics_*.json
    Identificar causa raiz
    Corrigir e recomeçar do Fase 4

================================================================================
CONFIGURAÇÕES POR ATIVO (Referência Rápida)
================================================================================

Ativo          ATR Threshold    Score Min    Característica
--------------- ---------------  ------------ ----------------
EURUSD_otc     0.0005 (0.05%)   0.65         Baixa volatilidade
GBPUSD_otc     0.0008 (0.08%)   0.68         Média volatilidade
USDJPY_otc     0.0010 (0.10%)   0.70         Alta volatilidade
AUDUSD_otc     0.0007 (0.07%)   0.68         Commodity-correl
BTC_otc        0.0020 (0.20%)   0.72         Alta volatilidade
ETH_otc        0.0018 (0.18%)   0.72         Alta volatilidade
#AAPL_otc      0.0015 (0.15%)   0.70         Ação (baixa liquidez OTC)
#TSLA_otc      0.0020 (0.20%)   0.72         Ação (alta volatilidade)

================================================================================
COMANDOS ÚTEIS (Referência Rápida)
================================================================================

# Ver logs HFT em tempo real
$ tail -f logs/app.log | grep "\[HFT\]"

# Métricas via curl
$ curl -s http://localhost:8000/api/v1/hft/metrics | python -m json.tool

# Ver estado Redis
$ redis-cli keys "*hft*"
$ redis-cli hgetall hft:active_orders

# Forçar circuit breaker aberto (emergência)
$ redis-cli set circuit_breaker:EURUSD_otc '{"is_active": false}'

# Resetar estado HFT
$ redis-cli FLUSHDB

# Estatísticas de performance
$ python -c "
import json, sys
m = json.load(sys.stdin)['metrics']
print(f\"Sinais: {m['total_signals']}\")
print(f\"Ordens: {m['orders_executed']}/{m['orders_submitted']}\")
print(f\"Latência: {m['avg_latency_ms']:.2f}ms\")
" < <(curl -s http://localhost:8000/api/v1/hft/metrics)

================================================================================
CONTATOS E RECURSOS
================================================================================

Documentação: services/engine/RESUMO_IMPLEMENTACAO.py
Código integração: services/engine/HFT_INTEGRATION_CODE.py
Stress test: python -m services.engine.stress_test
E2E test: python -m services.engine.hft_e2e_test

================================================================================
ASSINATURA DE CONCLUSÃO
================================================================================

Data de início: ___________
Responsável: _____________

Checklist completado:
□ Fase 1: Preparação
□ Fase 2: Integração
□ Fase 3: Testes Locais
□ Fase 4: Deploy Demo
□ Fase 5: Validação 24-48h
□ Fase 6: Expansão (se aplicável)

Status final: ___ GO  ___ NO-GO  ___ ROLLBACK

Observações:
_____________________________________________________________________________
_____________________________________________________________________________

================================================================================
"""
