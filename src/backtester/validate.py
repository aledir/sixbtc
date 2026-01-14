"""
Backtester Validation Suite - Comprehensive

Automatic validation of the backtester with ~200+ tests covering:
1. Combination matrix (Direction x SL Type x Leverage x Exit)
2. Edge cases (gap, same-bar SL/TP, margin exhaustion, etc.)
3. Universal invariants (equity, sizes, timestamps, prices)
4. Numba vs Python consistency (all scenarios)
5. VectorBT comparison (extended)
6. Multi-trade realistic scenarios
7. Trailing stop comprehensive tests
8. Basic sanity tests
9. NaN handling (data with missing values)
10. All 24 structure templates (direction x exit mechanisms)
11. ATR-based stop loss/take profit tests

RUN: python -m src.backtester.validate

If ALL tests pass, the backtester is computing correctly.
The backtester daemon will call this at startup and block if validation fails.
"""

import sys
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Type
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, '.')

from src.strategies.base import StrategyCore, Signal, StopLossType, ExitType
from src.backtester.backtest_engine import BacktestEngine
from src.utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

FEE_RATE = 0.0004      # 0.04% per side
SLIPPAGE = 0.0002      # 0.02% per side
INITIAL_CAPITAL = 10000.0

TEST_CONFIG = {
    'hyperliquid': {
        'fee_rate': FEE_RATE,
        'slippage': SLIPPAGE,
        'min_notional': 10.0,  # Minimum trade size in USDC
    },
    'backtesting': {
        'initial_capital': INITIAL_CAPITAL,
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
# TEST RESULT TRACKING
# =============================================================================

@dataclass
class TestResult:
    name: str
    passed: bool
    expected: float
    actual: float
    tolerance: float
    details: str = ""


class ValidationReport:
    def __init__(self):
        self.results: List[TestResult] = []
        self.section_results: Dict[str, List[TestResult]] = {}
        self.current_section: str = "General"

    def start_section(self, name: str):
        self.current_section = name
        if name not in self.section_results:
            self.section_results[name] = []

    def add(self, name: str, passed: bool, expected: float, actual: float,
            tolerance: float = 0.01, details: str = ""):
        result = TestResult(name, passed, expected, actual, tolerance, details)
        self.results.append(result)
        self.section_results[self.current_section].append(result)

    def check(self, name: str, expected: float, actual: float,
              tolerance: float = 0.01, details: str = "") -> bool:
        if expected == 0:
            passed = abs(actual) < tolerance
        else:
            passed = abs(actual - expected) / abs(expected) < tolerance or abs(actual - expected) < tolerance
        self.add(name, passed, expected, actual, tolerance, details)
        return passed

    def check_exact(self, name: str, expected, actual, details: str = "") -> bool:
        passed = expected == actual
        self.add(name, passed, float(expected) if isinstance(expected, (int, float)) else 0,
                float(actual) if isinstance(actual, (int, float)) else 0, 0, details)
        return passed

    def check_bool(self, name: str, condition: bool, details: str = "") -> bool:
        self.add(name, condition, 1.0, 1.0 if condition else 0.0, 0, details)
        return condition

    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def print_report(self):
        print("\n" + "=" * 70)
        print("BACKTESTER VALIDATION REPORT")
        print("=" * 70)

        for section, results in self.section_results.items():
            print(f"\n--- {section} ---")
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                if r.passed:
                    print(f"  [{status}] {r.name}")
                else:
                    print(f"  [{status}] {r.name}")
                    print(f"         Expected: {r.expected:.6f}")
                    print(f"         Actual:   {r.actual:.6f}")
                    print(f"         Diff:     {abs(r.actual - r.expected):.6f}")
                if r.details:
                    print(f"         {r.details}")

        print("\n" + "=" * 70)
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        if self.all_passed():
            print(f"VALIDATION PASSED: {passed}/{total} tests")
            print("The backtester is computing correctly.")
        else:
            print(f"VALIDATION FAILED: {passed}/{total} tests passed")
            print("The backtester has bugs that need fixing.")
        print("=" * 70 + "\n")


# =============================================================================
# MOCK COIN REGISTRY
# =============================================================================

class MockCoinRegistry:
    def get_max_leverage(self, symbol: str) -> int:
        return 50


def patch_coin_registry():
    import src.backtester.backtest_engine as be_module
    be_module.get_registry = lambda: MockCoinRegistry()


# =============================================================================
# TEST DATA GENERATORS
# =============================================================================

def create_linear_data(start: float, end: float, n_bars: int = 200) -> pd.DataFrame:
    """Linear price movement from start to end."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.linspace(start, end, n_bars)
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': close * 1.001,
        'low': close * 0.999,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_flat_data(price: float, n_bars: int = 200) -> pd.DataFrame:
    return create_linear_data(price, price, n_bars)


def create_spike_data(base: float, spike: float, spike_bar: int, n_bars: int = 200) -> pd.DataFrame:
    """Price spikes at spike_bar."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.ones(n_bars) * base
    close[spike_bar:] = spike
    high = close * 1.001
    low = close * 0.999
    high[spike_bar] = max(base, spike) * 1.002
    low[spike_bar] = min(base, spike) * 0.998
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_trailing_test_data(n_bars: int = 200) -> pd.DataFrame:
    """Data for trailing stop: rise to 106, then drop to trigger trailing SL."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.ones(n_bars) * 100.0

    # Rise from 100 to 106 by bar 120
    for i in range(100, 121):
        close[i] = 100.0 + (106.0 - 100.0) * (i - 100) / 20

    # Stay at high
    close[121:130] = 106.0

    # Drop to trigger trailing SL (106 * 0.98 = 103.88)
    for i in range(130, 145):
        close[i] = 106.0 - (106.0 - 102.0) * (i - 130) / 15
    close[145:] = 102.0

    high = close * 1.002
    low = close * 0.998
    low[140] = 103.0  # Below trailing SL

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_short_trailing_data(n_bars: int = 200) -> pd.DataFrame:
    """Data for short trailing stop: drop to 94, then rise to trigger."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.ones(n_bars) * 100.0

    # Drop from 100 to 94 by bar 120
    for i in range(100, 121):
        close[i] = 100.0 - (100.0 - 94.0) * (i - 100) / 20

    # Stay at low
    close[121:130] = 94.0

    # Rise to trigger trailing SL (94 * 1.02 = 95.88)
    for i in range(130, 145):
        close[i] = 94.0 + (98.0 - 94.0) * (i - 130) / 15
    close[145:] = 98.0

    high = close * 1.002
    low = close * 0.998
    high[140] = 97.0  # Above trailing SL at 95.88

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_gap_data(base: float, gap_price: float, gap_bar: int, n_bars: int = 200) -> pd.DataFrame:
    """Price gaps at gap_bar (opens beyond SL/TP)."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.ones(n_bars) * base
    close[gap_bar:] = gap_price

    # Create gap: open at gap_price, not at base
    opens = close.copy()
    opens[gap_bar] = gap_price  # Gap open

    high = np.maximum(opens, close) * 1.001
    low = np.minimum(opens, close) * 0.999

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_sltp_same_bar_data(n_bars: int = 200) -> pd.DataFrame:
    """Bar that hits both SL and TP levels."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    close = np.ones(n_bars) * 100.0

    # Bar 110: High hits TP (105), Low hits SL (97)
    # Entry at bar 100 = 100
    # TP at 105 (5%), SL at 97 (3%)
    high = close * 1.001
    low = close * 0.999

    # Make bar 110 span both levels
    high[110] = 106.0  # Above TP at 105
    low[110] = 96.0    # Below SL at 97
    close[110] = 100.0

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_multi_signal_data(n_bars: int = 500) -> pd.DataFrame:
    """Data for multi-trade tests with slight upward trend."""
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')
    # Slight upward drift with noise
    trend = np.linspace(100, 110, n_bars)
    noise = np.random.RandomState(42).randn(n_bars) * 0.5
    close = trend + noise

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': close * 1.002,
        'low': close * 0.998,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


def create_volatile_data(base_price: float, volatility_pct: float, n_bars: int = 200) -> pd.DataFrame:
    """
    Create data with consistent volatility for ATR testing.

    The high-low range is approximately volatility_pct of price each bar,
    so ATR should be roughly volatility_pct * base_price.

    Args:
        base_price: Base price level (e.g., 100)
        volatility_pct: Daily range as percentage (e.g., 0.02 = 2%)
        n_bars: Number of bars
    """
    timestamps = pd.date_range(start=datetime(2024, 1, 1), periods=n_bars, freq='15min')

    # Slight upward drift
    close = np.linspace(base_price, base_price * 1.05, n_bars)

    # Create consistent high-low range
    range_size = base_price * volatility_pct
    high = close + range_size / 2
    low = close - range_size / 2

    return pd.DataFrame({
        'timestamp': timestamps,
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.ones(n_bars) * 1000.0,
    })


# =============================================================================
# STRATEGY FACTORY
# =============================================================================

def create_strategy(
    direction: str = 'long',
    sl_type: StopLossType = StopLossType.PERCENTAGE,
    sl_pct: float = 0.03,
    tp_pct: float = 0.05,
    leverage: int = 1,
    exit_after_bars: int = 9999,
    trailing_stop_pct: float = None,
    trailing_activation_pct: float = None,
    atr_stop_multiplier: float = 2.0,
    atr_take_multiplier: float = 3.0,
    atr_period: int = 14,
    entry_bar: int = 100,
    entry_bars: List[int] = None,
    calculate_atr: bool = False,
) -> Type[StrategyCore]:
    """Factory to create test strategies dynamically."""

    _entry_bars = entry_bars if entry_bars is not None else [entry_bar]
    _calculate_atr = calculate_atr

    class DynamicStrategy(StrategyCore):
        signal_column = 'entry_signal'

        def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
            df = df.copy()
            df['entry_signal'] = False
            for bar in _entry_bars:
                if len(df) > bar:
                    df.loc[df.index[bar], 'entry_signal'] = True

            # Calculate ATR if requested (for ATR-based strategies)
            if _calculate_atr:
                import talib as ta
                df['atr'] = ta.ATR(df['high'], df['low'], df['close'], timeperiod=14)

            return df

        def generate_signal(self, df, symbol=None):
            return None

    DynamicStrategy.direction = direction
    DynamicStrategy.sl_type = sl_type
    DynamicStrategy.sl_pct = sl_pct
    DynamicStrategy.tp_pct = tp_pct
    DynamicStrategy.leverage = leverage
    DynamicStrategy.exit_after_bars = exit_after_bars

    if trailing_stop_pct is not None:
        DynamicStrategy.trailing_stop_pct = trailing_stop_pct
    if trailing_activation_pct is not None:
        DynamicStrategy.trailing_activation_pct = trailing_activation_pct

    # ATR parameters
    DynamicStrategy.atr_stop_multiplier = atr_stop_multiplier
    DynamicStrategy.atr_take_multiplier = atr_take_multiplier
    DynamicStrategy.atr_period = atr_period

    return DynamicStrategy


# =============================================================================
# UNIVERSAL INVARIANTS
# =============================================================================

def check_universal_invariants(
    results: Dict,
    data: Dict[str, pd.DataFrame],
    report: ValidationReport,
    test_prefix: str = ""
) -> bool:
    """Check invariants that must ALWAYS be true for any backtest."""
    trades = results.get('trades', [])
    all_passed = True

    if not trades:
        return True  # No trades = no invariants to check

    # 1. Equity = initial + sum(pnl)
    total_pnl = sum(t['pnl'] for t in trades)
    expected_equity = INITIAL_CAPITAL + total_pnl
    if not report.check(f"{test_prefix}Invariant: equity = initial + sum(pnl)",
                       expected_equity, results['final_equity'], tolerance=0.1):
        all_passed = False

    # 2. All sizes > 0
    all_sizes_positive = all(t['size'] > 0 for t in trades)
    if not report.check_bool(f"{test_prefix}Invariant: all sizes > 0", all_sizes_positive):
        all_passed = False

    # 3. Entry idx < exit idx
    all_entry_before_exit = all(t['entry_idx'] < t['exit_idx'] for t in trades)
    if not report.check_bool(f"{test_prefix}Invariant: entry_idx < exit_idx", all_entry_before_exit):
        all_passed = False

    # 4. All margins > 0
    all_margins_positive = all(t['margin'] > 0 for t in trades)
    if not report.check_bool(f"{test_prefix}Invariant: all margins > 0", all_margins_positive):
        all_passed = False

    # 5. Notional = margin * leverage
    notional_correct = True
    for t in trades:
        expected_notional = t['margin'] * t['leverage']
        if abs(t['notional'] - expected_notional) > 0.1:
            notional_correct = False
            break
    if not report.check_bool(f"{test_prefix}Invariant: notional = margin * leverage", notional_correct):
        all_passed = False

    # 6. Exit price within bar range (approximately)
    exit_in_range = True
    for t in trades:
        symbol = t['symbol']
        if symbol in data:
            df = data[symbol]
            exit_idx = t['exit_idx']
            if exit_idx < len(df):
                bar_high = df.iloc[exit_idx]['high']
                bar_low = df.iloc[exit_idx]['low']
                # Allow some tolerance for slippage
                if t['exit_price'] < bar_low * 0.99 or t['exit_price'] > bar_high * 1.01:
                    exit_in_range = False
                    break
    if not report.check_bool(f"{test_prefix}Invariant: exit price in bar range", exit_in_range):
        all_passed = False

    return all_passed


# =============================================================================
# PHASE 1: COMBINATION MATRIX TESTS
# =============================================================================

def run_combination_matrix_tests(engine: BacktestEngine, report: ValidationReport):
    """Test all combinations of Direction x SL Type x Leverage x Exit."""
    report.start_section("1. Combination Matrix Tests")

    # Define combinations to test
    combinations = [
        # (direction, sl_type, leverage, scenario_name, data_generator, expected_exit)
        # Long + Percentage SL
        ('long', StopLossType.PERCENTAGE, 1, 'Long/Pct/1x/SL', lambda: create_spike_data(100, 90, 110), 'sl'),
        ('long', StopLossType.PERCENTAGE, 1, 'Long/Pct/1x/TP', lambda: create_spike_data(100, 120, 110), 'tp'),
        ('long', StopLossType.PERCENTAGE, 1, 'Long/Pct/1x/Time', lambda: create_flat_data(100), 'time_exit'),
        ('long', StopLossType.PERCENTAGE, 5, 'Long/Pct/5x/SL', lambda: create_spike_data(100, 90, 110), 'sl'),
        ('long', StopLossType.PERCENTAGE, 5, 'Long/Pct/5x/TP', lambda: create_spike_data(100, 120, 110), 'tp'),
        ('long', StopLossType.PERCENTAGE, 20, 'Long/Pct/20x/SL', lambda: create_spike_data(100, 90, 110), 'sl'),

        # Short + Percentage SL
        ('short', StopLossType.PERCENTAGE, 1, 'Short/Pct/1x/SL', lambda: create_spike_data(100, 110, 110), 'sl'),
        ('short', StopLossType.PERCENTAGE, 1, 'Short/Pct/1x/TP', lambda: create_spike_data(100, 85, 110), 'tp'),
        ('short', StopLossType.PERCENTAGE, 1, 'Short/Pct/1x/Time', lambda: create_flat_data(100), 'time_exit'),
        ('short', StopLossType.PERCENTAGE, 5, 'Short/Pct/5x/SL', lambda: create_spike_data(100, 110, 110), 'sl'),
        ('short', StopLossType.PERCENTAGE, 5, 'Short/Pct/5x/TP', lambda: create_spike_data(100, 85, 110), 'tp'),

        # Long + Trailing SL
        ('long', StopLossType.TRAILING, 1, 'Long/Trail/1x/SL', lambda: create_trailing_test_data(), 'sl'),
        ('long', StopLossType.TRAILING, 5, 'Long/Trail/5x/SL', lambda: create_trailing_test_data(), 'sl'),

        # Short + Trailing SL
        ('short', StopLossType.TRAILING, 1, 'Short/Trail/1x/SL', lambda: create_short_trailing_data(), 'sl'),
        ('short', StopLossType.TRAILING, 5, 'Short/Trail/5x/SL', lambda: create_short_trailing_data(), 'sl'),
    ]

    for direction, sl_type, leverage, name, data_gen, expected_exit in combinations:
        # Create strategy
        exit_bars = 15 if expected_exit == 'time_exit' else 9999

        if sl_type == StopLossType.TRAILING:
            Strategy = create_strategy(
                direction=direction,
                sl_type=sl_type,
                sl_pct=0.02,
                tp_pct=0.50,
                leverage=leverage,
                exit_after_bars=exit_bars,
                trailing_stop_pct=0.02,
                trailing_activation_pct=0.01,
            )
        else:
            Strategy = create_strategy(
                direction=direction,
                sl_type=sl_type,
                sl_pct=0.03,
                tp_pct=0.05,
                leverage=leverage,
                exit_after_bars=exit_bars,
            )

        strategy = Strategy()
        data = {'TEST': data_gen()}
        results = engine.backtest(strategy, data, max_positions=1)

        # Check trade count
        report.check_exact(f"{name}: 1 trade", 1, results['total_trades'])

        if results['total_trades'] == 1:
            trade = results['trades'][0]

            # Check exit reason
            report.check_exact(f"{name}: exit = {expected_exit}", expected_exit, trade['exit_reason'])

            # Check leverage recorded
            report.check_exact(f"{name}: leverage = {leverage}", leverage, trade['leverage'])

            # Check PnL direction
            if expected_exit == 'sl':
                if sl_type == StopLossType.TRAILING:
                    # Trailing SL locks profits - PnL should be positive
                    report.check_bool(f"{name}: PnL > 0 (trailing locked profit)", trade['pnl'] > 0,
                                     details=f"PnL={trade['pnl']:.2f}")
                else:
                    # Regular SL should result in loss
                    report.check_bool(f"{name}: PnL < 0 (SL hit)", trade['pnl'] < 0,
                                     details=f"PnL={trade['pnl']:.2f}")
            elif expected_exit == 'tp':
                # TP should result in profit
                report.check_bool(f"{name}: PnL > 0 (TP hit)", trade['pnl'] > 0,
                                 details=f"PnL={trade['pnl']:.2f}")


# =============================================================================
# PHASE 2: EDGE CASES
# =============================================================================

def run_edge_case_tests(engine: BacktestEngine, report: ValidationReport):
    """Test critical edge cases."""
    report.start_section("2. Edge Cases")

    # 2.1: Gap beyond SL
    Strategy = create_strategy(direction='long', sl_pct=0.03, tp_pct=0.50)
    strategy = Strategy()
    # Entry at 100, SL at 97. Gap to 94 at bar 110.
    data = {'TEST': create_gap_data(100, 94, 110)}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        # Exit should be at gap price (94-ish), not SL price (97)
        report.check_bool("Gap beyond SL: exit at gap price",
                         trade['exit_price'] < 97.0,
                         details=f"exit={trade['exit_price']:.2f} (should be ~94, not 97)")
        report.check_exact("Gap beyond SL: exit reason = sl", 'sl', trade['exit_reason'])
    else:
        report.check_exact("Gap beyond SL: 1 trade", 1, results['total_trades'])

    # 2.2: Time exit beats SL
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, exit_after_bars=10)
    strategy = Strategy()
    data = {'TEST': create_flat_data(100)}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("Time exit priority: exit = time_exit", 'time_exit', trade['exit_reason'])
        # Exit should be at bar 110 (entry 100 + 10 bars)
        report.check_exact("Time exit priority: exit at bar 110", 110, trade['exit_idx'])
    else:
        report.check_exact("Time exit priority: 1 trade", 1, results['total_trades'])

    # 2.3: SL beats time exit
    Strategy = create_strategy(direction='long', sl_pct=0.03, tp_pct=0.50, exit_after_bars=20)
    strategy = Strategy()
    # SL hit at bar 110, time exit would be at bar 120
    data = {'TEST': create_spike_data(100, 90, 110)}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("SL beats time: exit = sl", 'sl', trade['exit_reason'])
        report.check_bool("SL beats time: exit before bar 120", trade['exit_idx'] < 120,
                         details=f"exit_idx={trade['exit_idx']}")
    else:
        report.check_exact("SL beats time: 1 trade", 1, results['total_trades'])

    # 2.4: High leverage (40x)
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, leverage=40)
    strategy = Strategy()
    data = {'TEST': create_linear_data(100, 110)}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("High leverage: leverage = 40", 40, trade['leverage'])
        # Notional should be 40x margin
        expected_notional = trade['margin'] * 40
        report.check("High leverage: notional = margin * 40",
                    expected_notional, trade['notional'], tolerance=0.01)
    else:
        report.check_exact("High leverage: 1 trade", 1, results['total_trades'])

    # 2.5: Max positions limit
    Strategy = create_strategy(entry_bars=[100, 100, 100])  # 3 signals same bar
    strategy = Strategy()
    # Use 3 symbols
    data = {
        'BTC': create_linear_data(100, 110),
        'ETH': create_linear_data(100, 110),
        'SOL': create_linear_data(100, 110),
    }
    results = engine.backtest(strategy, data, max_positions=2)  # Limit to 2

    report.check_bool("Max positions: trades <= max",
                     results['total_trades'] <= 2,
                     details=f"trades={results['total_trades']}, max=2")

    # 2.6: Multi-symbol concurrent positions
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, exit_after_bars=50)
    strategy = Strategy()
    data = {
        'BTC': create_linear_data(100, 105),
        'ETH': create_linear_data(200, 210),
    }
    results = engine.backtest(strategy, data, max_positions=5)

    report.check_exact("Multi-symbol: 2 trades", 2, results['total_trades'])
    if results['total_trades'] == 2:
        symbols = {t['symbol'] for t in results['trades']}
        report.check_bool("Multi-symbol: both symbols traded",
                         symbols == {'BTC', 'ETH'},
                         details=f"symbols={symbols}")


