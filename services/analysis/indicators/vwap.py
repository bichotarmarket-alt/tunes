"""VWAP (Volume Weighted Average Price) indicator"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class VWAP(TechnicalIndicator):
    """Volume Weighted Average Price indicator"""

    def __init__(self, period: int = 14):
        """
        Initialize VWAP indicator

        Args:
            period: VWAP period for rolling calculation (default: 14)
        """
        super().__init__("VWAP")
        self.period = period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate VWAP parameters"""
        period = kwargs.get('period', self.period)
        return isinstance(period, int) and period > 0

    @cached_indicator("VWAP")
    @handle_indicator_errors("VWAP", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate VWAP values

        Args:
            data: DataFrame with OHLCV data (must have 'high', 'low', 'close', 'volume' columns)

        Returns:
            pd.Series: VWAP values
        """
        # Validate input data - VWAP needs OHLCV
        validate_dataframe(data, ['high', 'low', 'close', 'volume'], min_rows=self.period)

        if len(data) < self.period:
            logger.warning(f"Not enough data points for VWAP calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate typical price: (high + low + close) / 3
        typical_price = (data['high'] + data['low'] + data['close']) / 3

        # Calculate VWAP: cumulative(TP * Volume) / cumulative(Volume)
        vwap = (typical_price * data['volume']).rolling(window=self.period).sum() / data['volume'].rolling(window=self.period).sum()

        return vwap

    def get_signal(self, data: pd.DataFrame) -> Optional[str]:
        """
        Get trading signal based on VWAP

        Args:
            data: DataFrame with OHLC data

        Returns:
            Optional[str]: 'buy', 'sell', or None
        """
        if len(data) < 2:
            return None

        vwap = self.calculate(data)
        close = data['close']

        if len(vwap) < 2 or len(close) < 2:
            return None

        # Price crosses above VWAP = bullish
        if close.iloc[-2] <= vwap.iloc[-2] and close.iloc[-1] > vwap.iloc[-1]:
            return 'buy'
        # Price crosses below VWAP = bearish
        elif close.iloc[-2] >= vwap.iloc[-2] and close.iloc[-1] < vwap.iloc[-1]:
            return 'sell'

        return None

    def calculate_confidence(self, data: pd.DataFrame) -> float:
        """
        Calculate confidence level of signal

        Args:
            data: DataFrame with OHLC data

        Returns:
            float: Confidence level (0.0 to 1.0)
        """
        if len(data) < self.period:
            return 0.0

        vwap = self.calculate(data)
        close = data['close']

        if len(vwap) == 0 or pd.isna(vwap.iloc[-1]):
            return 0.0

        # Distance from VWAP as percentage
        distance = abs(close.iloc[-1] - vwap.iloc[-1]) / vwap.iloc[-1]

        # Higher distance = higher confidence (max 1.0 at 2% distance)
        return min(1.0, distance / 0.02)
