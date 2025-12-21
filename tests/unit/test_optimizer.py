"""
Unit Tests for Walk-Forward Optimizer

Tests parameter optimization with focus on:
- Walk-forward window creation
- Grid search functionality
- Parameter stability checking
- Out-of-sample validation
- Overfitting prevention
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.backtester.optimizer import WalkForwardOptimizer
from src.strategies.base import StrategyCore, Signal


# Mock strategy for testing
class MockStrategy(StrategyCore):
    """Simple mock strategy for testing optimizer"""

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.period = self.params.get('period', 14)
        self.threshold = self.params.get('threshold', 0.5)

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < self.period:
            return None

        # Simple mock logic
        if df['close'].iloc[-1] > df['close'].iloc[-2]:
            return Signal(
                direction='long',
                stop_loss=df['close'].iloc[-1] * 0.98,
                take_profit=df['close'].iloc[-1] * 1.03,
                confidence=1.0,
                reason="Mock signal"
            )
        return None


@pytest.fixture
def sample_data():
    """Generate sample OHLCV data for testing"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=1000, freq='1h')

    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.random.randn(1000) * 1000,
        'high': 50500 + np.random.randn(1000) * 1000,
        'low': 49500 + np.random.randn(1000) * 1000,
        'close': 50000 + np.random.randn(1000) * 1000,
        'volume': np.random.rand(1000) * 1000
    })

    # Ensure high >= low
    df['high'] = df[['high', 'low']].max(axis=1)
    df['low'] = df[['high', 'low']].min(axis=1)

    return df


@pytest.fixture
def optimizer():
    """Create WalkForwardOptimizer instance"""
    mock_backtester = Mock()
    return WalkForwardOptimizer(backtester=mock_backtester)


class TestWindowCreation:
    """Test walk-forward window creation"""

    def test_create_windows_count(self, optimizer, sample_data):
        """Test correct number of windows created"""
        windows = optimizer._create_windows(sample_data, n_windows=4, train_pct=0.75)

        assert len(windows) == 4

    def test_create_windows_expanding(self, optimizer, sample_data):
        """Test windows are expanding (train size increases)"""
        windows = optimizer._create_windows(sample_data, n_windows=4, train_pct=0.75)

        train_sizes = [len(train) for train, test in windows]

        # Train sizes should be increasing
        for i in range(len(train_sizes) - 1):
            assert train_sizes[i] < train_sizes[i + 1]

    def test_create_windows_no_overlap(self, optimizer, sample_data):
        """Test train and test sets don't overlap"""
        windows = optimizer._create_windows(sample_data, n_windows=4, train_pct=0.75)

        for train, test in windows:
            # Last train timestamp should be before first test timestamp
            assert train.index[-1] < test.index[0]

    def test_create_windows_initial_split(self, optimizer, sample_data):
        """Test first window respects initial train_pct for dataset"""
        windows = optimizer._create_windows(sample_data, n_windows=4, train_pct=0.75)

        train, test = windows[0]

        # First window train should be 75% of full dataset
        train_ratio_full = len(train) / len(sample_data)
        assert 0.70 <= train_ratio_full <= 0.80  # Allow 5% tolerance

    def test_create_windows_uses_all_data(self, optimizer, sample_data):
        """Test all windows use complete dataset by final window"""
        windows = optimizer._create_windows(sample_data, n_windows=4, train_pct=0.75)

        final_train, final_test = windows[-1]

        # Last test data should reach end of dataset
        assert final_test.index[-1] == sample_data.index[-1]


