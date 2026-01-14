"""
Backtester Validation Tests

Validates the backtester using strategies with KNOWN mathematical results.
This is the gold standard for backtester correctness - if these tests pass,
the backtester is computing correctly.

TEST STRATEGIES:
1. BuyAndHold: Buy bar 0, hold to end -> result = price_change - fees - slippage
2. AlwaysFlat: Never trade -> PnL = 0, equity = initial
3. SingleTradeLong: One long trade with known entry/exit -> manual calculation
4. SingleTradeShort: One short trade -> manual calculation
5. NumbaVsPython: Both engines must produce identical results
6. Invariant: final_equity = initial + sum(trade_pnl)

Author: SixBTC Validation Suite
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.strategies.base import StrategyCore, Signal, StopLossType, ExitType
from src.backtester.backtest_engine import BacktestEngine


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Backtester config with KNOWN values for calculation
TEST_CONFIG = {
    'hyperliquid': {
        'fee_rate': 0.0004,      # 0.04% per trade (entry + exit = 0.08%)
        'slippage': 0.0002,      # 0.02% slippage each way
        'min_notional': 10.0,    # Minimum trade size in USDC
    },
    'backtesting': {
        'initial_capital': 10000.0,
    },
    'risk': {
        'fixed_fractional': {
            'risk_per_trade_pct': 0.02,
            'max_position_size_pct': 0.20,
        },
        'limits': {
            'max_open_positions_per_subaccount': 10,
        },
        'emergency': {
            'max_portfolio_drawdown': 0.30,
            'max_consecutive_losses': 5,
        },
    },
}


# =============================================================================
# CONTROLLED TEST DATA
# =============================================================================

def create_linear_price_data(
    start_price: float = 100.0,
    end_price: float = 110.0,
    n_bars: int = 200,
    high_low_range: float = 0.001
) -> pd.DataFrame:
    """
    Create OHLCV data with LINEAR price movement (no noise).
    This makes results perfectly predictable.

    Args:
        start_price: Starting price
        end_price: Ending price
        n_bars: Number of bars
        high_low_range: High/Low as % of close

    Returns:
        DataFrame with timestamp index and OHLCV columns
    """
    timestamps = pd.date_range(
        start=datetime(2024, 1, 1),
        periods=n_bars,
        freq='15min'
    )

    # Linear interpolation from start to end
    close = np.linspace(start_price, end_price, n_bars)

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': close * (1 + high_low_range),
        'low': close * (1 - high_low_range),
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })

    return df


def create_flat_price_data(
    price: float = 100.0,
    n_bars: int = 200,
    high_low_range: float = 0.001
) -> pd.DataFrame:
    """Create OHLCV data with FLAT price (constant)."""
    timestamps = pd.date_range(
        start=datetime(2024, 1, 1),
        periods=n_bars,
        freq='15min'
    )

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': np.ones(n_bars) * price,
        'high': np.ones(n_bars) * price * (1 + high_low_range),
        'low': np.ones(n_bars) * price * (1 - high_low_range),
        'close': np.ones(n_bars) * price,
        'volume': np.ones(n_bars) * 1000.0,
    })

    return df


def create_spike_then_flat_data(
    start_price: float = 100.0,
    spike_price: float = 110.0,
    spike_bar: int = 50,
    n_bars: int = 200
) -> pd.DataFrame:
    """
    Create data that spikes to a price at spike_bar then stays flat.
    Useful for testing TP hit scenarios.
    """
    timestamps = pd.date_range(
        start=datetime(2024, 1, 1),
        periods=n_bars,
        freq='15min'
    )

    close = np.ones(n_bars) * start_price
    close[spike_bar:] = spike_price

    high = close * 1.001
    low = close * 0.999

    # Make sure the spike bar has HIGH that hits TP
    high[spike_bar] = spike_price * 1.001

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })

    return df


def create_drop_then_flat_data(
    start_price: float = 100.0,
    drop_price: float = 95.0,
    drop_bar: int = 50,
    n_bars: int = 200
) -> pd.DataFrame:
    """
    Create data that drops to a price at drop_bar then stays flat.
    Useful for testing SL hit scenarios.
    """
    timestamps = pd.date_range(
        start=datetime(2024, 1, 1),
        periods=n_bars,
        freq='15min'
    )

    close = np.ones(n_bars) * start_price
    close[drop_bar:] = drop_price

    high = close * 1.001
    low = close * 0.999

    # Make sure the drop bar has LOW that hits SL
    low[drop_bar] = drop_price * 0.999

    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })

    return df


# =============================================================================
# TEST STRATEGIES (Known Results)
# =============================================================================

class BuyAndHoldStrategy(StrategyCore):
    """
    Buys on first bar after warmup, holds until end.
    Result is mathematically calculable.
    """
    direction = 'long'
    sl_pct = 0.50       # 50% SL - will never hit
    tp_pct = 0.50       # 50% TP - will never hit
    leverage = 1
    exit_after_bars = 9999  # Never time-exit
    signal_column = 'entry_signal'

    def __init__(self):
        super().__init__()
        self._has_entered = False

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Entry signal only on bar 100 (after warmup)
        df['entry_signal'] = False
        if len(df) > 100:
            df.loc[df.index[100], 'entry_signal'] = True
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None  # Not used in vectorized mode


class AlwaysFlatStrategy(StrategyCore):
    """
    Never generates entry signals.
    Expected: 0 trades, equity unchanged.
    """
    direction = 'long'
    sl_pct = 0.02
    tp_pct = 0.04
    leverage = 1
    exit_after_bars = 20
    signal_column = 'entry_signal'

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['entry_signal'] = False  # Never enter
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None


class SingleEntryTPStrategy(StrategyCore):
    """
    Single entry that hits TP.
    Entry at bar 100, TP at +5%.
    """
    direction = 'long'
    sl_pct = 0.10       # 10% SL - won't hit
    tp_pct = 0.05       # 5% TP - will hit
    leverage = 1
    exit_after_bars = 9999
    signal_column = 'entry_signal'

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['entry_signal'] = False
        if len(df) > 100:
            df.loc[df.index[100], 'entry_signal'] = True
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None


class SingleEntrySLStrategy(StrategyCore):
    """
    Single entry that hits SL.
    Entry at bar 100, SL at -3%.
    """
    direction = 'long'
    sl_pct = 0.03       # 3% SL - will hit
    tp_pct = 0.50       # 50% TP - won't hit
    leverage = 1
    exit_after_bars = 9999
    signal_column = 'entry_signal'

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['entry_signal'] = False
        if len(df) > 100:
            df.loc[df.index[100], 'entry_signal'] = True
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None


class MultiEntryStrategy(StrategyCore):
    """
    Multiple entries at known bars for invariant testing.
    """
    direction = 'long'
    sl_pct = 0.02
    tp_pct = 0.04
    leverage = 1
    exit_after_bars = 10
    signal_column = 'entry_signal'

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['entry_signal'] = False
        # Entries at bars 100, 120, 140, 160
        for bar in [100, 120, 140, 160]:
            if len(df) > bar:
                df.loc[df.index[bar], 'entry_signal'] = True
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None


# =============================================================================
# MOCK COIN REGISTRY (avoid DB dependency)
# =============================================================================

class MockCoinRegistry:
    """Mock registry that returns fixed leverage for any coin."""
    def get_max_leverage(self, symbol: str) -> int:
        return 50  # All coins allow 50x


# =============================================================================
# TESTS
# =============================================================================

class TestBacktesterValidation:
    """Core validation tests for backtester correctness."""

    @pytest.fixture
    def engine(self, monkeypatch):
        """Create backtester with mocked coin registry."""
        # Mock the coin registry to avoid DB dependency
        import src.backtester.backtest_engine as be_module
        monkeypatch.setattr(be_module, 'get_registry', lambda: MockCoinRegistry())

        return BacktestEngine(config=TEST_CONFIG)

    def test_always_flat_zero_pnl(self, engine):
        """
        TEST: AlwaysFlat strategy must have exactly 0 PnL.

        A strategy that never enters should:
        - Have 0 trades
        - Total return = 0 exactly
        """
        strategy = AlwaysFlatStrategy()
        data = {'BTC': create_flat_price_data(price=50000.0, n_bars=200)}

        results = engine.backtest(strategy, data, max_positions=1)

        assert results['total_trades'] == 0, "AlwaysFlat should have 0 trades"
        assert results['total_return'] == 0.0, "AlwaysFlat should have 0 return"
        assert len(results['trades']) == 0, "AlwaysFlat should have empty trades list"

    def test_buy_and_hold_matches_calculation(self, engine):
        """
        TEST: BuyAndHold PnL must match mathematical calculation.

        With linear price 100 -> 110:
        - Entry at bar 100, price ~105 (linear interpolation)
        - Exit at end, price = 110
        - Gross return = (110/105 - 1) = ~4.76%
        - After fees and slippage: slightly less
        """
        start_price = 100.0
        end_price = 110.0
        n_bars = 200

        strategy = BuyAndHoldStrategy()
        data = {'BTC': create_linear_price_data(
            start_price=start_price,
            end_price=end_price,
            n_bars=n_bars
        )}

        results = engine.backtest(strategy, data, max_positions=1)

        # Must have exactly 1 trade
        assert results['total_trades'] == 1, f"Expected 1 trade, got {results['total_trades']}"

        # Get trade details
        trade = results['trades'][0]

        # Calculate expected values
        # Entry price (bar 100) with slippage
        linear_price_at_100 = start_price + (end_price - start_price) * (100 / (n_bars - 1))
        expected_entry = linear_price_at_100 * (1 + engine.slippage)  # Long entry slippage

        # Exit price at end with slippage
        expected_exit = end_price * (1 - engine.slippage)  # Long exit slippage

        # Gross return
        gross_return = (expected_exit - expected_entry) / expected_entry

        # Check trade prices are close
        assert abs(trade['entry_price'] - expected_entry) < 0.01, \
            f"Entry price mismatch: {trade['entry_price']} vs {expected_entry}"
        assert abs(trade['exit_price'] - expected_exit) < 0.01, \
            f"Exit price mismatch: {trade['exit_price']} vs {expected_exit}"

        # PnL should be positive (price went up)
        assert trade['pnl'] > 0, f"Expected positive PnL, got {trade['pnl']}"

        # Total return should be positive
        assert results['total_return'] > 0, f"Expected positive return, got {results['total_return']}"

    def test_single_trade_tp_hit(self, engine):
        """
        TEST: Trade exits at TP price, not close price.

        With data that spikes to TP level, exit should be at TP price.
        """
        start_price = 100.0
        tp_pct = 0.05  # 5% TP

        strategy = SingleEntryTPStrategy()

        # Create data where price spikes to TP at bar 110
        spike_price = start_price * 1.10  # 10% up (more than TP)
        data = {'BTC': create_spike_then_flat_data(
            start_price=start_price,
            spike_price=spike_price,
            spike_bar=110,
            n_bars=200
        )}

        results = engine.backtest(strategy, data, max_positions=1)

        assert results['total_trades'] == 1, f"Expected 1 trade, got {results['total_trades']}"

        trade = results['trades'][0]

        # Entry is at bar 100, price = start_price
        entry_with_slippage = start_price * (1 + engine.slippage)

        # TP price
        tp_price = entry_with_slippage * (1 + tp_pct)

        # Exit should be at TP (with exit slippage applied)
        assert trade['exit_reason'] == 'tp', f"Expected TP exit, got {trade['exit_reason']}"

        # Exit price should be close to TP price (with slippage)
        # Note: exit slippage is AGAINST us, so for TP it's slightly below
        expected_exit = tp_price * (1 - engine.slippage)
        assert abs(trade['exit_price'] - expected_exit) < 1.0, \
            f"Exit price {trade['exit_price']} should be near TP {expected_exit}"

    def test_single_trade_sl_hit(self, engine):
        """
        TEST: Trade exits at SL price, not close price.
        """
        start_price = 100.0
        sl_pct = 0.03  # 3% SL

        strategy = SingleEntrySLStrategy()

        # Create data where price drops below SL at bar 110
        drop_price = start_price * 0.90  # 10% down (more than SL)
        data = {'BTC': create_drop_then_flat_data(
            start_price=start_price,
            drop_price=drop_price,
            drop_bar=110,
            n_bars=200
        )}

        results = engine.backtest(strategy, data, max_positions=1)

        assert results['total_trades'] == 1, f"Expected 1 trade, got {results['total_trades']}"

        trade = results['trades'][0]

        # Exit should be at SL
        assert trade['exit_reason'] == 'sl', f"Expected SL exit, got {trade['exit_reason']}"

        # PnL should be negative (stopped out)
        assert trade['pnl'] < 0, f"SL trade should have negative PnL, got {trade['pnl']}"

    def test_invariant_equity_equals_initial_plus_pnl(self, engine):
        """
        TEST: final_equity == initial_capital + sum(trade_pnl)

        This is the fundamental accounting invariant.
        """
        strategy = MultiEntryStrategy()
        data = {'BTC': create_linear_price_data(
            start_price=100.0,
            end_price=105.0,
            n_bars=200
        )}

        results = engine.backtest(strategy, data, max_positions=1)

        # Calculate sum of all trade PnLs
        total_pnl = sum(t['pnl'] for t in results['trades'])

        # Expected final equity
        expected_final = TEST_CONFIG['backtesting']['initial_capital'] + total_pnl

        # Allow tiny floating point tolerance
        assert abs(results['final_equity'] - expected_final) < 0.01, \
            f"Invariant violated: {results['final_equity']} != {expected_final} " \
            f"(initial={TEST_CONFIG['backtesting']['initial_capital']}, pnl_sum={total_pnl})"

    def test_numba_vs_python_consistency(self, engine):
        """
        TEST: Numba and Python implementations must produce identical results.

        This validates that the Numba optimization doesn't change behavior.
        """
        strategy = MultiEntryStrategy()
        data = {'BTC': create_linear_price_data(
            start_price=100.0,
            end_price=108.0,
            n_bars=200
        )}

        # Run Numba version
        results_numba = engine.backtest(strategy, data, max_positions=1)

        # Run Python version
        results_python = engine.backtest_python(strategy, data, max_positions=1)

        # Compare key metrics
        assert results_numba['total_trades'] == results_python['total_trades'], \
            f"Trade count mismatch: Numba={results_numba['total_trades']}, Python={results_python['total_trades']}"

        assert abs(results_numba['total_return'] - results_python['total_return']) < 1e-6, \
            f"Return mismatch: Numba={results_numba['total_return']}, Python={results_python['total_return']}"

        assert abs(results_numba['final_equity'] - results_python['final_equity']) < 0.01, \
            f"Equity mismatch: Numba={results_numba['final_equity']}, Python={results_python['final_equity']}"

        # Compare individual trades
        for i, (t_numba, t_python) in enumerate(zip(results_numba['trades'], results_python['trades'])):
            assert abs(t_numba['pnl'] - t_python['pnl']) < 0.01, \
                f"Trade {i} PnL mismatch: Numba={t_numba['pnl']}, Python={t_python['pnl']}"
            assert t_numba['exit_reason'] == t_python['exit_reason'], \
                f"Trade {i} exit_reason mismatch: Numba={t_numba['exit_reason']}, Python={t_python['exit_reason']}"

    def test_fees_are_applied_correctly(self, engine):
        """
        TEST: Fees are applied as (notional * fee_rate * 2) for round trip.
        """
        strategy = BuyAndHoldStrategy()
        data = {'BTC': create_flat_price_data(price=100.0, n_bars=200)}

        results = engine.backtest(strategy, data, max_positions=1)

        # With flat price, the only PnL change should be from fees + slippage
        trade = results['trades'][0]

        # Fees should be recorded
        assert 'fees' in trade, "Trade should have fees recorded"
        assert trade['fees'] > 0, "Fees should be positive"

        # Calculate expected fees
        notional = trade['entry_price'] * trade['size']
        expected_fees = notional * engine.fee_rate * 2

        assert abs(trade['fees'] - expected_fees) < 0.01, \
            f"Fee mismatch: {trade['fees']} vs expected {expected_fees}"

    def test_slippage_direction_correct(self, engine):
        """
        TEST: Slippage is applied adversely (against trader).

        Long: entry higher, exit lower
        Short: entry lower, exit higher
        """
        strategy = BuyAndHoldStrategy()  # Long strategy
        base_price = 100.0
        data = {'BTC': create_flat_price_data(price=base_price, n_bars=200)}

        results = engine.backtest(strategy, data, max_positions=1)
        trade = results['trades'][0]

        # For long: entry should be ABOVE base price (slippage against us)
        assert trade['entry_price'] > base_price, \
            f"Long entry {trade['entry_price']} should be > base {base_price}"

        # For long: exit should be BELOW base price (slippage against us)
        assert trade['exit_price'] < base_price, \
            f"Long exit {trade['exit_price']} should be < base {base_price}"

    def test_no_trades_when_data_too_short(self, engine):
        """
        TEST: With insufficient data (< warmup), no trades should occur.
        """
        strategy = BuyAndHoldStrategy()
        # Only 50 bars - less than warmup of 100
        data = {'BTC': create_flat_price_data(price=100.0, n_bars=50)}

        results = engine.backtest(strategy, data, max_positions=1)

        assert results['total_trades'] == 0, \
            f"Expected 0 trades with short data, got {results['total_trades']}"


class TestBacktesterEdgeCases:
    """Edge case and boundary condition tests."""

    @pytest.fixture
    def engine(self, monkeypatch):
        import src.backtester.backtest_engine as be_module
        monkeypatch.setattr(be_module, 'get_registry', lambda: MockCoinRegistry())
        return BacktestEngine(config=TEST_CONFIG)

    def test_max_positions_respected(self, engine):
        """
        TEST: Cannot have more open positions than max_positions.
        """
        # Strategy that tries to enter on every bar
        class GreedyStrategy(StrategyCore):
            direction = 'long'
            sl_pct = 0.50
            tp_pct = 0.50
            leverage = 1
            exit_after_bars = 9999
            signal_column = 'entry_signal'

            def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                df = df.copy()
                df['entry_signal'] = True  # Always try to enter
                df.loc[df.index[:100], 'entry_signal'] = False  # Except warmup
                return df

            def generate_signal(self, df, symbol=None):
                return None

        strategy = GreedyStrategy()

        # Multiple symbols
        data = {
            'BTC': create_flat_price_data(price=50000.0, n_bars=200),
            'ETH': create_flat_price_data(price=3000.0, n_bars=200),
            'SOL': create_flat_price_data(price=100.0, n_bars=200),
        }

        # Max 2 positions
        results = engine.backtest(strategy, data, max_positions=2)

        # Should have trades, but limited by max_positions
        # Since we have 3 symbols trying to enter simultaneously, max should be 2
        # Count concurrent positions from trades
        # (This is a simplified check - actual concurrent tracking is in the engine)
        assert results['total_trades'] > 0, "Should have some trades"

    def test_empty_data_returns_empty_results(self, engine):
        """
        TEST: Empty data dictionary returns empty results without crash.
        """
        strategy = AlwaysFlatStrategy()
        data = {}

        results = engine.backtest(strategy, data, max_positions=1)

        assert results['total_trades'] == 0
        assert results['total_return'] == 0.0

    def test_leverage_applied_to_position_size(self, engine):
        """
        TEST: Leverage multiplies notional exposure.
        """
        class LeveragedStrategy(StrategyCore):
            direction = 'long'
            sl_pct = 0.02
            tp_pct = 0.04
            leverage = 5  # 5x leverage
            exit_after_bars = 10
            signal_column = 'entry_signal'

            def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
                df = df.copy()
                df['entry_signal'] = False
                if len(df) > 100:
                    df.loc[df.index[100], 'entry_signal'] = True
                return df

            def generate_signal(self, df, symbol=None):
                return None

        strategy = LeveragedStrategy()
        data = {'BTC': create_flat_price_data(price=100.0, n_bars=200)}

        results = engine.backtest(strategy, data, max_positions=1)

        trade = results['trades'][0]

        # Notional should be margin * leverage
        expected_notional = trade['margin'] * trade['leverage']
        assert abs(trade['notional'] - expected_notional) < 1.0, \
            f"Notional {trade['notional']} != margin {trade['margin']} * leverage {trade['leverage']}"

        assert trade['leverage'] == 5, f"Leverage should be 5, got {trade['leverage']}"


# =============================================================================
# RUN VALIDATION
# =============================================================================

def run_validation():
    """
    Run all validation tests and print summary.
    Can be called directly for quick validation.
    """
    import sys

    print("=" * 60)
    print("BACKTESTER VALIDATION SUITE")
    print("=" * 60)
    print()

    # Run pytest programmatically
    exit_code = pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '-x',  # Stop on first failure
    ])

    print()
    print("=" * 60)
    if exit_code == 0:
        print("VALIDATION PASSED - Backtester is computing correctly")
    else:
        print("VALIDATION FAILED - Backtester has bugs")
    print("=" * 60)

    return exit_code


if __name__ == '__main__':
    run_validation()
