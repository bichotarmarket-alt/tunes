-- ============================================================
-- ÍNDICES RECOMENDADOS PARA OTIMIZAÇÃO DE PERFORMANCE
-- Tunestrade - Otimização de Queries (Mar/2026)
-- ============================================================
-- Execute estes comandos no seu banco de dados SQLite/PostgreSQL
-- para melhorar a performance das queries otimizadas
-- ============================================================

-- 1. ÍNDICE para queries de balance (account_id nas autotrade_configs)
-- Usado em: _on_balance_updated, _on_balance_data
-- Otimização: Batch updates de initial_balance e highest_balance
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_active 
ON autotrade_configs (account_id, is_active);

-- 2. ÍNDICE para buscar configs ativas com initial_balance IS NULL
-- Usado em: Batch update de inicialização de initial_balance
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_null_initial 
ON autotrade_configs (account_id, is_active) WHERE initial_balance IS NULL;

-- 3. ÍNDICE para buscar configs ativas com highest_balance IS NULL
-- Usado em: Batch update de inicialização de highest_balance
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_null_highest 
ON autotrade_configs (account_id, is_active) WHERE highest_balance IS NULL;

-- 4. ÍNDICE para verificação de saldo mínimo (busca amount das configs ativas)
-- Usado em: _on_balance_data - verificação de saldo insuficiente
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_amount 
ON autotrade_configs (account_id, is_active, amount);

-- 5. ÍNDICE para buscar usuário via account (JOIN otimizado)
-- Usado em: telegram_chat_id query, _handle_account_connection
CREATE INDEX IF NOT EXISTS idx_accounts_user_id 
ON accounts (user_id);

-- 6. ÍNDICE para buscar contas ativas ou com autotrade ativo
-- Usado em: _monitor_loop - busca de contas para monitoramento
CREATE INDEX IF NOT EXISTS idx_accounts_is_active 
ON accounts (is_active);

-- 7. ÍNDICE composto para buscar configs ativas por account
-- Usado em: _handle_account_connection, batch updates
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_id_active 
ON autotrade_configs (account_id, is_active, last_activity_timestamp);

-- 8. ÍNDICE para buscar telegram_chat_id via JOIN
-- Usado em: Notificações Telegram (query JOIN users-accounts)
CREATE INDEX IF NOT EXISTS idx_users_telegram_chat 
ON users (id) INCLUDE (telegram_chat_id);  -- PostgreSQL
-- Para SQLite: CREATE INDEX IF NOT EXISTS idx_users_telegram_chat ON users (id);

-- ============================================================
-- COMANDOS PARA VERIFICAR SE OS ÍNDICES FORAM CRIADOS
-- ============================================================

-- SQLite: Ver índices existentes
-- SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='autotrade_configs';
-- SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='accounts';
-- SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users';

-- PostgreSQL: Ver índices existentes
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'autotrade_configs';
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'accounts';
-- SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'users';

-- ============================================================
-- MEDIÇÃO DE IMPACTO (após criar os índices)
-- ============================================================

-- Verificar se queries estão usando os índices (SQLite)
-- EXPLAIN QUERY PLAN SELECT * FROM autotrade_configs WHERE account_id = 'xxx' AND is_active = TRUE;

-- Verificar se queries estão usando os índices (PostgreSQL)
-- EXPLAIN ANALYZE SELECT * FROM autotrade_configs WHERE account_id = 'xxx' AND is_active = TRUE;

-- ============================================================
-- RESUMO DAS OTIMIZAÇÕES IMPLEMENTADAS
-- ============================================================
-- 
-- 1. Query telegram_chat_id: 
--    - ANTES: Subquery correlacionada (SELECT ... WHERE id = (SELECT ...))
--    + DEPOIS: JOIN direto users JOIN accounts
--    
-- 2. Batch updates para balances:
--    - ANTES: Loop N+1 (1 SELECT + N UPDATEs para N configs)
--    + DEPOIS: 3 UPDATEs em batch (fixos, independente de N)
--    
-- 3. Desativação por saldo insuficiente:
--    - ANTES: Loop for config in configs + update individual
--    + DEPOIS: UPDATE em batch com WHERE account_id = :id AND is_active = TRUE
--    
-- 4. Query complexa _handle_account_connection:
--    - ANTES: LEFT JOINs com BOOL_OR, COUNT, MAX, GROUP BY
--    + DEPOIS: 3 queries simples sem JOINs complexos
--
-- ============================================================
