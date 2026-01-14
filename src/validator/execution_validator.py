"""
Execution Validator - Phase 4 of validation pipeline

Runtime validation:
1. Strategy can be instantiated
2. generate_signal executes without errors
3. Signal output is valid format
4. Strategy doesn't crash on edge cases
"""

import importlib.util
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import numpy as np
import pandas as pd

from src.strategies.base import StrategyCore, Signal
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionValidationResult:
    """Result of execution validation"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    signals_generated: int
    execution_time_ms: float


class ExecutionValidator:
    """
    Phase 4: Runtime execution validation

    Tests that the strategy actually works when executed:
    - Can be loaded as a Python module
    - Can be instantiated
    - generate_signal() executes without errors
    - Returns valid Signal objects (or None)
    """

    # Edge case test data sizes
    EDGE_CASE_SIZES = [0, 1, 5, 10, 50, 100, 500]

    def __init__(self, timeout_seconds: float = 30.0):
        """
        Initialize ExecutionValidator.

        Args:
            timeout_seconds: Maximum time for validation (not yet implemented)
        """
        self.timeout_seconds = timeout_seconds

    def validate(
        self,
        code: str,
        class_name: str,
        test_data: Optional[pd.DataFrame] = None
    ) -> ExecutionValidationResult:
        """
        Run execution validation on strategy code.

        Args:
            code: Python source code string
            class_name: Expected class name in the code
            test_data: Optional test data (generates synthetic if None)

        Returns:
            ExecutionValidationResult with pass/fail and details
        """
        import time
        start_time = time.time()

        errors = []
        warnings = []
        signals_generated = 0

        # Phase 4a: Load strategy as module
        strategy_class = self._load_strategy_class(code, class_name)

        if strategy_class is None:
            errors.append("Failed to load strategy class from code")
            return ExecutionValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                signals_generated=0,
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # Phase 4b: Instantiate strategy
        try:
            strategy = strategy_class()
        except Exception as e:
            errors.append(f"Failed to instantiate strategy: {e}")
            return ExecutionValidationResult(
                passed=False,
                errors=errors,
                warnings=warnings,
                signals_generated=0,
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # Phase 4c: Test generate_signal on regular data
        if test_data is not None:
            data = test_data
        else:
            data = self._generate_test_data(500)

        try:
            signal_count, signal_errors = self._test_signal_generation(strategy, data)
            signals_generated = signal_count
            errors.extend(signal_errors)
        except Exception as e:
            errors.append(f"Signal generation test failed: {e}")
            logger.error(f"Signal generation error: {traceback.format_exc()}")

        # Phase 4d: Test edge cases
        edge_case_warnings = self._test_edge_cases(strategy)
        warnings.extend(edge_case_warnings)

        # Phase 4e: Check signal quality
        if signals_generated == 0:
            warnings.append("Strategy generated 0 signals on test data")
        elif signals_generated < 5:
            warnings.append(f"Strategy generated very few signals ({signals_generated})")

        passed = len(errors) == 0
        execution_time_ms = (time.time() - start_time) * 1000

        if passed:
            logger.debug(
                f"Execution validation PASSED: {signals_generated} signals, "
                f"{execution_time_ms:.1f}ms"
            )
        else:
            logger.warning(f"Execution validation FAILED: {errors}")

        return ExecutionValidationResult(
            passed=passed,
            errors=errors,
            warnings=warnings,
            signals_generated=signals_generated,
            execution_time_ms=execution_time_ms
        )

    def _load_strategy_class(self, code: str, class_name: str) -> Optional[type]:
        """
        Load strategy class from code string.

        Args:
            code: Python source code
            class_name: Class name to extract

        Returns:
            Strategy class type or None if failed
        """
        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                temp_path = Path(f.name)

            # Load as module
            spec = importlib.util.spec_from_file_location(
                f"temp_strategy_{class_name}",
                temp_path
            )

            if spec is None or spec.loader is None:
                logger.error("Failed to create module spec")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module

            try:
                spec.loader.exec_module(module)
            except Exception as e:
                logger.error(f"Failed to execute module: {e}")
                return None
            finally:
                # Clean up temp file
                temp_path.unlink(missing_ok=True)

            # Get class from module
            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                if isinstance(cls, type) and issubclass(cls, StrategyCore):
                    return cls

            logger.error(f"Class {class_name} not found or not StrategyCore subclass")
            return None

        except Exception as e:
            logger.error(f"Failed to load strategy class: {e}")
            return None

    def _test_signal_generation(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame
    ) -> tuple[int, List[str]]:
        """
        Test generate_signal on data.

        Uses two-phase approach: calculate_indicators() then generate_signal().

        Returns:
            Tuple of (signal_count, errors)
        """
        errors = []
        signal_count = 0

        # Test at various points in the data
        # Respect strategy's LOOKBACK requirement (some indicators need 60+ bars)
        lookback = getattr(strategy, 'LOOKBACK', 50)
        min_test_point = max(lookback + 10, 50)  # At least LOOKBACK + buffer
        test_points = [min_test_point, 100, 200, 300, len(data) - 1]

        for i in test_points:
            if i >= len(data):
                continue

            df_slice = data.iloc[:i+1].copy()

            try:
                # Phase 1: Calculate indicators (required before generate_signal)
                df_with_indicators = strategy.calculate_indicators(df_slice)

                # Phase 2: Generate signal from pre-calculated indicators
                signal = strategy.generate_signal(df_with_indicators)

                # Validate signal format
                if signal is not None:
                    if not isinstance(signal, Signal):
                        errors.append(
                            f"generate_signal returned {type(signal).__name__}, "
                            "expected Signal or None"
                        )
                    elif signal.direction not in ['long', 'short', 'close']:
                        errors.append(
                            f"Invalid signal direction: {signal.direction}"
                        )
                    else:
                        signal_count += 1

            except Exception as e:
                errors.append(f"generate_signal raised exception at bar {i}: {e}")

        return signal_count, errors

    def _test_edge_cases(self, strategy: StrategyCore) -> List[str]:
        """
        Test strategy on edge case data.

        Uses two-phase approach: calculate_indicators() then generate_signal().

        Returns:
            List of warnings (not errors)
        """
        warnings = []

        for size in self.EDGE_CASE_SIZES:
            data = self._generate_test_data(size)

            try:
                if size > 0:
                    # Two-phase approach
                    df_with_indicators = strategy.calculate_indicators(data)
                    signal = strategy.generate_signal(df_with_indicators)
                    # Edge case handling is OK as long as it doesn't crash
            except Exception as e:
                warnings.append(
                    f"Strategy raised exception on {size}-bar data: {type(e).__name__}"
                )

        return warnings

    def _generate_test_data(self, n_bars: int) -> pd.DataFrame:
        """
        Generate synthetic OHLCV test data.

        Args:
            n_bars: Number of bars to generate

        Returns:
            DataFrame with OHLCV columns
        """
        if n_bars == 0:
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])

        np.random.seed(42)  # Reproducible

        # Generate random walk for close prices
        returns = np.random.randn(n_bars) * 0.02  # 2% daily vol
        close = 50000 * np.cumprod(1 + returns)  # Start at 50k (like BTC)

        # Generate OHLC from close
        high = close * (1 + np.abs(np.random.randn(n_bars) * 0.01))
        low = close * (1 - np.abs(np.random.randn(n_bars) * 0.01))
        open_price = close * (1 + np.random.randn(n_bars) * 0.005)

        # Ensure high >= close and low <= close
        high = np.maximum(high, close)
        low = np.minimum(low, close)
        high = np.maximum(high, open_price)
        low = np.minimum(low, open_price)

        volume = np.random.uniform(100, 1000, n_bars)

        return pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })
