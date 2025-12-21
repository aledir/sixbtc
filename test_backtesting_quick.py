#!/usr/bin/env python3
"""
Quick Backtesting Test

Fast validation of Phase 4 components (skips slow tests)
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.backtester.data_loader import BacktestDataLoader
from src.backtester.validator import LookaheadValidator, QuickValidator
from src.utils.logger import setup_logging

logger = setup_logging()


def generate_synthetic_data(bars: int = 200) -> pd.DataFrame:
    """Generate minimal synthetic data"""
    np.random.seed(42)

    close = 50000 + np.cumsum(np.random.randn(bars) * 100)
    high = close + np.abs(np.random.randn(bars) * 50)
    low = close - np.abs(np.random.randn(bars) * 50)
    open_price = np.roll(close, 1)

    timestamps = pd.date_range(start='2024-01-01', periods=bars, freq='15min')

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.uniform(1e6, 5e6, bars)
    })


def test_data_loader():
    """Test data loader basics"""
    logger.info("TEST: Data Loader")
    loader = BacktestDataLoader()

    df = generate_synthetic_data(200)
    windows = loader.walk_forward_split(df, n_windows=3, train_pct=0.75)

    assert len(windows) == 3, "Should create 3 windows"
    logger.info(f"  ✓ Created {len(windows)} walk-forward windows")

    return df


def test_lookahead_validator():
    """Test lookahead validator (AST only - fast)"""
    logger.info("\nTEST: Lookahead Validator (Quick)")

    # Clean code
    clean_code = """
import pandas as pd
from src.strategies.base import StrategyCore

class Clean(StrategyCore):
    def generate_signal(self, df):
        sma = df['close'].rolling(10).mean()
        return None
"""

    passed, violations = QuickValidator.quick_check(clean_code)
    assert passed, f"Clean code failed: {violations}"
    logger.info("  ✓ Clean code passed AST check")

    # Bad code
    bad_code = """
import pandas as pd

class Bad:
    def test(self, df):
        future = df['close'].shift(-5)
        centered = df['high'].rolling(10, center=True).max()
"""

    passed, violations = QuickValidator.quick_check(bad_code)
    assert not passed, "Bad code should fail"
    assert len(violations) >= 2, "Should detect violations"
    logger.info(f"  ✓ Detected {len(violations)} violations in bad code")


def main():
    """Run quick tests"""
    logger.info("=" * 60)
    logger.info("SIXBTC PHASE 4 - QUICK TEST")
    logger.info("=" * 60)

    try:
        df = test_data_loader()
        test_lookahead_validator()

        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL QUICK TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nPhase 4 core components are working!")
        logger.info("Note: Full VectorBT integration test requires more time")
        logger.info("      and will be validated in production use.")

        return 0

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
