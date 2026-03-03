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

    def __init__(self, base_path: str = "data/actives", max_ticks_per_file: int = 10000):
        self.base_path = Path(base_path)
        self._running = False
        # Locks para evitar race condition por arquivo
        self._file_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Limite máximo de ticks por arquivo para evitar crescimento excessivo
        self._max_ticks_per_file = max_ticks_per_file
        # Contador de escritas por arquivo para verificação periódica de truncagem
        self._write_counters: Dict[str, int] = {}

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
        
        logger.info(f"[OK] Local Storage iniciado em {self.base_path} (clear_on_start={clear_on_start}, max_ticks={self._max_ticks_per_file})")

    async def stop(self):
        """Parar serviço"""
        self._running = False
        logger.info("[OK] Local Storage parado")

    async def _clear_actives_folder(self):
        """Limpar pasta actives ao iniciar"""
        if self.base_path.exists():
            try:
                # Usar loop.run_in_executor para operações síncronas de arquivo
                loop = asyncio.get_event_loop()
                
                # Tentar deletar cada arquivo individualmente para evitar erros de arquivos em uso
                files = await loop.run_in_executor(None, lambda: list(self.base_path.glob("*.txt")))
                for file_path in files:
                    try:
                        await loop.run_in_executor(None, file_path.unlink)
                    except Exception as e:
                        # Ignorar arquivos que não podem ser deletados (provavelmente em uso)
                        pass
                
                logger.info(f"[OK] Pasta {self.base_path} limpa")
            except Exception as e:
                logger.warning(f"Aviso: Não foi possível limpar pasta {self.base_path}: {e}")
        
        # Criar pasta de forma assíncrona
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.base_path.mkdir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Aviso ao criar pasta: {e}")

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
        """Adicionar tick direto ao arquivo usando append mode - MUITO MAIS RÁPIDO"""
        lock = self._file_locks[asset_symbol]
        
        async with lock:
            try:
                file_path = self.base_path / f"{asset_symbol}.txt"
                
                # Usar append mode ('a') em vez de reescrever tudo!
                # Formato: Line-delimited JSON (JSONL) - uma linha por tick, sem indentação
                line = json.dumps(tick_data, separators=(',', ':'))
                
                async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
                    await f.write(line + "\n")
                
                # Verificar se precisa truncar periodicamente (a cada 100 escritas)
                self._write_counters[asset_symbol] = self._write_counters.get(asset_symbol, 0) + 1
                if self._write_counters[asset_symbol] % 100 == 0:
                    await self._truncate_if_needed(asset_symbol, file_path)
                
            except Exception as e:
                logger.error(f"Erro ao salvar tick para {asset_symbol}: {e}")

    async def _append_to_file_batch(self, asset_symbol: str, tick_data_list: List[Dict]):
        """Adicionar múltiplos ticks em batch usando append mode - MUITO MAIS RÁPIDO"""
        if not tick_data_list:
            return
            
        lock = self._file_locks[asset_symbol]
        
        async with lock:
            try:
                file_path = self.base_path / f"{asset_symbol}.txt"
                
                # Verificar último timestamp apenas se arquivo existir (leitura parcial)
                last_timestamp = 0
                if file_path.exists():
                    try:
                        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                            await f.seek(0, 2)  # SEEK_END
                            file_size = await f.tell()
                            if file_size > 0:
                                # Ler últimos 1KB para encontrar última linha
                                read_size = min(1024, file_size)
                                await f.seek(file_size - read_size)
                                last_chunk = await f.read()
                                lines = last_chunk.strip().split('\n')
                                if lines:
                                    last_line = lines[-1]
                                    try:
                                        last_tick = json.loads(last_line)
                                        last_timestamp = last_tick.get("timestamp", 0)
                                    except:
                                        pass
                    except Exception:
                        pass
                
                # Filtrar apenas ticks novos
                new_ticks = [tick for tick in tick_data_list if tick["timestamp"] > last_timestamp]
                
                if new_ticks:
                    # Escrever todas as linhas de uma vez usando append mode
                    lines = [json.dumps(tick, separators=(',', ':')) for tick in new_ticks]
                    content = "\n".join(lines) + "\n"
                    
                    async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
                        await f.write(content)
                    
                    # Verificar truncagem periodicamente
                    self._write_counters[asset_symbol] = self._write_counters.get(asset_symbol, 0) + len(new_ticks)
                    if self._write_counters[asset_symbol] % 100 == 0:
                        await self._truncate_if_needed(asset_symbol, file_path)
                    
                    logger.debug(f"[OK] [{asset_symbol}] Adicionados {len(new_ticks)} ticks via append")
                else:
                    logger.debug(f"[SKIP] [{asset_symbol}] Nenhum tick novo")
                
            except Exception as e:
                logger.error(f"Erro ao salvar ticks em lote para {asset_symbol}: {e}")

    async def _truncate_if_needed(self, asset_symbol: str, file_path: Path):
        """Truncar arquivo se exceder limite de ticks"""
        try:
            if not file_path.exists():
                return
            
            # Obter tamanho do arquivo de forma assíncrona via aiofiles
            # Usar loop.run_in_executor para evitar bloqueio
            loop = asyncio.get_event_loop()
            file_size = await loop.run_in_executor(None, file_path.stat)
            file_size = file_size.st_size
            
            if file_size < self._max_ticks_per_file * 50:  # Estimativa: ~50 bytes por linha
                return
            
            line_count = 0
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                async for _ in f:
                    line_count += 1
                    if line_count > self._max_ticks_per_file:
                        break
            
            if line_count > self._max_ticks_per_file:
                # Manter apenas últimos N ticks
                lines_to_keep = []
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    all_lines = await f.readlines()
                    lines_to_keep = all_lines[-self._max_ticks_per_file:]
                
                # Reescrever com dados truncados
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.writelines(lines_to_keep)
                
                logger.info(f"[TRUNCATE] [{asset_symbol}] Arquivo truncado para {len(lines_to_keep)} ticks")
                
        except Exception as e:
            logger.warning(f"Erro ao verificar/truncar arquivo {asset_symbol}: {e}")

    async def _load_ticks_optimized(self, asset_symbol: str, limit: int = 1000) -> List[Dict[str, Any]]:
        """Carregar ticks do arquivo de forma otimizada (linha por linha)"""
        file_path = self.base_path / f"{asset_symbol}.txt"
        
        if not file_path.exists():
            return []
        
        try:
            ticks = []
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if line:
                        try:
                            tick = json.loads(line)
                            ticks.append(tick)
                        except json.JSONDecodeError:
                            continue
            
            # Retornar apenas os últimos N ticks se limit especificado
            if limit and len(ticks) > limit:
                return ticks[-limit:]
            return ticks
                
        except Exception as e:
            logger.error(f"Erro ao carregar ticks para {asset_symbol}: {e}")
            return []

    def get_asset_path(self, asset_symbol: str) -> Path:
        """Obter caminho do ativo"""
        return self.base_path / asset_symbol

    def list_assets(self) -> List[str]:
        """Listar todos os ativos com dados"""
        if not self.base_path.exists():
            return []
        
        return [f.stem for f in self.base_path.glob("*.txt") if f.is_file()]

    async def load_candles_from_file(self, asset_symbol: str, timeframe: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Carregar candles do arquivo local e converter para formato OHLC (otimizado)"""
        ticks = await self._load_ticks_optimized(asset_symbol, limit=limit * 10)
        
        if not ticks:
            return []
        
        return self._convert_ticks_to_ohlc(ticks, timeframe, limit)
    
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
        """Obter o tick mais recente para um símbolo (otimizado - lê apenas última linha)"""
        file_path = self.base_path / f"{symbol}.txt"
        
        if not file_path.exists():
            return None
        
        try:
            # Ler apenas a última linha do arquivo (MUITO mais rápido!)
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                await f.seek(0, 2)  # SEEK_END
                file_size = await f.tell()
                
                if file_size == 0:
                    return None
                
                # Ler últimos 1KB para encontrar última linha
                read_size = min(1024, file_size)
                await f.seek(file_size - read_size)
                last_chunk = await f.read()
                
                lines = last_chunk.strip().split('\n')
                if lines:
                    last_line = lines[-1]
                    try:
                        tick = json.loads(last_line)
                        return {
                            "price": tick["price"],
                            "timestamp": tick["timestamp"]
                        }
                    except json.JSONDecodeError:
                        return None
                
                return None
                
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
