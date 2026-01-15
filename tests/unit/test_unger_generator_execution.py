"""
Tests for Unger generator code execution.

These tests ACTUALLY GENERATE AND EXECUTE strategies to catch runtime errors
like "The truth value of a Series is ambiguous" that static validation misses.

This is the critical test that ensures generated code is runnable.
"""
import pytest
import pandas as pd
import numpy as np
from typing import Optional

from src.config import load_config
from src.generator.unger.generator import UngerGenerator
from src.generator.unger.catalogs.entries import ALL_ENTRIES
from src.generator.unger.catalogs.filters import ALL_FILTERS
from src.generator.unger.catalogs.sl_types import SL_CONFIGS
from src.generator.unger.catalogs.tp_types import TP_CONFIGS
from src.generator.unger.catalogs.exit_mechanisms import EXIT_MECHANISMS
from src.generator.unger.composer import StrategyBlueprint


def resolve_params(params: dict) -> dict:
    """
    Resolve parameter ranges to single values.

    Params in catalogs are ranges like {"period": [10, 14, 20]}.
    For testing, we pick the first value from each list.
    """
    if not params:
        return {}

    resolved = {}
    for key, value in params.items():
        if isinstance(value, list) and value:
            resolved[key] = value[0]  # Pick first value
        else:
            resolved[key] = value
    return resolved


def create_test_ohlcv(rows: int = 500) -> pd.DataFrame:
    """Create realistic OHLCV test data."""
    np.random.seed(42)

    # Generate realistic price movements
    returns = np.random.normal(0, 0.02, rows)
    close = 100 * np.exp(np.cumsum(returns))

    # Generate OHLCV
    high = close * (1 + np.abs(np.random.normal(0, 0.01, rows)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, rows)))
    open_price = low + (high - low) * np.random.random(rows)
    volume = np.random.uniform(1000, 10000, rows)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def execute_strategy_code(code: str, df: pd.DataFrame) -> tuple[bool, Optional[str]]:
    """
    Execute generated strategy code and return (success, error_message).

    This actually compiles and runs the strategy to catch runtime errors.
    """
    try:
        # Create execution namespace with required imports
        namespace = {
            'pd': pd,
            'np': np,
            'pandas': pd,
            'numpy': np,
        }

        # Execute the strategy code to define the class
        exec(code, namespace)

        # Find the strategy class (starts with UngStrat_)
        strategy_class = None
        for name, obj in namespace.items():
            if name.startswith('UngStrat_') and isinstance(obj, type):
                strategy_class = obj
                break

        if strategy_class is None:
            return False, "No strategy class found in generated code"

        # Instantiate and run
        strategy = strategy_class()

        # Test calculate_indicators (where vectorization bugs occur)
        df_with_indicators = strategy.calculate_indicators(df.copy())

        # Test generate_signal (where point-in-time bugs occur)
        signal = strategy.generate_signal(df_with_indicators)

        return True, None

    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


