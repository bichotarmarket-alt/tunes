"""
Aggregation Job - Job assíncrono para atualizar tabela de agregação

Este job calcula métricas agregadas de sinais e atualiza a tabela
daily_signal_summary para queries de relatório rápidas.
"""
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, case, Integer
from loguru import logger
import asyncio

from core.database import get_db_context
from models import Signal, Trade
from models.daily_summary import DailySignalSummary, AggregationJobLog


class AggregationJob:
    """
    Job para calcular e atualizar agregações de sinais
    
    Executa periodicamente (ex: a cada hora) para manter
    as agregações atualizadas.
    """
    
    def __init__(self, interval_minutes: int = 60):
        self.interval_minutes = interval_minutes
        self._task: Optional[asyncio.Task] = None
        self._is_running = False
        self.last_run: Optional[str] = None  # Para dashboard tracking
    
    @property
    def is_running(self) -> bool:
        """Propriedade para verificar se job está rodando (para dashboard)"""
        return self._is_running
    
    async def start(self):
        """Iniciar job de agregação"""
        if self._is_running:
            return
        
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[AGGREGATION JOB] Iniciado | intervalo={self.interval_minutes}min")
    
    async def stop(self):
        """Parar job de agregação"""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[AGGREGATION JOB] Parado")
    
    async def _run_loop(self):
        """Loop principal do job"""
        while self._is_running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"[AGGREGATION JOB] Erro: {e}")
            
            # Aguardar próxima execução
            await asyncio.sleep(self.interval_minutes * 60)
    
    async def run_once(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Executar agregação uma vez
        
        Args:
            target_date: Data para agregar (default: ontem)
        
        Returns:
            Estatísticas da execução
        """
        if target_date is None:
            target_date = date.today() - timedelta(days=1)
        
        job_name = f"daily_aggregation_{target_date.isoformat()}"
        start_time = datetime.utcnow()
        
        async with get_db_context() as db:
            # Criar log de execução
            log_entry = AggregationJobLog(
                job_name=job_name,
                started_at=start_time,
                status='running'
            )
            db.add(log_entry)
            await db.commit()
            await db.refresh(log_entry)
            
            try:
                # Calcular agregações
                records_processed = await self._calculate_aggregations(db, target_date)
                
                # Commit final após todos os upserts
                await db.commit()
                
                # Atualizar log
                log_entry.status = 'completed'
                log_entry.completed_at = datetime.utcnow()
                log_entry.records_processed = records_processed
                
                await db.commit()
                
                duration = (log_entry.completed_at - start_time).total_seconds()
                
                # Atualizar timestamp de última execução para dashboard
                self.last_run = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                
                logger.info(
                    f"[AGGREGATION JOB] Concluído | date={target_date} | "
                    f"records={records_processed} | duration={duration:.1f}s"
                )
                
                return {
                    'status': 'completed',
                    'date': target_date,
                    'records_processed': records_processed,
                    'duration_seconds': duration
                }
                
            except Exception as e:
                log_entry.status = 'failed'
                log_entry.completed_at = datetime.utcnow()
                log_entry.error_message = str(e)
                await db.commit()
                
                logger.error(f"[AGGREGATION JOB] Falhou: {e}")
                raise
    
    async def _calculate_aggregations(self, db, target_date: date) -> int:
        """
        Calcular agregações para uma data específica
        
        Returns:
            Número de registros processados
        """
        records_processed = 0
        
        # Agregação por estratégia
        strategy_results = await self._aggregate_by_strategy(db, target_date)
        for result in strategy_results:
            await self._upsert_summary(db, target_date, result)
            records_processed += 1
        
        # Agregação por ativo
        asset_results = await self._aggregate_by_asset(db, target_date)
        for result in asset_results:
            await self._upsert_summary(db, target_date, result)
            records_processed += 1
        
        # Agregação geral (todos)
        total_result = await self._aggregate_total(db, target_date)
        await self._upsert_summary(db, target_date, total_result)
        records_processed += 1
        
        return records_processed
    
    async def _aggregate_by_strategy(self, db, target_date: date) -> List[Dict]:
        """Agregar sinais por estratégia"""
        query = select(
            Signal.strategy_id,
            func.count().label('total'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'buy', Integer), 0)).label('buys'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'sell', Integer), 0)).label('sells'),
            func.sum(func.coalesce(func.cast(Signal.is_executed == True, Integer), 0)).label('executed'),
            func.avg(Signal.confidence).label('avg_confidence'),
            func.avg(Signal.confluence).label('avg_confluence')
        ).where(
            and_(
                func.date(Signal.created_at) == target_date,
                Signal.strategy_id.isnot(None)
            )
        ).group_by(Signal.strategy_id)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                'strategy_id': row.strategy_id,
                'asset_id': 'all',
                'timeframe': 0,
                'total_signals': row.total,
                'buy_signals': row.buys or 0,
                'sell_signals': row.sells or 0,
                'executed_signals': row.executed or 0,
                'avg_confidence': float(row.avg_confidence or 0),
                'avg_confluence': float(row.avg_confluence or 0)
            }
            for row in rows
        ]
    
    async def _aggregate_by_asset(self, db, target_date: date) -> List[Dict]:
        """Agregar sinais por ativo"""
        query = select(
            Signal.asset_id,
            func.count().label('total'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'buy', Integer), 0)).label('buys'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'sell', Integer), 0)).label('sells'),
            func.sum(func.coalesce(func.cast(Signal.is_executed == True, Integer), 0)).label('executed'),
            func.avg(Signal.confidence).label('avg_confidence'),
            func.avg(Signal.confluence).label('avg_confluence')
        ).where(
            func.date(Signal.created_at) == target_date
        ).group_by(Signal.asset_id)
        
        result = await db.execute(query)
        rows = result.all()
        
        return [
            {
                'strategy_id': 'all',
                'asset_id': str(row.asset_id),
                'timeframe': 0,
                'total_signals': row.total,
                'buy_signals': row.buys or 0,
                'sell_signals': row.sells or 0,
                'executed_signals': row.executed or 0,
                'avg_confidence': float(row.avg_confidence or 0),
                'avg_confluence': float(row.avg_confluence or 0)
            }
            for row in rows
        ]
    
    async def _aggregate_total(self, db, target_date: date) -> Dict:
        """Agregar total de sinais (todas as estratégias e ativos)"""
        query = select(
            func.count().label('total'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'buy', Integer), 0)).label('buys'),
            func.sum(func.coalesce(func.cast(func.text(Signal.signal_type) == 'sell', Integer), 0)).label('sells'),
            func.sum(func.coalesce(func.cast(Signal.is_executed == True, Integer), 0)).label('executed'),
            func.avg(Signal.confidence).label('avg_confidence'),
            func.avg(Signal.confluence).label('avg_confluence')
        ).where(
            func.date(Signal.created_at) == target_date
        )
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            'strategy_id': 'all',
            'asset_id': 'all',
            'timeframe': 0,
            'total_signals': row.total,
            'buy_signals': row.buys or 0,
            'sell_signals': row.sells or 0,
            'executed_signals': row.executed or 0,
            'avg_confidence': float(row.avg_confidence or 0),
            'avg_confluence': float(row.avg_confluence or 0)
        }
    
    async def _upsert_summary(self, db, target_date: date, data: Dict):
        """Inserir ou atualizar registro de agregação usando upsert atômico"""
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from datetime import datetime
        
        summary_id = DailySignalSummary.generate_id(
            date=target_date,
            strategy_id=data['strategy_id'],
            asset_id=data['asset_id'],
            timeframe=data['timeframe']
        )
        
        # Usar upsert atômico (INSERT ON CONFLICT DO UPDATE) para PostgreSQL
        # Isso evita race conditions que causam duplicatas
        stmt = pg_insert(DailySignalSummary).values(
            id=summary_id,
            date=target_date,
            strategy_id=data['strategy_id'],
            asset_id=data['asset_id'],
            timeframe=data['timeframe'],
            total_signals=data['total_signals'],
            buy_signals=data['buy_signals'],
            sell_signals=data['sell_signals'],
            executed_signals=data['executed_signals'],
            avg_confidence=data['avg_confidence'],
            avg_confluence=data['avg_confluence'],
            updated_at=datetime.utcnow()
        )
        
        # On conflict, update all columns
        update_dict = {
            'total_signals': stmt.excluded.total_signals,
            'buy_signals': stmt.excluded.buy_signals,
            'sell_signals': stmt.excluded.sell_signals,
            'executed_signals': stmt.excluded.executed_signals,
            'avg_confidence': stmt.excluded.avg_confidence,
            'avg_confluence': stmt.excluded.avg_confluence,
            'updated_at': stmt.excluded.updated_at
        }
        
        do_update_stmt = stmt.on_conflict_do_update(
            constraint='daily_signal_summary_pkey',  # Nome da constraint PRIMARY KEY
            set_=update_dict
        )
        
        await db.execute(do_update_stmt)
        await db.flush()


# Instância global do job
aggregation_job = AggregationJob(interval_minutes=60)
