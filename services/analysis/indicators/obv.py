"""OBV (On Balance Volume) indicator"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class OBV(TechnicalIndicator):
    """On Balance Volume indicator"""

    def __init__(self, period: int = 14, signal_period: int = 9):
        """
        Initialize OBV indicator

        Args:
            period: OBV calculation period (default: 14)
            signal_period: Signal line EMA period (default: 9)
        """
        super().__init__("OBV")
        self.period = period
        self.signal_period = signal_period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate OBV parameters"""
        period = kwargs.get('period', self.period)
        signal_period = kwargs.get('signal_period', self.signal_period)
        return (
            isinstance(period, int) and period > 0 and
            isinstance(signal_period, int) and signal_period > 0
        )

    @cached_indicator("OBV")
    @handle_indicator_errors("OBV", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate OBV values

        Args:
            data: DataFrame with OHLCV data (must have 'close' and 'volume' columns)

        Returns:
            pd.Series: OBV values
        """
        # Validate input data - OBV needs close and volume
        validate_dataframe(data, ['close', 'volume'], min_rows=2)

        close = data['close']
        volume = data['volume']

        # Calculate price change
        price_change = close.diff()

        # Calculate OBV
        obv = pd.Series(0, index=data.index, dtype=float)

        for i in range(1, len(data)):
            if price_change.iloc[i] > 0:
                # Closing price up: add volume
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif price_change.iloc[i] < 0:
                # Closing price down: subtract volume
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                # No change: keep same OBV
                obv.iloc[i] = obv.iloc[i-1]

        return obv

    def get_signal(self, data: pd.DataFrame) -> Optional[str]:
        """
        Get trading signal based on OBV trend

        Args:
            data: DataFrame with OHLC data

        Returns:
            Optional[str]: 'buy', 'sell', or None
        """
        if len(data) < self.period + 2:
            return None

        obv = self.calculate(data)

        if len(obv) < self.period + 2:
            return None

        # Calculate OBV EMA (signal line)
        obv_ema = obv.ewm(span=self.signal_period, adjust=False).mean()

        # OBV crosses above its EMA = bullish
        if obv.iloc[-2] <= obv_ema.iloc[-2] and obv.iloc[-1] > obv_ema.iloc[-1]:
            return 'buy'
        # OBV crosses below its EMA = bearish
        elif obv.iloc[-2] >= obv_ema.iloc[-2] and obv.iloc[-1] < obv_ema.iloc[-1]:
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

        obv = self.calculate(data)

        if len(obv) == 0 or pd.isna(obv.iloc[-1]):
            return 0.0

        # Calculate OBV momentum (rate of change)
        obv_roc = abs(obv.iloc[-1] - obv.iloc[-min(self.period, len(obv))]) / abs(obv.iloc[-min(self.period, len(obv))] + 1)

        # Higher momentum = higher confidence (max 1.0 at 50% change)
        return min(1.0, obv_roc / 0.5)
