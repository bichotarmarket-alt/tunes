"""
Momentum Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class Momentum(TechnicalIndicator):
    """Momentum indicator"""

    def __init__(self, period: int = 3, overbought: float = 2.0, oversold: float = -2.0):
        """
        Initialize Momentum indicator

        Args:
            period: Momentum period (default: 10)
            overbought: Overbought threshold (default: 2.0)
            oversold: Oversold threshold (default: -2.0)
        """
        super().__init__("Momentum")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def validate_parameters(self, **kwargs) -> bool:
        """Validate Momentum parameters"""
        period = kwargs.get('period', self.period)
        overbought = kwargs.get('overbought', self.overbought)
        oversold = kwargs.get('oversold', self.oversold)
        return (
            isinstance(period, int) and period > 0 and
            isinstance(overbought, (int, float)) and
            isinstance(oversold, (int, float)) and
            overbought > oversold
        )

    @cached_indicator("Momentum")
    @handle_indicator_errors("Momentum", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate Momentum values

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            pd.Series: Momentum values
        """
        # Validate input data
        validate_dataframe(data, ['close'], min_rows=self.period)

        if 'close' not in data.columns:
            raise ValueError("DataFrame must have 'close' column")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for Momentum calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        close = data['close']

        # Validate data integrity
        if (close < 0).any():
            logger.warning("Momentum: Detected negative price values, applying correction")
            close = close.clip(lower=0)

        # Check for extreme values
        max_price = close.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"Momentum: Detected extreme price values (max: {max_price})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate Momentum: (current price - price N periods ago) / price N periods ago
        close_shifted = close.shift(self.period)
        denominator = close_shifted.replace(0, np.nan)

        # Handle NaN in denominator before division
        momentum = np.where(denominator.notna() & (denominator != 0),
                          (close - close_shifted) / denominator,
                          np.nan)

        momentum_series = pd.Series(momentum, index=data.index)

        # Clip extreme values to prevent overflow
        momentum_series = momentum_series.clip(-10000, 10000)

        return momentum_series

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 2.0,
        oversold_threshold: float = -2.0
    ) -> pd.DataFrame:
        """
        Calculate Momentum with buy/sell signals

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought threshold
            oversold_threshold: Oversold threshold

        Returns:
            pd.DataFrame: DataFrame with momentum values and signals
        """
        momentum = self.calculate(data)

        # Determine signals
        buy_signal = (momentum < oversold_threshold) & (momentum.shift(1) >= oversold_threshold)
        sell_signal = (momentum > overbought_threshold) & (momentum.shift(1) <= overbought_threshold)

        return pd.DataFrame({
            'momentum': momentum,
            'buy_signal': buy_signal,
            'sell_signal': sell_signal,
            'overbought': overbought_threshold,
            'oversold': oversold_threshold
        }, index=data.index)
