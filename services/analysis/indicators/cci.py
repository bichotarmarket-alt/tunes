"""
CCI (Commodity Channel Index) Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class CCI(TechnicalIndicator):
    """Commodity Channel Index indicator"""

    def __init__(self, period: int = 5, overbought: float = 100.0, oversold: float = -100.0):
        """
        Initialize CCI indicator

        Args:
            period: CCI period (default: 20)
            overbought: Overbought threshold (default: 100.0)
            oversold: Oversold threshold (default: -100.0)
        """
        super().__init__("CCI")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def validate_parameters(self, **kwargs) -> bool:
        """Validate CCI parameters"""
        period = kwargs.get('period', self.period)
        overbought = kwargs.get('overbought', self.overbought)
        oversold = kwargs.get('oversold', self.oversold)
        return (
            isinstance(period, int) and period > 0 and
            isinstance(overbought, (int, float)) and
            isinstance(oversold, (int, float)) and
            overbought > oversold
        )

    @cached_indicator("CCI")
    @handle_indicator_errors("CCI", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate CCI values

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)

        Returns:
            pd.Series: CCI values
        """
        # Validate input data
        validate_dataframe(data, ['high', 'low', 'close'], min_rows=self.period)
        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', 'close' columns")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for CCI calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        high = data['high']
        low = data['low']
        close = data['close']

        # Validate data integrity
        if (high < low).any():
            logger.warning("CCI: Detected invalid data (high < low), applying correction")
            high = np.maximum(high, low)

        # Check for extreme values that could cause overflow
        max_price = high.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"CCI: Detected extreme price values (max: {max_price})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate typical price (TP)
        tp = (high + low + close) / 3

        # Calculate simple moving average of TP
        sma_tp = tp.rolling(window=self.period).mean()

        # Calculate mean deviation using vectorized approach (faster than apply)
        tp_rolling = tp.rolling(window=self.period)
        mean_tp = tp_rolling.mean()
        md = (tp - mean_tp).abs().rolling(window=self.period).mean()

        # Calculate CCI with division by zero protection
        denominator = 0.015 * md
        cci = (tp - sma_tp) / denominator.replace(0, np.nan)

        # Clip extreme values to prevent overflow
        cci = cci.clip(-1000, 1000)

        return cci

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 100.0,
        oversold_threshold: float = -100.0
    ) -> pd.DataFrame:
        """
        Calculate CCI with trading signals

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level (default: 100)
            oversold_threshold: Oversold level (default: -100)

        Returns:
            pd.DataFrame: DataFrame with CCI values and signals
        """
        cci = self.calculate(data)

        if cci.empty:
            logger.warning("CCI: No data available for signal calculation")
            return pd.DataFrame()

        # Generate signals using vectorization
        signals = pd.Series('hold', index=data.index)
        signals.loc[cci > overbought_threshold] = 'sell'
        signals.loc[cci < oversold_threshold] = 'buy'
        signals.loc[cci.isna()] = 'hold'

        result = pd.DataFrame({
            'cci': cci,
            'signal': signals
        }, index=data.index)

        return result

    def get_latest_signal(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 100.0,
        oversold_threshold: float = -100.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest CCI signal

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level
            oversold_threshold: Oversold level

        Returns:
            Optional[Dict]: Signal information or None
        """
        cci = self.calculate(data)

        if cci.empty or cci.isna().all():
            logger.warning("CCI: No valid signal available")
            return None

        latest_val = cci.iloc[-1]

        signal = {
            'cci': latest_val,
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
        Calculate CCI with zero crossing signals

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.DataFrame: DataFrame with CCI and zero crossing signals
        """
        cci = self.calculate(data)
        
        if cci.empty:
            return pd.DataFrame()

        # Detect zero crossings
        zero_cross_up = (cci > 0) & (cci.shift(1) <= 0)
        zero_cross_down = (cci < 0) & (cci.shift(1) >= 0)

        result = pd.DataFrame({
            'cci': cci,
            'zero_cross_up': zero_cross_up,
            'zero_cross_down': zero_cross_down
        }, index=data.index)

        return result

    def calculate_trend_lines(
        self,
        data: pd.DataFrame,
        deviation_multiplier: float = 2.0
    ) -> pd.DataFrame:
        """
        Calculate CCI with trend lines based on overbought/oversold thresholds

        Args:
            data: DataFrame with OHLC data
            deviation_multiplier: Multiplier for deviation bands

        Returns:
            pd.DataFrame: DataFrame with CCI and trend lines
        """
        cci = self.calculate(data)

        if cci.empty:
            return pd.DataFrame()

        # Calculate trend lines based on overbought/oversold thresholds
        upper_line = pd.Series([self.overbought] * len(cci), index=cci.index)
        lower_line = pd.Series([self.oversold] * len(cci), index=cci.index)

        result = pd.DataFrame({
            'cci': cci,
            'upper_line': upper_line,
            'lower_line': lower_line
        }, index=data.index)

        return result
