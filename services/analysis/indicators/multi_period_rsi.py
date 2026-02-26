"""Multi-Period RSI Indicator"""
import pandas as pd
from typing import Dict, List, Optional, Any
from loguru import logger

from .rsi import RSI


class MultiPeriodRSI:
    """RSI com múltiplos períodos para confluência de sinais"""

    def __init__(
        self,
        periods: List[int] = None,
        min_agreement: float = 0.75
    ):
        """
        Initialize Multi-Period RSI

        Args:
            periods: Lista de períodos para RSI (default [14, 21, 34, 55])
            min_agreement: Mínimo de concordância para gerar sinal (default 0.75 = 75%)
        """
        self.periods = periods or [14, 21, 34, 55]
        self.min_agreement = min_agreement

        # Criar instâncias de RSI para cada período
        self.rsi_indicators = {p: RSI(period=p) for p in self.periods}

    def calculate_all(self, data: pd.DataFrame) -> Dict[int, pd.Series]:
        """
        Calcula RSI para todos os períodos

        Args:
            data: DataFrame com OHLC

        Returns:
            Dict com período como chave e série RSI como valor
        """
        results = {}

        for period, rsi_indicator in self.rsi_indicators.items():
            try:
                rsi = rsi_indicator.calculate(data)
                results[period] = rsi
            except Exception as e:
                logger.error(f"Erro ao calcular RSI período {period}: {e}", exc_info=True)
                results[period] = pd.Series([0] * len(data))

        return results

    def get_confluence_signal(
        self,
        data: pd.DataFrame,
        oversold: float = 30.0,
        overbought: float = 70.0
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos

        Args:
            data: DataFrame com OHLC
            oversold: Nível oversold (default 30)
            overbought: Nível overbought (default 70)

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        try:
            # Calcular RSI para todos os períodos
            rsi_values = self.calculate_all(data)

            signals = []
            signal_details = []

            for period, rsi in rsi_values.items():
                if len(rsi) == 0:
                    continue

                current_rsi = rsi.iloc[-1]
                signal = self.rsi_indicators[period].get_signal(
                    current_rsi,
                    oversold,
                    overbought
                )

                if signal:
                    signals.append(signal)
                    signal_details.append({
                        'period': period,
                        'rsi': current_rsi,
                        'signal': signal
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
        oversold: float = 30.0,
        overbought: float = 70.0,
        use_divergence: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos com divergência

        Args:
            data: DataFrame com OHLC
            oversold: Nível oversold (default 30)
            overbought: Nível overbought (default 70)
            use_divergence: Usar detecção de divergência (default True)

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        # Obter sinal de confluência
        confluence_signal = self.get_confluence_signal(data, oversold, overbought)

        if not confluence_signal:
            return None

        # Se não usar divergência, retornar sinal de confluência
        if not use_divergence:
            return confluence_signal

        # Verificar divergência no RSI principal (período 14)
        try:
            rsi_14 = self.rsi_indicators[14].calculate(data)

            if len(rsi_14) == 0:
                return confluence_signal

            # Detectar divergência avançada
            divergence = self.rsi_indicators[14].detect_divergence_advanced(data, rsi_14)

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
        oversold: float = 30.0,
        overbought: float = 70.0,
        min_confidence: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal avançado com todas as confirmações

        Args:
            data: DataFrame com OHLC
            oversold: Nível oversold (default 30)
            overbought: Nível overbought (default 70)
            min_confidence: Confiança mínima (default 0.8)

        Returns:
            Dict com sinal avançado ou None
        """
        try:
            # Obter sinal de confluência com divergência
            signal = self.get_confluence_with_divergence(data, oversold, overbought)

            if not signal:
                return None

            # Verificar confiança mínima
            if signal['confidence'] < min_confidence:
                logger.debug(
                    f"❌ Confiança {signal['confidence']:.0%} abaixo do mínimo {min_confidence:.0%}"
                )
                return None

            # Confirmar tendência
            trend = self.rsi_indicators[14].confirm_trend(data)

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

            # Validar timeframe
            # Nota: timeframe_seconds não está disponível aqui, seria passado como parâmetro

            result = signal.copy()
            result['trend'] = trend

            logger.info(
                f"✓ Sinal {signal['signal'].upper()} confirmado | "
                f"Confiança: {signal['confidence']:.0%} | "
                f"Tendência: {trend or 'N/A'}"
            )

            return result

        except Exception as e:
            logger.error(f"Erro ao gerar sinal avançado: {e}", exc_info=True)
            return None
