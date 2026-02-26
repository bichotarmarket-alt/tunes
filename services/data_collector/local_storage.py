"""
Serviço de armazenamento local de dados de mercado
"""

import json
import asyncio
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger
from collections import defaultdict
import aiofiles


class LocalStorageService:
    """Serviço para salvar dados de mercado em arquivos locais"""

    def __init__(self, base_path: str = "data/actives"):
        self.base_path = Path(base_path)
        self._running = False
        # Locks para evitar race condition por arquivo
        self._file_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def start(self, clear_on_start: bool = True):
        """Iniciar serviço de armazenamento local
        
        Args:
            clear_on_start: Se True, limpa a pasta de ativos ao iniciar (apenas no startup do sistema)
        """
        self._running = True
        
        # Limpar pasta ao iniciar APENAS se clear_on_start=True (startup do sistema)
        if clear_on_start:
            await self._clear_actives_folder()
        
        # Criar pasta se não existir
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[OK] Local Storage iniciado em {self.base_path} (clear_on_start={clear_on_start})")

    async def stop(self):
        """Parar serviço"""
        self._running = False
        logger.info("[OK] Local Storage parado")

    async def _clear_actives_folder(self):
        """Limpar pasta actives ao iniciar"""
        if self.base_path.exists():
            try:
                # Tentar deletar cada arquivo individualmente para evitar erros de arquivos em uso
                for file_path in self.base_path.glob("*.txt"):
                    try:
                        file_path.unlink()
                    except Exception as e:
                        # Ignorar arquivos que não podem ser deletados (provavelmente em uso)
                        pass
                
                logger.info(f"[OK] Pasta {self.base_path} limpa")
            except Exception as e:
                logger.warning(f"Aviso: Não foi possível limpar pasta {self.base_path}: {e}")
        
        # Recriar pasta
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_tick(self, asset_symbol: str, price: float, timestamp: float):
        """Salvar tick direto no disco"""
        tick_data = {
            "timestamp": timestamp,
            "datetime": datetime.fromtimestamp(timestamp).isoformat(),
            "price": price
        }
        
        await self._append_to_file(asset_symbol, tick_data)

    async def save_history(self, asset_symbol: str, period: int, candles: List[List[float]]):
        """Salvar histórico de candles como ticks direto no disco"""
        # Converter todos os candles para tick_data de uma vez
        tick_data_list = []
        for candle in candles:
            tick_data_list.append({
                "timestamp": candle[0],
                "datetime": datetime.fromtimestamp(candle[0]).isoformat(),
                "price": candle[1]
            })
        
        # Salvar todos os ticks de uma vez
        await self._append_to_file_batch(asset_symbol, tick_data_list)

    async def _append_to_file(self, asset_symbol: str, tick_data: Dict):
        """Adicionar tick direto ao arquivo com lock"""
        # Obter lock para este arquivo específico
        lock = self._file_locks[asset_symbol]
        
        async with lock:
            try:
                # Caminho: data/actives/{asset}.txt
                file_path = self.base_path / f"{asset_symbol}.txt"
                
                # Ler arquivo existente se houver
                existing_data = []
                if file_path.exists():
                    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        if content:
                            try:
                                existing_data = json.loads(content)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Arquivo JSON corrompido para {asset_symbol}, criando novo: {e}")
                                existing_data = []
                
                # Adicionar novo tick
                existing_data.append(tick_data)
                
                # Salvar
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(existing_data, indent=2))
                
            except Exception as e:
                logger.error(f"Erro ao salvar tick para {asset_symbol}: {e}")

    async def _append_to_file_batch(self, asset_symbol: str, tick_data_list: List[Dict]):
        """Adicionar múltiplos ticks ao arquivo de uma vez, evitando duplicação"""
        # Obter lock para este arquivo específico
        lock = self._file_locks[asset_symbol]
        
        async with lock:
            try:
                # Caminho: data/actives/{asset}.txt
                file_path = self.base_path / f"{asset_symbol}.txt"
                
                # Ler arquivo existente se houver
                existing_data = []
                last_timestamp = 0
                
                if file_path.exists():
                    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        if content:
                            try:
                                existing_data = json.loads(content)
                                # Obter o último timestamp para evitar duplicação
                                if existing_data and len(existing_data) > 0:
                                    last_timestamp = existing_data[-1].get("timestamp", 0)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Arquivo JSON corrompido para {asset_symbol}, criando novo: {e}")
                                existing_data = []
                
                # Filtrar novos dados: apenas ticks com timestamp maior que o último existente
                # Isso evita duplicação e lacunas
                new_ticks = [tick for tick in tick_data_list if tick["timestamp"] > last_timestamp]
                
                # Se houver novos ticks, adicionar ao arquivo
                if new_ticks:
                    existing_data.extend(new_ticks)
                    
                    # Salvar
                    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                        await f.write(json.dumps(existing_data, indent=2))
                    
                    logger.info(f"[OK] [{asset_symbol}] Adicionados {len(new_ticks)} novos ticks (último timestamp: {new_ticks[-1]['timestamp']})")
                else:
                    logger.debug(f"[SKIP] [{asset_symbol}] Nenhum tick novo para adicionar (último timestamp: {last_timestamp})")
                
            except Exception as e:
                logger.error(f"Erro ao salvar ticks em lote para {asset_symbol}: {e}")

    def get_asset_path(self, asset_symbol: str) -> Path:
        """Obter caminho do ativo"""
        return self.base_path / asset_symbol

    def list_assets(self) -> List[str]:
        """Listar todos os ativos com dados"""
        if not self.base_path.exists():
            return []
        
        return [d.name for d in self.base_path.iterdir() if d.is_dir()]

    async def load_candles_from_file(self, asset_symbol: str, timeframe: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Carregar candles do arquivo local e converter para formato OHLC
        
        Args:
            asset_symbol: Símbolo do ativo
            timeframe: Timeframe em segundos
            limit: Número máximo de candles a retornar
            
        Returns:
            Lista de candles no formato OHLC
        """
        file_path = self.base_path / f"{asset_symbol}.txt"
        
        if not file_path.exists():
            return []
        
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                if not content:
                    return []
                
                ticks = json.loads(content)
                
                if not ticks:
                    return []
                
                # Converter ticks em candles OHLC para o timeframe especificado
                candles = self._convert_ticks_to_ohlc(ticks, timeframe, limit)
                
                return candles
                
        except Exception as e:
            logger.error(f"Erro ao carregar candles para {asset_symbol}: {e}")
            return []
    
    def _convert_ticks_to_ohlc(self, ticks: List[Dict], timeframe: int, limit: int) -> List[Dict[str, Any]]:
        """Converter ticks em candles OHLC para um timeframe específico
        
        Args:
            ticks: Lista de ticks com timestamp e price
            timeframe: Timeframe em segundos
            limit: Número máximo de candles a retornar
            
        Returns:
            Lista de candles no formato OHLC
        """
        if not ticks:
            return []
        
        # Ordenar ticks por timestamp
        sorted_ticks = sorted(ticks, key=lambda x: x["timestamp"])
        
        # Agrupar ticks por timeframe
        candles_dict = {}
        
        for tick in sorted_ticks:
            timestamp = tick["timestamp"]
            price = tick["price"]
            
            # Calcular o início do candle baseado no timeframe
            candle_start = (timestamp // timeframe) * timeframe
            
            if candle_start not in candles_dict:
                candles_dict[candle_start] = {
                    "timestamp": candle_start,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 1
                }
            else:
                candle = candles_dict[candle_start]
                candle["high"] = max(candle["high"], price)
                candle["low"] = min(candle["low"], price)
                candle["close"] = price
                candle["volume"] += 1
        
        # Converter para lista e ordenar
        candles = list(candles_dict.values())
        candles = sorted(candles, key=lambda x: x["timestamp"])
        
        # Retornar apenas os últimos N candles
        return candles[-limit:] if len(candles) > limit else candles
    
    async def get_candles(
        self,
        symbol: str,
        timeframe: int,
        limit: int = 100,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Obter candles para um símbolo e timeframe específicos
        
        Args:
            symbol: Símbolo do ativo
            timeframe: Timeframe em segundos
            limit: Número máximo de candles a retornar
            start_time: Timestamp inicial (opcional)
            end_time: Timestamp final (opcional)
            
        Returns:
            Lista de candles no formato OHLC
        """
        candles = await self.load_candles_from_file(symbol, timeframe, limit)
        
        # Filtrar por intervalo de tempo se especificado
        if start_time is not None:
            candles = [c for c in candles if c["timestamp"] >= start_time]
        if end_time is not None:
            candles = [c for c in candles if c["timestamp"] <= end_time]
        
        return candles
    
    async def get_latest_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Obter o tick mais recente para um símbolo
        
        Args:
            symbol: Símbolo do ativo
            
        Returns:
            Dicionário com timestamp e price, ou None se não houver dados
        """
        file_path = self.base_path / f"{symbol}.txt"
        
        if not file_path.exists():
            return None
        
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                if not content:
                    return None
                
                ticks = json.loads(content)
                
                if not ticks:
                    return None
                
                # Retornar o tick mais recente
                latest_tick = max(ticks, key=lambda x: x["timestamp"])
                
                return {
                    "price": latest_tick["price"],
                    "timestamp": latest_tick["timestamp"]
                }
                
        except Exception as e:
            logger.error(f"Erro ao carregar tick mais recente para {symbol}: {e}")
            return None
    
    async def get_available_assets(self) -> List[str]:
        """Obter lista de ativos com dados disponíveis
        
        Returns:
            Lista de símbolos de ativos
        """
        if not self.base_path.exists():
            return []
        
        assets = []
        for file_path in self.base_path.glob("*.txt"):
            assets.append(file_path.stem)
        
        return assets

    async def delete_asset_file(self, asset_symbol: str) -> bool:
        """Apagar arquivo de dados de um ativo específico
        
        Args:
            asset_symbol: Símbolo do ativo a ser apagado
            
        Returns:
            True se arquivo foi apagado, False se não existia ou houve erro
        """
        file_path = self.base_path / f"{asset_symbol}.txt"
        
        if not file_path.exists():
            logger.debug(f"Arquivo não encontrado para {asset_symbol}")
            return False
        
        # Obter lock para este arquivo específico
        lock = self._file_locks[asset_symbol]
        
        async with lock:
            # Tentar deletar com retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    file_path.unlink()
                    logger.info(f"[OK] Arquivo apagado: {file_path}")
                    return True
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Arquivo {asset_symbol} em uso, tentando novamente em 100ms...")
                        await asyncio.sleep(0.1 * (attempt + 1))  # Backoff crescente
                    else:
                        logger.error(f"Erro ao apagar arquivo de {asset_symbol} após {max_retries} tentativas: {e}")
                        return False
                except Exception as e:
                    logger.error(f"Erro ao apagar arquivo de {asset_symbol}: {e}")
                    return False
        
        return False


# Instância global
local_storage = LocalStorageService()
