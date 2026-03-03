"""
Script para inserir User5 com account e autotrade_config
"""
import asyncio
import asyncpg
from datetime import datetime
import uuid

async def insert_user5():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    try:
        # 1. Verificar se User5 existe
        user_result = await conn.fetchrow("SELECT id FROM users WHERE email = 'user5@example.com'")
        
        if user_result:
            user_id = user_result['id']
            print(f"✅ User5 já existe: {user_id}")
        else:
            # Criar User5
            user_id = str(uuid.uuid4())
            await conn.execute("""
                INSERT INTO users (id, email, password, name, is_active, is_superuser, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
            """, user_id, 'user5@example.com', 'senha123', 'User5', True, False)
            print(f"✅ User5 criado: {user_id}")
        
        # 2. Criar Strategy para User5
        strategy_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO strategies (id, user_id, name, parameters, is_active, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
        """, strategy_id, user_id, 'User5 Strategy', 
            '{"timeframe": 5, "indicators": ["rsi", "macd", "bollinger_bands"]}',
            True)
        print(f"✅ Strategy criada: {strategy_id}")
        
        # 3. Criar Account para User5 com session/uid do PocketOption
        account_id = str(uuid.uuid4())
        session = "rjdpn31j7ptu0548hf9bkr98ni"
        uid = 125631375
        is_demo = True
        platform = 2
        
        await conn.execute("""
            INSERT INTO accounts (
                id, user_id, name, balance, session, uid, is_demo, platform, 
                is_fast_history, is_optimized, is_active, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
        """, 
            account_id, user_id, 'User5 Demo', 1000.0, session, uid, 
            is_demo, platform, True, True, True)
        print(f"✅ Account criada: {account_id}")
        print(f"   Session: {session}")
        print(f"   UID: {uid}")
        print(f"   Demo: {is_demo}")
        print(f"   Platform: {platform}")
        
        # 4. Criar AutoTrade Config
        config_id = str(uuid.uuid4())
        await conn.execute("""
            INSERT INTO autotrade_configs (
                id, account_id, strategy_id, amount, stop1, stop2,
                no_hibernate_on_consecutive_stop, stop_amount_win, stop_amount_loss,
                soros, martingale, timeframe, min_confidence, cooldown_seconds,
                trade_timing, all_win_percentage, is_active,
                highest_balance, initial_balance,
                smart_reduction_enabled, smart_reduction_loss_trigger, smart_reduction_win_restore,
                smart_reduction_percentage, smart_reduction_loss_count, smart_reduction_win_count,
                smart_reduction_active, smart_reduction_base_amount,
                smart_reduction_cascading, smart_reduction_cascade_level,
                soros_level, soros_amount, martingale_level, martingale_amount,
                loss_consecutive, win_consecutive, total_wins, total_losses,
                daily_trades_count, last_trade_date, last_trade_time, last_activity_timestamp,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27,
                $28, $29, $30, $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, NOW(), NOW()
            )
        """,
            config_id,                    # id
            account_id,                   # account_id
            strategy_id,                  # strategy_id
            10.0,                         # amount
            3,                            # stop1
            5,                            # stop2
            False,                        # no_hibernate_on_consecutive_stop
            100.0,                        # stop_amount_win
            50.0,                         # stop_amount_loss
            0,                            # soros
            0,                            # martingale
            5,                            # timeframe
            0.7,                          # min_confidence
            '0',                          # cooldown_seconds
            'on_signal',                  # trade_timing
            0.0,                          # all_win_percentage
            True,                         # is_active
            None,                         # highest_balance
            None,                         # initial_balance
            False,                        # smart_reduction_enabled
            3,                            # smart_reduction_loss_trigger
            2,                            # smart_reduction_win_restore
            0.5,                          # smart_reduction_percentage
            0,                            # smart_reduction_loss_count
            0,                            # smart_reduction_win_count
            False,                        # smart_reduction_active
            0.0,                          # smart_reduction_base_amount
            False,                        # smart_reduction_cascading
            0,                            # smart_reduction_cascade_level
            0,                            # soros_level
            0.0,                          # soros_amount
            0,                            # martingale_level
            0.0,                          # martingale_amount
            0,                            # loss_consecutive
            0,                            # win_consecutive
            0,                            # total_wins
            0,                            # total_losses
            0,                            # daily_trades_count
            None,                         # last_trade_date
            None,                         # last_trade_time
            None                          # last_activity_timestamp
        )
        print(f"✅ AutoTrade Config criada: {config_id}")
        
        # 5. Criar relação strategy_indicators (usando indicadores padrão)
        indicator_ids = await conn.fetch("SELECT id FROM indicators LIMIT 3")
        for idx, ind in enumerate(indicator_ids):
            await conn.execute("""
                INSERT INTO strategy_indicators (strategy_id, indicator_id, parameters, "order")
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (strategy_id, indicator_id) DO NOTHING
            """, strategy_id, ind['id'], '{}', idx)
        print(f"✅ Indicadores associados à strategy")
        
        print("\n🎉 User5 configurado com sucesso!")
        print(f"   User ID: {user_id}")
        print(f"   Account ID: {account_id}")
        print(f"   Strategy ID: {strategy_id}")
        print(f"   Config ID: {config_id}")
        print(f"\n📡 Auth WebSocket:")
        print(f'   42["auth",{{"session":"{session}","isDemo":{1 if is_demo else 0},"uid":{uid},"platform":{platform},"isFastHistory":true,"isOptimized":true}}]')
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(insert_user5())
