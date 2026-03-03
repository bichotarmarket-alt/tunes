"""
Performance Monitor - Dashboard de métricas em arquivo único
Atualizado a cada 5 segundos com métricas operacionais completas
"""
import asyncio
import time
import psutil
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


# Mecanismo global para tracking de métricas (evita import circular)
# Estas variáveis são acessíveis de qualquer lugar sem precisar importar performance_monitor
_ws_messages_sent = 0
_ws_messages_recv = 0


def record_ws_message_global(sent: bool = True):
    """Função global para registrar mensagem WebSocket - pode ser chamada de qualquer lugar"""
    global _ws_messages_sent, _ws_messages_recv
    if sent:
        _ws_messages_sent += 1
    else:
        _ws_messages_recv += 1


def get_ws_message_counts():
    """Retorna contagens atuais de mensagens WebSocket"""
    return _ws_messages_sent, _ws_messages_recv


class PerformanceMonitor:
    """
    Monitor de performance que escreve métricas em arquivo único
    Atualizado a cada 5 segundos
    """
    
    def __init__(self, log_file: str = "logs/performance/dashboard.log"):
        self.log_file = Path(log_file)
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
        # Métricas acumuladas
        self.stats = {
            # Requisições
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_latency_ms': 0.0,
            'max_latency_ms': 0.0,
            'rps_current': 0.0,
            'rps_peak': 0.0,
            'latency_p95_ms': 0.0,
            'latency_p99_ms': 0.0,
            'http_4xx_errors': 0,
            'http_5xx_errors': 0,
            
            # Endpoints (top 5 lentos)
            'endpoint_latencies': {},
            
            # Conexões
            'user_connections': 0,
            'monitoring_connections': 0,
            'ws_connections': 0,
            'active_accounts': 0,
            
            # Sistema
            'disk_usage_percent': 0.0,
            'disk_read_mb': 0.0,
            'disk_write_mb': 0.0,
            'network_sent_mb': 0.0,
            'network_recv_mb': 0.0,
            'load_avg_1m': 0.0,
            'load_avg_5m': 0.0,
            'load_avg_15m': 0.0,
            'swap_used_mb': 0.0,
            'swap_total_mb': 0.0,
            
            # Trades
            'trades_executed': 0,
            'trades_pending': 0,
            'trades_success_rate': 0.0,
            
            # Sinais
            'signals_generated': 0,
            'signals_executed': 0,
            'signals_low_confidence': 0,
            
            # Banco de dados
            'db_queries': 0,
            'db_selects': 0,
            'db_inserts': 0,
            'db_updates': 0,
            'db_deletes': 0,
            'db_errors': 0,
            'db_avg_time_ms': 0.0,
            'db_slow_queries': 0,
            'db_total_time_ms': 0.0,
            'db_pool_active': 0,
            'db_pool_available': 0,
            
            # Cache
            'cache_hits': 0,
            'cache_misses': 0,
            'cache_hit_rate': 0.0,
            'cache_memory_mb': 0.0,
            
            # Batch
            'batch_signals_queued': 0,
            'batch_signals_saved': 0,
            'batch_save_errors': 0,
            'batch_avg_time_ms': 0.0,
            'batch_throughput': 0.0,
            'batch_last_save_time': None,
            
            # Agregação
            'aggregation_last_run': None,
            'aggregation_status': 'idle',
            
            # WebSocket & Conectividade
            'ws_messages_sent': 0,
            'ws_messages_recv': 0,
            'ws_reconnections': 0,
            'ws_last_reconnect_time': None,
            'broker_latency_ms': 0.0,
            'broker_last_response_time': None,
            
            # Dados & Agregação
            'assets_available': 0,
            'assets_with_data': 0,
            'candle_gaps_total': 0,
            'candle_gaps_last_hour': 0,
            'data_delay_max_ms': 0.0,
            'data_delay_avg_ms': 0.0,
            'last_tick_time': None,
            'stale_assets_count': 0,
        }
        
        # Histórico para médias móveis e percentis
        self.history = {
            'latency_samples': [],
            'memory_samples': [],
            'cpu_samples': [],
            'request_times': [],  # Para calcular RPS
            'batch_times': [],
        }
        
        # Contadores anteriores para calcular delta
        self._prev_disk_io = None
        self._prev_network_io = None
        self._last_request_count = 0
        self._last_batch_count = 0
        
        # Criar diretório se não existir
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
    async def start(self):
        """Iniciar monitoramento"""
        logger.info("[PerformanceMonitor] start() chamado - running={}", self.running)
        
        if self.running:
            logger.warning("[PerformanceMonitor] Já está rodando, ignorando start()")
            return
            
        self.running = True
        self._start_time = time.time()
        
        # Criar diretório novamente para garantir
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[PerformanceMonitor] Diretório criado: {}", self.log_file.parent)
        
        # Criar arquivo imediatamente
        try:
            await self._collect_metrics()
            await self._write_dashboard()
            logger.info("[PerformanceMonitor] Primeiro dashboard escrito com sucesso")
        except Exception as e:
            logger.error("[PerformanceMonitor] ERRO ao escrever dashboard inicial: {}", e)
            raise
        
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("[PerformanceMonitor] Iniciado - Dashboard em: {}", self.log_file)
        
    async def stop(self):
        """Parar monitoramento"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("[PerformanceMonitor] Parado")
        
    async def _monitor_loop(self):
        """Loop principal de monitoramento - atualiza a cada 1s"""
        while self.running:
            try:
                await self._collect_metrics()
                await self._write_dashboard()
                await asyncio.sleep(1)  # Atualizar a cada 1 segundo
            except Exception as e:
                logger.error(f"[PerformanceMonitor] Erro: {e}")
                await asyncio.sleep(1)
                
    async def _collect_metrics(self):
        """Coletar métricas do sistema e de outros serviços"""
        # Usar processo persistente para medição correta de CPU
        if not hasattr(self, '_process'):
            self._process = psutil.Process()
            # Primeira chamada para inicializar baseline
            self._process.cpu_percent(interval=None)
        
        process = self._process
        
        # CPU e Memória - cpu_percent normalizado (igual ao Gerenciador de Tarefas)
        memory_info = process.memory_info()
        # interval=None retorna uso desde última chamada; divide por cpu_count() para % total
        cpu_percent_raw = process.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count() or 1
        cpu_percent = cpu_percent_raw / cpu_count  # Normalizado para % total do sistema
        
        # Memória: usar working_set no Windows (igual ao Gerenciador de Tarefas)
        # rss no Linux/mac
        import sys
        if sys.platform == 'win32' and hasattr(memory_info, 'wset'):
            memory_mb = memory_info.wset / 1024 / 1024  # Windows Working Set
        else:
            memory_mb = memory_info.rss / 1024 / 1024  # RSS para outros sistemas
        
        # Load Average (Unix-like systems)
        try:
            load_avg = psutil.getloadavg()
            self.stats['load_avg_1m'] = load_avg[0]
            self.stats['load_avg_5m'] = load_avg[1]
            self.stats['load_avg_15m'] = load_avg[2]
        except Exception:
            self.stats['load_avg_1m'] = 0.0
            self.stats['load_avg_5m'] = 0.0
            self.stats['load_avg_15m'] = 0.0
        
        # Memória Swap
        try:
            swap = psutil.swap_memory()
            self.stats['swap_used_mb'] = swap.used / 1024 / 1024
            self.stats['swap_total_mb'] = swap.total / 1024 / 1024
        except Exception:
            self.stats['swap_used_mb'] = 0.0
            self.stats['swap_total_mb'] = 0.0
        
        # Disco - Uso e IO
        try:
            disk_usage = psutil.disk_usage('/')
            self.stats['disk_usage_percent'] = disk_usage.percent
            
            # IO counters (delta desde última medição)
            disk_io = psutil.disk_io_counters()
            if self._prev_disk_io is not None and disk_io:
                read_bytes = disk_io.read_bytes - self._prev_disk_io.read_bytes
                write_bytes = disk_io.write_bytes - self._prev_disk_io.write_bytes
                self.stats['disk_read_mb'] = read_bytes / 1024 / 1024
                self.stats['disk_write_mb'] = write_bytes / 1024 / 1024
            self._prev_disk_io = disk_io
        except Exception:
            self.stats['disk_usage_percent'] = 0.0
        
        # Network IO
        try:
            net_io = psutil.net_io_counters()
            if self._prev_network_io is not None and net_io:
                sent_bytes = net_io.bytes_sent - self._prev_network_io.bytes_sent
                recv_bytes = net_io.bytes_recv - self._prev_network_io.bytes_recv
                self.stats['network_sent_mb'] = sent_bytes / 1024 / 1024
                self.stats['network_recv_mb'] = recv_bytes / 1024 / 1024
            self._prev_network_io = net_io
        except Exception:
            pass
        
        # Calcular RPS (requests por segundo)
        current_time = time.time()
        current_requests = self.stats['total_requests']
        # Limpar samples antigos (> 1 minuto)
        cutoff_time = current_time - 60
        self.history['request_times'] = [
            t for t in self.history['request_times'] if t > cutoff_time
        ]
        # Adicionar samples para requests recentes
        requests_diff = current_requests - self._last_request_count
        for _ in range(max(0, requests_diff)):
            self.history['request_times'].append(current_time)
        self._last_request_count = current_requests
        # RPS = requests no último minuto / 60
        rps = len(self.history['request_times']) / 60.0
        self.stats['rps_current'] = rps
        self.stats['rps_peak'] = max(self.stats.get('rps_peak', 0), rps)
        
        # Calcular percentis de latência
        if self.history['latency_samples']:
            sorted_latencies = sorted(self.history['latency_samples'])
            n = len(sorted_latencies)
            p95_idx = int(n * 0.95)
            p99_idx = int(n * 0.99)
            self.stats['latency_p95_ms'] = sorted_latencies[min(p95_idx, n-1)]
            self.stats['latency_p99_ms'] = sorted_latencies[min(p99_idx, n-1)]
        
        self.stats['memory_mb'] = memory_mb
        self.stats['cpu_percent'] = cpu_percent
        self.stats['threads'] = process.num_threads()
        self.stats['connections'] = len(process.connections())
        
        # Adicionar ao histórico
        self.history['memory_samples'].append(self.stats['memory_mb'])
        self.history['cpu_samples'].append(cpu_percent)
        
        # Manter apenas últimos 60 samples (5 minutos) para CPU/Memória
        if len(self.history['memory_samples']) > 60:
            self.history['memory_samples'].pop(0)
        if len(self.history['cpu_samples']) > 60:
            self.history['cpu_samples'].pop(0)
        
        # Manter últimos 300 samples de latência (5 minutos a 1 sample/seg)
        if len(self.history['latency_samples']) > 300:
            self.history['latency_samples'].pop(0)
            
        # Calcular throughput do batch (sinais/segundo)
        current_batch_saved = self.stats['batch_signals_saved']
        batch_diff = current_batch_saved - getattr(self, '_last_batch_count', 0)
        if batch_diff > 0:
            self.history['batch_times'].append((current_time, batch_diff))
        self._last_batch_count = current_batch_saved
        # Limpar batch times antigos (> 1 minuto)
        self.history['batch_times'] = [
            (t, c) for t, c in self.history['batch_times'] if current_time - t < 60
        ]
        # Throughput = total no último minuto / 60
        total_batch_last_min = sum(c for t, c in self.history['batch_times'])
        self.stats['batch_throughput'] = total_batch_last_min / 60.0
            
        # Tempo de atividade
        if not hasattr(self, '_start_time'):
            self._start_time = time.time()
        uptime_seconds = time.time() - self._start_time
        self.stats['uptime'] = self._format_uptime(uptime_seconds)
        
        # Sincronizar métricas de mensagens WebSocket das variáveis globais
        global _ws_messages_sent, _ws_messages_recv
        self.stats['ws_messages_sent'] = _ws_messages_sent
        self.stats['ws_messages_recv'] = _ws_messages_recv
        
        # Tentar coletar métricas de reconexões do connection_manager
        try:
            from services.data_collector.realtime import data_collector
            if hasattr(data_collector, 'connection_manager') and data_collector.connection_manager:
                cm = data_collector.connection_manager
                # Contar reconexões - verificar atributos existentes
                reconnections = 0
                for conn_id, conn in cm.connections.items():
                    # Verificar se é uma conexão que foi reconectada
                    if hasattr(conn, '_reconnect_count'):
                        reconnections += conn._reconnect_count
                    elif hasattr(conn, 'reconnect_count'):
                        reconnections += conn.reconnect_count
                    # Verificar no reconnection_manager também
                    if hasattr(data_collector, 'reconnection_manager') and data_collector.reconnection_manager:
                        rm = data_collector.reconnection_manager
                        if hasattr(rm, '_reconnect_counts') and conn_id in rm._reconnect_counts:
                            reconnections += rm._reconnect_counts[conn_id]
                
                self.stats['ws_reconnections'] = reconnections
                logger.debug(f"[PerformanceMonitor] Reconexões contadas: {reconnections}")
                
                # Última reconexão
                last_reconnect = None
                for conn in cm.connections.values():
                    if hasattr(conn, 'last_reconnect_time') and conn.last_reconnect_time:
                        if last_reconnect is None or conn.last_reconnect_time > last_reconnect:
                            last_reconnect = conn.last_reconnect_time
                if last_reconnect:
                    self.stats['ws_last_reconnect_time'] = last_reconnect.strftime("%H:%M:%S")
        except Exception as e:
            logger.debug(f"[PerformanceMonitor] Erro ao coletar reconexões: {e}")
        
        # Tentar coletar métricas de ativos e dados
        try:
            from services.data_collector.realtime import data_collector
            from services.pocketoption.constants import ASSETS
            
            # Usar ASSETS importado diretamente do módulo
            if ASSETS:
                assets_count = len(ASSETS)
                self.stats['assets_available'] = assets_count
                logger.debug(f"[PerformanceMonitor] Ativos disponíveis: {assets_count}")
            
            # Contar ativos com dados
            assets_with_data = 0
            stale_assets = 0
            max_delay_ms = 0
            total_delay_ms = 0
            delay_count = 0
            
            if hasattr(data_collector, '_candle_buffers') and data_collector._candle_buffers:
                now = datetime.now(timezone.utc)
                logger.debug(f"[PerformanceMonitor] _candle_buffers existe com {len(data_collector._candle_buffers)} ativos")
                for asset, buffers in data_collector._candle_buffers.items():
                    has_data = False
                    logger.debug(f"[PerformanceMonitor] Verificando {asset}: {len(buffers)} timeframes")
                    for tf, buffer in buffers.items():
                        if buffer and len(buffer) > 0:
                            has_data = True
                            logger.debug(f"[PerformanceMonitor]   {asset}@{tf}s tem {len(buffer)} candles")
                            # Verificar atraso do último candle
                            try:
                                last_candle = buffer[-1]
                                logger.debug(f"[PerformanceMonitor]   Tipo do candle: {type(last_candle)}")
                                # Tentar diferentes formas de obter o timestamp
                                candle_ts = None
                                if isinstance(last_candle, dict):
                                    candle_ts = last_candle.get('timestamp') or last_candle.get('time')
                                    logger.debug(f"[PerformanceMonitor]   Dict timestamp: {candle_ts}")
                                elif hasattr(last_candle, 'timestamp'):
                                    candle_ts = last_candle.timestamp
                                    logger.debug(f"[PerformanceMonitor]   Obj timestamp: {candle_ts}")
                                elif hasattr(last_candle, 'time'):
                                    candle_ts = last_candle.time
                                    logger.debug(f"[PerformanceMonitor]   Obj time: {candle_ts}")
                                
                                if candle_ts:
                                    delay = 0
                                    if isinstance(candle_ts, (int, float)):
                                        # Timestamp em segundos
                                        delay = (now.timestamp() - candle_ts) * 1000
                                    elif isinstance(candle_ts, datetime):
                                        delay = (now - candle_ts).total_seconds() * 1000
                                    max_delay_ms = max(max_delay_ms, delay)
                                    total_delay_ms += delay
                                    delay_count += 1
                                    logger.debug(f"[PerformanceMonitor]   Delay: {delay:.0f}ms")
                                    # Se atraso > 30 segundos = stale
                                    if delay > 30000:
                                        stale_assets += 1
                            except Exception as candle_err:
                                logger.debug(f"[PerformanceMonitor] Erro ao processar candle {asset}@{tf}s: {candle_err}")
                            break
                    if has_data:
                        assets_with_data += 1
                
                self.stats['assets_with_data'] = assets_with_data
                self.stats['stale_assets_count'] = stale_assets
                self.stats['data_delay_max_ms'] = max_delay_ms
                self.stats['data_delay_avg_ms'] = total_delay_ms / delay_count if delay_count > 0 else 0
                logger.debug(f"[PerformanceMonitor] Ativos com dados: {assets_with_data}, Stale: {stale_assets}, Delay max: {max_delay_ms:.0f}ms")
        except Exception as e:
            logger.debug(f"[PerformanceMonitor] Erro ao coletar métricas de ativos: {e}")
        
        # Tentar coletar métricas de WebSocket do connection_manager
        try:
            from services.data_collector.realtime import data_collector
            if hasattr(data_collector, 'connection_manager') and data_collector.connection_manager:
                cm = data_collector.connection_manager
                active_ws = sum(1 for c in cm.connections.values() if c.is_connected)
                self.stats['user_connections'] = active_ws
                self.stats['ws_connections'] = active_ws
        except Exception:
            pass
        
        # Tentar coletar conexões de monitoramento (payout + ativos)
        try:
            from services.data_collector.realtime import data_collector
            monitoring_connections = 0
            
            # Contar payout_client se estiver conectado
            if hasattr(data_collector, 'payout_client') and data_collector.payout_client:
                if hasattr(data_collector.payout_client, 'is_connected') and data_collector.payout_client.is_connected:
                    monitoring_connections += 1
            
            # Contar ativos_clients conectados
            if hasattr(data_collector, 'ativos_clients') and data_collector.ativos_clients:
                for client in data_collector.ativos_clients:
                    if hasattr(client, 'is_connected') and client.is_connected:
                        monitoring_connections += 1
            
            self.stats['monitoring_connections'] = monitoring_connections
            # Adicionar ao total de conexões WS
            self.stats['ws_connections'] += monitoring_connections
        except Exception:
            pass
        
        # Tentar coletar número de contas ativas
        try:
            from services.data_collector.realtime import data_collector
            if hasattr(data_collector, 'connection_manager') and data_collector.connection_manager:
                self.stats['active_accounts'] = len(data_collector.connection_manager.connections)
        except Exception:
            pass
        try:
            from services.data_collector.realtime import data_collector
            if hasattr(data_collector, 'batch_signal_saver') and data_collector.batch_signal_saver:
                bs = data_collector.batch_signal_saver
                self.stats['batch_signals_queued'] = len(bs._pending_signals)
        except Exception:
            pass
        
        # Tentar coletar métricas de agregação
        try:
            from services.aggregation_job import aggregation_job
            if hasattr(aggregation_job, 'last_run'):
                self.stats['aggregation_last_run'] = aggregation_job.last_run
            if hasattr(aggregation_job, 'is_running'):
                self.stats['aggregation_status'] = 'running' if aggregation_job.is_running else 'idle'
        except Exception:
            pass
        
    def _format_uptime(self, seconds: float) -> str:
        """Formatar uptime em HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    async def _write_dashboard(self):
        """Escrever dashboard no arquivo"""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # Calcular médias móveis
        avg_memory = sum(self.history['memory_samples']) / len(self.history['memory_samples']) if self.history['memory_samples'] else 0
        avg_cpu = sum(self.history['cpu_samples']) / len(self.history['cpu_samples']) if self.history['cpu_samples'] else 0
        
        # Taxa de sucesso de requisições
        total_req = self.stats['total_requests']
        success_rate = (self.stats['successful_requests'] / total_req * 100) if total_req > 0 else 0
        
        # Cache hit rate
        total_cache = self.stats['cache_hits'] + self.stats['cache_misses']
        cache_hit_rate = (self.stats['cache_hits'] / total_cache * 100) if total_cache > 0 else 0
        
        # DEBUG: Log do caminho do arquivo
        abs_path = self.log_file.absolute()
        logger.debug("[PerformanceMonitor] Escrevendo dashboard em: {}", abs_path)
        
        dashboard = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    TUNESTRADE PERFORMANCE DASHBOARD                          ║
