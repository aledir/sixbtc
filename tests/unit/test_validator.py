"""
Unit tests for LookaheadValidator and QuickValidator
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from src.backtester.validator import LookaheadValidator, QuickValidator
from src.strategies.base import StrategyCore, Signal


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data for testing"""
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-01', periods=200, freq='1h')

    return pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.random.randn(200) * 100,
        'high': 50500 + np.random.randn(200) * 100,
        'low': 49500 + np.random.randn(200) * 100,
        'close': 50000 + np.random.randn(200) * 100,
        'volume': 1000 + np.random.randn(200) * 50
    })


@pytest.fixture
def valid_strategy_code():
    """Valid strategy code with no lookahead bias"""
    return """
class Strategy_Test(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Valid: uses only past data
        rsi = ta.RSI(df['close'], timeperiod=14)
        ma = df['close'].rolling(20).mean()  # No center=True

        if rsi.iloc[-1] < 30 and df['close'].iloc[-1] > ma.iloc[-1]:
            return Signal(direction='long')

        return None
"""


@pytest.fixture
def invalid_strategy_code_centered_rolling():
    """Invalid strategy with centered rolling"""
    return """
class Strategy_Invalid(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # INVALID: rolling with center=True uses future data
        ma = df['close'].rolling(20, center=True).mean()

        if df['close'].iloc[-1] > ma.iloc[-1]:
            return Signal(direction='long')

        return None
"""


@pytest.fixture
def invalid_strategy_code_negative_shift():
    """Invalid strategy with negative shift"""
    return """
class Strategy_Invalid(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # INVALID: shift(-1) uses future data
        future_close = df['close'].shift(-1)

        if df['close'].iloc[-1] < future_close.iloc[-1]:
            return Signal(direction='long')

        return None
"""


@pytest.fixture
def valid_strategy_instance():
    """Valid strategy instance for shuffle test"""
    class TestStrategy(StrategyCore):
        def generate_signal(self, df: pd.DataFrame) -> Signal | None:
            # Simple RSI strategy
            if len(df) < 20:
                return None

            # Calculate RSI
            close = df['close'].values
            changes = np.diff(close)
            gains = np.where(changes > 0, changes, 0)
            losses = np.abs(np.where(changes < 0, changes, 0))

            avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
            avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0

            if avg_loss == 0:
                return None

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

            # Signal logic
            if rsi < 30:
                return Signal(direction='long', reason='RSI oversold')
            elif rsi > 70:
                return Signal(direction='short', reason='RSI overbought')

            return None

    return TestStrategy()