class TestUngerGeneratorExecution:
    """Test that ALL entry types generate executable code."""

    @pytest.fixture(scope="class")
    def generator(self):
        """Create generator with real config."""
        config = load_config()._raw_config
        return UngerGenerator(config)

    @pytest.fixture(scope="class")
    def test_df(self):
        """Create test OHLCV data."""
        return create_test_ohlcv(500)

    @pytest.mark.parametrize("entry", ALL_ENTRIES, ids=lambda e: e.id)
    def test_entry_generates_executable_code(self, generator, test_df, entry):
        """
        Test that each entry type generates code that actually executes.

        This catches bugs like:
        - min(df["col1"], df["col2"]) instead of df[["col1","col2"]].min(axis=1)
        - Missing imports
        - Invalid pandas operations
        - Vectorization errors
        """
        # Create minimal blueprint for this entry
        direction = entry.direction if entry.direction != 'BIDI' else 'LONG'
        bp = StrategyBlueprint(
            strategy_id=f"test_{entry.id}",
            timeframe='1h',
            direction=direction,
            entry_condition=entry,
            entry_params=resolve_params(entry.params),
            exit_mechanism=EXIT_MECHANISMS[0],  # TP_ONLY
            sl_config=SL_CONFIGS[0],  # percentage SL
            sl_params={'sl_pct': 0.02},
            tp_config=TP_CONFIGS[0],  # percentage TP
            tp_params={'tp_pct': 0.04},
            trading_coins=['BTC'],
        )

        # Generate code
        code = generator._render_strategy(bp)

        # Execute and verify
        success, error = execute_strategy_code(code, test_df)

        assert success, (
            f"Entry {entry.id} ({entry.name}) generates non-executable code:\n"
            f"Error: {error}\n"
            f"Category: {entry.category}\n"
            f"This is a BUG in the generator or entry template."
        )

    @pytest.mark.parametrize("filter_cfg", ALL_FILTERS, ids=lambda f: f.id)
    def test_filter_generates_executable_code(self, generator, test_df, filter_cfg):
        """
        Test that each filter type generates executable vectorized code.
        """
        # Use a simple entry to test the filter
        simple_entry = next(e for e in ALL_ENTRIES if e.category == 'threshold')

        bp = StrategyBlueprint(
            strategy_id=f"test_filter_{filter_cfg.id}",
            timeframe='1h',
            direction='LONG',
            entry_condition=simple_entry,
            entry_params=resolve_params(simple_entry.params),
            exit_mechanism=EXIT_MECHANISMS[0],
            sl_config=SL_CONFIGS[0],
            sl_params={'sl_pct': 0.02},
            entry_filters=[(filter_cfg, resolve_params(filter_cfg.params))],
            tp_config=TP_CONFIGS[0],
            tp_params={'tp_pct': 0.04},
            trading_coins=['BTC'],
        )

        code = generator._render_strategy(bp)
        success, error = execute_strategy_code(code, test_df)

        assert success, (
            f"Filter {filter_cfg.id} ({filter_cfg.name}) generates non-executable code:\n"
            f"Error: {error}\n"
            f"This is a BUG in the filter template or vectorization."
        )

    def test_all_candlestick_entries_execute(self, generator, test_df):
        """
        Specifically test ALL candlestick (CDL) entries.

        CDL entries often use min()/max() which requires special vectorization.
        """
        cdl_entries = [e for e in ALL_ENTRIES if e.category == 'candlestick']

        failures = []
        for entry in cdl_entries:
            direction = entry.direction if entry.direction != 'BIDI' else 'LONG'
            bp = StrategyBlueprint(
                strategy_id=f"test_cdl_{entry.id}",
                timeframe='1h',
                direction=direction,
                entry_condition=entry,
                entry_params=resolve_params(entry.params),
                exit_mechanism=EXIT_MECHANISMS[0],
                sl_config=SL_CONFIGS[0],
                sl_params={'sl_pct': 0.02},
                tp_config=TP_CONFIGS[0],
                tp_params={'tp_pct': 0.04},
                trading_coins=['BTC'],
            )

            code = generator._render_strategy(bp)
            success, error = execute_strategy_code(code, test_df)

            if not success:
                failures.append(f"{entry.id}: {error}")

        assert not failures, (
            f"\n{len(failures)} CDL entries generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_bidi_entries_execute(self, generator, test_df):
        """Test that BIDI direction entries generate executable code."""
        bidi_entries = [e for e in ALL_ENTRIES if e.direction == 'BIDI']

        if not bidi_entries:
            pytest.skip("No BIDI entries in catalog")

        failures = []
        for entry in bidi_entries:
            bp = StrategyBlueprint(
                strategy_id=f"test_bidi_{entry.id}",
                timeframe='1h',
                direction='BIDI',
                entry_condition=entry,
                entry_params=resolve_params(entry.params),
                exit_mechanism=EXIT_MECHANISMS[0],
                sl_config=SL_CONFIGS[0],
                sl_params={'sl_pct': 0.02},
                tp_config=TP_CONFIGS[0],
                tp_params={'tp_pct': 0.04},
                trading_coins=['BTC'],
                # For BIDI we need both long and short entries
                entry_condition_long=entry,
                entry_condition_short=entry,
                entry_params_long=resolve_params(entry.params),
                entry_params_short=resolve_params(entry.params),
            )

            code = generator._render_strategy(bp)
            success, error = execute_strategy_code(code, test_df)

            if not success:
                failures.append(f"{entry.id}: {error}")

        assert not failures, (
            f"\n{len(failures)} BIDI entries generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )


class TestVectorizationPatterns:
    """Test specific vectorization patterns that have caused bugs."""

    @pytest.fixture
    def generator(self):
        config = load_config()._raw_config
        return UngerGenerator(config)

    def test_min_max_vectorization(self, generator):
        """
        Test that min(df["a"], df["b"]) is correctly vectorized.

        This was a bug: min() on Series raises "truth value ambiguous".
        Fix: convert to df[["a", "b"]].min(axis=1)
        """
        # Test the vectorization function directly
        input_logic = 'lower_wick = min(df["close"], df["open"]) - df["low"]'
        vectorized = generator._vectorize_logic(input_logic)

        # Should be converted to pandas min
        assert 'df[["close", "open"]].min(axis=1)' in vectorized, (
            f"min() not vectorized correctly:\n"
            f"Input:  {input_logic}\n"
            f"Output: {vectorized}"
        )

    def test_max_vectorization(self, generator):
        """Test max() vectorization."""
        input_logic = 'upper_wick = df["high"] - max(df["close"], df["open"])'
        vectorized = generator._vectorize_logic(input_logic)

        assert 'df[["close", "open"]].max(axis=1)' in vectorized, (
            f"max() not vectorized correctly:\n"
            f"Input:  {input_logic}\n"
            f"Output: {vectorized}"
        )

    def test_iloc_removal(self, generator):
        """Test that .iloc[-1] is correctly removed for vectorization."""
        input_logic = 'df["close"].iloc[-1] > df["open"].iloc[-1]'
        vectorized = generator._vectorize_logic(input_logic)

        assert '.iloc[-1]' not in vectorized, (
            f".iloc[-1] not removed:\n"
            f"Input:  {input_logic}\n"
            f"Output: {vectorized}"
        )
        assert 'df["close"] > df["open"]' in vectorized
