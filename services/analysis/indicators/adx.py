"""
ADX (Average Directional Index) Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class ADX(TechnicalIndicator):
    """Average Directional Index indicator"""

    def __init__(self, period: int = 5):
        """
        Initialize ADX indicator

        Args:
            period: ADX period (default: 14)
        """
        super().__init__("ADX")
        self.period = period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate ADX parameters"""
        period = kwargs.get('period', self.period)
        return isinstance(period, int) and period > 0

    @cached_indicator("ADX")
    @handle_indicator_errors("ADX", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate ADX values

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)

        Returns:
            pd.Series: ADX values
        """
        # Validate input data
        validate_dataframe(data, ['high', 'low', 'close'], min_rows=self.period)

        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', and 'close' columns")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for ADX calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        high = data['high']
        low = data['low']
        close = data['close']

        # Validate data integrity
        if (high < 0).any() or (low < 0).any() or (close < 0).any():
            logger.warning("ADX: Detected negative price values, applying correction")
            high = high.clip(lower=0)
            low = low.clip(lower=0)
            close = close.clip(lower=0)

        # Check for extreme values
        max_price = max(high.max(), close.max())
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"ADX: Detected extreme price values (max: {max_price})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate +DM and -DM
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smooth TR, +DM, -DM
        atr = tr.rolling(window=self.period).mean()
        plus_di = 100 * (pd.Series(plus_dm, index=data.index).rolling(window=self.period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm, index=data.index).rolling(window=self.period).mean() / atr)

        # Calculate DX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

        # Calculate ADX
        adx = dx.rolling(window=self.period).mean()

        return adx

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        strong_trend_threshold: float = 25.0,
        weak_trend_threshold: float = 20.0
    ) -> pd.DataFrame:
        """
        Calculate ADX with trend strength signals

        Args:
            data: DataFrame with OHLC data
            strong_trend_threshold: Strong trend threshold (default: 25)
            weak_trend_threshold: Weak trend threshold (default: 20)

        Returns:
            pd.DataFrame: DataFrame with ADX values and trend signals
        """
        adx = self.calculate(data)

        # Determine trend strength
        strong_trend = adx > strong_trend_threshold
        weak_trend = (adx > weak_trend_threshold) & (adx <= strong_trend_threshold)
        no_trend = adx <= weak_trend_threshold

        return pd.DataFrame({
            'adx': adx,
            'strong_trend': strong_trend,
            'weak_trend': weak_trend,
            'no_trend': no_trend,
            'strong_trend_threshold': strong_trend_threshold,
            'weak_trend_threshold': weak_trend_threshold
        }, index=data.index)
