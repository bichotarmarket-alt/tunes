"""Helper functions for converting models to response schemas"""
from models import Account, Trade, Strategy, Asset, User
from schemas import AccountResponse, TradeResponse, StrategyResponse, AssetResponse, UserResponse
from datetime import datetime


def account_to_response(account: Account) -> AccountResponse:
    """Convert Account model to AccountResponse schema"""
    return AccountResponse(
        id=account.id,
        user_id=account.user_id,
        ssid_demo=account.ssid_demo,
        ssid_real=account.ssid_real,
        name=account.name,
        autotrade_demo=account.autotrade_demo,
        autotrade_real=account.autotrade_real,
        uid=account.uid,
        platform=account.platform,
        balance_demo=account.balance_demo,
        balance_real=account.balance_real,
        currency=account.currency,
        is_active=account.is_active,
        last_connected=account.last_connected,
        created_at=account.created_at,
        updated_at=account.updated_at
    )


def trade_to_response(trade: Trade) -> TradeResponse:
    """Convert Trade model to TradeResponse schema"""
    return TradeResponse(
        id=trade.id,
        account_id=trade.account_id,
        asset_id=trade.asset_id,
        strategy_id=trade.strategy_id,
        direction=trade.direction.value if hasattr(trade.direction, 'value') else str(trade.direction),
        amount=trade.amount,
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        duration=trade.duration,
        status=trade.status.value if hasattr(trade.status, 'value') else str(trade.status),
        profit=trade.profit,
        payout=trade.payout,
        placed_at=trade.placed_at,
        expires_at=trade.expires_at,
        closed_at=trade.closed_at,
        signal_confidence=trade.signal_confidence,
        signal_indicators=trade.signal_indicators
    )


def strategy_to_response(strategy: Strategy) -> StrategyResponse:
    """Convert Strategy model to StrategyResponse schema"""
    return StrategyResponse(
        id=strategy.id,
        user_id=strategy.user_id,
        account_id=strategy.account_id,
        name=strategy.name,
        type=strategy.type.value if hasattr(strategy.type, 'value') else str(strategy.type),
        parameters=strategy.parameters,
        assets=strategy.assets,
        is_active=strategy.is_active,
        total_trades=strategy.total_trades,
        winning_trades=strategy.winning_trades,
        losing_trades=strategy.losing_trades,
        total_profit=strategy.total_profit,
        total_loss=strategy.total_loss,
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
        last_executed=strategy.last_executed
    )


def asset_to_response(asset: Asset) -> AssetResponse:
    """Convert Asset model to AssetResponse schema"""
    return AssetResponse(
        id=asset.id,
        symbol=asset.symbol,
        name=asset.name,
        type=asset.type,
        is_active=asset.is_active,
        payout=asset.payout,
        min_order_amount=asset.min_order_amount,
        max_order_amount=asset.max_order_amount,
        min_duration=asset.min_duration,
        max_duration=asset.max_duration,
        available_timeframes=asset.available_timeframes,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


def user_to_response(user: User) -> UserResponse:
    """Convert User model to UserResponse schema"""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


def accounts_to_response(accounts: list[Account]) -> list[AccountResponse]:
    """Convert list of Account models to AccountResponse schemas"""
    return [account_to_response(account) for account in accounts]


def trades_to_response(trades: list[Trade]) -> list[TradeResponse]:
    """Convert list of Trade models to TradeResponse schemas"""
    return [trade_to_response(trade) for trade in trades]


def strategies_to_response(strategies: list[Strategy]) -> list[StrategyResponse]:
    """Convert list of Strategy models to StrategyResponse schemas"""
    return [strategy_to_response(strategy) for strategy in strategies]


def assets_to_response(assets: list[Asset]) -> list[AssetResponse]:
    """Convert list of Asset models to AssetResponse schemas"""
    return [asset_to_response(asset) for asset in assets]
