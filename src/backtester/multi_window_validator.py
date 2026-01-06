"""
Multi-Window Validation

Validates strategy consistency across multiple non-overlapping time windows.
Used post-scoring to detect overfitting (strategy only works in one period).

Pass criteria:
1. Average Sharpe across windows >= min_avg_sharpe
2. Coefficient of Variation (std/avg) <= max_cv (consistency)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID
import numpy as np

from src.strategies.base import StrategyCore
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.database import get_session
from src.database.models import ValidationCache
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MultiWindowValidator:
    """
    Validates strategy performance consistency across multiple time windows.

    Detects overfitting by checking if strategy performs consistently
    across different market periods, not just the training window.
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

        # Training/holdout config for window sizing
        self.training_days = config['backtesting']['training_days']
        self.holdout_days = config['backtesting']['holdout_days']
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
        timeframe: str,
        base_code_hash: Optional[str] = None
    ) -> Tuple[bool, str, Dict]:
        """
        Validate strategy across multiple time windows.

        Args:
            strategy: StrategyCore instance to validate
            pairs: List of trading pairs (already validated)
            timeframe: Timeframe to test
            base_code_hash: For caching (same base code = same result)

        Returns:
            Tuple of (passed, reason, metrics):
            - passed: True if validation passed
            - reason: Description of result
            - metrics: Dict with avg_sharpe, std_sharpe, cv, window_results
        """
        if not self.enabled:
            return (True, "multi_window_disabled", {})

        # Check cache first (if base_code_hash provided)
        if base_code_hash:
            cached = self._get_cached_result(base_code_hash)
            if cached is not None:
                passed, reason = cached
                logger.debug(
                    f"Multi-window result from cache: {passed} ({reason})"
                )
                return (passed, f"cached:{reason}", {})

        # Generate time windows
        windows = self._generate_windows()

        if len(windows) < 2:
            logger.warning("Not enough data for multi-window validation")
            return (True, "insufficient_data_windows", {})

        # Run backtest on each window
        window_results = []

        for i, (end_offset_days, train_days, holdout_days) in enumerate(windows):
            end_date = datetime.now() - timedelta(days=end_offset_days)

            try:
                # Load data for this window
                training_data, holdout_data = self.data_loader.load_multi_symbol_training_holdout(
                    symbols=pairs,
                    timeframe=timeframe,
                    training_days=train_days,
                    holdout_days=holdout_days,
                    end_date=end_date,
                    target_count=self.max_coins
                )

                if not training_data or len(training_data) < 5:
                    logger.debug(f"Window {i+1}: insufficient data, skipping")
                    continue

                # Run backtest on training period of this window
                result = self.engine.backtest(
                    strategy=strategy,
                    data=training_data,
                    timeframe=timeframe
                )

                if result and result.get('total_trades', 0) > 0:
                    sharpe = result.get('sharpe_ratio', 0) or 0
                    window_results.append({
                        'window': i + 1,
                        'sharpe': sharpe,
                        'trades': result.get('total_trades', 0),
                        'win_rate': result.get('win_rate', 0),
                        'end_date': end_date.strftime('%Y-%m-%d')
                    })
                    logger.debug(
                        f"Window {i+1}: Sharpe={sharpe:.2f}, trades={result.get('total_trades', 0)}"
                    )
                else:
                    logger.debug(f"Window {i+1}: no trades")

            except Exception as e:
                logger.warning(f"Window {i+1} backtest failed: {e}")
                continue

        # Analyze results
        if len(window_results) < 2:
            reason = f"only_{len(window_results)}_windows_with_trades"
            if base_code_hash:
                self._cache_result(base_code_hash, True, reason)
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

        # Cache result
        if base_code_hash:
            self._cache_result(base_code_hash, passed, reason)

        logger.info(
            f"Multi-window validation: {'PASSED' if passed else 'FAILED'} - "
            f"avg_sharpe={avg_sharpe:.2f}, std={std_sharpe:.2f}, cv={cv:.2f} "
            f"({len(window_results)} windows)"
        )

        return (passed, reason, metrics)

    def _generate_windows(self) -> List[Tuple[int, int, int]]:
        """
        Generate time window definitions.

        Returns:
            List of (end_offset_days, training_days, holdout_days) tuples

        Example with 365d training + 30d holdout and 3 windows:
        - Window 1: end=today, train=180d, holdout=30d (most recent)
        - Window 2: end=today-90d, train=180d, holdout=30d
        - Window 3: end=today-180d, train=180d, holdout=30d
        """
        # For multi-window, use shorter training period (180d vs 365d)
        # This allows more non-overlapping windows in the available data
        window_training = 180
        window_holdout = 30
        total_window = window_training + window_holdout

        # Calculate offset between windows to minimize overlap
        # With 365+30 data, we can fit ~3 windows of 180+30 each
        available_data = self.training_days + self.holdout_days  # Total data we have
        window_offset = (available_data - total_window) // (self.n_windows - 1) if self.n_windows > 1 else 0

        # Ensure minimum offset of 30 days between holdout periods
        window_offset = max(window_offset, 30)

        windows = []
        for i in range(self.n_windows):
            end_offset = i * window_offset
            windows.append((end_offset, window_training, window_holdout))

        return windows

    def _get_cached_result(self, base_code_hash: str) -> Optional[Tuple[bool, str]]:
        """
        Check ValidationCache for existing multi-window result.

        Args:
            base_code_hash: Hash of base strategy code

        Returns:
            Tuple of (passed, reason) or None if not cached
        """
        try:
            with get_session() as session:
                cache = session.query(ValidationCache).filter(
                    ValidationCache.code_hash == base_code_hash
                ).first()

                if cache and cache.multi_window_passed is not None:
                    return (cache.multi_window_passed, cache.multi_window_reason or "")
                return None
        except Exception as e:
            logger.debug(f"Cache lookup failed: {e}")
            return None

    def _cache_result(self, base_code_hash: str, passed: bool, reason: str) -> None:
        """
        Save multi-window validation result to cache.

        Args:
            base_code_hash: Hash of base strategy code
            passed: Whether validation passed
            reason: Description of result
        """
        try:
            with get_session() as session:
                cache = session.query(ValidationCache).filter(
                    ValidationCache.code_hash == base_code_hash
                ).first()

                if cache:
                    cache.multi_window_passed = passed
                    cache.multi_window_reason = reason[:200]  # Truncate if needed
                    cache.validated_at = datetime.utcnow()
                else:
                    session.add(ValidationCache(
                        code_hash=base_code_hash,
                        multi_window_passed=passed,
                        multi_window_reason=reason[:200],
                        validated_at=datetime.utcnow()
                    ))
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to cache multi-window result: {e}")