║                    Atualizado: {now}                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─ [SISTEMA & RECURSOS] ──────────────────────────────────────────────────────┐
│ Uptime:           {self.stats['uptime']:>20}                                    │
│ Memória Atual:    {self.stats['memory_mb']:>6.1f} MB                                                    │
│ Memória Média:    {avg_memory:>6.1f} MB (últimos 5min)                                              │
│ CPU Atual:        {self.stats['cpu_percent']:>6.1f}%                                                     │
│ CPU Média:        {avg_cpu:>6.1f}% (últimos 5min)                                                     │
│ Threads:          {self.stats['threads']:>3}                                                            │
│ Disco Uso:        {self.stats['disk_usage_percent']:>6.1f}%                                                    │
│ Disco I/O:        ↓{self.stats['disk_read_mb']:>6.2f} MB ↑{self.stats['disk_write_mb']:>6.2f} MB                                                │
│ Network I/O:      ↓{self.stats['network_recv_mb']:>6.2f} MB ↑{self.stats['network_sent_mb']:>6.2f} MB                                                │
│ Load Average:      {self.stats['load_avg_1m']:>5.2f} / {self.stats['load_avg_5m']:>5.2f} / {self.stats['load_avg_15m']:>5.2f}                                          │
│ Swap:             {self.stats['swap_used_mb']:>6.1f} / {self.stats['swap_total_mb']:>6.1f} MB                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [API & LATÊNCIA] ──────────────────────────────────────────────────────────┐
│ Total Requisições:     {self.stats['total_requests']:>6}                                                │
│ Sucessos:              {self.stats['successful_requests']:>6} ({success_rate:>5.1f}%)                                      │
│ Falhas:                {self.stats['failed_requests']:>6}                                                │
│ Erros HTTP 4xx:       {self.stats['http_4xx_errors']:>6}                                                │
│ Erros HTTP 5xx:       {self.stats['http_5xx_errors']:>6}                                                │
│ RPS Atual:            {self.stats['rps_current']:>6.1f}/s                                                │
│ RPS Pico:             {self.stats['rps_peak']:>6.1f}/s                                                │
│ Latência Média:        {self.stats['avg_latency_ms']:>6.1f} ms                                                │
│ Latência P95:          {self.stats['latency_p95_ms']:>6.1f} ms                                                │
│ Latência P99:          {self.stats['latency_p99_ms']:>6.1f} ms                                                │
│ Latência Máxima:        {self.stats['max_latency_ms']:>6.1f} ms                                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [CONEXÕES & REDE] ─────────────────────────────────────────────────────────┐
│ Conexões de Usuários:     {self.stats['user_connections']:>3}                                                            │
│ Conexões de Monitoramento:  {self.stats['monitoring_connections']:>3}                                                 │
│ Total Conexões WS:        {self.stats['ws_connections']:>3}                                                            │
│ Contas Ativas:            {self.stats['active_accounts']:>3}                                                            │
│ Mensagens WS Enviadas:    {self.stats['ws_messages_sent']:>8}                                                │
│ Mensagens WS Recebidas:   {self.stats['ws_messages_recv']:>8}                                                │
│ Reconexões:               {self.stats['ws_reconnections']:>8}                                                │
│ Latência Corretora:       {self.stats['broker_latency_ms']:>6.1f} ms                                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [TRADES & SINAIS] ─────────────────────────────────────────────────────────┐
│ Trades Executados:     {self.stats['trades_executed']:>6}                                                │
│ Trades Pendentes:      {self.stats['trades_pending']:>6}                                                │
│ Taxa Sucesso Trades:   {self.stats['trades_success_rate']:>6.1f}%                                               │
│ Sinais Gerados:        {self.stats['signals_generated']:>6}                                                │
│ Sinais Executados:     {self.stats['signals_executed']:>6}                                                │
│ Sinais Baixa Conf.:    {self.stats['signals_low_confidence']:>6}                                                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [BANCO DE DADOS] ────────────────────────────────────────────────────────────┐
│ Queries Executadas:     {self.stats['db_queries']:>6}                                                │
│   ├─ Consultas (SELECT): {self.stats['db_selects']:>6}                                                │
│   ├─ Inserções (INSERT): {self.stats['db_inserts']:>6}                                                │
│   ├─ Atualizações (UPD): {self.stats['db_updates']:>6}                                                │
│   └─ Deleções (DELETE):  {self.stats['db_deletes']:>6}                                                │
│ Erros DB:               {self.stats['db_errors']:>6}                                                │
│ Queries Lentas (>1s):   {self.stats['db_slow_queries']:>6}                                                │
│ Tempo Médio Query:      {self.stats['db_avg_time_ms']:>6.1f} ms                                                │
│ Tempo Total Queries:    {self.stats['db_total_time_ms']:>8.1f} ms                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [PROCESSAMENTO & OTIMIZAÇÕES] ─────────────────────────────────────────────┐
│ Cache Hits:            {self.stats['cache_hits']:>6}                                                │
│ Cache Misses:          {self.stats['cache_misses']:>6}                                                │
│ Cache Hit Rate:        {cache_hit_rate:>6.1f}%                                               │
│ Batch Fila:            {self.stats['batch_signals_queued']:>6}                                                │
│ Batch Salvos:          {self.stats['batch_signals_saved']:>6}                                                │
│ Batch Erros:           {self.stats['batch_save_errors']:>6}                                                │
│ Batch Tempo Médio:     {self.stats['batch_avg_time_ms']:>6.1f} ms                                                │
│ Batch Throughput:      {self.stats['batch_throughput']:>6.1f} sinais/s                                          │
│ Batch Último Save:     {self.stats['batch_last_save_time'] or 'Nunca':>12}                                      │
│ Agregação Última:      {self.stats['aggregation_last_run'] or 'Nunca':>20}                                    │
│ Agregação Status:      {self.stats['aggregation_status']:>12}                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ [DADOS & ATIVOS] ──────────────────────────────────────────────────────────┐
│ Ativos Disponíveis:     {self.stats['assets_available']:>4}                                                │
│ Ativos com Dados:       {self.stats['assets_with_data']:>4}                                                │
│ Ativos Desatualizados:  {self.stats['stale_assets_count']:>4}                                                │
│ Atraso Máximo:          {self.stats['data_delay_max_ms']:>6.0f} ms                                               │
│ Atraso Médio:           {self.stats['data_delay_avg_ms']:>6.0f} ms                                               │
└─────────────────────────────────────────────────────────────────────────────┘


