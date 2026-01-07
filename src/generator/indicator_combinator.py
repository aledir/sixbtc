"""
Indicator Combinator for AI Strategy Generation

Generates unique indicator combinations for AI-based strategies.
Tracks used combinations in database to avoid repetition.

Space: ~112 billion unique combinations
- 6 strategy types × 6 timeframes × 366,145 main combos × 8,516 filter combos
"""

from itertools import combinations
from typing import Optional
from datetime import datetime

from src.utils import get_logger

logger = get_logger(__name__)


# Curated list of pandas_ta indicators suitable for trading strategies
# Excludes utility functions, statistics, and rarely-used indicators
VALID_INDICATORS = [
    # Trend indicators
    'adx', 'aroon', 'cci', 'cmo', 'dpo', 'ema', 'hma', 'kama', 'linreg',
    'macd', 'psar', 'qstick', 'sma', 'supertrend', 't3', 'tema', 'trima',
    'trix', 'vortex', 'wma',

    # Momentum indicators
    'ao', 'apo', 'bias', 'bop', 'brar', 'cfo', 'cg', 'coppock', 'er',
    'fisher', 'inertia', 'kdj', 'kst', 'mom', 'pgo', 'ppo', 'psl',
    'roc', 'rsi', 'rvgi', 'slope', 'smi', 'squeeze', 'stoch', 'stochrsi',
    'tsi', 'uo', 'willr',

    # Volatility indicators
    'aberration', 'accbands', 'atr', 'bbands', 'donchian', 'hwc', 'kc',
    'massi', 'natr', 'pdist', 'rvi', 'thermo', 'true_range', 'ui',

    # Volume indicators
    'ad', 'adosc', 'aobv', 'cmf', 'efi', 'eom', 'kvo', 'mfi', 'nvi',
    'obv', 'pvi', 'pvol', 'pvr', 'pvt', 'vp', 'vwap', 'vwma',

    # Statistics (useful as filters)
    'entropy', 'kurtosis', 'mad', 'median', 'skew', 'stdev', 'variance', 'zscore',
]


class IndicatorCombinator:
    """
    Generates unique indicator combinations for AI strategies.

    Uses pandas_ta indicators, generating combinations of:
    - 2 or 3 main indicators (for signal generation)
    - 0, 1, or 2 filter indicators (for entry confirmation)

    Tracks used combinations to guarantee uniqueness.
    """

    def __init__(self, indicators: Optional[list] = None):
        """
        Initialize combinator with indicator list.

        Args:
            indicators: List of valid indicator names. If None, uses VALID_INDICATORS.
        """
        self.all_indicators = indicators or VALID_INDICATORS
        logger.info(f"IndicatorCombinator initialized with {len(self.all_indicators)} indicators")

    def get_combination(
        self,
        strategy_type: str,
        timeframe: str,
        used_combinations: set
    ) -> Optional[dict]:
        """
        Get an unused indicator combination for the given type/timeframe.

        Args:
            strategy_type: Strategy type (MOM, REV, TRN, etc.)
            timeframe: Timeframe (5m, 15m, 1h, etc.)
            used_combinations: Set of already used combo keys

        Returns:
            {
                'main_indicators': ['rsi', 'macd'],
                'filter_indicators': ['adx'],  # or [] for no filter
            }
            or None if all combinations used
        """
        # Try 2-indicator main combinations first (simpler = better)
        combo = self._find_unused_combo(2, used_combinations)
        if combo:
            return combo

        # Then try 3-indicator main combinations
        combo = self._find_unused_combo(3, used_combinations)
        if combo:
            return combo

        logger.warning(
            f"All indicator combinations used for {strategy_type}/{timeframe}"
        )
        return None

    def _find_unused_combo(
        self,
        n_main: int,
        used_combinations: set
    ) -> Optional[dict]:
        """
        Find an unused combination with n_main main indicators.

        Iterates through:
        - All n_main combinations of main indicators
        - For each: 0, 1, 2 filter indicators

        Returns first unused combination found.
        """
        for main in combinations(self.all_indicators, n_main):
            main_sorted = tuple(sorted(main))

            # Try with 0 filters first
            combo_key = (main_sorted, ())
            if combo_key not in used_combinations:
                return {
                    'main_indicators': list(main),
                    'filter_indicators': [],
                }

            # Try with 1 filter
            remaining = [i for i in self.all_indicators if i not in main]
            for filter_ind in remaining:
                combo_key = (main_sorted, (filter_ind,))
                if combo_key not in used_combinations:
                    return {
                        'main_indicators': list(main),
                        'filter_indicators': [filter_ind],
                    }

            # Try with 2 filters
            for filters in combinations(remaining, 2):
                filters_sorted = tuple(sorted(filters))
                combo_key = (main_sorted, filters_sorted)
                if combo_key not in used_combinations:
                    return {
                        'main_indicators': list(main),
                        'filter_indicators': list(filters),
                    }

        return None

    @staticmethod
    def make_combo_key(main_indicators: list, filter_indicators: list) -> tuple:
        """
        Create a hashable key for a combination.

        Args:
            main_indicators: List of main indicator names
            filter_indicators: List of filter indicator names

        Returns:
            Tuple key: (sorted_main_tuple, sorted_filter_tuple)
        """
        return (
            tuple(sorted(main_indicators)),
            tuple(sorted(filter_indicators))
        )

    def count_total_combinations(self) -> int:
        """
        Count total possible combinations.

        Returns:
            Total number of unique combinations
        """
        n = len(self.all_indicators)

        # Main indicators: C(n,2) + C(n,3)
        from math import comb
        main_2 = comb(n, 2)
        main_3 = comb(n, 3)

        # For each main combo, filter options:
        # - 0 filters: 1
        # - 1 filter: n - n_main (remaining indicators)
        # - 2 filters: C(n - n_main, 2)

        # Simplified estimate (upper bound)
        filter_options = 1 + n + comb(n, 2)

        total = (main_2 + main_3) * filter_options
        return total


def get_indicator_combinator() -> IndicatorCombinator:
    """Factory function to get combinator instance."""
    return IndicatorCombinator()
