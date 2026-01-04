"""
Lookahead Bias Detection - Freqtrade-Style Test

This module implements Freqtrade-style lookahead bias detection using the
two-phase strategy architecture (calculate_indicators + generate_signal).

HOW IT WORKS:
For each test bar T, compare indicator values between two runs:
1. BASELINE: calculate_indicators(df[:T+1]) - indicators up to bar T
2. EXTENDED: calculate_indicators(df[:T+1+lookahead]) - indicators with future data

If indicator values at bar T differ between runs, the strategy uses future data
(lookahead bias) in its indicator calculations.

This catches:
- rolling(center=True) - uses future bars in window
- shift(-N) - looks N bars into the future
- Any other operation that uses future data

See: https://www.freqtrade.io/en/stable/lookahead-analysis/
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Dict

from src.strategies.base import StrategyCore, Signal
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class LookaheadTestResult:
    """Result of lookahead bias test"""
    passed: bool
    lookahead_detected: bool
    biased_bars: List[int]
    biased_indicators: List[str] = field(default_factory=list)
    total_bars_tested: int = 0
    bias_rate: float = 0.0
    details: str = ""


class LookaheadTester:
    """
    Freqtrade-Style Lookahead Bias Detector

    Uses the two-phase architecture to compare indicator values:
    1. Calculate indicators on baseline data (df[:T+1])
    2. Calculate indicators on extended data (df[:T+1+lookahead])
    3. Compare indicator values at bar T

    If values differ, the strategy has lookahead bias.

    This is the DEFINITIVE lookahead test that catches any use of future data,
    including subtle cases that AST analysis might miss.
    """

    MIN_BARS = 100
    WARMUP_BARS = 50
    DEFAULT_LOOKAHEAD = 10  # How many future bars to add for extended test

    def __init__(
        self,
        sample_points: int = 10,
        lookahead_bars: int = 10,
        tolerance: float = 1e-9
    ):
        """
        Initialize lookahead tester.

        Args:
            sample_points: Number of test points to sample
            lookahead_bars: Number of future bars to add in extended test
            tolerance: Numerical tolerance for float comparison
        """
        self.sample_points = sample_points
        self.lookahead_bars = lookahead_bars
        self.tolerance = tolerance

    def validate(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        sample_points: Optional[int] = None
    ) -> LookaheadTestResult:
        """
        Run Freqtrade-style lookahead bias test.

        For each test bar T:
        1. Run calculate_indicators(df[:T+1]) -> baseline indicators
        2. Run calculate_indicators(df[:T+1+lookahead]) -> extended indicators
        3. Compare indicator values at bar T between baseline and extended

        If values differ, the strategy uses future data (lookahead bias).

        Args:
            strategy: StrategyCore instance with calculate_indicators() method
            data: Full OHLCV DataFrame
            sample_points: Override default number of test points

        Returns:
            LookaheadTestResult with pass/fail and details
        """
        n_points = sample_points or self.sample_points

        # Validate data
        if len(data) < self.MIN_BARS + self.lookahead_bars:
            return LookaheadTestResult(
                passed=False,
                lookahead_detected=False,
                biased_bars=[],
                total_bars_tested=0,
                bias_rate=0.0,
                details=(
                    f"Insufficient data: {len(data)} bars "
                    f"(need {self.MIN_BARS + self.lookahead_bars})"
                )
            )

        # Get indicator columns from strategy
        indicator_columns = getattr(strategy, 'indicator_columns', [])
        if not indicator_columns:
            logger.warning(
                "Strategy has no indicator_columns defined. "
                "Lookahead test will check all non-OHLCV columns."
            )

        logger.debug(
            f"Running Freqtrade-style lookahead test: "
            f"{len(data)} bars, {n_points} sample points, "
            f"{self.lookahead_bars} lookahead bars"
        )

        # Select test points (leave room for lookahead)
        start_idx = self.WARMUP_BARS
        end_idx = len(data) - self.lookahead_bars - 1
        test_indices = np.linspace(start_idx, end_idx, n_points, dtype=int)
        test_indices = sorted(set(test_indices))

        biased_bars = []
        biased_indicators_set = set()
        tested_bars = 0
        errors = []

        for idx in test_indices:
            tested_bars += 1

            try:
                # BASELINE: Calculate indicators on data up to bar T
                df_baseline = data.iloc[:idx + 1].copy()
                df_baseline_with_indicators = strategy.calculate_indicators(df_baseline)

                # EXTENDED: Calculate indicators on data up to bar T + lookahead
                df_extended = data.iloc[:idx + 1 + self.lookahead_bars].copy()
                df_extended_with_indicators = strategy.calculate_indicators(df_extended)

                # Get columns to check
                if indicator_columns:
                    columns_to_check = indicator_columns
                else:
                    # Check all columns except OHLCV
                    ohlcv_cols = {'open', 'high', 'low', 'close', 'volume', 'timestamp'}
                    columns_to_check = [
                        c for c in df_baseline_with_indicators.columns
                        if c.lower() not in ohlcv_cols
                    ]

                # Compare indicator values at bar T
                for col in columns_to_check:
                    if col not in df_baseline_with_indicators.columns:
                        continue
                    if col not in df_extended_with_indicators.columns:
                        continue

                    # Get values at bar T (last bar of baseline)
                    baseline_value = df_baseline_with_indicators[col].iloc[-1]
                    # Get value at same bar T in extended run
                    extended_value = df_extended_with_indicators[col].iloc[idx]

                    # Compare values
                    if not self._values_equal(baseline_value, extended_value):
                        biased_bars.append(idx)
                        biased_indicators_set.add(col)
                        logger.debug(
                            f"Lookahead detected at bar {idx}, column '{col}': "
                            f"baseline={baseline_value}, extended={extended_value}"
                        )
                        break  # One mismatch is enough to flag this bar

            except Exception as e:
                errors.append(f"Bar {idx}: {str(e)}")
                logger.debug(f"Error at bar {idx}: {e}")
                continue

        # Calculate results
        has_lookahead = len(biased_bars) > 0
        bias_rate = len(biased_bars) / tested_bars if tested_bars > 0 else 0.0
        passed = not has_lookahead and len(errors) == 0

        # Build details message
        if passed:
            details = (
                f"No lookahead bias detected ({tested_bars} bars tested, "
                f"{len(indicator_columns)} indicators checked)"
            )
            logger.info(f"Lookahead test PASSED: {details}")
        else:
            if has_lookahead:
                biased_indicators_list = sorted(biased_indicators_set)
                details = (
                    f"LOOKAHEAD BIAS DETECTED: {len(biased_bars)}/{tested_bars} bars "
                    f"({bias_rate:.1%}) show future data usage. "
                    f"Biased indicators: {biased_indicators_list}"
                )
            else:
                details = f"ERRORS: {len(errors)} execution errors"
            logger.warning(f"Lookahead test FAILED: {details}")

        return LookaheadTestResult(
            passed=passed,
            lookahead_detected=has_lookahead,
            biased_bars=biased_bars,
            biased_indicators=sorted(biased_indicators_set),
            total_bars_tested=tested_bars,
            bias_rate=bias_rate,
            details=details
        )

    def _values_equal(self, v1, v2) -> bool:
        """
        Compare two values for equality with tolerance for floats.

        Args:
            v1: First value
            v2: Second value

        Returns:
            True if values are equal (within tolerance for floats)
        """
        # Handle NaN
        if pd.isna(v1) and pd.isna(v2):
            return True
        if pd.isna(v1) or pd.isna(v2):
            return False

        # Handle numeric types
        try:
            if isinstance(v1, (int, float, np.number)) and isinstance(v2, (int, float, np.number)):
                return abs(float(v1) - float(v2)) < self.tolerance
        except (TypeError, ValueError):
            pass

        # Fallback to equality
        return v1 == v2


class ConsistencyTester:
    """
    Strategy Consistency Tester

    Tests that strategy produces consistent signals (same input -> same output).
    This catches non-deterministic strategies (random, time-based, etc.)

    This is a SUPPLEMENTARY test to the lookahead tester.
    """

    MIN_BARS = 100
    WARMUP_BARS = 50

    def __init__(self, sample_points: int = 20, consistency_runs: int = 2):
        self.sample_points = sample_points
        self.consistency_runs = consistency_runs

    def validate(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        sample_points: Optional[int] = None
    ) -> LookaheadTestResult:
        """
        Run consistency test on strategy.

        For each test bar T:
        1. Calculate indicators on df[:T+1]
        2. Run generate_signal() multiple times
        3. Verify all runs produce the same signal

        This catches non-deterministic strategies.
        """
        n_points = sample_points or self.sample_points

        if len(data) < self.MIN_BARS:
            return LookaheadTestResult(
                passed=False,
                lookahead_detected=False,
                biased_bars=[],
                total_bars_tested=0,
                bias_rate=0.0,
                details=f"Insufficient data: {len(data)} bars (need {self.MIN_BARS})"
            )

        logger.debug(f"Running consistency test on {len(data)} bars")

        # Select test points
        start_idx = self.WARMUP_BARS
        end_idx = len(data) - 1
        test_indices = np.linspace(start_idx, end_idx, n_points, dtype=int)
        test_indices = sorted(set(test_indices))

        inconsistent_bars = []
        tested_bars = 0
        errors = []

        for idx in test_indices:
            tested_bars += 1

            try:
                # Calculate indicators once
                df_slice = data.iloc[:idx + 1].copy()
                df_with_indicators = strategy.calculate_indicators(df_slice)

                # Run generate_signal multiple times
                signals = []
                for _ in range(self.consistency_runs):
                    signal = strategy.generate_signal(df_with_indicators)
                    signals.append(signal)

                # Check consistency
                if not self._all_signals_equal(signals):
                    inconsistent_bars.append(idx)
                    logger.debug(f"Inconsistent signal at bar {idx}")

            except Exception as e:
                errors.append(f"Bar {idx}: {str(e)}")
                logger.debug(f"Error at bar {idx}: {e}")
                continue

        # Results
        has_inconsistency = len(inconsistent_bars) > 0
        inconsistency_rate = len(inconsistent_bars) / tested_bars if tested_bars > 0 else 0.0
        passed = not has_inconsistency and len(errors) == 0

        if passed:
            details = f"Strategy is consistent ({tested_bars} points tested)"
            logger.info(f"Consistency test PASSED: {details}")
        else:
            if has_inconsistency:
                details = (
                    f"INCONSISTENT: {len(inconsistent_bars)}/{tested_bars} points "
                    f"({inconsistency_rate:.1%}) produced different signals"
                )
            else:
                details = f"ERRORS: {len(errors)} execution errors"
            logger.warning(f"Consistency test FAILED: {details}")

        return LookaheadTestResult(
            passed=passed,
            lookahead_detected=False,
            biased_bars=inconsistent_bars,
            total_bars_tested=tested_bars,
            bias_rate=inconsistency_rate,
            details=details
        )

    def _all_signals_equal(self, signals: List[Optional[Signal]]) -> bool:
        """Check if all signals in list are equal."""
        if len(signals) < 2:
            return True
        first = signals[0]
        for sig in signals[1:]:
            if not self._signals_equal(first, sig):
                return False
        return True

    def _signals_equal(self, s1: Optional[Signal], s2: Optional[Signal]) -> bool:
        """Compare two signals for equality."""
        if s1 is None and s2 is None:
            return True
        if s1 is None or s2 is None:
            return False
        return s1.direction == s2.direction


# Backward compatibility aliases
ShuffleTester = LookaheadTester


def validate(strategy: StrategyCore, data: pd.DataFrame) -> LookaheadTestResult:
    """
    Run full lookahead validation (Freqtrade-style).

    This is the recommended validation function that tests:
    1. Lookahead bias (comparing indicator values between baseline and extended)
    2. Signal consistency (same input -> same output)

    Args:
        strategy: StrategyCore instance
        data: Full OHLCV DataFrame

    Returns:
        LookaheadTestResult with pass/fail and details
    """
    tester = LookaheadTester()
    return tester.validate(strategy, data)


def validate_consistency(strategy: StrategyCore, data: pd.DataFrame) -> LookaheadTestResult:
    """
    Run consistency validation only.

    Args:
        strategy: StrategyCore instance
        data: OHLCV DataFrame

    Returns:
        LookaheadTestResult
    """
    tester = ConsistencyTester()
    return tester.validate(strategy, data)
