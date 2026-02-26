"""
Agregador de Ticks em Candles OHLC
"""

import pandas as pd
from typing import List, Dict, Tuple
from loguru import logger


class TickAggregator:
    """Agrega ticks em candles OHLC"""

    @staticmethod
    def aggregate_to_ohlc(ticks: pd.DataFrame, timeframe: int) -> pd.DataFrame:
        """
        Agregar ticks em candles OHLC para um timeframe específico
        
        Args:
            ticks: DataFrame com colunas timestamp, datetime, price
            timeframe: Timeframe em segundos (ex: 60 = 1min, 300 = 5min)
        
        Returns:
            DataFrame com colunas timestamp, open, high, low, close
        """
        if len(ticks) == 0:
            return pd.DataFrame()
        
        # Ordenar por timestamp
        ticks = ticks.sort_values('timestamp').copy()
        
        # Criar coluna de período
        ticks['period'] = (ticks['timestamp'] // timeframe) * timeframe
        
        # Agrupar por período e calcular OHLC
        candles = ticks.groupby('period').agg({
            'timestamp': 'first',
            'price': ['first', 'max', 'min', 'last']
        }).reset_index(drop=True)
        
        # Renomear colunas
        candles.columns = ['timestamp', 'open', 'high', 'low', 'close']
        
        # Adicionar datetime
        candles['datetime'] = pd.to_datetime(candles['timestamp'], unit='s')
        
        return candles

    @staticmethod
    def aggregate_multiple_timeframes(ticks: pd.DataFrame, timeframes: List[int]) -> Dict[int, pd.DataFrame]:
        """
        Agregar ticks em candles OHLC para múltiplos timeframes
        
        Args:
            ticks: DataFrame com colunas timestamp, datetime, price
            timeframes: Lista de timeframes em segundos
        
        Returns:
            Dict com {timeframe: DataFrame OHLC}
        """
        results = {}
        
        for tf in timeframes:
            candles = TickAggregator.aggregate_to_ohlc(ticks, tf)
            if len(candles) > 0:
                results[tf] = candles
        
        return results

    @staticmethod
    def calculate_candle_count(ticks: pd.DataFrame, timeframe: int) -> int:
        """
        Calcular quantos candles OHLC podem ser gerados
        
        Args:
            ticks: DataFrame com ticks
            timeframe: Timeframe em segundos
        
        Returns:
            Número de candles que podem ser gerados
        """
        if len(ticks) == 0:
            return 0
        
        first_timestamp = ticks['timestamp'].min()
        last_timestamp = ticks['timestamp'].max()
        
        duration = last_timestamp - first_timestamp
        candle_count = int(duration / timeframe) + 1
        
        return candle_count


# Instância global
tick_aggregator = TickAggregator()
