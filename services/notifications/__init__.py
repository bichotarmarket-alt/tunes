"""Notifications service

Exporta o servico de notificacao do Telegram.
Para usar a versao otimizada V2, importe de telegram_v2.
"""

# Importar servico V2 (otimizado) como padrao
from .telegram_v2 import telegram_service_v2, telegram_service

# Manter compatibilidade - telegram_service aponta para V2 via adapter
__all__ = [
    'telegram_service',      # Instancia principal (agora V2 via adapter)
    'telegram_service_v2',   # Instancia V2 explicita
]

# Nota sobre migracao:
# O servico telegram_service agora usa a implementacao V2 atraves do adapter.
# A API permanece compativel - todos os metodos antigos funcionam.
# Para acessar novos recursos (health_check, validate_token), use telegram_service_v2.

