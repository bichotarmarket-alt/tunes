# Deploy no Railway - Guia Completo

## 1. Configuração do railway.toml (já feito ✓)

O arquivo `railway.toml` já está configurado:
- Python 3.11
- Healthcheck em `/health` com timeout de 120s
- Delay de 5s no startup para o banco iniciar

## 2. Banco de Dados PostgreSQL

### No Dashboard do Railway:
1. Clique em **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Aguarde a criação (status: "Available")
3. Clique na variável `DATABASE_URL` e copie o valor

### Variável de Ambiente Obrigatória:
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/database
```

**IMPORTANTE:** O Railway fornece automaticamente `DATABASE_URL` quando você cria um PostgreSQL e conecta ao serviço.

## 3. Redis (Opcional - para cache)

1. **"New"** → **"Database"** → **"Add Redis"**
2. A variável `REDIS_URL` será criada automaticamente
3. Ative o cache nas variáveis:
```
REDIS_ENABLED=true
```

## 4. Variáveis de Ambiente Obrigatórias

No Railway Dashboard, vá em **"Variables"** e adicione:

```
# Segurança (GERAR NOVOS VALORES!)
SECRET_KEY=sua-chave-secreta-aqui-minimo-32-caracteres
ALGORITHM=HS256

# Ambiente
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# API
API_HOST=0.0.0.0
API_PORT=$PORT  # Railway define automaticamente
API_PREFIX=/api/v1

# Autenticação
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_MINUTE_AUTH=300

# CORS (adicione seu domínio frontend)
CORS_ORIGINS=https://seu-frontend.vercel.app,https://tunestrade.com

# Banco (Railway fornece automaticamente)
DATABASE_URL=${{Postgres.DATABASE_URL}}
DB_ECHO=false

# Redis (se usar)
REDIS_URL=${{Redis.REDIS_URL}}
REDIS_ENABLED=true

# Telegram (opcional)
TELEGRAM_BOT_TOKEN=seu-token-aqui
TELEGRAM_ENABLED=true

# Pocket Option (configurar na aplicação)
POCKETOPTION_DEFAULT_REGION=EUROPA
POCKETOPTION_PING_INTERVAL=20

# Limites de Trading
MAX_TRADES_PER_DAY=20
MAX_TRADES_SIMULTANEOUS=5
MAX_TRADE_AMOUNT=100.0
MAX_DAILY_LOSS_PERCENT=5.0
MIN_SIGNAL_CONFIDENCE=0.7

# Data Collector
DATA_COLLECTOR_ENABLED=true
DATA_COLLECTION_INTERVAL=1
```

## 5. Deploy Automático

1. Conecte o repositório GitHub no Railway:
   - **"New"** → **"GitHub Repo"**
   - Selecione `bichotarmarket-alt/tunes`

2. O deploy será automático a cada push na branch `main`

3. Acompanhe os logs em **"View logs"**

## 6. Solução de Problemas Comuns

### "Healthcheck failure"
- Verifique se o PostgreSQL está conectado ao serviço
- Confira se `DATABASE_URL` está configurada
- Aumente o `healthcheckTimeout` se necessário

### "ModuleNotFoundError"
- Certifique-se que o `requirements.txt` está completo
- Faça commit e push das dependências

### "Database connection failed"
- Verifique se o banco PostgreSQL foi criado
- Confirme que a variável `DATABASE_URL` existe

## 7. Após Deploy Bem-Sucedido

1. **Obtenha a URL do serviço**:
   - Vá em **"Settings"** → **"Domains"**
   - Copie a URL gerada (ex: `https://tunestrade-production.up.railway.app`)

2. **Configure no Frontend**:
   - Adicione a URL do backend nas variáveis de ambiente do frontend
   - Atualize `CORS_ORIGINS` no Railway com o domínio do frontend

3. **Execute as Migrations** (se necessário):
   - Acesse o console do Railway
   - Execute: `alembic upgrade head`

## Comandos Úteis

```bash
# Verificar status do deploy
git status

# Commitar mudanças
git add .
git commit -m "Deploy para Railway"
git push origin main

# Ver logs no Railway
# Acesse: railway.com → Seu Projeto → View logs
```

## Links Importantes

- Railway Dashboard: https://railway.com/dashboard
- GitHub Repo: https://github.com/bichotarmarket-alt/tunes
- Documentação Railway: https://docs.railway.com/

---

**Status Atual:** Aguardando criação do PostgreSQL no Railway
