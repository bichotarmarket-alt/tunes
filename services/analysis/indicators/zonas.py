"""
Zonas (Support/Resistance) Indicator
Identifica zonas de suporte e resistência com alta precisão
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from collections import defaultdict

from .base import TechnicalIndicator
from .error_handler import handle_indicator_errors, validate_dataframe
from .cache import cached_indicator


class Zonas(TechnicalIndicator):
    """Zonas de Suporte e Resistência - Indicador Principal"""

    def __init__(
        self,
        swing_period: int = 3,
        zone_strength: int = 2,
        zone_tolerance: float = 0.005,
        min_zone_width: float = 0.003,
        atr_multiplier: float = 0.5
    ):
        """
        Initialize Zonas indicator

        Args:
            swing_period: Período para identificar swing highs/lows (default: 5)
            zone_strength: Mínimo de toques para validar zona (default: 2)
            zone_tolerance: Tolerância para agrupar zonas (default: 0.5%)
            min_zone_width: Largura mínima da zona em % do preço (default: 0.3%)
            atr_multiplier: Multiplicador do ATR para largura da zona (default: 0.5)
        """
        super().__init__("Zonas")
        self.swing_period = swing_period
        self.zone_strength = zone_strength
        self.zone_tolerance = zone_tolerance
        self.min_zone_width = min_zone_width
        self.atr_multiplier = atr_multiplier

    def validate_parameters(self, **kwargs) -> bool:
        """Validate Zonas parameters"""
        swing_period = kwargs.get('swing_period', self.swing_period)
        zone_strength = kwargs.get('zone_strength', self.zone_strength)
        return (isinstance(swing_period, int) and swing_period > 0 and
                isinstance(zone_strength, int) and zone_strength > 0)

    @cached_indicator("Zonas")
    @handle_indicator_errors("Zonas", fallback_value=None)
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Zonas de Suporte e Resistência com múltiplas metodologias

        Args:
            data: DataFrame com OHLC data

        Returns:
            pd.DataFrame: DataFrame com zonas identificadas
        """
        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("DataFrame must have 'high', 'low', 'close' columns")

        # Adaptar swing_period baseado no número de candles disponíveis
        adaptive_swing_period = min(self.swing_period, max(2, len(data) // 4))
        
        if len(data) < adaptive_swing_period * 2:
            logger.warning(f"Not enough data points for Zonas calculation (need {adaptive_swing_period * 2}, got {len(data)})")
            return pd.DataFrame()

        # Calcular ATR para determinar largura das zonas
        atr = self._calculate_atr(data)

        # Identificar swing highs e lows com período adaptativo
        swing_highs, swing_lows = self._identify_swings_adaptive(data, adaptive_swing_period)

        # Criar zonas de suporte e resistência com margem
        resistance_zones = self._create_zones_with_margin(swing_highs, 'resistance', data, atr)
        support_zones = self._create_zones_with_margin(swing_lows, 'support', data, atr)

        # Calcular força das zonas
        resistance_zones = self._calculate_zone_strength(resistance_zones, data, 'resistance')
        support_zones = self._calculate_zone_strength(support_zones, data, 'support')

        # Detectar toques duplos
        double_tops = self._detect_double_tops(swing_highs, data)
        double_bottoms = self._detect_double_bottoms(swing_lows, data)

        # Detectar reversões
        reversals = self._detect_reversals(data, swing_highs, swing_lows)

        # Detectar Supply/Demand Zones
        demand_zones = self._detect_demand_zones(data, atr)
        supply_zones = self._detect_supply_zones(data, atr)

        # Detectar Fair Value Gaps (FVG)
        fvg_zones = self._detect_fair_value_gaps(data, atr)

        # Detectar Order Blocks
        order_blocks = self._detect_order_blocks(data, atr)

        # Detectar Pivot Points
        pivot_points = self._calculate_pivot_points(data)

        # Detectar Fibonacci Levels
        fib_levels = self._calculate_fibonacci_levels(data)

        # Detectar Psychological Levels
        psych_levels = self._detect_psychological_levels(data)

        # Detectar Liquidity Zones
        liquidity_zones = self._detect_liquidity_zones(data, swing_highs, swing_lows, atr)

        # Criar DataFrame de resultado
        result = pd.DataFrame(index=data.index)
        result['swing_high'] = swing_highs
        result['swing_low'] = swing_lows

        # Adicionar zonas mais próximas com margem
        if resistance_zones:
            result['nearest_resistance'] = self._get_nearest_zone(resistance_zones, data['close'], 'resistance')
            result['resistance_strength'] = self._get_zone_strength(resistance_zones, data['close'], 'resistance')
            result['resistance_high'] = self._get_zone_boundary(resistance_zones, data['close'], 'resistance', 'high')
            result['resistance_low'] = self._get_zone_boundary(resistance_zones, data['close'], 'resistance', 'low')
        else:
            result['nearest_resistance'] = np.nan
            result['resistance_strength'] = 0
            result['resistance_high'] = np.nan
            result['resistance_low'] = np.nan

        if support_zones:
            result['nearest_support'] = self._get_nearest_zone(support_zones, data['close'], 'support')
            result['support_strength'] = self._get_zone_strength(support_zones, data['close'], 'support')
            result['support_high'] = self._get_zone_boundary(support_zones, data['close'], 'support', 'high')
            result['support_low'] = self._get_zone_boundary(support_zones, data['close'], 'support', 'low')
        else:
            result['nearest_support'] = np.nan
            result['support_strength'] = 0
            result['support_high'] = np.nan
            result['support_low'] = np.nan

        # Adicionar Supply/Demand Zones
        if demand_zones:
            result['nearest_demand'] = self._get_nearest_zone(demand_zones, data['close'], 'demand')
            result['demand_strength'] = self._get_zone_strength(demand_zones, data['close'], 'demand')
        else:
            result['nearest_demand'] = np.nan
            result['demand_strength'] = 0

        if supply_zones:
            result['nearest_supply'] = self._get_nearest_zone(supply_zones, data['close'], 'supply')
            result['supply_strength'] = self._get_zone_strength(supply_zones, data['close'], 'supply')
        else:
            result['nearest_supply'] = np.nan
            result['supply_strength'] = 0

        # Adicionar Fair Value Gaps
        if fvg_zones:
            result['nearest_fvg'] = self._get_nearest_zone(fvg_zones, data['close'], 'fvg')
            result['fvg_type'] = self._get_fvg_type(fvg_zones, data['close'])
        else:
            result['nearest_fvg'] = np.nan
            result['fvg_type'] = 'none'

        # Adicionar Order Blocks
        if order_blocks:
            result['nearest_order_block'] = self._get_nearest_zone(order_blocks, data['close'], 'order_block')
            result['order_block_type'] = self._get_order_block_type(order_blocks, data['close'])
        else:
            result['nearest_order_block'] = np.nan
            result['order_block_type'] = 'none'

        # Adicionar Pivot Points
        if pivot_points:
            result['nearest_pivot'] = self._get_nearest_pivot(pivot_points, data['close'])
            result['pivot_type'] = self._get_pivot_type(pivot_points, data['close'])
        else:
            result['nearest_pivot'] = np.nan
            result['pivot_type'] = 'none'

        # Adicionar Fibonacci Levels
        if fib_levels:
            result['nearest_fib'] = self._get_nearest_fib(fib_levels, data['close'])
            result['fib_level'] = self._get_fib_level_name(fib_levels, data['close'])
        else:
            result['nearest_fib'] = np.nan
            result['fib_level'] = 'none'

        # Adicionar Psychological Levels
        if psych_levels:
            result['nearest_psych'] = self._get_nearest_psych(psych_levels, data['close'])
        else:
            result['nearest_psych'] = np.nan

        # Adicionar Liquidity Zones
        if liquidity_zones:
            result['nearest_liquidity'] = self._get_nearest_zone(liquidity_zones, data['close'], 'liquidity')
            result['liquidity_type'] = self._get_liquidity_type(liquidity_zones, data['close'])
        else:
            result['nearest_liquidity'] = np.nan
            result['liquidity_type'] = 'none'

        # Adicionar padrões
        result['double_top'] = False
        result['double_bottom'] = False
        result['reversal_signal'] = 'hold'

        for idx, row in reversals.iterrows():
            if idx in result.index:
                result.loc[idx, 'reversal_signal'] = row['signal']

        return result

    def _identify_swings(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """
        Identificar swing highs e swing lows

        Args:
            data: DataFrame com OHLC data

        Returns:
            Tuple: (swing_highs, swing_lows)
        """
        high = data['high']
        low = data['low']

        swing_highs = pd.Series(np.nan, index=data.index)
        swing_lows = pd.Series(np.nan, index=data.index)

        for i in range(self.swing_period, len(data) - self.swing_period):
            # Verificar se é swing high
            is_swing_high = True
            for j in range(i - self.swing_period, i + self.swing_period + 1):
                if j != i and high.iloc[j] >= high.iloc[i]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.iloc[i] = high.iloc[i]

            # Verificar se é swing low
            is_swing_low = True
            for j in range(i - self.swing_period, i + self.swing_period + 1):
                if j != i and low.iloc[j] <= low.iloc[i]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.iloc[i] = low.iloc[i]

        return swing_highs, swing_lows

    def _identify_swings_adaptive(self, data: pd.DataFrame, period: int) -> Tuple[pd.Series, pd.Series]:
        """
        Identificar swing highs e swing lows com período adaptativo
        Funciona melhor para timeframes curtos (3s, 5s, 30s)

        Args:
            data: DataFrame com OHLC data
            period: Período adaptativo para identificação de swings

        Returns:
            Tuple: (swing_highs, swing_lows)
        """
        high = data['high']
        low = data['low']

        swing_highs = pd.Series(np.nan, index=data.index)
        swing_lows = pd.Series(np.nan, index=data.index)

        # Para timeframes muito curtos, usar método simplificado
        if len(data) < period * 3:
            # Identificar highs e lows absolutos
            max_idx = high.idxmax()
            min_idx = low.idxmin()
            swing_highs.loc[max_idx] = high.loc[max_idx]
            swing_lows.loc[min_idx] = low.loc[min_idx]
        else:
            # Método normal com período adaptativo
            for i in range(period, len(data) - period):
                # Verificar se é swing high
                is_swing_high = True
                for j in range(i - period, i + period + 1):
                    if j != i and high.iloc[j] >= high.iloc[i]:
                        is_swing_high = False
                        break
                if is_swing_high:
                    swing_highs.iloc[i] = high.iloc[i]

                # Verificar se é swing low
                is_swing_low = True
                for j in range(i - period, i + period + 1):
                    if j != i and low.iloc[j] <= low.iloc[i]:
                        is_swing_low = False
                        break
                if is_swing_low:
                    swing_lows.iloc[i] = low.iloc[i]

        return swing_highs, swing_lows

    def _calculate_atr(self, data: pd.DataFrame) -> float:
        """
        Calcular ATR médio para determinar largura das zonas

        Args:
            data: DataFrame com OHLC data

        Returns:
            float: Valor médio do ATR
        """
        if len(data) < 14:
            return data['close'].iloc[-1] * 0.01  # Fallback: 1% do preço

        high = data['high']
        low = data['low']
        close = data['close']

        # Calcular True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        true_range.iloc[0] = high.iloc[0] - low.iloc[0]

        # Calcular ATR (Wilder)
        atr = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

        # Retornar ATR médio dos últimos 20 períodos (com fallback)
        recent_atr = atr.iloc[-20:].dropna()
        if recent_atr.empty:
            return data['close'].iloc[-1] * 0.01
        return recent_atr.mean()

    def _create_zones_with_margin(
        self,
        swings: pd.Series,
        zone_type: str,
        data: pd.DataFrame,
        atr: float
    ) -> List[Dict[str, Any]]:
        """
        Criar zonas com margem baseada em swings e ATR

        Args:
            swings: Series com swing highs ou lows
            zone_type: 'support' ou 'resistance'
            data: DataFrame com OHLC data
            atr: Valor médio do ATR

        Returns:
            List: Lista de zonas com margem
        """
        valid_swings = swings.dropna()
        zones = []

        if len(valid_swings) < self.zone_strength:
            return zones

        # Agrupar swings em zonas
        grouped = self._group_swings_into_zones(valid_swings, zone_type)

        for level, (swings_list, timestamps_list) in grouped.items():
            if len(swings_list) >= self.zone_strength:
                # Calcular nível médio da zona
                zone_level = np.mean(swings_list)

                # Calcular margem baseada no ATR
                zone_margin = atr * self.atr_multiplier if np.isfinite(atr) else 0.0

                # Calcular margem mínima baseada no preço (min_zone_width)
                min_margin = zone_level * self.min_zone_width

                # Usar a maior das duas margens
                final_margin = max(zone_margin, min_margin)

                # Criar zona com margem
                zones.append({
                    'level': zone_level,
                    'high': zone_level + final_margin,
                    'low': zone_level - final_margin,
                    'width': final_margin * 2,
                    'margin': final_margin,
                    'touches': len(swings_list),
                    'type': zone_type,
                    'timestamps': timestamps_list,
                    'swings': swings_list
                })

        return zones

    def _group_swings_into_zones(
        self,
        swings: pd.Series,
        zone_type: str
    ) -> Dict[float, Tuple[List[float], List[Any]]]:
        """
        Agrupar swings em zonas baseadas na tolerância

        Args:
            swings: Series com swings
            zone_type: 'support' ou 'resistance'

        Returns:
            Dict: Dicionário agrupando swings por nível (valor, [valores], [timestamps])
        """
        grouped = defaultdict(lambda: ([], []))  # (valores, timestamps)

        for idx, swing in swings.items():
            added = False

            # Tentar agrupar com zonas existentes
            for level in list(grouped.keys()):
                tolerance = level * self.zone_tolerance
                if abs(swing - level) <= tolerance:
                    grouped[level][0].append(swing)
                    grouped[level][1].append(idx)
                    added = True
                    break

            # Se não agrupou, criar nova zona
            if not added:
                grouped[swing][0].append(swing)
                grouped[swing][1].append(idx)

        return grouped

    def _calculate_zone_strength(
        self,
        zones: List[Dict[str, Any]],
        data: pd.DataFrame,
        zone_type: str
    ) -> List[Dict[str, Any]]:
        """
        Calcular força das zonas

        Args:
            zones: Lista de zonas
            data: DataFrame com OHLC data
            zone_type: 'support' ou 'resistance'

        Returns:
            List: Lista de zonas com força calculada
        """
        for zone in zones:
            # Fatores de força
            touches_factor = min(zone['touches'] / 5.0, 1.0)  # Max 1.0 para 5+ toques

            # Tempo desde o último toque
            last_touch = max(zone['timestamps'])
            # Converter para timestamp se necessário
            if hasattr(last_touch, 'total_seconds'):
                time_diff = (data.index[-1] - last_touch).total_seconds()
            else:
                # Converter ambos para timestamp em segundos
                if hasattr(data.index[-1], 'timestamp'):
                    current_ts = data.index[-1].timestamp()
                elif isinstance(data.index[-1], (int, float)):
                    current_ts = data.index[-1] / 1000 if data.index[-1] > 10000000000 else data.index[-1]
                else:
                    current_ts = float(data.index[-1])
                
                if hasattr(last_touch, 'timestamp'):
                    last_ts = last_touch.timestamp()
                elif isinstance(last_touch, (int, float)):
                    last_ts = last_touch / 1000 if last_touch > 10000000000 else last_touch
                else:
                    last_ts = float(last_touch)
                
                time_diff = current_ts - last_ts
            
            time_factor = 1.0 - min(time_diff / 86400.0, 0.5)

            # Força final (0-100)
            zone['strength'] = (touches_factor * 0.6 + time_factor * 0.4) * 100

        return zones

    def _detect_double_tops(
        self,
        swing_highs: pd.Series,
        data: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Detectar padrões de double top

        Args:
            swing_highs: Series com swing highs
            data: DataFrame com OHLC data

        Returns:
            List: Lista de double tops detectados
        """
        valid_highs = swing_highs.dropna()
        double_tops = []

        if len(valid_highs) < 2:
            return double_tops

        for i in range(len(valid_highs) - 1):
            high1 = valid_highs.iloc[i]
            high2 = valid_highs.iloc[i + 1]

            # Verificar se são aproximadamente iguais
            avg_high = (high1 + high2) / 2
            tolerance = avg_high * self.zone_tolerance

            if abs(high1 - high2) <= tolerance:
                # Verificar se há um vale entre eles
                idx1 = valid_highs.index[i]
                idx2 = valid_highs.index[i + 1]

                valley_data = data.loc[idx1:idx2]
                if len(valley_data) > 0:
                    valley_low = valley_data['low'].min()

                    # Verificar profundidade do vale
                    depth = (avg_high - valley_low) / avg_high

                    if depth >= 0.01:  # Mínimo 1% de profundidade
                        double_tops.append({
                            'level': avg_high,
                            'high1': high1,
                            'high2': high2,
                            'valley': valley_low,
                            'depth': depth,
                            'timestamp1': idx1,
                            'timestamp2': idx2
                        })

        return double_tops

    def _detect_double_bottoms(
        self,
        swing_lows: pd.Series,
        data: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Detectar padrões de double bottom

        Args:
            swing_lows: Series com swing lows
            data: DataFrame com OHLC data

        Returns:
            List: Lista de double bottoms detectados
        """
        valid_lows = swing_lows.dropna()
        double_bottoms = []

        if len(valid_lows) < 2:
            return double_bottoms

        for i in range(len(valid_lows) - 1):
            low1 = valid_lows.iloc[i]
            low2 = valid_lows.iloc[i + 1]

            # Verificar se são aproximadamente iguais
            avg_low = (low1 + low2) / 2
            tolerance = avg_low * self.zone_tolerance

            if abs(low1 - low2) <= tolerance:
                # Verificar se há um pico entre eles
                idx1 = valid_lows.index[i]
                idx2 = valid_lows.index[i + 1]

                peak_data = data.loc[idx1:idx2]
                if len(peak_data) > 0:
                    peak_high = peak_data['high'].max()

                    # Verificar altura do pico
                    height = (peak_high - avg_low) / avg_low

                    if height >= 0.01:  # Mínimo 1% de altura
                        double_bottoms.append({
                            'level': avg_low,
                            'low1': low1,
                            'low2': low2,
                            'peak': peak_high,
                            'height': height,
                            'timestamp1': idx1,
                            'timestamp2': idx2
                        })

        return double_bottoms

    def _detect_reversals(
        self,
        data: pd.DataFrame,
        swing_highs: pd.Series,
        swing_lows: pd.Series
    ) -> pd.DataFrame:
        """
        Detectar sinais de reversão com lógica melhorada

        Args:
            data: DataFrame com OHLC data
            swing_highs: Series com swing highs
            swing_lows: Series com swing lows

        Returns:
            pd.DataFrame: DataFrame com sinais de reversão
        """
        reversals = pd.DataFrame(index=data.index, columns=['signal'])

        for i in range(1, len(data)):
            # Reversão de alta (bearish to bullish) - swing low mais alto
            if (not pd.isna(swing_lows.iloc[i]) and
                not pd.isna(swing_lows.iloc[i - 1]) and
                swing_lows.iloc[i] > swing_lows.iloc[i - 1]):
                reversals.iloc[i] = 'buy'

            # Reversão de baixa (bullish to bearish) - swing high mais baixo
            elif (not pd.isna(swing_highs.iloc[i]) and
                  not pd.isna(swing_highs.iloc[i - 1]) and
                  swing_highs.iloc[i] < swing_highs.iloc[i - 1]):
                reversals.iloc[i] = 'sell'

        # Lógica adicional: detectar reversões baseadas em proximidade de zonas
        # para o último candle
        if len(data) > 0:
            last_idx = data.index[-1]
            last_price = data['close'].iloc[-1]
            last_low = data['low'].iloc[-1]
            last_high = data['high'].iloc[-1]

            # Verificar se está perto de um swing low recente (suporte)
            recent_swing_lows = swing_lows.dropna().tail(5)
            if not recent_swing_lows.empty:
                for idx, swing_low in recent_swing_lows.items():
                    if abs(last_price - swing_low) / last_price < 0.002:  # 0.2% de tolerância
                        if last_low > swing_low:  # Preço subiu acima do swing low
                            reversals.loc[last_idx] = 'buy'
                            break

            # Verificar se está perto de um swing high recente (resistência)
            recent_swing_highs = swing_highs.dropna().tail(5)
            if not recent_swing_highs.empty:
                for idx, swing_high in recent_swing_highs.items():
                    if abs(last_price - swing_high) / last_price < 0.002:  # 0.2% de tolerância
                        if last_high < swing_high:  # Preço caiu abaixo do swing high
                            reversals.loc[last_idx] = 'sell'
                            break

        reversals = reversals.fillna('hold')
        return reversals

    def _get_nearest_zone(
        self,
        zones: List[Dict[str, Any]],
        prices: pd.Series,
        zone_type: str
    ) -> pd.Series:
        """
        Obter a zona mais próxima para cada preço

        Args:
            zones: Lista de zonas
            prices: Series com preços
            zone_type: 'support', 'resistance', 'demand', 'supply', 'fvg', 'order_block', ou 'liquidity'

        Returns:
            pd.Series: Series com zonas mais próximas
        """
        nearest = pd.Series(np.nan, index=prices.index)

        if not zones:
            return nearest

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)

                # Filtrar por tipo de zona
                if zone_type == 'support' and zone['level'] <= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone['level']
                elif zone_type == 'resistance' and zone['level'] >= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone['level']
                # Para demand, supply, fvg, order_block, liquidity - retorna a mais próxima sem filtro
                elif zone_type in ['demand', 'supply', 'fvg', 'order_block', 'liquidity']:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone['level']

            if nearest_zone is not None:
                nearest.iloc[i] = nearest_zone

        return nearest

    def _get_zone_boundary(
        self,
        zones: List[Dict[str, Any]],
        prices: pd.Series,
        zone_type: str,
        boundary: str
    ) -> pd.Series:
        """
        Obter o limite (high ou low) da zona mais próxima para cada preço

        Args:
            zones: Lista de zonas
            prices: Series com preços
            zone_type: 'support', 'resistance', 'demand', 'supply', 'fvg', 'order_block', ou 'liquidity'
            boundary: 'high' ou 'low'

        Returns:
            pd.Series: Series com limites das zonas
        """
        boundary_values = pd.Series(np.nan, index=prices.index)

        if not zones:
            return boundary_values

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)

                # Filtrar por tipo de zona
                if zone_type == 'support' and zone['level'] <= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone
                elif zone_type == 'resistance' and zone['level'] >= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone
                # Para demand, supply, fvg, order_block, liquidity - retorna a mais próxima sem filtro
                elif zone_type in ['demand', 'supply', 'fvg', 'order_block', 'liquidity']:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone

            if nearest_zone is not None:
                boundary_values.iloc[i] = nearest_zone[boundary]

        return boundary_values

    def _get_zone_strength(
        self,
        zones: List[Dict[str, Any]],
        prices: pd.Series,
        zone_type: str
    ) -> pd.Series:
        """
        Obter a força da zona mais próxima para cada preço

        Args:
            zones: Lista de zonas
            prices: Series com preços
            zone_type: 'support', 'resistance', 'demand', 'supply', 'fvg', 'order_block', ou 'liquidity'

        Returns:
            pd.Series: Series com forças das zonas
        """
        strength = pd.Series(0.0, index=prices.index, dtype=float)

        if not zones:
            return strength

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)

                # Filtrar por tipo de zona
                if zone_type == 'support' and zone['level'] <= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone
                elif zone_type == 'resistance' and zone['level'] >= price:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone
                # Para demand, supply, fvg, order_block, liquidity - retorna a mais próxima sem filtro
                elif zone_type in ['demand', 'supply', 'fvg', 'order_block', 'liquidity']:
                    if distance < min_distance:
                        min_distance = distance
                        nearest_zone = zone

            if nearest_zone is not None:
                strength.iloc[i] = float(nearest_zone['strength'])

        return strength

    def get_latest_signal(self, data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Obter o sinal mais recente baseado em todas as zonas

        Args:
            data: DataFrame com OHLC data

        Returns:
            Optional[Dict]: Sinal mais recente com todas as zonas
        """
        zonas_df = self.calculate(data)

        if zonas_df.empty:
            return None

        latest = zonas_df.iloc[-1]
        current_price = data['close'].iloc[-1]

        # Calcular distância para zonas principais
        support_distance = 0
        resistance_distance = 0
        support_zone_width = 0
        resistance_zone_width = 0

        if not pd.isna(latest['nearest_support']):
            support_distance = (current_price - latest['nearest_support']) / current_price * 100
            support_zone_width = (latest['support_high'] - latest['support_low']) / current_price * 100

        if not pd.isna(latest['nearest_resistance']):
            resistance_distance = (latest['nearest_resistance'] - current_price) / current_price * 100
            resistance_zone_width = (latest['resistance_high'] - latest['resistance_low']) / current_price * 100

        # Calcular confluência de zonas
        confluence_count = 0
        confluence_zones = []

        if not pd.isna(latest['nearest_demand']):
            confluence_count += 1
            confluence_zones.append('demand')

        if not pd.isna(latest['nearest_supply']):
            confluence_count += 1
            confluence_zones.append('supply')

        if not pd.isna(latest['nearest_fvg']):
            confluence_count += 1
            confluence_zones.append('fvg')

        if not pd.isna(latest['nearest_order_block']):
            confluence_count += 1
            confluence_zones.append('order_block')

        if not pd.isna(latest['nearest_pivot']):
            confluence_count += 1
            confluence_zones.append('pivot')

        if not pd.isna(latest['nearest_fib']):
            confluence_count += 1
            confluence_zones.append('fibonacci')

        if not pd.isna(latest['nearest_psych']):
            confluence_count += 1
            confluence_zones.append('psychological')

        if not pd.isna(latest['nearest_liquidity']):
            confluence_count += 1
            confluence_zones.append('liquidity')

        # Determinar sinal baseado em confluência
        signal = 'hold'
        confidence = 0
        in_zone = False

        # Verificar se está dentro de alguma zona principal
        if not pd.isna(latest['nearest_support']) and not pd.isna(latest['support_high']) and not pd.isna(latest['support_low']):
            if latest['support_low'] <= current_price <= latest['support_high']:
                in_zone = True
                confidence = latest['support_strength'] + (confluence_count * 5)
                if confidence > 70:
                    signal = 'buy'

        if not pd.isna(latest['nearest_resistance']) and not pd.isna(latest['resistance_high']) and not pd.isna(latest['resistance_low']):
            if latest['resistance_low'] <= current_price <= latest['resistance_high']:
                in_zone = True
                confidence = latest['resistance_strength'] + (confluence_count * 5)
                if confidence > 70:
                    signal = 'sell'

        # Se não está em zona, verificar proximidade e confluência
        if not in_zone and confluence_count >= 2:
            # Alta confluência = sinal mais forte
            if not pd.isna(latest['nearest_demand']) and support_distance < 1.0:
                signal = 'buy'
                confidence = 80 + min(confluence_count * 3, 15)
            elif not pd.isna(latest['nearest_supply']) and resistance_distance < 1.0:
                signal = 'sell'
                confidence = 80 + min(confluence_count * 3, 15)
        elif not in_zone:
            if not pd.isna(latest['nearest_support']) and support_distance < 0.5:
                if latest['support_strength'] > 70:
                    signal = 'buy'
                    confidence = latest['support_strength'] * 0.7 + (confluence_count * 3)
            elif not pd.isna(latest['nearest_resistance']) and resistance_distance < 0.5:
                if latest['resistance_strength'] > 70:
                    signal = 'sell'
                    confidence = latest['resistance_strength'] * 0.7 + (confluence_count * 3)

        return {
            'signal': signal,
            'confidence': min(confidence, 100),
            'current_price': current_price,
            # Zonas principais
            'nearest_support': latest['nearest_support'],
            'nearest_resistance': latest['nearest_resistance'],
            'support_strength': latest['support_strength'],
            'resistance_strength': latest['resistance_strength'],
            'support_high': latest['support_high'],
            'support_low': latest['support_low'],
            'resistance_high': latest['resistance_high'],
            'resistance_low': latest['resistance_low'],
            'support_zone_width_pct': support_zone_width,
            'resistance_zone_width_pct': resistance_zone_width,
            'support_distance_pct': support_distance,
            'resistance_distance_pct': resistance_distance,
            # Supply/Demand
            'nearest_demand': latest['nearest_demand'],
            'nearest_supply': latest['nearest_supply'],
            'demand_strength': latest['demand_strength'],
            'supply_strength': latest['supply_strength'],
            # Fair Value Gaps
            'nearest_fvg': latest['nearest_fvg'],
            'fvg_type': latest['fvg_type'],
            # Order Blocks
            'nearest_order_block': latest['nearest_order_block'],
            'order_block_type': latest['order_block_type'],
            # Pivot Points
            'nearest_pivot': latest['nearest_pivot'],
            'pivot_type': latest['pivot_type'],
            # Fibonacci
            'nearest_fib': latest['nearest_fib'],
            'fib_level': latest['fib_level'],
            # Psychological
            'nearest_psych': latest['nearest_psych'],
            # Liquidity
            'nearest_liquidity': latest['nearest_liquidity'],
            'liquidity_type': latest['liquidity_type'],
            # Status
            'in_zone': in_zone,
            'confluence_count': confluence_count,
            'confluence_zones': confluence_zones,
            'reversal_signal': latest['reversal_signal'],
            'timestamp': data.index[-1]
        }

    def get_zones_summary(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Obter resumo de todas as zonas identificadas

        Args:
            data: DataFrame com OHLC data

        Returns:
            Dict: Resumo de todas as zonas
        """
        zonas_df = self.calculate(data)

        if zonas_df.empty:
            return {}

        latest = zonas_df.iloc[-1]

        return {
            'support_zones': {
                'nearest': latest['nearest_support'],
                'strength': latest['support_strength'],
                'high': latest['support_high'],
                'low': latest['support_low']
            },
            'resistance_zones': {
                'nearest': latest['nearest_resistance'],
                'strength': latest['resistance_strength'],
                'high': latest['resistance_high'],
                'low': latest['resistance_low']
            },
            'demand_zones': {
                'nearest': latest['nearest_demand'],
                'strength': latest['demand_strength']
            },
            'supply_zones': {
                'nearest': latest['nearest_supply'],
                'strength': latest['supply_strength']
            },
            'fvg_zones': {
                'nearest': latest['nearest_fvg'],
                'type': latest['fvg_type']
            },
            'order_blocks': {
                'nearest': latest['nearest_order_block'],
                'type': latest['order_block_type']
            },
            'pivot_points': {
                'nearest': latest['nearest_pivot'],
                'type': latest['pivot_type']
            },
            'fibonacci_levels': {
                'nearest': latest['nearest_fib'],
                'level': latest['fib_level']
            },
            'psychological_levels': {
                'nearest': latest['nearest_psych']
            },
            'liquidity_zones': {
                'nearest': latest['nearest_liquidity'],
                'type': latest['liquidity_type']
            }
        }

    def _detect_demand_zones(self, data: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Detectar zonas de demanda (bullish order blocks)"""
        demand_zones = []
        high = data['high']
        low = data['low']
        close = data['close']
        has_open = 'open' in data.columns

        for i in range(2, len(data)):
            # Identificar candle bearish forte
            if has_open:
                is_bearish = close.iloc[i-1] < data['open'].iloc[i-1]
                is_bullish = close.iloc[i] > data['open'].iloc[i]
            else:
                is_bearish = close.iloc[i-1] < high.iloc[i-1]
                is_bullish = close.iloc[i] > low.iloc[i]

            if is_bearish and is_bullish:
                # Criar zona de demanda
                zone_level = low.iloc[i-1]
                zone_margin = atr * 0.5

                demand_zones.append({
                    'level': zone_level,
                    'high': zone_level + zone_margin,
                    'low': max(zone_level - zone_margin, 0),
                    'type': 'demand',
                    'strength': 70,
                    'timestamp': data.index[i-1]
                })

        return demand_zones

    def _detect_supply_zones(self, data: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Detectar zonas de oferta (bearish order blocks)"""
        supply_zones = []
        high = data['high']
        low = data['low']
        close = data['close']
        has_open = 'open' in data.columns

        for i in range(2, len(data)):
            # Identificar candle bullish forte
            if has_open:
                is_bullish = close.iloc[i-1] > data['open'].iloc[i-1]
                is_bearish = close.iloc[i] < data['open'].iloc[i]
            else:
                is_bullish = close.iloc[i-1] > low.iloc[i-1]
                is_bearish = close.iloc[i] < high.iloc[i]

            if is_bullish and is_bearish:
                # Criar zona de oferta
                zone_level = high.iloc[i-1]
                zone_margin = atr * 0.5

                supply_zones.append({
                    'level': zone_level,
                    'high': zone_level + zone_margin,
                    'low': max(zone_level - zone_margin, 0),
                    'type': 'supply',
                    'strength': 70,
                    'timestamp': data.index[i-1]
                })

        return supply_zones

    def _detect_fair_value_gaps(self, data: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Detectar Fair Value Gaps"""
        fvg_zones = []

        for i in range(2, len(data)):
            # Bullish FVG: gap entre candle i-2 e i
            if data['low'].iloc[i] > data['high'].iloc[i-2]:
                gap_high = data['low'].iloc[i]
                gap_low = data['high'].iloc[i-2]
                gap_size = gap_high - gap_low

                if gap_size > atr * 0.3:
                    fvg_zones.append({
                        'level': (gap_high + gap_low) / 2,
                        'high': gap_high,
                        'low': gap_low,
                        'type': 'bullish',
                        'strength': 75,
                        'timestamp': data.index[i]
                    })

            # Bearish FVG
            if data['high'].iloc[i] < data['low'].iloc[i-2]:
                gap_high = data['low'].iloc[i-2]
                gap_low = data['high'].iloc[i]
                gap_size = gap_high - gap_low

                if gap_size > atr * 0.3:
                    fvg_zones.append({
                        'level': (gap_high + gap_low) / 2,
                        'high': gap_high,
                        'low': gap_low,
                        'type': 'bearish',
                        'strength': 75,
                        'timestamp': data.index[i]
                    })

        return fvg_zones

    def _detect_order_blocks(self, data: pd.DataFrame, atr: float) -> List[Dict[str, Any]]:
        """Detectar Order Blocks"""
        order_blocks = []
        has_open = 'open' in data.columns

        for i in range(1, len(data) - 1):
            # Bullish Order Block (último candle bearish antes de movimento de alta)
            if data['close'].iloc[i+1] > data['close'].iloc[i]:
                if has_open:
                    is_bearish = data['close'].iloc[i] < data['open'].iloc[i]
                else:
                    is_bearish = data['close'].iloc[i] < data['high'].iloc[i]

                if is_bearish:
                    zone_level = data['low'].iloc[i]
                    order_blocks.append({
                        'level': zone_level,
                        'high': zone_level + atr * 0.3,
                        'low': max(zone_level - atr * 0.3, 0),
                        'type': 'bullish',
                        'strength': 65,
                        'timestamp': data.index[i]
                    })

            # Bearish Order Block (último candle bullish antes de movimento de baixa)
            if data['close'].iloc[i+1] < data['close'].iloc[i]:
                if has_open:
                    is_bullish = data['close'].iloc[i] > data['open'].iloc[i]
                else:
                    is_bullish = data['close'].iloc[i] > data['low'].iloc[i]

                if is_bullish:
                    zone_level = data['high'].iloc[i]
                    order_blocks.append({
                        'level': zone_level,
                        'high': zone_level + atr * 0.3,
                        'low': max(zone_level - atr * 0.3, 0),
                        'type': 'bearish',
                        'strength': 65,
                        'timestamp': data.index[i]
                    })

        return order_blocks

    def _calculate_pivot_points(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Calcular Pivot Points"""
        if len(data) < 2:
            return []

        # Usar candle anterior para calcular pivots
        prev = data.iloc[-2]
        high = prev['high']
        low = prev['low']
        close = prev['close']

        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)

        return [
            {'level': pivot, 'type': 'pivot', 'strength': 80},
            {'level': r1, 'type': 'resistance', 'strength': 70},
            {'level': r2, 'type': 'resistance', 'strength': 60},
            {'level': r3, 'type': 'resistance', 'strength': 50},
            {'level': s1, 'type': 'support', 'strength': 70},
            {'level': s2, 'type': 'support', 'strength': 60},
            {'level': s3, 'type': 'support', 'strength': 50}
        ]

    def _calculate_fibonacci_levels(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Calcular níveis de Fibonacci"""
        if len(data) < 20:
            return []

        high = data['high'].iloc[-20:].max()
        low = data['low'].iloc[-20:].min()
        diff = high - low

        if diff == 0:
            return []

        fib_levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
        fib_names = ['0%', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']
        fib_types = ['support', 'support', 'support', 'pivot', 'resistance', 'resistance', 'resistance']

        levels = []
        for level, name, ftype in zip(fib_levels, fib_names, fib_types):
            price = low + diff * level
            levels.append({
                'level': price,
                'type': ftype,
                'name': name,
                'strength': 65
            })

        return levels

    def _detect_psychological_levels(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detectar níveis psicológicos (números redondos)"""
        close = data['close'].iloc[-1]
        levels = []

        # Determinar escala baseada no preço
        if close >= 1000:
            step = 100
        elif close >= 100:
            step = 10
        elif close >= 10:
            step = 1
        elif close >= 1:
            step = 0.1
        else:
            step = 0.01

        # Encontrar nível base mais próximo
        base = round(close / step) * step

        # Adicionar níveis psicológicos próximos
        for offset in range(-5, 6):
            level = base + offset * step
            if level > 0:
                levels.append({
                    'level': level,
                    'type': 'psychological',
                    'strength': 50
                })

        return levels

    def _detect_liquidity_zones(
        self,
        data: pd.DataFrame,
        swing_highs: pd.Series,
        swing_lows: pd.Series,
        atr: float
    ) -> List[Dict[str, Any]]:
        """Detectar zonas de liquidez"""
        liquidity_zones = []
        tolerance = atr * 0.5

        # Agrupar swing highs próximos (liquidez de venda)
        valid_highs = swing_highs.dropna()
        if len(valid_highs) >= 2:
            for i in range(len(valid_highs) - 1):
                for j in range(i + 1, len(valid_highs)):
                    if abs(valid_highs.iloc[i] - valid_highs.iloc[j]) < tolerance:
                        level = (valid_highs.iloc[i] + valid_highs.iloc[j]) / 2
                        liquidity_zones.append({
                            'level': level,
                            'high': level + tolerance,
                            'low': max(level - tolerance, 0),
                            'type': 'sell',
                            'liq_type': 'sell',
                            'strength': 60
                        })
                        break

        # Agrupar swing lows próximos (liquidez de compra)
        valid_lows = swing_lows.dropna()
        if len(valid_lows) >= 2:
            for i in range(len(valid_lows) - 1):
                for j in range(i + 1, len(valid_lows)):
                    if abs(valid_lows.iloc[i] - valid_lows.iloc[j]) < tolerance:
                        level = (valid_lows.iloc[i] + valid_lows.iloc[j]) / 2
                        liquidity_zones.append({
                            'level': level,
                            'high': level + tolerance,
                            'low': max(level - tolerance, 0),
                            'type': 'buy',
                            'liq_type': 'buy',
                            'strength': 60
                        })
                        break

        return liquidity_zones

    def _get_fvg_type(self, zones: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter tipo do FVG mais próximo"""
        fvg_types = pd.Series('none', index=prices.index)

        if not zones:
            return fvg_types

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_zone = zone

            if nearest_zone is not None:
                fvg_types.iloc[i] = nearest_zone['type']

        return fvg_types

    def _get_order_block_type(self, zones: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter tipo do Order Block mais próximo"""
        ob_types = pd.Series('none', index=prices.index)

        if not zones:
            return ob_types

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_zone = zone

            if nearest_zone is not None:
                ob_types.iloc[i] = nearest_zone['type']

        return ob_types

    def _get_nearest_pivot(self, pivots: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter pivot mais próximo"""
        nearest = pd.Series(np.nan, index=prices.index)

        if not pivots:
            return nearest

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_pivot = None
            min_distance = float('inf')

            for pivot in pivots:
                distance = abs(pivot['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_pivot = pivot['level']

            if nearest_pivot is not None:
                nearest.iloc[i] = nearest_pivot

        return nearest

    def _get_pivot_type(self, pivots: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter tipo do pivot mais próximo"""
        pivot_types = pd.Series('none', index=prices.index)

        if not pivots:
            return pivot_types

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_pivot = None
            min_distance = float('inf')

            for pivot in pivots:
                distance = abs(pivot['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_pivot = pivot

            if nearest_pivot is not None:
                pivot_types.iloc[i] = nearest_pivot['type']

        return pivot_types

    def _get_nearest_fib(self, fibs: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter nível Fibonacci mais próximo"""
        nearest = pd.Series(np.nan, index=prices.index)

        if not fibs:
            return nearest

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_fib = None
            min_distance = float('inf')

            for fib in fibs:
                distance = abs(fib['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_fib = fib['level']

            if nearest_fib is not None:
                nearest.iloc[i] = nearest_fib

        return nearest

    def _get_fib_level_name(self, fibs: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter nome do nível Fibonacci mais próximo"""
        fib_names = pd.Series('none', index=prices.index)

        if not fibs:
            return fib_names

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_fib = None
            min_distance = float('inf')

            for fib in fibs:
                distance = abs(fib['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_fib = fib

            if nearest_fib is not None:
                fib_names.iloc[i] = nearest_fib['name']

        return fib_names

    def _get_nearest_psych(self, psych_levels: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter nível psicológico mais próximo"""
        nearest = pd.Series(np.nan, index=prices.index)

        if not psych_levels:
            return nearest

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_level = None
            min_distance = float('inf')

            for level in psych_levels:
                distance = abs(level['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_level = level['level']

            if nearest_level is not None:
                nearest.iloc[i] = nearest_level

        return nearest

    def _get_liquidity_type(self, zones: List[Dict[str, Any]], prices: pd.Series) -> pd.Series:
        """Obter tipo da zona de liquidez mais próxima"""
        liq_types = pd.Series('none', index=prices.index)

        if not zones:
            return liq_types

        for i, price in enumerate(prices):
            if pd.isna(price):
                continue

            nearest_zone = None
            min_distance = float('inf')

            for zone in zones:
                distance = abs(zone['level'] - price)
                if distance < min_distance:
                    min_distance = distance
                    nearest_zone = zone

            if nearest_zone is not None:
                liq_types.iloc[i] = nearest_zone['liq_type']

        return liq_types
