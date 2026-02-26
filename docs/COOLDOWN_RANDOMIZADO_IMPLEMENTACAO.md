# Cooldown Randomizado - Resumo de Implementação

## Funcionalidade Implementada

O sistema de cooldown agora suporta tempos randomizados quando configurado no formato "X-X".

## Formatos Suportados

### Cooldown Fixo
- `"300"` ou `300`: Cooldown fixo de 300 segundos
- `"0"`: Sem cooldown

### Cooldown Randomizado
- `"5-10"`: Cooldown aleatório entre 5 e 10 segundos (inclusive)
- `"10-30"`: Cooldown aleatório entre 10 e 30 segundos

## Alterações Realizadas

### 1. Novo Arquivo: `utils/cooldown_utils.py`
- Criada função `parse_cooldown()` que:
  - Aceita strings no formato "X-X" para cooldown randomizado
  - Aceita strings ou números para cooldown fixo
  - Retorna valor aleatório quando formato é "X-X"
  - Retorna valor fixo quando formato é "X" ou número

### 2. Modelo atualizado: `models/__init__.py`
- Campo `cooldown_seconds` alterado de `Integer` para `String`
- Comentário explicando o formato suportado

### 3. Trade Executor atualizado: `services/trade_executor.py`
- `_check_cooldown()`: Usa `parse_cooldown()` para interpretar o valor em tempo real
- `_apply_consecutive_stop_cooldown()`: Usa `parse_cooldown()` para interpretar o valor

### 4. Schemas atualizados: `schemas/__init__.py`
- `AutoTradeConfig`: `cooldown_seconds` alterado de `int` para `str`
- `AutoTradeConfigCreate`: `cooldown_seconds` alterado de `int` para `str`
- `AutoTradeConfigUpdate`: `cooldown_seconds` alterado de `Optional[int]` para `Optional[str]`

### 5. Migration criada: `migrations_alembic/versions/cooldown_randomized_change_cooldown_seconds_type.py`
- Converte coluna `cooldown_seconds` de INTEGER para TEXT
- Preserva dados existentes (convertendo números para strings)
- Inclui downgrade para reverter alteração

## Como Usar

### Configurar Cooldown Fixo
```python
config.cooldown_seconds = "300"  # 300 segundos fixos
```

### Configurar Cooldown Randomizado
```python
config.cooldown_seconds = "5-10"  # Entre 5 e 10 segundos aleatórios
```

## Comportamento

- Quando `cooldown_seconds` é `"0"` ou vazio: Sem cooldown
- Quando `cooldown_seconds` é `"X"`: Cooldown fixo de X segundos
- Quando `cooldown_seconds` é `"X-Y"`: Cooldown aleatório entre X e Y segundos
- A cada verificação de cooldown, se for randomizado, um novo valor é sorteado

## Notas Importantes

1. A migration deve ser executada para atualizar o banco de dados
2. Valores existentes são preservados (convertidos de INTEGER para TEXT)
3. O cooldown por ativo após loss (`_cooldown_duration = 30` em `realtime.py`) não foi alterado, pois é um cooldown diferente do configurado pelo usuário
4. Não há campos adicionais - tudo é interpretação do valor `cooldown_seconds`