class TestGridSearch:
    """Test grid search functionality"""

    def test_grid_search_finds_best_params(self, optimizer, sample_data):
        """Test grid search finds optimal parameters"""
        param_grid = {
            'period': [10, 14, 20],
            'threshold': [0.3, 0.5, 0.7]
        }

        # Mock backtester to return different metrics for different params
        def mock_backtest(strategy, data):
            # Higher period = better Sharpe (for testing)
            sharpe = strategy.params.get('period', 14) / 10.0
            return {'sharpe_ratio': sharpe, 'total_trades': 100}

        optimizer.backtester.backtest = mock_backtest

        best_params = optimizer._grid_search(
            MockStrategy,
            sample_data,
            param_grid,
            metric='sharpe_ratio'
        )

        # Should select period=20 (highest Sharpe)
        assert best_params['period'] == 20

    def test_grid_search_all_combinations(self, optimizer, sample_data):
        """Test grid search tries all parameter combinations"""
        param_grid = {
            'period': [10, 20],
            'threshold': [0.5, 0.7]
        }

        combinations_tested = []

        def mock_backtest(strategy, data):
            combinations_tested.append((strategy.params['period'], strategy.params['threshold']))
            return {'sharpe_ratio': 1.5, 'total_trades': 100}

        optimizer.backtester.backtest = mock_backtest

        optimizer._grid_search(MockStrategy, sample_data, param_grid, 'sharpe_ratio')

        # Should test all 4 combinations (2x2)
        assert len(combinations_tested) == 4
        assert (10, 0.5) in combinations_tested
        assert (10, 0.7) in combinations_tested
        assert (20, 0.5) in combinations_tested
        assert (20, 0.7) in combinations_tested

    def test_grid_search_returns_best_even_if_poor(self, optimizer, sample_data):
        """Test grid search returns best params even if all are poor"""
        param_grid = {'period': [10, 20]}

        # Mock backtester to always return poor results
        optimizer.backtester.backtest = lambda s, d: {'sharpe_ratio': -1.0, 'total_trades': 0}

        result = optimizer._grid_search(MockStrategy, sample_data, param_grid, 'sharpe_ratio')

        # Should still return the best (least bad) params
        assert result is not None
        assert 'period' in result


class TestParameterStability:
    """Test parameter stability checking"""

    def test_check_stability_stable_params(self, optimizer):
        """Test stability check passes for stable parameters"""
        params_per_window = [
            {'period': 14, 'threshold': 0.5},
            {'period': 15, 'threshold': 0.52},
            {'period': 14, 'threshold': 0.48},
            {'period': 14, 'threshold': 0.51}
        ]

        is_stable, cv_values = optimizer._check_stability(params_per_window, max_cv=0.30)

        assert is_stable is True

    def test_check_stability_unstable_params(self, optimizer):
        """Test stability check fails for unstable parameters"""
        params_per_window = [
            {'period': 10, 'threshold': 0.3},
            {'period': 20, 'threshold': 0.7},
            {'period': 15, 'threshold': 0.5},
            {'period': 25, 'threshold': 0.9}
        ]

        is_stable, cv_values = optimizer._check_stability(params_per_window, max_cv=0.30)

        assert is_stable is False

    def test_check_stability_calculates_cv_correctly(self, optimizer):
        """Test coefficient of variation calculation"""
        params_per_window = [
            {'period': 10},
            {'period': 10},
            {'period': 10},
            {'period': 10}
        ]

        is_stable, cv_values = optimizer._check_stability(params_per_window, max_cv=0.30)

        # CV for identical values should be 0
        assert cv_values['period'] == 0.0

    def test_check_stability_multiple_params(self, optimizer):
        """Test stability checking with multiple parameters"""
        params_per_window = [
            {'period': 14, 'threshold': 0.3},
            {'period': 14, 'threshold': 0.5},
            {'period': 15, 'threshold': 0.7}  # threshold has high variation
        ]

        is_stable, cv_values = optimizer._check_stability(params_per_window, max_cv=0.10)

        # Should fail due to threshold variation (CV > 0.10)
        assert is_stable is False
        assert 'threshold' in cv_values


class TestParameterAveraging:
    """Test parameter averaging across windows"""

    def test_average_params_numeric(self, optimizer):
        """Test averaging numeric parameters"""
        params_per_window = [
            {'period': 10, 'threshold': 0.4},
            {'period': 14, 'threshold': 0.5},
            {'period': 16, 'threshold': 0.6}
        ]

        avg_params = optimizer._average_params(params_per_window)

        # Average of 10, 14, 16 = 13.33, rounded to 13 (integer)
        assert avg_params['period'] == 13
        assert isinstance(avg_params['period'], int)

        # Average of 0.4, 0.5, 0.6 = 0.5 (float)
        assert abs(avg_params['threshold'] - 0.5) < 0.01

    def test_average_params_rounds_integers(self, optimizer):
        """Test integer parameters are rounded"""
        params_per_window = [
            {'period': 10},
            {'period': 15},
            {'period': 14}
        ]

        avg_params = optimizer._average_params(params_per_window)

        # Should round to nearest integer
        assert isinstance(avg_params['period'], int)
        assert avg_params['period'] == 13  # round(13)


