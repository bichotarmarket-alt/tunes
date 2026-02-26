# INSTALAÇÃO NO TERMUX - TUNESTRADE

## Problema: pandas/numpy requerem compilação pesada

### Solução 1: Usar repositório de wheels pré-compilados (RECOMENDADO)

```bash
# 1. Instalar dependências do sistema
pkg update && pkg upgrade -y
pkg install python python-pip git sqlite clang cmake pkg-config -y
pkg install libffi openssl libxml2 libxslt libpng libjpeg-turbo -y

# 2. Configurar repositório its-pointless (wheels pré-compilados para Termux)
pkg install tur-repo -y
pkg install python-numpy python-pandas -y

# 3. Criar ambiente virtual
python -m venv venv --system-site-packages
source venv/bin/activate

# 4. Instalar requirements (sem numpy/pandas que já estão no sistema)
pip install -r requirements.txt --no-deps
pip install fastapi uvicorn sqlalchemy aiosqlite alembic python-jose passlib python-multipart slowapi loguru websockets aiofiles requests httpx python-dotenv pytz python-telegram-bot pyngrok gspread oauth2client pytest pytest-asyncio orjson

# 5. Verificar instalação
python -c "import numpy; import pandas; print('OK')"
```

### Solução 2: Instalar sem pandas/numpy (versão mínima)

Se os indicadores não forem essenciais, use `requirements-termux.txt`:

```bash
pip install -r requirements-termux.txt
```

**Aviso**: Indicadores técnicos não funcionarão sem numpy/pandas.

### Solução 3: Compilar manualmente (demorado!)

```bash
# Instalar MESON e NINJA do Termux
pkg install meson ninja -y

# Configurar variáveis de ambiente para compilação
export CFLAGS="-Wno-error"
export LDFLAGS="-lm"

# Instalar numpy primeiro (sem dependências)
pip install --no-build-isolation numpy==2.3.3

# Depois pandas
pip install --no-build-isolation pandas==2.3.3

# Finalmente o resto
pip install -r requirements.txt
```

## Configuração do .env para Termux

```bash
# Copiar e editar
cp .env.example .env
nano .env
```

Configurações mínimas:
```env
ENVIRONMENT=development
DEBUG=true
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=sua-chave-de-32-caracteres-minimo
DATABASE_URL=sqlite+aiosqlite:///./autotrade.db
REDIS_ENABLED=false
DATA_COLLECTOR_ENABLED=false
TELEGRAM_ENABLED=false
NGROK_ENABLED=false
```

## Rodar o sistema

```bash
# Criar diretórios
mkdir -p logs data

# Iniciar
python run.py
```

## Troubleshooting

### Erro "No module named '_sqlite3'"
```bash
pkg install python sqlite
```

### Erro de permissão
```bash
termux-setup-storage
chmod +x run.py
```

### Memory Error na compilação
O Termux tem memória limitada. Use a Solução 1 com wheels pré-compilados.

### Erro "cannot find -lpython3.x"
```bash
export LDFLAGS="-lpython3.12"
```

## Dicas

1. **Use ambiente virtual** sempre para evitar conflitos
2. **Instale numpy/pandas do tur-repo** primeiro (muito mais rápido)
3. **Desative Redis** no .env (não funciona bem no Termux sem configuração extra)
4. **Use --system-site-packages** no venv para reaproveitar pacotes do sistema
