"""Utilitários para gerenciamento de cooldown com suporte a randomização."""
import random


def parse_cooldown(cooldown_value: str | int | None, default: int = 0) -> int:
    """
    Parse cooldown value e retorna o tempo em segundos.
    
    Formatos suportados:
    - "X-X" (ex: "5-10"): retorna valor aleatório entre min e max
    - "X" (ex: "300"): retorna valor fixo
    - Número (ex: 300): retorna valor fixo
    - None ou vazio: retorna valor default
    
    Args:
        cooldown_value: Valor do cooldown (string, int ou None)
        default: Valor padrão se cooldown_value for None ou vazio
        
    Returns:
        int: Tempo de cooldown em segundos
    """
    if cooldown_value is None:
        return default
    
    # Converter para string se for número
    cooldown_str = str(cooldown_value).strip()
    
    if not cooldown_str:
        return default
    
    # Verificar se está no formato X-X (min-max)
    if "-" in cooldown_str:
        try:
            parts = cooldown_str.split("-")
            if len(parts) == 2:
                min_val = int(parts[0].strip())
                max_val = int(parts[1].strip())
                
                # Validar que min < max
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                
                # Retornar valor aleatório entre min e max (inclusive)
                return random.randint(min_val, max_val)
        except (ValueError, AttributeError):
            pass
    
    # Tentar converter para número fixo
    try:
        return int(cooldown_str)
    except (ValueError, AttributeError):
        return default
