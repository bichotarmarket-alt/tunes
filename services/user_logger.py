"""
Logger de análise por usuário - Gera logs individuais para cada usuário com estratégia ativa
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger as main_logger


class UserAnalysisLogger:
    """
    Gerencia logs individuais de análise para cada usuário
    Arquivos são criados em logs/users/<nome_usuario>.txt
    Otimizado para reduzir flood de logs
    """

    def __init__(self):
        self.base_dir = Path("logs/users")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._active_loggers: Dict[str, Any] = {}  # Cache de handlers abertos
        
        # Rate limiting: { (username, asset): last_log_timestamp }
        self._last_indicator_log: Dict[tuple, float] = {}
        self._indicator_log_interval = 60  # Log de mesmo indicador só a cada 60s
        
        # Buffer de confluence para evitar log duplicado
        self._last_confluence_log: Dict[tuple, Dict] = {}
        self._confluence_log_interval = 30  # Log de confluence só a cada 30s
        
        # Contadores para estatísticas
        self._log_stats: Dict[str, int] = {
            'indicators_skipped': 0,
            'indicators_logged': 0,
            'confluence_skipped': 0,
            'confluence_logged': 0
        }

    def _is_system_account(self, username: str) -> bool:
        """Verifica se é uma conta de sistema (monitoramento, etc)"""
        if not username:
            return False
        system_patterns = [
            'ativos', 'payout', 'monitor', 'system', 'admin',
            'test', 'demo_system', 'bot'
        ]
        username_lower = username.lower()
        return any(pattern in username_lower for pattern in system_patterns)

    def _sanitize_username(self, username: str) -> str:
        """Sanitiza nome de usuário para nome de arquivo seguro"""
        # Remove caracteres especiais e espaços
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', username)
        # Remove underscores duplicados
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove underscores no início/fim
        sanitized = sanitized.strip('_')
        return sanitized.lower() if sanitized else "unknown_user"

    def _get_log_file_path(self, username: str) -> Path:
        """Retorna o caminho do arquivo de log para o usuário"""
        sanitized = self._sanitize_username(username)
        return self.base_dir / f"{sanitized}.txt"

    def log_signal_analysis(
        self,
        username: str,
        account_id: str,
        asset: str,
        strategy_name: str,
        signal_data: Dict[str, Any],
        indicators_data: Optional[Dict[str, Any]] = None
    ):
        """
        Registra análise de sinal completa para o usuário
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] ANÁLISE DE SINAL - {asset}",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Estratégia: {strategy_name}",
            f"Ativo: {asset}",
            f"",
            f"--- RESULTADO DA ANÁLISE ---",
            f"Direção: {signal_data.get('direction', 'HOLD')}",
            f"Confiança: {signal_data.get('confidence', 0):.4f}",
            f"Score: {signal_data.get('score', 0):.4f}",
        ]

        # Adicionar dados dos indicadores se disponíveis
        if indicators_data:
            lines.extend([
                f"",
                f"--- INDICADORES CALCULADOS ---",
            ])
            for indicator_name, data in indicators_data.items():
                signal = data.get('signal', 'NEUTRAL')
                confidence = data.get('confidence', 0)
                lines.append(f"  {indicator_name}: {signal} (conf={confidence:.2f})")

        lines.extend([
            f"",
            f"{'='*80}",
        ])

        # Escrever no arquivo (append mode)
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever log para {username}: {e}")

    def log_trade_execution(
        self,
        username: str,
        account_id: str,
        asset: str,
        strategy_name: str,
        trade_data: Dict[str, Any],
        result: Optional[str] = None
    ):
        """
        Registra execução de trade para o usuário
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        direction = trade_data.get('direction', 'UNKNOWN')
        amount = trade_data.get('amount', 0)
        duration = trade_data.get('duration', 0)
        order_id = trade_data.get('order_id', 'N/A')

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] EXECUÇÃO DE TRADE - {asset}",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Estratégia: {strategy_name}",
            f"Ativo: {asset}",
            f"",
            f"--- DETALHES DO TRADE ---",
            f"Direção: {direction}",
            f"Valor: ${amount:.2f}",
            f"Duração: {duration}s",
            f"Order ID: {order_id}",
        ]

        if result:
            result_emoji = "✅" if result == "win" else "❌" if result == "loss" else "⏳"
            lines.extend([
                f"",
                f"--- RESULTADO ---",
                f"{result_emoji} {result.upper()}",
            ])
        else:
            lines.extend([
                f"",
                f"--- STATUS ---",
                f"⏳ PENDENTE",
            ])

        lines.extend([
            f"",
            f"{'='*80}",
        ])

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever log de trade para {username}: {e}")

    def log_trade_result(
        self,
        username: str,
        account_id: str,
        asset: str,
        order_id: str,
        result: str,
        profit: Optional[float] = None,
        balance_before: Optional[float] = None,
        balance_after: Optional[float] = None
    ):
        """
        Registra resultado final de um trade
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result_emoji = "✅ WIN" if result == "win" else "❌ LOSS" if result == "loss" else "🤝 DRAW" if result == "draw" else "❓ UNKNOWN"

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] RESULTADO DO TRADE - {asset}",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Ativo: {asset}",
            f"Order ID: {order_id}",
            f"",
            f"--- RESULTADO FINAL ---",
            f"{result_emoji}",
        ]

        if profit is not None:
            profit_str = f"+${profit:.2f}" if profit > 0 else f"${profit:.2f}"
            lines.append(f"Lucro/Prejuízo: {profit_str}")

        if balance_before is not None and balance_after is not None:
            lines.extend([
                f"",
                f"--- SALDO ---",
                f"Antes: ${balance_before:.2f}",
                f"Depois: ${balance_after:.2f}",
                f"Variação: ${balance_after - balance_before:.2f}",
            ])

        lines.extend([
            f"",
            f"{'='*80}",
        ])

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever resultado para {username}: {e}")

    def log_strategy_params(
        self,
        username: str,
        account_id: str,
        strategy_name: str,
        params: Dict[str, Any]
    ):
        """
        Registra parâmetros da estratégia para o usuário
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] PARÂMETROS DA ESTRATÉGIA",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Estratégia: {strategy_name}",
            f"",
            f"--- CONFIGURAÇÃO ---",
        ]

        for key, value in params.items():
            lines.append(f"  {key}: {value}")

        lines.extend([
            f"",
            f"{'='*80}",
        ])

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever parâmetros para {username}: {e}")

    def _should_log_indicator(self, username: str, asset: str, indicator_name: str) -> bool:
        """Verifica se deve logar este indicador (rate limiting)"""
        import time
        key = (username, asset, indicator_name)
        current_time = time.time()
        last_time = self._last_indicator_log.get(key, 0)
        
        if current_time - last_time < self._indicator_log_interval:
            self._log_stats['indicators_skipped'] += 1
            return False
        
        self._last_indicator_log[key] = current_time
        self._log_stats['indicators_logged'] += 1
        return True

    def _should_log_confluence(self, username: str, asset: str, final_direction: str) -> bool:
        """Verifica se deve logar confluence (evita duplicados)"""
        import time
        key = (username, asset)
        current_time = time.time()
        last_log = self._last_confluence_log.get(key)
        
        if last_log:
            time_diff = current_time - last_log['time']
            same_direction = last_log['direction'] == final_direction
            
            # Só loga se passou tempo suficiente OU mudou a direção
            if time_diff < self._confluence_log_interval and same_direction:
                self._log_stats['confluence_skipped'] += 1
                return False
        
        self._last_confluence_log[key] = {
            'time': current_time,
            'direction': final_direction
        }
        self._log_stats['confluence_logged'] += 1
        return True

    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas de log para debug"""
        return self._log_stats.copy()

    def log_indicator_calculation(
        self,
        username: str,
        asset: str,
        indicator_name: str,
        values_count: int,
        values_type: str,
        parameters: Optional[Dict[str, Any]] = None
    ):
        """
        DESABILITADO: Não loga mais cálculos de indicadores
        """
        # SILENCIADO: Logs de cálculo de indicadores desabilitados
        pass

    def log_indicator_signal(
        self,
        username: str,
        asset: str,
        strategy_name: str,
        indicator_name: str,
        signal: str,
        confidence: float,
        result_details: Optional[Dict[str, Any]] = None
    ):
        """
        DESABILITADO: Não loga mais sinais individuais de indicadores
        """
        # SILENCIADO: Logs de sinais individuais desabilitados
        pass

    def log_indicator_no_signal(
        self,
        username: str,
        asset: str,
        indicator_name: str,
        reason: str = "sem condição de sinal"
    ):
        """
        DESABILITADO: Não loga indicadores sem sinal
        """
        pass

    def log_confluence_analysis(
        self,
        username: str,
        asset: str,
        buy_score: float,
        sell_score: float,
        buy_signals: int,
        sell_signals: int,
        buy_indicators: list,
        sell_indicators: list,
        final_direction: str,
        final_score: float,
        difference: Optional[float] = None
    ):
        """
        DESABILITADO: Não loga mais análise de confluence
        """
        # SILENCIADO: Logs de confluence desabilitados
        pass

    def log_cooldown(
        self,
        username: str,
        asset: str,
        remaining_time: float,
        expires_at: str
    ):
        """
        Registra quando um ativo está em cooldown - SILENCIADO (sem flood)
        """
        # SILENCIADO: Não logar cooldown no arquivo do usuário
        # Apenas logar no console principal (já feito em realtime.py)
        pass

    def log_final_signal(
        self,
        username: str,
        account_id: str,
        asset: str,
        strategy_name: str,
        direction: str,
        confidence: float,
        confluence_score: float,
        num_indicators: int
    ):
        """
        Registra SINAL FINAL gerado (quando vai ser usado para trade)
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        emoji = "🚀 BUY" if direction.upper() == "BUY" else "🔻 SELL" if direction.upper() == "SELL" else "➖ HOLD"
        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] SINAL GERADO - {emoji}",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Ativo: {asset}",
            f"Estratégia: {strategy_name}",
            f"",
            f"--- DETALHES DO SINAL ---",
            f"Direção: {direction}",
            f"Confiança: {confidence:.2f}",
            f"Confluence: {confluence_score:.2f}",
            f"Indicadores: {num_indicators}",
            f"{'='*80}",
        ]

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever sinal final para {username}: {e}")

    def log_strategy_activation(
        self,
        username: str,
        account_id: str,
        strategy_name: str,
        asset: str,
        timeframe: str,
        action: str = "activated"  # activated ou deactivated
    ):
        """
        Registra ativação ou desativação de estratégia
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        action_emoji = "🟢 ATIVADA" if action == "activated" else "🔴 DESATIVADA"
        action_text = "ativada" if action == "activated" else "desativada"

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] ESTRATÉGIA {action_emoji}",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Estratégia: {strategy_name}",
            f"Ativo: {asset}",
            f"Timeframe: {timeframe}",
            f"Ação: Estratégia {action_text}",
            f"{'='*80}",
        ]

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever ativação para {username}: {e}")

    def log_config_update(
        self,
        username: str,
        account_id: str,
        config_type: str,  # 'strategy', 'indicators', 'risk', etc
        changes: Dict[str, Any]
    ):
        """
        Registra atualização de configurações
        """
        # Ignorar contas de sistema
        if self._is_system_account(username):
            return

        log_file = self._get_log_file_path(username)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            f"\n{'='*80}",
            f"[{timestamp}] CONFIGURAÇÃO ATUALIZADA",
            f"{'='*80}",
            f"Usuário: {username}",
            f"Conta: {account_id[:8]}...",
            f"Tipo: {config_type}",
            f"",
            f"--- ALTERAÇÕES ---",
        ]

        for key, value in changes.items():
            lines.append(f"  {key}: {value}")

        lines.append(f"{'='*80}")

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            main_logger.error(f"[USER LOGGER] Erro ao escrever config para {username}: {e}")

    def get_user_log_path(self, username: str) -> Path:
        """Retorna o caminho do arquivo de log do usuário"""
        return self._get_log_file_path(username)


# Instância global
user_logger = UserAnalysisLogger()
