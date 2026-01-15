"""
Tests for the Validator module.

Covers:
1. ExecutionValidator - runtime execution validation
2. SyntaxValidator - Python syntax validation
3. LookaheadDetector - AST-based lookahead detection

These are critical tests that ensure strategies are properly validated
before entering the pipeline.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.validator.execution_validator import ExecutionValidator, ExecutionValidationResult
from src.validator.syntax_validator import SyntaxValidator
from src.validator.lookahead_detector import LookaheadDetector


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def test_ohlcv_with_datetime_index():
    """Create OHLCV data with proper DatetimeIndex (required for VWAP etc)."""
    np.random.seed(42)
    n_bars = 500

    returns = np.random.normal(0, 0.02, n_bars)
    close = 100 * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n_bars)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n_bars)))
    open_price = low + (high - low) * np.random.random(n_bars)
    volume = np.random.uniform(1000, 10000, n_bars)

    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_bars, freq='15min')

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }, index=dates)


@pytest.fixture
def valid_strategy_code():
    """A minimal valid strategy that should pass all validation."""
    return '''
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal

class PtaStrat_TRD_abc12345(StrategyCore):
    """Test strategy for validation."""

    LOOKBACK = 20

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['sma'] = df['close'].rolling(20).mean()
        return df

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < self.LOOKBACK:
            return None
        if df['close'].iloc[-1] > df['sma'].iloc[-1]:
            return Signal(direction='long')
        return None
'''


@pytest.fixture
def lookahead_strategy_code():
    """Strategy with lookahead bias (should fail)."""
    return '''
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal

class PtaStrat_TRD_def67890(StrategyCore):
    """Strategy with lookahead bias."""

    LOOKBACK = 20

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # LOOKAHEAD: using future data with shift(-1)
        df['future_close'] = df['close'].shift(-1)
        return df

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < self.LOOKBACK:
            return None
        return Signal(direction='long')
'''


@pytest.fixture
def syntax_error_code():
    """Code with syntax error."""
    return '''
import pandas as pd

class PtaStrat_TRD_aaa11111(StrategyCore)
    # Missing colon above - syntax error
    def calculate_indicators(self, df):
        return df
'''


@pytest.fixture
def vwap_strategy_code():
    """Strategy using VWAP (requires DatetimeIndex)."""
    return '''
import pandas as pd
import pandas_ta as ta
from src.strategies.base import StrategyCore, Signal

class PtaStrat_VOL_bbb22222(StrategyCore):
    """Strategy using VWAP indicator."""

    LOOKBACK = 50

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        df['vwap'] = vwap
        return df

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < self.LOOKBACK:
            return None
        if pd.isna(df['vwap'].iloc[-1]):
            return None
        if df['close'].iloc[-1] > df['vwap'].iloc[-1]:
            return Signal(direction='long')
        return None
'''


# =============================================================================
# EXECUTION VALIDATOR TESTS
# =============================================================================

class TestExecutionValidator:
    """Tests for ExecutionValidator."""

    def test_valid_strategy_passes(self, valid_strategy_code, test_ohlcv_with_datetime_index):
        """Valid strategy should pass execution validation."""
        validator = ExecutionValidator()
        result = validator.validate(
            code=valid_strategy_code,
            class_name="PtaStrat_TRD_abc12345",
            test_data=test_ohlcv_with_datetime_index
        )

        assert result.passed is True
        assert len(result.errors) == 0

    def test_invalid_class_name_fails(self, valid_strategy_code, test_ohlcv_with_datetime_index):
        """Wrong class name should fail."""
        validator = ExecutionValidator()
        result = validator.validate(
            code=valid_strategy_code,
            class_name="NonExistentClass",
            test_data=test_ohlcv_with_datetime_index
        )

        assert result.passed is False
        assert any("Failed to load" in e for e in result.errors)

    def test_generate_test_data_has_datetime_index(self):
        """Generated test data must have DatetimeIndex for VWAP compatibility."""
        validator = ExecutionValidator()
        df = validator._generate_test_data(100)

        assert isinstance(df.index, pd.DatetimeIndex), \
            "Test data must have DatetimeIndex (required by pandas_ta VWAP)"

    def test_generate_test_data_has_required_columns(self):
        """Generated test data must have OHLCV columns."""
        validator = ExecutionValidator()
        df = validator._generate_test_data(100)

        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"

    def test_generate_test_data_empty(self):
        """Empty test data should return empty DataFrame with columns."""
        validator = ExecutionValidator()
        df = validator._generate_test_data(0)

        assert len(df) == 0
        assert 'close' in df.columns

    def test_vwap_strategy_works_with_datetime_index(
        self, vwap_strategy_code, test_ohlcv_with_datetime_index
    ):
        """VWAP strategy should work when DatetimeIndex is provided."""
        validator = ExecutionValidator()
        result = validator.validate(
            code=vwap_strategy_code,
            class_name="PtaStrat_VOL_bbb22222",
            test_data=test_ohlcv_with_datetime_index
        )

        # Should pass without VWAP warnings causing issues
        assert result.passed is True, f"VWAP strategy failed: {result.errors}"


# =============================================================================
# SYNTAX VALIDATOR TESTS
# =============================================================================

class TestSyntaxValidator:
    """Tests for SyntaxValidator."""

    def test_valid_code_passes(self, valid_strategy_code):
        """Valid Python code should pass syntax validation."""
        validator = SyntaxValidator()
        result = validator.validate(valid_strategy_code)

        assert result.passed is True
        assert len(result.errors) == 0

    def test_syntax_error_fails(self, syntax_error_code):
        """Code with syntax errors should fail."""
        validator = SyntaxValidator()
        result = validator.validate(syntax_error_code)

        assert result.passed is False
        assert len(result.errors) > 0

    def test_empty_code_fails(self):
        """Empty code should fail."""
        validator = SyntaxValidator()
        result = validator.validate("")

        assert result.passed is False

    def test_invalid_class_name_format_fails(self):
        """Code with wrong class name format should fail."""
        code_bad_name = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class MyStrategy(StrategyCore):
    LOOKBACK = 20
    def calculate_indicators(self, df): return df
    def generate_signal(self, df): return None
'''
        validator = SyntaxValidator()
        result = validator.validate(code_bad_name)

        assert result.passed is False
        assert any("class name" in e.lower() for e in result.errors)


# =============================================================================
# LOOKAHEAD DETECTOR TESTS
# =============================================================================

class TestLookaheadDetector:
    """Tests for LookaheadDetector (AST-based lookahead detection)."""

    def test_clean_code_passes(self, valid_strategy_code):
        """Code without lookahead should pass."""
        detector = LookaheadDetector()
        result = detector.validate(valid_strategy_code)

        assert result.passed is True
        assert len(result.violations) == 0

    def test_shift_negative_detected(self, lookahead_strategy_code):
        """shift(-N) should be detected as lookahead."""
        detector = LookaheadDetector()
        result = detector.validate(lookahead_strategy_code)

        assert result.passed is False
        assert len(result.violations) > 0
        assert any("shift" in str(v).lower() for v in result.violations)

    def test_rolling_center_detected(self):
        """rolling(center=True) should be detected as lookahead."""
        code_with_center = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class PtaStrat_TRD_ccc33333(StrategyCore):
    LOOKBACK = 20

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # LOOKAHEAD: center=True uses future data
        df['centered_ma'] = df['close'].rolling(10, center=True).mean()
        return df

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        return None
'''
        detector = LookaheadDetector()
        result = detector.validate(code_with_center)

        assert result.passed is False
        assert any("center" in str(v).lower() for v in result.violations)

    def test_iloc_last_is_ok(self):
        """iloc[-1] accessing last element should be OK."""
        code_with_safe_iloc = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class PtaStrat_TRD_ddd44444(StrategyCore):
    LOOKBACK = 20

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # This is OK - accessing last element
        current = df['close'].iloc[-1]
        return None
'''
        detector = LookaheadDetector()
        result = detector.validate(code_with_safe_iloc)

        # iloc[-1] is OK (current bar), should pass
        assert result.passed is True


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestValidationPipeline:
    """Integration tests for the full validation pipeline."""

    def test_full_pipeline_valid_strategy(
        self, valid_strategy_code, test_ohlcv_with_datetime_index
    ):
        """Valid strategy should pass all validation phases."""
        # Phase 1: Syntax
        syntax_validator = SyntaxValidator()
        syntax_result = syntax_validator.validate(valid_strategy_code)
        assert syntax_result.passed is True, f"Syntax validation failed: {syntax_result.errors}"

        # Phase 2: Lookahead
        lookahead_detector = LookaheadDetector()
        lookahead_result = lookahead_detector.validate(valid_strategy_code)
        assert lookahead_result.passed is True, f"Lookahead detection failed: {lookahead_result.violations}"

        # Phase 3: Execution
        execution_validator = ExecutionValidator()
        execution_result = execution_validator.validate(
            code=valid_strategy_code,
            class_name="PtaStrat_TRD_abc12345",
            test_data=test_ohlcv_with_datetime_index
        )
        assert execution_result.passed is True, f"Execution validation failed: {execution_result.errors}"

    def test_full_pipeline_lookahead_strategy(self, lookahead_strategy_code):
        """Strategy with lookahead should fail at lookahead detection phase."""
        # Phase 1: Syntax (should pass)
        syntax_validator = SyntaxValidator()
        syntax_result = syntax_validator.validate(lookahead_strategy_code)
        assert syntax_result.passed is True, f"Syntax should pass: {syntax_result.errors}"

        # Phase 2: Lookahead (should FAIL)
        lookahead_detector = LookaheadDetector()
        lookahead_result = lookahead_detector.validate(lookahead_strategy_code)
        assert lookahead_result.passed is False, "Lookahead should be detected"