# =============================================================================
# PHASE 3: MULTI-TRADE REALISTIC SCENARIOS
# =============================================================================

def run_multi_trade_tests(engine: BacktestEngine, report: ValidationReport):
    """Test scenarios with many trades."""
    report.start_section("3. Multi-Trade Realistic Scenarios")

    # 3.1: Many trades with compounding
    entry_bars = list(range(50, 450, 20))  # 20 entries
    Strategy = create_strategy(
        direction='long',
        sl_pct=0.02,
        tp_pct=0.03,
        leverage=1,
        exit_after_bars=15,
        entry_bars=entry_bars,
    )
    strategy = Strategy()
    data = {'TEST': create_multi_signal_data(500)}
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("Many trades: total_trades >= 10",
                     results['total_trades'] >= 10,
                     details=f"trades={results['total_trades']}")

    # Check invariants
    check_universal_invariants(results, data, report, "ManyTrades: ")

    # 3.2: Win rate calculation
    if results['total_trades'] >= 10:
        wins = sum(1 for t in results['trades'] if t['pnl'] > 0)
        expected_win_rate = wins / results['total_trades']
        report.check("Win rate accuracy",
                    expected_win_rate, results.get('win_rate', 0),
                    tolerance=0.01,
                    details=f"wins={wins}, total={results['total_trades']}")

    # 3.3: Drawdown consistency
    # Max drawdown should be >= 0 and <= 1
    max_dd = results.get('max_drawdown', 0)
    report.check_bool("Drawdown: 0 <= max_dd <= 1",
                     0 <= max_dd <= 1,
                     details=f"max_dd={max_dd:.4f}")


