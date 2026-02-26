# Plano de Implementação: Execução no Sinal vs Saída da Vela

## Visão Geral
Implementar suporte para dois modos de execução de trades:
1. **Executar Trade No Sinal** (`on_signal`) - Executar imediatamente quando o sinal é detectado
2. **Executar Trade Na Saída da Vela** (`on_candle_close`) - Aguardar o fechamento da vela para executar

## Arquitetura Proposta

### 1. Componentes Principais

#### A. TradeTimingManager (Novo)
Responsável por gerenciar o timing de execução de trades.

**Responsabilidades:**
- Rastrear sinais pendentes para execução no fechamento da vela
- Monitorar fechamento de velas por timeframe
- Executar trades agendados no momento exato do fechamento
- Validar se o sinal ainda é válido no fechamento

**Estrutura de Dados:**
```python
class PendingTrade:
    signal: Dict[str, Any]
    symbol: str
    timeframe: int
    strategy_id: str
    account_id: str
    autotrade_config: Dict[str, Any]
    scheduled_for: float  # Timestamp do fechamento da vela
    created_at: float  # Timestamp quando o sinal foi criado
```

#### B. CandleCloseTracker (Novo)
Responsável por rastrear o fechamento de velas.

**Responsabilidades:**
- Monitorar atualizações de candles
- Detectar quando uma vela fecha
- Notificar o TradeTimingManager quando uma vela fecha
- Calcular o timestamp do próximo fechamento da vela

**Lógica de Detecção:**
```python
def on_candle_update(symbol, timeframe, candle):
    # Calcular tempo até o fechamento da vela
    current_time = time.time()
    candle_time = candle['time']
    timeframe_seconds = timeframe
    
    # Calcular início da vela atual
    candle_start = (candle_time // timeframe_seconds) * timeframe_seconds
    candle_end = candle_start + timeframe_seconds
    
    # Se estamos dentro da janela de fechamento (últimos 100ms)
    if candle_end - current_time <= 0.1:
        # Vela está fechando
        notify_candle_close(symbol, timeframe, candle_end)
```

#### C. Modificação em TradeExecutor
Adicionar suporte para verificar o modo de execução.

**Modificações:**
```python
async def execute_trade(self, signal, symbol, timeframe, strategy_name, account_id, autotrade_config):
    # Verificar trade_timing da configuração
    trade_timing = autotrade_config.get('trade_timing', 'on_signal')
    
    if trade_timing == 'on_signal':
        # Execução atual: executar imediatamente
        return await self._execute_trade_immediate(signal, symbol, timeframe, ...)
    elif trade_timing == 'on_candle_close':
        # Nova: agendar para fechamento da vela
        return await self._schedule_trade_for_candle_close(signal, symbol, timeframe, ...)
```

### 2. Fluxo de Execução

#### Modo: Executar Trade No Sinal (Atual)
```
1. Sinal detectado
2. Verificar cooldown, stop loss, etc.
3. Executar trade imediatamente
4. Salvar no banco
```

#### Modo: Executar Trade Na Saída da Vela (Novo)
```
1. Sinal detectado
2. Verificar cooldown, stop loss, etc.
3. Calcular timestamp do próximo fechamento da vela
4. Salvar sinal pendente no TradeTimingManager
5. Aguardar fechamento da vela
6. No fechamento:
   - Validar se o sinal ainda é válido
   - Executar trade
   - Remover sinal pendente
```

### 3. Sincronização Perfeita na Saída da Vela

#### A. Cálculo do Timestamp de Fechamento
```python
def calculate_next_candle_close(current_time, timeframe):
    """Calcular timestamp do próximo fechamento da vela"""
    candle_start = (current_time // timeframe) * timeframe
    candle_end = candle_start + timeframe
    return candle_end
```

