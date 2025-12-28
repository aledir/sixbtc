#!/usr/bin/env python3
"""
Test Pattern-Discovery Integration

Tests the new pattern API integration with formula_source and helpers.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.loader import load_config
from src.generator.pattern_fetcher import PatternFetcher
from src.generator.helper_fetcher import HelperFetcher
from src.generator.direct_generator import DirectPatternGenerator


def test_helper_fetcher():
    """Test fetching helpers from API"""
    print("\n=== Testing HelperFetcher ===")

    config = load_config()
    api_url = config.get('pattern_discovery.api_url')
    print(f"API URL: {api_url}")

    fetcher = HelperFetcher(api_url)

    # Test availability
    if not fetcher.is_available():
        print("WARNING: Helper API not available, using fallback")

    # Fetch helpers for 15m timeframe
    context = fetcher.get_helpers("15m")

    if context:
        print(f"\nBase timeframe: {context.base_timeframe}")
        print(f"Timeframe bars ({len(context.timeframe_bars)} mappings):")
        for period, bars in sorted(context.timeframe_bars.items()):
            print(f"  bars_{period}() = {bars}")

        print(f"\nHelper functions ({len(context.helper_functions)} functions):")
        for name in context.helper_functions.keys():
            print(f"  {name}")

        # Test code generation
        print("\n--- Generated bars_*() code ---")
        print(fetcher.generate_bars_functions_code("15m"))

        return True
    else:
        print("ERROR: Failed to fetch helpers")
        return False


def test_pattern_fetcher():
    """Test fetching patterns with new fields"""
    print("\n=== Testing PatternFetcher (new fields) ===")

    config = load_config()
    api_url = config.get('pattern_discovery.api_url')

    fetcher = PatternFetcher(api_url=api_url)

    if not fetcher.is_available():
        print("ERROR: Pattern API not available")
        return False

    # Fetch patterns
    patterns = fetcher.get_tier_1_patterns(limit=3)
    print(f"\nFetched {len(patterns)} patterns")

    for i, p in enumerate(patterns):
        print(f"\n--- Pattern {i+1}: {p.name} ---")
        print(f"  Direction: {p.target_direction}")
        print(f"  Edge: {p.test_edge*100:.2f}%")
        print(f"  Win Rate: {p.test_win_rate*100:.1f}%")
        print(f"  Strategy Type: {p.strategy_type}")
        print(f"  Timeframe: {p.timeframe}")

        # New fields
        print(f"  formula_readable: {p.formula_readable}")
        print(f"  formula_source: {'YES' if p.formula_source else 'NO'}")
        if p.formula_source:
            # Show first 100 chars
            preview = p.formula_source[:100].replace('\n', ' ')
            print(f"    Preview: {preview}...")
        print(f"  formula_components: {'YES' if p.formula_components else 'NO'}")

    return len(patterns) > 0


def test_direct_generator():
    """Test direct generation (Mode A)"""
    print("\n=== Testing DirectPatternGenerator (Mode A) ===")

    config = load_config()._raw_config

    # Fetch a pattern with formula_source
    api_url = config['pattern_discovery']['api_url']
    fetcher = PatternFetcher(api_url=api_url)

    patterns = fetcher.get_tier_1_patterns(limit=5)
    pattern_with_source = None

    for p in patterns:
        if p.formula_source:
            pattern_with_source = p
            break

    if not pattern_with_source:
        print("WARNING: No patterns with formula_source found")
        print("Direct generation requires patterns with executable source code")
        return False

    print(f"\nUsing pattern: {pattern_with_source.name}")
    print(f"  Direction: {pattern_with_source.target_direction}")
    print(f"  formula_source available: YES")

    # Test direct generation
    generator = DirectPatternGenerator(config)
    result = generator.generate(pattern_with_source, leverage=5)

    if result:
        print(f"\n--- Generated Strategy ---")
        print(f"  ID: {result.strategy_id}")
        print(f"  Type: {result.strategy_type}")
        print(f"  Mode: {result.generation_mode}")
        print(f"  Validation: {'PASSED' if result.validation_passed else 'FAILED'}")

        if result.validation_errors:
            print(f"  Errors: {result.validation_errors}")

        # Show code preview
        print(f"\n--- Code Preview (first 500 chars) ---")
        print(result.code[:500])
        print("...")

        # Verify key elements
        checks = {
            "has_bars_functions": "def bars_" in result.code,
            "has_pattern_function": pattern_with_source.name in result.code,
            "has_strategy_class": "class Strategy_" in result.code,
            "has_generate_signal": "def generate_signal" in result.code,
            "has_signal_return": "return Signal(" in result.code,
        }

        print(f"\n--- Verification Checks ---")
        all_passed = True
        for check, passed in checks.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {check}: {status}")
            if not passed:
                all_passed = False

        return result.validation_passed and all_passed
    else:
        print("ERROR: Direct generation returned None")
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("PATTERN-DISCOVERY INTEGRATION TEST")
    print("=" * 60)

    results = {}

    # Test 1: Helper Fetcher
    try:
        results['helper_fetcher'] = test_helper_fetcher()
    except Exception as e:
        print(f"ERROR in test_helper_fetcher: {e}")
        results['helper_fetcher'] = False

    # Test 2: Pattern Fetcher (new fields)
    try:
        results['pattern_fetcher'] = test_pattern_fetcher()
    except Exception as e:
        print(f"ERROR in test_pattern_fetcher: {e}")
        results['pattern_fetcher'] = False

    # Test 3: Direct Generator
    try:
        results['direct_generator'] = test_direct_generator()
    except Exception as e:
        print(f"ERROR in test_direct_generator: {e}")
        import traceback
        traceback.print_exc()
        results['direct_generator'] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("ALL TESTS PASSED")
        return 0
    else:
        print("SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
