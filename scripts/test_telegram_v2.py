"""
Teste do novo servico de notificacoes Telegram V2
Execute: python test_telegram_v2.py
"""
import asyncio
import sys
sys.path.insert(0, 'c:/Users/SOUZAS/Desktop/tunestrade')

from services.notifications.telegram_v2 import telegram_service_v2, telegram_service


async def test_health_check():
    """Testa verificacao de saude do servico"""
    print("\n[TESTE 1] Health Check...")
    metrics = await telegram_service_v2.health_check()
    print(f"Enabled: {metrics['enabled']}")
    print(f"Token Configured: {metrics['token_configured']}")
    print(f"API Connected: {metrics.get('api_connected', False)}")
    print(f"Bot Name: {metrics.get('bot_name', 'N/A')}")
    print(f"Queue Size: {metrics['queue_size']}")
    print(f"Success Rate: {metrics['success_rate']:.1%}")
    return metrics['enabled']


async def test_validate_token():
    """Testa validacao de token"""
    print("\n[TESTE 2] Validacao de Token...")
    valid = await telegram_service_v2.validate_token()
    print(f"Token Valido: {valid}")
    return valid


async def test_send_message():
    """Testa envio de mensagem"""
    print("\n[TESTE 3] Envio de Mensagem...")
    # Substitua pelo seu chat_id real para teste
    chat_id = "5421864068"  # ID do log

    message = """[TESTE TELEGRAM V2]

Este e um teste do novo servico de notificacoes.

Horario: {time}""".format(time=telegram_service_v2._format_time())

    success = await telegram_service_v2.send_message(message, chat_id)
    print(f"Mensagem enviada: {success}")

    # Aguardar processamento da fila
    await asyncio.sleep(2)

    # Ver metricas
    metrics = await telegram_service_v2.health_check()
    print(f"Total Enviado: {metrics['total_sent']}")
    print(f"Total Falhas: {metrics['total_failed']}")
    return success


async def test_send_signal():
    """Testa notificacao de sinal"""
    print("\n[TESTE 4] Notificacao de Sinal...")
    chat_id = "5421864068"

    success = await telegram_service_v2.send_signal(
        asset="EURUSD_otc",
        direction="BUY",
        confidence=0.85,
        timeframe=5,
        account_name="Conta Teste",
        chat_id=chat_id,
        trade_amount=10.0,
        strategy_name="Estrategia Zonas",
        account_type="demo"
    )
    print(f"Sinal enviado: {success}")

    await asyncio.sleep(2)
    return success


async def test_send_trade_result():
    """Testa notificacao de resultado"""
    print("\n[TESTE 5] Notificacao de Resultado...")
    chat_id = "5421864068"

    success = await telegram_service_v2.send_trade_result(
        asset="EURUSD_otc",
        direction="BUY",
        result="WIN",
        profit=8.5,
        account_name="Conta Teste",
        chat_id=chat_id,
        account_type="demo"
    )
    print(f"Resultado enviado: {success}")

    await asyncio.sleep(2)
    return success


async def test_send_stop_loss():
    """Testa notificacao de stop loss"""
    print("\n[TESTE 6] Notificacao de Stop Loss...")
    chat_id = "5421864068"

    success = await telegram_service_v2.send_stop_loss(
        account_name="Conta Teste",
        loss_consecutive=3,
        stop_loss_level=3,
        chat_id=chat_id,
        account_type="demo"
    )
    print(f"Stop loss enviado: {success}")

    await asyncio.sleep(2)
    return success


async def test_sync_methods():
    """Testa metodos sincronos"""
    print("\n[TESTE 7] Metodos Sincronos...")
    chat_id = "5421864068"

    # Testar via adapter (compatibilidade)
    success = telegram_service.send_signal_sync(
        asset="GBPUSD_otc",
        direction="SELL",
        confidence=0.75,
        timeframe=5,
        account_name="Conta Sync",
        chat_id=chat_id
    )
    print(f"Sinal sync enviado: {success}")
    return success


async def test_metrics():
    """Exibe metricas finais"""
    print("\n[TESTE 8] Metricas Finais...")
    metrics = await telegram_service_v2.health_check()

    print("\n=== METRICAS ===")
    print(f"Total Enviado: {metrics['total_sent']}")
    print(f"Total Falhas: {metrics['total_failed']}")
    print(f"Total Retries: {metrics['total_retries']}")
    print(f"Rate Limit Hits: {metrics['rate_limit_hits']}")
    print(f"Success Rate: {metrics['success_rate']:.1%}")
    print(f"Avg Response Time: {metrics['avg_response_time']:.3f}s")
    print(f"Offline Chats: {metrics['offline_chats_count']}")
    print(f"Errors by Code: {metrics['errors_by_code']}")

    if metrics['last_error']:
        print(f"\nUltimo Erro: {metrics['last_error']}")

    return metrics


async def main():
    """Executa todos os testes"""
    print("="*60)
    print("TESTE DO SERVICO TELEGRAM V2")
    print("="*60)

    try:
        # Teste 1: Health Check
        enabled = await test_health_check()
        if not enabled:
            print("\n[AVISO] Servico desabilitado. Configure TELEGRAM_BOT_TOKEN no .env")
            return

        # Teste 2: Validar Token
        valid = await test_validate_token()
        if not valid:
            print("\n[AVISO] Token invalido. Verifique sua configuracao.")
            return

        # Testes 3-7: Enviar notificacoes
        await test_send_message()
        await test_send_signal()
        await test_send_trade_result()
        await test_send_stop_loss()
        await test_sync_methods()

        # Teste 8: Metricas
        await test_metrics()

        print("\n" + "="*60)
        print("TESTES CONCLUIDOS!")
        print("="*60)

    except KeyboardInterrupt:
        print("\n\nTeste interrompido pelo usuario.")
    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Fechar recursos
        await telegram_service_v2.close()


if __name__ == "__main__":
    asyncio.run(main())
