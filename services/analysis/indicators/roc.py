"""
ROC (Rate of Change) Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class ROC(TechnicalIndicator):
    """Rate of Change indicator"""

    def __init__(self, period: int = 5, overbought: float = 2.0, oversold: float = -2.0):
        """
        Initialize ROC indicator

        Args:
            period: ROC period (default: 12)
            overbought: Overbought threshold (default: 2.0)
            oversold: Oversold threshold (default: -2.0)
        """
        super().__init__("ROC")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def validate_parameters(self, **kwargs) -> bool:
        """Validate ROC parameters"""
        period = kwargs.get('period', self.period)
        overbought = kwargs.get('overbought', self.overbought)
        oversold = kwargs.get('oversold', self.oversold)
        return (
            isinstance(period, int) and period > 0 and
            isinstance(overbought, (int, float)) and
            isinstance(oversold, (int, float)) and
            overbought > oversold
        )

    @cached_indicator("ROC")
    @handle_indicator_errors("ROC", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate ROC values

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            pd.Series: ROC values as percentage
        """
        # Validate input data
        validate_dataframe(data, ['close'], min_rows=self.period)

        if 'close' not in data.columns:
            raise ValueError("DataFrame must have 'close' column")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for ROC calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        close = data['close']

        # Validate data integrity
        if (close < 0).any():
            logger.warning("ROC: Detected negative price values, applying correction")
            close = close.clip(lower=0)

        # Check for extreme values
        max_price = close.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"ROC: Detected extreme price values (max: {max_price})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate ROC as percentage with division by zero protection
        close_shifted = close.shift(self.period)
        denominator = close_shifted.replace(0, np.nan)

        # Handle NaN in denominator before division
        roc = np.where(denominator.notna() & (denominator != 0),
                      ((close - close_shifted) / denominator) * 100,
                      np.nan)

        roc_series = pd.Series(roc, index=data.index)

        # Clip extreme values to prevent overflow
        roc_series = roc_series.clip(-10000, 10000)

        return roc_series

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 5.0,
        oversold_threshold: float = -5.0
    ) -> pd.DataFrame:
        """
        Calculate ROC with trading signals

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level (default: 5.0)
            oversold_threshold: Oversold level (default: -5.0)

        Returns:
            pd.DataFrame: DataFrame with ROC values and signals
        """
        roc = self.calculate(data)

        if roc.empty:
            logger.warning("ROC: No data available for signal calculation")
            return pd.DataFrame()

        # Generate signals using vectorization
        signals = pd.Series('hold', index=data.index)
        signals.loc[roc > overbought_threshold] = 'sell'
        signals.loc[roc < oversold_threshold] = 'buy'
        signals.loc[roc.isna()] = 'hold'

        result = pd.DataFrame({
            'roc': roc,
            'signal': signals
        }, index=data.index)

        return result

    def get_latest_signal(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 5.0,
        oversold_threshold: float = -5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest ROC signal

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level
            oversold_threshold: Oversold level

        Returns:
            Optional[Dict]: Signal information or None
        """
        roc = self.calculate(data)

        if roc.empty or roc.isna().all():
            logger.warning("ROC: No valid signal available")
            return None

        latest_val = roc.iloc[-1]

        signal = {
            'roc': latest_val,
            'signal': 'hold',
            'timestamp': data.index[-1]
        }

        if pd.isna(latest_val):
            signal['signal'] = 'hold'
        elif latest_val > overbought_threshold:
            signal['signal'] = 'sell'
        elif latest_val < oversold_threshold:
            signal['signal'] = 'buy'

        return signal

    def calculate_zero_crossing(
        self,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate ROC with zero crossing signals

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.DataFrame: DataFrame with ROC and zero crossing signals
        """
        roc = self.calculate(data)
        
        if roc.empty:
            return pd.DataFrame()

        # Detect zero crossings
        zero_cross_up = (roc > 0) & (roc.shift(1) <= 0)
        zero_cross_down = (roc < 0) & (roc.shift(1) >= 0)

        result = pd.DataFrame({
            'roc': roc,
            'zero_cross_up': zero_cross_up,
            'zero_cross_down': zero_cross_down
        }, index=data.index)

        return result

    def calculate_momentum(
        self,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate ROC momentum analysis

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.DataFrame: DataFrame with ROC momentum data
        """
        roc = self.calculate(data)
        
        if roc.empty:
            return pd.DataFrame()

        # Calculate momentum indicators
        roc_ma = roc.rolling(window=3).mean()  # 3-period ROC MA
        roc_change = roc.diff()  # Rate of change of ROC

        result = pd.DataFrame({
            'roc': roc,
            'roc_ma': roc_ma,
            'roc_change': roc_change
        }, index=data.index)

        return result

    def calculate_acceleration(
        self,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate ROC acceleration (second derivative)

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.DataFrame: DataFrame with ROC acceleration
        """
        roc = self.calculate(data)
        
        if roc.empty:
            return pd.DataFrame()

        # Calculate acceleration (second derivative)
        roc_acceleration = roc.diff().diff()

        result = pd.DataFrame({
            'roc': roc,
            'roc_acceleration': roc_acceleration
        }, index=data.index)

        return result