"""
        # Escrever no arquivo (sobrescreve a cada vez)
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(dashboard)
            logger.debug("[PerformanceMonitor] Dashboard escrito com sucesso: {} bytes", len(dashboard))
        except Exception as e:
            logger.error("[PerformanceMonitor] ERRO ao escrever arquivo {}: {}", self.log_file, e)
            
    # Métodos para atualizar métricas externamente
    def record_request(self, latency_ms: float, success: bool = True, endpoint: str = None, status_code: int = None):
        """Registrar uma requisição com endpoint e status code"""
        self.stats['total_requests'] += 1
        if success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1
            
        # Contabilizar erros HTTP por categoria
        if status_code:
            if 400 <= status_code < 500:
                self.stats['http_4xx_errors'] += 1
            elif status_code >= 500:
                self.stats['http_5xx_errors'] += 1
            
        # Atualizar latência média
        n = self.stats['successful_requests']
        if n > 0:
            self.stats['avg_latency_ms'] = (
                (self.stats['avg_latency_ms'] * (n-1) + latency_ms) / n
            )
        self.stats['max_latency_ms'] = max(self.stats['max_latency_ms'], latency_ms)
        
        # Adicionar ao histórico de latências para percentis
        self.history['latency_samples'].append(latency_ms)
        
        # Track endpoint latencies (top 5 lentos)
        if endpoint:
            if endpoint not in self.stats['endpoint_latencies']:
                self.stats['endpoint_latencies'][endpoint] = {'count': 0, 'avg_latency': 0.0, 'max_latency': 0.0}
            ep_stats = self.stats['endpoint_latencies'][endpoint]
            ep_stats['count'] += 1
            ep_stats['avg_latency'] = (ep_stats['avg_latency'] * (ep_stats['count'] - 1) + latency_ms) / ep_stats['count']
            ep_stats['max_latency'] = max(ep_stats['max_latency'], latency_ms)
        
    def record_ws_connection(self, count: int):
        """Atualizar contagem de conexões WS"""
        self.stats['ws_connections'] = count
        
    def record_ws_message(self, sent: bool = True):
        """Registrar mensagem WS - sincroniza com variáveis globais"""
        global _ws_messages_sent, _ws_messages_recv
        if sent:
            _ws_messages_sent += 1
            self.stats['ws_messages_sent'] = _ws_messages_sent
        else:
            _ws_messages_recv += 1
            self.stats['ws_messages_recv'] = _ws_messages_recv
            
    def record_trade(self, success: bool = True):
        """Registrar trade"""
        self.stats['trades_executed'] += 1
        if success:
            self.stats['trades_success_rate'] = (
                (self.stats['trades_success_rate'] * (self.stats['trades_executed'] - 1) + 100) 
                / self.stats['trades_executed']
            )
            
    def record_signal(self, executed: bool = False, low_confidence: bool = False):
        """Registrar sinal"""
        self.stats['signals_generated'] += 1
        if executed:
            self.stats['signals_executed'] += 1
        if low_confidence:
            self.stats['signals_low_confidence'] += 1
            
    def record_db_query(self, time_ms: float, error: bool = False, query_type: str = 'select', pool_active: int = 0, pool_available: int = 0, error_message: str = None):
        """Registrar query de banco com tipo (select, insert, update, delete)"""
        self.stats['db_queries'] += 1
        if error:
            self.stats['db_errors'] += 1
            # Logar erro no arquivo de errors
            if error_message:
                logger.error(f"[DB ERROR] Query {query_type} falhou: {error_message}")
            else:
                logger.error(f"[DB ERROR] Query {query_type} falhou (tempo: {time_ms:.1f}ms)")
        
        # Contabilizar por tipo
        query_type = query_type.lower()
        if query_type == 'select':
            self.stats['db_selects'] += 1
        elif query_type == 'insert':
            self.stats['db_inserts'] += 1
        elif query_type == 'update':
            self.stats['db_updates'] += 1
        elif query_type == 'delete':
            self.stats['db_deletes'] += 1
        
        # Atualizar tempo médio
        n = self.stats['db_queries']
        self.stats['db_avg_time_ms'] = (
            (self.stats['db_avg_time_ms'] * (n-1) + time_ms) / n
        )
        
        # Acumular tempo total
        self.stats['db_total_time_ms'] += time_ms
        
        # Contar queries lentas (>1000ms)
        if time_ms > 1000:
            self.stats['db_slow_queries'] += 1
            
        # Atualizar pool info se fornecido
        if pool_active > 0:
            self.stats['db_pool_active'] = pool_active
        if pool_available > 0:
            self.stats['db_pool_available'] = pool_available
        
    def record_cache(self, hit: bool = True, memory_mb: float = None):
        """Registrar acesso ao cache com memória opcional"""
        if hit:
            self.stats['cache_hits'] += 1
        else:
            self.stats['cache_misses'] += 1
            
        if memory_mb is not None:
            self.stats['cache_memory_mb'] = memory_mb
            
    def record_batch(self, queued: int = 0, saved: int = 0, errors: int = 0, time_ms: float = None):
        """Registrar operação de batch com tempo opcional"""
        self.stats['batch_signals_queued'] = queued
        self.stats['batch_signals_saved'] += saved
        self.stats['batch_save_errors'] += errors
        
        # Registrar tempo médio de batch
        if time_ms is not None and saved > 0:
            current_saved = self.stats['batch_signals_saved']
            if current_saved > 0:
                # Média móvel do tempo de batch
                self.stats['batch_avg_time_ms'] = (
                    (self.stats['batch_avg_time_ms'] * (current_saved - saved) + time_ms) / current_saved
                )
            else:
                self.stats['batch_avg_time_ms'] = time_ms
            self.stats['batch_last_save_time'] = datetime.now(timezone.utc).strftime("%H:%M:%S")
        
    def record_aggregation(self, status: str = 'completed'):
        """Registrar execução de agregação"""
        self.stats['aggregation_last_run'] = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.stats['aggregation_status'] = status


# Instância global
performance_monitor = PerformanceMonitor()
