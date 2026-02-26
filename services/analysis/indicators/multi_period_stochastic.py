"""Multi-Period Stochastic Indicator"""
from typing import List, Tuple, Optional, Dict, Any
import pandas as pd
from loguru import logger

from .stochastic import Stochastic


class MultiPeriodStochastic:
    """Stochastic com múltiplos períodos para confluência de sinais"""

    def __init__(
        self,
        periods: List[Tuple[int, int]] = None,
        min_agreement: float = 0.75
    ):
        """
        Initialize Multi-Period Stochastic

        Args:
            periods: Lista de tuplas (k_period, d_period) para cada período
            min_agreement: Mínimo de concordância para gerar sinal (default 0.75 = 75%)
        """
        self.periods = periods or [(14, 3), (5, 3), (21, 5)]
        self.min_agreement = min_agreement

        # Criar instâncias de Stochastic para cada período
        self.stochastic_indicators = {
            tuple(p): Stochastic(*p) for p in self.periods
        }

        logger.info(
            f"✓ Multi-Period Stochastic inicializado com {len(self.periods)} períodos: "
            f"{self.periods} | Mínimo de concordância: {self.min_agreement:.0%}"
        )

    def calculate_all(self, data: pd.DataFrame) -> Dict[Tuple[int, int], pd.DataFrame]:
        """
        Calcula Stochastic para todos os períodos

        Args:
            data: DataFrame com OHLC

        Returns:
            Dict com período como chave e DataFrame com %K e %D como valor
        """
        results = {}

        for period, stoch in self.stochastic_indicators.items():
            try:
                stochastic = stoch.calculate(data)
                results[period] = stochastic
            except Exception as e:
                logger.error(f"Erro ao calcular Stochastic período {period}: {e}", exc_info=True)

        return results

    def get_confluence_signal(
        self,
        data: pd.DataFrame,
        overbought: float = 80.0,
        oversold: float = 20.0
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos

        Args:
            data: DataFrame com OHLC
            overbought: Nível overbought (default 80)
            oversold: Nível oversold (default 20)

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        try:
            # Calcular Stochastic para todos os períodos
            stoch_values = self.calculate_all(data)

            signals = []
            signal_details = []

            for period, stochastic in stoch_values.items():
                if stochastic.empty:
                    continue

                k_val = stochastic.iloc[-1]['%K']

                # Buy signal: %K < oversold
                if k_val < oversold:
                    signals.append('buy')
                    signal_details.append({
                        'period': period,
                        'signal': 'buy',
                        '%K': k_val
                    })

                # Sell signal: %K > overbought
                elif k_val > overbought:
                    signals.append('sell')
                    signal_details.append({
                        'period': period,
                        'signal': 'sell',
                        '%K': k_val
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
        overbought: float = 80.0,
        oversold: float = 20.0,
        use_divergence: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal baseado em confluência de múltiplos períodos com divergência

        Args:
            data: DataFrame com OHLC
            overbought: Nível overbought
            oversold: Nível oversold
            use_divergence: Usar detecção de divergência (default True)

        Returns:
            Dict com sinal, confiança e detalhes ou None
        """
        # Obter sinal de confluência
        confluence_signal = self.get_confluence_signal(data, overbought, oversold)

        if not confluence_signal:
            return None

        # Se não usar divergência, retornar sinal de confluência
        if not use_divergence:
            return confluence_signal

        # Verificar divergência no Stochastic principal (período 14, 3)
        try:
            main_period = (14, 3)
            if main_period in self.stochastic_indicators:
                divergence = self.stochastic_indicators[main_period].get_divergence(data)

                # Se não há divergência, retornar sinal de confluência
                if divergence['divergence'] == 'none':
                    return confluence_signal

                # Se há divergência, aumentar confiança
                enhanced_confidence = min(1.0, confluence_signal['confidence'] + 0.1)

                logger.info(
                    f"✓ Divergência {divergence['divergence']} detectada | "
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
        overbought: float = 80.0,
        oversold: float = 20.0,
        min_confidence: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Gera sinal avançado com todas as confirmações

        Args:
            data: DataFrame com OHLC
            overbought: Nível overbought
            oversold: Nível oversold
            min_confidence: Confiança mínima (default 0.8)

        Returns:
            Dict com sinal avançado ou None
        """
        try:
            # Obter sinal de confluência com divergência
            signal = self.get_confluence_with_divergence(data, overbought, oversold)

            if not signal:
                return None

            # Verificar confiança mínima
            if signal['confidence'] < min_confidence:
                logger.debug(
                    f"❌ Confiança {signal['confidence']:.0%} abaixo do mínimo {min_confidence:.0%}"
                )
                return None

            # Filtrar sinais baseado em condições de mercado
            main_period = (14, 3)
            if main_period in self.stochastic_indicators:
                filtered = self.stochastic_indicators[main_period].filter_signals(
                    data, signal['signal']
                )

                if not filtered:
                    logger.debug(f"❌ Sinal {signal['signal']} filtrado por condições de mercado")
                    return None

            logger.info(
                f"✓ Sinal {signal['signal'].upper()} confirmado | "
                f"Confiança: {signal['confidence']:.0%} | "
                f"Divergência: {signal.get('divergence', {}).get('divergence', 'N/A')}"
            )

            return signal

        except Exception as e:
            logger.error(f"Erro ao gerar sinal avançado: {e}", exc_info=True)
            return None
