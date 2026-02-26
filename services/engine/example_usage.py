"""
Exemplo completo de uso do Trading Engine HFT

Este exemplo demonstra:
- Inicialização do engine
- Processamento de ticks
- Emissão de sinais
- Execução desacoplada
- Sistema adaptativo
"""
import asyncio
import random
from datetime import datetime

from services.engine import (
    AsyncTradingEngine,
    AdaptivePerformanceTracker,
    Signal
)


async def example_basic_usage():
    """Exemplo básico de uso do engine."""
    print("=" * 60)
    print("EXEMPLO 1: Uso Básico do AsyncTradingEngine")
    print("=" * 60)
    
    # Criar engine
    engine = AsyncTradingEngine(
        redis_host='localhost',
        redis_port=6379,
        num_workers=2,
        signal_threshold=0.65,
        max_queue_size=100
    )
    
    # Callback para receber sinais
    def on_signal(signal: Signal):
        print(f"📊 Callback recebido: {signal.symbol} {signal.direction.upper()}")
    
    engine.on_signal(on_signal)
    
    # Inicializar
    await engine.initialize()
    
    # Simular ticks para EURUSD
    price = 1.0850
    for i in range(50):
        # Simular movimento de preço
        price += random.uniform(-0.0010, 0.0010)
        await engine.on_price_update('EURUSD', price)
        await asyncio.sleep(0.01)  # 10ms entre ticks
    
    # Ver estatísticas
    stats = await engine.get_stats()
    print(f"\n📈 Estatísticas:")
    print(f"   Ticks recebidos: {stats['ticks_received']}")
    print(f"   Sinais na fila: {stats['queue_size']}")
    print(f"   Sinais executados: {stats['signals_executed']}")
    print(f"   Processors ativos: {stats['active_processors']}")
    
    # Shutdown
    await engine.shutdown()
    print("\n✅ Engine finalizado\n")


async def example_multi_asset():
    """Exemplo com múltiplos ativos."""
    print("=" * 60)
    print("EXEMPLO 2: Processamento Multi-Ativo")
    print("=" * 60)
    
    engine = AsyncTradingEngine(
        redis_host='localhost',
        num_workers=3,
        signal_threshold=0.60
    )
    
    await engine.initialize()
    
    # Ativos para simular
    assets = {
        'EURUSD': 1.0850,
        'GBPUSD': 1.2650,
        'USDJPY': 149.50,
        'AUDUSD': 0.6550,
    }
    
    # Simular 100 ticks por ativo
    for _ in range(100):
        tasks = []
        for symbol, base_price in assets.items():
            # Movimento aleatório
            new_price = base_price * (1 + random.uniform(-0.002, 0.002))
            assets[symbol] = new_price
            tasks.append(engine.on_price_update(symbol, new_price))
        
        await asyncio.gather(*tasks)
        await asyncio.sleep(0.005)  # 5ms
    
    stats = await engine.get_stats()
    print(f"📈 Processamento multi-ativo:")
    print(f"   Total de ticks: {stats['ticks_received']}")
    print(f"   Ativos ativos: {stats['active_processors']}")
    print(f"   Sinais gerados: {stats['signals_queued']}")
    
    for symbol, proc_stats in stats['processors'].items():
        print(f"   {symbol}: {proc_stats['ticks_processed']} ticks, "
              f"{proc_stats['signals_generated']} sinais")
    
    await engine.shutdown()
    print("\n✅ Multi-ativo finalizado\n")


async def example_adaptive_system():
    """Exemplo do sistema adaptativo."""
    print("=" * 60)
    print("EXEMPLO 3: Sistema Adaptativo por Ativo")
    print("=" * 60)
    
    tracker = AdaptivePerformanceTracker(
        min_trades_for_adjustment=5,
        lookback_trades=20,
        adjustment_factor=0.25
    )
    
    symbol = 'EURUSD'
    timeframe = 'M1'
    
    # Simular trades com resultado variado
    print("\n📝 Registrando trades simulados...")
    
    # Simular alguns wins
    for i in range(8):
        await tracker.record_trade_result(
            symbol=symbol,
            timeframe=timeframe,
            won=True,
            indicator_signals={'rsi': True, 'macd': i % 2 == 0}
        )
    
    # Simular alguns losses
    for i in range(4):
        await tracker.record_trade_result(
            symbol=symbol,
            timeframe=timeframe,
            won=False,
            indicator_signals={'rsi': True, 'macd': i % 2 == 0}
        )
    
    # Ver relatório
    report = await tracker.get_performance_report(symbol, timeframe)
    
    print(f"\n📊 Relatório de Performance para {symbol} {timeframe}:")
    print(f"   Winrate: {report['winrate']:.1%}")
    print(f"   Total trades: {report['total_trades']}")
    print(f"   Lucrativo: {'✅ Sim' if report['is_profitable'] else '❌ Não'}")
    print(f"   Threshold recomendado: {report['recommended_threshold']:.2f}")
    
    print(f"\n   Winrates por indicador:")
    for ind, wr in report['indicator_winrates'].items():
        print(f"      {ind}: {wr:.1%}")
    
    print(f"\n   Pesos ajustados:")
    for ind, weight in report['adjusted_weights'].items():
        base = 1.0
        change = (weight / base - 1) * 100
        print(f"      {ind}: {weight:.2f} ({change:+.0f}%)")
    
    print("\n✅ Sistema adaptativo finalizado\n")


async def example_error_handling():
    """Exemplo de tratamento de erros."""
    print("=" * 60)
    print("EXEMPLO 4: Tratamento de Erros e Retry")
    print("=" * 60)
    
    engine = AsyncTradingEngine(
        redis_host='localhost',
        num_workers=1,
        signal_threshold=0.50  # Threshold baixo para gerar mais sinais
    )
    
    errors_received = []
    
    def on_error(error, signal):
        errors_received.append((error, signal))
        print(f"⚠️ Erro capturado: {type(error).__name__}")
    
    engine.on_error(on_error)
    await engine.initialize()
    
    # Simular ticks
    price = 1.0850
    for i in range(30):
        price += random.uniform(-0.0005, 0.0005)
        await engine.on_price_update('EURUSD', price)
    
    # Aguardar processamento
    await asyncio.sleep(0.5)
    
    stats = await engine.get_stats()
    print(f"\n📈 Stats finais:")
    print(f"   Executados: {stats['signals_executed']}")
    print(f"   Falhas: {stats['signals_failed']}")
    print(f"   Erros capturados: {len(errors_received)}")
    
    await engine.shutdown()
    print("\n✅ Tratamento de erros finalizado\n")


async def main():
    """Executar todos exemplos."""
    print("\n" + "=" * 60)
    print("TRADING ENGINE HFT - DEMONSTRAÇÃO COMPLETA")
    print("=" * 60 + "\n")
    
    try:
        await example_basic_usage()
    except Exception as e:
        print(f"Erro no exemplo 1: {e}")
    
    try:
        await example_multi_asset()
    except Exception as e:
        print(f"Erro no exemplo 2: {e}")
    
    try:
        await example_adaptive_system()
    except Exception as e:
        print(f"Erro no exemplo 3: {e}")
    
    try:
        await example_error_handling()
    except Exception as e:
        print(f"Erro no exemplo 4: {e}")
    
    print("=" * 60)
    print("DEMONSTRAÇÃO FINALIZADA")
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
