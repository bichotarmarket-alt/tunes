"""Add daily_signal_summary table for fast reports

Revision ID: add_daily_signal_summary
Revises: 
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_daily_signal_summary'
down_revision = 'f659278ada58'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create daily_signal_summary table
    op.create_table(
        'daily_signal_summary',
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('date', sa.Date, nullable=False, index=True),
        sa.Column('strategy_id', sa.String, nullable=False, default='all'),
        sa.Column('asset_id', sa.String, nullable=False, default='all'),
        sa.Column('timeframe', sa.Integer, nullable=False, default=0),
        sa.Column('total_signals', sa.Integer, default=0),
        sa.Column('buy_signals', sa.Integer, default=0),
        sa.Column('sell_signals', sa.Integer, default=0),
        sa.Column('hold_signals', sa.Integer, default=0),
        sa.Column('executed_signals', sa.Integer, default=0),
        sa.Column('avg_confidence', sa.Float, default=0.0),
        sa.Column('avg_confluence', sa.Float, default=0.0),
        sa.Column('min_confidence', sa.Float, default=0.0),
        sa.Column('max_confidence', sa.Float, default=0.0),
        sa.Column('updated_at', sa.Date, nullable=False, server_default=sa.func.current_date())
    )
    
    # Create indexes
    op.create_index('idx_daily_summary_date_strategy', 'daily_signal_summary', ['date', 'strategy_id'])
    op.create_index('idx_daily_summary_date_asset', 'daily_signal_summary', ['date', 'asset_id'])
    op.create_index('idx_daily_summary_updated', 'daily_signal_summary', ['updated_at'])
    
    # Create aggregation_job_log table
    op.create_table(
        'aggregation_job_log',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('job_name', sa.String, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('records_processed', sa.Integer, default=0),
        sa.Column('status', sa.String, nullable=False),
        sa.Column('error_message', sa.String, nullable=True)
    )


def downgrade() -> None:
    # Drop tables
    op.drop_table('aggregation_job_log')
    op.drop_table('daily_signal_summary')
