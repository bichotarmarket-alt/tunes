# Deploy no Railway - Configuração e Limitações

## 🚀 Deploy

### 1. Criar projeto no Railway
```bash
railway login
railway init
railway up
```

### 2. Variáveis de Ambiente (Obrigatórias)
No painel Railway, configure:

| Variável | Valor | Descrição |
|----------|-------|-----------|
| `SECRET_KEY` | `sua-chave-secreta-aqui` | Chave JWT (mínimo 32 chars) |
| `ENVIRONMENT` | `production` | Ambiente |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Auto-inject pelo PostgreSQL Railway |
| `CORS_ORIGINS` | `*` | Ou domínio específico do frontend |

### 3. Banco de Dados
Adicione o plugin **PostgreSQL** no Railway dashboard.

---

## ⚠️ Limitações Críticas do Railway

### WebSockets
| Aspecto | Limite | Impacto |
|---------|--------|---------|
| **Timeout de conexão** | 30s | Clientes inativos desconectam |
| **Máximo de conexões** | ~100-200 por container | >200 = necessita scale horizontal |
| **Broadcast** | Single container | Workers múltiplos = isolados |
| **Sticky sessions** | ❌ Não suportado | Conexões podem balacear para workers diferentes |

### Soluções:

#### 1. Para +200 conexões:
```toml
# railway.toml - escala horizontal
[deploy]
replicas = 2  # Multiplica capacidade x2
```

**⚠️ Problema:** WebSockets em workers diferentes não se comunicam.

**Solução necessária:**
- Implementar **Redis Pub/Sub** para broadcast cross-workers
- Ou usar **Railway Websockets** (feature beta)

#### 2. Para sticky sessions (mesmo usuário no mesmo worker):
Railway **não suporta** sticky sessions nativamente.

Alternativas:
- Usar **Redis** como message broker entre workers
- Conectar todos os clientes ao **mesmo worker** (limita escala)

---

## 🔄 Configuração Recomendada para Railway

### Opção A: Single Worker (até ~150 conexões)
```toml
# railway.toml
[deploy]
startCommand = "python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 1"
replicas = 1
```

### Opção B: Multi-Worker com Redis (500+ conexões)
```toml
# railway.toml
[deploy]
startCommand = "python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers 2"
replicas = 2
```

Requer implementar Redis Pub/Sub no `ConnectionManager`.

---

## 🧪 Teste de Carga no Railway

### 1. Deploy na Railway
```bash
railway up
```

### 2. Obter URL
```bash
railway status
# URL: https://seu-projeto.up.railway.app
```

### 3. Executar teste local contra Railway:
```bash
python -m scripts.ws_load_test \
  --url wss://seu-projeto.up.railway.app/ws/ticks?symbol=EURUSD \
  --http-url https://seu-projeto.up.railway.app \
  --connections 100 \
  --duration 60
```

### 4. Monitorar métricas no Railway Dashboard:
- CPU usage
- Memory usage  
- Network I/O
- Request latency

---

## 🔍 Health Check

Endpoint: `GET /health`

Railway usa para determinar se container está saudável.

---

## 📊 Escala Realista no Railway

| Concorrência | Configuração | Estimativa |
|--------------|--------------|------------|
| Até 150 conexões | 1 worker | ✅ Estável |
| 150-500 | 2 workers + Redis Pub/Sub | ⚠️ Requer código extra |
| 500+ | Considerar VPS dedicada | ❌ Railway não é ideal |

---

## 🚨 Alternativas para Alta Concorrência

Se precisar de 500+ conexões WebSocket simultâneas:

1. **VPS dedicada** (DigitalOcean, AWS EC2, Hetzner)
2. **Fly.io** (melhor suporte a WebSockets que Railway)
3. **Ably** ou **Pusher** (WebSocket-as-a-service)

---

## ✅ Checklist Pré-Deploy

- [ ] `SECRET_KEY` configurada
- [ ] PostgreSQL plugin adicionado
- [ ] Redis plugin adicionado (se usar multi-worker)
- [ ] `ENVIRONMENT=production` setado
- [ ] Health check `/health` respondendo
- [ ] Testado localmente com `railway run`

---

## 📚 Documentação Oficial

- [Railway Docs](https://docs.railway.app/)
- [Railway WebSockets](https://docs.railway.app/reference/app-lifecycle#websockets)
