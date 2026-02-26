"""Multi-Period Bollinger Bands Indicator"""
from typing import List, Optional, Dict, Any
import pandas as pd
from loguru import logger

from .bollinger import BollingerBands


class MultiPeriodBollinger:
    """Bollinger Bands com múltiplos períodos para confluência de sinais"""

    def __init__(
        self,
        periods: List[int] = None,
        std_dev: float = 2.0,
        min_agreement: float = 0.75
    ):
        """
        Initialize Multi-Period Bollinger Bands

        Args:
            periods: Lista de períodos para Bollinger Bands
            std_dev: Standard deviation multiplier (default 2.0)
            min_agreement: Mínimo de concordância para gerar sinal (default 0.75 = 75%)
        """
        self.periods = periods or [10, 20, 50]
        self.std_dev = std_dev
        self.min_agreement = min_agreement

        # Criar instâncias de Bollinger Bands para cada período
        self.bb_indicators = {
            p: BollingerBands(period=p, std_dev=std_dev)
            for p in self.periods
        }

        logger.info(
            f"✓ Multi-Period Bollinger Bands inicializado com {len(self.periods)} períodos: "
            f"{self.periods} | Mínimo de concordância: {self.min_agreement:.0%}"
        )

    def calculate_all(self, data: pd.DataFrame) -> Dict[int, tuple]:
        """
        Calcula Bollinger Bands para todos os períodos

        Args:
            data: DataFrame com OHLC

        Returns:
            Dict com período como chave e (upper_band, middle_band, lower_band) como valor
        """
        results = {}

        for period, bb in self.bb_indicators.items():
            try:
                upper_band, middle_band, lower_band = bb.calculate(data)
                results[period] = (upper_band, middle_band, lower_band)
            except Exception as e:
                logger.error(f"Erro ao calcular Bollinger Bands período {period}: {e}", exc_info=True)

        return results

    def get_confluence_signal(
        self,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos

        Args:
            data: DataFrame com OHLC

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        try:
            # Calcular Bollinger Bands para todos os períodos
            bb_values = self.calculate_all(data)

            signals = []
            signal_details = []

            for period, (upper_band, middle_band, lower_band) in bb_values.items():
                if len(upper_band) == 0:
                    continue

                # Detectar sinais
                close = data['close'].iloc[-1]

                # Buy signal: price touches lower band
                if close <= lower_band.iloc[-1]:
                    signals.append('buy')
                    signal_details.append({
                        'period': period,
                        'signal': 'buy',
                        'close': close,
                        'lower_band': lower_band.iloc[-1]
                    })

                # Sell signal: price touches upper band
                elif close >= upper_band.iloc[-1]:
                    signals.append('sell')
                    signal_details.append({
                        'period': period,
                        'signal': 'sell',
                        'close': close,
                        'upper_band': upper_band.iloc[-1]
                    })

            if not signals:
                return None

            # Calcular confluência
            buy_count = signals.count('buy')
            sell_count = signals.count('sell')
            total = len(signals)

            buy_agreement = buy_count / total if total > 0 else 0
            sell_agreement = sell_count / total if total > 0 else 0

            # Verificar se há confluência mínima
            if buy_agreement >= self.min_agreement:
                confidence = buy_agreement
                logger.info(
                    f"✓ Confluência BUY: {buy_count}/{total} ({confidence:.0%}) | "
                    f"Períodos: {[d['period'] for d in signal_details if d['signal'] == 'buy']}"
                )
                return {
                    'signal': 'buy',
                    'confidence': confidence,
                    'buy_count': buy_count,
                    'sell_count': sell_count,
                    'total_periods': total,
                    'details': signal_details
                }
            elif sell_agreement >= self.min_agreement:
                confidence = sell_agreement
                logger.info(
                    f"✓ Confluência SELL: {sell_count}/{total} ({confidence:.0%}) | "
                    f"Períodos: {[d['period'] for d in signal_details if d['signal'] == 'sell']}"
                )
                return {
                    'signal': 'sell',
                    'confidence': confidence,
                    'buy_count': buy_count,
                    'sell_count': sell_count,
                    'total_periods': total,
                    'details': signal_details
                }
            else:
                logger.debug(
                    f"❌ Sem confluência suficiente: BUY {buy_count}/{total} ({buy_agreement:.0%}), "
                    f"SELL {sell_count}/{total} ({sell_agreement:.0%}) | Mínimo: {self.min_agreement:.0%}"
                )
                return None

        except Exception as e:
            logger.error(f"Erro ao calcular confluência de sinais: {e}", exc_info=True)
            return None

    def get_advanced_signal(
        self,
        data: pd.DataFrame,
        min_confidence: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal avançado com todas as confirmações

        Args:
            data: DataFrame com OHLC
            min_confidence: Confiança mínima (default 0.8)

        Returns:
            Dict com sinal avançado ou None
        """
        try:
            # Obter sinal de confluência
            signal = self.get_confluence_signal(data)

            if not signal:
                return None

            # Verificar confiança mínima
            if signal['confidence'] < min_confidence:
                logger.debug(
                    f"❌ Confiança {signal['confidence']:.0%} abaixo do mínimo {min_confidence:.0%}"
                )
                return None

            # Filtrar sinais baseado em condições de mercado
            main_period = 20  # Período principal
            if main_period in self.bb_indicators:
                filtered = self.bb_indicators[main_period].filter_signals(
                    data, signal['signal']
                )

                if not filtered:
                    logger.debug(f"❌ Sinal {signal['signal']} filtrado por condições de mercado")
                    return None

            # Confirmar tendência
            if main_period in self.bb_indicators:
                trend = self.bb_indicators[main_period].confirm_trend(data)

                if trend:
                    logger.info(f"✓ Tendência confirmada: {trend}")

                    # Se sinal é buy mas tendência é downtrend, ignorar
                    if signal['signal'] == 'buy' and trend == 'downtrend':
                        logger.debug("❌ Sinal BUY ignorado: tendência de baixa")
                        return None

                    # Se sinal é sell mas tendência é uptrend, ignorar
                    if signal['signal'] == 'sell' and trend == 'uptrend':
                        logger.debug("❌ Sinal SELL ignorado: tendência de alta")
                        return None

            result = signal.copy()
            result['trend'] = trend if main_period in self.bb_indicators else None

            logger.info(
                f"✓ Sinal {signal['signal'].upper()} confirmado | "
                f"Confiança: {signal['confidence']:.0%} | "
                f"Tendência: {trend or 'N/A'}"
            )

            return result

        except Exception as e:
            logger.error(f"Erro ao gerar sinal avançado: {e}", exc_info=True)
            return None