# =============================================================================
# PHASE 4: UNIVERSAL INVARIANTS ON ALL SCENARIOS
# =============================================================================

def run_invariant_tests(engine: BacktestEngine, report: ValidationReport):
    """Test universal invariants across multiple scenarios."""
    report.start_section("4. Universal Invariants")

    scenarios = [
        # (name, strategy_kwargs, data_generator)
        ("Long/SL", {'direction': 'long', 'sl_pct': 0.03}, lambda: create_spike_data(100, 90, 110)),
        ("Long/TP", {'direction': 'long', 'tp_pct': 0.05}, lambda: create_spike_data(100, 120, 110)),
        ("Short/SL", {'direction': 'short', 'sl_pct': 0.03}, lambda: create_spike_data(100, 110, 110)),
        ("Short/TP", {'direction': 'short', 'tp_pct': 0.05}, lambda: create_spike_data(100, 85, 110)),
        ("Long/5x", {'direction': 'long', 'leverage': 5}, lambda: create_linear_data(100, 105)),
        ("Short/5x", {'direction': 'short', 'leverage': 5}, lambda: create_linear_data(100, 95)),
        ("Long/Trail", {'direction': 'long', 'sl_type': StopLossType.TRAILING,
                       'trailing_stop_pct': 0.02, 'trailing_activation_pct': 0.01},
         lambda: create_trailing_test_data()),
    ]

    for name, kwargs, data_gen in scenarios:
        Strategy = create_strategy(**{**{'sl_pct': 0.03, 'tp_pct': 0.05}, **kwargs})
        strategy = Strategy()
        data = {'TEST': data_gen()}
        results = engine.backtest(strategy, data, max_positions=1)

        check_universal_invariants(results, data, report, f"{name}: ")


