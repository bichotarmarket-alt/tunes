"""SMA (Simple Moving Average) indicator"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class SMA(TechnicalIndicator):
    """Simple Moving Average indicator"""

    def __init__(self, period: int = 5):
        """
        Initialize SMA indicator

        Args:
            period: SMA period (default: 20)
        """
        super().__init__("SMA")
        self.period = period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate SMA parameters"""
        period = kwargs.get('period', self.period)
        return isinstance(period, int) and period > 0

    @cached_indicator("SMA")
    @handle_indicator_errors("SMA", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate SMA values

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            pd.Series: SMA values
        """
        # Validate input data
        validate_dataframe(data, ['close'], min_rows=self.period)

        if 'close' not in data.columns:
            raise ValueError("DataFrame must have 'close' column")

        if len(data) < self.period:
            return pd.Series([np.nan] * len(data), index=data.index)

        close = data['close']
        sma = close.rolling(window=self.period).mean()

        return sma
