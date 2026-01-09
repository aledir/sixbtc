"""
Multi-Window Validation

Validates strategy consistency across multiple non-overlapping time windows.
Used post-scoring to detect overfitting (strategy only works in one period).

Pass criteria:
1. Average Sharpe across windows >= min_avg_sharpe
2. Coefficient of Variation (std/avg) <= max_cv (consistency)
"""

from datetime import datetime, timedelta, UTC
from typing import Dict, List, Tuple
import numpy as np

from src.strategies.base import StrategyCore
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MultiWindowValidator:
    """
    Validates strategy performance consistency across multiple time windows.

    Detects overfitting by checking if strategy performs consistently
    across different market periods, not just the in-sample window.
    """

    def __init__(self, config: dict):
        """
        Initialize multi-window validator.

        Args:
            config: Configuration dict with backtesting.multi_window section
        """
        self.config = config

        # Multi-window config (Fast Fail - no defaults)
        mw_config = config['backtesting']['multi_window']
        self.enabled = mw_config['enabled']
        self.n_windows = mw_config['windows']
        self.min_avg_sharpe = mw_config['min_avg_sharpe']
        self.max_cv = mw_config['max_cv']

        # IS/OOS config for window sizing
        self.is_days = config['backtesting']['is_days']
        self.oos_days = config['backtesting']['oos_days']
        self.max_coins = config['backtesting']['max_coins']

        # Components
        self.engine = BacktestEngine(config)
        cache_dir = config['directories']['data'] + '/binance'
        self.data_loader = BacktestDataLoader(cache_dir)

        logger.info(
            f"MultiWindowValidator initialized: {self.n_windows} windows, "
            f"min_avg_sharpe={self.min_avg_sharpe}, max_cv={self.max_cv}"
        )

    def validate(
        self,
        strategy: StrategyCore,
        pairs: List[str],
        timeframe: str
    ) -> Tuple[bool, str, Dict]:
        """
        Validate strategy across multiple time windows.

        Each strategy is tested independently - no caching by base_code_hash
        because consistency depends on parameters, not just base code.

        Args:
            strategy: StrategyCore instance to validate
            pairs: List of trading pairs (already validated)
            timeframe: Timeframe to test

        Returns:
            Tuple of (passed, reason, metrics):
            - passed: True if validation passed
            - reason: Description of result
            - metrics: Dict with avg_sharpe, std_sharpe, cv, window_results
        """
        if not self.enabled:
            return (True, "multi_window_disabled", {})

        # Generate time windows
        windows = self._generate_windows()

        if len(windows) < 2:
            logger.warning("Not enough data for multi-window validation")
            return (True, "insufficient_data_windows", {})

        # Run backtest on each window
        window_results = []

        for i, (start_offset_days, window_days) in enumerate(windows):
            # end_date = end of window = today - (start_offset - window_days)
            end_date = datetime.now(UTC) - timedelta(days=start_offset_days - window_days)
            period_desc = f"{start_offset_days}d-{start_offset_days - window_days}d ago"

            try:
                # Load data for this window (no IS/OOS split needed)
                window_data = self.data_loader.load_multi_symbol(
                    symbols=pairs,
                    timeframe=timeframe,
                    days=window_days,
                    end_date=end_date,
                    target_count=self.max_coins
                )

                if not window_data:
                    logger.debug(f"Window {i+1} ({period_desc}): no data loaded, skipping")
                    continue

                # Run backtest on this window
                result = self.engine.backtest(
                    strategy=strategy,
                    data=window_data,
                    timeframe=timeframe
                )

                if result and result.get('total_trades', 0) > 0:
                    sharpe = result.get('sharpe_ratio', 0) or 0
                    window_results.append({
                        'window': i + 1,
                        'sharpe': sharpe,
                        'trades': result.get('total_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'period': period_desc
                    })
                    logger.debug(
                        f"Window {i+1} ({period_desc}): Sharpe={sharpe:.2f}, "
                        f"trades={result.get('total_trades', 0)}"
                    )
                else:
                    logger.debug(f"Window {i+1} ({period_desc}): no trades")

            except Exception as e:
                logger.warning(f"Window {i+1} ({period_desc}) backtest failed: {e}")
                continue

        # Analyze results
        if len(window_results) < 2:
            reason = f"only_{len(window_results)}_windows_with_trades"
            return (True, reason, {'window_results': window_results})

        # Calculate statistics
        sharpes = [w['sharpe'] for w in window_results]
        avg_sharpe = float(np.mean(sharpes))
        std_sharpe = float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0

        # Coefficient of variation (avoid division by zero)
        if avg_sharpe > 0:
            cv = std_sharpe / avg_sharpe
        else:
            cv = float('inf') if std_sharpe > 0 else 0.0

        metrics = {
            'avg_sharpe': avg_sharpe,
            'std_sharpe': std_sharpe,
            'cv': cv,
            'n_windows': len(window_results),
            'window_results': window_results
        }

        # Check pass criteria
        passed = True
        reason_parts = []

        if avg_sharpe < self.min_avg_sharpe:
            passed = False
            reason_parts.append(f"avg_sharpe={avg_sharpe:.2f}<{self.min_avg_sharpe}")

        if cv > self.max_cv:
            passed = False
            reason_parts.append(f"cv={cv:.2f}>{self.max_cv}")

        if passed:
            reason = f"passed:avg={avg_sharpe:.2f},cv={cv:.2f}"
        else:
            reason = ";".join(reason_parts)

        logger.info(
            f"Multi-window validation: {'PASSED' if passed else 'FAILED'} - "
            f"avg_sharpe={avg_sharpe:.2f}, std={std_sharpe:.2f}, cv={cv:.2f} "
            f"({len(window_results)} windows)"
        )

        return (passed, reason, metrics)

    def _generate_windows(self) -> List[Tuple[int, int]]:
        """
        Divide the backtest period into N non-overlapping windows.

        Instead of looking further back in time (which causes 0 symbols),
        we divide the SAME period used by the main backtest into N windows.

        Example with 150d total (120 IS + 30 OOS) and 4 windows:
        - Each window = 37.5d
        - Window 1: oldest (150d-112.5d ago)
        - Window 4: most recent (37.5d-0d ago)

        Returns:
            List of (start_offset_days, window_days) tuples
            - start_offset_days: days from today to START of window
            - window_days: duration of the window
        """
        total_days = self.is_days + self.oos_days
        window_days = total_days // self.n_windows

        windows = []
        for i in range(self.n_windows):
            # i=0: oldest window, i=n-1: most recent window
            start_offset = total_days - (i * window_days)
            windows.append((start_offset, window_days))

        logger.debug(
            f"Generated {self.n_windows} windows of {window_days}d each "
            f"covering {total_days}d total"
        )

        return windows
