#!/usr/bin/env python3
"""
Real Validator Test Suite

Tests ALL 4 phases of the validation pipeline with real code,
real data, and real execution. No mocks.

Run: python scripts/test_validator_real.py
"""

import sys
import os
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd


# =====================================================
# TEST STRATEGY SAMPLES
# =====================================================

# Valid strategy - should pass all phases
VALID_STRATEGY = '''
import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_test1234(StrategyCore):
    """Momentum strategy for testing"""

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        # Calculate RSI - only uses past data
        rsi = ta.RSI(df['close'].values, timeperiod=14)
        current_rsi = rsi[-1]

        # Calculate SMA - only uses past data
        sma = ta.SMA(df['close'].values, timeperiod=20)
        current_sma = sma[-1]
        current_price = df['close'].iloc[-1]

        # Entry conditions
        if current_rsi < 30 and current_price > current_sma:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason="RSI oversold + above SMA"
            )

        if current_rsi > 70 and current_price < current_sma:
            return Signal(
                direction='short',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason="RSI overbought + below SMA"
            )

        return None
'''

# Invalid syntax - should fail Phase 1
INVALID_SYNTAX = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_bad12345(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 10
            return None  # Missing colon!
        return None
'''

# Missing class - should fail Phase 1
MISSING_CLASS = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

def generate_signal(df):
    return None
'''

# Lookahead bias - rolling center=True - should fail Phase 2
LOOKAHEAD_ROLLING_CENTER = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_look1234(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        # LOOKAHEAD BIAS: center=True uses future data!
        rolling_high = df['high'].rolling(10, center=True).max()
        current_high = rolling_high.iloc[-1]

        if df['close'].iloc[-1] > current_high * 0.95:
            return Signal(direction='long', atr_stop_multiplier=2.0, atr_take_multiplier=3.0)
        return None
'''

# Lookahead bias - negative shift - should fail Phase 2
LOOKAHEAD_SHIFT_NEGATIVE = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_look5678(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        # LOOKAHEAD BIAS: shift(-1) accesses future data!
        future_close = df['close'].shift(-1)
        if df['close'].iloc[-1] < future_close.iloc[-1]:
            return Signal(direction='long', atr_stop_multiplier=2.0, atr_take_multiplier=3.0)
        return None
'''

# Uses global max - potential lookahead (shuffle test should catch it)
LOOKAHEAD_GLOBAL_MAX = '''
import pandas as pd
import talib as ta
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_gmax1234(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 50:
            return None

        # LOOKAHEAD BIAS: uses ALL data including future in max calculation
        # When fake future is appended with extreme values, this will change!
        all_time_high = df['high'].max()
        current_close = df['close'].iloc[-1]

        # This ratio depends on ALL data, including future
        ratio = current_close / all_time_high

        if ratio > 0.95:
            return Signal(direction='long', atr_stop_multiplier=2.0, atr_take_multiplier=3.0)
        return None
'''

# Execution error - runtime crash
EXECUTION_ERROR = '''
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_exec1234(StrategyCore):
    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        # Will crash: divide by zero
        value = 1 / 0
        return None
'''


def generate_test_data(n_bars: int = 500) -> pd.DataFrame:
    """Generate synthetic OHLCV test data"""
    np.random.seed(42)

    returns = np.random.randn(n_bars) * 0.02
    close = 50000 * np.cumprod(1 + returns)

    high = close * (1 + np.abs(np.random.randn(n_bars) * 0.01))
    low = close * (1 - np.abs(np.random.randn(n_bars) * 0.01))
    open_price = close * (1 + np.random.randn(n_bars) * 0.005)

    high = np.maximum(high, close)
    low = np.minimum(low, close)
    high = np.maximum(high, open_price)
    low = np.minimum(low, open_price)

    volume = np.random.uniform(100, 1000, n_bars)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })


