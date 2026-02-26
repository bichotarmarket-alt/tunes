# Análise Completa: Hospedagem para Sistema de Trading

## 📊 Requisitos do Projeto

### Funcionais:
- WebSockets em tempo real (ticks, candles)
- PostgreSQL (já configurado)
- Resiliência (circuit breaker, retry)
- Autenticação JWT
- Notificações Telegram

### Não-funcionais:
- Suportar 100-500 usuários simultâneos
- Latência <100ms para broadcasts
- 99.9% uptime
- Backup automático

---

## 🏆 Comparativo de Plataformas

### 1. Railway (PaaS)
| Aspecto | Avaliação |
|---------|-----------|
| **Facilidade** | ⭐⭐⭐⭐⭐ (deploy em 1 comando) |
| **WebSockets** | ⭐⭐ (máx ~150 conexões/worker) |
| **PostgreSQL** | ⭐⭐⭐⭐ (plugin integrado) |
| **Preço** | $5-50/mês dependendo do uso |
| **Escalabilidade** | ⭐⭐ (horizontal complicada) |

**Problemas:**
- Timeout WebSocket 30s (não configurável)
- Sem sticky sessions
- Broadcast não funciona entre workers

**Custo estimado:**
- Starter: $5/mês (baixo tráfego)
- Pro: $20-50/mês (médio tráfego)
- Enterprise: $100+/mês (alto tráfego)

---

### 2. Fly.io (PaaS especializado)
| Aspecto | Avaliação |
|---------|-----------|
| **Facilidade** | ⭐⭐⭐⭐ (deploy simples) |
| **WebSockets** | ⭐⭐⭐⭐⭐ (melhor que Railway) |
| **PostgreSQL** | ⭐⭐⭐⭐⭐ (Postgres cluster nativo) |
| **Preço** | $2-30/mês |
| **Escalabilidade** | ⭐⭐⭐⭐ (melhor que Railway) |

**Vantagens sobre Railway:**
- WebSockets funcionam melhor
- Sticky sessions suportados
- Postgres com replicação
- Edge deployment (menor latência)

**Custo estimado:**
- Shared CPU: $2-5/mês
- Dedicated CPU: $10-30/mês
- PostgreSQL: $5-15/mês

---

### 3. VPS - Hetzner/DigitalOcean (IaaS)
| Aspecto | Avaliação |
|---------|-----------|
| **Facilidade** | ⭐⭐ (precisa configurar tudo) |
| **WebSockets** | ⭐⭐⭐⭐⭐ (sem limitações) |
| **PostgreSQL** | ⭐⭐⭐⭐ (instalação manual ou managed) |
| **Preço** | $6-20/mês |
| **Escalabilidade** | ⭐⭐⭐⭐⭐ (você controla tudo) |

**Hetzner (melhor custo-benefício):**
- CPX11: 2vCPU, 4GB RAM = €5.35/mês (~$6)
- CPX21: 4vCPU, 8GB RAM = €10.70/mês (~$12)

**DigitalOcean:**
- Basic: 1vCPU, 1GB = $6/mês
- General: 2vCPU, 4GB = $24/mês

**Vantagens:**
- Controle total
- WebSockets sem limites
- PostgreSQL na mesma máquina = zero latência
- Backup manual ou automático

---

### 4. AWS/GCP/Azure (Cloud Enterprise)
| Aspecto | Avaliação |
|---------|-----------|
| **Facilidade** | ⭐⭐ (complexo) |
| **WebSockets** | ⭐⭐⭐⭐⭐ (API Gateway WebSocket) |
| **PostgreSQL** | ⭐⭐⭐⭐⭐ (RDS) |
| **Preço** | $50-200/mês |
| **Escalabilidade** | ⭐⭐⭐⭐⭐ (ilimitada) |

**Problemas:**
- Custo alto
- Complexidade excessiva para startup
- Curva de aprendizado longa

---

## 🎯 Recomendação por Cenário

