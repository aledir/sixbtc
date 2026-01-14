"""
Tests for pandas_ta catalog validation.

These tests ensure that all indicators in the catalog have correct
input_type declarations that match the actual pandas_ta function signatures.
"""
import pytest

from src.generator.pandas_ta.validate_catalog import validate_indicator
from src.generator.pandas_ta.catalogs.indicators import ALL_INDICATORS, INDICATORS_BY_ID


class TestPandasTaCatalogValidation:
    """Test suite for pandas_ta catalog validation."""

    def test_all_indicators_have_valid_signatures(self):
        """
        Validate all indicators have correct input_type declarations.

        This test will fail if any indicator has:
        - An input_type not supported by the template
        - Missing required positional arguments
        - Extra arguments that conflict with keyword params
        """
        broken = []

        for ind in ALL_INDICATORS:
            errors, _ = validate_indicator(ind)
            if errors:
                broken.append((ind.id, errors))

        if broken:
            error_msg = f"\n{len(broken)} indicators have invalid configurations:\n"
            for ind_id, errors in broken[:10]:  # Show first 10
                error_msg += f"\n  {ind_id}:\n"
                for err in errors:
                    error_msg += f"    - {err}\n"
            if len(broken) > 10:
                error_msg += f"\n  ... and {len(broken) - 10} more\n"
            error_msg += "\nRun: python -m src.generator.pandas_ta.validate_catalog"
            pytest.fail(error_msg)

    @pytest.mark.parametrize(
        "indicator_id,expected_input_type",
        [
            ("RSI", "close"),
            ("ATR", "hlc"),
            ("ADX", "hlc"),
            ("MACD", "close"),
            ("BBANDS", "close"),
        ],
    )
    def test_common_indicators_have_correct_input_type(
        self, indicator_id: str, expected_input_type: str
    ):
        """Verify common indicators have the expected input_type."""
        if indicator_id not in INDICATORS_BY_ID:
            pytest.skip(f"Indicator {indicator_id} not in catalog")

        ind = INDICATORS_BY_ID[indicator_id]
        actual = getattr(ind, "input_type", None) or "close"
        assert actual == expected_input_type, (
            f"{indicator_id} has input_type='{actual}', expected '{expected_input_type}'"
        )

    def test_no_duplicate_indicator_ids(self):
        """Ensure all indicator IDs are unique."""
        ids = [ind.id for ind in ALL_INDICATORS]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not duplicates, f"Duplicate indicator IDs found: {set(duplicates)}"

    def test_all_indicators_have_pandas_ta_func(self):
        """Ensure all indicators have a pandas_ta_func defined."""
        missing = [ind.id for ind in ALL_INDICATORS if not ind.pandas_ta_func]
        assert not missing, f"Indicators missing pandas_ta_func: {missing}"