def test_phase1_syntax_validator():
    """Test Phase 1: SyntaxValidator"""
    print("\n" + "=" * 70)
    print("PHASE 1: SyntaxValidator")
    print("=" * 70)

    from src.validator.syntax_validator import SyntaxValidator
    validator = SyntaxValidator()

    tests = [
        ("Valid Strategy", VALID_STRATEGY, True),
        ("Invalid Syntax (missing colon)", INVALID_SYNTAX, False),
        ("Missing StrategyCore class", MISSING_CLASS, False),
    ]

    passed = 0
    failed = 0

    for name, code, expected_pass in tests:
        try:
            result = validator.validate(code)
            actual_pass = result.passed

            if actual_pass == expected_pass:
                status = "OK"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"\n  [{status}] {name}")
            print(f"      Expected: {'PASS' if expected_pass else 'FAIL'}")
            print(f"      Actual:   {'PASS' if actual_pass else 'FAIL'}")
            if not result.passed:
                print(f"      Errors:   {result.errors[:2]}")
            if result.class_name:
                print(f"      Class:    {result.class_name}")

        except Exception as e:
            print(f"\n  [ERROR] {name}: {e}")
            failed += 1
            traceback.print_exc()

    print(f"\n  Summary: {passed}/{passed+failed} tests passed")
    return failed == 0


def test_phase2_lookahead_detector():
    """Test Phase 2: LookaheadDetector (AST analysis)"""
    print("\n" + "=" * 70)
    print("PHASE 2: LookaheadDetector (AST Analysis)")
    print("=" * 70)

    from src.validator.lookahead_detector import LookaheadDetector
    detector = LookaheadDetector()

    tests = [
        ("Valid Strategy (no lookahead)", VALID_STRATEGY, True),
        ("Lookahead: rolling(center=True)", LOOKAHEAD_ROLLING_CENTER, False),
        ("Lookahead: shift(-1)", LOOKAHEAD_SHIFT_NEGATIVE, False),
        # Global max is not detected by AST (needs shuffle test)
        ("Global max (AST can't detect)", LOOKAHEAD_GLOBAL_MAX, True),
    ]

    passed = 0
    failed = 0

    for name, code, expected_pass in tests:
        try:
            result = detector.validate(code)
            actual_pass = result.passed

            if actual_pass == expected_pass:
                status = "OK"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"\n  [{status}] {name}")
            print(f"      Expected: {'PASS' if expected_pass else 'FAIL'}")
            print(f"      Actual:   {'PASS' if actual_pass else 'FAIL'}")
            if not result.passed:
                print(f"      Violations: {result.violations}")
            print(f"      Patterns checked: {result.patterns_checked}")

        except Exception as e:
            print(f"\n  [ERROR] {name}: {e}")
            failed += 1
            traceback.print_exc()

    print(f"\n  Summary: {passed}/{passed+failed} tests passed")
    return failed == 0


def test_phase3_execution_validator():
    """Test Phase 3: ExecutionValidator"""
    print("\n" + "=" * 70)
    print("PHASE 3: ExecutionValidator")
    print("=" * 70)

    from src.validator.execution_validator import ExecutionValidator
    validator = ExecutionValidator()

    test_data = generate_test_data(500)

    tests = [
        ("Valid Strategy", VALID_STRATEGY, "Strategy_MOM_test1234", True),
        ("Runtime Error (div by zero)", EXECUTION_ERROR, "Strategy_MOM_exec1234", False),
    ]

    passed = 0
    failed = 0

    for name, code, class_name, expected_pass in tests:
        try:
            result = validator.validate(code, class_name, test_data)
            actual_pass = result.passed

            if actual_pass == expected_pass:
                status = "OK"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"\n  [{status}] {name}")
            print(f"      Expected: {'PASS' if expected_pass else 'FAIL'}")
            print(f"      Actual:   {'PASS' if actual_pass else 'FAIL'}")
            print(f"      Signals:  {result.signals_generated}")
            print(f"      Time:     {result.execution_time_ms:.1f}ms")
            if not result.passed:
                print(f"      Errors:   {result.errors[:2]}")
            if result.warnings:
                print(f"      Warnings: {result.warnings[:2]}")

        except Exception as e:
            print(f"\n  [ERROR] {name}: {e}")
            failed += 1
            traceback.print_exc()

    print(f"\n  Summary: {passed}/{passed+failed} tests passed")
    return failed == 0


