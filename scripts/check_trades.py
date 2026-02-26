import asyncio
from core.database import get_db_context
from sqlalchemy import select
from models import Trade, Asset

async def get_recent_trades():
    async with get_db_context() as db:
        result = await db.execute(
            select(Trade.id, Trade.placed_at, Asset.symbol, Trade.direction, Trade.status, Trade.profit, Trade.account_id, Trade.connection_type)
            .join(Asset, Trade.asset_id == Asset.id)
            .order_by(Trade.placed_at.desc())
            .limit(10)
        )
        trades = result.all()
        print('ULTIMOS 10 TRADES NO BANCO:')
        print('='*120)
        header = f"{'ID':<12} {'PLACED_AT':<22} {'SYMBOL':<20} {'DIRECTION':<10} {'STATUS':<10} {'PROFIT':<10} {'CONN_TYPE':<10}"
        print(header)
        print('-'*120)
        for t in trades:
            direction = str(t.direction).split('.')[-1] if hasattr(t.direction, 'value') else str(t.direction)
            status = str(t.status).split('.')[-1] if hasattr(t.status, 'value') else str(t.status)
            symbol = t.symbol if t.symbol else 'N/A'
            profit = f'${t.profit:.2f}' if t.profit else '$0.00'
            conn_type = t.connection_type or 'N/A'
            placed_at = str(t.placed_at)[:19] if t.placed_at else 'N/A'
            line = f"{t.id[:10]:<12} {placed_at:<22} {symbol:<20} {direction:<10} {status:<10} {profit:<10} {conn_type:<10}"
            print(line)
        return trades

asyncio.run(get_recent_trades())
