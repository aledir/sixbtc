"""
Validation script for Unger entry conditions.

Checks:
1. pandas_ta function signatures are correct
2. lookback_required is sufficient for the indicators used

Run: python -m src.generator.unger.validate_entries
"""

import re
import inspect
from functools import lru_cache
from typing import Tuple

import numpy as np
import pandas as pd
import pandas_ta

from src.generator.unger.catalogs.entries import ALL_ENTRIES


# Known pandas_ta function signatures (positional args only)
# Format: function_name -> (required_positional_args, optional_positional_args)
PANDAS_TA_SIGNATURES = {
    # Trend indicators
    "supertrend": (["high", "low", "close"], []),
    "psar": (["high", "low"], []),  # close is NOT a positional arg!
    "ichimoku": (["high", "low", "close"], []),
    "aroon": (["high", "low"], []),
    "vortex": (["high", "low", "close"], []),
    "chop": (["high", "low", "close"], []),
    "chandelier_exit": (["high", "low", "close"], []),

    # MA indicators
    "hma": (["close"], []),
    "alma": (["close"], []),
    "ema": (["close"], []),
    "sma": (["close"], []),
    "wma": (["close"], []),
    "t3": (["close"], []),
    "tema": (["close"], []),
    "dema": (["close"], []),
    "kama": (["close"], []),
    "fwma": (["close"], []),
    "pwma": (["close"], []),
    "swma": (["close"], []),
    "vidya": (["close"], []),
    "zlma": (["close"], []),

    # Momentum indicators
    "tsi": (["close"], []),
    "fisher": (["high", "low"], []),
    "cmo": (["close"], []),
    "uo": (["high", "low", "close"], []),
    "stochrsi": (["close"], []),
    "rvgi": (["open", "high", "low", "close"], []),
    "qqe": (["close"], []),
    "inertia": (["close"], ["high", "low"]),  # high, low are optional
    "rsx": (["close"], []),
    "rsi": (["close"], []),
    "macd": (["close"], []),
    "stoch": (["high", "low", "close"], []),
    "willr": (["high", "low", "close"], []),
    "cci": (["high", "low", "close"], []),
    "mom": (["close"], []),
    "roc": (["close"], []),

    # Volume indicators
    "cmf": (["high", "low", "close", "volume"], []),
    "efi": (["close", "volume"], []),
    "kvo": (["high", "low", "close", "volume"], []),
    "pvo": (["volume"], []),
    "nvi": (["close", "volume"], []),
    "pvi": (["close", "volume"], []),
    "aobv": (["close", "volume"], []),
    "ad": (["high", "low", "close", "volume"], []),
    "adosc": (["high", "low", "close", "volume"], []),
    "obv": (["close", "volume"], []),
    "mfi": (["high", "low", "close", "volume"], []),
    "vwap": (["high", "low", "close", "volume"], []),

    # Volatility indicators
    "atr": (["high", "low", "close"], []),
    "natr": (["high", "low", "close"], []),
    "bbands": (["close"], []),
    "kc": (["high", "low", "close"], []),
    "donchian": (["high", "low"], []),
    "massi": (["high", "low"], []),
    "thermo": (["high", "low"], []),

    # Other
    "squeeze": (["high", "low", "close"], []),
    "squeeze_pro": (["high", "low", "close"], []),
    "adx": (["high", "low", "close"], []),
    "dm": (["high", "low"], []),
}


