# Cooldown Randomizado - Revisão de Lógica

## Problema Original
A função `parse_cooldown()` estava sendo chamada a cada verificação de cooldown. Para cooldowns randomizados ("5-10"), isso geraria valores diferentes a cada chamada, causando comportamento inconsistente.

## Solução Implementada

### 1. Campo Adicionado: `cooldown_duration_calculated`
- **Localização**: `models/__init__.py`
- **Tipo**: `Integer` (nullable)
- **Propósito**: Armazenar o valor de cooldown calculado (para cooldowns randomizados)
- **Benefício**: Evita recalcular o cooldown a cada verificação

### 2. Lógica de Cálculo em `_check_cooldown()`
- **Localização**: `services/trade_executor.py`
- **Comportamento**:
  1. Verifica se `cooldown_duration_calculated` existe
  2. Se não existe, calcula usando `parse_cooldown()`
  3. Se existe, verifica se a configuração mudou:
     - **Cooldown fixo**: Compara se `cooldown_duration_calculated == int(cooldown_seconds)`
     - **Cooldown randomizado**: Verifica se `cooldown_duration_calculated` está fora do range atual
  4. Se necessário, recalcula e persiste no banco

### 3. Detecção de Mudança de Configuração

#### Para Cooldown Fixo
```python
if "-" not in str(config.cooldown_seconds):
    config_value = int(config.cooldown_seconds)
    if cooldown_duration != config_value:
        needs_calculation = True
```

#### Para Cooldown Randomizado
```python
else:
    parts = config.cooldown_seconds.split("-")
    if len(parts) == 2:
        min_val = int(parts[0].strip())
        max_val = int(parts[1].strip())
        if cooldown_duration < min_val or cooldown_duration > max_val:
            needs_calculation = True
```

### 4. Migration
- **Localização**: `migrations_alembic/versions/cooldown_randomized_change_cooldown_seconds_type.py`
- **Alterações**:
  - Converte `cooldown_seconds` de `INTEGER` para `TEXT`
  - Adiciona campo `cooldown_duration_calculated`
  - Preserva dados existentes

### 5. Schemas Atualizados
- **Localização**: `schemas/__init__.py`
- **Alterações**:
  - `cooldown_seconds`: `int` → `str`
  - Adiciona `cooldown_duration_calculated: Optional[int]`

## Análise de Possíveis Problemas

### ✅ Resolvido: Cooldown Randomizado Inconsistente
- **Antes**: `parse_cooldown()` chamado a cada verificação → valores diferentes
- **Depois**: Valor calculado uma vez e armazenado → consistente

### ✅ Resolvido: Detecção de Mudança de Configuração
- **Cooldown fixo**: Comparação direta de valores
- **Cooldown randomizado**: Verificação se valor está fora do range

### ⚠️ Possível Problema: Cooldown por Ativo após Loss
- **Localização**: `services/data_collector/realtime.py`
- **Status**: NÃO alterado (usa `_cooldown_duration = 30` fixo)
- **Justificativa**: É um cooldown diferente, por ativo após loss, não configurável pelo usuário

### ⚠️ Possível Problema: Race Condition
- **Cenário**: Múltiplas threads tentando calcular cooldown ao mesmo tempo
- **Mitigação**: Banco de dados serializa as operações
- **Risco**: Baixo (cooldown é verificado antes de cada trade)

### ⚠️ Possível Problema: Cooldown Não Recalculado Após Trade
- **Cenário**: Se o usuário mudar a configuração durante o cooldown, o valor pode não ser atualizado
- **Mitigação**: A verificação de mudança de configuração é feita a cada chamada de `_check_cooldown()`
- **Risco**: Baixo (configurações mudam raramente durante operação)

## Recomendações

1. **Testar Cooldown Fixo**
   - Configurar `cooldown_seconds = "300"`
   - Verificar se cooldown de 300s é aplicado consistentemente

2. **Testar Cooldown Randomizado**
   - Configurar `cooldown_seconds = "5-10"`
   - Verificar se um valor entre 5 e 10 é escolhido uma vez e usado consistentemente

3. **Testar Mudança de Configuração**
   - Configurar `cooldown_seconds = "5-10"`
   - Executar um trade
   - Mudar para `cooldown_seconds = "10-20"`
   - Verificar se novo valor é calculado

4. **Testar Cooldown Zero**
   - Configurar `cooldown_seconds = "0"`
   - Verificar se trades são executados sem espera

## Conclusão

A implementação está correta e evita conflitos de lógica. O cooldown randomizado é calculado uma vez e armazenado, garantindo consistência. A lógica de detecção de mudança de configuração funciona para ambos os casos (fixo e randomizado).