class TestLookaheadValidator:
    """Test suite for LookaheadValidator"""

    def test_ast_check_valid_code(self, valid_strategy_code):
        """Test AST check passes for valid code"""
        validator = LookaheadValidator()

        passed, violations = validator._ast_check(valid_strategy_code)

        assert passed is True
        assert len(violations) == 0

    def test_ast_check_centered_rolling(self, invalid_strategy_code_centered_rolling):
        """Test AST check detects centered rolling"""
        validator = LookaheadValidator()

        passed, violations = validator._ast_check(invalid_strategy_code_centered_rolling)

        assert passed is False
        assert len(violations) == 1
        assert 'rolling(center=True)' in violations[0]

    def test_ast_check_negative_shift(self, invalid_strategy_code_negative_shift):
        """Test AST check detects negative shift"""
        validator = LookaheadValidator()

        passed, violations = validator._ast_check(invalid_strategy_code_negative_shift)

        assert passed is False
        assert len(violations) == 1
        assert 'shift(' in violations[0]

    def test_ast_check_multiple_violations(self):
        """Test AST check detects multiple violations"""
        code = """
class Strategy_MultiViolation(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Multiple violations
        ma1 = df['close'].rolling(20, center=True).mean()  # Violation 1
        future = df['close'].shift(-5)  # Violation 2

        return Signal(direction='long')
"""
        validator = LookaheadValidator()

        passed, violations = validator._ast_check(code)

        assert passed is False
        assert len(violations) >= 2

    def test_ast_check_syntax_error(self):
        """Test AST check handles syntax errors"""
        code = "def invalid_syntax(: invalid"

        validator = LookaheadValidator()

        passed, violations = validator._ast_check(code)

        assert passed is False
        assert len(violations) == 1
        assert 'Syntax error' in violations[0]

    def test_shuffle_test_sufficient_signals(self, valid_strategy_instance, sample_ohlcv):
        """Test shuffle test with sufficient signals"""
        validator = LookaheadValidator()

        p_value, passed = validator._shuffle_test(
            strategy=valid_strategy_instance,
            data=sample_ohlcv,
            n_iterations=50  # Reduced for speed
        )

        # Should return valid p-value
        assert 0.0 <= p_value <= 1.0
        assert isinstance(passed, bool)

    def test_shuffle_test_too_few_signals(self, sample_ohlcv):
        """Test shuffle test with too few signals"""
        # Strategy that generates very few signals
        class RareSignalStrategy(StrategyCore):
            def generate_signal(self, df: pd.DataFrame) -> Signal | None:
                # Only signal once every 100 bars
                if len(df) % 100 == 0:
                    return Signal(direction='long')
                return None

        validator = LookaheadValidator()

        p_value, passed = validator._shuffle_test(
            strategy=RareSignalStrategy(),
            data=sample_ohlcv,
            n_iterations=50
        )

        # Should fail due to insufficient signals
        assert p_value == 1.0
        assert passed is False

    def test_calculate_simple_edge_long_signals(self, sample_ohlcv):
        """Test edge calculation for long signals"""
        validator = LookaheadValidator()

        # Create simple long signals
        signals = [1, 1, 1]  # 3 long signals
        entry_prices = [
            sample_ohlcv['close'].iloc[10],
            sample_ohlcv['close'].iloc[20],
            sample_ohlcv['close'].iloc[30]
        ]

        edge = validator._calculate_simple_edge(
            signals=signals,
            entry_prices=entry_prices,
            price_series=sample_ohlcv['close']
        )

        # Should return a float
        assert isinstance(edge, float)

    def test_calculate_simple_edge_short_signals(self, sample_ohlcv):
        """Test edge calculation for short signals"""
        validator = LookaheadValidator()

        # Create short signals
        signals = [-1, -1, -1]  # 3 short signals
        entry_prices = [
            sample_ohlcv['close'].iloc[10],
            sample_ohlcv['close'].iloc[20],
            sample_ohlcv['close'].iloc[30]
        ]

        edge = validator._calculate_simple_edge(
            signals=signals,
            entry_prices=entry_prices,
            price_series=sample_ohlcv['close']
        )

        # Should return a float
        assert isinstance(edge, float)

    def test_calculate_simple_edge_empty_signals(self, sample_ohlcv):
        """Test edge calculation with no signals"""
        validator = LookaheadValidator()

        edge = validator._calculate_simple_edge(
            signals=[],
            entry_prices=[],
            price_series=sample_ohlcv['close']
        )

        assert edge == 0.0

    def test_validate_full_suite_valid(self, valid_strategy_instance, valid_strategy_code, sample_ohlcv):
        """Test full validation suite with valid strategy"""
        validator = LookaheadValidator()

        results = validator.validate(
            strategy=valid_strategy_instance,
            strategy_code=valid_strategy_code,
            backtest_data=sample_ohlcv,
            shuffle_iterations=30  # Reduced for speed
        )

        # Should have all required keys
        assert 'ast_check_passed' in results
        assert 'ast_violations' in results
        assert 'shuffle_test_passed' in results
        assert 'shuffle_p_value' in results
        assert 'passed' in results

        # AST should pass
        assert results['ast_check_passed'] is True
        assert len(results['ast_violations']) == 0

    def test_validate_full_suite_invalid_ast(
        self,
        valid_strategy_instance,
        invalid_strategy_code_centered_rolling,
        sample_ohlcv
    ):
        """Test full validation suite with AST violations"""
        validator = LookaheadValidator()

        results = validator.validate(
            strategy=valid_strategy_instance,
            strategy_code=invalid_strategy_code_centered_rolling,
            backtest_data=sample_ohlcv,
            shuffle_iterations=30
        )

        # AST should fail
        assert results['ast_check_passed'] is False
        assert len(results['ast_violations']) > 0

        # Shuffle test should be skipped
        assert results['shuffle_test_passed'] is False
        assert results['shuffle_p_value'] == 1.0

        # Overall should fail
        assert results['passed'] is False

    def test_validate_shuffle_test_exception(self, valid_strategy_code, sample_ohlcv):
        """Test validation handles shuffle test exceptions"""
        # Strategy that raises exception
        class BrokenStrategy(StrategyCore):
            def generate_signal(self, df: pd.DataFrame) -> Signal | None:
                raise Exception("Strategy error")

        validator = LookaheadValidator()

        results = validator.validate(
            strategy=BrokenStrategy(),
            strategy_code=valid_strategy_code,
            backtest_data=sample_ohlcv,
            shuffle_iterations=30
        )

        # AST should pass, shuffle should fail
        assert results['ast_check_passed'] is True
        assert results['shuffle_test_passed'] is False
        assert results['shuffle_p_value'] == 1.0
        assert results['passed'] is False


