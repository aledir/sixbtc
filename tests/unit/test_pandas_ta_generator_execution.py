"""
Tests for PandasTa generator code execution.

These tests ACTUALLY GENERATE AND EXECUTE strategies to catch runtime errors
that static validation misses.

This ensures generated code is runnable before reaching production.
"""
import pytest
import pandas as pd
import numpy as np
from typing import Optional

from src.config import load_config
from src.generator.pandas_ta.generator import PandasTaGenerator
from src.generator.pandas_ta.composer import PtaBlueprint, PtaEntryCondition, PtaComposer
from src.generator.pandas_ta.catalogs.indicators import ALL_INDICATORS, PtaIndicator
from src.generator.pandas_ta.catalogs.conditions import (
    ConditionType, CATEGORY_CONDITIONS, INDICATOR_THRESHOLDS
)
from src.generator.unger.catalogs.sl_types import SL_CONFIGS
from src.generator.unger.catalogs.tp_types import TP_CONFIGS
from src.generator.unger.catalogs.exit_mechanisms import EXIT_MECHANISMS


def resolve_params(params: dict) -> dict:
    """
    Resolve parameter ranges to single values.

    Params in catalogs are ranges like {"length": [10, 14, 20]}.
    For testing, we pick the first value from each list.
    """
    if not params:
        return {}

    resolved = {}
    for key, value in params.items():
        if isinstance(value, list) and value:
            resolved[key] = value[0]
        else:
            resolved[key] = value
    return resolved


def create_test_ohlcv(rows: int = 500) -> pd.DataFrame:
    """Create realistic OHLCV test data with DatetimeIndex."""
    np.random.seed(42)

    returns = np.random.normal(0, 0.02, rows)
    close = 100 * np.exp(np.cumsum(returns))

    high = close * (1 + np.abs(np.random.normal(0, 0.01, rows)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, rows)))
    open_price = low + (high - low) * np.random.random(rows)
    volume = np.random.uniform(1000, 10000, rows)

    # DatetimeIndex required by pandas_ta indicators like VWAP
    dates = pd.date_range(end=pd.Timestamp.now(), periods=rows, freq='15min')

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }, index=dates)


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

        # Find the strategy class (starts with PtaStrat_)
        strategy_class = None
        for name, obj in namespace.items():
            if name.startswith('PtaStrat_') and isinstance(obj, type):
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


def get_default_threshold(indicator: PtaIndicator, condition_type: ConditionType) -> float:
    """Get a sensible default threshold for testing."""
    # Check if we have specific thresholds for this indicator
    thresholds = INDICATOR_THRESHOLDS.get(indicator.id, {})

    if condition_type in [ConditionType.THRESHOLD_BELOW, ConditionType.CROSSED_BELOW]:
        # Use oversold threshold
        if "oversold" in thresholds and thresholds["oversold"]:
            return thresholds["oversold"][0]
        return 30.0  # Default for oscillators

    elif condition_type in [ConditionType.THRESHOLD_ABOVE, ConditionType.CROSSED_ABOVE]:
        # Use overbought threshold
        if "overbought" in thresholds and thresholds["overbought"]:
            return thresholds["overbought"][0]
        return 70.0  # Default for oscillators

    # For other condition types (SLOPE_UP, etc.), use 0
    return 0.0


