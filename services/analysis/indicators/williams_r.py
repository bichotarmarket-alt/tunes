"""
Williams %R Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class WilliamsR(TechnicalIndicator):
    """Williams %R indicator"""

    def __init__(self, period: int = 5, overbought: float = -20.0, oversold: float = -80.0):
        """
        Initialize Williams %R indicator

        Args:
            period: Williams %R period (default: 14)
            overbought: Overbought threshold (default: -20.0)
            oversold: Oversold threshold (default: -80.0)
        """
        super().__init__("WilliamsR")
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def validate_parameters(self, **kwargs) -> bool:
        """Validate Williams %R parameters"""
        period = kwargs.get('period', self.period)
        overbought = kwargs.get('overbought', self.overbought)
        oversold = kwargs.get('oversold', self.oversold)
        return (
            isinstance(period, int) and period > 0 and
            isinstance(overbought, (int, float)) and
            isinstance(oversold, (int, float)) and
            overbought > oversold
        )

    @cached_indicator("WilliamsR")
    @handle_indicator_errors("WilliamsR", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate Williams %R values

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)

        Returns:
            pd.Series: Williams %R values (-100 to 0)
        """
        # Validate input data
        validate_dataframe(data, ['high', 'low', 'close'], min_rows=self.period)

        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', 'close' columns")

        if len(data) < self.period:
            logger.warning(f"Not enough data points for Williams %R calculation (need {self.period}, got {len(data)})")
            return pd.Series([np.nan] * len(data), index=data.index)

        high = data['high']
        low = data['low']
        close = data['close']

        # Validate data integrity
        if (high < low).any():
            logger.warning("Williams %R: Detected invalid data (high < low), applying correction")
            high = np.maximum(high, low)

        # Check for extreme values
        max_price = high.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"Williams %R: Detected extreme price values (max: {max_price})")
            return pd.Series([np.nan] * len(data), index=data.index)

        # Calculate highest high and lowest low over the period
        highest_high = high.rolling(window=self.period).max()
        lowest_low = low.rolling(window=self.period).min()

        # Calculate Williams %R with division by zero protection
        denominator = highest_high - lowest_low
        williams_r = -100 * (highest_high - close) / denominator.replace(0, np.nan)

        # Clip to valid range (-100 to 0)
        williams_r = williams_r.clip(-100, 0)

        return williams_r

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = -20.0,
        oversold_threshold: float = -80.0
    ) -> pd.DataFrame:
        """
        Calculate Williams %R with trading signals

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level (default: -20)
            oversold_threshold: Oversold level (default: -80)

        Returns:
            pd.DataFrame: DataFrame with Williams %R values and signals
        """
        williams_r = self.calculate(data)

        if williams_r.empty:
            logger.warning("Williams %R: No data available for signal calculation")
            return pd.DataFrame()

        # Generate signals using vectorization
        signals = pd.Series('hold', index=data.index)
        signals.loc[williams_r > overbought_threshold] = 'sell'
        signals.loc[williams_r < oversold_threshold] = 'buy'
        signals.loc[williams_r.isna()] = 'hold'

        result = pd.DataFrame({
            'williams_r': williams_r,
            'signal': signals
        }, index=data.index)

        return result

    def get_latest_signal(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = -20.0,
        oversold_threshold: float = -80.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest Williams %R signal

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level
            oversold_threshold: Oversold level

        Returns:
            Optional[Dict]: Signal information or None
        """
        williams_r = self.calculate(data)

        if williams_r.empty or williams_r.isna().all():
            logger.warning("Williams %R: No valid signal available")
            return None

        latest_val = williams_r.iloc[-1]

        signal = {
            'williams_r': latest_val,
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

    def calculate_divergence(
        self,
        data: pd.DataFrame,
        lookback: int = 14
    ) -> Dict[str, Any]:
        """
        Detect divergence between price and Williams %R

        Args:
            data: DataFrame with OHLC data
            lookback: Period to check for divergence

        Returns:
            Dict: Divergence information
        """
        if len(data) < self.period + lookback:
            return {'divergence': 'none'}

        williams_r = self.calculate(data)
        close = data['close']

        # Get current and historical values
        current_close = close.iloc[-1]
        current_wr = williams_r.iloc[-1]
        
        # Get highest/lowest from lookback period
        past_close_high = close.iloc[-lookback:-1].max()
        past_close_low = close.iloc[-lookback:-1].min()
        past_wr_high = williams_r.iloc[-lookback:-1].max()
        past_wr_low = williams_r.iloc[-lookback:-1].min()

        divergence = 'none'

        # Bullish divergence: lower lows + higher Williams %R (less negative)
        if (current_close < past_close_low and 
            current_wr > past_wr_low):
            divergence = 'bullish'

        # Bearish divergence: higher highs + lower Williams %R (more negative)
        elif (current_close > past_close_high and 
              current_wr < past_wr_high):
            divergence = 'bearish'

        return {
            'divergence': divergence,
            'current_close': current_close,
            'current_wr': current_wr,
            'past_close_high': past_close_high,
            'past_close_low': past_close_low,
            'past_wr_high': past_wr_high,
            'past_wr_low': past_wr_low
        }
