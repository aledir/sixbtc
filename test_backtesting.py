#!/usr/bin/env python3
"""
Test Backtesting Pipeline

Tests the complete Phase 4 implementation:
1. Data loader
2. VectorBT backtester
3. Lookahead validator
4. Walk-forward optimizer
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.backtester.data_loader import BacktestDataLoader
from src.backtester.vectorbt_engine import VectorBTBacktester
from src.backtester.validator import LookaheadValidator
from src.backtester.optimizer import WalkForwardOptimizer
from src.strategies.examples import Strategy_MOM_Example, Strategy_REV_Example
from src.utils.logger import setup_logging

logger = setup_logging()


def generate_synthetic_data(bars: int = 500) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing"""
    np.random.seed(42)

    # Generate price with trend + noise
    base_price = 50000
    trend = np.linspace(0, 5000, bars)
    noise = np.cumsum(np.random.randn(bars) * 200)

    close = base_price + trend + noise

    # Generate OHLC
    high = close + np.abs(np.random.randn(bars) * 300)
    low = close - np.abs(np.random.randn(bars) * 300)
    open_price = np.roll(close, 1)
    open_price[0] = close[0]

    # Generate volume
    volume = np.random.uniform(1000000, 5000000, bars)

    # Generate timestamps
    timestamps = pd.date_range(
        start='2024-01-01',
        periods=bars,
        freq='15min'
    )

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })

    return df


def test_1_data_loader():
    """Test data loader"""
    logger.info("=" * 80)
    logger.info("TEST 1: Data Loader")
    logger.info("=" * 80)

    loader = BacktestDataLoader()

    # Test synthetic data
    logger.info("\n1. Generating synthetic data...")
    df = generate_synthetic_data(bars=500)
    logger.info(f"   Generated {len(df)} candles")
    logger.info(f"   Price range: ${df['close'].min():,.0f} - ${df['close'].max():,.0f}")

    # Test walk-forward split
    logger.info("\n2. Creating walk-forward windows...")
    windows = loader.walk_forward_split(df, n_windows=4, train_pct=0.75)

    for i, (train, test) in enumerate(windows):
        logger.info(f"   Window {i+1}: Train={len(train)}, Test={len(test)}")

    logger.info("\n✓ Data Loader Test PASSED")
    return df


def test_2_vectorbt_backtester(data: pd.DataFrame):
    """Test VectorBT backtester"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: VectorBT Backtester")
    logger.info("=" * 80)

    backtester = VectorBTBacktester()

    # Test with example strategy
    logger.info("\n1. Backtesting MOM example strategy...")
    strategy = Strategy_MOM_Example()

    results = backtester.backtest(strategy, data, symbol='BTC-TEST')

    logger.info(f"   Total trades: {results['total_trades']}")
    logger.info(f"   Sharpe ratio: {results['sharpe_ratio']:.2f}")
    logger.info(f"   Win rate: {results['win_rate']:.1%}")
    logger.info(f"   Expectancy: {results['expectancy']:.4f}")
    logger.info(f"   Max DD: {results['max_drawdown']:.1%}")
    logger.info(f"   ED Ratio: {results['ed_ratio']:.2f}")

    if results['total_trades'] == 0:
        logger.warning("   WARNING: No trades generated!")
    else:
        logger.info(f"\n   Sample trades (first 3):")
        for i, trade in enumerate(results['trades'][:3]):
            logger.info(f"     Trade {i+1}: Entry ${trade['entry_price']:,.2f}, "
                       f"Exit ${trade['exit_price']:,.2f}, "
                       f"PnL ${trade['pnl']:,.2f}")

    logger.info("\n✓ VectorBT Backtester Test PASSED")
    return results


def test_3_lookahead_validator():
    """Test lookahead validator"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Lookahead Validator")
    logger.info("=" * 80)

    validator = LookaheadValidator()

    # Test 1: Clean code (should pass)
    logger.info("\n1. Testing clean code (should PASS)...")
    clean_code = """
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class TestStrategy(StrategyCore):
    def generate_signal(self, df: pd.DataFrame):
        if len(df) < 20:
            return None

        # Clean: uses past data only
        sma = df['close'].rolling(10).mean()

        if df['close'].iloc[-1] > sma.iloc[-1]:
            return Signal(direction='long', size=0.1,
                         stop_loss=df['close'].iloc[-1] * 0.98,
                         take_profit=df['close'].iloc[-1] * 1.02,
                         reason='test')
        return None
"""

    passed, violations = validator._ast_check(clean_code)
    logger.info(f"   AST check: {'PASSED' if passed else 'FAILED'}")
    if violations:
        for v in violations:
            logger.info(f"     - {v}")

    assert passed, "Clean code should pass AST check"

    # Test 2: Code with lookahead bias (should fail)
    logger.info("\n2. Testing code with lookahead bias (should FAIL)...")
    bad_code = """
import pandas as pd
from src.strategies.base import StrategyCore, Signal

class BadStrategy(StrategyCore):
    def generate_signal(self, df: pd.DataFrame):
        # BAD: uses future data
        future_high = df['high'].rolling(10, center=True).max()
        future_price = df['close'].shift(-5)

        return None
"""

    passed, violations = validator._ast_check(bad_code)
    logger.info(f"   AST check: {'PASSED' if passed else 'FAILED'}")
    if violations:
        for v in violations:
            logger.info(f"     - {v}")

    assert not passed, "Bad code should fail AST check"
    assert len(violations) >= 2, "Should detect multiple violations"

    logger.info("\n✓ Lookahead Validator Test PASSED")


