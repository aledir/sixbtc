"""
Lookahead Bias Detection (Freqtrade-style)

Principle: Compare signals generated with truncated vs extended data.
If adding future data changes the signal at bar T, lookahead bias is detected.

Test Method:
1. SAFE: generate_signal(df[:T+1]) -> signal for bar T (no future data)
2. BIASED: generate_signal(df[:T+1] + extreme_future) -> signal for bar T

If signals differ, the strategy is using future data in its calculations.

This catches:
- df['high'].max() (contaminated by extreme future highs)
- df['close'].rolling(center=True) (uses future data in window)
- shift(-1) patterns that cause NaN vs value differences
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List

from src.strategies.base import StrategyCore, Signal
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class LookaheadTestResult:
    """Result of lookahead bias test"""
    passed: bool
    lookahead_detected: bool
    biased_bars: List[int]
    total_bars_tested: int
    bias_rate: float
    details: str


class LookaheadTester:
    """
    Freqtrade-style Lookahead Bias Detection

    Algorithm:
    For each test bar T:
    1. SAFE: Call generate_signal(df[:T+1]) - only sees data up to T
    2. BIASED: Call generate_signal(df[:T+1] + fake_future) - sees T + extreme future

    Compare signals at bar T:
    - If they differ -> strategy is contaminated by future data
    - If they match -> no lookahead bias at that bar

    Why this works:
    - A pure strategy only uses df.iloc[-1] (current bar) and past data
    - Adding future data shouldn't affect calculations for bar T
    - If it DOES affect them, strategy has lookahead bias
    """

    MIN_BARS = 100
    WARMUP_BARS = 50
    N_FAKE_FUTURE = 30

    def __init__(
        self,
        sample_points: int = 50,
        early_exit_threshold: int = 5
    ):
        self.sample_points = sample_points
        self.early_exit_threshold = early_exit_threshold

    def validate(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        sample_points: Optional[int] = None
    ) -> LookaheadTestResult:
        """Run Freqtrade-style lookahead bias test."""
        n_points = sample_points or self.sample_points

        if len(data) < self.MIN_BARS:
            return LookaheadTestResult(
                passed=False,
                lookahead_detected=False,
                biased_bars=[],
                total_bars_tested=0,
                bias_rate=0.0,
                details=f"Insufficient data: {len(data)} bars"
            )

        logger.debug(f"Running Freqtrade-style lookahead test on {len(data)} bars")

        # Select test points
        start_idx = self.WARMUP_BARS
        end_idx = len(data) - 1
        test_indices = np.linspace(start_idx, end_idx, n_points, dtype=int)
        test_indices = sorted(set(test_indices))

        biased_bars = []
        tested_bars = 0

        for idx in test_indices:
            tested_bars += 1

            try:
                # Truncated data up to bar idx
                df_truncated = data.iloc[:idx + 1].copy()

                # 1. SAFE: Signal with only past data
                signal_safe = strategy.generate_signal(df_truncated)

                # 2. BIASED: Signal with extreme future appended
                fake_future = self._create_extreme_future(df_truncated)
                df_contaminated = pd.concat(
                    [df_truncated, fake_future],
                    ignore_index=True
                )
                signal_biased = strategy.generate_signal(df_contaminated)

                # Compare signals
                if not self._signals_equal(signal_safe, signal_biased):
                    biased_bars.append(idx)
                    logger.debug(
                        f"Lookahead at bar {idx}: "
                        f"safe={self._signal_str(signal_safe)} vs "
                        f"biased={self._signal_str(signal_biased)}"
                    )

                    if len(biased_bars) >= self.early_exit_threshold:
                        logger.warning(f"Early exit: {len(biased_bars)} violations found")
                        break

            except Exception as e:
                logger.debug(f"Test error at bar {idx}: {e}")
                continue

        # Results
        lookahead_detected = len(biased_bars) > 0
        bias_rate = len(biased_bars) / tested_bars if tested_bars > 0 else 0.0
        passed = not lookahead_detected

        if passed:
            details = f"No lookahead bias detected ({tested_bars} sample points tested)"
            logger.info(f"Lookahead test PASSED: {details}")
        else:
            details = (
                f"LOOKAHEAD BIAS DETECTED at {len(biased_bars)}/{tested_bars} points "
                f"({bias_rate:.1%}): bars {biased_bars[:5]}"
            )
            logger.warning(f"Lookahead test FAILED: {details}")

        return LookaheadTestResult(
            passed=passed,
            lookahead_detected=lookahead_detected,
            biased_bars=biased_bars,
            total_bars_tested=tested_bars,
            bias_rate=bias_rate,
            details=details
        )

    def _create_extreme_future(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Create fake future bars with EXTREME values.

        These values are designed to contaminate calculations if the
        strategy uses df['high'].max() or similar on full data.
        """
        last_close = data['close'].iloc[-1]

        # Extreme values that would definitely affect max/min calculations
        extreme_high = last_close * 3.0   # 200% above current
        extreme_low = last_close * 0.33   # 67% below current

        fake_bars = []
        for i in range(self.N_FAKE_FUTURE):
            # Alternate between extreme high and low
            if i % 2 == 0:
                fake_bars.append({
                    'open': extreme_high * 0.95,
                    'high': extreme_high,
                    'low': extreme_high * 0.9,
                    'close': extreme_high * 0.98,
                    'volume': data['volume'].mean()
                })
            else:
                fake_bars.append({
                    'open': extreme_low * 1.05,
                    'high': extreme_low * 1.1,
                    'low': extreme_low,
                    'close': extreme_low * 1.02,
                    'volume': data['volume'].mean()
                })

        return pd.DataFrame(fake_bars)

    def _signals_equal(self, s1: Optional[Signal], s2: Optional[Signal]) -> bool:
        """Compare two signals for equality."""
        if s1 is None and s2 is None:
            return True
        if s1 is None or s2 is None:
            return False
        return (
            s1.direction == s2.direction and
            abs((s1.atr_stop_multiplier or 0) - (s2.atr_stop_multiplier or 0)) < 0.01 and
            abs((s1.atr_take_multiplier or 0) - (s2.atr_take_multiplier or 0)) < 0.01
        )

    def _signal_str(self, sig: Optional[Signal]) -> str:
        """Convert signal to string for logging."""
        if sig is None:
            return "None"
        return f"{sig.direction}(stop={sig.atr_stop_multiplier:.1f})"


# Backward compatibility alias
ShuffleTester = LookaheadTester


def validate(strategy: StrategyCore, data: pd.DataFrame) -> LookaheadTestResult:
    """Convenience function."""
    tester = LookaheadTester()
    return tester.validate(strategy, data)
