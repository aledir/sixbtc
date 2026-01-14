"""
Systematic validation of ALL PatternBlocks in building_blocks.py.

This script tests every single block by:
1. Generating synthetic OHLCV data
2. Executing the formula_template with real params
3. Verifying no exceptions are raised
4. Checking entry_signal column exists and is boolean

Run this BEFORE deploying any changes to building_blocks.py.
"""

import pandas as pd
import numpy as np
import talib as ta
from typing import Any
from dataclasses import dataclass


@dataclass
class ValidationResult:
    block_id: str
    success: bool
    error: str | None = None
    warning: str | None = None


def generate_synthetic_ohlcv(n_bars: int = 200) -> pd.DataFrame:
    """Generate realistic OHLCV data for testing."""
    np.random.seed(42)

    # Generate price series with trend and noise
    returns = np.random.normal(0.0002, 0.02, n_bars)
    close = 100 * np.exp(np.cumsum(returns))

    # Generate OHLC from close
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n_bars)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n_bars)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]

    # Ensure high >= close >= low and high >= open >= low
    high = np.maximum(high, np.maximum(close, open_))
    low = np.minimum(low, np.minimum(close, open_))

    # Generate volume
    volume = np.random.uniform(1000, 10000, n_bars)

    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })


def validate_block(block: Any, df: pd.DataFrame) -> ValidationResult:
    """Validate a single PatternBlock."""
    block_id = block.id

    try:
        # Get first param combination
        params = {}
        for key, values in block.params.items():
            params[key] = values[0] if isinstance(values, list) else values

        # Format the formula with params
        formula = block.formula_template.format(**params)

        # Execute the formula
        local_vars = {'df': df.copy(), 'ta': ta, 'np': np, 'pd': pd}
        exec(formula, local_vars)
        df_result = local_vars['df']

        # Check entry_signal exists
        if 'entry_signal' not in df_result.columns:
            return ValidationResult(
                block_id=block_id,
                success=False,
                error="Missing 'entry_signal' column after execution"
            )

        # Check entry_signal dtype
        signal_col = df_result['entry_signal']
        if signal_col.dtype == 'float64':
            # Check if it's actually boolean-like (0.0, 1.0, NaN)
            unique_vals = signal_col.dropna().unique()
            if not all(v in [0.0, 1.0, True, False] for v in unique_vals):
                return ValidationResult(
                    block_id=block_id,
                    success=False,
                    error=f"entry_signal is float with non-boolean values: {unique_vals[:5]}"
                )
            # Warning: float instead of bool (might cause issues with ~)
            return ValidationResult(
                block_id=block_id,
                success=True,
                warning="entry_signal is float64 instead of bool (potential ~ operator issue)"
            )

        if signal_col.dtype != 'bool':
            return ValidationResult(
                block_id=block_id,
                success=False,
                error=f"entry_signal has unexpected dtype: {signal_col.dtype}"
            )

        # Check for NaN in entry_signal (after lookback period)
        lookback = block.lookback
        valid_signals = signal_col.iloc[lookback:]
        if valid_signals.isna().any():
            nan_count = valid_signals.isna().sum()
            return ValidationResult(
                block_id=block_id,
                success=True,
                warning=f"{nan_count} NaN values in entry_signal after lookback={lookback}"
            )

        return ValidationResult(block_id=block_id, success=True)

    except Exception as e:
        return ValidationResult(
            block_id=block_id,
            success=False,
            error=f"{type(e).__name__}: {str(e)}"
        )


def validate_all_blocks() -> tuple[list[ValidationResult], dict]:
    """Validate ALL blocks in building_blocks.py."""
    from src.generator.pattern_gen.building_blocks import ALL_BLOCKS

    df = generate_synthetic_ohlcv(300)  # Extra bars for high lookback

    results = []
    for block in ALL_BLOCKS:
        result = validate_block(block, df)
        results.append(result)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    warnings = sum(1 for r in results if r.warning)

    summary = {
        'total': total,
        'passed': passed,
        'failed': failed,
        'with_warnings': warnings,
        'pass_rate': f"{passed/total*100:.1f}%"
    }

    return results, summary


def print_report(results: list[ValidationResult], summary: dict) -> None:
    """Print validation report."""
    print("=" * 70)
    print("PATTERN BLOCK VALIDATION REPORT")
    print("=" * 70)
    print(f"Total blocks: {summary['total']}")
    print(f"Passed: {summary['passed']} ({summary['pass_rate']})")
    print(f"Failed: {summary['failed']}")
    print(f"With warnings: {summary['with_warnings']}")
    print("=" * 70)

    # Print failures
    failures = [r for r in results if not r.success]
    if failures:
        print("\nFAILURES:")
        print("-" * 70)
        for r in failures:
            print(f"  {r.block_id}: {r.error}")

    # Print warnings
    warnings = [r for r in results if r.warning]
    if warnings:
        print("\nWARNINGS:")
        print("-" * 70)
        for r in warnings:
            print(f"  {r.block_id}: {r.warning}")

    if not failures:
        print("\nAll blocks validated successfully!")


if __name__ == "__main__":
    results, summary = validate_all_blocks()
    print_report(results, summary)

    # Exit with error code if failures
    if summary['failed'] > 0:
        exit(1)