#### B. Execução no Momento Exato
```python
async def execute_on_candle_close(pending_trade):
    """Executar trade no momento exato do fechamento"""
    # Calcular tempo até o fechamento
    now = time.time()
    time_until_close = pending_trade.scheduled_for - now
    
    # Aguardar até o fechamento (com margem de segurança)
    if time_until_close > 0:
        await asyncio.sleep(time_until_close - 0.05)  # 50ms antes
    
    # Verificar se ainda estamos na janela de fechamento
    now = time.time()
    if abs(now - pending_trade.scheduled_for) > 0.5:  # 500ms de tolerância
        logger.warning(f"Trade agendado expirou: {now - pending_trade.scheduled_for:.3f}s")
        return None
    
    # Validar sinal
    if not validate_signal(pending_trade.signal, pending_trade.symbol, pending_trade.timeframe):
        logger.info(f"Sinal inválido no fechamento, cancelando trade")
        return None
    
    # Executar trade
    return await execute_trade_immediate(...)
```

#### C. Validação do Sinal no Fechamento
```python
def validate_signal(signal, symbol, timeframe):
    """Validar se o sinal ainda é válido no fechamento"""
    # Recalcular indicadores no fechamento
    current_candles = get_candles(symbol, timeframe)
    
    # Verificar se a direção do sinal ainda é válida
    if signal.signal_type == 'call':
        # Verificar se ainda é um sinal de CALL
        return is_call_signal(current_candles)
    elif signal.signal_type == 'put':
        # Verificar se ainda é um sinal de PUT
        return is_put_signal(current_candles)
    
    return False
```

### 4. Integração com Backend

#### A. Adicionar campo trade_timing ao modelo
```python
# models/__init__.py
class AutoTradeConfig(Base):
    # ... campos existentes ...
    trade_timing: str = Column(String, default='on_signal')  # 'on_signal' ou 'on_candle_close'
```

#### B. Atualizar schemas
```python
# schemas/__init__.py
class AutoTradeConfigCreate(BaseModel):
    # ... campos existentes ...
    trade_timing: Optional[str] = 'on_signal'
```

#### C. Atualizar API
```python
# api/routers/autotrade_config.py
@router.post("/", response_model=AutoTradeConfigResponse)
async def create_autotrade_config(config: AutoTradeConfigCreate, ...):
    # trade_timing já está incluído
    ...
```

### 5. Gerenciamento de Sinais Pendentes

#### A. Armazenamento
```python
class TradeTimingManager:
    def __init__(self):
        self.pending_trades: Dict[str, PendingTrade] = {}  # key: f"{symbol}_{timeframe}_{account_id}"
    
    def add_pending_trade(self, signal, symbol, timeframe, account_id, autotrade_config):
        key = f"{symbol}_{timeframe}_{account_id}"
        scheduled_for = calculate_next_candle_close(time.time(), timeframe)
        
        pending_trade = PendingTrade(
            signal=signal,
            symbol=symbol,
            timeframe=timeframe,
            strategy_id=autotrade_config['strategy_id'],
            account_id=account_id,
            autotrade_config=autotrade_config,
            scheduled_for=scheduled_for,
            created_at=time.time()
        )
        
        self.pending_trades[key] = pending_trade
        logger.info(f"Trade agendado para fechamento da vela: {symbol} {timeframe}s @ {scheduled_for}")
    
    def get_pending_trades_for_candle_close(self, symbol, timeframe, close_time):
        """Obter trades pendentes para este fechamento de vela"""
        trades = []
        for key, pending in self.pending_trades.items():
            if (pending.symbol == symbol and 
                pending.timeframe == timeframe and 
                abs(pending.scheduled_for - close_time) < 1.0):
                trades.append(pending)
        return trades
    
    def remove_pending_trade(self, key):
        if key in self.pending_trades:
            del self.pending_trades[key]
```

