"""EMA (Exponential Moving Average) indicator"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class EMA(TechnicalIndicator):
    """Exponential Moving Average indicator"""

    def __init__(self, period: int = 5):
        """
        Initialize EMA indicator

        Args:
            period: EMA period (default: 20)
        """
        super().__init__("EMA")
        self.period = period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate EMA parameters"""
        period = kwargs.get('period', self.period)
        return isinstance(period, int) and period > 0

    @cached_indicator("EMA")
    @handle_indicator_errors("EMA", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate EMA values

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            pd.Series: EMA values
        """
        # Validate input data
        validate_dataframe(data, ['close'], min_rows=self.period)

        if 'close' not in data.columns:
            raise ValueError("DataFrame must have 'close' column")

        if len(data) < self.period:
            return pd.Series([np.nan] * len(data), index=data.index)

        close = data['close']
        ema = close.ewm(span=self.period, adjust=False).mean()

        return ema
