"""
ATR (Average True Range) Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class ATR(TechnicalIndicator):
    """Average True Range indicator"""

    def __init__(self, period: int = 5):
        """
        Initialize ATR indicator

        Args:
            period: ATR period (default: 14)
        """
        super().__init__("ATR")
        self.period = period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate ATR parameters"""
        period = kwargs.get('period', self.period)
        return isinstance(period, int) and period > 0

    @cached_indicator("ATR")
    @handle_indicator_errors("ATR", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate ATR values

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)

        Returns:
            pd.Series: ATR values
        """
        # Validate input data
        validate_dataframe(data, ['high', 'low', 'close'], min_rows=self.period)

        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', 'close' columns")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for ATR calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        high = data['high']
        low = data['low']
        close = data['close']

        # Calculate True Range components
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # First TR is just high - low (no previous close)
        true_range.iloc[0] = high.iloc[0] - low.iloc[0]

        # Calculate ATR using Wilder's smoothing
        atr = true_range.ewm(alpha=1 / self.period, adjust=False, min_periods=self.period).mean()

        return atr

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        volatility_threshold: float = 0.02
    ) -> pd.DataFrame:
        """
        Calculate ATR with volatility signals

        Args:
            data: DataFrame with OHLC data
            volatility_threshold: Threshold for high volatility (default: 2%)

        Returns:
            pd.DataFrame: DataFrame with ATR and signals
        """
        atr = self.calculate(data)
        
        result = data.copy()
        result['atr'] = atr
        result['atr_percent'] = atr / data['close'].replace(0, np.nan) * 100
        
        # Volatility signal
        result['volatility_signal'] = result['atr_percent'].apply(
            lambda x: 'high' if x > volatility_threshold else 'normal'
        )
        
        # ATR-based support/resistance levels
        result['resistance'] = data['close'] + atr
        result['support'] = data['close'] - atr
        
        return result

    def get_latest_signal(
        self,
        data: pd.DataFrame,
        volatility_threshold: float = 0.02
    ) -> Optional[Dict[str, Any]]:
        """
        Get the latest ATR-based volatility signal

        Args:
            data: DataFrame with OHLC data
            volatility_threshold: Threshold for high volatility

        Returns:
            Optional[Dict]: Volatility signal or None
        """
        if len(data) < self.period:
            return None

        atr_values = self.calculate(data)
        latest_atr = atr_values.iloc[-1]
        latest_close = data['close'].iloc[-1]

        atr_percent = (latest_atr / latest_close) * 100 if latest_close else 0.0

        signal = {
            'atr': latest_atr,
            'atr_percent': atr_percent,
            'volatility': 'high' if atr_percent > volatility_threshold else 'normal',
            'timestamp': data.index[-1]
        }

        return signal
