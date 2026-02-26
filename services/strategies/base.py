"""Base class for trading strategies"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd

from models import Candle, Signal, SignalType


class BaseStrategy(ABC):
    """Base class for trading strategies"""

    def __init__(
        self,
        name: str,
        strategy_type: str,
        account_id: str,
        parameters: Dict[str, Any],
        assets: List[str]
    ):
        self.name = name
        self.strategy_type = strategy_type
        self.account_id = account_id
        self.parameters = parameters
        self.assets = assets
        self.is_active = True

    @abstractmethod
    async def analyze(self, candles: List[Candle]) -> Optional[Signal]:
        """
        Analyze candles and generate signal

        Args:
            candles: List of candles to analyze

        Returns:
            Optional[Signal]: Generated signal or None
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """
        Validate strategy parameters

        Returns:
            bool: True if parameters are valid
        """
        pass

    async def backtest(
        self,
        candles: List[Candle],
        initial_balance: float = 1000.0
    ) -> Dict[str, Any]:
        """
        Backtest strategy on historical data

        Args:
            candles: Historical candles
            initial_balance: Starting balance

        Returns:
            Dict: Backtest results
        """
        results = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "net_profit": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0
        }

        # Simple backtest implementation
        balance = initial_balance
        max_balance = initial_balance
        max_drawdown = 0.0

        for i in range(len(candles) - 1):
            # Analyze with available candles
            window = candles[max(0, i - 50):i + 1]
            signal = await self.analyze(window)

            if signal and signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                results["total_trades"] += 1

                # Simulate trade (simplified)
                entry_price = candles[i].close
                exit_price = candles[i + 1].close

                # Validate entry_price to avoid division by zero
                if entry_price == 0:
                    logger.warning(f"Entry price is zero at candle {i}, skipping trade")
                    continue

                if signal.signal_type == SignalType.BUY:
                    profit = (exit_price - entry_price) / entry_price * balance
                else:
                    profit = (entry_price - exit_price) / entry_price * balance

                balance += profit

                if profit > 0:
                    results["winning_trades"] += 1
                    results["total_profit"] += profit
                else:
                    results["losing_trades"] += 1
                    results["total_loss"] += abs(profit)

                # Track max drawdown
                if balance > max_balance:
                    max_balance = balance
                if max_balance > 0:
                    drawdown = (max_balance - balance) / max_balance * 100
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown

        # Calculate metrics
        if results["total_trades"] > 0:
            results["win_rate"] = (results["winning_trades"] / results["total_trades"]) * 100

        results["net_profit"] = balance - initial_balance
        results["max_drawdown"] = max_drawdown

        if results["total_loss"] > 0:
            results["profit_factor"] = results["total_profit"] / results["total_loss"]
        elif results["total_profit"] > 0:
            results["profit_factor"] = float('inf')

        return results
