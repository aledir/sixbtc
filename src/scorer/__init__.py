"""
SCORER Module - Strategy Score Calculation and Pool Management

Single Responsibility: Calculate composite scores from metrics

Components:
- BacktestScorer: Score from backtest metrics (edge, sharpe, win_rate, drawdown, recency)
- LiveScorer: Score from live trade metrics
- PoolManager: Manage ACTIVE pool with leaderboard logic

Score Formula (5 components):
    Score = (0.40 x Expectancy) + (0.25 x Sharpe) + (0.10 x Win Rate) +
            (0.15 x Drawdown) + (0.10 x Recency)
    Normalized to 0-100 scale
"""

from src.scorer.backtest_scorer import BacktestScorer
from src.scorer.live_scorer import LiveScorer
from src.scorer.pool_manager import PoolManager

__all__ = ['BacktestScorer', 'LiveScorer', 'PoolManager']