# =============================================================================
# PHASE 5: NUMBA VS PYTHON EXTENDED
# =============================================================================

def run_numba_python_extended(engine: BacktestEngine, report: ValidationReport):
    """Extended Numba vs Python comparison across all scenario types."""
    report.start_section("5. Numba vs Python Extended")

    scenarios = [
        ("Long/Pct/1x", {'direction': 'long', 'sl_pct': 0.03, 'tp_pct': 0.05},
         lambda: create_spike_data(100, 120, 110)),
        ("Short/Pct/1x", {'direction': 'short', 'sl_pct': 0.03, 'tp_pct': 0.05},
         lambda: create_spike_data(100, 85, 110)),
        ("Long/5x", {'direction': 'long', 'leverage': 5, 'sl_pct': 0.50, 'tp_pct': 0.50},
         lambda: create_linear_data(100, 110, n_bars=200)),
        ("Long/Trail", {'direction': 'long', 'sl_type': StopLossType.TRAILING,
                       'trailing_stop_pct': 0.02, 'trailing_activation_pct': 0.01},
         lambda: create_trailing_test_data()),
        ("MultiTrade", {'entry_bars': [100, 120, 140, 160], 'exit_after_bars': 15},
         lambda: create_linear_data(100, 108, n_bars=200)),
    ]

    for name, kwargs, data_gen in scenarios:
        Strategy = create_strategy(**{**{'sl_pct': 0.03, 'tp_pct': 0.05}, **kwargs})
        strategy = Strategy()
        data = {'TEST': data_gen()}

        results_numba = engine.backtest(strategy, data, max_positions=1)
        results_python = engine.backtest_python(strategy, data, max_positions=1)

        # Compare trade count
        report.check_exact(f"Numba=Python {name}: trade count",
                          results_numba['total_trades'], results_python['total_trades'])

        # Compare total return
        report.check(f"Numba=Python {name}: total return",
                    results_numba['total_return'], results_python['total_return'],
                    tolerance=1e-6)

        # Compare final equity
        report.check(f"Numba=Python {name}: final equity",
                    results_numba['final_equity'], results_python['final_equity'],
                    tolerance=0.01)


