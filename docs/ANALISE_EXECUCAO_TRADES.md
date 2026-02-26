# Análise da Lógica de Execução de Trades

## Data: 2026-02-16
## Objetivo: Garantir execução de trades para múltiplos usuários sem delay e simultaneamente

---

## 🔍 PROBLEMAS IDENTIFICADOS

### 1. **LOCK POR CONTA - SERIALIZAÇÃO DE EXECUÇÃO** ⚠️ CRÍTICO
**Arquivo:** `services/trade_executor.py:909`

```python
async with account_lock:
    # Toda a lógica de execução está dentro do lock
    # Isso serializa trades da mesma conta
```

**Problema:** O `account_lock` é usado para cada conta individual, mas a execução de trades para uma mesma conta é serializada. Se um usuário tentar executar múltiplos trades simultaneamente (diferentes ativos), eles serão executados um por um.

**Impacto:**
- Um trade lento bloqueia outros trades da mesma conta
- Não aproveita conexões WebSocket simultâneas
- Atraso acumulativo entre operações

---

### 2. **VERIFICAÇÃO DE TRADES ATIVOS - BLOQUEIO GLOBAL** ⚠️ CRÍTICO
**Arquivo:** `services/trade_executor.py:954-957`

```python
# Verificar se há trades ativos para garantir funcionamento correto do soros/martingale
if not await self._check_no_active_trades(account.id):
    logger.info(f"[TradeExecutor] [{account.name}] Aguardando fechamento de trade anterior")
    return None
```

**Problema:** O sistema **BLOQUEIA** novos trades se houver qualquer trade ativo na conta. Isso impede execução paralela mesmo em ativos diferentes.

**Impacto:**
- Impossível executar trades simultâneos na mesma conta
- Sempre serializado, mesmo para ativos diferentes
- Perda de oportunidades de entrada

---

### 3. **COOLDOWN ENTRE OPERAÇÕES - DELAY FORÇADO** ⚠️ ALTO
**Arquivo:** `services/trade_executor.py:945-948`

```python
# Verificar cooldown (tempo mínimo entre operações)
if not await self._check_cooldown(autotrade_config, duration):
    return None
```

**Problema:** Cooldown aplicado globalmente por conta, não por ativo.

**Impacto:**
- Trades em ativos diferentes são bloqueados pelo cooldown
- Delay forçado entre operações independentes

---

### 4. **MONITORAMENTO SERIAL DE TRADES** ⚠️ MÉDIO
**Arquivo:** `services/trade_executor.py:244-296`

```python
async def _monitor_active_trades(self):
    while self._is_monitoring:
        await asyncio.sleep(60)  # Polling a cada 60s
        for trade in expired_trades:
            account_lock = self._get_account_lock(trade.account_id)
            async with account_lock:
                await self._check_trade_result(trade, db)
```

**Problema:** Verificação de trades expirados é feita sequencialmente com locks.

---

### 5. **CONEXÕES WEBSOCKET - LIMITAÇÃO POR CONTA** ⚠️ ALTO
**Arquivo:** `services/data_collector/connection_manager.py`

Cada conta tem no máximo 2 conexões (demo + real), mas o sistema não aproveita isso para execução paralela.

---

## ✅ PONTOS POSITIVOS

### 1. **TradeExecutor é Instanciado uma vez**
- Usado por múltiplos usuários simultaneamente
- `connection_manager` gerencia conexões de todos os usuários

### 2. **Locks são por Conta**
- Cada conta tem seu próprio `asyncio.Lock`
- Diferentes contas podem operar simultaneamente sem interferência

### 3. **Connection Manager Suporta Múltiplas Conexões**
```python
self.connections: Dict[str, UserConnection] = {}
# Key: "{account_id}_{connection_type}"
```

### 4. **Execução de Estratégias é Paralela**
O realtime.py parece processar sinais em paralelo para diferentes contas.

---

## 🎯 SOLUÇÕES PROPOSTAS

### SOLUÇÃO 1: **REMOVER BLOQUEIO DE TRADES ATIVOS POR ATIVO** 🔥 PRIORIDADE MÁXIMA

**Modificar:** `services/trade_executor.py:954-957`

**Atual:**
```python
if not await self._check_no_active_trades(account.id):
    return None
```

**Proposto:**
```python
# Verificar apenas trades ativos no MESMO ativo
if not await self._check_no_active_trades_for_asset(account.id, symbol):
    logger.info(f"[TradeExecutor] [{account.name}] Trade ativo no mesmo ativo {symbol}, aguardando...")
    return None
```

**Nova função:**
```python
async def _check_no_active_trades_for_asset(self, account_id: str, symbol: str) -> bool:
    """Verificar se há trades ativos apenas para o mesmo ativo"""
    async with get_db_context() as db:
        result = await db.execute(
            select(Trade).where(
                Trade.account_id == account_id,
                Trade.status == TradeStatus.ACTIVE,
                Trade.asset_id == ASSETS.get(symbol)  # Apenas mesmo ativo
            )
        )
        return len(result.scalars().all()) == 0
```

---

### SOLUÇÃO 2: **REDUZIR ESCOPO DO LOCK** 🔥 PRIORIDADE MÁXIMA

**Modificar:** `services/trade_executor.py:909`

**Atual:**
```python
async with account_lock:
    # TODAS as verificações e execução dentro do lock
    # ~100 linhas de código
```

