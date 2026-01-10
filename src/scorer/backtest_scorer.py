"""
Backtest Scorer - Unified Score Formula (5 Components)

Calculates composite score for strategy ranking based on:
- Expectancy (edge per trade) - 40%
- Sharpe ratio - 25%
- Win rate - 10%
- Drawdown penalty - 15%
- Recency (OOS vs IS) - 10%

Score Formula:
    Score = 0.40 * expectancy_norm +
            0.25 * sharpe_norm +
            0.10 * win_rate_norm +
            0.15 * drawdown_norm +
            0.10 * recency_norm

All components normalized to 0-100, final score naturally in 0-100 range.
No clamping needed - properly designed formula.
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
                - win_rate: Win rate (0-1)
                - max_drawdown: Maximum drawdown (0-1, lower=better)

        Returns:
            Composite score (0-100 scale)
        """
        # Extract with guards against None values
        expectancy = metrics.get('expectancy', 0) or 0.0
        sharpe = metrics.get('sharpe_ratio', 0) or 0.0
        win_rate = metrics.get('win_rate', 0) or 0.0
        max_drawdown = metrics.get('max_drawdown', 0) or 0.0

        # Normalize each metric to 0-1 scale
        expectancy_score = self._normalize_expectancy(expectancy)
        sharpe_score = self._normalize_sharpe(sharpe)
        win_rate_score = win_rate  # Already 0-1
        drawdown_score = self._normalize_drawdown(max_drawdown)

        # Weighted sum (unified formula)
        score = (
            self.weights['expectancy'] * expectancy_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['win_rate'] * win_rate_score +
            self.weights['drawdown'] * drawdown_score
        )

        # Scale to 0-100
        return min(max(score * 100, 0), 100)

    def score_from_backtest_result(
        self,
        backtest_result,
        degradation: float = 0.0
    ) -> float:
        """
        Calculate score from BacktestResult model using 5-component formula.

        Uses IN-SAMPLE metrics (statistically robust from IS period) + recency (OOS performance).

        Args:
            backtest_result: BacktestResult model instance (must be in-sample period)
            degradation: (is_sharpe - oos_sharpe) / is_sharpe
                         Negative = OOS better, Positive = OOS worse
                         Range typically [-0.5, +0.5]

        Returns:
            Final score (0-100 scale)

        Raises:
            ValueError: If backtest_result is missing required metrics
        """
        if backtest_result.sharpe_ratio is None:
            raise ValueError(
                f"BacktestResult {backtest_result.id} missing IS metrics. "
                f"Re-run backtest to populate fields."
            )

        # Extract in-sample metrics
        expectancy = backtest_result.expectancy or 0.0
        sharpe = backtest_result.sharpe_ratio or 0.0
        win_rate = backtest_result.win_rate or 0.0
        max_drawdown = backtest_result.max_drawdown or 0.0

        # Normalize all 5 components to 0-1 scale
        expectancy_norm = self._normalize_expectancy(expectancy)
        sharpe_norm = self._normalize_sharpe(sharpe)
        win_rate_norm = win_rate  # Already 0-1
        drawdown_norm = self._normalize_drawdown(max_drawdown)

        # Recency: degradation [-0.5, +0.5] → recency_norm [0, 1]
        # -0.5 (OOS much better) → 1.0
        # +0.5 (OOS much worse) → 0.0
        recency_norm = 0.5 - degradation
        recency_norm = min(1.0, max(0.0, recency_norm))

        # 5-component weighted sum (each weight from config)
        score = (
            self.weights['expectancy'] * expectancy_norm +
            self.weights['sharpe'] * sharpe_norm +
            self.weights['win_rate'] * win_rate_norm +
            self.weights['drawdown'] * drawdown_norm +
            self.weights['recency'] * recency_norm
        )

        # Scale to 0-100 (natural range, no clamping needed)
        final_score = score * 100

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
