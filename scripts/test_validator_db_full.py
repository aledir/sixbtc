#!/usr/bin/env python3
"""
Full Validation Test on Real Database Strategies

Tests complete 4-phase validation on strategies from the database,
including the shuffle test with real data loading.

Run: python scripts/test_validator_db_full.py
"""

import sys
import os
import traceback
import tempfile
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np


def main():
    print("\n" + "=" * 70)
    print("FULL VALIDATION TEST ON DATABASE STRATEGIES")
    print("=" * 70 + "\n")

    # Step 1: Load config and connect to database
    print("[1/5] Loading configuration and connecting to database...")
    try:
        from src.config import load_config
        from sqlalchemy import create_engine
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
        print("    Database connected")
    except Exception as e:
        print(f"    ERROR: {e}")
        traceback.print_exc()
        return 1

    # Step 2: Fetch strategies from database
    print("\n[2/5] Fetching strategies from database...")
    try:
        # Get GENERATED or VALIDATED strategies
        strategies = session.query(Strategy).filter(
            Strategy.status.in_(['GENERATED', 'VALIDATED'])
        ).limit(5).all()

        if not strategies:
            print("    No strategies found in database")
            return 1

        print(f"    Found {len(strategies)} strategies")
        for s in strategies:
            print(f"      - {s.name} ({s.status})")
    except Exception as e:
        print(f"    ERROR: {e}")
        traceback.print_exc()
        return 1

    # Step 3: Load test data
    print("\n[3/5] Loading test data...")
    try:
        from src.backtester.data_loader import BacktestDataLoader
        cache_dir = config.get('directories', {}).get('data', 'data/binance')
        loader = BacktestDataLoader(cache_dir=cache_dir)

        # Try to load real data
        try:
            test_data = loader.load_single_symbol('BTC', '15m', days=30)
            print(f"    Loaded {len(test_data)} bars of BTC 15m data")
        except Exception as e:
            print(f"    Failed to load real data: {e}")
            print("    Using synthetic data instead...")
            test_data = generate_synthetic_data(500)
            print(f"    Generated {len(test_data)} bars of synthetic data")
    except Exception as e:
        print(f"    ERROR: {e}")
        print("    Using synthetic data...")
        test_data = generate_synthetic_data(500)
        print(f"    Generated {len(test_data)} bars of synthetic data")

    # Step 4: Initialize validators
    print("\n[4/5] Initializing validators...")
    try:
        from src.validator.syntax_validator import SyntaxValidator
        from src.validator.lookahead_detector import LookaheadDetector
        from src.validator.execution_validator import ExecutionValidator
        from src.validator.lookahead_test import LookaheadTester

        syntax_validator = SyntaxValidator()
        lookahead_detector = LookaheadDetector()
        execution_validator = ExecutionValidator()
        lookahead_tester = LookaheadTester(sample_points=30)  # More points for real test

        print("    All validators initialized")
    except Exception as e:
        print(f"    ERROR: {e}")
        traceback.print_exc()
        return 1

    # Step 5: Validate each strategy through full pipeline
    print("\n[5/5] Running full validation pipeline...")
    print("-" * 70)

    results = []

    for strategy in strategies:
        print(f"\nValidating: {strategy.name}")
        result = {
            'name': strategy.name,
            'syntax': False,
            'lookahead_ast': False,
            'execution': False,
            'shuffle_test': False,
            'errors': []
        }

        code = strategy.code

        # Phase 1: Syntax
        print("  Phase 1: Syntax...", end=" ")
        try:
            syntax_result = syntax_validator.validate(code)
            if syntax_result.passed:
                print("PASS")
                result['syntax'] = True
                class_name = syntax_result.class_name
            else:
                print(f"FAIL - {syntax_result.errors[:1]}")
                result['errors'].append(f"Syntax: {syntax_result.errors[0]}")
                results.append(result)
                continue
        except Exception as e:
            print(f"ERROR - {e}")
            result['errors'].append(f"Syntax error: {e}")
            results.append(result)
            continue

        # Phase 2: Lookahead AST
        print("  Phase 2: Lookahead AST...", end=" ")
        try:
            ast_result = lookahead_detector.validate(code)
            if ast_result.passed:
                print("PASS")
                result['lookahead_ast'] = True
            else:
                print(f"FAIL - {ast_result.violations[:1]}")
                result['errors'].append(f"Lookahead AST: {ast_result.violations[0]}")
                results.append(result)
                continue
        except Exception as e:
            print(f"ERROR - {e}")
            result['errors'].append(f"AST error: {e}")
            results.append(result)
            continue

        # Phase 3: Execution
        print("  Phase 3: Execution...", end=" ")
        try:
            exec_result = execution_validator.validate(code, class_name, test_data)
            if exec_result.passed:
                print(f"PASS ({exec_result.signals_generated} signals)")
                result['execution'] = True
            else:
                print(f"FAIL - {exec_result.errors[:1]}")
                result['errors'].append(f"Execution: {exec_result.errors[0]}")
                results.append(result)
                continue
        except Exception as e:
            print(f"ERROR - {e}")
            result['errors'].append(f"Execution error: {e}")
            results.append(result)
            continue

        # Phase 4: Shuffle Test
        print("  Phase 4: Shuffle Test...", end=" ")
        try:
            strategy_instance = load_strategy_instance(code, class_name)
            if strategy_instance is None:
                print("ERROR - Failed to load instance")
                result['errors'].append("Failed to load strategy instance")
                results.append(result)
                continue

            shuffle_result = lookahead_tester.validate(strategy_instance, test_data)
            if shuffle_result.passed:
                print(f"PASS ({shuffle_result.total_bars_tested} bars tested)")
                result['shuffle_test'] = True
            else:
                print(f"FAIL - {shuffle_result.bias_rate:.1%} bias rate")
                result['errors'].append(f"Shuffle: {shuffle_result.details}")
        except Exception as e:
            print(f"ERROR - {e}")
            result['errors'].append(f"Shuffle error: {e}")

        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS SUMMARY")
    print("=" * 70)

    total = len(results)
    full_pass = sum(1 for r in results if all([
        r['syntax'], r['lookahead_ast'], r['execution'], r['shuffle_test']
    ]))
    syntax_pass = sum(1 for r in results if r['syntax'])
    ast_pass = sum(1 for r in results if r['lookahead_ast'])
    exec_pass = sum(1 for r in results if r['execution'])
    shuffle_pass = sum(1 for r in results if r['shuffle_test'])

    print(f"\nTotal strategies tested: {total}")
    print(f"  Phase 1 (Syntax):       {syntax_pass}/{total} passed")
    print(f"  Phase 2 (Lookahead AST): {ast_pass}/{total} passed")
    print(f"  Phase 3 (Execution):    {exec_pass}/{total} passed")
    print(f"  Phase 4 (Shuffle Test): {shuffle_pass}/{total} passed")
    print(f"\n  FULL PIPELINE PASS:     {full_pass}/{total}")

    if full_pass < total:
        print("\nFailed strategies:")
        for r in results:
            if r['errors']:
                print(f"  {r['name']}: {r['errors'][0]}")

    print("\n" + "=" * 70)
    if full_pass == total:
        print("ALL STRATEGIES PASSED FULL VALIDATION")
    else:
        print(f"{full_pass}/{total} STRATEGIES PASSED")
    print("=" * 70 + "\n")

    session.close()
    return 0 if full_pass == total else 1


def generate_synthetic_data(n_bars: int) -> pd.DataFrame:
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


def load_strategy_instance(code: str, class_name: str):
    """Load strategy instance from code string"""
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = Path(f.name)

        spec = importlib.util.spec_from_file_location(f"temp_{class_name}", temp_path)
        if spec and spec.loader:
            import sys
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                return cls()
    except Exception as e:
        print(f"    Load error: {e}")
    finally:
        if 'temp_path' in locals():
            temp_path.unlink(missing_ok=True)
    return None


if __name__ == "__main__":
    exit(main())
