"""
Teste completo dos 10 novos indicadores técnicos

Este script testa cada indicador individualmente para garantir que funcionam
corretamente com diferentes cenários de dados.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys

# Importar indicadores
from services.analysis.indicators import (
    ParabolicSAR, IchimokuCloud, MoneyFlowIndex, AverageDirectionalIndex,
    KeltnerChannels, DonchianChannels, HeikenAshi, PivotPoints,
    Supertrend, FibonacciRetracement
)
from services.analysis.indicators.synthetic_volume import add_synthetic_volume


def create_test_data(n_candles=200):
    """Criar dados de teste realistas"""
    np.random.seed(42)
    
    # Criar tendência com ruído
    trend = np.linspace(100, 120, n_candles)
    noise = np.random.randn(n_candles) * 0.5
    
    close = trend + noise
    high = close + np.random.rand(n_candles) * 0.5
    low = close - np.random.rand(n_candles) * 0.5
    open_price = close + np.random.randn(n_candles) * 0.3
    
    dates = pd.date_range('2024-01-01', periods=n_candles, freq='1min')
    
    data = pd.DataFrame({
        'timestamp': dates.astype(np.int64) // 10**9,
        'datetime': dates,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(1000, 10000, n_candles)
    })
    
    # Adicionar volume sintético
    data = add_synthetic_volume(data)
    
    return data


def test_indicator(name, indicator_class, data, min_candles=10):
    """Testar um indicador individualmente"""
    print(f"\n{'='*60}")
    print(f"Testando: {name}")
    print(f"{'='*60}")
    
    try:
        # Instanciar indicador
        indicator = indicator_class()
        print(f"[OK] Instanciado: {indicator.name}")
        
        # Verificar parâmetros padrão
        params = indicator.get_default_parameters()
        print(f"[OK] Parâmetros padrão: {params}")
        
        # Validar parâmetros
        if indicator.validate_parameters(**params):
            print(f"[OK] Validação de parâmetros: OK")
        else:
            print(f"[ERRO] Validação de parâmetros: FALHOU")
            return False
        
        # Calcular indicador
        result = indicator.calculate(data)
        
        if result is None:
            print(f"[ERRO] Cálculo retornou None")
            return False
        
        print(f"[OK] Cálculo realizado: {len(result)} candles")
        print(f"[OK] Colunas: {result.columns.tolist()}")
        
        # Verificar se há sinais
        if 'signal' in result.columns:
            signals = result['signal'].value_counts()
            print(f"[OK] Sinais gerados: {signals.to_dict()}")
        
        # Verificar se há valores NaN
        nan_count = result.isna().sum().sum()
        if nan_count > 0:
            print(f"[AVISO] Valores NaN: {nan_count}")
        else:
            print(f"[OK] Sem valores NaN")
        
        # Testar filtro de sinais
        buy_signals = result[result['signal'] == 'buy']
        sell_signals = result[result['signal'] == 'sell']
        
        if len(buy_signals) > 0:
            print(f"[OK] {len(buy_signals)} sinais de compra encontrados")
            # Testar filtro para buy signals
            for idx in buy_signals.index[-3:]:  # Testar últimos 3
                signal_data = result.loc[:idx]
                if indicator.filter_signals(signal_data, 'buy'):
                    print(f"  [OK] Filtro buy: OK (idx={idx})")
                else:
                    print(f"  [ERRO] Filtro buy: FALHOU (idx={idx})")
        
        if len(sell_signals) > 0:
            print(f"[OK] {len(sell_signals)} sinais de venda encontrados")
            # Testar filtro para sell signals
            for idx in sell_signals.index[-3:]:  # Testar últimos 3
                signal_data = result.loc[:idx]
                if indicator.filter_signals(signal_data, 'sell'):
                    print(f"  [OK] Filtro sell: OK (idx={idx})")
                else:
                    print(f"  [ERRO] Filtro sell: FALHOU (idx={idx})")
        
        # Verificar explicações de parâmetros
        explanations = indicator.get_parameter_explanations()
        if explanations:
            print(f"[OK] Explicações de parâmetros: {len(explanations)} parâmetros")
        
        print(f"[OK] Teste de {name} concluído com SUCESSO")
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao testar {name}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Executar todos os testes"""
    print("="*60)
    print("TESTE COMPLETO DOS 10 NOVOS INDICADORES")
    print("="*60)
    
    # Criar dados de teste
    data = create_test_data(200)
    print(f"\nDados de teste criados: {len(data)} candles")
    print(f"Range de preço: {data['close'].min():.2f} - {data['close'].max():.2f}")
    
    # Lista de indicadores para testar
    indicators_to_test = [
        ("Parabolic SAR", ParabolicSAR),
        ("Ichimoku Cloud", IchimokuCloud),
        ("Money Flow Index", MoneyFlowIndex),
        ("Average Directional Index", AverageDirectionalIndex),
        ("Keltner Channels", KeltnerChannels),
        ("Donchian Channels", DonchianChannels),
        ("Heiken Ashi", HeikenAshi),
        ("Pivot Points", PivotPoints),
        ("Supertrend", Supertrend),
        ("Fibonacci Retracement", FibonacciRetracement)
    ]
    
    # Testar cada indicador
    results = {}
    for name, indicator_class in indicators_to_test:
        success = test_indicator(name, indicator_class, data)
        results[name] = success
    
    # Resumo dos testes
    print(f"\n{'='*60}")
    print("RESUMO DOS TESTES")
    print(f"{'='*60}")
    
    passed = sum(results.values())
    total = len(results)
    
    for name, success in results.items():
        status = "[OK] PASSOU" if success else "[ERRO] FALHOU"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} indicadores passaram nos testes")
    
    if passed == total:
        print("[OK] Todos os indicadores passaram nos testes!")
        return 0
    else:
        print(f"[ERRO] {total - passed} indicadores falharam nos testes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
