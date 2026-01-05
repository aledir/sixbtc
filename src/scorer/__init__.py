"""
SCORER Module - Strategy Score Calculation and Pool Management

Single Responsibility: Calculate composite scores from metrics

Components:
- BacktestScorer: Score from backtest metrics (edge, sharpe, consistency, stability)
- LiveScorer: Score from live trade metrics
- PoolManager: Manage ACTIVE pool with leaderboard logic

Score Formula:
    Score = (0.50 x Edge) + (0.25 x Sharpe) + (0.15 x Consistency) + (0.10 x Stability)
    Normalized to 0-100 scale
"""

from src.scorer.backtest_scorer import BacktestScorer
from src.scorer.live_scorer import LiveScorer
from src.scorer.pool_manager import PoolManager

__all__ = ['BacktestScorer', 'LiveScorer', 'PoolManager']
