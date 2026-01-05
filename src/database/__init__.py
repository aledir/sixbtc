"""
Database module for SixBTC

Provides:
- SQLAlchemy models
- Database connection management
- Session management
- Multi-process strategy coordination
"""

from .models import Base, Strategy, StrategyTemplate, BacktestResult, PipelineMetricsSnapshot, Trade, PerformanceSnapshot, Subaccount, Coin, ScheduledTaskExecution, PairsUpdateLog
from .connection import get_engine, get_session, init_db
from .strategy_processor import StrategyProcessor

__all__ = [
    "Base",
    "Strategy",
    "StrategyTemplate",
    "BacktestResult",
    "PipelineMetricsSnapshot",
    "Trade",
    "PerformanceSnapshot",
    "Subaccount",
    "Coin",
    "ScheduledTaskExecution",
    "PairsUpdateLog",
    "get_engine",
    "get_session",
    "init_db",
    "StrategyProcessor",
]
