"""Multi-Period MACD Indicator"""
from typing import List, Tuple, Optional, Dict, Any
import pandas as pd
from loguru import logger

from .macd import MACD


class MultiPeriodMACD:
    """MACD com múltiplos períodos para confluência de sinais"""

    def __init__(
        self,
        periods: List[Tuple[int, int, int]] = None,
        min_agreement: float = 0.75
    ):
        """
        Initialize Multi-Period MACD

        Args:
            periods: Lista de tuplas (fast, slow, signal) para cada período
            min_agreement: Mínimo de concordância para gerar sinal (default 0.75 = 75%)
        """
        self.periods = periods or [(12, 26, 9), (5, 13, 4), (21, 34, 9)]
        self.min_agreement = min_agreement

        # Criar instâncias de MACD para cada período
        self.macd_indicators = {
            tuple(p): MACD(*p) for p in self.periods
        }

        logger.info(
            f"✓ Multi-Period MACD inicializado com {len(self.periods)} períodos: "
            f"{self.periods} | Mínimo de concordância: {self.min_agreement:.0%}"
        )

    def calculate_all(self, data: pd.DataFrame) -> Dict[Tuple[int, int, int], Tuple[pd.Series, pd.Series, pd.Series]]:
        """
        Calcula MACD para todos os períodos

        Args:
            data: DataFrame com OHLC

        Returns:
            Dict com período como chave e (macd_line, signal_line, histogram) como valor
        """
        results = {}

        for period, macd_indicator in self.macd_indicators.items():
            try:
                macd_line, signal_line, histogram = macd_indicator.calculate(data)
                results[period] = (macd_line, signal_line, histogram)
            except Exception as e:
                logger.error(f"Erro ao calcular MACD período {period}: {e}", exc_info=True)

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
            # Calcular MACD para todos os períodos
            macd_values = self.calculate_all(data)

            signals = []
            signal_details = []

            for period, (macd_line, signal_line, histogram) in macd_values.items():
                if len(histogram) == 0:
                    continue

                # Detectar crossover básico
                if len(histogram) >= 2:
                    if histogram.iloc[-2] <= 0 and histogram.iloc[-1] > 0:
                        signals.append('buy')
                        signal_details.append({
                            'period': period,
                            'signal': 'buy',
                            'histogram': histogram.iloc[-1]
                        })
                    elif histogram.iloc[-2] >= 0 and histogram.iloc[-1] < 0:
                        signals.append('sell')
                        signal_details.append({
                            'period': period,
                            'signal': 'sell',
                            'histogram': histogram.iloc[-1]
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

    def get_confluence_with_divergence(
        self,
        data: pd.DataFrame,
        use_divergence: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos com divergência

        Args:
            data: DataFrame com OHLC
            use_divergence: Usar detecção de divergência (default True)

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        # Obter sinal de confluência
        confluence_signal = self.get_confluence_signal(data)

        if not confluence_signal:
            return None

        # Se não usar divergência, retornar sinal de confluência
        if not use_divergence:
            return confluence_signal

        # Verificar divergência no MACD principal (período 12, 26, 9)
        try:
            main_period = (12, 26, 9)
            if main_period in self.macd_indicators:
                macd_line, _, _ = self.macd_indicators[main_period].calculate(data)

                if len(macd_line) == 0:
                    return confluence_signal

                # Detectar divergência
                divergence = self.macd_indicators[main_period].detect_divergence(data, macd_line)

                # Se não há divergência, retornar sinal de confluência
                if divergence['divergence'] == 'none':
                    return confluence_signal

                # Se há divergência, aumentar confiança
                enhanced_confidence = min(1.0, confluence_signal['confidence'] + 0.1)

                logger.info(
                    f"✓ Divergência {divergence['divergence']} (força {divergence['strength']}/10) "
                    f"melhora confiança de {confluence_signal['confidence']:.0%} para {enhanced_confidence:.0%}"
                )

                result = confluence_signal.copy()
                result['confidence'] = enhanced_confidence
                result['divergence'] = divergence

                return result

        except Exception as e:
            logger.error(f"Erro ao verificar divergência: {e}", exc_info=True)
            return confluence_signal

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
            # Obter sinal de confluência com divergência
            signal = self.get_confluence_with_divergence(data)

            if not signal:
                return None

            # Verificar confiança mínima
            if signal['confidence'] < min_confidence:
                logger.debug(
                    f"❌ Confiança {signal['confidence']:.0%} abaixo do mínimo {min_confidence:.0%}"
                )
                return None

            # Validar com volume
            main_period = (12, 26, 9)
            if main_period in self.macd_indicators:
                macd_line, signal_line, histogram = self.macd_indicators[main_period].calculate(data)

                # Filtrar sinais baseado em condições de mercado
                if signal['signal'] in ['buy', 'sell']:
                    filtered = self.macd_indicators[main_period].filter_signals(
                        data, signal['signal']
                    )

                    if not filtered:
                        logger.debug(f"❌ Sinal {signal['signal']} filtrado por condições de mercado")
                        return None

                # Confirmar com volume
                volume_confirmed = self.macd_indicators[main_period]._confirm_with_volume(data)

                if not volume_confirmed:
                    logger.debug(f"❌ Sinal {signal['signal']} não confirmado por volume")
                    # Não filtrar, apenas avisar

            logger.info(
                f"✓ Sinal {signal['signal'].upper()} confirmado | "
                f"Confiança: {signal['confidence']:.0%} | "
                f"Divergência: {signal.get('divergence', {}).get('divergence', 'N/A')}"
            )

            return signal

        except Exception as e:
            logger.error(f"Erro ao gerar sinal avançado: {e}", exc_info=True)
            return None
