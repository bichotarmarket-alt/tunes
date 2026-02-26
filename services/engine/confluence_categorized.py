"""Confluence Calculator Categorizado - Agrupamento estatístico de indicadores"""
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class SignalDirection(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0


class IndicatorCategory(Enum):
    MOMENTUM = "momentum"
    TREND = "trend"
    VOLATILITY = "volatility"
    STRUCTURE = "structure"
    VOLUME = "volume"


@dataclass
class IndicatorSignal:
    name: str
    category: IndicatorCategory
    direction: SignalDirection
    confidence: float  # 0.0 a 1.0
    value: Optional[float] = None


@dataclass
class ConfluenceResult:
    final_score: float
    direction: SignalDirection
    raw_score: float
    category_scores: Dict[IndicatorCategory, float]
    breakdown: Dict[str, any]
    should_trade: bool
    circuit_breaker_blocked: bool = False  # Indica se CB bloqueou
    atr_value: Optional[float] = None  # Valor do ATR usado


class ConfluenceCalculatorCategorized:
    """
    Motor de confluência com agrupamento estatístico por categoria.
    
    Resolve o problema de indicadores correlacionados inflando o score.
    
    Estratégia:
    1. Agrupar indicadores por categoria (momentum, trend, volatility, structure)
    2. Calcular contribuição máxima por categoria (capping)
    3. Aplicar penalidades por correlação interna
    4. Calcular score global ponderado
    
    Categories:
        MOMENTUM: RSI, Stochastic, Williams %R, CCI, Momentum, ROC
        TREND: MACD, SMA, EMA, ADX, Ichimoku, Parabolic SAR
        VOLATILITY: Bollinger, ATR, Keltner, Donchian
        STRUCTURE: Zonas, Pivot Points, Fibonacci
        VOLUME: MFI, Synthetic Volume
    """
    
    # Mapeamento de indicadores para categorias
    INDICATOR_CATEGORIES = {
        # Momentum
        'rsi': IndicatorCategory.MOMENTUM,
        'stochastic': IndicatorCategory.MOMENTUM,
        'stochastic_k': IndicatorCategory.MOMENTUM,
        'stochastic_d': IndicatorCategory.MOMENTUM,
        'williams_r': IndicatorCategory.MOMENTUM,
        'cci': IndicatorCategory.MOMENTUM,
        'momentum': IndicatorCategory.MOMENTUM,
        'roc': IndicatorCategory.MOMENTUM,
        
        # Trend
        'macd': IndicatorCategory.TREND,
        'macd_signal': IndicatorCategory.TREND,
        'macd_histogram': IndicatorCategory.TREND,
        'sma': IndicatorCategory.TREND,
        'ema': IndicatorCategory.TREND,
        'adx': IndicatorCategory.TREND,
        'ichimoku': IndicatorCategory.TREND,
        'parabolic_sar': IndicatorCategory.TREND,
        'supertrend': IndicatorCategory.TREND,
        
        # Volatility
        'bollinger_bands': IndicatorCategory.VOLATILITY,
        'bollinger_upper': IndicatorCategory.VOLATILITY,
        'bollinger_lower': IndicatorCategory.VOLATILITY,
        'atr': IndicatorCategory.VOLATILITY,
        'keltner': IndicatorCategory.VOLATILITY,
        'donchian': IndicatorCategory.VOLATILITY,
        
        # Structure
        'zonas': IndicatorCategory.STRUCTURE,
        'pivot_points': IndicatorCategory.STRUCTURE,
        'fibonacci': IndicatorCategory.STRUCTURE,
        'heiken_ashi': IndicatorCategory.STRUCTURE,
        
        # Volume
        'mfi': IndicatorCategory.VOLUME,
        'synthetic_volume': IndicatorCategory.VOLUME,
    }
    
    # Cap máximo por categoria (evita dominação)
    DEFAULT_CATEGORY_CAPS = {
        IndicatorCategory.MOMENTUM: 0.40,
        IndicatorCategory.TREND: 0.40,
        IndicatorCategory.VOLATILITY: 0.20,
        IndicatorCategory.STRUCTURE: 0.15,
        IndicatorCategory.VOLUME: 0.15,
    }
    
    # Pesos base por categoria
    DEFAULT_CATEGORY_WEIGHTS = {
        IndicatorCategory.MOMENTUM: 1.0,
        IndicatorCategory.TREND: 1.2,  # Trend é mais confiável
        IndicatorCategory.VOLATILITY: 0.8,
        IndicatorCategory.STRUCTURE: 0.9,
        IndicatorCategory.VOLUME: 0.7,
    }
    
    def __init__(
        self,
        min_confluence: float = 0.5,
        category_caps: Optional[Dict[IndicatorCategory, float]] = None,
        category_weights: Optional[Dict[IndicatorCategory, float]] = None,
        correlation_penalty: float = 0.15,
        require_trend_confirmation: bool = False
    ):
        self.min_confluence = min_confluence
        self.category_caps = category_caps or self.DEFAULT_CATEGORY_CAPS.copy()
        self.category_weights = category_weights or self.DEFAULT_CATEGORY_WEIGHTS.copy()
        self.correlation_penalty = correlation_penalty
        self.require_trend_confirmation = require_trend_confirmation
    
    def calculate_confluence(self, signals: List[IndicatorSignal]) -> ConfluenceResult:
        """
        Calcular confluência categorizada.
        
        Args:
            signals: Lista de sinais de indicadores
            
        Returns:
            ConfluenceResult com score final e decisão
        """
        if not signals:
            return ConfluenceResult(
                final_score=0.0,
                direction=SignalDirection.HOLD,
                raw_score=0.0,
                category_scores={},
                breakdown={},
                should_trade=False
            )
        
        # Agrupar por categoria
        category_signals: Dict[IndicatorCategory, List[IndicatorSignal]] = {
            cat: [] for cat in IndicatorCategory
        }
        
        for signal in signals:
            cat = self.INDICATOR_CATEGORIES.get(signal.name, IndicatorCategory.MOMENTUM)
            category_signals[cat].append(signal)
        
        # Calcular score por categoria
        category_results = {}
        category_directions = {}
        
        for category, cat_signals in category_signals.items():
            if not cat_signals:
                continue
                
            score, direction, details = self._calculate_category_score(cat_signals)
            
            # Aplicar cap máximo
            capped_score = min(score, self.category_caps.get(category, 1.0))
            
            # Aplicar peso da categoria
            weighted_score = capped_score * self.category_weights.get(category, 1.0)
            
            category_results[category] = {
                'raw_score': score,
                'capped_score': capped_score,
                'weighted_score': weighted_score,
                'direction': direction,
                'count': len(cat_signals),
                'details': details
            }
            category_directions[category] = direction
        
        # Verificar concordância entre categorias
        buy_categories = sum(1 for d in category_directions.values() if d == SignalDirection.BUY)
        sell_categories = sum(1 for d in category_directions.values() if d == SignalDirection.SELL)
        
        # Score global ponderado
        total_weighted_score = sum(
            r['weighted_score'] for r in category_results.values()
        )
        max_possible_score = sum(
            self.category_caps.get(cat, 1.0) * self.category_weights.get(cat, 1.0)
            for cat in category_results.keys()
        )
        
        if max_possible_score > 0:
            normalized_score = total_weighted_score / max_possible_score
        else:
            normalized_score = 0.0
        
        # Aplicar bônus por concordância multi-categoria
        consensus_bonus = 0.0
        active_categories = len(category_results)
        
        if active_categories >= 3:
            # 3+ categorias concordando = bônus de 10%
            if buy_categories >= 3 or sell_categories >= 3:
                consensus_bonus = 0.10
        
        # Penalidade por conflito
        conflict_penalty = 0.0
        if buy_categories > 0 and sell_categories > 0:
            # Ambos lados ativos = penalidade
            conflict_penalty = self.correlation_penalty * min(buy_categories, sell_categories)
        
        final_score = normalized_score + consensus_bonus - conflict_penalty
        final_score = max(0.0, min(1.0, final_score))  # Clamp 0-1
        
        # Determinar direção final
        final_direction = SignalDirection.HOLD
        if buy_categories > sell_categories:
            final_direction = SignalDirection.BUY
        elif sell_categories > buy_categories:
            final_direction = SignalDirection.SELL
        
        # Verificar trend confirmation se necessário
        should_trade = final_score >= self.min_confluence
        
        if self.require_trend_confirmation:
            trend_direction = category_directions.get(IndicatorCategory.TREND, SignalDirection.HOLD)
            if trend_direction != SignalDirection.HOLD and trend_direction != final_direction:
                should_trade = False
                final_direction = SignalDirection.HOLD
        
        return ConfluenceResult(
            final_score=final_score,
            direction=final_direction,
            raw_score=normalized_score,
            category_scores={
                cat: r['weighted_score'] 
                for cat, r in category_results.items()
            },
            breakdown={
                'category_results': category_results,
                'consensus_bonus': consensus_bonus,
                'conflict_penalty': conflict_penalty,
                'buy_categories': buy_categories,
                'sell_categories': sell_categories,
                'active_categories': active_categories
            },
            should_trade=should_trade
        )
    
    def _calculate_category_score(
        self, 
        signals: List[IndicatorSignal]
    ) -> Tuple[float, SignalDirection, Dict]:
        """
        Calcular score para uma categoria de indicadores.
        
        Returns:
            (score, direction, details)
        """
        if not signals:
            return 0.0, SignalDirection.HOLD, {}
        
        # Contar sinais buy/sell
        buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]
        
        total = len(signals)
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        
        # Calcular confiança média ponderada por lado
        avg_buy_conf = sum(s.confidence for s in buy_signals) / buy_count if buy_signals else 0
        avg_sell_conf = sum(s.confidence for s in sell_signals) / sell_count if sell_signals else 0
        
        # Score baseado em concordância
        if buy_count > sell_count:
            # Consenso de compra
            consensus_ratio = buy_count / total
            score = consensus_ratio * avg_buy_conf
            direction = SignalDirection.BUY
        elif sell_count > buy_count:
            # Consenso de venda
            consensus_ratio = sell_count / total
            score = consensus_ratio * avg_sell_conf
            direction = SignalDirection.SELL
        else:
            # Empate ou nenhum sinal direcional
            score = 0.0
            direction = SignalDirection.HOLD
        
        # Penalidade por sinais isolados na categoria
        if total == 1:
            score *= 0.7  # Penalidade 30% por sinal isolado
        
        details = {
            'total_signals': total,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'avg_buy_confidence': avg_buy_conf,
            'avg_sell_confidence': avg_sell_conf,
            'consensus_ratio': consensus_ratio if direction != SignalDirection.HOLD else 0
        }
        
        return score, direction, details
    
    def calculate_confluence_with_circuit_breaker(
        self,
        signals: List[IndicatorSignal],
        circuit_breaker_active: bool = True,
        atr_value: Optional[float] = None
    ) -> ConfluenceResult:
        """
        Calcular confluência com integração ao Circuit Breaker.
        
        Args:
            signals: Lista de sinais de indicadores
            circuit_breaker_active: Se False, ignora CB (modo override)
            atr_value: Valor do ATR para validação do CB
            
        Returns:
            ConfluenceResult com informação de bloqueio do CB
        """
        # Verificar circuit breaker
        if not circuit_breaker_active:
            # Circuit breaker desativado - calcular normalmente
            result = self.calculate_confluence(signals)
            return ConfluenceResult(
                final_score=result.final_score,
                direction=result.direction,
                raw_score=result.raw_score,
                category_scores=result.category_scores,
                breakdown=result.breakdown,
                should_trade=result.should_trade,
                circuit_breaker_blocked=False,
                atr_value=atr_value
            )
        
        # Circuit breaker ativo - verificar volatilidade
        if atr_value is not None and atr_value < 0.0001:  # Threshold mínimo
            # Mercado sem volatilidade - bloquear
            return ConfluenceResult(
                final_score=0.0,
                direction=SignalDirection.HOLD,
                raw_score=0.0,
                category_scores={},
                breakdown={'circuit_breaker': 'ATR muito baixo', 'atr': atr_value},
                should_trade=False,
                circuit_breaker_blocked=True,
                atr_value=atr_value
            )
        
        # Calcular confluência normal
        result = self.calculate_confluence(signals)
        
        return ConfluenceResult(
            final_score=result.final_score,
            direction=result.direction,
            raw_score=result.raw_score,
            category_scores=result.category_scores,
            breakdown=result.breakdown,
            should_trade=result.should_trade,
            circuit_breaker_blocked=False,
            atr_value=atr_value
        )
    
    def should_generate_signal(
        self, 
        signals: List[IndicatorSignal],
        min_confluence: Optional[float] = None
    ) -> bool:
        """Verificar se deve gerar sinal baseado em confluência."""
        threshold = min_confluence or self.min_confluence
        result = self.calculate_confluence(signals)
        return result.should_trade and result.final_score >= threshold
