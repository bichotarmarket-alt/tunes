"""
Script para atualizar o token do ngrok no .env
"""
import os
from pathlib import Path

def update_ngrok_token(new_token: str):
    """Atualiza o NGROK_TOKEN no arquivo .env"""
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Arquivo .env não encontrado")
        return False
    
    # Ler conteúdo atual do .env
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se NGROK_TOKEN existe
    if 'NGROK_TOKEN=' not in content:
        print("⚠️  NGROK_TOKEN não encontrado no .env")
        print("Você pode adicionar manualmente:")
        print(f"NGROK_TOKEN={new_token}")
        return False
    
    # Substituir o token
    lines = content.split('\n')
    updated_lines = []
    for line in lines:
        if line.startswith('NGROK_TOKEN='):
            updated_lines.append(f'NGROK_TOKEN={new_token}')
        else:
            updated_lines.append(line)
    
    # Escrever de volta
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(updated_lines))
    
    print(f"✓ NGROK_TOKEN atualizado no .env")
    print(f"  Novo token: {new_token[:10]}...{new_token[-10:]}")
    return True

if __name__ == "__main__":
    import sys
    
    # Token fornecido pelo usuário
    new_token = "39LwGmVglUTpHs7UcfGEuF57a65_4jZin6AMR6oxh73dkzy6z"
    
    if len(sys.argv) > 1:
        new_token = sys.argv[1]
    
    update_ngrok_token(new_token)
