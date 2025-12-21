"""
Walk-Forward Optimizer

Parameter optimization with walk-forward validation to prevent overfitting.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.strategies.base import StrategyCore
from src.backtester.vectorbt_engine import VectorBTBacktester
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WalkForwardOptimizer:
    """
    Walk-Forward parameter optimization

    Prevents overfitting by:
    1. Splitting data into expanding train/test windows
    2. Optimizing on train, validating on test
    3. Checking parameter stability across windows
    4. Rejecting if parameters vary too much (overfitting indicator)
    """

    def __init__(self, backtester: Optional[VectorBTBacktester] = None):
        """
        Initialize optimizer

        Args:
            backtester: VectorBT backtester instance (creates new if None)
        """
        self.backtester = backtester or VectorBTBacktester()

    def optimize(
        self,
        strategy_class: type,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        n_windows: int = 4,
        train_pct: float = 0.75,
        metric: str = 'sharpe_ratio',
        min_metric_value: float = 1.0,
        max_cv: float = 0.30
    ) -> Optional[Dict]:
        """
        Walk-forward optimization with stability check

        Args:
            strategy_class: StrategyCore class (not instance!)
            data: Historical OHLCV data
            param_grid: Dict mapping param_name → list of values to try
            n_windows: Number of walk-forward windows
            train_pct: Initial train/test split ratio
            metric: Metric to optimize ('sharpe_ratio', 'expectancy', etc.)
            min_metric_value: Minimum acceptable metric value
            max_cv: Maximum coefficient of variation for parameter stability

        Returns:
            Best parameters dict if stable, None if unstable/poor performance
        """
        logger.info(f"Walk-forward optimization: {n_windows} windows, metric={metric}")

        # Create walk-forward windows
        windows = self._create_windows(data, n_windows, train_pct)

        # Store best params per window
        params_per_window = []
        metrics_per_window = []

        for i, (train_data, test_data) in enumerate(windows):
            logger.info(f"Window {i+1}/{n_windows}: {len(train_data)} train, {len(test_data)} test")

            # Grid search on train set
            best_params = self._grid_search(
                strategy_class,
                train_data,
                param_grid,
                metric
            )

            if best_params is None:
                logger.warning(f"  No valid params found for window {i+1}")
                return None

            logger.info(f"  Train best: {best_params}")

            # Validate on test set (out-of-sample)
            test_metrics = self._test_params(
                strategy_class,
                test_data,
                best_params
            )

            logger.info(f"  Test {metric}: {test_metrics[metric]:.3f}")

            # Check minimum performance threshold
            if test_metrics[metric] < min_metric_value:
                logger.warning(
                    f"  Test {metric} below threshold "
                    f"({test_metrics[metric]:.3f} < {min_metric_value})"
                )
                return None

            params_per_window.append(best_params)
            metrics_per_window.append(test_metrics[metric])

        # Check parameter stability across windows
        is_stable, cv_values = self._check_stability(params_per_window, max_cv)

        if not is_stable:
            logger.warning(f"  Parameters UNSTABLE (CV > {max_cv}): {cv_values}")
            return None

        logger.info(f"  Parameters STABLE (CV: {cv_values})")

        # Return average parameters
        final_params = self._average_params(params_per_window)

        # Calculate stability metrics
        final_params['_wf_worst_window'] = min(metrics_per_window)
        final_params['_wf_stability'] = 1.0 - np.std(metrics_per_window) / np.mean(metrics_per_window)

        logger.info(f"Final params: {final_params}")

        return final_params

    def _create_windows(
        self,
        data: pd.DataFrame,
        n_windows: int,
        train_pct: float
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Create expanding walk-forward windows

        Example with 4 windows (75% initial split):
        Window 1: [0:75%] train, [75:81%] test
        Window 2: [0:81%] train, [81:87%] test
        Window 3: [0:87%] train, [87:93%] test
        Window 4: [0:93%] train, [93:100%] test

        Args:
            data: Full dataset
            n_windows: Number of windows
            train_pct: Initial train percentage (0.75 = 75%)

        Returns:
            List of (train_df, test_df) tuples
        """
        total_len = len(data)
        windows = []

        for i in range(n_windows):
            # Expanding train set
            train_end_pct = train_pct + (i * (1 - train_pct) / n_windows)
            train_end = int(total_len * train_end_pct)

            # Test set follows train
            test_end_pct = train_end_pct + ((1 - train_pct) / n_windows)
            test_end = int(total_len * test_end_pct)

            train_df = data.iloc[:train_end].copy()
            test_df = data.iloc[train_end:test_end].copy()

            windows.append((train_df, test_df))

        return windows

    def _grid_search(
        self,
        strategy_class: type,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        metric: str
    ) -> Optional[Dict]:
        """
        Grid search for best parameters on training data

        Args:
            strategy_class: StrategyCore class
            data: Training data
            param_grid: Parameter combinations to try
            metric: Optimization metric

        Returns:
            Best parameters dict
        """
        # Generate all parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        logger.info(f"  Grid search: {len(combinations)} combinations")

        best_metric = -np.inf
        best_params = None

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                # Test this parameter combination
                strategy = strategy_class(params=params)
                metrics = self.backtester.backtest(strategy, data)

                # Check if better
                if metrics[metric] > best_metric:
                    best_metric = metrics[metric]
                    best_params = params

            except Exception as e:
                logger.debug(f"  Failed params {params}: {e}")
                continue

        return best_params

    def _test_params(
        self,
        strategy_class: type,
        data: pd.DataFrame,
        params: Dict
    ) -> Dict:
        """
        Test specific parameters on validation data

        Args:
            strategy_class: StrategyCore class
            data: Test data
            params: Parameters to test

        Returns:
            Metrics dict
        """
        strategy = strategy_class(params=params)
        return self.backtester.backtest(strategy, data)

    def _check_stability(
        self,
        params_per_window: List[Dict],
        max_cv: float
    ) -> Tuple[bool, Dict[str, float]]:
        """
        Check parameter stability across windows

        Uses coefficient of variation (CV = std / mean):
        - CV < 0.30 (30%) = stable
        - CV >= 0.30 = unstable (overfitting)

        Args:
            params_per_window: List of best params per window
            max_cv: Maximum acceptable CV

        Returns:
            (is_stable, cv_values) tuple
        """
        if len(params_per_window) == 0:
            return (False, {})

        # Get all parameter names
        param_names = params_per_window[0].keys()

        cv_values = {}

        for param_name in param_names:
            # Skip metadata params (starting with _)
            if param_name.startswith('_'):
                continue

            # Get values across all windows
            values = [p[param_name] for p in params_per_window]

            # Skip if not numeric
            if not all(isinstance(v, (int, float)) for v in values):
                continue

            values = np.array(values)

            # Calculate coefficient of variation
            mean_val = np.mean(values)
            std_val = np.std(values)

            if mean_val == 0:
                cv = 0.0
            else:
                cv = std_val / abs(mean_val)

            cv_values[param_name] = cv

        # Check if all CVs are below threshold
        is_stable = all(cv < max_cv for cv in cv_values.values())

        return (is_stable, cv_values)

    def _average_params(self, params_per_window: List[Dict]) -> Dict:
        """
        Average parameters across windows

        Args:
            params_per_window: List of parameter dicts

        Returns:
            Averaged parameters
        """
        if len(params_per_window) == 0:
            return {}

        avg_params = {}
        param_names = params_per_window[0].keys()

        for param_name in param_names:
            # Skip metadata params
            if param_name.startswith('_'):
                continue

            values = [p[param_name] for p in params_per_window]

            # Average if numeric
            if all(isinstance(v, (int, float)) for v in values):
                avg_value = np.mean(values)

                # Round to int if all original values were integers
                if all(isinstance(v, int) for v in values):
                    avg_params[param_name] = int(round(avg_value))
                else:
                    avg_params[param_name] = avg_value
            else:
                # Use most common value for non-numeric
                avg_params[param_name] = max(set(values), key=values.count)

        return avg_params


class SimpleOptimizer:
    """
    Simple optimizer without walk-forward (for rapid testing)

    Only use for quick validation - NOT for production strategies!
    """

    def __init__(self, backtester: Optional[VectorBTBacktester] = None):
        self.backtester = backtester or VectorBTBacktester()

    def optimize(
        self,
        strategy_class: type,
        data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        metric: str = 'sharpe_ratio'
    ) -> Optional[Dict]:
        """
        Simple grid search (NO walk-forward validation)

        WARNING: High risk of overfitting!

        Args:
            strategy_class: StrategyCore class
            data: Historical data
            param_grid: Parameter grid
            metric: Optimization metric

        Returns:
            Best parameters
        """
        logger.warning("Using SimpleOptimizer - risk of overfitting!")

        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        combinations = list(product(*param_values))

        best_metric = -np.inf
        best_params = None

        for combo in combinations:
            params = dict(zip(param_names, combo))

            try:
                strategy = strategy_class(params=params)
                metrics = self.backtester.backtest(strategy, data)

                if metrics[metric] > best_metric:
                    best_metric = metrics[metric]
                    best_params = params

            except:
                continue

        return best_params