### Cenário 1: Startup/MVP (até 50 usuários)
**🏆 Fly.io**
- Custo: ~$10/mês
- Deploy simples
- PostgreSQL integrado
- WebSockets funcionam bem

**Comando de deploy:**
```bash
flyctl launch
flyctl postgres create
flyctl deploy
```

---

### Cenário 2: Crescimento (50-200 usuários)
**🏆 Hetzner VPS + PostgreSQL Managed**
- Custo: ~$15-25/mês
- CPX21 (4vCPU, 8GB): €10.70
- PostgreSQL managed: €5-10

**Vantagens:**
- WebSockets ilimitados
- Performance consistente
- Backup automático

---

### Cenário 3: Escala (200-1000 usuários)
**🏆 Hetzner VPS + Redis + Load Balancer**
- Custo: ~$30-50/mês
- 2x CPX21 + Load Balancer
- Redis para Pub/Sub entre instâncias

**Arquitetura:**
```
Load Balancer
    ├── VPS 1 (ConnectionManager + API)
    ├── VPS 2 (ConnectionManager + API)
    └── Redis (Pub/Sub broadcast)
```

---

## 🚀 Minha Recomendação Definitiva

### **Fase 1 (Agora): Fly.io**
```bash
# Deploy inicial
flyctl launch --name tunestrade
flyctl postgres create --name tunestrade-db
flyctl deploy
```

**Custo:** ~$10-15/mês
**Capacidade:** até 150 usuários simultâneos

### **Fase 2 (Crescimento): Migrar para Hetzner**
Quando atingir limites do Fly.io:
```bash
# VPS Hetzner
CPX21 (4vCPU, 8GB RAM)
Ubuntu 22.04
PostgreSQL 15
```

**Custo:** ~$15-20/mês
**Capacidade:** 500+ usuários simultâneos

---

## 📁 Arquivos de Configuração

### Fly.io: `fly.toml`
```toml
app = "tunestrade"
primary_region = "iad"

[build]
  builder = "heroku/buildpacks:20"

[env]
  PORT = "8080"
  ENVIRONMENT = "production"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[checks]
  [checks.alive]
    port = 8080
    type = "http"
    interval = "10s"
    timeout = "5s"
    grace_period = "30s"
    method = "get"
    path = "/health"
```

### Hetzner: `docker-compose.yml`
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/tunestrade
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    restart: always

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=tunestrade
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

volumes:
  postgres_data:
```

---

## ⚡ Checklist de Migração PostgreSQL

### Atual (SQLite) → PostgreSQL

1. **Backup SQLite:**
```bash
cp autotrade.db autotrade_backup.db
```

2. **Configurar PostgreSQL:**
```python
# core/config.py
DATABASE_URL = "postgresql+asyncpg://user:password@host:5432/tunestrade"
```

3. **Migrar dados:**
```bash
# Instalar ferramenta de migração
pip install sqlalchemy-utils

# Script de migração
python scripts/migrate_sqlite_to_postgres.py
```

4. **Verificar conexão:**
```bash
curl http://localhost:8000/health
# Deve retornar: "database": "connected"
```

---

## 💰 Custo Comparativo (1 ano)

| Plataforma | Mensal | Anual | WebSockets |
|------------|--------|-------|------------|
| **Railway** | $20 | $240 | ⚠️ Limitado |
| **Fly.io** | $12 | $144 | ✅ Bom |
| **Hetzner** | $12 | $144 | ✅ Excelente |
| **AWS** | $80 | $960 | ✅ Excelente (caro) |

---

## 🎬 Próximos Passos Recomendados

1. **Agora:** Deploy no Fly.io (mais rápido)
2. **Quando crescer:** Migre para Hetzner
3. **Futuro:** Considere Kubernetes se >1000 usuários

Quer que eu gere os arquivos de configuração para **Fly.io** ou **Hetzner**? Ou prefere seguir com Railway mesmo sabendo das limitações?
