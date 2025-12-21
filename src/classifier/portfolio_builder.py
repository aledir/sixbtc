"""
Portfolio Builder - Top 10 Strategy Selection

Selects best strategies with diversification constraints.
"""

import logging
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class PortfolioBuilder:
    """
    Selects top strategies with diversification constraints

    Constraints:
    - Maximum N strategies of same type (MOM, REV, etc.)
    - Maximum M strategies on same timeframe
    - Minimum performance thresholds
    - Low correlation (future enhancement)
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize portfolio builder

        Args:
            config: Configuration dict with 'classification' section or diversification directly
        """
        # Support both nested config['classification'] and direct config
        # NO defaults - config must be complete (Fast Fail principle)
        if config:
            if 'classification' in config:
                classification_config = config['classification']
                diversification = classification_config['diversification']
                # Min thresholds from backtesting.thresholds
                self.min_sharpe = config['backtesting']['thresholds']['min_sharpe']
                self.min_win_rate = config['backtesting']['thresholds']['min_win_rate']
            elif 'diversification' in config:
                # Direct config (for tests)
                diversification = config['diversification']
                self.min_sharpe = config['min_sharpe']
                self.min_win_rate = config['min_win_rate']
            else:
                raise ValueError("Config must have 'classification' or 'diversification' section")

            self.max_same_type = diversification['max_same_type']
            self.max_same_timeframe = diversification['max_same_timeframe']
            # max_same_symbol not in current config.yaml, use sensible default
            self.max_same_symbol = diversification.get('max_same_symbol', 2)
        elif config is None:
            # Allow None for unit tests only
            # In production, config is REQUIRED
            self.min_sharpe = 1.0
            self.min_win_rate = 0.55
            self.max_same_type = 3
            self.max_same_timeframe = 3
            self.max_same_symbol = 2
        else:
            raise ValueError("PortfolioBuilder requires config")

        self.min_score = 50  # Minimum composite score

        logger.info(
            f"PortfolioBuilder initialized: max_same_type={self.max_same_type}, "
            f"max_same_timeframe={self.max_same_timeframe}, "
            f"max_same_symbol={self.max_same_symbol}"
        )

    def select_top_10(self, strategies: List[Dict]) -> List[Dict]:
        """
        Select top 10 strategies with diversification

        Args:
            strategies: List of strategy dicts with:
                - score: Composite score
                - type: Strategy type (MOM, REV, etc.)
                - timeframe: Timeframe (15m, 1h, etc.)
                - backtest_sharpe: Sharpe ratio
                - backtest_win_rate: Win rate
                - shuffle_p_value: Shuffle test p-value

        Returns:
            List of up to 10 selected strategies (sorted by score)
        """
        # 1. Filter by minimum thresholds
        eligible = self._filter_eligible(strategies)

        if not eligible:
            logger.warning("No strategies pass minimum thresholds")
            return []

        # 2. Sort by score
        eligible.sort(key=lambda s: s.get('score', 0), reverse=True)

        # 3. Select with diversification constraints
        selected = self._select_with_diversification(eligible, max_count=10)

        logger.info(
            f"Selected {len(selected)}/10 strategies from {len(strategies)} candidates"
        )

        return selected

    def _filter_eligible(self, strategies: List[Dict]) -> List[Dict]:
        """Filter strategies by minimum thresholds"""
        eligible = []

        for strategy in strategies:
            # Get metrics from backtest_results if present
            backtest_results = strategy.get('backtest_results', {})

            # Check all thresholds
            # Support both direct fields and nested backtest_results
            sharpe = strategy.get('backtest_sharpe') or backtest_results.get('sharpe_ratio', 0)
            win_rate = strategy.get('backtest_win_rate') or backtest_results.get('win_rate', 0)

            if (
                strategy.get('score', 0) >= self.min_score and
                sharpe >= self.min_sharpe and
                win_rate >= self.min_win_rate and
                strategy.get('shuffle_p_value', 0.0) < 0.05  # Default to 0.0 (pass if missing)
            ):
                eligible.append(strategy)

        logger.info(f"Filtered {len(eligible)}/{len(strategies)} eligible strategies")
        return eligible

    def _select_with_diversification(
        self,
        strategies: List[Dict],
        max_count: int = 10
    ) -> List[Dict]:
        """
        Select strategies ensuring diversification

        Args:
            strategies: Sorted list (highest score first)
            max_count: Maximum number to select

        Returns:
            Selected strategies
        """
        selected = []
        type_counts = defaultdict(int)
        tf_counts = defaultdict(int)
        symbol_counts = defaultdict(int)

        for strategy in strategies:
            if len(selected) >= max_count:
                break

            strategy_type = strategy.get('type', 'UNKNOWN')
            timeframe = strategy.get('timeframe', 'UNKNOWN')
            symbol = strategy.get('symbol', 'UNKNOWN')

            # Check diversification constraints
            if (
                type_counts[strategy_type] < self.max_same_type and
                tf_counts[timeframe] < self.max_same_timeframe and
                symbol_counts[symbol] < self.max_same_symbol
            ):
                selected.append(strategy)
                type_counts[strategy_type] += 1
                tf_counts[timeframe] += 1
                symbol_counts[symbol] += 1

                logger.debug(
                    f"Selected {strategy.get('name', 'unknown')} "
                    f"(type={strategy_type}, tf={timeframe}, symbol={symbol}, "
                    f"score={strategy.get('score', 0):.1f})"
                )
            else:
                logger.debug(
                    f"Skipped {strategy.get('name', 'unknown')} due to diversification "
                    f"(type_count={type_counts[strategy_type]}, "
                    f"tf_count={tf_counts[timeframe]}, "
                    f"symbol_count={symbol_counts[symbol]})"
                )

        return selected

    def get_portfolio_stats(self, portfolio: List[Dict]) -> Dict:
        """
        Calculate portfolio-level statistics

        Args:
            portfolio: List of selected strategies

        Returns:
            Dictionary with portfolio stats
        """
        if not portfolio:
            return {
                'count': 0,
                'avg_score': 0,
                'avg_sharpe': 0,
                'type_distribution': {},
                'timeframe_distribution': {}
            }

        # Calculate aggregates
        avg_score = sum(s.get('score', 0) for s in portfolio) / len(portfolio)
        avg_sharpe = sum(s.get('backtest_sharpe', 0) for s in portfolio) / len(portfolio)

        # Type distribution
        type_dist = defaultdict(int)
        for s in portfolio:
            type_dist[s.get('type', 'UNKNOWN')] += 1

        # Timeframe distribution
        tf_dist = defaultdict(int)
        for s in portfolio:
            tf_dist[s.get('timeframe', 'UNKNOWN')] += 1

        return {
            'count': len(portfolio),
            'avg_score': avg_score,
            'avg_sharpe': avg_sharpe,
            'type_distribution': dict(type_dist),
            'timeframe_distribution': dict(tf_dist)
        }