class TestPandasTaGeneratorExecution:
    """Test that ALL indicator types generate executable code."""

    @pytest.fixture(scope="class")
    def generator(self):
        """Create generator with real config."""
        config = load_config()._raw_config
        return PandasTaGenerator(config)

    @pytest.fixture(scope="class")
    def composer(self):
        """Create composer for building blueprints."""
        config = load_config()._raw_config
        return PtaComposer(config)

    @pytest.fixture(scope="class")
    def test_df(self):
        """Create test OHLCV data."""
        return create_test_ohlcv(500)

    @pytest.mark.parametrize("indicator", ALL_INDICATORS, ids=lambda i: i.id)
    def test_indicator_generates_executable_code(self, generator, test_df, indicator):
        """
        Test that each indicator type generates code that actually executes.

        This catches bugs like:
        - Wrong pandas_ta function signatures
        - Invalid condition logic
        - Missing imports
        """
        # Get a compatible condition type for this indicator's category
        compatible_conditions = CATEGORY_CONDITIONS.get(
            indicator.category, [ConditionType.THRESHOLD_ABOVE]
        )
        condition_type = compatible_conditions[0]

        # Create entry condition with resolved parameters
        entry_condition = PtaEntryCondition(
            indicator=indicator,
            condition_type=condition_type,
            indicator_params=resolve_params(indicator.params),
            threshold=get_default_threshold(indicator, condition_type),
        )

        # Create minimal blueprint
        bp = PtaBlueprint(
            strategy_id=f"test_{indicator.id}",
            timeframe='1h',
            direction='LONG',
            regime_type='MIXED',
            entry_conditions=[entry_condition],
            exit_mechanism=EXIT_MECHANISMS[0],
            sl_config=SL_CONFIGS[0],
            sl_params={'sl_pct': 0.02},
            tp_config=TP_CONFIGS[0],
            tp_params={'tp_pct': 0.04},
            trading_coins=['BTC'],
        )

        # Generate code
        code = generator._render_strategy(bp)

        # Execute and verify
        success, error = execute_strategy_code(code, test_df)

        assert success, (
            f"Indicator {indicator.id} ({indicator.name}) generates non-executable code:\n"
            f"Error: {error}\n"
            f"Category: {indicator.category}\n"
            f"Condition: {condition_type.value}\n"
            f"This is a BUG in the generator or indicator template."
        )

    def test_all_condition_types_execute(self, generator, test_df):
        """Test that all condition types generate executable code."""
        # Use RSI as a simple indicator that supports many condition types
        rsi = next(i for i in ALL_INDICATORS if i.id == 'RSI')

        failures = []
        rsi_conditions = CATEGORY_CONDITIONS.get(rsi.category, [])
        for condition_type in rsi_conditions:

            entry_condition = PtaEntryCondition(
                indicator=rsi,
                condition_type=condition_type,
                indicator_params=resolve_params(rsi.params),
                threshold=get_default_threshold(rsi, condition_type),
                threshold_high=70.0 if condition_type == ConditionType.BETWEEN else None,
            )

            bp = PtaBlueprint(
                strategy_id=f"test_condition_{condition_type.value}",
                timeframe='1h',
                direction='LONG',
                regime_type='MIXED',
                entry_conditions=[entry_condition],
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
                failures.append(f"{condition_type.value}: {error}")

        assert not failures, (
            f"\n{len(failures)} condition types generate non-executable code:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )

    def test_multi_indicator_strategy_executes(self, generator, test_df):
        """Test that strategies with 2-3 indicators execute."""
        # Get a few compatible indicators
        rsi = next(i for i in ALL_INDICATORS if i.id == 'RSI')
        macd = next(i for i in ALL_INDICATORS if i.id == 'MACD')

        entry_conditions = [
            PtaEntryCondition(
                indicator=rsi,
                condition_type=ConditionType.THRESHOLD_BELOW,
                indicator_params=resolve_params(rsi.params),
                threshold=30.0,
            ),
            PtaEntryCondition(
                indicator=macd,
                condition_type=ConditionType.CROSSED_ABOVE,
                indicator_params=resolve_params(macd.params),
                threshold=0.0,
            ),
        ]

        bp = PtaBlueprint(
            strategy_id="test_multi_indicator",
            timeframe='1h',
            direction='LONG',
            regime_type='MIXED',
            entry_conditions=entry_conditions,
            exit_mechanism=EXIT_MECHANISMS[0],
            sl_config=SL_CONFIGS[0],
            sl_params={'sl_pct': 0.02},
            tp_config=TP_CONFIGS[0],
            tp_params={'tp_pct': 0.04},
            trading_coins=['BTC'],
        )

        code = generator._render_strategy(bp)
        success, error = execute_strategy_code(code, test_df)

        assert success, (
            f"Multi-indicator strategy generates non-executable code:\n"
            f"Error: {error}"
        )

    def test_bidi_strategy_executes(self, generator, test_df):
        """Test that BIDI strategies with separate long/short conditions execute."""
        rsi = next(i for i in ALL_INDICATORS if i.id == 'RSI')

        long_condition = PtaEntryCondition(
            indicator=rsi,
            condition_type=ConditionType.THRESHOLD_BELOW,
            indicator_params=resolve_params(rsi.params),
            threshold=30.0,
        )

        short_condition = PtaEntryCondition(
            indicator=rsi,
            condition_type=ConditionType.THRESHOLD_ABOVE,
            indicator_params=resolve_params(rsi.params),
            threshold=70.0,
        )

        bp = PtaBlueprint(
            strategy_id="test_bidi",
            timeframe='1h',
            direction='BIDI',
            regime_type='MIXED',
            entry_conditions=[long_condition],  # Default
            exit_mechanism=EXIT_MECHANISMS[0],
            sl_config=SL_CONFIGS[0],
            sl_params={'sl_pct': 0.02},
            tp_config=TP_CONFIGS[0],
            tp_params={'tp_pct': 0.04},
            trading_coins=['BTC'],
            entry_conditions_long=[long_condition],
            entry_conditions_short=[short_condition],
        )

        code = generator._render_strategy(bp)
        success, error = execute_strategy_code(code, test_df)

        assert success, (
            f"BIDI strategy generates non-executable code:\n"
            f"Error: {error}"
        )

    def test_all_categories_have_working_indicators(self, generator, test_df):
        """Test at least one indicator from each category works."""
        categories = set(ind.category for ind in ALL_INDICATORS)

        failures = []
        for category in categories:
            # Get first indicator from this category
            indicator = next(i for i in ALL_INDICATORS if i.category == category)

            compatible_conditions = CATEGORY_CONDITIONS.get(
                indicator.category, [ConditionType.THRESHOLD_ABOVE]
            )
            condition_type = compatible_conditions[0]

            entry_condition = PtaEntryCondition(
                indicator=indicator,
                condition_type=condition_type,
                indicator_params=resolve_params(indicator.params),
                threshold=get_default_threshold(indicator, condition_type),
            )

            bp = PtaBlueprint(
                strategy_id=f"test_category_{category}",
                timeframe='1h',
                direction='LONG',
                regime_type='MIXED',
                entry_conditions=[entry_condition],
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
                failures.append(f"{category} ({indicator.id}): {error}")

        assert not failures, (
            f"\n{len(failures)} categories have non-working indicators:\n"
            + "\n".join(f"  - {f}" for f in failures)
        )
