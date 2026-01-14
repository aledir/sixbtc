#!/usr/bin/env python3
"""
Validates pandas_ta catalog entries against actual function signatures.

Finds mismatches BEFORE they cause runtime errors:
- Template-unsupported input_types
- Missing positional arguments
- Positional overflow conflicts (extra args filling keyword param slots)

Usage:
    python -m src.generator.pandas_ta.validate_catalog

Exit codes:
    0 = All indicators valid
    N = Number of broken indicators found
"""
import inspect
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas_ta as ta

from src.generator.pandas_ta.catalogs.indicators import ALL_INDICATORS


# Input types that the template (pandas_ta.j2) actually supports
# If an indicator uses an input_type not in this set, it falls back to 'close'
TEMPLATE_SUPPORTED_INPUT_TYPES = {
    None,
    "close",
    "hl",
    "hlc",
    "hlcv",
    "ohlcv",
    "cv",
    "ohlc",
    "oc",
    "volume",
}

# Map input_type to the positional arguments that will be passed
INPUT_TYPE_TO_ARGS = {
    None: ["close"],
    "close": ["close"],
    "hl": ["high", "low"],
    "hlc": ["high", "low", "close"],
    "ohlc": ["open", "high", "low", "close"],
    "ohlcv": ["open", "high", "low", "close", "volume"],
    "hlcv": ["high", "low", "close", "volume"],
    "cv": ["close", "volume"],
    "oc": ["open_", "close"],
    "volume": ["volume"],
}


def get_positional_params(sig: inspect.Signature) -> list[tuple[str, bool]]:
    """
    Extract positional parameters from signature.

    Returns list of (param_name, has_default) tuples.
    """
    params = []
    for name, param in sig.parameters.items():
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            if name not in ("kwargs", "args"):
                has_default = param.default != inspect.Parameter.empty
                params.append((name, has_default))
    return params


def normalize_arg_name(name: str) -> str:
    """Normalize argument names (e.g., 'open_' -> 'open')."""
    return name.rstrip("_")


def infer_correct_input_type(required_args: list[str]) -> str:
    """Infer the correct input_type based on required arguments."""
    req_set = set(normalize_arg_name(a) for a in required_args)

    type_map = {
        frozenset({"close"}): "close",
        frozenset({"high", "low"}): "hl",
        frozenset({"high", "low", "close"}): "hlc",
        frozenset({"open", "high", "low", "close"}): "ohlc",
        frozenset({"open", "high", "low", "close", "volume"}): "ohlcv",
        frozenset({"high", "low", "close", "volume"}): "hlcv",
        frozenset({"close", "volume"}): "cv",
        frozenset({"open", "close"}): "oc",
        frozenset({"volume"}): "volume",
        frozenset({"fast", "slow"}): "dual_series",
    }

    return type_map.get(frozenset(req_set), f"unknown:{req_set}")


def validate_indicator(ind) -> tuple[list[str], str | None]:
    """
    Validate a single indicator against pandas_ta.

    Returns (list of errors, suggested fix or None).
    """
    errors = []
    func_name = ind.pandas_ta_func

    # Check if function exists in pandas_ta
    if not hasattr(ta, func_name):
        return [f"Function ta.{func_name} does not exist in pandas_ta"], None

    func = getattr(ta, func_name)
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return [f"Cannot get signature for ta.{func_name}"], None

    # Get all positional params and required-only params
    positional_params = get_positional_params(sig)
    required_args = [name for name, has_default in positional_params if not has_default]

    # What the catalog declares
    input_type = getattr(ind, "input_type", None)
    catalog_args = INPUT_TYPE_TO_ARGS.get(input_type, INPUT_TYPE_TO_ARGS[None])

    # Check 1: Template support
    if input_type not in TEMPLATE_SUPPORTED_INPUT_TYPES:
        errors.append(
            f"TEMPLATE: input_type='{input_type}' not supported by template "
            f"(will fall back to 'close')"
        )

    # Normalize for comparison
    req_normalized = [normalize_arg_name(a) for a in required_args]
    cat_normalized = [normalize_arg_name(a) for a in catalog_args]

    # Check 2: Missing arguments
    if len(cat_normalized) < len(req_normalized):
        errors.append(
            f"MISSING: input_type='{input_type}' provides {catalog_args} "
            f"but function requires {required_args}"
        )

    # Check 3: Extra arguments causing conflicts
    elif len(cat_normalized) > len(req_normalized):
        for i, extra_arg in enumerate(cat_normalized[len(req_normalized) :]):
            param_idx = len(req_normalized) + i
            if param_idx < len(positional_params):
                conflicting_param, _ = positional_params[param_idx]
                # Check if this param is also passed via ind.params (keyword)
                if ind.params and conflicting_param in ind.params:
                    errors.append(
                        f"CONFLICT: extra '{extra_arg}' fills position of "
                        f"'{conflicting_param}' which is also in params "
                        f"-> 'multiple values' error"
                    )
                else:
                    errors.append(
                        f"OVERFLOW: extra '{extra_arg}' fills "
                        f"'{conflicting_param}' param position"
                    )

    # Suggest fix if there are errors
    suggestion = None
    if errors:
        correct_type = infer_correct_input_type(required_args)
        if correct_type != input_type:
            suggestion = correct_type

    return errors, suggestion


def main() -> int:
    """Run validation and print results."""
    print("=" * 80)
    print("PANDAS_TA CATALOG VALIDATION")
    print("=" * 80)

    broken = []

    for ind in ALL_INDICATORS:
        errors, suggestion = validate_indicator(ind)
        if errors:
            broken.append(
                (
                    ind.id,
                    ind.pandas_ta_func,
                    getattr(ind, "input_type", None),
                    errors,
                    suggestion,
                )
            )

    if broken:
        print(f"\nBROKEN INDICATORS ({len(broken)}):\n")
        for ind_id, func_name, input_type, errors, suggestion in sorted(broken):
            print(f"  {ind_id} (ta.{func_name}, input_type='{input_type}'):")
            for err in errors:
                print(f"    - {err}")
            if suggestion and suggestion != input_type:
                print(f"    FIX: Change to input_type='{suggestion}'")
            print()
    else:
        print("\nAll indicators validated successfully!")

    print("=" * 80)
    print(f"Total indicators: {len(ALL_INDICATORS)}")
    print(f"Broken: {len(broken)}")
    print("=" * 80)

    return len(broken)


if __name__ == "__main__":
    sys.exit(main())
