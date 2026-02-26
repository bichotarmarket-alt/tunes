"""Base class for technical indicators"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd


class TechnicalIndicator(ABC):
    """Base class for technical indicators"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate indicator values

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            pd.Series: Indicator values
        """
        pass

    @abstractmethod
    def validate_parameters(self, **kwargs) -> bool:
        """
        Validate indicator parameters

        Returns:
            bool: True if parameters are valid
        """
        pass

    def get_signal(self, value: float, oversold: float, overbought: float) -> Optional[str]:
        """
        Get trading signal based on indicator value

        Args:
            value: Indicator value
            oversold: Oversold threshold
            overbought: Overbought threshold

        Returns:
            Optional[str]: 'buy', 'sell', or None
        """
        if value <= oversold:
            return 'buy'
        elif value >= overbought:
            return 'sell'
        return None

    def calculate_confidence(self, value: float, oversold: float, overbought: float) -> float:
        """
        Calculate confidence level of signal

        Args:
            value: Indicator value
            oversold: Oversold threshold
            overbought: Overbought threshold

        Returns:
            float: Confidence level (0.0 to 1.0)
        """
        if value <= oversold:
            # Closer to 0 = higher confidence
            return min(1.0, (oversold - value) / 10.0)
        elif value >= overbought:
            # Closer to 100 = higher confidence
            return min(1.0, (value - overbought) / 10.0)
        return 0.0