@lru_cache(maxsize=100)
def detect_min_lookback(func_name: str) -> int:
    """
    Auto-detect minimum bars needed for a pandas_ta function.

    Tests with increasing bar counts until valid output is produced.
    Results are cached for performance.

    Args:
        func_name: Name of the pandas_ta function (e.g., 'ichimoku', 'qqe')

    Returns:
        Minimum number of bars needed (includes 10-bar safety buffer)
    """
    func = getattr(pandas_ta, func_name, None)
    if func is None:
        return 50  # Default fallback

    # Get function signature to determine required args
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
    except (ValueError, TypeError):
        return 50

    # Test with increasing bar counts
    for n_bars in range(20, 150, 5):
        np.random.seed(42)
        df = pd.DataFrame({
            'open': 100 + np.random.randn(n_bars).cumsum(),
            'high': 101 + np.random.randn(n_bars).cumsum(),
            'low': 99 + np.random.randn(n_bars).cumsum(),
            'close': 100 + np.random.randn(n_bars).cumsum(),
            'volume': np.random.randint(1000, 10000, n_bars).astype(float),
        })
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)

        try:
            # Build args based on function signature
            args = []
            for p in params[:5]:  # First 5 positional args
                p_lower = p.lower()
                if p_lower in ('high', 'h'):
                    args.append(df['high'])
                elif p_lower in ('low', 'l'):
                    args.append(df['low'])
                elif p_lower in ('close', 'c'):
                    args.append(df['close'])
                elif p_lower in ('open', 'o'):
                    args.append(df['open'])
                elif p_lower in ('volume', 'v'):
                    args.append(df['volume'])
                else:
                    break

            if not args:
                return 50  # Can't determine args

            result = func(*args)

            # Check if result is valid
            if result is None:
                continue
            if isinstance(result, tuple):
                if result[0] is None:
                    continue
                result = result[0]

            # Check last value is not NaN
            if isinstance(result, pd.DataFrame):
                if result.iloc[-1].isna().all():
                    continue
            elif isinstance(result, pd.Series):
                if pd.isna(result.iloc[-1]):
                    continue

            # Add 10-bar safety buffer
            return n_bars + 10

        except Exception:
            continue

    return 150  # Fallback for very demanding indicators


def extract_ta_calls(logic_template: str) -> list[Tuple[str, list[str]]]:
    """
    Extract all ta.xxx(...) calls from logic_template.

    Returns list of (function_name, [positional_args])
    """
    calls = []

    # Pattern to match ta.function_name(args)
    # Handles multiline and nested parentheses
    pattern = r'ta\.(\w+)\s*\(([^)]*)\)'

    for match in re.finditer(pattern, logic_template, re.DOTALL):
        func_name = match.group(1).lower()
        args_str = match.group(2).strip()

        # Parse positional arguments (before any keyword arg)
        positional_args = []
        if args_str:
            # Split by comma, but be careful with nested brackets
            depth = 0
            current_arg = ""
            for char in args_str:
                if char in '([{':
                    depth += 1
                    current_arg += char
                elif char in ')]}':
                    depth -= 1
                    current_arg += char
                elif char == ',' and depth == 0:
                    arg = current_arg.strip()
                    if arg and '=' not in arg:  # Positional arg
                        positional_args.append(arg)
                    elif '=' in arg:  # Keyword arg - stop
                        break
                    current_arg = ""
                else:
                    current_arg += char

            # Last argument
            arg = current_arg.strip()
            if arg and '=' not in arg:
                positional_args.append(arg)

        calls.append((func_name, positional_args))

    return calls


