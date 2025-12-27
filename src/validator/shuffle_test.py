"""
Future Contamination Test - Phase 3 of validation pipeline

Empirical test for lookahead bias detection.

Logic:
1. For each decision point T, provide data ONLY up to T
2. Record the signal generated
3. Append FAKE future data (random) after T
4. Run strategy again with fake future appended
5. If signal CHANGES based on fake future data -> LOOKAHEAD DETECTED!

A correctly implemented strategy should ONLY use past data.
If changing future data changes the signal, the strategy is peeking ahead.

This is a DIRECT test of lookahead bias - if the strategy accesses
any data after the "current" bar, the fake future will contaminate it.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Tuple

from src.strategies.base import StrategyCore, Signal
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class LookaheadTestResult:
    """Result of lookahead bias test"""
    passed: bool
    lookahead_detected: bool
    contaminated_bars: List[int]  # Bar indices where lookahead was detected
    total_bars_tested: int
    contamination_rate: float  # Percentage of bars with lookahead
    details: str


class ShuffleTester:
    """
    Phase 3: Future Contamination Test for lookahead bias

    This test DIRECTLY detects if a strategy uses future data by:
    1. Running strategy with real data only (up to current bar)
    2. Running strategy with fake future appended
    3. If signals differ, the strategy is accessing future data

    This catches:
    - shift(-1) or negative shifts
    - rolling(center=True)
    - Any operation that reads beyond "current" bar
    - Accidental full-column operations (.max(), .min(), etc.)
    """

    # Configuration
    MIN_BARS_REQUIRED = 100  # Minimum bars needed for testing
    SAMPLE_POINTS = 50  # Number of points to test (for performance)
    FAKE_FUTURE_BARS = 20  # How many fake future bars to append
    N_RANDOM_FUTURES = 3  # Number of different random futures to test

    def __init__(
        self,
        sample_points: int = SAMPLE_POINTS,
        fake_future_bars: int = FAKE_FUTURE_BARS,
        n_random_futures: int = N_RANDOM_FUTURES
    ):
        """
        Initialize the tester.

        Args:
            sample_points: Number of time points to test
            fake_future_bars: Number of fake future bars to append
            n_random_futures: Number of different random futures per point
        """
        self.sample_points = sample_points
        self.fake_future_bars = fake_future_bars
        self.n_random_futures = n_random_futures

    def validate(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        sample_points: Optional[int] = None
    ) -> LookaheadTestResult:
        """
        Run lookahead bias test on strategy.

        Args:
            strategy: StrategyCore instance to test
            data: Historical OHLCV data
            sample_points: Override default sample points

        Returns:
            LookaheadTestResult with pass/fail and details
        """
        n_points = sample_points or self.sample_points

        if len(data) < self.MIN_BARS_REQUIRED:
            logger.warning(
                f"Insufficient data for lookahead test: {len(data)} < {self.MIN_BARS_REQUIRED}"
            )
            return LookaheadTestResult(
                passed=False,
                lookahead_detected=False,
                contaminated_bars=[],
                total_bars_tested=0,
                contamination_rate=0.0,
                details=f"Insufficient data: {len(data)} bars"
            )

        # Select test points (evenly spaced through data)
        # Skip first 50 bars (need history) and last fake_future_bars
        start_idx = 50
        end_idx = len(data) - self.fake_future_bars - 1

        if end_idx <= start_idx:
            return LookaheadTestResult(
                passed=False,
                lookahead_detected=False,
                contaminated_bars=[],
                total_bars_tested=0,
                contamination_rate=0.0,
                details="Data range too small for testing"
            )

        # Sample test indices
        test_indices = np.linspace(start_idx, end_idx, n_points, dtype=int)
        test_indices = list(set(test_indices))  # Remove duplicates

        contaminated_bars = []
        tested_bars = 0

        logger.debug(f"Testing {len(test_indices)} points for lookahead bias")

        for idx in test_indices:
            is_contaminated = self._test_single_point(strategy, data, idx)
            tested_bars += 1

            if is_contaminated:
                contaminated_bars.append(idx)
                logger.debug(f"Lookahead detected at bar {idx}")

                # Early exit: if we find lookahead, no need to test more
                if len(contaminated_bars) >= 3:
                    logger.warning(
                        f"Multiple lookahead violations detected, stopping early"
                    )
                    break

        # Calculate results
        lookahead_detected = len(contaminated_bars) > 0
        contamination_rate = len(contaminated_bars) / tested_bars if tested_bars > 0 else 0.0
        passed = not lookahead_detected

        if passed:
            details = f"No lookahead bias detected in {tested_bars} test points"
            logger.info(f"Lookahead test PASSED: {details}")
        else:
            details = (
                f"LOOKAHEAD BIAS DETECTED at {len(contaminated_bars)} points: "
                f"{contaminated_bars[:5]}{'...' if len(contaminated_bars) > 5 else ''}"
            )
            logger.warning(f"Lookahead test FAILED: {details}")

        return LookaheadTestResult(
            passed=passed,
            lookahead_detected=lookahead_detected,
            contaminated_bars=contaminated_bars,
            total_bars_tested=tested_bars,
            contamination_rate=contamination_rate,
            details=details
        )

    def _test_single_point(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        current_idx: int
    ) -> bool:
        """
        Test a single point for lookahead bias.

        Returns True if lookahead is detected (signal changes with fake future).
        """
        # Get data up to current point (this is what strategy SHOULD see)
        df_past_only = data.iloc[:current_idx + 1].copy()

        # Generate signal with past data only
        try:
            signal_past_only = strategy.generate_signal(df_past_only)
        except Exception as e:
            logger.debug(f"Signal generation failed at idx {current_idx}: {e}")
            return False  # Can't test if signal generation fails

        # Normalize signal for comparison
        signal_past_only_normalized = self._normalize_signal(signal_past_only)

        # Test with multiple different fake futures
        for i in range(self.n_random_futures):
            # Generate fake future data
            fake_future = self._generate_fake_future(df_past_only, self.fake_future_bars)

            # Append fake future to past data
            df_with_fake_future = pd.concat([df_past_only, fake_future], ignore_index=True)

            # Generate signal with fake future appended
            try:
                signal_with_future = strategy.generate_signal(df_with_fake_future)
            except Exception as e:
                logger.debug(f"Signal generation with future failed: {e}")
                continue

            signal_with_future_normalized = self._normalize_signal(signal_with_future)

            # Compare signals
            if signal_past_only_normalized != signal_with_future_normalized:
                logger.debug(
                    f"Signal changed at idx {current_idx}: "
                    f"{signal_past_only_normalized} -> {signal_with_future_normalized}"
                )
                return True  # Lookahead detected!

        return False  # No lookahead detected at this point

    def _normalize_signal(self, signal: Optional[Signal]) -> str:
        """Convert signal to comparable string representation."""
        if signal is None:
            return "NONE"
        if not isinstance(signal, Signal):
            return "INVALID"
        return f"{signal.direction}_{signal.atr_stop_multiplier}_{signal.atr_take_multiplier}"

    def _generate_fake_future(self, past_data: pd.DataFrame, n_bars: int) -> pd.DataFrame:
        """
        Generate fake future data using random walk from last price.

        The fake data should be plausible (realistic volatility) but random,
        so if a strategy uses it, the results will change.
        """
        if len(past_data) == 0:
            raise ValueError("Cannot generate fake future from empty data")

        last_row = past_data.iloc[-1]
        last_close = last_row['close']
        last_volume = past_data['volume'].mean()

        # Calculate realistic volatility from past data
        returns = past_data['close'].pct_change().dropna()
        volatility = returns.std() if len(returns) > 0 else 0.02

        # Generate random future
        fake_data = []
        current_price = last_close

        for i in range(n_bars):
            # Random return with realistic volatility
            ret = np.random.normal(0, volatility)
            current_price = current_price * (1 + ret)

            # Random OHLC around the close
            intrabar_vol = volatility * 0.5
            open_price = current_price * (1 + np.random.normal(0, intrabar_vol))
            high_price = max(open_price, current_price) * (1 + abs(np.random.normal(0, intrabar_vol)))
            low_price = min(open_price, current_price) * (1 - abs(np.random.normal(0, intrabar_vol)))

            # Random volume
            volume = last_volume * (0.5 + np.random.random())

            fake_data.append({
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': current_price,
                'volume': volume
            })

        fake_df = pd.DataFrame(fake_data)

        # Add timestamp if original data has it
        if 'timestamp' in past_data.columns:
            # Just create sequential timestamps (they won't matter for the test)
            last_ts = past_data['timestamp'].iloc[-1]
            if isinstance(last_ts, pd.Timestamp):
                fake_df['timestamp'] = pd.date_range(
                    start=last_ts + pd.Timedelta(minutes=15),
                    periods=n_bars,
                    freq='15min'
                )

        return fake_df


# Backward compatibility alias
def validate(strategy: StrategyCore, data: pd.DataFrame) -> LookaheadTestResult:
    """Convenience function for validation."""
    tester = ShuffleTester()
    return tester.validate(strategy, data)
