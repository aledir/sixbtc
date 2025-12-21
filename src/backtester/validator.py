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
from typing import Dict, List, Tuple, Optional

from src.strategies.base import StrategyCore
from src.utils.logger import get_logger

logger = get_logger(__name__)


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

        # Generate real signals
        real_signals = []
        real_prices = []

        for i in range(len(data)):
            df_slice = data.iloc[:i+1].copy()
            signal = strategy.generate_signal(df_slice)

            if signal and signal.direction in ['long', 'short']:
                real_signals.append(1 if signal.direction == 'long' else -1)
                real_prices.append(data['close'].iloc[i])

        if len(real_signals) < 10:
            logger.warning("  Too few signals for shuffle test (<10)")
            return (1.0, False)

        # Calculate real edge
        real_edge = self._calculate_simple_edge(real_signals, real_prices, data['close'])

        logger.debug(f"  Real edge: {real_edge:.4f} ({len(real_signals)} signals)")

        # Shuffle test
        logger.debug(f"  Running {n_iterations} shuffle iterations...")

        shuffled_edges = []
        for _ in range(n_iterations):
            # Shuffle signals (breaks temporal relationship)
            shuffled_signals = np.random.permutation(real_signals)

            # Calculate edge with shuffled signals
            shuffled_edge = self._calculate_simple_edge(
                shuffled_signals,
                real_prices,
                data['close']
            )
            shuffled_edges.append(shuffled_edge)

        # Calculate p-value
        shuffled_edges = np.array(shuffled_edges)
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
        price_series: pd.Series
    ) -> float:
        """
        Calculate simple edge (expectancy) from signals

        Args:
            signals: List of signal directions (1=long, -1=short)
            entry_prices: List of entry prices (aligned with signals)
            price_series: Full price series for exits

        Returns:
            Average return per trade
        """
        if len(signals) == 0:
            return 0.0

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
