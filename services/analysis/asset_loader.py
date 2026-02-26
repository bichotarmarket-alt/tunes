"""
Loader para carregar dados de ativos dos arquivos JSON
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from loguru import logger


class AssetDataLoader:
    """Carregar dados de ativos dos arquivos JSON salvos"""

    def __init__(self, base_path: str = "data/actives"):
        self.base_path = Path(base_path)

    def load_asset(self, asset_symbol: str) -> Optional[pd.DataFrame]:
        """
        Carregar dados de um ativo do arquivo JSON
        
        Args:
            asset_symbol: Símbolo do ativo (ex: AUDCHF_otc)
        
        Returns:
            DataFrame com colunas: timestamp, datetime, price
        """
        file_path = self.base_path / f"{asset_symbol}.txt"
        
        if not file_path.exists():
            logger.warning(f"Arquivo não encontrado: {file_path}")
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Converter para DataFrame
            df = pd.DataFrame(data)
            
            # Converter timestamp para datetime
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Ordenar por timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            logger.info(f"✓ Carregados {len(df)} ticks de {asset_symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Erro ao carregar {asset_symbol}: {e}")
            return None

    def load_multiple_assets(self, asset_symbols: List[str]) -> dict:
        """
        Carregar dados de múltiplos ativos
        
        Args:
            asset_symbols: Lista de símbolos de ativos
        
        Returns:
            Dict com {asset_symbol: DataFrame}
        """
        results = {}
        
        for symbol in asset_symbols:
            df = self.load_asset(symbol)
            if df is not None:
                results[symbol] = df
        
        return results

    def list_available_assets(self) -> List[str]:
        """
        Listar todos os ativos disponíveis
        
        Returns:
            Lista de símbolos de ativos
        """
        if not self.base_path.exists():
            return []
        
        assets = []
        for file_path in self.base_path.glob("*.txt"):
            # Remover extensão .txt
            asset_symbol = file_path.stem
            assets.append(asset_symbol)
        
        return sorted(assets)

    def get_asset_summary(self, asset_symbol: str) -> Optional[dict]:
        """
        Obter resumo dos dados de um ativo
        
        Args:
            asset_symbol: Símbolo do ativo
        
        Returns:
            Dict com informações do ativo
        """
        df = self.load_asset(asset_symbol)
        
        if df is None:
            return None
        
        return {
            "symbol": asset_symbol,
            "total_ticks": len(df),
            "first_timestamp": df['timestamp'].iloc[0],
            "last_timestamp": df['timestamp'].iloc[-1],
            "first_datetime": df['datetime'].iloc[0].isoformat(),
            "last_datetime": df['datetime'].iloc[-1].isoformat(),
            "min_price": df['price'].min(),
            "max_price": df['price'].max(),
            "avg_price": df['price'].mean(),
            "duration_seconds": df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
        }


# Instância global
asset_loader = AssetDataLoader()