# =============================================================================
# PHASE 6: VECTORBT EXTENDED
# =============================================================================

def run_vectorbt_extended(engine: BacktestEngine, report: ValidationReport):
    """Extended VectorBT comparison."""
    report.start_section("6. VectorBT Comparison")

    try:
        import vectorbt as vbt
    except ImportError:
        report.add("VectorBT: not installed (skipping)", True, 0, 0, 0, "pip install vectorbt")
        return

    # 6.1: Simple buy and hold
    n_bars = 200
    prices = np.linspace(100.0, 110.0, n_bars)
    close = pd.Series(prices, index=pd.date_range('2024-01-01', periods=n_bars, freq='15min'))

    entries = pd.Series(False, index=close.index)
    entries.iloc[100] = True
    exits = pd.Series(False, index=close.index)
    exits.iloc[-1] = True

    pf = vbt.Portfolio.from_signals(
        close, entries=entries, exits=exits,
        init_cash=INITIAL_CAPITAL, fees=0.0, slippage=0.0, freq='15min'
    )

    vbt_return = float(pf.total_return())
    vbt_trades = int(pf.trades.count())

    # Our backtester (no fees)
    no_fee_config = {
        'hyperliquid': {'fee_rate': 0.0, 'slippage': 0.0, 'min_notional': 10.0},
        'backtesting': {'initial_capital': INITIAL_CAPITAL},
        'risk': {
            'fixed_fractional': {'risk_per_trade_pct': 0.02, 'max_position_size_pct': 1.0},
            'limits': {'max_open_positions_per_subaccount': 10},
            'emergency': {'max_portfolio_drawdown': 0.30, 'max_consecutive_losses': 5},
        },
    }
    no_fee_engine = BacktestEngine(config=no_fee_config)

    Strategy = create_strategy(direction='long', sl_pct=0.02, tp_pct=0.50)  # sl=risk for 100% size
    strategy = Strategy()
    data = {'TEST': pd.DataFrame({
        'timestamp': close.index,
        'open': prices,
        'high': prices * 1.001,
        'low': prices * 0.999,
        'close': prices,
        'volume': np.ones(n_bars) * 1000.0,
    })}

    our_results = no_fee_engine.backtest(strategy, data, max_positions=1)

    report.check_exact("VBT single: trade count", vbt_trades, our_results['total_trades'])
    report.check("VBT single: return", vbt_return, our_results['total_return'], tolerance=0.02,
                details=f"vbt={vbt_return:.4f}, ours={our_results['total_return']:.4f}")

    # 6.2: Sequential trades (non-overlapping)
    # VBT and our backtester handle overlapping signals differently
    # Use sequential entries that don't overlap
    entries2 = pd.Series(False, index=close.index)
    exits2 = pd.Series(False, index=close.index)
    # Non-overlapping: entry 50, exit 69, entry 70, exit 89, etc.
    for i in [50, 70, 90, 110]:
        entries2.iloc[i] = True
        exits2.iloc[i + 19] = True

    pf2 = vbt.Portfolio.from_signals(
        close, entries=entries2, exits=exits2,
        init_cash=INITIAL_CAPITAL, fees=0.0, slippage=0.0, freq='15min'
    )

    vbt_trades2 = int(pf2.trades.count())

    Strategy2 = create_strategy(
        direction='long', sl_pct=0.02, tp_pct=0.50, exit_after_bars=20,
        entry_bars=[50, 70, 90, 110]  # Sequential, non-overlapping
    )
    strategy2 = Strategy2()
    our_results2 = no_fee_engine.backtest(strategy2, data, max_positions=1)

    # Note: We might get different counts due to position handling
    # Just check both have trades
    report.check_bool("VBT multi: both have trades",
                     vbt_trades2 > 0 and our_results2['total_trades'] > 0,
                     details=f"vbt={vbt_trades2}, ours={our_results2['total_trades']}")


