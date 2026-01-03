"""
Strategy Scorer - Multi-Factor Scoring System

Calculates composite score for strategy ranking based on:
- Edge (expectancy)
- Sharpe ratio
- Consistency (time-in-profit)
- Stability (walk-forward performance)
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class StrategyScorer:
    """
    Calculates composite score for strategy ranking

    Score Formula:
        Score = (0.4 × Edge) + (0.3 × Sharpe) + (0.2 × Consistency) + (0.1 × Stability)

    Normalized to 0-100 scale
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize scorer with weights

        Args:
            config: Configuration dict with 'classification' section
        """
        if config and 'classification' in config:
            # NO defaults - use config values directly (Fast Fail)
            self.weights = config['classification']['score_weights']
            # Load filter thresholds from config (with sensible defaults)
            filter_config = config['classification'].get('filter_thresholds', {})
            self.filter_min_sharpe = filter_config.get('min_sharpe', 0.5)
            self.filter_min_win_rate = filter_config.get('min_win_rate', 0.40)
            self.filter_min_trades = filter_config.get('min_trades', 20)
        elif config and 'score_weights' in config:
            # Direct config (for tests)
            self.weights = config['score_weights']
            self.filter_min_sharpe = config.get('filter_min_sharpe', 0.5)
            self.filter_min_win_rate = config.get('filter_min_win_rate', 0.40)
            self.filter_min_trades = config.get('filter_min_trades', 20)
        elif config is None:
            # Allow None for unit tests only
            # In production, config is REQUIRED
            self.weights = {
                'edge': 0.40,
                'sharpe': 0.30,
                'consistency': 0.20,
                'stability': 0.10
            }
            self.filter_min_sharpe = 0.5
            self.filter_min_win_rate = 0.40
            self.filter_min_trades = 20
        else:
            raise ValueError("StrategyScorer requires config with 'classification.score_weights'")

        logger.info(f"StrategyScorer initialized with weights: {self.weights}")

    def score(self, metrics: Dict[str, float]) -> float:
        """
        Calculate composite score from backtest metrics

        Args:
            metrics: Dictionary containing:
                - expectancy: Edge per trade (0-1 scale)
                - sharpe_ratio: Sharpe ratio
                - consistency: Time-in-profit percentage (0-1)
                - wf_stability: Walk-forward stability (0-1, lower=better)

        Returns:
            Composite score (0-100 scale)
        """
        # Normalize each metric to 0-1 scale
        edge_score = self._normalize_edge(metrics.get('expectancy', 0))
        sharpe_score = self._normalize_sharpe(metrics.get('sharpe_ratio', 0))
        consistency_score = metrics.get('consistency', 0)  # Already 0-1
        stability_score = 1 - metrics.get('wf_stability', 1)  # Lower is better

        # Weighted sum
        score = (
            self.weights['edge'] * edge_score +
            self.weights['sharpe'] * sharpe_score +
            self.weights['consistency'] * consistency_score +
            self.weights['stability'] * stability_score
        )

        # Scale to 0-100
        return min(max(score * 100, 0), 100)

    def score_strategy(self, strategy: Dict) -> float:
        """
        Calculate score for a strategy dict

        This is a convenience wrapper around score() that extracts
        metrics from the strategy dict.

        Args:
            strategy: Strategy dict with 'metrics' or 'backtest_results' key

        Returns:
            Composite score (0-100 scale)
        """
        # Support both 'backtest_results' and 'metrics' keys
        metrics = strategy.get('backtest_results') or strategy.get('metrics', {})
        return self.score(metrics)

    def _normalize_edge(self, edge: float, min_val: float = 0, max_val: float = 0.10) -> float:
        """
        Normalize edge (expectancy) to 0-1 scale

        Typical range: 0% to 10% edge per trade
        """
        return self._normalize(edge, min_val, max_val)

    def _normalize_sharpe(self, sharpe: float, min_val: float = 0, max_val: float = 3.0) -> float:
        """
        Normalize Sharpe ratio to 0-1 scale

        Typical range: 0 to 3.0
        """
        return self._normalize(sharpe, min_val, max_val)

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """
        Normalize value to 0-1 range

        Args:
            value: Value to normalize
            min_val: Minimum expected value
            max_val: Maximum expected value

        Returns:
            Normalized value (0-1)
        """
        if max_val == min_val:
            return 0

        normalized = (value - min_val) / (max_val - min_val)
        return min(max(normalized, 0), 1)  # Clamp to [0, 1]

    def filter_strategies(self, strategies: list[Dict]) -> list[Dict]:
        """
        Filter strategies by minimum thresholds

        Args:
            strategies: List of strategy dicts

        Returns:
            Filtered list passing minimum requirements
        """
        filtered = []

        for strategy in strategies:
            # Get metrics from either 'backtest_results' or 'metrics'
            metrics = strategy.get('backtest_results') or strategy.get('metrics', {})

            # Check minimum thresholds (from config)
            if (
                metrics.get('sharpe_ratio', 0) >= self.filter_min_sharpe and
                metrics.get('win_rate', 0) >= self.filter_min_win_rate and
                metrics.get('total_trades', 0) >= self.filter_min_trades
            ):
                filtered.append(strategy)

        logger.info(f"Filtered {len(filtered)}/{len(strategies)} strategies by minimum thresholds")
        return filtered

    def rank_strategies(self, strategies: list[Dict]) -> list[Dict]:
        """
        Rank strategies by score

        Args:
            strategies: List of strategy dicts with backtest_results

        Returns:
            Sorted list (highest score first)
        """
        # Calculate scores
        for strategy in strategies:
            # Support both 'backtest_results' and 'metrics' keys
            if 'backtest_results' in strategy:
                strategy['score'] = self.score(strategy['backtest_results'])
            elif 'metrics' in strategy:
                strategy['score'] = self.score(strategy['metrics'])
            else:
                strategy['score'] = 0

        # Sort by score (descending)
        return sorted(strategies, key=lambda s: s['score'], reverse=True)