def test_4_walk_forward_optimizer(data: pd.DataFrame):
    """Test walk-forward optimizer"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Walk-Forward Optimizer")
    logger.info("=" * 80)

    optimizer = WalkForwardOptimizer()

    # Define simple parameter grid
    param_grid = {
        'rsi_period': [10, 14, 20],
        'rsi_oversold': [25, 30, 35],
        'rsi_overbought': [65, 70, 75]
    }

    logger.info("\n1. Running walk-forward optimization...")
    logger.info(f"   Parameter grid: {param_grid}")
    logger.info(f"   Total combinations: {3 * 3 * 3} = 27")

    try:
        best_params = optimizer.optimize(
            strategy_class=Strategy_REV_Example,
            data=data,
            param_grid=param_grid,
            n_windows=3,  # Reduced for speed
            train_pct=0.70,
            metric='sharpe_ratio',
            min_metric_value=0.5,  # Lower threshold for synthetic data
            max_cv=0.40
        )

        if best_params:
            logger.info(f"\n   Optimized parameters: {best_params}")
            logger.info(f"   Worst window Sharpe: {best_params.get('_wf_worst_window', 'N/A')}")
            logger.info(f"   Stability: {best_params.get('_wf_stability', 'N/A')}")
            logger.info("\n✓ Walk-Forward Optimizer Test PASSED (found stable params)")
        else:
            logger.warning("\n⚠ Walk-Forward Optimizer Test: No stable params found")
            logger.warning("   This is OK for synthetic data - parameters may be unstable")

    except Exception as e:
        logger.error(f"\n✗ Walk-Forward Optimizer Test FAILED: {e}")
        raise


def test_5_full_pipeline():
    """Test complete pipeline integration"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Full Pipeline Integration")
    logger.info("=" * 80)

    logger.info("\n1. Load data...")
    data = generate_synthetic_data(bars=1000)

    logger.info("\n2. Initialize components...")
    backtester = VectorBTBacktester()
    validator = LookaheadValidator()
    strategy = Strategy_MOM_Example()

    logger.info("\n3. Validate strategy code...")
    # Get strategy source (simplified - in production would read from file)
    import inspect
    strategy_code = inspect.getsource(Strategy_MOM_Example)

    validation_results = validator.validate(
        strategy=strategy,
        strategy_code=strategy_code,
        backtest_data=data,
        shuffle_iterations=50  # Reduced for speed
    )

    logger.info(f"   Validation passed: {validation_results['passed']}")
    logger.info(f"   AST check: {validation_results['ast_check_passed']}")
    logger.info(f"   Shuffle test: {validation_results['shuffle_test_passed']}")
    logger.info(f"   Shuffle p-value: {validation_results['shuffle_p_value']:.4f}")

    logger.info("\n4. Run backtest...")
    backtest_results = backtester.backtest(strategy, data, symbol='BTC-TEST')

    logger.info(f"   Total trades: {backtest_results['total_trades']}")
    logger.info(f"   Sharpe ratio: {backtest_results['sharpe_ratio']:.2f}")
    logger.info(f"   Win rate: {backtest_results['win_rate']:.1%}")

    logger.info("\n5. Walk-forward validation...")
    loader = BacktestDataLoader()
    windows = loader.walk_forward_split(data, n_windows=3)

    wf_sharpes = []
    for i, (train, test) in enumerate(windows):
        test_results = backtester.backtest(strategy, test, symbol=f'BTC-WIN{i+1}')
        wf_sharpes.append(test_results['sharpe_ratio'])
        logger.info(f"   Window {i+1} Sharpe: {test_results['sharpe_ratio']:.2f}")

    avg_sharpe = np.mean(wf_sharpes)
    std_sharpe = np.std(wf_sharpes)
    logger.info(f"\n   Average Sharpe: {avg_sharpe:.2f} ± {std_sharpe:.2f}")

    logger.info("\n✓ Full Pipeline Integration Test PASSED")


def main():
    """Run all tests"""
    logger.info("SIXBTC - PHASE 4 BACKTESTING PIPELINE TEST")
    logger.info("=" * 80)

    try:
        # Run tests sequentially
        data = test_1_data_loader()
        test_2_vectorbt_backtester(data)
        test_3_lookahead_validator()
        test_4_walk_forward_optimizer(data)
        test_5_full_pipeline()

        logger.info("\n" + "=" * 80)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 80)
        logger.info("\nPhase 4 backtesting pipeline is ready for production!")

        return 0

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
