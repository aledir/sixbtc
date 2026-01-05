#!/usr/bin/env python3
"""Quick test for unified scroll-down logic"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.backtester.main_continuous import ContinuousBacktesterProcess
from src.config import load_config

def test_unified_scroll_down():
    """Test that both Pattern and AI use same scroll-down logic"""

    print("=" * 80)
    print("TESTING UNIFIED SCROLL-DOWN LOGIC")
    print("=" * 80)

    # Initialize backtester
    config = load_config()
    backtester = ContinuousBacktesterProcess(config)

    # Test 1: _scroll_down_coverage method exists and is callable
    print("\n[TEST 1] Check unified method exists...")
    assert hasattr(backtester, '_scroll_down_coverage'), "Method _scroll_down_coverage not found"
    print("✅ Method _scroll_down_coverage exists")

    # Test 2: AI pairs method returns tuple (pairs, status)
    print("\n[TEST 2] Check AI pairs method signature...")
    try:
        # Should accept timeframe parameter now
        pairs, status = backtester._get_backtest_pairs('4h')
        print(f"✅ AI pairs returned: {len(pairs) if pairs else 0} pairs, status: {status}")
    except Exception as e:
        print(f"❌ AI pairs failed: {e}")
        raise

    # Test 3: Pattern validation returns tuple (coins, status)
    print("\n[TEST 3] Check Pattern validation method signature...")
    try:
        # Test with empty list (should reject gracefully)
        validated, status = backtester._validate_pattern_coins([], '4h')
        assert validated is None, "Empty pattern coins should return None"
        assert status == "no_pattern_coins", f"Expected 'no_pattern_coins', got '{status}'"
        print(f"✅ Pattern validation returned: None, status: {status}")
    except Exception as e:
        print(f"❌ Pattern validation failed: {e}")
        raise

    # Test 4: Both methods call _scroll_down_coverage (check via code inspection)
    print("\n[TEST 4] Verify unified logic is used...")
    import inspect

    # Check AI method calls scroll_down_coverage
    ai_source = inspect.getsource(backtester._get_backtest_pairs)
    assert '_scroll_down_coverage' in ai_source, "AI method doesn't use unified logic"
    print("✅ AI method uses _scroll_down_coverage")

    # Check Pattern method calls scroll_down_coverage
    pattern_source = inspect.getsource(backtester._validate_pattern_coins)
    assert '_scroll_down_coverage' in pattern_source, "Pattern method doesn't use unified logic"
    print("✅ Pattern method uses _scroll_down_coverage")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✅")
    print("=" * 80)
    print("\nSummary:")
    print("- Unified scroll-down method exists")
    print("- AI pairs method uses unified logic")
    print("- Pattern validation uses unified logic")
    print("- Both return consistent (coins/pairs, status) tuple")

if __name__ == '__main__':
    test_unified_scroll_down()
