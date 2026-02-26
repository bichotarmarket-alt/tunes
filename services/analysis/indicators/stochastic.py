"""
Stochastic Oscillator Indicator
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class Stochastic(TechnicalIndicator):
    """Stochastic Oscillator indicator"""

    def __init__(self, k_period: int = 5, d_period: int = 2):
        """
        Initialize Stochastic indicator

        Args:
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)
        """
        super().__init__("Stochastic")
        self.k_period = k_period
        self.d_period = d_period

    def validate_parameters(self, **kwargs) -> bool:
        """Validate Stochastic parameters"""
        k_period = kwargs.get('k_period', self.k_period)
        d_period = kwargs.get('d_period', self.d_period)
        return isinstance(k_period, int) and k_period > 0 and isinstance(d_period, int) and d_period > 0

    @cached_indicator("Stochastic")
    @handle_indicator_errors("Stochastic", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Stochastic values

        Args:
            data: DataFrame with OHLC data (must have 'high', 'low', 'close' columns)

        Returns:
            pd.DataFrame: DataFrame with %K and %D values
        """
        # Validate input data
        validate_dataframe(data, ['high', 'low', 'close'], min_rows=self.k_period)

        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', 'close' columns")

        if len(data) < self.k_period:
            logger.warning(f"Not enough data points for Stochastic calculation (need {self.k_period}, got {len(data)})")
            return pd.DataFrame()

        high = data['high']
        low = data['low']
        close = data['close']

        # Validate data integrity
        if (high < low).any():
            logger.warning("Stochastic: Detected invalid data (high < low), applying correction")
            high = np.maximum(high, low)

        # Check for extreme values
        max_price = high.max()
        if max_price > 1e10 or np.isinf(max_price) or np.isnan(max_price):
            logger.warning(f"Stochastic: Detected extreme price values (max: {max_price})")
            return pd.DataFrame()

        # Calculate rolling highest high and lowest low
        highest_high = high.rolling(window=self.k_period).max()
        lowest_low = low.rolling(window=self.k_period).min()

        # Calculate %K with division by zero protection
        denominator = (highest_high - lowest_low).replace(0, np.nan)
        k_percent = 100 * (close - lowest_low) / denominator

        # Calculate %D (smoothed %K)
        d_percent = k_percent.rolling(window=self.d_period).mean()

        # Clip to valid range (0 to 100)
        k_percent = k_percent.clip(0, 100)
        d_percent = d_percent.clip(0, 100)

        result = pd.DataFrame({
            '%K': k_percent,
            '%D': d_percent
        }, index=data.index)

        return result

    def calculate_with_signals(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 80.0,
        oversold_threshold: float = 20.0
    ) -> pd.DataFrame:
        """
        Calculate Stochastic with trading signals

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level (default: 80)
            oversold_threshold: Oversold level (default: 20)

        Returns:
            pd.DataFrame: DataFrame with Stochastic values and signals
        """
        stochastic = self.calculate(data)

        if stochastic.empty:
            logger.warning("Stochastic: No data available for signal calculation")
            return pd.DataFrame()

        # Generate signals using vectorization
        signals = pd.Series('hold', index=stochastic.index)
        signals.loc[stochastic['%K'] > overbought_threshold] = 'sell'
        signals.loc[stochastic['%K'] < oversold_threshold] = 'buy'
        signals.loc[stochastic['%K'].isna()] = 'hold'

        stochastic['signal'] = signals

        # Add crossover signals
        stochastic['k_cross_above_d'] = stochastic['%K'] > stochastic['%D']
        stochastic['k_cross_below_d'] = stochastic['%K'] < stochastic['%D']

        return stochastic

    def get_latest_signal(
        self,
        data: pd.DataFrame,
        overbought_threshold: float = 80.0,
        oversold_threshold: float = 20.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest Stochastic signal

        Args:
            data: DataFrame with OHLC data
            overbought_threshold: Overbought level
            oversold_threshold: Oversold level

        Returns:
            Optional[Dict]: Signal information or None
        """
        if len(data) < self.k_period:
            logger.warning("Stochastic: Not enough data points")
            return None

        stochastic = self.calculate(data)

        if stochastic.empty:
            logger.warning("Stochastic: No valid signal available")
            return None

        latest = stochastic.iloc[-1]
        k_val = latest['%K']
        d_val = latest['%D']

        signal = {
            '%K': k_val,
            '%D': d_val,
            'signal': 'hold',
            'timestamp': data.index[-1]
        }

        if pd.isna(k_val) or pd.isna(d_val):
            signal['signal'] = 'hold'
        elif k_val > overbought_threshold:
            signal['signal'] = 'sell'
        elif k_val < oversold_threshold:
            signal['signal'] = 'buy'

        return signal

    def calculate_fast_slow(
        self,
        data: pd.DataFrame,
        fast_k: int = 5,
        fast_d: int = 3,
        slow_k: int = 14,
        slow_d: int = 3
    ) -> pd.DataFrame:
        """
        Calculate both fast and slow Stochastic

        Args:
            data: DataFrame with OHLC data
            fast_k: Fast %K period (default: 5)
            fast_d: Fast %D period (default: 3)
            slow_k: Slow %K period (default: 14)
            slow_d: Slow %D period (default: 3)

        Returns:
            pd.DataFrame: DataFrame with fast and slow Stochastic values
        """
        # Fast Stochastic
        fast_stoch = Stochastic(k_period=fast_k, d_period=fast_d)
        fast_result = fast_stoch.calculate(data)
        fast_result.columns = ['fast_%K', 'fast_%D']

        # Slow Stochastic
        slow_stoch = Stochastic(k_period=slow_k, d_period=slow_d)
        slow_result = slow_stoch.calculate(data)
        slow_result.columns = ['slow_%K', 'slow_%D']

        # Combine results
        result = pd.concat([fast_result, slow_result], axis=1)

        return result

    def get_divergence(
        self,
        data: pd.DataFrame,
        lookback: int = 14
    ) -> Dict[str, Any]:
        """
        Detect divergence between price and Stochastic

        Args:
            data: DataFrame with OHLC data
            lookback: Period to check for divergence

        Returns:
            Dict: Divergence information
        """
        if len(data) < self.k_period + lookback:
            return {'divergence': 'none'}

        stochastic = self.calculate(data)
        close = data['close']

        # Get current and historical values
        current_close = close.iloc[-1]
        current_stoch = stochastic.iloc[-1]['%K']

        # Get highest/lowest from lookback period
        past_close_high = close.iloc[-lookback:-1].max()
        past_close_low = close.iloc[-lookback:-1].min()
        past_stoch_high = stochastic.iloc[-lookback:-1]['%K'].max()
        past_stoch_low = stochastic.iloc[-lookback:-1]['%K'].min()

        divergence = 'none'

        # Bullish divergence: lower lows + higher stochastic
        if (current_close < past_close_low and
            current_stoch > past_stoch_low):
            divergence = 'bullish'

        # Bearish divergence: higher highs + lower stochastic
        elif (current_close > past_close_high and
              current_stoch < past_stoch_high):
            divergence = 'bearish'

        return {
            'divergence': divergence,
            'current_close': current_close,
            'current_stoch': current_stoch,
            'past_close_high': past_close_high,
            'past_close_low': past_close_low,
            'past_stoch_high': past_stoch_high,
            'past_stoch_low': past_stoch_low
        }

    def detect_crossover_advanced(
        self,
        k_values: pd.Series,
        d_values: pd.Series,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detecção avançada de crossover %K/%D

        Args:
            k_values: Série de valores %K
            d_values: Série de valores %D
            data: DataFrame com OHLC

        Returns:
            Dict com tipo, força, confirmação
        """
        try:
            # Detectar crossover %K vs %D
            k_crossover = self._detect_line_crossover(k_values, d_values)

            # Detectar crossover com oversold/overbought
            oversold_crossover = self._detect_oversold_crossover(k_values)
            overbought_crossover = self._detect_overbought_crossover(k_values)

            # Calcular força do crossover
            strength = self._calculate_crossover_strength(k_values, d_values)

            # Validar com volume
            volume_confirmation = self._confirm_with_volume(data)

            result = {
                'k_crossover': k_crossover,
                'oversold_crossover': oversold_crossover,
                'overbought_crossover': overbought_crossover,
                'strength': strength,
                'volume_confirmation': volume_confirmation
            }

            logger.info(
                f"✓ Crossover %K/%D: {k_crossover} | Oversold: {oversold_crossover} | "
                f"Overbought: {overbought_crossover} | Força: {strength:.2f} | "
                f"Volume: {'✓' if volume_confirmation else '✗'}"
            )

            return result

        except Exception as e:
            logger.error(f"Erro ao detectar crossover avançado: {e}", exc_info=True)
            return {
                'k_crossover': 'none',
                'oversold_crossover': 'none',
                'overbought_crossover': 'none',
                'strength': 0,
                'volume_confirmation': False
            }

    def _detect_line_crossover(
        self,
        k_values: pd.Series,
        d_values: pd.Series
    ) -> str:
        """
        Detecta crossover entre %K e %D

        Returns:
            'bullish', 'bearish', ou 'none'
        """
        if len(k_values) < 2 or len(d_values) < 2:
            return 'none'

        # Bullish crossover: %K cruza de baixo para cima da %D
        if (k_values.iloc[-2] < d_values.iloc[-2] and
            k_values.iloc[-1] > d_values.iloc[-1]):
            return 'bullish'

        # Bearish crossover: %K cruza de cima para baixo da %D
        if (k_values.iloc[-2] > d_values.iloc[-2] and
            k_values.iloc[-1] < d_values.iloc[-1]):
            return 'bearish'

        return 'none'

    def _detect_oversold_crossover(
        self,
        k_values: pd.Series,
        oversold: float = 20.0
    ) -> str:
        """
        Detecta crossover com oversold

        Returns:
            'bullish', 'bearish', ou 'none'
        """
        if len(k_values) < 2:
            return 'none'

        # Bullish crossover: %K cruza de oversold para cima
        if k_values.iloc[-2] <= oversold and k_values.iloc[-1] > oversold:
            return 'bullish'

        return 'none'

    def _detect_overbought_crossover(
        self,
        k_values: pd.Series,
        overbought: float = 80.0
    ) -> str:
        """
        Detecta crossover com overbought

        Returns:
            'bullish', 'bearish', ou 'none'
        """
        if len(k_values) < 2:
            return 'none'

        # Bearish crossover: %K cruza de overbought para baixo
        if k_values.iloc[-2] >= overbought and k_values.iloc[-1] < overbought:
            return 'bearish'

        return 'none'

    def _calculate_crossover_strength(
        self,
        k_values: pd.Series,
        d_values: pd.Series
    ) -> float:
        """
        Calcula força do crossover (0.0 a 1.0)

        Returns:
            float: Força do crossover
        """
        if len(k_values) == 0 or len(d_values) == 0:
            return 0.0

        diff = abs(k_values.iloc[-1] - d_values.iloc[-1])
        max_diff = k_values.abs().max()

        if max_diff == 0:
            return 0.0

        return min(1.0, diff / max_diff)

    def _confirm_with_volume(
        self,
        data: pd.DataFrame,
        lookback: int = 5
    ) -> bool:
        """
        Confirma sinal com volume

        Args:
            data: DataFrame com OHLC
            lookback: Período para análise

        Returns:
            bool: True se confirmado
        """
        if 'volume' not in data.columns:
            return False

        try:
            current_volume = data['volume'].iloc[-1]
            avg_volume = data['volume'].iloc[-lookback:-1].mean()

            # Ajustado threshold para 1.05 (5% acima da média) para volume sintético
            return current_volume > avg_volume * 1.05

        except Exception as e:
            logger.error(f"Erro ao confirmar com volume: {e}", exc_info=True)
            return False

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
        k_values: pd.Series,
        d_values: pd.Series
    ) -> float:
        """
        Calcula força do sinal (0.0 a 1.0)

        Args:
            k_values: Série de valores %K
            d_values: Série de valores %D

        Returns:
            float: Força do sinal
        """
        if len(k_values) == 0 or len(d_values) == 0:
            return 0.0

        diff = abs(k_values.iloc[-1] - d_values.iloc[-1])
        max_diff = k_values.abs().max()

        if max_diff == 0:
            return 0.0

        return min(1.0, diff / max_diff)