#### B. Execução no Fechamento
```python
async def on_candle_close(symbol, timeframe, close_time):
    """Callback quando uma vela fecha"""
    pending_trades = trade_timing_manager.get_pending_trades_for_candle_close(symbol, timeframe, close_time)
    
    for pending in pending_trades:
        try:
            # Executar trade
            trade = await execute_on_candle_close(pending)
            
            if trade:
                logger.success(f"Trade executado no fechamento: {symbol} {timeframe}s")
            else:
                logger.warning(f"Trade não executado no fechamento: {symbol} {timeframe}s")
            
            # Remover trade pendente
            key = f"{pending.symbol}_{pending.timeframe}_{pending.account_id}"
            trade_timing_manager.remove_pending_trade(key)
        except Exception as e:
            logger.error(f"Erro ao executar trade agendado: {e}")
```

### 6. Integração com Realtime Data Collector

#### A. Adicionar callback de fechamento de vela
```python
# services/data_collector/realtime.py
class RealtimeDataCollector:
    def __init__(self):
        # ... código existente ...
        self.candle_close_callbacks = []
    
    def add_candle_close_callback(self, callback):
        """Adicionar callback para fechamento de vela"""
        self.candle_close_callbacks.append(callback)
    
    def on_candle_update(self, symbol, timeframe, candle):
        """Chamado quando um candle é atualizado"""
        # ... código existente ...
        
        # Verificar se a vela está fechando
        current_time = time.time()
        candle_time = candle['time']
        timeframe_seconds = timeframe
        
        candle_start = (candle_time // timeframe_seconds) * timeframe_seconds
        candle_end = candle_start + timeframe_seconds
        
        # Se estamos dentro da janela de fechamento
        if candle_end - current_time <= 0.1:
            # Notificar callbacks
            for callback in self.candle_close_callbacks:
                asyncio.create_task(callback(symbol, timeframe, candle_end))
```

### 7. Considerações Importantes

#### A. Validação de Sinal no Fechamento
- Recalcular indicadores no fechamento
- Verificar se a direção ainda é válida
- Verificar se outros sinais não conflitantes apareceram

#### B. Limites de Tempo
- Sinal expira se não for executado dentro de 500ms do fechamento
- Trade não é executado se o fechamento ocorrer muito tarde

#### C. Concorrência
- Usar locks para evitar múltiplas execuções do mesmo trade
- Verificar se já existe um trade pendente para o mesmo ativo/timeframe/conta

#### D. Logs
- Logar quando um trade é agendado
- Logar quando um trade é executado no fechamento
- Logar quando um trade é cancelado (sinal inválido)

### 8. Ordem de Implementação

1. **Fase 1: Infraestrutura**
   - Criar `TradeTimingManager`
   - Criar `CandleCloseTracker`
   - Adicionar campo `trade_timing` ao modelo e schema

2. **Fase 2: Integração**
   - Modificar `TradeExecutor` para verificar `trade_timing`
   - Adicionar callback de fechamento de vela em `RealtimeDataCollector`
   - Implementar agendamento de trades

3. **Fase 3: Execução**
   - Implementar execução no fechamento da vela
   - Implementar validação de sinal no fechamento
   - Adicionar logs detalhados

4. **Fase 4: Testes**
   - Testar execução no sinal (comportamento existente)
   - Testar execução no fechamento da vela
   - Testar sincronização perfeita
   - Testar validação de sinal

### 9. Exemplo de Uso

```python
# Configuração com execução no sinal (padrão)
config = {
    'trade_timing': 'on_signal',
    # ... outras configs ...
}

# Configuração com execução no fechamento da vela
config = {
    'trade_timing': 'on_candle_close',
    # ... outras configs ...
}
```

## Benefícios

1. **Flexibilidade**: Usuários podem escolher o modo de execução
2. **Precisão**: Execução no fechamento da vela garante entrada no preço exato
3. **Validação**: Sinais são validados novamente no fechamento
4. **Sincronização**: Garantia de execução no momento exato do fechamento
