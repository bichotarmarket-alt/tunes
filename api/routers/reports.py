"""
Reports Router - API endpoints para relatórios otimizados

Usa a tabela daily_signal_summary para queries rápidas
em vez de escanear a tabela signals completa.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from datetime import date, timedelta
from loguru import logger

from core.database import get_db
from core.security import get_current_active_user
from models import User
from models.daily_summary import DailySignalSummary
from schemas import DailySummaryResponse, ReportQueryParams

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/daily-summary", response_model=List[DailySummaryResponse])
async def get_daily_summary(
    start_date: Optional[date] = Query(None, description="Data inicial (ISO format)"),
    end_date: Optional[date] = Query(None, description="Data final (ISO format)"),
    strategy_id: Optional[str] = Query(None, description="Filtrar por estratégia"),
    asset_id: Optional[str] = Query(None, description="Filtrar por ativo"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obter resumo diário de sinais (usando tabela agregada - rápido)
    
    Esta endpoint usa a tabela daily_signal_summary que é atualizada
    periodicamente pelo job de agregação, permitindo queries rápidas
    mesmo com milhões de sinais no banco.
    """
    # Default: últimos 30 dias
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Construir query
    query = select(DailySignalSummary).where(
        and_(
            DailySignalSummary.date >= start_date,
            DailySignalSummary.date <= end_date
        )
    )
    
    if strategy_id:
        query = query.where(DailySignalSummary.strategy_id == strategy_id)
    
    if asset_id:
        query = query.where(DailySignalSummary.asset_id == asset_id)
    
    # Ordenar por data decrescente
    query = query.order_by(desc(DailySignalSummary.date))
    
    result = await db.execute(query)
    summaries = result.scalars().all()
    
    return [
        DailySummaryResponse(
            id=s.id,
            date=s.date,
            strategy_id=s.strategy_id,
            asset_id=s.asset_id,
            total_signals=s.total_signals,
            buy_signals=s.buy_signals,
            sell_signals=s.sell_signals,
            executed_signals=s.executed_signals,
            avg_confidence=s.avg_confidence,
            execution_rate=(s.executed_signals / s.total_signals * 100) if s.total_signals > 0 else 0
        )
        for s in summaries
    ]


@router.get("/performance-metrics")
async def get_performance_metrics(
    days: int = Query(30, ge=1, le=365, description="Número de dias para análise"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Métricas de performance agregadas (rápido via tabela de agregação)
    """
    start_date = date.today() - timedelta(days=days)
    
    # Agregar da tabela de resumo (muito mais rápido que scanear signals)
    query = select(
        func.sum(DailySignalSummary.total_signals).label('total_signals'),
        func.sum(DailySignalSummary.executed_signals).label('total_executed'),
        func.avg(DailySignalSummary.avg_confidence).label('avg_confidence'),
        func.sum(DailySignalSummary.buy_signals).label('total_buys'),
        func.sum(DailySignalSummary.sell_signals).label('total_sells')
    ).where(
        and_(
            DailySignalSummary.date >= start_date,
            DailySignalSummary.strategy_id == 'all',  # Total geral
            DailySignalSummary.asset_id == 'all'
        )
    )
    
    result = await db.execute(query)
    row = result.one()
    
    total_signals = row.total_signals or 0
    total_executed = row.total_executed or 0
    
    return {
        'period_days': days,
        'total_signals': total_signals,
        'total_executed': total_executed,
        'execution_rate': (total_executed / total_signals * 100) if total_signals > 0 else 0,
        'avg_confidence': float(row.avg_confidence or 0),
        'total_buys': row.total_buys or 0,
        'total_sells': row.total_sells or 0
    }


@router.get("/strategy-comparison")
async def get_strategy_comparison(
    days: int = Query(30, ge=7, le=90, description="Período de comparação"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Comparar performance entre estratégias
    """
    start_date = date.today() - timedelta(days=days)
    
    query = select(
        DailySignalSummary.strategy_id,
        func.sum(DailySignalSummary.total_signals).label('total'),
        func.sum(DailySignalSummary.executed_signals).label('executed'),
        func.avg(DailySignalSummary.avg_confidence).label('avg_conf'),
        func.sum(DailySignalSummary.buy_signals).label('buys'),
        func.sum(DailySignalSummary.sell_signals).label('sells')
    ).where(
        and_(
            DailySignalSummary.date >= start_date,
            DailySignalSummary.strategy_id != 'all',  # Excluir totais
            DailySignalSummary.asset_id == 'all'
        )
    ).group_by(DailySignalSummary.strategy_id)
    
    result = await db.execute(query)
    rows = result.all()
    
    return [
        {
            'strategy_id': row.strategy_id,
            'total_signals': row.total,
            'executed': row.executed,
            'execution_rate': (row.executed / row.total * 100) if row.total > 0 else 0,
            'avg_confidence': float(row.avg_conf or 0),
            'buy_signals': row.buys,
            'sell_signals': row.sells
        }
        for row in rows
    ]
