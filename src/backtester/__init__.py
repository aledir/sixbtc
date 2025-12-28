"""
Backtesting module

Portfolio backtesting system for strategy validation
"""

from src.backtester.data_loader import BacktestDataLoader
from src.backtester.backtest_engine import BacktestEngine, VectorBTBacktester
from src.backtester.validator import LookaheadValidator

__all__ = [
    'BacktestDataLoader',
    'BacktestEngine',
    'VectorBTBacktester',  # Backward compatibility alias
    'LookaheadValidator',
]
