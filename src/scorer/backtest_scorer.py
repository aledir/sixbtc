"""
Backtest Scorer - Multi-Factor Scoring System

Calculates composite score for strategy ranking based on:
- Edge (expectancy)
- Sharpe ratio
- Consistency (win rate)
- Stability (walk-forward performance)

Score Formula:
    Score = (0.50 x Edge) + (0.25 x Sharpe) + (0.15 x Consistency) + (0.10 x Stability)
    Normalized to 0-100 scale
"""

from typing import Dict, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BacktestScorer:
    """
    Calculates composite score for strategy ranking from backtest metrics.

    Single Responsibility: Score calculation only.
    """

    def __init__(self, config: dict):
        """
        Initialize scorer with weights from config.

        Args:
            config: Configuration dict with 'scorer.weights' section

        Raises:
            KeyError: If required config sections are missing (Fast Fail)
        """
        # Try new config location first, fallback to legacy
        if 'scorer' in config:
            self.weights = config['scorer']['weights']
        elif 'classification' in config:
            # Legacy fallback
            self.weights = config['classification']['score_weights']
        else:
            raise KeyError("Config must have 'scorer.weights' or 'classification.score_weights'")

        logger.info(f"BacktestScorer initialized with weights: {self.weights}")

    def score(self, metrics: Dict[str, float]) -> float:
        """
        Calculate composite score from backtest metrics.

        Args:
            metrics: Dictionary containing:
                - expectancy: Edge per trade (as decimal, e.g., 0.05 = 5%)
                - sharpe_ratio: Sharpe ratio
                - consistency: Win rate (0-1)
                - wf_stability: Walk-forward stability (0-1, lower=better)

        Returns:
            Composite score (0-100 scale)
        """
        # Extract with guards against None values
        edge = metrics.get('expectancy', 0) or 0.0
        sharpe = metrics.get('sharpe_ratio', 0) or 0.0
        consistency = metrics.get('consistency', 0) or 0.0
        wf_stability = metrics.get('wf_stability')
        if wf_stability is None:
            wf_stability = 1.0  # Worst stability = no walk-forward data

        # Normalize each metric to 0-1 scale
        edge_score = self._normalize_edge(edge)
        sharpe_score = self._normalize_sharpe(sharpe)
        consistency_score = consistency  # Already 0-1
        stability_score = 1 - wf_stability  # Lower is better

        # Weighted sum
        score = (
            self.weights['edge'] * edge_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['consistency'] * consistency_score +
            self.weights['stability'] * stability_score
        )

        # Scale to 0-100
        return min(max(score * 100, 0), 100)

    def score_from_backtest_result(self, backtest_result) -> float:
        """
        Calculate score from BacktestResult model.

        Uses weighted metrics (training 40% + holdout 60%) for accurate ranking.

        Args:
            backtest_result: BacktestResult model instance

        Returns:
            Composite score (0-100 scale)

        Raises:
            ValueError: If backtest_result is missing weighted metrics
        """
        if backtest_result.weighted_sharpe_pure is None:
            raise ValueError(
                f"BacktestResult {backtest_result.id} missing weighted metrics. "
                f"Re-run backtest to populate weighted fields."
            )

        metrics = {
            'expectancy': backtest_result.weighted_expectancy or 0.0,
            'sharpe_ratio': backtest_result.weighted_sharpe_pure or 0.0,
            'consistency': backtest_result.weighted_win_rate or 0.0,
            'wf_stability': backtest_result.weighted_walk_forward_stability or 1.0,
        }

        return self.score(metrics)

    def _normalize_edge(self, edge: float, min_val: float = 0, max_val: float = 0.10) -> float:
        """
        Normalize edge (expectancy) to 0-1 scale.

        Typical range: 0% to 10% edge per trade
        """
        return self._normalize(edge, min_val, max_val)

    def _normalize_sharpe(self, sharpe: float, min_val: float = 0, max_val: float = 3.0) -> float:
        """
        Normalize Sharpe ratio to 0-1 scale.

        Typical range: 0 to 3.0
        """
        return self._normalize(sharpe, min_val, max_val)

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """
        Normalize value to 0-1 range.

        Args:
            value: Value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value

        Returns:
            Normalized value (0-1)
        """
        if value is None:
            return 0.0

        if max_val == min_val:
            return 0.5

        normalized = (value - min_val) / (max_val - min_val)
        return min(max(normalized, 0), 1)