def validate_entry(entry, check_lookback: bool = True) -> Tuple[list[str], list[str]]:
    """
    Validate a single entry's logic_template.

    Args:
        entry: EntryCondition to validate
        check_lookback: If True, also validate lookback_required is sufficient

    Returns (errors, warnings)
    """
    errors = []
    warnings = []

    # Skip entries without pandas_ta imports
    if "pandas_ta" not in entry.logic_template and "import pandas_ta" not in entry.logic_template:
        return errors, warnings

    # Extract ta.xxx() calls
    ta_calls = extract_ta_calls(entry.logic_template)

    # Check lookback requirements
    if check_lookback and ta_calls:
        max_required_lookback = 0
        for func_name, _ in ta_calls:
            min_lookback = detect_min_lookback(func_name)
            max_required_lookback = max(max_required_lookback, min_lookback)

        if entry.lookback_required < max_required_lookback:
            errors.append(
                f"lookback_required={entry.lookback_required} is insufficient, "
                f"indicator needs at least {max_required_lookback} bars"
            )

    for func_name, positional_args in ta_calls:
        # Check if we know this function
        if func_name not in PANDAS_TA_SIGNATURES:
            # Try to get signature from pandas_ta itself
            if hasattr(pandas_ta, func_name):
                warnings.append(f"Unknown signature for ta.{func_name}() - add to PANDAS_TA_SIGNATURES")
            else:
                errors.append(f"Unknown pandas_ta function: ta.{func_name}()")
            continue

        required_args, optional_args = PANDAS_TA_SIGNATURES[func_name]
        expected_count = len(required_args)
        max_count = len(required_args) + len(optional_args)
        actual_count = len(positional_args)

        # Check argument count
        if actual_count < expected_count:
            errors.append(
                f"ta.{func_name}(): expected {expected_count} positional args "
                f"({', '.join(required_args)}), got {actual_count}: {positional_args}"
            )
        elif actual_count > max_count:
            errors.append(
                f"ta.{func_name}(): too many positional args. "
                f"Expected max {max_count} ({', '.join(required_args + optional_args)}), "
                f"got {actual_count}: {positional_args}"
            )

        # Check argument types (basic validation)
        for i, arg in enumerate(positional_args):
            if i < len(required_args):
                expected_col = required_args[i]
                # Check if argument references expected column type
                if expected_col == "close" and "close" not in arg.lower():
                    if "high" in arg.lower() or "low" in arg.lower() or "open" in arg.lower() or "volume" in arg.lower():
                        warnings.append(
                            f"ta.{func_name}(): arg {i+1} should be 'close', got '{arg}'"
                        )
                elif expected_col == "high" and "high" not in arg.lower():
                    if "close" in arg.lower() or "low" in arg.lower():
                        warnings.append(
                            f"ta.{func_name}(): arg {i+1} should be 'high', got '{arg}'"
                        )
                elif expected_col == "low" and "low" not in arg.lower():
                    if "close" in arg.lower() or "high" in arg.lower():
                        warnings.append(
                            f"ta.{func_name}(): arg {i+1} should be 'low', got '{arg}'"
                        )
                elif expected_col == "volume" and "volume" not in arg.lower():
                    warnings.append(
                        f"ta.{func_name}(): arg {i+1} should be 'volume', got '{arg}'"
                    )

    return errors, warnings


def validate_all_entries() -> Tuple[list, list]:
    """
    Validate all Unger entries.

    Returns (broken_entries, warning_entries)
    """
    broken = []
    warned = []

    for entry in ALL_ENTRIES:
        errors, warnings = validate_entry(entry)
        if errors:
            broken.append((entry.id, entry.name, errors))
        if warnings:
            warned.append((entry.id, entry.name, warnings))

    return broken, warned


def main():
    """Run validation and print results."""
    print("=" * 70)
    print("UNGER ENTRIES VALIDATION")
    print("=" * 70)

    broken, warned = validate_all_entries()

    # Count entries with pandas_ta
    pandas_ta_entries = [e for e in ALL_ENTRIES if "pandas_ta" in e.logic_template]
    print(f"\nTotal entries: {len(ALL_ENTRIES)}")
    print(f"Entries using pandas_ta: {len(pandas_ta_entries)}")

    if broken:
        print(f"\n{'!' * 70}")
        print(f"ERRORS: {len(broken)} entries have invalid pandas_ta calls")
        print(f"{'!' * 70}")
        for entry_id, entry_name, errors in broken:
            print(f"\n  {entry_id}: {entry_name}")
            for err in errors:
                print(f"    ERROR: {err}")
    else:
        print(f"\n[OK] All pandas_ta calls have valid signatures")

    if warned:
        print(f"\n{'-' * 70}")
        print(f"WARNINGS: {len(warned)} entries have potential issues")
        print(f"{'-' * 70}")
        for entry_id, entry_name, warnings in warned[:10]:  # Show first 10
            print(f"\n  {entry_id}: {entry_name}")
            for warn in warnings:
                print(f"    WARN: {warn}")
        if len(warned) > 10:
            print(f"\n  ... and {len(warned) - 10} more warnings")

    print("\n" + "=" * 70)
    if broken:
        print(f"RESULT: FAILED - {len(broken)} entries need fixes")
        return 1
    else:
        print("RESULT: PASSED - All entries valid")
        return 0


if __name__ == "__main__":
    exit(main())
