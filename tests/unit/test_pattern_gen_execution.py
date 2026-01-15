"""
Tests for PatternGen generator code execution.

These tests ACTUALLY GENERATE AND EXECUTE strategies to catch runtime errors
that static validation misses.

This ensures generated code is runnable before reaching production.
"""
import pytest
import pandas as pd
import numpy as np
from typing import Optional

from src.config import load_config
from src.generator.pattern_gen.generator import PatternGenGenerator
from src.generator.pattern_gen.building_blocks import ALL_BLOCKS


def create_test_ohlcv(rows: int = 500) -> pd.DataFrame:
    """Create realistic OHLCV test data."""
    np.random.seed(42)

    returns = np.random.normal(0, 0.02, rows)
    close = 100 * np.exp(np.cumsum(returns))

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
    """
    try:
        namespace = {
            'pd': pd,
            'np': np,
            'pandas': pd,
            'numpy': np,
        }

        exec(code, namespace)

        # Find the strategy class (starts with PGnStrat_ or PGgStrat_)
        strategy_class = None
        for name, obj in namespace.items():
            if (name.startswith('PGnStrat_') or name.startswith('PGgStrat_')) and isinstance(obj, type):
                strategy_class = obj
                break

        if strategy_class is None:
            return False, "No strategy class found in generated code"

        strategy = strategy_class()

        # Test calculate_indicators
        df_with_indicators = strategy.calculate_indicators(df.copy())

        # Test generate_signal
        signal = strategy.generate_signal(df_with_indicators)

        return True, None

    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"


class TestPatternGenExecution:
    """Test that PatternGen generates executable code."""

    @pytest.fixture(scope="class")
    def generator(self):
        """Create generator with real config."""
        config = load_config()._raw_config
        return PatternGenGenerator(config, seed=42)

    @pytest.fixture(scope="class")
    def test_df(self):
        """Create test OHLCV data."""
        return create_test_ohlcv(500)

    def test_long_strategies_execute(self, generator, test_df):
        """Test that generated LONG strategies execute."""
        results = generator.generate(timeframe='1h', direction='long', count=5)

        failures = []
        for result in results:
            success, error = execute_strategy_code(result.code, test_df)
            if not success:
                failures.append(f"{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} LONG strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_short_strategies_execute(self, generator, test_df):
        """Test that generated SHORT strategies execute."""
        results = generator.generate(timeframe='1h', direction='short', count=5)

        failures = []
        for result in results:
            success, error = execute_strategy_code(result.code, test_df)
            if not success:
                failures.append(f"{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} SHORT strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_bidi_strategies_execute(self, generator, test_df):
        """Test that generated BIDI strategies execute."""
        results = generator.generate(timeframe='1h', direction='bidi', count=5)

        failures = []
        for result in results:
            success, error = execute_strategy_code(result.code, test_df)
            if not success:
                failures.append(f"{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} BIDI strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_all_timeframes_work(self, generator, test_df):
        """Test that strategies work for all timeframes."""
        timeframes = ['15m', '30m', '1h', '2h']

        failures = []
        for tf in timeframes:
            results = generator.generate(timeframe=tf, direction='long', count=2)
            for result in results:
                success, error = execute_strategy_code(result.code, test_df)
                if not success:
                    failures.append(f"{tf}/{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} timeframe/strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_batch_generation_executes(self, generator, test_df):
        """Test that batch-generated strategies execute."""
        results = generator.generate_batch(batch_size=10, timeframe='1h')

        failures = []
        for result in results:
            success, error = execute_strategy_code(result.code, test_df)
            if not success:
                failures.append(f"{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} batch strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    @pytest.mark.parametrize("strategy_type", ["THR", "CRS", "VOL", "PRC", "STA"])
    def test_strategy_types_execute(self, generator, test_df, strategy_type):
        """
        Test strategies of each type execute.

        Generate multiple strategies and check if any match the target type.
        """
        # Generate a batch of strategies
        results = generator.generate(timeframe='1h', direction='long', count=20)

        # Filter to target type
        matching = [r for r in results if r.strategy_type == strategy_type]

        if not matching:
            pytest.skip(f"No {strategy_type} strategies generated in this batch")

        # Test execution
        failures = []
        for result in matching[:3]:  # Test first 3 of this type
            success, error = execute_strategy_code(result.code, test_df)
            if not success:
                failures.append(f"{result.strategy_id}: {error}")

        assert not failures, (
            f"\n{len(failures)} {strategy_type} strategies generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )


class TestPatternGenBlockIntegrity:
    """Test building block integrity and consistency."""

    def test_all_blocks_have_required_fields(self):
        """Ensure all blocks have required fields populated."""
        missing = []
        for block in ALL_BLOCKS:
            if not block.id:
                missing.append(f"Block missing id: {block.name}")
            if not block.name:
                missing.append(f"Block missing name: {block.id}")
            if not block.formula_template:
                missing.append(f"Block missing formula_template: {block.id}")
            if not block.direction:
                missing.append(f"Block missing direction: {block.id}")

        assert not missing, f"Blocks with missing fields:\n" + "\n".join(missing)

    def test_no_duplicate_block_ids(self):
        """Ensure all block IDs are unique."""
        ids = [block.id for block in ALL_BLOCKS]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not duplicates, f"Duplicate block IDs found: {set(duplicates)}"

    def test_block_directions_are_valid(self):
        """Ensure all blocks have valid direction values."""
        valid_directions = {"long", "short", "bidi"}
        invalid = []
        for block in ALL_BLOCKS:
            if block.direction not in valid_directions:
                invalid.append(f"{block.id}: {block.direction}")

        assert not invalid, f"Blocks with invalid direction:\n" + "\n".join(invalid)

    def test_all_categories_represented(self):
        """Ensure we have blocks in all expected categories."""
        expected_categories = {"threshold", "crossover", "volume", "price_action", "statistical"}
        actual_categories = set(block.category for block in ALL_BLOCKS)

        missing = expected_categories - actual_categories
        assert not missing, f"Missing block categories: {missing}"
