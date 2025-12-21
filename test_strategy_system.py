"""
Test Strategy System

Tests the complete strategy generation and validation pipeline.
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.base import StrategyCore, Signal
from src.strategies.examples import (
    Strategy_MOM_Example,
    Strategy_REV_Example,
    Strategy_TRN_Example
)


def generate_test_data(bars: int = 200) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing"""
    np.random.seed(42)

    # Generate price data with trend + noise
    base_price = 50000
    trend = np.linspace(0, 2000, bars)
    noise = np.random.randn(bars) * 500

    close = base_price + trend + noise

    # Generate OHLC
    high = close + np.abs(np.random.randn(bars) * 200)
    low = close - np.abs(np.random.randn(bars) * 200)
    open_price = close + np.random.randn(bars) * 100

    # Generate volume
    volume = np.random.uniform(1000000, 5000000, bars)

    df = pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })

    return df


def test_example_strategies():
    """Test hand-crafted example strategies"""
    print("\n" + "="*60)
    print("TESTING EXAMPLE STRATEGIES")
    print("="*60)

    df = generate_test_data(200)

    strategies = [
        Strategy_MOM_Example(),
        Strategy_REV_Example(),
        Strategy_TRN_Example()
    ]

    for strategy in strategies:
        print(f"\n{strategy.__class__.__name__}:")
        print(f"  Description: {strategy.__class__.__doc__.strip().split(chr(10))[0]}")

        # Test signal generation
        try:
            signal = strategy.generate_signal(df)

            if signal:
                print(f"  Signal: {signal.direction}")
                print(f"  ATR Stop: {signal.atr_stop_multiplier}x")
                print(f"  ATR TP: {signal.atr_take_multiplier}x")
                print(f"  Reason: {signal.reason}")
            else:
                print(f"  Signal: None (no entry conditions met)")

            print(f"  Status: PASS")

        except Exception as e:
            print(f"  Status: FAIL - {e}")

    print("\n" + "="*60)


def test_strategy_validation():
    """Test strategy validation logic"""
    print("\n" + "="*60)
    print("TESTING STRATEGY VALIDATION")
    print("="*60)

    from src.generator.strategy_builder import StrategyBuilder

    builder = StrategyBuilder(init_ai=False)  # Validation only

    # Test 1: Valid code
    valid_code = '''
import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal

class Strategy_TEST_valid(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 50:
            return None
        rsi = ta.RSI(df['close'], timeperiod=14)
        if rsi.iloc[-1] < 30:
            return Signal(direction='long', reason="RSI oversold")
        return None
'''

    print("\nTest 1: Valid code")
    passed, errors = builder._validate_code(valid_code)
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    if errors:
        print(f"  Errors: {errors}")

    # Test 2: Invalid code - lookahead bias (center=True)
    invalid_code_lookahead = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_TEST_lookahead(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        sma = df['close'].rolling(10, center=True).mean()  # LOOKAHEAD!
        return None
'''

    print("\nTest 2: Invalid code - lookahead bias (center=True)")
    passed, errors = builder._validate_code(invalid_code_lookahead)
    print(f"  Result: {'FAIL (expected)' if not passed else 'UNEXPECTED PASS'}")
    print(f"  Errors: {errors}")

    # Test 3: Invalid code - negative shift
    invalid_code_shift = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_TEST_shift(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        future_price = df['close'].shift(-1)  # LOOKAHEAD!
        return None
'''

    print("\nTest 3: Invalid code - negative shift")
    passed, errors = builder._validate_code(invalid_code_shift)
    print(f"  Result: {'FAIL (expected)' if not passed else 'UNEXPECTED PASS'}")
    print(f"  Errors: {errors}")

    # Test 4: Missing StrategyCore inheritance
    invalid_code_no_inherit = '''
import pandas as pd
from src.strategies.base import Signal

class Strategy_TEST_no_inherit:  # Missing StrategyCore!
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        return None
'''

    print("\nTest 4: Missing StrategyCore inheritance")
    passed, errors = builder._validate_code(invalid_code_no_inherit)
    print(f"  Result: {'FAIL (expected)' if not passed else 'UNEXPECTED PASS'}")
    print(f"  Errors: {errors}")

    print("\n" + "="*60)


def test_pattern_fetcher():
    """Test pattern-discovery API connection"""
    print("\n" + "="*60)
    print("TESTING PATTERN FETCHER")
    print("="*60)

    from src.generator.pattern_fetcher import PatternFetcher

    fetcher = PatternFetcher()

    print("\nAttempting to fetch patterns...")
    print("(This will fail if pattern-discovery API is not running)")

    try:
        patterns = fetcher.get_tier_1_patterns(timeframe='15m', limit=5)

        if patterns:
            print(f"\nFetched {len(patterns)} patterns:")
            for i, p in enumerate(patterns, 1):
                print(f"\n  Pattern {i}:")
                print(f"    Name: {p.name}")
                print(f"    Formula: {p.formula[:60]}...")
                print(f"    Edge: {p.test_edge:.2f}%")
                print(f"    Win Rate: {p.test_win_rate*100:.1f}%")
                print(f"    Quality: {p.quality_score:.2f}")
        else:
            print("\n  No patterns returned (API may be offline)")

    except Exception as e:
        print(f"\n  Failed to connect: {e}")
        print("  This is expected if pattern-discovery is not running")

    print("\n" + "="*60)


def test_ai_manager():
    """Test AI Manager initialization"""
    print("\n" + "="*60)
    print("TESTING AI MANAGER")
    print("="*60)

    from src.generator.ai_manager import AIManager

    print("\nInitializing AI Manager...")
    print("(This requires at least one API key in environment)")

    try:
        manager = AIManager()
        print(f"\nAvailable providers: {manager.available_providers}")

        if manager.available_providers:
            print("  Status: READY")
            print("\nNote: Actual generation not tested to avoid API costs")
            print("      Use manual test if needed: python -m src.generator.test_generate")
        else:
            print("  Status: NO PROVIDERS")
            print("  Set at least one API key:")
            print("    - ANTHROPIC_API_KEY for Claude")
            print("    - GOOGLE_API_KEY for Gemini")
            print("    - OPENAI_API_KEY for OpenAI")

    except Exception as e:
        print(f"  Failed: {e}")

    print("\n" + "="*60)


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print(" "*20 + "SIXBTC STRATEGY SYSTEM TEST")
    print("="*80)

    # Test 1: Example strategies
    test_example_strategies()

    # Test 2: Validation logic
    test_strategy_validation()

    # Test 3: Pattern fetcher
    test_pattern_fetcher()

    # Test 4: AI Manager
    test_ai_manager()

    print("\n" + "="*80)
    print(" "*25 + "ALL TESTS COMPLETE")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
