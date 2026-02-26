# Análise de Custos: 50 Usuários Simultâneos

## 📊 Perfil de Uso Estimado (50 usuários)

### Comportamento por Usuário:
| Atividade | Frequência | Recursos |
|-----------|------------|----------|
| **Login** | 2x por dia | 1 request JWT + DB query |
| **WebSocket** | Conectado 8h/dia | 1 conexão ativa, recebe ticks |
| **Análise/Trades** | 20 trades/dia | DB writes, validações, notificações |
| **API REST** | 100 requests/dia | Candles, estratégias, histórico |
| **Notificações** | Real-time | Telegram API calls |

### Volume Diário Estimado:
```
Logins: 50 × 2 = 100 logins/dia
WebSocket conexões: 50 simultâneas (8h cada)
Trades executados: 50 × 20 = 1.000 trades/dia
API requests: 50 × 100 = 5.000 requests/dia
Ticks recebidos: 50 × 1.440 (1/min) = 72.000 ticks/dia
Notificações Telegram: 1.000/dia
```

---

## 💾 Consumo de Recursos por Componente

### 1. WebSocket (Ticks em Tempo Real)
```
50 conexões simultâneas:
- Memória: ~5MB por conexão = 250MB total
- CPU: ~2% por 50 conexões (broadcast leve)
- Tráfego: ~1KB/s por conexão = 50KB/s = 4.3GB/dia
- Banco: Leitura de ticks (cacheado)
```

### 2. PostgreSQL Database
```
Operações diárias:
- Trades: 1.000 inserts/dia
- Sinais: 1.000 inserts/dia
- Candles: ~50.000 registros (50 ativos × 1.440 min/dia)
- Histórico: 100 queries/dia por usuário
- Storage: ~500MB crescimento/mês

Recursos:
- RAM: 512MB mínimo (cache + queries)
- CPU: 5-10% (escrita frequente)
- IOPS: Moderado (trades síncronos)
```

### 3. API REST + Lógica de Negócio
```
Requests diários: 5.000
- Autenticação: JWT verify (100/dia)
- Candles: DB read cacheado (2.000/dia)
- Estratégias: DB read (1.500/dia)
- Indicadores: CPU intensivo (500/dia)

Recursos:
- CPU: 15-25% (média), picos em análises
- RAM: 300-500MB (aplicação + cache)
```

### 4. PocketOption WebSocket (Externo)
```
Conexões:
- 1 conexão por usuário ativo
- 50 conexões para PocketOption
- Tráfego: bidirecional moderado
- Latência crítica: <100ms

Obs: Não consome seus recursos, mas depende deles
```

### 5. Notificações Telegram
```
1.000 notificações/dia:
- API calls: 1.000/dia
- Latência: não crítica
- Custo: $0 (Telegram free tier)
- Retry automático: sim
```

---

## 🧮 Estimativa de Recursos Totais (50 usuários)

### CPU:
```
WebSocket broadcast:      2%
API REST requests:       20%
Trade execution:         15%
DB operations:           10%
Notificações:           3%
Overhead sistema:       5%
────────────────────────────
TOTAL:                  ~55% de 1 vCPU
```

### Memória:
```
Aplicação Python:       400MB
50 WebSockets:          250MB
PostgreSQL cache:       300MB
Redis (opcional):       100MB
Overhead sistema:       200MB
────────────────────────────
TOTAL:                  ~1.25GB RAM
```

### Tráfego de Rede (mensal):
```
WebSocket ticks:        130GB/mês
API REST:               5GB/mês
PocketOption WS:        20GB/mês
────────────────────────────
TOTAL:                  ~155GB/mês
```

### Storage (PostgreSQL):
```
Candles histórico:      500MB/mês
Trades/logs:            100MB/mês
Backup:                 200MB/mês
────────────────────────────
TOTAL:                  ~800MB/mês
```

---

## 💰 Custo Mensal por Plataforma (50 usuários)

### 1. Railway (PaaS)
```
Componente              Uso Estimado    Custo
─────────────────────────────────────────────
Container (1x)          512MB, 0.5vCPU    $5
PostgreSQL              1GB RAM          $10
Tráfego                 155GB            $15
─────────────────────────────────────────────
TOTAL MENSAL:                           ~$30

Limitações:
- Timeout WebSocket 30s
- Máx ~150 conexões (você está em 50 = OK)
- Sem Redis (não incluído)
```

### 2. Fly.io (PaaS)
```
Componente              Uso Estimado    Custo
─────────────────────────────────────────────
App (shared-cpu-1x)     1GB RAM          $6
PostgreSQL (dev)        256MB            $0 (incluído)
Tráfego                 155GB            $2
─────────────────────────────────────────────
TOTAL MENSAL:                           ~$8

Upgrade necessário:
App (dedicated-cpu-1x)  2GB RAM          $15
PostgreSQL (prod)       1GB RAM          $10
─────────────────────────────────────────────
TOTAL OTIMIZADO:                        ~$27

Vantagens:
- WebSockets funcionam bem
- Postgres incluído no free tier
- Melhor que Railway para WS
```

### 3. Hetzner VPS (IaaS) ⭐ RECOMENDADO
```
Componente              Especificação    Custo
─────────────────────────────────────────────
CPX21 (VPS)             4vCPU, 8GB RAM  €5.35/mês (~$6)
Ubuntu 22.04            -                $0
PostgreSQL 15           Self-hosted      $0
─────────────────────────────────────────────
TOTAL MENSAL:                           ~$6

Backup (opcional):
- Snapshots Hetzner:     €1/mês (~$1)
- S3 backup externo:     $2/mês
─────────────────────────────────────────────
TOTAL COM BACKUP:                       ~$9

Recursos:
- 4 vCPUs (sobra para 200 usuários)
- 8GB RAM (3x o necessário)
- 20TB tráfego incluído
- 40GB SSD NVMe
```