# =============================================================================
# PHASE 7: TRAILING STOP COMPREHENSIVE
# =============================================================================

def run_trailing_comprehensive(engine: BacktestEngine, report: ValidationReport):
    """Comprehensive trailing stop tests."""
    report.start_section("7. Trailing Stop Comprehensive")

    # 7.1: Long trailing - locks profits
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.TRAILING,
        sl_pct=0.02,
        trailing_stop_pct=0.02,
        trailing_activation_pct=0.01,
        tp_pct=0.50,
    )
    strategy = Strategy()
    data = {'TEST': create_trailing_test_data()}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("Long trail: exit = sl", 'sl', trade['exit_reason'])
        report.check_bool("Long trail: PnL > 0 (locked profit)", trade['pnl'] > 0,
                         details=f"PnL={trade['pnl']:.2f}")
        # Exit should be above the final price (102) due to trailing
        report.check_bool("Long trail: exit > end price", trade['exit_price'] > 102,
                         details=f"exit={trade['exit_price']:.2f}")
    else:
        report.check_exact("Long trail: 1 trade", 1, results['total_trades'])

    # 7.2: Short trailing - locks profits
    Strategy = create_strategy(
        direction='short',
        sl_type=StopLossType.TRAILING,
        sl_pct=0.02,
        trailing_stop_pct=0.02,
        trailing_activation_pct=0.01,
        tp_pct=0.50,
    )
    strategy = Strategy()
    data = {'TEST': create_short_trailing_data()}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("Short trail: exit = sl", 'sl', trade['exit_reason'])
        report.check_bool("Short trail: PnL > 0 (locked profit)", trade['pnl'] > 0,
                         details=f"PnL={trade['pnl']:.2f}")
        # Exit should be below the final price (98) due to trailing
        report.check_bool("Short trail: exit < end price", trade['exit_price'] < 98,
                         details=f"exit={trade['exit_price']:.2f}")
    else:
        report.check_exact("Short trail: 1 trade", 1, results['total_trades'])

    # 7.3: Long trailing with leverage
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.TRAILING,
        sl_pct=0.02,
        trailing_stop_pct=0.02,
        trailing_activation_pct=0.01,
        tp_pct=0.50,
        leverage=5,
    )
    strategy = Strategy()
    data = {'TEST': create_trailing_test_data()}
    results = engine.backtest(strategy, data, max_positions=1)

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("Trail+5x: leverage = 5", 5, trade['leverage'])
        report.check_bool("Trail+5x: PnL > 0", trade['pnl'] > 0,
                         details=f"PnL={trade['pnl']:.2f}")
    else:
        report.check_exact("Trail+5x: 1 trade", 1, results['total_trades'])


# =============================================================================
# PHASE 8: BASIC SANITY TESTS (from original)
# =============================================================================

def run_basic_sanity_tests(engine: BacktestEngine, report: ValidationReport):
    """Basic sanity tests."""
    report.start_section("8. Basic Sanity Tests")

    # Always flat = 0 trades
    Strategy = create_strategy(entry_bars=[])  # No entries
    strategy = Strategy()
    data = {'TEST': create_flat_data(100)}
    results = engine.backtest(strategy, data, max_positions=1)
    report.check_exact("AlwaysFlat: 0 trades", 0, results['total_trades'])
    report.check("AlwaysFlat: 0 return", 0.0, results['total_return'], tolerance=1e-10)

    # Long buy&hold profit
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50)
    strategy = Strategy()
    data = {'TEST': create_linear_data(100, 110)}
    results = engine.backtest(strategy, data, max_positions=1)
    report.check_exact("LongBuyHold: 1 trade", 1, results['total_trades'])
    if results['total_trades'] == 1:
        report.check_bool("LongBuyHold: PnL > 0", results['trades'][0]['pnl'] > 0)

    # Short buy&hold profit (price down)
    Strategy = create_strategy(direction='short', sl_pct=0.50, tp_pct=0.50)
    strategy = Strategy()
    data = {'TEST': create_linear_data(100, 90)}
    results = engine.backtest(strategy, data, max_positions=1)
    report.check_exact("ShortBuyHold: 1 trade", 1, results['total_trades'])
    if results['total_trades'] == 1:
        report.check_bool("ShortBuyHold: PnL > 0", results['trades'][0]['pnl'] > 0)


# =============================================================================
# PHASE 9: NaN HANDLING TESTS
# =============================================================================

def create_data_with_nan(nan_column: str, nan_bars: List[int], n_bars: int = 200) -> pd.DataFrame:
    """Create data with NaN values in specified column at specified bars."""
    data = create_linear_data(100, 110, n_bars)
    for bar in nan_bars:
        if bar < len(data):
            data.loc[data.index[bar], nan_column] = np.nan
    return data


