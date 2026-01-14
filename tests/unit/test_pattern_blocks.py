"""
Unit tests for pattern_gen building_blocks validation.

This test ensures ALL PatternBlocks in building_blocks.py:
1. Execute without exceptions
2. Produce a valid entry_signal column
3. Have correct boolean dtype

Run with: pytest tests/unit/test_pattern_blocks.py -v
"""

import pytest
from src.generator.pattern_gen.validate_blocks import (
    validate_all_blocks,
    generate_synthetic_ohlcv,
    validate_block,
)


class TestPatternBlocks:
    """Test all pattern blocks for correctness."""

    def test_all_blocks_pass_validation(self):
        """Every PatternBlock must pass validation."""
        results, summary = validate_all_blocks()

        # Collect failures for detailed error message
        failures = [r for r in results if not r.success]

        if failures:
            failure_details = "\n".join(
                f"  - {r.block_id}: {r.error}" for r in failures
            )
            pytest.fail(
                f"{len(failures)} blocks failed validation:\n{failure_details}"
            )

        assert summary['failed'] == 0, f"Expected 0 failures, got {summary['failed']}"
        assert summary['passed'] == summary['total'], "Not all blocks passed"

    def test_synthetic_data_generation(self):
        """Synthetic data must have correct structure."""
        df = generate_synthetic_ohlcv(100)

        assert len(df) == 100
        assert set(df.columns) == {'open', 'high', 'low', 'close', 'volume'}
        assert (df['high'] >= df['close']).all()
        assert (df['high'] >= df['open']).all()
        assert (df['low'] <= df['close']).all()
        assert (df['low'] <= df['open']).all()
        assert (df['volume'] > 0).all()

    def test_no_nan_in_entry_signals_after_lookback(self):
        """Entry signals should not have NaN after lookback period."""
        from src.generator.pattern_gen.building_blocks import ALL_BLOCKS

        df = generate_synthetic_ohlcv(300)
        blocks_with_nan = []

        for block in ALL_BLOCKS:
            result = validate_block(block, df)
            if result.warning and "NaN values" in result.warning:
                blocks_with_nan.append(block.id)

        if blocks_with_nan:
            pytest.fail(
                f"{len(blocks_with_nan)} blocks have NaN in entry_signal after lookback:\n"
                + "\n".join(f"  - {b}" for b in blocks_with_nan[:10])
            )


class TestSpecificPatterns:
    """Test specific patterns that had issues in the past."""

    def test_squeeze_blocks_no_float_error(self):
        """SQUEEZE blocks must handle shifted booleans correctly."""
        from src.generator.pattern_gen.building_blocks import SQUEEZE_BLOCKS

        df = generate_synthetic_ohlcv(100)

        for block in SQUEEZE_BLOCKS:
            result = validate_block(block, df)
            assert result.success, f"{block.id} failed: {result.error}"

    def test_elder_impulse_blocks_no_float_error(self):
        """ELDER_IMPULSE blocks must handle shifted booleans correctly."""
        from src.generator.pattern_gen.building_blocks import ELDER_IMPULSE_BLOCKS

        df = generate_synthetic_ohlcv(100)

        for block in ELDER_IMPULSE_BLOCKS:
            result = validate_block(block, df)
            assert result.success, f"{block.id} failed: {result.error}"

    def test_chandelier_blocks_no_float_error(self):
        """CHANDELIER blocks must handle shifted booleans correctly."""
        from src.generator.pattern_gen.building_blocks import CHANDELIER_EXIT_BLOCKS

        df = generate_synthetic_ohlcv(100)

        for block in CHANDELIER_EXIT_BLOCKS:
            result = validate_block(block, df)
            assert result.success, f"{block.id} failed: {result.error}"

    def test_dynamic_momentum_blocks_no_nan_cast(self):
        """DYNAMIC_MOMENTUM blocks must handle NaN in astype(int)."""
        from src.generator.pattern_gen.building_blocks import DYNAMIC_MOMENTUM_BLOCKS

        df = generate_synthetic_ohlcv(100)

        for block in DYNAMIC_MOMENTUM_BLOCKS:
            result = validate_block(block, df)
            assert result.success, f"{block.id} failed: {result.error}"
