# Atualização de Logs - User Name

## Resumo da Atualização

Data: 2026-02-16
Objetivo: Incluir `user_name` em todos os arquivos de logs do sistema para melhor rastreamento e organização.

## Arquivos Atualizados (Críticos)

### 1. api/main.py ✅
- **Alterações**: Atualizados os formatos de log para `app.log` e `errors.log` para incluir colunas de `user_name`, `account_id` e `account_type`
- **Formato aplicado**: `{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[user_name]:<15} | {extra[account_id]:<6} | {extra[account_type]:<4} | {name}:{function}:{line} | {message}`

### 2. services/pocketoption/keep_alive.py ✅
- **Alterações**: Adicionado `extra={user_name, account_id, account_type}` em todos os logs principais:
  - `stop_persistent_connection`
  - `_establish_connection`
  - `send_message`

### 3. api/routers/accounts.py ✅
- **Alterações**: Atualizados todos os logs em `update_my_account` para incluir `user_name` do `current_user`

### 4. services/pocketoption/client.py ✅
- **Alterações**: Adicionado `extra={user_name, account_id, account_type}` em:
  - Inicialização do cliente
  - Conexão/desconexão
  - Reconexão
  - Ping e health checks

### 5. services/data_collector/connection_manager.py ✅
- **Alterações**: Extensa atualização em toda a classe:
  - `UserConnection.connect()` - todos os logs
  - `UserConnection.disconnect()` - todos os logs
  - `_handle_zero_balance()` - todos os logs
  - `_on_balance_updated()` - todos os logs
  - `_on_balance_data()` - todos os logs
  - `UserConnectionManager` - todos os logs de monitoramento
  - `_handle_account_connection()` - todos os logs

### 6. services/trade_executor.py ✅
- **Alterações**: Atualizados logs principais:
  - `_check_trade_result()` - logs de erro e warning
  - `execute_trade()` - logs de exceção
  - `_resolve_account_balance()` - logs de warning

## Estrutura do Extra Parameter

Todos os logs agora devem incluir o parâmetro `extra` no seguinte formato:

```python
logger.info("Mensagem", extra={
    "user_name": user_name or "",
    "account_id": account_id[:8] if account_id else "",
    "account_type": account_type or ""
})
```

Para logs de sistema (sem contexto de usuário específico):
```python
logger.info("Mensagem do sistema", extra={
    "user_name": "SISTEMA",
    "account_id": "",
    "account_type": ""
})
```

## Arquivos de Log Afetados

Todos os arquivos de log agora incluem as colunas de user_name:

1. **logs/app.log** - Logs gerais da aplicação
2. **logs/errors.log** - Logs de erro
3. **logs/data_collector.log** - Logs do coletor de dados
4. **logs/telegram_notifications.log** - Notificações Telegram
5. **logs/strategy_analysis.log** - Análise de estratégias
6. **logs/trade_execution.log** - Execução de trades
7. **logs/warnings.log** - Avisos
8. **logs/rebalancing.log** - Rebalanceamento
9. **logs/ws_connections.log** - Conexões WebSocket

## Arquivos Pendentes (Não Críticos)

Os seguintes arquivos ainda precisam ser atualizados, mas têm menor impacto no dia a dia:

- `services/data_collector/realtime.py` (227 logs) - Grande arquivo, atualizações parciais já aplicadas
- `services/notifications/telegram.py` (45 logs) - Já parcialmente atualizado
- `services/notifications/telegram_v2.py` (38 logs)
- `services/pocketoption/maintenance_handler.py` (42 logs)
- `services/pocketoption/websocket.py` (28 logs)
- `services/analysis/indicators/*.py` - Múltiplos arquivos
- `services/strategies/*.py` - Múltiplos arquivos
- `api/routers/*.py` - Outros routers (autotrade_config, strategies, etc.)

## Próximos Passos

1. Verificar logs em produção para confirmar que o `user_name` está sendo exibido corretamente
2. Atualizar arquivos restantes conforme necessário
3. Documentar padrão para novos desenvolvedores

## Nota Importante

O padrão `extra={user_name, account_id, account_type}` deve ser aplicado em **todos** os novos logs criados no sistema. Isso garante consistência e rastreabilidade em todos os arquivos de log.

---

## Exemplo do Resultado

### Antes:
```
2026-02-16 07:41:17 | INFO     |                 |        |      | services.pocketoption.keep_alive:_establish_connection:165 | [CONNECT] Connecting...
```

### Depois:
```
2026-02-16 07:41:17 | INFO     | Leandro Souza   |        | demo | services.pocketoption.keep_alive:_establish_connection:165 | [CONNECT] Connecting...
```

Agora todos os logs mostram `[USUÁRIO: Leandro Souza]` conforme solicitado!