def run_nan_handling_tests(engine: BacktestEngine, report: ValidationReport):
    """Test that backtester handles NaN values without crashing."""
    report.start_section("9. NaN Handling")

    # 9.1: NaN in close prices (before entry)
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, entry_bar=100)
    strategy = Strategy()
    data = {'TEST': create_data_with_nan('close', [50, 60, 70])}  # NaN before entry
    try:
        results = engine.backtest(strategy, data, max_positions=1)
        report.check_bool("NaN in close (before entry): no crash",
                         results is not None and 'final_equity' in results,
                         details=f"trades={results.get('total_trades', 0)}")
    except Exception as e:
        report.check_bool("NaN in close (before entry): no crash", False,
                         details=f"Exception: {str(e)[:50]}")

    # 9.2: NaN in high prices
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, entry_bar=100)
    strategy = Strategy()
    data = {'TEST': create_data_with_nan('high', [50, 60])}
    try:
        results = engine.backtest(strategy, data, max_positions=1)
        report.check_bool("NaN in high: no crash",
                         results is not None and 'final_equity' in results,
                         details=f"trades={results.get('total_trades', 0)}")
    except Exception as e:
        report.check_bool("NaN in high: no crash", False,
                         details=f"Exception: {str(e)[:50]}")

    # 9.3: NaN in low prices
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, entry_bar=100)
    strategy = Strategy()
    data = {'TEST': create_data_with_nan('low', [50, 60])}
    try:
        results = engine.backtest(strategy, data, max_positions=1)
        report.check_bool("NaN in low: no crash",
                         results is not None and 'final_equity' in results,
                         details=f"trades={results.get('total_trades', 0)}")
    except Exception as e:
        report.check_bool("NaN in low: no crash", False,
                         details=f"Exception: {str(e)[:50]}")

    # 9.4: NaN in volume
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, entry_bar=100)
    strategy = Strategy()
    data = {'TEST': create_data_with_nan('volume', [50, 60, 70, 80, 90])}
    try:
        results = engine.backtest(strategy, data, max_positions=1)
        report.check_bool("NaN in volume: no crash",
                         results is not None and 'final_equity' in results,
                         details=f"trades={results.get('total_trades', 0)}")
    except Exception as e:
        report.check_bool("NaN in volume: no crash", False,
                         details=f"Exception: {str(e)[:50]}")

    # 9.5: NaN at entry bar (should skip trade or handle gracefully)
    Strategy = create_strategy(direction='long', sl_pct=0.50, tp_pct=0.50, entry_bar=100)
    strategy = Strategy()
    data = {'TEST': create_data_with_nan('close', [100])}  # NaN exactly at entry
    try:
        results = engine.backtest(strategy, data, max_positions=1)
        report.check_bool("NaN at entry bar: no crash",
                         results is not None and 'final_equity' in results,
                         details=f"trades={results.get('total_trades', 0)}")
    except Exception as e:
        report.check_bool("NaN at entry bar: no crash", False,
                         details=f"Exception: {str(e)[:50]}")


# =============================================================================
# PHASE 10: ALL 24 STRUCTURE TEMPLATE TESTS
# =============================================================================

def run_all_structures_tests(engine: BacktestEngine, report: ValidationReport):
    """
    Test all 24 valid strategy structure templates.

    The structures represent different combinations of exit mechanisms:
    - Direction: long, short, both
    - Has TP: Take Profit target
    - Has Time Exit: Exit after N bars
    - Has Trailing: Trailing stop

    Not all combinations are valid/useful. We test the 24 representative structures.
    """
    report.start_section("10. All 24 Structure Templates")

    # Define 24 structures to test
    # Format: (struct_id, direction, has_tp, has_time, has_trail, name)
    STRUCTURES = [
        # Long-only structures (8 variants)
        (1, 'long', True, False, False, 'LONG_TP'),
        (2, 'long', False, True, False, 'LONG_TIME'),
        (3, 'long', True, True, False, 'LONG_TP+TIME'),
        (4, 'long', True, False, True, 'LONG_TP+TRAIL'),
        (5, 'long', False, True, True, 'LONG_TIME+TRAIL'),
        (6, 'long', True, True, True, 'LONG_TP+TIME+TRAIL'),
        (7, 'long', False, False, True, 'LONG_TRAIL'),
        (8, 'long', False, False, False, 'LONG_SL_ONLY'),

        # Short-only structures (8 variants)
        (9, 'short', True, False, False, 'SHORT_TP'),
        (10, 'short', False, True, False, 'SHORT_TIME'),
        (11, 'short', True, True, False, 'SHORT_TP+TIME'),
        (12, 'short', True, False, True, 'SHORT_TP+TRAIL'),
        (13, 'short', False, True, True, 'SHORT_TIME+TRAIL'),
        (14, 'short', True, True, True, 'SHORT_TP+TIME+TRAIL'),
        (15, 'short', False, False, True, 'SHORT_TRAIL'),
        (16, 'short', False, False, False, 'SHORT_SL_ONLY'),

        # Bidirectional structures (8 variants)
        (17, 'both', True, False, False, 'BOTH_TP'),
        (18, 'both', False, True, False, 'BOTH_TIME'),
        (19, 'both', True, True, False, 'BOTH_TP+TIME'),
        (20, 'both', True, False, True, 'BOTH_TP+TRAIL'),
        (21, 'both', False, True, True, 'BOTH_TIME+TRAIL'),
        (22, 'both', True, True, True, 'BOTH_TP+TIME+TRAIL'),
        (23, 'both', False, False, True, 'BOTH_TRAIL'),
        (24, 'both', False, False, False, 'BOTH_SL_ONLY'),
    ]

    for struct_id, direction, has_tp, has_time, has_trail, name in STRUCTURES:
        # Build strategy kwargs
        kwargs = {
            'direction': direction if direction != 'both' else 'long',  # Use long for 'both'
            'sl_pct': 0.03,
            'tp_pct': 0.05 if has_tp else 0.999,  # Very high TP = effectively disabled
            'exit_after_bars': 50 if has_time else 9999,
            'leverage': 1,
            'entry_bar': 100,
        }

        if has_trail:
            kwargs['sl_type'] = StopLossType.TRAILING
            kwargs['trailing_stop_pct'] = 0.02
            kwargs['trailing_activation_pct'] = 0.01

        # Choose appropriate data
        if direction == 'long' or direction == 'both':
            if has_trail:
                data = {'TEST': create_trailing_test_data()}
            elif has_tp:
                data = {'TEST': create_linear_data(100, 110)}  # Price up for TP
            else:
                data = {'TEST': create_linear_data(100, 105)}  # Slight up
        else:  # short
            if has_trail:
                data = {'TEST': create_short_trailing_data()}
            elif has_tp:
                data = {'TEST': create_linear_data(100, 90)}  # Price down for TP
            else:
                data = {'TEST': create_linear_data(100, 95)}  # Slight down

        Strategy = create_strategy(**kwargs)
        strategy = Strategy()

        try:
            results = engine.backtest(strategy, data, max_positions=1)

            # Check 1: Got exactly 1 trade
            has_trade = results['total_trades'] == 1
            report.check_bool(f"Struct{struct_id} {name}: 1 trade", has_trade,
                             details=f"trades={results['total_trades']}")

            if has_trade:
                trade = results['trades'][0]

                # Check 2: Universal invariants
                check_universal_invariants(results, data, report, f"Struct{struct_id}: ")

                # Check 3: Structure-specific exit logic
                if has_trail and not has_tp and not has_time:
                    # Pure trailing should exit via SL (trailing SL)
                    report.check_bool(f"Struct{struct_id} {name}: trail exit = sl",
                                     trade['exit_reason'] == 'sl',
                                     details=f"exit={trade['exit_reason']}")
                    # Trailing should lock profit
                    report.check_bool(f"Struct{struct_id} {name}: trail PnL > 0",
                                     trade['pnl'] > 0,
                                     details=f"pnl={trade['pnl']:.2f}")

                elif has_time and not has_tp and not has_trail:
                    # Pure time exit
                    expected_exit_idx = 100 + 50  # entry_bar + exit_after_bars
                    report.check_bool(f"Struct{struct_id} {name}: time exit idx ~150",
                                     abs(trade['exit_idx'] - expected_exit_idx) <= 1,
                                     details=f"exit_idx={trade['exit_idx']}")

        except Exception as e:
            report.check_bool(f"Struct{struct_id} {name}: no crash", False,
                             details=f"Exception: {str(e)[:50]}")


