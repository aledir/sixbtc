"""
Backtest Scorer - Unified Score Formula

Calculates composite score for strategy ranking based on:
- Expectancy (edge per trade)
- Sharpe ratio
- Consistency (win rate)
- Drawdown penalty

Score Formula (Base Score from TRAINING metrics):
    Base Score = (0.45 x Expectancy) + (0.25 x Sharpe) + (0.15 x Consistency) + (0.15 x Drawdown)
    Normalized to 0-100 scale

Recency Bonus (from holdout degradation):
    Bonus = -degradation x 50, capped at [-15, +15]
    Final Score = Base Score + Recency Bonus (0-100)

Strategies performing better in recent 30 days (holdout) get a bonus.
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
                - max_drawdown: Maximum drawdown (0-1, lower=better)

        Returns:
            Composite score (0-100 scale)
        """
        # Extract with guards against None values
        expectancy = metrics.get('expectancy', 0) or 0.0
        sharpe = metrics.get('sharpe_ratio', 0) or 0.0
        consistency = metrics.get('consistency', 0) or 0.0
        max_drawdown = metrics.get('max_drawdown', 0) or 0.0

        # Normalize each metric to 0-1 scale
        expectancy_score = self._normalize_expectancy(expectancy)
        sharpe_score = self._normalize_sharpe(sharpe)
        consistency_score = consistency  # Already 0-1
        drawdown_score = self._normalize_drawdown(max_drawdown)

        # Weighted sum (unified formula)
        score = (
            self.weights['expectancy'] * expectancy_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['consistency'] * consistency_score +
            self.weights['drawdown'] * drawdown_score
        )

        # Scale to 0-100
        return min(max(score * 100, 0), 100)

    def score_from_backtest_result(self, backtest_result, degradation: float = 0.0) -> float:
        """
        Calculate score from BacktestResult model.

        Uses TRAINING metrics (statistically robust from 730 days) + recency bonus
        from holdout degradation.

        Args:
            backtest_result: BacktestResult model instance (must be training period)
            degradation: (training_score - holdout_score) / training_score
                         Negative = holdout better (bonus), Positive = holdout worse (penalty)

        Returns:
            Final score (0-100 scale) with recency bonus applied

        Raises:
            ValueError: If backtest_result is missing required metrics
        """
        if backtest_result.sharpe_ratio is None:
            raise ValueError(
                f"BacktestResult {backtest_result.id} missing training metrics. "
                f"Re-run backtest to populate fields."
            )

        # 1. Base score from TRAINING metrics (statistically robust)
        metrics = {
            'expectancy': backtest_result.expectancy or 0.0,
            'sharpe_ratio': backtest_result.sharpe_ratio or 0.0,
            'consistency': backtest_result.win_rate or 0.0,
            'max_drawdown': backtest_result.max_drawdown or 0.0,
        }
        base_score = self.score(metrics)

        # 2. Recency bonus from degradation (±15 max)
        # Negative degradation = holdout performed better → positive bonus
        # Positive degradation = holdout performed worse → negative penalty
        recency_bonus = -degradation * 50
        recency_bonus = max(-15, min(15, recency_bonus))

        # 3. Final score (0-100)
        final_score = max(0, min(100, base_score + recency_bonus))

        return final_score

    def _normalize_expectancy(self, expectancy: float, min_val: float = 0, max_val: float = 0.10) -> float:
        """
        Normalize expectancy to 0-1 scale.

        Typical range: 0% to 10% expectancy per trade
        """
        return self._normalize(expectancy, min_val, max_val)

    def _normalize_sharpe(self, sharpe: float, min_val: float = 0, max_val: float = 3.0) -> float:
        """
        Normalize Sharpe ratio to 0-1 scale.

        Typical range: 0 to 3.0
        """
        return self._normalize(sharpe, min_val, max_val)

    def _normalize_drawdown(self, dd: float, max_allowed: float = 0.30) -> float:
        """
        Normalize drawdown to 0-1 scale (lower DD = higher score).

        Args:
            dd: Maximum drawdown as decimal (e.g., 0.15 = 15%)
            max_allowed: Maximum acceptable drawdown (default 30%)

        Returns:
            Score 0-1 where 1 = no drawdown, 0 = max_allowed or worse
        """
        if dd is None or dd <= 0:
            return 1.0  # No drawdown = perfect score
        return max(0.0, 1.0 - (dd / max_allowed))

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
