"""
Lookahead Bias Validator

Detects lookahead bias in strategies using:
1. AST analysis (static code analysis)
2. Shuffle test (empirical validation)
"""

import ast
import numpy as np
import pandas as pd
import scipy.stats
from numba import jit
from typing import Dict, List, Tuple, Optional

from src.strategies.base import StrategyCore
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# NUMBA JIT-COMPILED FUNCTIONS
# =============================================================================

@jit(nopython=True, cache=True)
def _calculate_edge_numba(
    signals: np.ndarray,
    entry_prices: np.ndarray,
    entry_indices: np.ndarray,
    close_prices: np.ndarray,
    exit_bars: int = 10
) -> float:
    """
    JIT-compiled edge calculation.

    Args:
        signals: Array of signal directions (1=long, -1=short)
        entry_prices: Array of entry prices
        entry_indices: Array of bar indices where entries occurred
        close_prices: Full price series
        exit_bars: Number of bars to hold position (default 10)

    Returns:
        Average return per trade
    """
    n_signals = len(signals)
    if n_signals == 0:
        return 0.0

    n_bars = len(close_prices)
    total_return = 0.0

    for i in range(n_signals):
        signal = signals[i]
        entry_price = entry_prices[i]
        entry_idx = entry_indices[i]

        # Exit after exit_bars or at end of data
        exit_idx = min(entry_idx + exit_bars, n_bars - 1)
        exit_price = close_prices[exit_idx]

        # Calculate return
        if signal == 1:  # Long
            ret = (exit_price - entry_price) / entry_price
        else:  # Short
            ret = (entry_price - exit_price) / entry_price

        total_return += ret

    return total_return / n_signals


@jit(nopython=True, cache=True)
def _run_shuffle_iterations_numba(
    signals: np.ndarray,
    entry_prices: np.ndarray,
    entry_indices: np.ndarray,
    close_prices: np.ndarray,
    n_iterations: int,
    exit_bars: int = 10
) -> np.ndarray:
    """
    JIT-compiled shuffle test iterations.

    Runs multiple shuffle iterations efficiently in Numba.

    Args:
        signals: Original signals array
        entry_prices: Entry prices array
        entry_indices: Entry bar indices array
        close_prices: Full price series
        n_iterations: Number of shuffle iterations
        exit_bars: Number of bars to hold position

    Returns:
        Array of shuffled edge values
    """
    n_signals = len(signals)
    shuffled_edges = np.empty(n_iterations, dtype=np.float64)

    # Work with a copy for shuffling
    shuffled_signals = signals.copy()

    for iteration in range(n_iterations):
        # Fisher-Yates shuffle
        for i in range(n_signals - 1, 0, -1):
            j = np.random.randint(0, i + 1)
            shuffled_signals[i], shuffled_signals[j] = shuffled_signals[j], shuffled_signals[i]

        # Calculate edge with shuffled signals
        shuffled_edges[iteration] = _calculate_edge_numba(
            shuffled_signals, entry_prices, entry_indices, close_prices, exit_bars
        )

    return shuffled_edges


