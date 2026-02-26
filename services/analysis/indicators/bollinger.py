"""Bollinger Bands indicator"""
import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class BollingerBands(TechnicalIndicator):
    """Bollinger Bands indicator"""

    def __init__(self, period: int = 5, std_dev: float = 2.0):
        """
        Initialize Bollinger Bands indicator

        Args:
            period: Period for moving average (default: 20)
            std_dev: Standard deviation multiplier (default: 2.0)
        """
        super().__init__("Bollinger Bands")
        self.period = period
        self.std_dev = std_dev

    def validate_parameters(self, **kwargs) -> bool:
        """Validate Bollinger Bands parameters"""
        period = kwargs.get('period', self.period)
        std_dev = kwargs.get('std_dev', self.std_dev)

        return (
            isinstance(period, int) and period > 0 and
            isinstance(std_dev, (int, float)) and std_dev > 0
        )

    @cached_indicator("Bollinger")
    @handle_indicator_errors("Bollinger", fallback_value=(None, None, None))
    def calculate(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Args:
            data: DataFrame with OHLC data (must have 'close' column)

        Returns:
            Tuple: (upper_band, middle_band, lower_band)
        """
        # Validate input data
        validate_dataframe(data, ['close'], min_rows=self.period)

        if 'close' not in data.columns:
            raise ValueError("DataFrame must have 'close' column")

        close = data['close']

        # Validate data integrity
        if (close < 0).any():
            logger.warning("Bollinger Bands: Detected negative price values, applying correction")
            close = close.clip(lower=0)

        # Check for extreme values
        max_price = close.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"Bollinger Bands: Detected extreme price values (max: {max_price})")
            return (
                pd.Series([np.nan] * len(data), index=data.index),
                pd.Series([np.nan] * len(data), index=data.index),
                pd.Series([np.nan] * len(data), index=data.index)
            )

        # Calculate middle band (SMA)
        middle_band = close.rolling(window=self.period).mean()

        # Calculate standard deviation
        std = close.rolling(window=self.period).std()

        # Calculate upper and lower bands
        upper_band = middle_band + (std * self.std_dev)
        lower_band = middle_band - (std * self.std_dev)

        # Clip extreme values to prevent overflow
        upper_band = upper_band.clip(-1e10, 1e10)
        lower_band = lower_band.clip(-1e10, 1e10)

        return upper_band, middle_band, lower_band

    def get_signal(
        self,
        data: pd.DataFrame
    ) -> Optional[str]:
        """
        Get trading signal based on Bollinger Bands

        Args:
            data: DataFrame with OHLC data

        Returns:
            Optional[str]: 'buy', 'sell', or None
        """
        if len(data) < self.period:
            return None

        upper_band, middle_band, lower_band = self.calculate(data)
        close = data['close']

        # Check if price touches bands
        latest_close = close.iloc[-1]
        latest_upper = upper_band.iloc[-1]
        latest_lower = lower_band.iloc[-1]

        # Buy signal: price touches lower band
        if latest_close <= latest_lower:
            return 'buy'

        # Sell signal: price touches upper band
        if latest_close >= latest_upper:
            return 'sell'

        return None

    def calculate_bandwidth(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate Bollinger Bandwidth

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.Series: Bandwidth values
        """
        upper_band, middle_band, lower_band = self.calculate(data)
        bandwidth = (upper_band - lower_band) / middle_band.replace(0, np.nan) * 100
        return bandwidth

    def calculate_percent_b(self, data: pd.DataFrame) -> pd.Series:
        """
        Calculate %B (Percent B)

        Args:
            data: DataFrame with OHLC data

        Returns:
            pd.Series: %B values
        """
        upper_band, middle_band, lower_band = self.calculate(data)
        close = data['close']

        denominator = (upper_band - lower_band).replace(0, np.nan)
        percent_b = (close - lower_band) / denominator * 100
        return percent_b

    def detect_squeeze(self, data: pd.DataFrame, threshold: float = 0.5) -> pd.Series:
        """
        Detect squeeze (when bands are very narrow)

        Args:
            data: DataFrame with OHLC data
            threshold: Bandwidth threshold for squeeze detection (default: 0.5%)

        Returns:
            pd.Series: Boolean series indicating squeeze
        """
        bandwidth = self.calculate_bandwidth(data)
        squeeze = bandwidth < threshold
        return squeeze

    def detect_squeeze_release(self, data: pd.DataFrame, lookback: int = 5) -> str:
        """
        Detect squeeze release (when bands start expanding after squeeze)

        Args:
            data: DataFrame with OHLC data
            lookback: Periods to check for squeeze release

        Returns:
            str: 'bullish', 'bearish', or 'none'
        """
        if len(data) < self.period + lookback:
            return 'none'

        bandwidth = self.calculate_bandwidth(data)
        squeeze = self.detect_squeeze(data)
        close = data['close']

        # Check if we were in squeeze recently
        recent_squeeze = squeeze.iloc[-lookback:-1].any()

        if not recent_squeeze:
            return 'none'

        # Check if bandwidth is expanding now
        current_bandwidth = bandwidth.iloc[-1]
        avg_bandwidth = bandwidth.iloc[-lookback:-1].mean()

        if current_bandwidth > avg_bandwidth * 1.2:  # 20% expansion
            # Determine direction based on price movement
            price_change = (close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]
            if price_change > 0:
                return 'bullish'
            elif price_change < 0:
                return 'bearish'

        return 'none'

    def detect_breakout(
        self,
        data: pd.DataFrame,
        upper_band: pd.Series,
        lower_band: pd.Series
    ) -> Optional[str]:
        """
        Detecta breakout das bandas

        Args:
            data: DataFrame com OHLC
            upper_band: Banda superior
            lower_band: Banda inferior

        Returns:
            'buy', 'sell', ou None
        """
        try:
            close = data['close']
            latest_close = close.iloc[-1]
            prev_close = close.iloc[-2]

            latest_upper = upper_band.iloc[-1]
            latest_lower = lower_band.iloc[-1]

            # Breakout superior
            if prev_close <= latest_upper and latest_close > latest_upper:
                logger.info(f"✓ Breakout superior detectado: {latest_close:.5f} > {latest_upper:.5f}")
                return 'sell'

            # Breakout inferior
            if prev_close >= latest_lower and latest_close < latest_lower:
                logger.info(f"✓ Breakout inferior detectado: {latest_close:.5f} < {latest_lower:.5f}")
                return 'buy'

            return None

        except Exception as e:
            logger.error(f"Erro ao detectar breakout: {e}", exc_info=True)
            return None

    def filter_signals(
        self,
        data: pd.DataFrame,
        signal: str
    ) -> bool:
        """
        Filtra sinais baseado em condições de mercado

        Args:
            data: DataFrame com OHLC
            signal: Sinal ('buy' ou 'sell')

        Returns:
            bool: True se sinal deve ser mantido
        """
        try:
            # Detectar mercado lateral
            is_ranging = self._is_ranging_market(data)

            # Detectar baixa volatilidade
            is_low_volatility = self._is_low_volatility(data)

            # Filtrar se mercado lateral ou baixa volatilidade
            if is_ranging or is_low_volatility:
                logger.debug(f"❌ Sinal {signal} filtrado: mercado lateral ou baixa volatilidade")
                return False

            return True

        except Exception as e:
            logger.error(f"Erro ao filtrar sinais: {e}", exc_info=True)
            return True

    def _is_ranging_market(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> bool:
        """
        Detecta se o mercado está lateral

        Args:
            data: DataFrame com OHLC
            lookback: Período para análise

        Returns:
            bool: True se mercado lateral
        """
        try:
            close = data['close'].iloc[-lookback:]

            # Calcular range
            high = close.max()
            low = close.min()
            range_pct = (high - low) / low

            # Se range < 2%, mercado lateral
            return range_pct < 0.02

        except Exception as e:
            logger.error(f"Erro ao detectar mercado lateral: {e}", exc_info=True)
            return False

    def _is_low_volatility(
        self,
        data: pd.DataFrame,
        lookback: int = 20
    ) -> bool:
        """
        Detecta se há baixa volatilidade

        Args:
            data: DataFrame com OHLC
            lookback: Período para análise

        Returns:
            bool: True se baixa volatilidade
        """
        try:
            close = data['close'].iloc[-lookback:]

            # Calcular volatilidade (desvio padrão)
            volatility = close.pct_change().std()

            # Se volatilidade < 1%, baixa volatilidade
            return volatility < 0.01

        except Exception as e:
            logger.error(f"Erro ao detectar baixa volatilidade: {e}", exc_info=True)
            return False

    def calculate_signal_strength(
        self,
        data: pd.DataFrame,
        upper_band: pd.Series,
        lower_band: pd.Series
    ) -> float:
        """
        Calcula força do sinal (0.0 a 1.0)

        Args:
            data: DataFrame com OHLC
            upper_band: Banda superior
            lower_band: Banda inferior

        Returns:
            float: Força do sinal
        """
        try:
            close = data['close'].iloc[-1]
            middle_band = (upper_band + lower_band) / 2

            # Distância do meio
            distance = abs(close - middle_band.iloc[-1])
            max_distance = (upper_band.iloc[-1] - lower_band.iloc[-1]) / 2

            if max_distance == 0:
                return 0.0

            return min(1.0, distance / max_distance)

        except Exception as e:
            logger.error(f"Erro ao calcular força do sinal: {e}", exc_info=True)
            return 0.0

    def confirm_trend(
        self,
        data: pd.DataFrame,
        min_adx: float = 25.0
    ) -> Optional[str]:
        """
        Confirma se há tendência forte

        Args:
            data: DataFrame com OHLC
            min_adx: Mínimo ADX para considerar tendência forte

        Returns:
            'uptrend', 'downtrend', ou None
        """
        try:
            # Calcular ADX
            adx = self._calculate_adx(data)

            if len(adx) == 0:
                return None

            current_adx = adx.iloc[-1]

            # Verificar se há tendência forte
            if current_adx < min_adx:
                logger.debug(f"ADX {current_adx:.2f} < {min_adx}: sem tendência forte")
                return None

            # Determinar direção da tendência
            close = data['close']
            sma_fast = close.rolling(window=20).mean()
            sma_slow = close.rolling(window=50).mean()

            if len(sma_fast) == 0 or len(sma_slow) == 0:
                return None

            if sma_fast.iloc[-1] > sma_slow.iloc[-1]:
                logger.info(f"✓ Tendência de alta detectada (ADX: {current_adx:.2f})")
                return 'uptrend'
            else:
                logger.info(f"✓ Tendência de baixa detectada (ADX: {current_adx:.2f})")
                return 'downtrend'

        except Exception as e:
            logger.error(f"Erro ao confirmar tendência: {e}", exc_info=True)
            return None

    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calcula ADX (Average Directional Index)

        Args:
            data: DataFrame com OHLC
            period: Período para cálculo (default 14)

        Returns:
            pd.Series: Valores de ADX
        """
        try:
            high = data['high']
            low = data['low']
            close = data['close']

            # Calcular True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # Calcular +DM e -DM
            plus_dm = high.diff()
            minus_dm = low.diff()

            plus_dm = plus_dm.where((plus_dm > 0) & (plus_dm > minus_dm), 0)
            minus_dm = minus_dm.where((minus_dm > 0) & (minus_dm > plus_dm), 0)

            # Calcular médias
            atr = tr.rolling(window=period).mean()
            plus_dm_smooth = plus_dm.rolling(window=period).mean()
            minus_dm_smooth = minus_dm.rolling(window=period).mean()

            # Calcular +DI e -DI
            plus_di = 100 * (plus_dm_smooth / atr)
            minus_di = 100 * (minus_dm_smooth / atr)

            # Calcular DX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

            # Calcular ADX
            adx = dx.rolling(window=period).mean()

            return adx

        except Exception as e:
            logger.error(f"Erro ao calcular ADX: {e}", exc_info=True)
            return pd.Series([0] * len(data))
