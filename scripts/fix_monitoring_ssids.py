"""
Script para corrigir o formato do SSID nas contas de monitoramento
Execute: python scripts/fix_monitoring_ssids.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from sqlalchemy import text
from core.database import get_db_context

async def fix_monitoring_ssids():
    """Corrigir formato do SSID nas contas de monitoramento"""
    
    print("=" * 60)
    print("CORREÇÃO DO FORMATO SSID")
    print("=" * 60)
    
    async with get_db_context() as db:
        try:
            # Buscar todas as contas de monitoramento
            result = await db.execute(
                text("""
                    SELECT id, ssid, account_type, name
                    FROM monitoring_accounts
                    WHERE is_active = 1
                """)
            )
            rows = result.fetchall()
            
            print(f"\nEncontradas {len(rows)} contas ativas")
            print("-" * 60)
            
            fixed_count = 0
            
            for row in rows:
                id_, ssid, account_type, name = row
                
                print(f"\nVerificando: {name} ({account_type})")
                
                # Verificar se o SSID está em formato de mensagem Socket.IO
                if ssid and ssid.startswith('42["auth",'):
                    print(f"  SSID em formato incorreto detectado")
                    print(f"  SSID atual: {ssid[:60]}...")
                    
                    try:
                        # Extrair o JSON da mensagem Socket.IO
                        # Formato: 42["auth",{...}]
                        # Precisamos extrair o segundo argumento
                        
                        # Remover o prefixo '42[' e o sufixo ']'
                        inner = ssid[3:-1]  # Remove '42[' do início e ']' do final
                        
                        # Parse como array JSON
                        parts = json.loads(inner)
                        
                        if len(parts) >= 2 and isinstance(parts[1], dict):
                            auth_data = parts[1]
                            session_id = auth_data.get('session')
                            
                            if session_id:
                                # Atualizar o SSID com apenas o session ID
                                await db.execute(
                                    text("""
                                        UPDATE monitoring_accounts
                                        SET ssid = :ssid
                                        WHERE id = :id
                                    """),
                                    {"ssid": session_id, "id": id_}
                                )
                                await db.commit()
                                
                                print(f"  ✅ SSID corrigido para: {session_id}")
                                fixed_count += 1
                            else:
                                print(f"  ❌ Session ID não encontrado nos dados")
                        else:
                            print(f"  ❌ Formato inesperado nos dados de autenticação")
                            
                    except Exception as e:
                        print(f"  ❌ Erro ao processar SSID: {e}")
                        
                        # Tentar extrair manualmente com regex como fallback
                        import re
                        match = re.search(r'"session":"([^"]+)"', ssid)
                        if match:
                            session_id = match.group(1)
                            await db.execute(
                                text("""
                                    UPDATE monitoring_accounts
                                    SET ssid = :ssid
                                    WHERE id = :id
                                """),
                                {"ssid": session_id, "id": id_}
                            )
                            await db.commit()
                            
                            print(f"  ✅ SSID corrigido (via regex) para: {session_id}")
                            fixed_count += 1
                        else:
                            print(f"  ❌ Não foi possível extrair session ID")
                else:
                    print(f"  ✅ SSID já está no formato correto: {ssid[:30] if ssid else 'VAZIO'}...")
            
            print("\n" + "=" * 60)
            print(f"✅ Correção concluída! {fixed_count} contas corrigidas.")
            print("=" * 60)
            print("\nReinicie o sistema para aplicar as mudanças.")
            
        except Exception as e:
            print(f"❌ Erro ao corrigir SSIDs: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_monitoring_ssids())