class LookaheadValidator:
    """
    Validates strategies for lookahead bias

    Two-stage validation:
    1. AST Check: Fast static analysis for forbidden patterns
    2. Shuffle Test: Slower empirical test for unexpected correlations
    """

    # Forbidden patterns that cause lookahead bias
    FORBIDDEN_PATTERNS = {
        'center_true': "rolling(center=True) - uses future data",
        'negative_shift': "shift(-N) - uses future data",
        'future_max': "expanding(center=True) - uses future data",
        'future_min': "expanding(center=True) - uses future data",
    }

    def validate(
        self,
        strategy: StrategyCore,
        strategy_code: str,
        backtest_data: pd.DataFrame,
        shuffle_iterations: int = 100
    ) -> Dict:
        """
        Run full validation suite

        Args:
            strategy: StrategyCore instance (for shuffle test)
            strategy_code: Source code string (for AST check)
            backtest_data: Historical OHLCV data
            shuffle_iterations: Number of shuffle test iterations

        Returns:
            {
                'ast_check_passed': bool,
                'ast_violations': list[str],
                'shuffle_test_passed': bool,
                'shuffle_p_value': float,
                'passed': bool (overall result)
            }
        """
        logger.info("Running lookahead bias validation")

        results = {}

        # 1. AST Static Analysis
        logger.info("  [1/2] AST static analysis...")
        ast_passed, violations = self._ast_check(strategy_code)

        results['ast_check_passed'] = ast_passed
        results['ast_violations'] = violations

        if not ast_passed:
            logger.warning(f"  AST check FAILED: {len(violations)} violations")
            for violation in violations:
                logger.warning(f"    - {violation}")

            # Skip shuffle test if AST fails
            results['shuffle_test_passed'] = False
            results['shuffle_p_value'] = 1.0
            results['passed'] = False
            return results

        logger.info("  AST check PASSED")

        # 2. Shuffle Test (empirical)
        logger.info(f"  [2/2] Shuffle test ({shuffle_iterations} iterations)...")
        try:
            p_value, test_passed = self._shuffle_test(
                strategy,
                backtest_data,
                shuffle_iterations
            )

            results['shuffle_test_passed'] = test_passed
            results['shuffle_p_value'] = p_value

            if test_passed:
                logger.info(f"  Shuffle test PASSED (p={p_value:.4f})")
            else:
                logger.warning(f"  Shuffle test FAILED (p={p_value:.4f} >= 0.05)")

        except Exception as e:
            logger.error(f"  Shuffle test ERROR: {e}")
            results['shuffle_test_passed'] = False
            results['shuffle_p_value'] = 1.0

        # Overall result
        results['passed'] = results['ast_check_passed'] and results['shuffle_test_passed']

        return results

    def _ast_check(self, code: str) -> Tuple[bool, List[str]]:
        """
        AST-based static code analysis

        Detects forbidden patterns that cause lookahead bias:
        - rolling(center=True)
        - shift(-N) with negative values
        - iloc with negative indexing beyond current bar

        Args:
            code: Python source code string

        Returns:
            (passed, violations) tuple
        """
        violations = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            violations.append(f"Syntax error: {e}")
            return (False, violations)

        # Walk AST and check for violations
        for node in ast.walk(tree):
            # Check: rolling(center=True)
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'rolling':
                    for kw in node.keywords:
                        if kw.arg == 'center':
                            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                violations.append(
                                    "rolling(center=True) detected - uses future data"
                                )

            # Check: shift(-N) with negative values
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'shift':
                    if node.args:
                        arg = node.args[0]

                        # Detect negative constant
                        if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                            if isinstance(arg.operand, ast.Constant):
                                violations.append(
                                    f"shift(-{arg.operand.value}) detected - uses future data"
                                )

                        # Detect negative number directly
                        elif isinstance(arg, ast.Constant) and arg.value < 0:
                            violations.append(
                                f"shift({arg.value}) detected - uses future data"
                            )

            # Check: expanding(center=True) - less common but still wrong
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr == 'expanding':
                    for kw in node.keywords:
                        if kw.arg == 'center' and kw.value.value is True:
                            violations.append(
                                "expanding(center=True) detected - uses future data"
                            )

        passed = len(violations) == 0

        return (passed, violations)

    def _shuffle_test(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        n_iterations: int = 100
    ) -> Tuple[float, bool]:
        """
        Empirical shuffle test for lookahead bias

        Uses Numba JIT-compiled functions for fast shuffle iterations.

        Logic:
        1. Generate signals for entire dataset (real order)
        2. Calculate real edge (expectancy)
        3. Shuffle signals randomly and recalculate edge
        4. Repeat N times to build null distribution
        5. Calculate p-value: Is real edge significantly better than random?

        If p < 0.05: Strategy has predictive power (GOOD)
        If p >= 0.05: Strategy is random/lucky (BAD - likely lookahead)

        Args:
            strategy: StrategyCore instance
            data: Historical OHLCV data
            n_iterations: Number of shuffle iterations

        Returns:
            (p_value, passed) tuple
        """
        logger.debug(f"  Generating signals for {len(data)} candles...")

        # Pre-calculate indicators ONCE on full data (two-phase approach)
        try:
            data_with_indicators = strategy.calculate_indicators(data)
        except Exception as e:
            logger.warning(f"  Failed to calculate indicators: {e}")
            data_with_indicators = data

        # Generate real signals and capture bar indices
        real_signals = []
        real_prices = []
        entry_indices = []

        for i in range(len(data_with_indicators)):
            df_slice = data_with_indicators.iloc[:i+1].copy()
            try:
                signal = strategy.generate_signal(df_slice)
            except Exception:
                continue  # Skip bars where signal generation fails

            if signal and signal.direction in ['long', 'short']:
                real_signals.append(1 if signal.direction == 'long' else -1)
                real_prices.append(data_with_indicators['close'].iloc[i])
                entry_indices.append(i)  # Capture bar index directly

        if len(real_signals) < 10:
            logger.warning("  Too few signals for shuffle test (<10)")
            return (1.0, False)

        # Convert to NumPy arrays for Numba
        signals_arr = np.array(real_signals, dtype=np.int64)
        prices_arr = np.array(real_prices, dtype=np.float64)
        indices_arr = np.array(entry_indices, dtype=np.int64)
        close_arr = data_with_indicators['close'].values.astype(np.float64)

        # Calculate real edge using Numba
        real_edge = _calculate_edge_numba(
            signals_arr, prices_arr, indices_arr, close_arr, 10
        )

        logger.debug(f"  Real edge: {real_edge:.4f} ({len(real_signals)} signals)")

        # Run shuffle iterations using Numba (all in one call)
        logger.debug(f"  Running {n_iterations} shuffle iterations...")

        shuffled_edges = _run_shuffle_iterations_numba(
            signals_arr, prices_arr, indices_arr, close_arr, n_iterations, 10
        )

        # Calculate p-value
        mean_shuffled = np.mean(shuffled_edges)
        std_shuffled = np.std(shuffled_edges)

        if std_shuffled == 0:
            logger.warning("  Shuffle test: zero variance")
            return (1.0, False)

        # Z-score: How many std deviations is real edge from random?
        z_score = (real_edge - mean_shuffled) / std_shuffled

        # P-value: Probability real edge is from random distribution
        p_value = 1 - scipy.stats.norm.cdf(z_score)

        # Pass if p < 0.05 (real edge is significantly better than random)
        passed = p_value < 0.05

        logger.debug(
            f"  Shuffle test: real={real_edge:.4f}, "
            f"shuffled_mean={mean_shuffled:.4f}, "
            f"z={z_score:.2f}, p={p_value:.4f}"
        )

        return (float(p_value), passed)

    def _calculate_simple_edge(
        self,
        signals: List[int],
        entry_prices: List[float],
        price_series: pd.Series,
        entry_indices: Optional[List[int]] = None
    ) -> float:
        """
        Calculate simple edge (expectancy) from signals.

        Note: This method is kept for backward compatibility.
        Internal shuffle test uses Numba-optimized _calculate_edge_numba() directly.

        Args:
            signals: List of signal directions (1=long, -1=short)
            entry_prices: List of entry prices (aligned with signals)
            price_series: Full price series for exits
            entry_indices: Optional pre-computed entry bar indices

        Returns:
            Average return per trade
        """
        if len(signals) == 0:
            return 0.0

        # If entry indices provided, use Numba path
        if entry_indices is not None:
            signals_arr = np.array(signals, dtype=np.int64)
            prices_arr = np.array(entry_prices, dtype=np.float64)
            indices_arr = np.array(entry_indices, dtype=np.int64)
            close_arr = price_series.values.astype(np.float64)
            return _calculate_edge_numba(signals_arr, prices_arr, indices_arr, close_arr, 10)

        # Fallback: Python implementation for backward compatibility
        returns = []

        for i, (signal, entry_price) in enumerate(zip(signals, entry_prices)):
            # Exit after 10 bars or at end of data
            entry_idx = price_series[price_series == entry_price].index[0]
            exit_idx = min(entry_idx + 10, len(price_series) - 1)

            exit_price = price_series.iloc[exit_idx]

            # Calculate return
            if signal == 1:  # Long
                ret = (exit_price - entry_price) / entry_price
            else:  # Short
                ret = (entry_price - exit_price) / entry_price

            returns.append(ret)

        return np.mean(returns) if returns else 0.0


class QuickValidator:
    """
    Quick validator for rapid checks (no shuffle test)

    Use during strategy generation for fast feedback
    """

    @staticmethod
    def quick_check(code: str) -> Tuple[bool, List[str]]:
        """
        Quick AST check only (no shuffle test)

        Args:
            code: Python source code

        Returns:
            (passed, violations) tuple
        """
        validator = LookaheadValidator()
        return validator._ast_check(code)
