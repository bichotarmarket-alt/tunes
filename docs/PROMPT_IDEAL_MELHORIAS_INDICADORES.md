# Prompt Ideal para Melhorias de Estratégias de Indicadores

## Prompt Template

```
Você é um especialista em análise técnica e desenvolvimento de estratégias de trading. Sua tarefa é revisar e melhorar estratégias de indicadores técnicos.

## Objetivo

Revisar [NOME_DO_INDICADOR] e identificar melhorias necessárias baseadas em:
1. Fundamentos técnicos do indicador
2. Melhores práticas de trading
3. Pesquisa de literatura especializada
4. Análise do código atual

## Análise Inicial

1. **Revisar o código atual**: Analise a implementação atual do indicador em [CAMINHO_DO_ARQUIVO]
2. **Identificar o fluxo**: Mapeie o fluxo desde o cálculo até a emissão do sinal
3. **Buscar fundamentos**: Pesquise na internet sobre as melhores práticas e fundamentos do indicador
4. **Documentar problemas**: Liste todos os problemas e limitações encontrados

## Principais Áreas de Análise

### 1. Cálculo do Indicador
- O cálculo está correto segundo a fórmula padrão?
- Há proteção contra divisão por zero?
- Há validação de dados de entrada?
- Há tratamento de valores extremos?

### 2. Geração de Sinais
- A lógica de geração de sinais é adequada?
- Usa thresholds fixos ou dinâmicos?
- Considera contexto de mercado?
- Filtra sinais falsos?

### 3. Confiança e Validação
- Como é calculada a confiança?
- Há sistema de validação de sinais?
- Usa confirmação de tendência?
- Valida com outros indicadores?

### 4. Detecção de Padrões
- Detecta divergência?
- Identifica níveis de suporte/resistência?
- Usa múltiplos períodos?
- Analisa padrões de preço?

### 5. Filtros de Mercado
- Filtra mercados laterais?
- Considera volatilidade?
- Valida timeframe adequado?
- Usa confirmação de volume?

## Melhorias Necessárias

Para cada área de análise, identifique:

### Alta Prioridade (Impacto Alto, Risco Baixo)
- [ ] Melhoria 1
- [ ] Melhoria 2
- [ ] Melhoria 3

### Média Prioridade (Impacto Médio, Risco Médio)
- [ ] Melhoria 1
- [ ] Melhoria 2
- [ ] Melhoria 3

### Baixa Prioridade (Impacto Baixo, Risco Alto)
- [ ] Melhoria 1
- [ ] Melhoria 2
- [ ] Melhoria 3

## Viabilidade de Implementação

Para cada melhoria, analise:

1. **Viabilidade**: É possível implementar sem quebrar o código existente?
2. **Impacto**: Qual o impacto na precisão dos sinais?
3. **Dificuldade**: Qual o nível de dificuldade de implementação?
4. **Dependências**: Requer novos dados ou indicadores?

## Documentação

Crie os seguintes documentos:

1. **[NOME_DO_INDICADOR]_MELHORIAS.md**: Lista detalhada de melhorias necessárias
2. **[NOME_DO_INDICADOR]_VIABILIDADE.md**: Análise de viabilidade de cada melhoria
3. **[NOME_DO_INDICADOR]_IMPLEMENTACAO.md**: Guia de implementação passo a passo

## Implementação

Implemente as melhorias seguindo esta ordem:

### Fase 1: Baixo Risco
- Implementar melhorias que não afetam o funcionamento existente
- Adicionar parâmetros opcionais para novas funcionalidades
- Manter compatibilidade com código existente

### Fase 2: Risco Médio
- Extender métodos existentes
- Adicionar novos métodos auxiliares
- Melhorar lógica existente

### Fase 3: Alto Impacto
- Criar novas classes se necessário
- Refatorar código complexo
- Integrar todas as melhorias

## Exemplo de Implementação

Para cada melhoria, forneça:

1. **Descrição**: O que será implementado
2. **Código**: Código da implementação
3. **Testes**: Como testar a implementação
4. **Documentação**: Como usar a nova funcionalidade

## Padrões de Código

Siga estes padrões:

1. **Nomes de métodos**: Use snake_case para métodos privados (_method)
2. **Documentação**: Adicione docstrings completas
3. **Logging**: Use logger.info/debug/error apropriadamente
4. **Tratamento de erros**: Use try/except com logging
5. **Validação**: Valide parâmetros e dados de entrada

## Verificação Final

Antes de concluir, verifique:

1. [ ] Todas as melhorias foram implementadas
2. [ ] Código compila sem erros
3. [ ] Documentação está completa
4. [ ] Testes foram realizados
5. [ ] Código segue padrões existentes
6. [ ] Não há regressões de funcionalidade

## Entregáveis

1. Código implementado
2. Documentação completa
3. Guia de uso
4. Exemplos de implementação
```

## Prompt Específico para RSI

```
Você é um especialista em análise técnica. Revise o indicador RSI (Relative Strength Index) em [CAMINHO_DO_ARQUIVO].

## Tarefas

1. **Análise de Fundamentos**
   - Pesquise sobre as melhores práticas de RSI
   - Identifique limitações da implementação atual
   - Compare com literatura especializada

2. **Identificação de Melhorias**
   - True RSI Levels (níveis dinâmicos baseados em histórico)
   - Confidence Level (80% rule)
   - Filtros de Timeframe
   - Hidden RSI Levels
   - Divergência Avançada
   - Confirmação de Tendência (ADX)
   - Múltiplos Períodos

3. **Viabilidade**
   - Analise se cada melhoria é viável
   - Identifique impacto e dificuldade
   - Documente dependências

4. **Implementação**
   - Implemente todas as melhorias viáveis
   - Mantenha compatibilidade com código existente
   - Adicione documentação completa

## Padrões Específicos do RSI

- Usar Wilder's smoothing (alpha = 1/period)
- Proteção contra divisão por zero
- Clipar valores para 0-100
- Validar dados de entrada
- Tratar valores NaN

## Exemplo de Uso

```python
# RSI básico
rsi = RSI(period=14)
result = rsi.calculate(data)

# RSI com True RSI Levels
rsi = RSI(period=14, use_true_levels=True)
result = rsi.calculate_with_signals(data)

# RSI avançado
hidden_levels = rsi.find_hidden_rsi_levels(data, rsi)
divergence = rsi.detect_divergence_advanced(data, rsi)
trend = rsi.confirm_trend(data)

# Multi-Period RSI
multi_rsi = MultiPeriodRSI(periods=[14, 21, 34, 55])
signal = multi_rsi.get_advanced_signal(data)
```
```

## Prompt Genérico para Qualquer Indicador

```
Revise o indicador [NOME_DO_INDICADOR] em [CAMINHO_DO_ARQUIVO].

## Análise

1. Estude o código atual
2. Pesquise fundamentos e melhores práticas
3. Identifique problemas e limitações
4. Liste melhorias necessárias

## Implementação

Implemente as melhorias seguindo:
- Fase 1: Baixo risco
- Fase 2: Risco médio
- Fase 3: Alto impacto

## Documentação

Crie documentação completa para cada melhoria.
```

## Checklist de Qualidade

Para cada melhoria implementada, verifique:

- [ ] Código funciona corretamente
- [ ] Trata erros apropriadamente
- [ ] Tem logging adequado
- [ ] Está documentado
- [ ] Segue padrões de código
- [ ] Não quebra funcionalidade existente
- [ ] Tem testes (se aplicável)
- [ ] É compatível com versões anteriores

## Exemplos de Prompts Específicos

### Para MACD
```
Revise o indicador MACD em [CAMINHO]. Implemente:
- Detecção avançada de crossover
- Validação com volume
- Filtragem de sinais falsos
- Múltiplos períodos
```

### Para Bollinger Bands
```
Revise Bollinger Bands em [CAMINHO]. Implemente:
- Níveis dinâmicos baseados em volatilidade
- Detecção de squeeze
- Validação com tendência
- Múltiplos períodos
```

### Para Stochastic
```
Revise Stochastic em [CAMINHO]. Implemente:
- Detecção de crossover %K/%D
- Validação com divergência
- Filtragem de sinais
- Múltiplos períodos
```

## Conclusão

Use este prompt como template para revisar e melhorar qualquer indicador técnico. Adapte as seções conforme necessário para cada indicador específico.
```
