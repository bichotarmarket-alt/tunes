"""Dependency injection for the application"""
from functools import lru_cache
from typing import Optional

# Import repositories (to be created later)
# from repositories.account_repository import AccountRepository
# from repositories.trade_repository import TradeRepository
# from repositories.strategy_repository import StrategyRepository

# Import services (to be created later)
# from services.account_service import AccountService
# from services.trade_service import TradeService
# from services.strategy_service import StrategyService

# Import event bus
from core.events import event_bus


@lru_cache(maxsize=1)
def get_event_bus():
    """Get the global event bus instance (singleton)"""
    return event_bus


# Repository singletons (to be implemented later)
# @lru_cache(maxsize=1)
# def get_account_repository() -> AccountRepository:
#     """Get account repository (singleton)"""
#     return AccountRepository()

# @lru_cache(maxsize=1)
# def get_trade_repository() -> TradeRepository:
#     """Get trade repository (singleton)"""
#     return TradeRepository()

# @lru_cache(maxsize=1)
# def get_strategy_repository() -> StrategyRepository:
#     """Get strategy repository (singleton)"""
#     return StrategyRepository()


# Service singletons (to be implemented later)
# @lru_cache(maxsize=1)
# def get_account_service() -> AccountService:
#     """Get account service (singleton)"""
#     return AccountService(get_account_repository())

# @lru_cache(maxsize=1)
# def get_trade_service() -> TradeService:
#     """Get trade service (singleton)"""
#     return TradeService(get_trade_repository())

# @lru_cache(maxsize=1)
# def get_strategy_service() -> StrategyService:
#     """Get strategy service (singleton)"""
#     return StrategyService(get_strategy_repository())