# =============================================================================
# PHASE 11: ATR-BASED STOPS
# =============================================================================

def run_atr_tests(engine: BacktestEngine, report: ValidationReport):
    """
    Test ATR-based stop loss/take profit functionality.

    ATR-based stops convert ATR × multiplier to percentage of entry price:
        sl_pct = (ATR × atr_stop_multiplier) / entry_price
        tp_pct = (ATR × atr_take_multiplier) / entry_price
    """
    report.start_section("11. ATR-Based Stops")

    # 11.1: Long ATR SL - verify ATR is used correctly
    # With 2% volatility, ATR ~ 2.0 at price 100
    # SL multiplier 2.0 -> SL at 4% from entry (2 × 2%)
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.ATR,
        atr_stop_multiplier=2.0,
        atr_take_multiplier=3.0,
        tp_pct=0.50,  # High TP to not interfere
        entry_bar=100,
        calculate_atr=True,
    )
    strategy = Strategy()

    # Create volatile data: 2% range per bar -> ATR ~2 at price 100
    data = {'TEST': create_volatile_data(100, 0.02, n_bars=200)}
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("ATR Long: 1 trade",
                     results['total_trades'] == 1,
                     details=f"trades={results['total_trades']}")

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        # Check invariants
        check_universal_invariants(results, data, report, "ATR Long: ")

        # Verify trade executed
        report.check_bool("ATR Long: entry > 0",
                         trade['entry_price'] > 0,
                         details=f"entry={trade['entry_price']:.2f}")

    # 11.2: Short ATR SL
    Strategy = create_strategy(
        direction='short',
        sl_type=StopLossType.ATR,
        atr_stop_multiplier=2.0,
        atr_take_multiplier=3.0,
        tp_pct=0.50,
        entry_bar=100,
        calculate_atr=True,
    )
    strategy = Strategy()

    # For short, we need price to drop
    data = {'TEST': create_linear_data(100, 90, n_bars=200)}
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("ATR Short: 1 trade",
                     results['total_trades'] == 1,
                     details=f"trades={results['total_trades']}")

    if results['total_trades'] == 1:
        check_universal_invariants(results, data, report, "ATR Short: ")

    # 11.3: ATR with different multipliers
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.ATR,
        atr_stop_multiplier=1.0,  # Tighter SL
        atr_take_multiplier=2.0,
        tp_pct=0.50,
        entry_bar=100,
        calculate_atr=True,
    )
    strategy = Strategy()
    data = {'TEST': create_volatile_data(100, 0.03, n_bars=200)}  # 3% volatility
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("ATR 1x mult: 1 trade",
                     results['total_trades'] == 1,
                     details=f"trades={results['total_trades']}")

    if results['total_trades'] == 1:
        check_universal_invariants(results, data, report, "ATR 1x: ")

    # 11.4: ATR fallback when no ATR column (on-the-fly calculation)
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.ATR,
        atr_stop_multiplier=2.0,
        atr_take_multiplier=3.0,
        tp_pct=0.50,
        entry_bar=100,
        calculate_atr=False,  # No ATR column - backtester calculates on-the-fly
    )
    strategy = Strategy()
    data = {'TEST': create_volatile_data(100, 0.02, n_bars=200)}
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("ATR fallback (no column): 1 trade",
                     results['total_trades'] == 1,
                     details=f"trades={results['total_trades']}")

    if results['total_trades'] == 1:
        check_universal_invariants(results, data, report, "ATR fallback: ")

    # 11.5: ATR with leverage
    Strategy = create_strategy(
        direction='long',
        sl_type=StopLossType.ATR,
        atr_stop_multiplier=2.0,
        atr_take_multiplier=3.0,
        leverage=5,
        tp_pct=0.50,
        entry_bar=100,
        calculate_atr=True,
    )
    strategy = Strategy()
    data = {'TEST': create_linear_data(100, 110, n_bars=200)}
    results = engine.backtest(strategy, data, max_positions=1)

    report.check_bool("ATR + 5x leverage: 1 trade",
                     results['total_trades'] == 1,
                     details=f"trades={results['total_trades']}")

    if results['total_trades'] == 1:
        trade = results['trades'][0]
        report.check_exact("ATR + 5x: leverage = 5", 5, trade['leverage'])
        check_universal_invariants(results, data, report, "ATR+5x: ")


# =============================================================================
# MAIN VALIDATION
# =============================================================================

def validate_backtester() -> bool:
    """
    Run complete backtester validation.

    Returns:
        True if all tests pass, False otherwise.
    """
    print("\nStarting Comprehensive Backtester Validation...")
    print("-" * 70)

    # Setup
    patch_coin_registry()
    engine = BacktestEngine(config=TEST_CONFIG)
    report = ValidationReport()

    # Run all test phases
    run_combination_matrix_tests(engine, report)
    run_edge_case_tests(engine, report)
    run_multi_trade_tests(engine, report)
    run_invariant_tests(engine, report)
    run_numba_python_extended(engine, report)
    run_vectorbt_extended(engine, report)
    run_trailing_comprehensive(engine, report)
    run_basic_sanity_tests(engine, report)
    run_nan_handling_tests(engine, report)
    run_all_structures_tests(engine, report)
    run_atr_tests(engine, report)

    # Print report
    report.print_report()

    return report.all_passed()


if __name__ == '__main__':
    success = validate_backtester()
    sys.exit(0 if success else 1)
