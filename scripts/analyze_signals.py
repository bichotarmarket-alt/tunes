#!/usr/bin/env python3
"""
Script para analisar sinais gerados por indicadores no strategy_analysis.log
Conta quantos sinais cada indicador gerou para verificar se estão funcionando corretamente.
"""

import re
import sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime


def analyze_signals(log_file_path: str):
    """Analisa o arquivo de log e conta sinais por indicador."""
    
    # Estruturas para armazenar contagens
    signals_by_indicator = defaultdict(lambda: defaultdict(int))  # {indicator: {user: count}}
    total_signals_by_indicator = defaultdict(int)
    total_by_user = defaultdict(int)
    
    # Padrão regex para capturar sinais gerados
    # Exemplo: ✅ [USUÁRIO: Gabriel] [ESTRATÉGIA: AutoTrade-6586753b] Sinal gerado por zonas: sell | conf=1.00
    pattern = re.compile(
        r'\[USUÁRIO:\s+(\w+(?:\s+\w+)?(?:@\w+\.\w+)?)\].*?Sinal gerado por (\w+):\s*(buy|sell)'
    )
    
    # Também capturar o padrão anterior se existir
    pattern2 = re.compile(
        r'Sinal gerado por (\w+):\s*(buy|sell).*?USUÁRIO:\s*(\w+)'
    )
    
    print(f"\n{'='*80}")
    print(f"ANÁLISE DE SINAIS POR INDICADOR")
    print(f"Arquivo: {log_file_path}")
    print(f"{'='*80}\n")
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Arquivo não encontrado: {log_file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro ao ler arquivo: {e}")
        sys.exit(1)
    
    print(f"Total de linhas no log: {len(lines):,}\n")
    
    # Processar linhas
    for line_num, line in enumerate(lines, 1):
        # Tentar primeiro padrão
        match = pattern.search(line)
        if match:
            user = match.group(1).strip()
            indicator = match.group(2).strip().lower()
            direction = match.group(3).strip().lower()
            
            signals_by_indicator[indicator][user] += 1
            total_signals_by_indicator[indicator] += 1
            total_by_user[user] += 1
        
        # Verificar também indicadores que não geraram sinal (para debug)
        no_signal_pattern = re.compile(
            r'\[USUÁRIO:\s+(\w+(?:\s+\w+)?(?:@\w+\.\w+)?)\].*?Indicador (\w+) nao gerou sinal'
        )
        no_match = no_signal_pattern.search(line)
        if no_match:
            # Apenas registramos que o indicador foi processado, mas não gerou sinal
            pass
    
    # Resultados
    print(f"{'='*80}")
    print("RESUMO GERAL POR INDICADOR")
    print(f"{'='*80}\n")
    
    if not total_signals_by_indicator:
        print("[ERRO] Nenhum sinal encontrado no log!")
        return
    
    # Ordenar por total de sinais (decrescente)
    sorted_indicators = sorted(
        total_signals_by_indicator.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    print(f"{'Indicador':<25} {'Total Sinais':>12} {'Status':>20}")
    print(f"{'-'*25} {'-'*12} {'-'*20}")
    
    for indicator, total in sorted_indicators:
        if total >= 20:
            status = "[OK] EXCELENTE"
        elif total >= 10:
            status = "[OK] BOM"
        elif total > 0:
            status = "[ATENCAO] POUCOS"
        else:
            status = "[ERRO] ZERO"
        print(f"{indicator:<25} {total:>12} {status:>20}")
    
    print(f"\n{'='*80}")
    print("RESUMO POR USUÁRIO")
    print(f"{'='*80}\n")
    
    print(f"{'Usuário':<30} {'Total Sinais':>12}")
    print(f"{'-'*30} {'-'*12}")
    
    sorted_users = sorted(total_by_user.items(), key=lambda x: x[1], reverse=True)
    for user, total in sorted_users:
        print(f"{user:<30} {total:>12}")
    
    print(f"\n{'='*80}")
    print("DETALHAMENTO POR INDICADOR E USUÁRIO")
    print(f"{'='*80}\n")
    
    for indicator in sorted(total_signals_by_indicator.keys()):
        total = total_signals_by_indicator[indicator]
        print(f"\n[INDICADOR] {indicator.upper()} (Total: {total})")
        print(f"   {'Usuário':<30} {'Sinais':>10} {'% do Total':>12}")
        print(f"   {'-'*30} {'-'*10} {'-'*12}")
        
        user_counts = signals_by_indicator[indicator]
        sorted_user_counts = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        
        for user, count in sorted_user_counts:
            percentage = (count / total * 100) if total > 0 else 0
            print(f"   {user:<30} {count:>10} {percentage:>11.1f}%")
    
    # Alertas
    print(f"\n{'='*80}")
    print("ALERTAS")
    print(f"{'='*80}\n")
    
    alerts = []
    for indicator, total in sorted_indicators:
        if total == 0:
            alerts.append(f"[ERRO] {indicator}: ZERO sinais - INDICADOR NAO FUNCIONANDO!")
        elif total < 5:
            alerts.append(f"[ATENCAO] {indicator}: Apenas {total} sinais - MUITO POUCO")
        elif total < 10:
            alerts.append(f"[ATENCAO] {indicator}: {total} sinais - ABAIXO DO ESPERADO (min: 10)")
    
    if alerts:
        for alert in alerts:
            print(alert)
    else:
        print("[OK] Todos os indicadores estao gerando sinais adequadamente!")
    
    print(f"\n{'='*80}")
    print(f"Total de indicadores analisados: {len(total_signals_by_indicator)}")
    print(f"Total de sinais no período: {sum(total_signals_by_indicator.values())}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    # Verificar argumentos
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    else:
        # Tentar caminhos padrão
        possible_paths = [
            r"c:\Users\SOUZAS\Desktop\tunestrade\logs\strategy_analysis.log",
            r".\logs\strategy_analysis.log",
            r"./logs/strategy_analysis.log",
            "strategy_analysis.log"
        ]
        
        log_path = None
        for path in possible_paths:
            if Path(path).exists():
                log_path = path
                break
        
        if not log_path:
            print("❌ Arquivo de log não encontrado!")
            print("Uso: python analyze_signals.py <caminho_do_log>")
            sys.exit(1)
    
    analyze_signals(log_path)