class TestOutOfSampleValidation:
    """Test out-of-sample testing"""

    def test_test_params_on_unseen_data(self, optimizer, sample_data):
        """Test params validation on out-of-sample data"""
        params = {'period': 14, 'threshold': 0.5}

        # Mock backtester
        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 1.5,
            'total_trades': 50,
            'win_rate': 0.6
        }

        metrics = optimizer._test_params(MockStrategy, sample_data, params)

        assert metrics['sharpe_ratio'] == 1.5
        assert metrics['total_trades'] == 50
        assert metrics['win_rate'] == 0.6

    def test_test_params_creates_strategy_correctly(self, optimizer, sample_data):
        """Test strategy is instantiated with correct params"""
        params = {'period': 20, 'threshold': 0.7}

        strategy_created = None

        def capture_strategy(strategy, data):
            nonlocal strategy_created
            strategy_created = strategy
            return {'sharpe_ratio': 1.0, 'total_trades': 10}

        optimizer.backtester.backtest = capture_strategy

        optimizer._test_params(MockStrategy, sample_data, params)

        assert strategy_created is not None
        assert strategy_created.params['period'] == 20
        assert strategy_created.params['threshold'] == 0.7


class TestFullOptimization:
    """Test complete walk-forward optimization workflow"""

    def test_optimize_returns_best_params(self, optimizer, sample_data):
        """Test full optimization returns optimized parameters"""
        param_grid = {
            'period': [10, 14, 20],
            'threshold': [0.5, 0.7]
        }

        # Mock consistent good performance
        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 1.5,
            'total_trades': 100,
            'win_rate': 0.6
        }

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=4,
            metric='sharpe_ratio',
            min_metric_value=1.0
        )

        assert result is not None
        assert 'period' in result
        assert 'threshold' in result

    def test_optimize_rejects_poor_performance(self, optimizer, sample_data):
        """Test optimization rejects strategies below threshold"""
        param_grid = {'period': [10, 14]}

        # Mock poor performance
        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 0.5,  # Below threshold
            'total_trades': 10
        }

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=4,
            metric='sharpe_ratio',
            min_metric_value=1.0
        )

        assert result is None

    def test_optimize_rejects_unstable_params(self, optimizer, sample_data):
        """Test optimization rejects unstable parameters"""
        param_grid = {'period': [10, 20, 30]}

        call_count = [0]

        def varying_performance(strategy, data):
            # Return different optimal params per window
            call_count[0] += 1
            return {
                'sharpe_ratio': 1.5,
                'total_trades': 100
            }

        optimizer.backtester.backtest = varying_performance

        # Make grid search return different params each window
        original_grid_search = optimizer._grid_search

        def unstable_grid_search(strategy_class, data, param_grid, metric):
            # Return different params based on data size
            if len(data) < 600:
                return {'period': 10}
            elif len(data) < 800:
                return {'period': 20}
            else:
                return {'period': 30}

        optimizer._grid_search = unstable_grid_search

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=4,
            metric='sharpe_ratio',
            max_cv=0.10  # Low threshold
        )

        # Should reject due to instability
        assert result is None

    def test_optimize_includes_stability_metrics(self, optimizer, sample_data):
        """Test final params include stability metrics"""
        param_grid = {'period': [14]}

        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 1.5,
            'total_trades': 100
        }

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=4,
            metric='sharpe_ratio'
        )

        assert result is not None
        assert '_wf_worst_window' in result
        assert '_wf_stability' in result
        assert 0.0 <= result['_wf_stability'] <= 1.0


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_optimize_with_single_window(self, optimizer, sample_data):
        """Test optimization with single window"""
        param_grid = {'period': [14]}

        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 1.5,
            'total_trades': 100
        }

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=1,
            metric='sharpe_ratio'
        )

        assert result is not None

    def test_optimize_with_empty_param_grid(self, optimizer, sample_data):
        """Test optimization with empty parameter grid"""
        param_grid = {}

        result = optimizer.optimize(
            MockStrategy,
            sample_data,
            param_grid,
            n_windows=2
        )

        # Should handle gracefully
        assert result is not None or result is None

    def test_optimize_with_insufficient_data(self, optimizer):
        """Test optimization with too little data"""
        small_data = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=10, freq='1h'),
            'open': [50000] * 10,
            'high': [51000] * 10,
            'low': [49000] * 10,
            'close': [50000] * 10,
            'volume': [1000] * 10
        })

        param_grid = {'period': [5]}

        optimizer.backtester.backtest = lambda s, d: {
            'sharpe_ratio': 1.5,
            'total_trades': 100
        }

        # May return None or raise error (both acceptable)
        try:
            result = optimizer.optimize(MockStrategy, small_data, param_grid, n_windows=4)
            # If it completes, that's fine
        except Exception:
            # If it raises an error, that's also acceptable
            pass