class TestQuickValidator:
    """Test suite for QuickValidator"""

    def test_quick_check_valid(self, valid_strategy_code):
        """Test quick check passes for valid code"""
        passed, violations = QuickValidator.quick_check(valid_strategy_code)

        assert passed is True
        assert len(violations) == 0

    def test_quick_check_invalid(self, invalid_strategy_code_centered_rolling):
        """Test quick check detects violations"""
        passed, violations = QuickValidator.quick_check(invalid_strategy_code_centered_rolling)

        assert passed is False
        assert len(violations) > 0

    def test_quick_check_syntax_error(self):
        """Test quick check handles syntax errors"""
        code = "def broken(syntax: invalid"

        passed, violations = QuickValidator.quick_check(code)

        assert passed is False
        assert 'Syntax error' in violations[0]


class TestValidatorEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_ast_check_expanding_center_true(self):
        """Test detection of expanding(center=True)"""
        code = """
class Strategy(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Invalid: expanding with center
        max_val = df['high'].expanding(center=True).max()
        return Signal(direction='long')
"""
        validator = LookaheadValidator()

        passed, violations = validator._ast_check(code)

        assert passed is False
        assert any('expanding' in v for v in violations)

    def test_shuffle_test_zero_variance(self, sample_ohlcv):
        """Test shuffle test with zero variance results"""
        # Strategy that always generates same signal
        class ConstantStrategy(StrategyCore):
            def generate_signal(self, df: pd.DataFrame) -> Signal | None:
                if len(df) >= 20 and len(df) % 10 == 0:
                    return Signal(direction='long')
                return None

        validator = LookaheadValidator()

        # This might trigger zero variance in some cases
        # Should handle gracefully
        p_value, passed = validator._shuffle_test(
            strategy=ConstantStrategy(),
            data=sample_ohlcv,
            n_iterations=30
        )

        assert isinstance(p_value, float)
        assert isinstance(passed, (bool, np.bool_))  # Accept both Python and NumPy booleans

    def test_calculate_edge_near_data_end(self):
        """Test edge calculation when signals near end of data"""
        validator = LookaheadValidator()

        # Short dataset
        short_data = pd.Series([100, 101, 102, 103, 104, 105], name='close')

        # Signal near end
        signals = [1]
        entry_prices = [104]  # Second-to-last price

        # Should handle gracefully
        edge = validator._calculate_simple_edge(
            signals=signals,
            entry_prices=entry_prices,
            price_series=short_data
        )

        assert isinstance(edge, float)
