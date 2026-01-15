"""
Tests for Unger entries validation.

These tests ensure that all pandas_ta function calls in entry conditions
have correct signatures that match the actual pandas_ta library.
"""

import pytest

from src.generator.unger.validate_entries import validate_entry, validate_all_entries
from src.generator.unger.catalogs.entries import ALL_ENTRIES, TREND_ADVANCED_ENTRIES


class TestUngerEntriesValidation:
    """Test suite for Unger entries validation."""

    def test_all_entries_have_valid_pandas_ta_signatures(self):
        """
        Validate all entries have correct pandas_ta function calls.

        This test will fail if any entry has:
        - Wrong number of positional arguments
        - Arguments in wrong order (e.g., close instead of high)
        - Unknown pandas_ta functions
        """
        broken, _ = validate_all_entries()

        if broken:
            error_msg = f"\n{len(broken)} entries have invalid pandas_ta calls:\n"
            for entry_id, entry_name, errors in broken[:10]:
                error_msg += f"\n  {entry_id}: {entry_name}\n"
                for err in errors:
                    error_msg += f"    - {err}\n"
            if len(broken) > 10:
                error_msg += f"\n  ... and {len(broken) - 10} more\n"
            error_msg += "\nRun: python -m src.generator.unger.validate_entries"
            pytest.fail(error_msg)

    def test_no_duplicate_entry_ids(self):
        """Ensure all entry IDs are unique."""
        ids = [entry.id for entry in ALL_ENTRIES]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        assert not duplicates, f"Duplicate entry IDs found: {set(duplicates)}"

    def test_all_entries_have_required_fields(self):
        """Ensure all entries have required fields populated."""
        missing = []
        for entry in ALL_ENTRIES:
            if not entry.id:
                missing.append(f"Entry missing id: {entry.name}")
            if not entry.name:
                missing.append(f"Entry missing name: {entry.id}")
            if not entry.logic_template:
                missing.append(f"Entry missing logic_template: {entry.id}")
            if not entry.direction:
                missing.append(f"Entry missing direction: {entry.id}")

        assert not missing, f"Entries with missing fields:\n" + "\n".join(missing)

    def test_psar_entries_have_correct_signature(self):
        """Specifically test PSAR entries (previously broken)."""
        psar_entries = [e for e in ALL_ENTRIES if "psar" in e.logic_template.lower()]

        for entry in psar_entries:
            errors, _ = validate_entry(entry)
            assert not errors, (
                f"PSAR entry {entry.id} has errors: {errors}\n"
                "PSAR should be called with (high, low) only, NOT (high, low, close)"
            )

    @pytest.mark.parametrize(
        "entry_id,expected_func",
        [
            ("TRD_03", "psar"),
            ("TRD_04", "psar"),
            ("TRD_05", "ichimoku"),
            ("TRD_06", "ichimoku"),
        ],
    )
    def test_specific_entries_use_expected_functions(self, entry_id: str, expected_func: str):
        """Verify specific entries use the expected pandas_ta functions."""
        entry = next((e for e in ALL_ENTRIES if e.id == entry_id), None)
        assert entry is not None, f"Entry {entry_id} not found"
        assert expected_func in entry.logic_template.lower(), (
            f"Entry {entry_id} should use {expected_func}"
        )

    def test_trend_advanced_entries_import_pandas_ta(self):
        """Ensure all trend_advanced entries import pandas_ta."""
        for entry in TREND_ADVANCED_ENTRIES:
            if "ta." in entry.logic_template:
                assert "pandas_ta" in entry.logic_template, (
                    f"Entry {entry.id} uses ta.xxx() but doesn't import pandas_ta"
                )

    def test_entry_directions_are_valid(self):
        """Ensure all entries have valid direction values."""
        valid_directions = {"LONG", "SHORT", "BIDI"}
        invalid = []
        for entry in ALL_ENTRIES:
            if entry.direction not in valid_directions:
                invalid.append(f"{entry.id}: {entry.direction}")

        assert not invalid, f"Entries with invalid direction:\n" + "\n".join(invalid)

    def test_all_indicators_have_lookback_formulas(self):
        """
        Ensure all indicators_used in entries have lookback formulas.

        This prevents runtime warnings like:
        'Unknown indicator for lookback calculation: XXX'
        """
        from src.generator.unger.lookback import LOOKBACK_FORMULAS

        # Collect all unique indicators from all entries
        all_indicators = set()
        for entry in ALL_ENTRIES:
            if entry.indicators_used:
                for indicator in entry.indicators_used:
                    all_indicators.add(indicator.upper())

        # Check which are missing
        missing = []
        for indicator in sorted(all_indicators):
            if indicator not in LOOKBACK_FORMULAS:
                # Find which entries use this indicator
                using_entries = [
                    e.id for e in ALL_ENTRIES
                    if e.indicators_used and indicator in [i.upper() for i in e.indicators_used]
                ]
                missing.append(f"{indicator} (used by: {', '.join(using_entries[:3])}{'...' if len(using_entries) > 3 else ''})")

        assert not missing, (
            f"\n{len(missing)} indicators missing lookback formulas in lookback.py:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nAdd formulas to LOOKBACK_FORMULAS in src/generator/unger/lookback.py"
        )