**Proposto:**
```python
# Verificações prévias SEM lock (só leitura)
if not await self._check_cooldown(autotrade_config, duration):
    return None
if not await self._check_daily_limits(autotrade_config):
    return None

# Lock APENAS para operações críticas (escrita no banco)
async with account_lock:
    # Recarregar config dentro do lock
    autotrade_config = await self._get_autotrade_config(account.id)
    
    # Verificar novamente condições que podem mudar
    if not autotrade_config or not autotrade_config.is_active:
        return None
    
    # Executar trade
    trade = await self._place_order(...)
    
    if trade:
        await self._update_autotrade_counters_after_trade(trade, autotrade_config, db)

# Lock liberado imediatamente após execução
```

---

### SOLUÇÃO 3: **COOLDOWN POR ATIVO EM VEZ DE GLOBAL** 🔥 PRIORIDADE ALTA

**Modificar:** `services/trade_executor.py:1422`

**Atual:**
```python
async def _check_cooldown(self, config: AutoTradeConfig, duration: int = None) -> bool:
    # Usa config.last_trade_time global
```

**Proposto:**
```python
async def _check_cooldown_for_asset(self, config: AutoTradeConfig, symbol: str, duration: int = None) -> bool:
    """Verificar cooldown específico por ativo"""
    # Verificar se há trades recentes no MESMO ativo
    async with get_db_context() as db:
        recent_trade = await db.execute(
            select(Trade).where(
                Trade.account_id == config.account_id,
                Trade.status.in_([TradeStatus.ACTIVE, TradeStatus.WIN, TradeStatus.LOSS]),
                Trade.asset_id == ASSETS.get(symbol),
                Trade.placed_at >= datetime.utcnow() - timedelta(seconds=config.cooldown_seconds or 0)
            ).order_by(Trade.placed_at.desc()).limit(1)
        )
        return recent_trade.scalar_one_or_none() is None
```

---

### SOLUÇÃO 4: **EXECUÇÃO PARALELA COM SEMÁFORO** 🔥 PRIORIDADE ALTA

**Adicionar ao TradeExecutor:**

```python
class TradeExecutor:
    def __init__(self, connection_manager):
        # ... existente ...
        self._execution_semaphore = asyncio.Semaphore(10)  # Max 10 execuções simultâneas
    
    async def execute_trade(self, ...):
        # ... código anterior ...
        
        # Usar semáforo para limitar execuções paralelas
        async with self._execution_semaphore:
            return await self._execute_trade_internal(...)
```

---

### SOLUÇÃO 5: **TASK GROUP PARA EXECUÇÃO SIMULTÂNEA** 🔥 PRIORIDADE ALTA

**No realtime.py quando processar múltiplos sinais:**

```python
async def _execute_strategies_for_candle_close(self, ...):
    # ... código existente ...
    
    # Criar lista de tarefas para execução paralela
    tasks = []
    for config in active_configs:
        for signal in signals:
            task = asyncio.create_task(
                self.trade_executor.execute_trade(
                    signal=signal,
                    symbol=symbol,
                    timeframe_seconds=timeframe,
                    strategy_name=strategy_name,
                    account_id=config.account_id,
                    autotrade_config=config
                )
            )
            tasks.append(task)
    
    # Executar todas simultaneamente
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 📊 IMPACTO ESPERADO DAS MUDANÇAS

| Mudança | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Execução por conta | Serial (1 trade por vez) | Paralela (múltiplos ativos) | 5-10x mais rápido |
| Bloqueio de trades ativos | Global (qualquer ativo) | Por ativo | Elimina atraso desnecessário |
| Cooldown | Global por conta | Por ativo | Mais oportunidades de entrada |
| Uso de WebSocket | Subutilizado | Máximo aproveitamento | Melhor performance |

---

## ⚡ IMPLEMENTAÇÃO RECOMENDADA

### FASE 1 (Imediata) - Correções Críticas:
1. Modificar `_check_no_active_trades` para verificar apenas o mesmo ativo
2. Reduzir escopo do `account_lock`
3. Testar com 2-3 usuários simultâneos

### FASE 2 (Curto prazo) - Otimizações:
4. Implementar cooldown por ativo
5. Adicionar semáforo de execução
6. Otimizar verificações de pré-execução

### FASE 3 (Médio prazo) - Melhorias Avançadas:
7. Implementar execução com Task Groups
8. Adicionar métricas de performance
9. Criar testes de carga

---

## 🧪 TESTES RECOMENDADOS

### Teste 1: Execução Simultânea
```python
# Simular 3 usuários tentando executar trades ao mesmo tempo
async def test_concurrent_execution():
    tasks = [
        trade_executor.execute_trade(user1_signal),
        trade_executor.execute_trade(user2_signal),
        trade_executor.execute_trade(user3_signal),
    ]
    results = await asyncio.gather(*tasks)
    # Verificar se todos executaram sem delay significativo
```

### Teste 2: Múltiplos Ativos Mesmo Usuário
```python
# Um usuário tentando operar 3 ativos diferentes simultaneamente
async def test_multi_asset():
    tasks = [
        trade_executor.execute_trade(asset="EURUSD", user=user1),
        trade_executor.execute_trade(asset="GBPUSD", user=user1),
        trade_executor.execute_trade(asset="USDJPY", user=user1),
    ]
    results = await asyncio.gather(*tasks)
    # Verificar se todos executaram (não apenas o primeiro)
```

---

## 📝 RESUMO EXECUTIVO

**Status Atual:** ❌ Não otimizado para execução simultânea
- Bloqueio global por trades ativos impede paralelismo
- Lock por conta serializa operações
- Cooldown global limita oportunidades

**Status Após Correções:** ✅ Suporta execução massivamente paralela
- Múltiplos usuários podem operar simultaneamente
- Mesmo usuário pode operar múltiplos ativos ao mesmo tempo
- Sem delays artificiais entre operações

**Esforço de Implementação:** 2-3 dias de trabalho
**Risco:** Baixo (mudanças localizadas)
**Benefício:** Alto (melhoria significativa de performance)