def test_phase4_lookahead_tester():
    """Test Phase 4: LookaheadTester (shuffle test with extreme future)"""
    print("\n" + "=" * 70)
    print("PHASE 4: LookaheadTester (Freqtrade-style Shuffle Test)")
    print("=" * 70)

    from src.validator.lookahead_test import LookaheadTester
    import importlib.util
    import tempfile

    tester = LookaheadTester(sample_points=20)  # Fewer points for speed
    test_data = generate_test_data(500)

    def load_strategy_instance(code: str, class_name: str):
        """Load strategy instance from code"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            spec = importlib.util.spec_from_file_location(f"test_{class_name}", temp_path)
            if spec and spec.loader:
                import sys
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                if hasattr(module, class_name):
                    return getattr(module, class_name)()
        finally:
            Path(temp_path).unlink(missing_ok=True)
        return None

    tests = [
        ("Valid Strategy (no lookahead)", VALID_STRATEGY, "Strategy_MOM_test1234", True),
        ("Global max (shuffle should detect)", LOOKAHEAD_GLOBAL_MAX, "Strategy_MOM_gmax1234", False),
    ]

    passed = 0
    failed = 0

    for name, code, class_name, expected_pass in tests:
        try:
            strategy = load_strategy_instance(code, class_name)
            if strategy is None:
                print(f"\n  [ERROR] {name}: Failed to load strategy instance")
                failed += 1
                continue

            result = tester.validate(strategy, test_data)
            actual_pass = result.passed

            if actual_pass == expected_pass:
                status = "OK"
                passed += 1
            else:
                status = "FAIL"
                failed += 1

            print(f"\n  [{status}] {name}")
            print(f"      Expected: {'PASS' if expected_pass else 'FAIL'}")
            print(f"      Actual:   {'PASS' if actual_pass else 'FAIL'}")
            print(f"      Bars tested: {result.total_bars_tested}")
            print(f"      Bias rate:   {result.bias_rate:.1%}")
            if result.biased_bars:
                print(f"      Biased bars: {result.biased_bars[:5]}")

        except Exception as e:
            print(f"\n  [ERROR] {name}: {e}")
            failed += 1
            traceback.print_exc()

    print(f"\n  Summary: {passed}/{passed+failed} tests passed")
    return failed == 0


def test_full_pipeline():
    """Test full 4-phase validation pipeline"""
    print("\n" + "=" * 70)
    print("FULL PIPELINE TEST: All 4 Phases Sequential")
    print("=" * 70)

    from src.validator.syntax_validator import SyntaxValidator
    from src.validator.lookahead_detector import LookaheadDetector
    from src.validator.execution_validator import ExecutionValidator
    from src.validator.lookahead_test import LookaheadTester
    import importlib.util
    import tempfile

    syntax_validator = SyntaxValidator()
    lookahead_detector = LookaheadDetector()
    execution_validator = ExecutionValidator()
    lookahead_tester = LookaheadTester(sample_points=20)

    test_data = generate_test_data(500)

    def load_strategy_instance(code: str, class_name: str):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            spec = importlib.util.spec_from_file_location(f"test_{class_name}", temp_path)
            if spec and spec.loader:
                import sys
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                if hasattr(module, class_name):
                    return getattr(module, class_name)()
        finally:
            Path(temp_path).unlink(missing_ok=True)
        return None

    print("\n  Testing VALID strategy through all 4 phases...")

    code = VALID_STRATEGY
    print("\n  Phase 1: Syntax...")
    result1 = syntax_validator.validate(code)
    print(f"    Result: {'PASS' if result1.passed else 'FAIL'}")
    if not result1.passed:
        print(f"    Errors: {result1.errors}")
        return False

    print("\n  Phase 2: Lookahead AST...")
    result2 = lookahead_detector.validate(code)
    print(f"    Result: {'PASS' if result2.passed else 'FAIL'}")
    if not result2.passed:
        print(f"    Violations: {result2.violations}")
        return False

    print("\n  Phase 3: Execution...")
    result3 = execution_validator.validate(code, result1.class_name, test_data)
    print(f"    Result: {'PASS' if result3.passed else 'FAIL'}")
    print(f"    Signals: {result3.signals_generated}")
    if not result3.passed:
        print(f"    Errors: {result3.errors}")
        return False

    print("\n  Phase 4: Lookahead Shuffle Test...")
    strategy = load_strategy_instance(code, result1.class_name)
    if strategy is None:
        print("    ERROR: Failed to load strategy")
        return False

    result4 = lookahead_tester.validate(strategy, test_data)
    print(f"    Result: {'PASS' if result4.passed else 'FAIL'}")
    print(f"    Bars tested: {result4.total_bars_tested}")
    if not result4.passed:
        print(f"    Biased bars: {result4.biased_bars}")
        return False

    print("\n  All 4 phases PASSED!")
    return True


def test_database_strategies():
    """Test validation on real strategies from database"""
    print("\n" + "=" * 70)
    print("DATABASE TEST: Validate Real Strategies from DB")
    print("=" * 70)

    try:
        from src.config import load_config
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from src.database.models import Strategy

        config = load_config()._raw_config
        db_url = (
            f"postgresql://{config['database']['user']}:{config['database']['password']}"
            f"@{config['database']['host']}:{config['database']['port']}"
            f"/{config['database']['database']}"
        )
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Get some strategies from DB
        strategies = session.query(Strategy).filter(
            Strategy.status == 'GENERATED'
        ).limit(3).all()

        if not strategies:
            print("  No GENERATED strategies found in database")
            # Try VALIDATED
            strategies = session.query(Strategy).filter(
                Strategy.status == 'VALIDATED'
            ).limit(3).all()

        if not strategies:
            print("  No strategies found in database to test")
            return True  # Not a failure, just no data

        print(f"  Found {len(strategies)} strategies to test")

        from src.validator.syntax_validator import SyntaxValidator
        from src.validator.lookahead_detector import LookaheadDetector

        syntax_validator = SyntaxValidator()
        lookahead_detector = LookaheadDetector()

        for s in strategies:
            print(f"\n  Testing: {s.name}")

            result1 = syntax_validator.validate(s.code)
            print(f"    Syntax: {'PASS' if result1.passed else 'FAIL'}")
            if not result1.passed:
                print(f"    Errors: {result1.errors[:2]}")

            result2 = lookahead_detector.validate(s.code)
            print(f"    Lookahead AST: {'PASS' if result2.passed else 'FAIL'}")
            if not result2.passed:
                print(f"    Violations: {result2.violations}")

        session.close()
        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all validator tests"""
    print("\n" + "=" * 70)
    print("SIXBTC VALIDATOR - REAL TEST SUITE")
    print("=" * 70)

    results = {}

    # Phase 1
    results['Phase 1: Syntax'] = test_phase1_syntax_validator()

    # Phase 2
    results['Phase 2: Lookahead AST'] = test_phase2_lookahead_detector()

    # Phase 3
    results['Phase 3: Execution'] = test_phase3_execution_validator()

    # Phase 4
    results['Phase 4: Shuffle Test'] = test_phase4_lookahead_tester()

    # Full Pipeline
    results['Full Pipeline'] = test_full_pipeline()

    # Database test
    results['Database Strategies'] = test_database_strategies()

    # Summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED - Check output above")
    print("=" * 70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
