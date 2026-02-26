"""
Script para adicionar os 10 novos indicadores técnicos ao banco de dados

Este script adiciona os seguintes indicadores à tabela indicators:
1. Parabolic SAR
2. Ichimoku Cloud
3. Money Flow Index
4. Average Directional Index (ADX)
5. Keltner Channels
6. Donchian Channels
7. Heiken Ashi
8. Pivot Points
9. Supertrend
10. Fibonacci Retracement
"""

import sqlite3
import json


def add_new_indicators():
    """Adiciona os 10 novos indicadores ao banco de dados"""
    
    # Conectar ao banco de dados
    conn = sqlite3.connect('autotrade.db')
    cursor = conn.cursor()
    
    # Lista de novos indicadores
    new_indicators = [
        {
            'name': 'Parabolic SAR',
            'type': 'parabolic_sar',
            'description': 'Parabolic Stop and Reverse - trend reversal indicator',
            'parameters': json.dumps({'initial_af': 0.02, 'max_af': 0.2, 'step_af': 0.02}),
            'is_default': 1
        },
        {
            'name': 'Ichimoku Cloud',
            'type': 'ichimoku_cloud',
            'description': 'Ichimoku Kinko Hyo - comprehensive trend indicator',
            'parameters': json.dumps({'tenkan_period': 9, 'kijun_period': 26, 'senkou_span_b_period': 52, 'chikou_shift': 26}),
            'is_default': 1
        },
        {
            'name': 'Money Flow Index',
            'type': 'money_flow_index',
            'description': 'MFI - momentum indicator with volume',
            'parameters': json.dumps({'period': 14}),
            'is_default': 1
        },
        {
            'name': 'ADX',
            'type': 'average_directional_index',
            'description': 'Average Directional Index - trend strength indicator',
            'parameters': json.dumps({'period': 14}),
            'is_default': 1
        },
        {
            'name': 'Keltner Channels',
            'type': 'keltner_channels',
            'description': 'Keltner Channels - volatility bands',
            'parameters': json.dumps({'ema_period': 20, 'atr_period': 20, 'multiplier': 2.0}),
            'is_default': 1
        },
        {
            'name': 'Donchian Channels',
            'type': 'donchian_channels',
            'description': 'Donchian Channels - price channel indicator',
            'parameters': json.dumps({'period': 20}),
            'is_default': 1
        },
        {
            'name': 'Heiken Ashi',
            'type': 'heiken_ashi',
            'description': 'Heiken Ashi - filtered price candles',
            'parameters': json.dumps({}),
            'is_default': 1
        },
        {
            'name': 'Pivot Points',
            'type': 'pivot_points',
            'description': 'Pivot Points - support and resistance levels',
            'parameters': json.dumps({}),
            'is_default': 1
        },
        {
            'name': 'Supertrend',
            'type': 'supertrend',
            'description': 'Supertrend - trend following indicator',
            'parameters': json.dumps({'atr_period': 10, 'multiplier': 3.0}),
            'is_default': 1
        },
        {
            'name': 'Fibonacci Retracement',
            'type': 'fibonacci_retracement',
            'description': 'Fibonacci Retracement - support/resistance levels',
            'parameters': json.dumps({'lookback': 50}),
            'is_default': 1
        }
    ]
    
    # Adicionar indicadores ao banco de dados
    added_count = 0
    for ind in new_indicators:
        cursor.execute('SELECT id FROM indicators WHERE name = ?', (ind['name'],))
        if cursor.fetchone() is None:
            # Gerar ID único
            import uuid
            indicator_id = str(uuid.uuid4())
            
            cursor.execute('''
                INSERT INTO indicators (id, name, type, description, parameters, is_default)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (indicator_id, ind['name'], ind['type'], ind['description'], ind['parameters'], ind['is_default']))
            print(f'Adicionado: {ind["name"]}')
            added_count += 1
        else:
            print(f'Já existe: {ind["name"]}')
    
    conn.commit()
    
    # Verificar todos os indicadores
    cursor.execute('SELECT id, name, type, is_default FROM indicators ORDER BY name')
    indicators = cursor.fetchall()
    
    print(f'\nTotal de indicadores no banco de dados: {len(indicators)}')
    print('Indicadores:')
    for ind in indicators:
        print(f'  - {ind[1]} ({ind[2]}) - is_default={ind[3]}')
    
    conn.close()
    
    print(f'\n{added_count} novos indicadores adicionados com sucesso!')
    print('\nOs indicadores agora aparecerão na tela de criar/editar estratégias.')
    print('Os parâmetros podem ser alterados na tela de criar/editar estratégias.')


if __name__ == '__main__':
    add_new_indicators()