### 4. DigitalOcean (IaaS)
```
Componente              Especificação    Custo
─────────────────────────────────────────────
Droplet Basic           2vCPU, 4GB RAM  $24/mês
PostgreSQL Managed      1vCPU, 1GB RAM  $15/mês
Tráfego                 155GB            $0 (incluído até 1TB)
─────────────────────────────────────────────
TOTAL MENSAL:                           ~$39

Vantagens:
- Managed Postgres (menos trabalho)
- Backup automático
- Load balancer fácil
```

### 5. AWS (Cloud)
```
Componente              Especificação    Custo
─────────────────────────────────────────────
EC2 t3.small            2vCPU, 2GB RAM  $16/mês
RDS PostgreSQL          db.t3.micro     $13/mês
Data transfer           155GB            $14/mês
ALB (load balancer)     -               $16/mês
CloudWatch              -               $5/mês
─────────────────────────────────────────────
TOTAL MENSAL:                           ~$64

Overkill para 50 usuários
```

---

## 📊 Comparativo Visual

```
Custo Mensal (50 usuários)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hetzner      ████████░░░░░░░░░░░░  $6-9
Fly.io       ███████████████████░  $8-27
Railway      █████████████████████░  $30
DigitalOcean ████████████████████████████████  $39
AWS          ████████████████████████████████████████████████  $64
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🏆 Recomendação para 50 Usuários

### **Opção 1: Hetzner CPX21** ⭐ MELHOR CUSTO-BENEFÍCIO
- **Custo:** $6/mês
- **Capacidade:** Suporta 200+ usuários (4x margem)
- **WebSockets:** ✅ Sem limitações
- **PostgreSQL:** ✅ Mesma máquina (zero latência)
- **Setup:** Docker Compose (1 arquivo)

**Comando de deploy:**
```bash
# Hetzner Cloud Console
1. Criar servidor CPX21 (Ubuntu 22.04)
2. Conectar via SSH
3. git clone seu-repo
4. docker-compose up -d
```

---

### **Opção 2: Fly.io** (Se não quiser gerenciar VPS)
- **Custo:** $15-20/mês
- **Capacidade:** 150 usuários (com folga)
- **WebSockets:** ✅ Melhor que Railway
- **PostgreSQL:** ✅ Managed
- **Deploy:** `fly deploy`

---

## ⚠️ Custos Ocultos a Considerar

### 1. Crescimento (100 usuários = 2x custo)
| Plataforma | Custo 50u | Custo 100u | Escala fácil? |
|------------|-----------|------------|---------------|
| Hetzner    | $6        | $6 (mesmo) | Vertical      |
| Fly.io     | $15       | $30        | Horizontal    |
| Railway    | $30       | $60        | Horizontal    |

### 2. Backup e Monitoramento
```
Hetzner:
- Snapshots: €1/mês (~$1)
- Uptime monitoring (UptimeRobot): $0 (free)
- Logs (Grafana Cloud): $0 (free tier)

Fly.io:
- Backup Postgres: incluído
- Logs: incluído
- Métricas: incluído
```

### 3. Domínio e SSL
```
Domínio .com:           $10-15/ano (~$1/mês)
SSL (Let's Encrypt):    $0 (automático)
CDN (Cloudflare):       $0 (free tier)
```

---

## 📈 Projeção de Custos (12 meses)

### Cenário: Crescimento 50 → 100 usuários

| Mês | Usuários | Hetzner | Fly.io | Railway |
|-----|----------|---------|--------|---------|
| 1-3 | 50       | $6      | $15    | $30     |
| 4-6 | 60       | $6      | $20    | $35     |
| 7-9 | 80       | $12*    | $30    | $50     |
| 10-12| 100     | $12     | $40    | $65     |
| **Total Ano** | | **$108** | **$318** | **$540** |

*Upgrade CPX31 para 80+ usuários

---

## 🎯 Decisão Final

### Para 50 usuários simultâneos:

**🏆 Vencedor: Hetzner CPX21**
- Custo: **$6/mês**
- Performance: **4x o necessário**
- WebSockets: **Sem limitações**
- PostgreSQL: **Incluso**

**Runner-up: Fly.io**
- Custo: **$15-20/mês**
- Zero configuração de infra
- Boa para quem não quer gerenciar servidor

**Evitar: Railway**
- Timeout WebSocket vai desconectar usuários inativos
- Broadcast não funciona bem entre workers
- Custo alto para o que oferece

---

## 📋 Checklist de Setup (Hetzner)

```bash
# 1. Criar conta Hetzner Cloud
# 2. Criar projeto
# 3. Deploy:

$ hcloud server create --name tunestrade --type cpx21 --image ubuntu-22.04
$ ssh root@<ip>

# No servidor:
$ apt update && apt install -y docker.io docker-compose
$ git clone https://github.com/seu-user/tunestrade.git
$ cd tunestrade
$ docker-compose up -d

# 4. Configurar DNS apontar para IP
# 5. SSL automático com Let's Encrypt
```

---

## 🚀 Resumo para Decisão Rápida

| Se você valoriza... | Escolha | Custo |
|---------------------|---------|-------|
| **Menor custo** | Hetzner | $6/mês |
| **Zero config** | Fly.io | $15/mês |
| **Suporte 24h** | DigitalOcean | $39/mês |
| **Escalabilidade automática** | AWS | $64/mês (overkill) |

**Para trading em tempo real com 50 usuários:**
👉 **Hetzner CPX21** é a escolha inteligente.

Quer que eu gere o arquivo `docker-compose.yml` completo para deploy no Hetzner?
