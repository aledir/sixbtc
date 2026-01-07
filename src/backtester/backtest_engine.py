"""
Backtesting Engine

Backtests StrategyCore instances with realistic portfolio simulation.
Uses Numba JIT compilation for high-performance simulation loops.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import math
import time

from numba import jit, prange
from numba.typed import List as NumbaList

from src.strategies.base import StrategyCore, Signal, StopLossType, TakeProfitType, ExitType
from src.utils.logger import get_logger
from src.config.loader import load_config
from src.executor.risk_manager import RiskManager
from src.data.coin_registry import get_registry, CoinNotFoundError

logger = get_logger(__name__)


# =============================================================================
# NUMBA JIT-COMPILED SIMULATION KERNEL
# =============================================================================

@jit(nopython=True, cache=True)
def _simulate_portfolio_numba(
    close_2d: np.ndarray,           # (n_bars, n_symbols) float64
    high_2d: np.ndarray,            # (n_bars, n_symbols) float64
    low_2d: np.ndarray,             # (n_bars, n_symbols) float64
    entries_2d: np.ndarray,         # (n_bars, n_symbols) bool
    exits_2d: np.ndarray,           # (n_bars, n_symbols) bool
    sizes_2d: np.ndarray,           # (n_bars, n_symbols) float64 - position size as % of equity
    sl_pcts_2d: np.ndarray,         # (n_bars, n_symbols) float64
    tp_pcts_2d: np.ndarray,         # (n_bars, n_symbols) float64
    directions_2d: np.ndarray,      # (n_bars, n_symbols) int8: 1=long, -1=short, 0=none
    leverages_2d: np.ndarray,       # (n_bars, n_symbols) int32
    max_leverages: np.ndarray,      # (n_symbols,) int32 - per-coin max leverage
    trailing_flags_2d: np.ndarray,  # (n_bars, n_symbols) bool - is trailing SL
    trailing_pcts_2d: np.ndarray,   # (n_bars, n_symbols) float64 - trailing stop %
    trailing_act_2d: np.ndarray,    # (n_bars, n_symbols) float64 - activation %
    time_exit_flags_2d: np.ndarray, # (n_bars, n_symbols) bool - has time-based exit
    exit_after_bars_2d: np.ndarray, # (n_bars, n_symbols) int32 - bars until exit
    max_positions: int,
    initial_capital: float,
    fee_rate: float,
    slippage: float
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray,
           np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """
    Numba-optimized portfolio simulation loop.

    This is the hot path - runs 20-50x faster than pure Python.

    Returns:
        equity_curve: (n_bars+1,) float64
        trade_symbol_idx: (max_trades,) int64 - symbol index for each trade
        trade_entry_idx: (max_trades,) int64
        trade_exit_idx: (max_trades,) int64
        trade_entry_price: (max_trades,) float64
        trade_exit_price: (max_trades,) float64
        trade_pnl: (max_trades,) float64
        trade_direction: (max_trades,) int8
        trade_leverage: (max_trades,) int32
        trade_exit_reason: (max_trades,) int8 - 0=sl, 1=tp, 2=signal, 3=time, 4=end
        n_trades: int - actual number of trades
    """
    n_bars, n_symbols = close_2d.shape

    # Position state arrays (per symbol)
    # -1 means no position, otherwise it's the entry bar index
    pos_entry_idx = np.full(n_symbols, -1, dtype=np.int64)
    pos_entry_price = np.zeros(n_symbols, dtype=np.float64)
    pos_size = np.zeros(n_symbols, dtype=np.float64)
    pos_margin = np.zeros(n_symbols, dtype=np.float64)
    pos_leverage = np.zeros(n_symbols, dtype=np.int32)
    pos_sl = np.zeros(n_symbols, dtype=np.float64)
    pos_tp = np.zeros(n_symbols, dtype=np.float64)
    pos_direction = np.zeros(n_symbols, dtype=np.int8)

    # Trailing stop state
    pos_trailing = np.zeros(n_symbols, dtype=np.bool_)
    pos_trailing_pct = np.zeros(n_symbols, dtype=np.float64)
    pos_trailing_act_pct = np.zeros(n_symbols, dtype=np.float64)
    pos_trailing_active = np.zeros(n_symbols, dtype=np.bool_)
    pos_high_water = np.zeros(n_symbols, dtype=np.float64)

    # Time-based exit state
    pos_time_exit = np.zeros(n_symbols, dtype=np.bool_)
    pos_exit_after_bars = np.zeros(n_symbols, dtype=np.int32)

    # Output arrays - pre-allocate for max possible trades
    max_trades = n_bars * n_symbols  # Upper bound
    trade_symbol_idx = np.zeros(max_trades, dtype=np.int64)
    trade_entry_idx = np.zeros(max_trades, dtype=np.int64)
    trade_exit_idx = np.zeros(max_trades, dtype=np.int64)
    trade_entry_price = np.zeros(max_trades, dtype=np.float64)
    trade_exit_price = np.zeros(max_trades, dtype=np.float64)
    trade_pnl = np.zeros(max_trades, dtype=np.float64)
    trade_direction = np.zeros(max_trades, dtype=np.int8)
    trade_leverage = np.zeros(max_trades, dtype=np.int32)
    trade_exit_reason = np.zeros(max_trades, dtype=np.int8)
    n_trades = 0

    # Equity tracking
    equity = initial_capital
    equity_curve = np.zeros(n_bars + 1, dtype=np.float64)
    equity_curve[0] = equity

    # Main simulation loop
    for i in range(n_bars):
        # Count open positions
        n_open = 0
        for j in range(n_symbols):
            if pos_entry_idx[j] >= 0:
                n_open += 1

        # 1. Update trailing stops BEFORE checking exits
        for j in range(n_symbols):
            if pos_entry_idx[j] < 0 or not pos_trailing[j]:
                continue

            current_high = high_2d[i, j]
            current_price = close_2d[i, j]
            direction = pos_direction[j]

            # Check activation
            if not pos_trailing_active[j]:
                if direction == 1:  # long
                    profit_pct = (current_price - pos_entry_price[j]) / pos_entry_price[j]
                else:  # short
                    profit_pct = (pos_entry_price[j] - current_price) / pos_entry_price[j]

                if profit_pct >= pos_trailing_act_pct[j]:
                    pos_trailing_active[j] = True
                    if direction == 1:
                        pos_high_water[j] = current_high
                    else:
                        pos_high_water[j] = current_price
                continue

            # Update trailing SL
            if direction == 1:  # long
                if current_high > pos_high_water[j]:
                    pos_high_water[j] = current_high
                new_sl = pos_high_water[j] * (1.0 - pos_trailing_pct[j])
                if new_sl > pos_sl[j]:
                    pos_sl[j] = new_sl
            else:  # short
                if current_price < pos_high_water[j]:
                    pos_high_water[j] = current_price
                new_sl = pos_high_water[j] * (1.0 + pos_trailing_pct[j])
                if new_sl < pos_sl[j]:
                    pos_sl[j] = new_sl

        # 2. Check exits for open positions
        for j in range(n_symbols):
            if pos_entry_idx[j] < 0:
                continue

            current_price = close_2d[i, j]
            current_high = high_2d[i, j]
            current_low = low_2d[i, j]
            direction = pos_direction[j]
            should_close = False
            exit_price = current_price
            exit_reason = 0  # 0=sl, 1=tp, 2=signal, 3=time

            # Check TIME_BASED exit first
            if pos_time_exit[j]:
                bars_held = i - pos_entry_idx[j]
                if bars_held >= pos_exit_after_bars[j]:
                    should_close = True
                    exit_reason = 3  # time

            # Check stop loss using LOW for longs, HIGH for shorts
            # This correctly detects intrabar SL hits
            if not should_close:
                if direction == 1 and current_low <= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]
                    exit_reason = 0  # sl
                elif direction == -1 and current_high >= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]
                    exit_reason = 0  # sl

            # Check take profit using HIGH for longs, LOW for shorts
            # This correctly detects intrabar TP hits (critical for pattern-based strategies)
            if not should_close and pos_tp[j] > 0:
                if direction == 1 and current_high >= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]
                    exit_reason = 1  # tp
                elif direction == -1 and current_low <= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]
                    exit_reason = 1  # tp

            # Check exit signal
            if not should_close and exits_2d[i, j]:
                should_close = True
                exit_reason = 2  # signal

            if should_close:
                # Apply slippage
                if direction == 1:
                    slipped_exit = exit_price * (1.0 - slippage)
                    pnl = (slipped_exit - pos_entry_price[j]) * pos_size[j]
                else:
                    slipped_exit = exit_price * (1.0 + slippage)
                    pnl = (pos_entry_price[j] - slipped_exit) * pos_size[j]

                # Apply fees
                notional = pos_entry_price[j] * pos_size[j]
                fees = notional * fee_rate * 2.0
                pnl -= fees

                equity += pnl

                # Record trade
                trade_symbol_idx[n_trades] = j
                trade_entry_idx[n_trades] = pos_entry_idx[j]
                trade_exit_idx[n_trades] = i
                trade_entry_price[n_trades] = pos_entry_price[j]
                trade_exit_price[n_trades] = slipped_exit
                trade_pnl[n_trades] = pnl
                trade_direction[n_trades] = direction
                trade_leverage[n_trades] = pos_leverage[j]
                trade_exit_reason[n_trades] = exit_reason
                n_trades += 1

                # Clear position
                pos_entry_idx[j] = -1
                n_open -= 1

        # 3. Check for new entries (if slots available)
        if n_open < max_positions:
            for j in range(n_symbols):
                if n_open >= max_positions:
                    break
                if pos_entry_idx[j] >= 0:
                    continue  # Already have position
                if not entries_2d[i, j]:
                    continue  # No entry signal

                direction = directions_2d[i, j]
                if direction == 0:
                    continue

                price = close_2d[i, j]

                # Apply slippage to entry
                if direction == 1:
                    slipped_entry = price * (1.0 + slippage)
                else:
                    slipped_entry = price * (1.0 - slippage)

                # Calculate leverage (min of signal leverage and coin max)
                target_lev = leverages_2d[i, j]
                coin_max_lev = max_leverages[j]
                actual_lev = min(target_lev, coin_max_lev)
                if actual_lev < 1:
                    actual_lev = 1

                # Calculate position size
                size_pct = sizes_2d[i, j]
                margin = equity * size_pct
                notional = margin * actual_lev
                size = notional / slipped_entry

                # Calculate SL/TP prices
                sl_pct = sl_pcts_2d[i, j]
                tp_pct = tp_pcts_2d[i, j]

                if direction == 1:
                    sl_price = slipped_entry * (1.0 - sl_pct)
                    tp_price = slipped_entry * (1.0 + tp_pct) if tp_pct > 0 else 0.0
                else:
                    sl_price = slipped_entry * (1.0 + sl_pct)
                    tp_price = slipped_entry * (1.0 - tp_pct) if tp_pct > 0 else 0.0

                # Store position
                pos_entry_idx[j] = i
                pos_entry_price[j] = slipped_entry
                pos_size[j] = size
                pos_margin[j] = margin
                pos_leverage[j] = actual_lev
                pos_sl[j] = sl_price
                pos_tp[j] = tp_price
                pos_direction[j] = direction

                # Trailing stop
                pos_trailing[j] = trailing_flags_2d[i, j]
                pos_trailing_pct[j] = trailing_pcts_2d[i, j]
                pos_trailing_act_pct[j] = trailing_act_2d[i, j]
                pos_trailing_active[j] = False
                pos_high_water[j] = price

                # Time-based exit
                pos_time_exit[j] = time_exit_flags_2d[i, j]
                pos_exit_after_bars[j] = exit_after_bars_2d[i, j]

                n_open += 1

        equity_curve[i + 1] = equity

    # Close remaining positions at end
    for j in range(n_symbols):
        if pos_entry_idx[j] < 0:
            continue

        exit_price = close_2d[n_bars - 1, j]
        direction = pos_direction[j]

        if direction == 1:
            slipped_exit = exit_price * (1.0 - slippage)
            pnl = (slipped_exit - pos_entry_price[j]) * pos_size[j]
        else:
            slipped_exit = exit_price * (1.0 + slippage)
            pnl = (pos_entry_price[j] - slipped_exit) * pos_size[j]

        notional = pos_entry_price[j] * pos_size[j]
        fees = notional * fee_rate * 2.0
        pnl -= fees

        equity += pnl

        trade_symbol_idx[n_trades] = j
        trade_entry_idx[n_trades] = pos_entry_idx[j]
        trade_exit_idx[n_trades] = n_bars - 1
        trade_entry_price[n_trades] = pos_entry_price[j]
        trade_exit_price[n_trades] = slipped_exit
        trade_pnl[n_trades] = pnl
        trade_direction[n_trades] = direction
        trade_leverage[n_trades] = pos_leverage[j]
        trade_exit_reason[n_trades] = 4  # end
        n_trades += 1

    # Update final equity
    equity_curve[n_bars] = equity

    return (equity_curve, trade_symbol_idx, trade_entry_idx, trade_exit_idx,
            trade_entry_price, trade_exit_price, trade_pnl, trade_direction,
            trade_leverage, trade_exit_reason, n_trades)


def sanitize_float(value: float, default: float = 0.0) -> float:
    """
    Sanitize float values for JSON storage.
    Replaces Infinity and NaN with default value.
    """
    if value is None or math.isnan(value) or math.isinf(value):
        return default
    return float(value)


class BacktestEngine:
    """
    Backtesting engine for StrategyCore strategies

    Executes strategies on historical data with realistic portfolio simulation
    and calculates comprehensive performance metrics.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize backtester

        Args:
            config: Configuration dict (if None, loads from file)
        """
        self.config = config or load_config()

        # Extract config values - handle both Config object and raw dict
        if hasattr(self.config, '_raw_config'):
            # Config object - use dot notation
            self.fee_rate = self.config.get('hyperliquid.fee_rate')
            self.slippage = self.config.get('hyperliquid.slippage')
            self.initial_capital = self.config.get('backtesting.initial_capital')
            risk_config = self.config._raw_config
        else:
            # Raw dict - navigate manually
            self.fee_rate = self.config.get('hyperliquid', {}).get('fee_rate', 0.0004)
            self.slippage = self.config.get('hyperliquid', {}).get('slippage', 0.0002)
            self.initial_capital = self.config.get('backtesting', {}).get('initial_capital', 10000)
            risk_config = self.config

        # Use the same RiskManager as live executor for consistency
        # This ensures backtest results match live trading behavior
        self.risk_manager = RiskManager(risk_config)

        # Cache for coin max leverage (avoid repeated DB queries)
        self._coin_max_leverage_cache: Dict[str, int] = {}

    def _get_coin_max_leverage(self, symbol: str) -> int:
        """
        Get max leverage for a coin from CoinRegistry (with local caching).

        Args:
            symbol: Coin symbol (e.g., 'BTC', 'ETH')

        Returns:
            Max leverage from registry

        Raises:
            ValueError: If coin not found in registry
        """
        if symbol in self._coin_max_leverage_cache:
            return self._coin_max_leverage_cache[symbol]

        try:
            max_leverage = get_registry().get_max_leverage(symbol)
            self._coin_max_leverage_cache[symbol] = max_leverage
            return max_leverage
        except CoinNotFoundError:
            raise ValueError(
                f"Coin {symbol} not found in CoinRegistry - cannot determine max_leverage. "
                "Run pairs_updater to sync coins from Hyperliquid."
            )

    def backtest(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame],
        max_positions: Optional[int] = None,
        timeframe: Optional[str] = None
    ) -> Dict:
        """
        Portfolio backtest with realistic position limits

        This is the PRIMARY method for multi-symbol backtesting.
        Simulates real trading constraints:
        - Maximum concurrent positions (from config: risk.limits.max_open_positions_per_subaccount)
        - Shared capital pool across all symbols
        - Position priority based on signal order
        - Slippage and fees applied to each trade

        This ensures backtest results match live trading behavior.

        Args:
            strategy: StrategyCore instance
            data: Dict mapping symbol → OHLCV DataFrame
            max_positions: Maximum concurrent open positions (default from config)
            timeframe: Timeframe string ('15m', '1h', '4h', '1d') for correct Sharpe annualization

        Returns:
            Portfolio-level metrics with position-limited simulation
        """
        # Get max_positions from config if not provided
        if max_positions is None:
            # Handle both Config object (with dot notation) and raw dict
            if hasattr(self.config, '_raw_config'):
                max_positions = self.config.get('risk.limits.max_open_positions_per_subaccount')
            else:
                # Raw dict - navigate manually
                max_positions = self.config.get('risk', {}).get('limits', {}).get('max_open_positions_per_subaccount')

            # Must have a value for Numba (doesn't accept None)
            if max_positions is None:
                max_positions = 10

        strategy_name = strategy.__class__.__name__
        logger.info(
            f"[{strategy_name}] Running portfolio backtest "
            f"({len(data)} symbols, max_positions={max_positions})"
        )

        # Profiling timers
        _t_start = time.perf_counter()
        _t_align = 0.0
        _t_signals = 0.0
        _t_simulation = 0.0

        # Align all dataframes to common timestamp index
        _t0 = time.perf_counter()
        aligned_data = self._align_dataframes(data)
        _t_align = time.perf_counter() - _t0

        if aligned_data is None:
            return self._empty_results()

        common_index = aligned_data['_index']
        symbols = [s for s in aligned_data.keys() if s != '_index']

        # Track state across time
        open_positions = {}  # symbol -> {entry_price, entry_idx, size, sl, tp}
        closed_trades = []
        equity = self.initial_capital
        equity_curve = [equity]

        # Generate signals for all symbols upfront (parallelized by symbol)
        _t0 = time.perf_counter()
        all_signals = {}

        def process_symbol(symbol):
            df = aligned_data[symbol]
            entries, exits, sizes, sl_pcts, tp_pcts, signal_meta = self._generate_signals_fast(
                strategy, df, symbol
            )
            return symbol, {
                'entries': entries,
                'exits': exits,
                'sizes': sizes,
                'sl_pcts': sl_pcts,
                'tp_pcts': tp_pcts,
                'close': df['close'],
                'high': df['high'],
                'low': df['low'],
                'signal_meta': signal_meta,
            }

        # Use ThreadPoolExecutor for parallel signal generation
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(symbols), 8)) as executor:
            results = list(executor.map(process_symbol, symbols))

        for symbol, signals_dict in results:
            all_signals[symbol] = signals_dict

        _t_signals = time.perf_counter() - _t0

        # Prepare 2D arrays for Numba simulation
        _t0 = time.perf_counter()
        arrays = self._prepare_simulation_arrays(all_signals, symbols, len(common_index))
        _t_prepare = time.perf_counter() - _t0

        # Run Numba-optimized simulation
        _t0 = time.perf_counter()
        (equity_curve_arr, trade_symbol_idx, trade_entry_idx, trade_exit_idx,
         trade_entry_price, trade_exit_price, trade_pnl, trade_direction,
         trade_leverage, trade_exit_reason, n_trades) = _simulate_portfolio_numba(
            arrays['close'],
            arrays['high'],
            arrays['low'],
            arrays['entries'],
            arrays['exits'],
            arrays['sizes'],
            arrays['sl_pcts'],
            arrays['tp_pcts'],
            arrays['directions'],
            arrays['leverages'],
            arrays['max_leverages'],
            arrays['trailing_flags'],
            arrays['trailing_pcts'],
            arrays['trailing_act'],
            arrays['time_exit_flags'],
            arrays['exit_after_bars'],
            max_positions,
            self.initial_capital,
            self.fee_rate,
            self.slippage
        )
        _t_simulation = time.perf_counter() - _t0

        # Convert trade arrays back to list of dicts
        closed_trades = self._trades_from_arrays(
            symbols, n_trades,
            trade_symbol_idx, trade_entry_idx, trade_exit_idx,
            trade_entry_price, trade_exit_price, trade_pnl,
            trade_direction, trade_leverage, trade_exit_reason,
            arrays['sizes'], arrays['leverages']
        )

        equity_curve = equity_curve_arr.tolist()

        # Calculate metrics
        metrics = self._calculate_portfolio_metrics(
            closed_trades,
            equity_curve,
            self.initial_capital,
            timeframe=timeframe
        )
        metrics['max_positions_used'] = max_positions
        metrics['symbols_count'] = len(symbols)

        # Log profiling results
        _t_total = time.perf_counter() - _t_start
        logger.info(
            f"[{strategy_name}] Backtest complete: {len(closed_trades)} trades, {len(symbols)} symbols, "
            f"{len(common_index)} bars | "
            f"Time: {_t_total:.2f}s (align={_t_align:.2f}s, signals={_t_signals:.2f}s, "
            f"prepare={_t_prepare:.3f}s, sim={_t_simulation:.3f}s)"
        )

        return metrics

    def _prepare_simulation_arrays(
        self,
        all_signals: Dict,
        symbols: List[str],
        n_bars: int
    ) -> Dict[str, np.ndarray]:
        """
        Convert signal dicts to 2D NumPy arrays for Numba.

        Args:
            all_signals: Dict of signal data per symbol
            symbols: List of symbol names (defines column order)
            n_bars: Number of bars in simulation

        Returns:
            Dict of 2D arrays ready for Numba simulation
        """
        n_symbols = len(symbols)

        # Initialize arrays
        close_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        high_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        low_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        entries_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        exits_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        sizes_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        sl_pcts_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        tp_pcts_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        directions_2d = np.zeros((n_bars, n_symbols), dtype=np.int8)
        leverages_2d = np.zeros((n_bars, n_symbols), dtype=np.int32)
        max_leverages = np.zeros(n_symbols, dtype=np.int32)
        trailing_flags_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        trailing_pcts_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        trailing_act_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        time_exit_flags_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        exit_after_bars_2d = np.zeros((n_bars, n_symbols), dtype=np.int32)

        for j, symbol in enumerate(symbols):
            sig = all_signals[symbol]

            # Price data
            close_2d[:, j] = sig['close'].values
            high_2d[:, j] = sig['high'].values
            low_2d[:, j] = sig['low'].values

            # Signals
            entries_2d[:, j] = sig['entries'].values
            exits_2d[:, j] = sig['exits'].values
            sizes_2d[:, j] = np.nan_to_num(sig['sizes'].values, nan=0.0)
            sl_pcts_2d[:, j] = np.nan_to_num(sig['sl_pcts'].values, nan=0.02)
            tp_pcts_2d[:, j] = np.nan_to_num(sig['tp_pcts'].values, nan=0.0)

            # Max leverage for this coin
            max_leverages[j] = self._get_coin_max_leverage(symbol)

            # Process signal metadata
            signal_meta = sig['signal_meta']
            for bar_idx, meta in signal_meta.items():
                # Direction
                direction = meta.get('direction', 'long')
                if direction == 'long':
                    directions_2d[bar_idx, j] = 1
                elif direction == 'short':
                    directions_2d[bar_idx, j] = -1

                # Leverage
                leverages_2d[bar_idx, j] = meta.get('leverage', 1)

                # Trailing stop
                if meta.get('sl_type') == StopLossType.TRAILING:
                    trailing_flags_2d[bar_idx, j] = True
                    trailing_pcts_2d[bar_idx, j] = meta.get('trailing_stop_pct', 0.02)
                    trailing_act_2d[bar_idx, j] = meta.get('trailing_activation_pct', 0.01)

                # Time-based exit
                if meta.get('exit_type') == ExitType.TIME_BASED:
                    time_exit_flags_2d[bar_idx, j] = True
                    exit_after_bars_2d[bar_idx, j] = meta.get('exit_after_bars', 20)

        return {
            'close': close_2d,
            'high': high_2d,
            'low': low_2d,
            'entries': entries_2d,
            'exits': exits_2d,
            'sizes': sizes_2d,
            'sl_pcts': sl_pcts_2d,
            'tp_pcts': tp_pcts_2d,
            'directions': directions_2d,
            'leverages': leverages_2d,
            'max_leverages': max_leverages,
            'trailing_flags': trailing_flags_2d,
            'trailing_pcts': trailing_pcts_2d,
            'trailing_act': trailing_act_2d,
            'time_exit_flags': time_exit_flags_2d,
            'exit_after_bars': exit_after_bars_2d,
        }

    def _trades_from_arrays(
        self,
        symbols: List[str],
        n_trades: int,
        trade_symbol_idx: np.ndarray,
        trade_entry_idx: np.ndarray,
        trade_exit_idx: np.ndarray,
        trade_entry_price: np.ndarray,
        trade_exit_price: np.ndarray,
        trade_pnl: np.ndarray,
        trade_direction: np.ndarray,
        trade_leverage: np.ndarray,
        trade_exit_reason: np.ndarray,
        sizes_2d: np.ndarray,
        leverages_2d: np.ndarray
    ) -> List[Dict]:
        """
        Convert Numba output arrays back to list of trade dicts.

        Args:
            symbols: List of symbol names
            n_trades: Number of actual trades
            trade_*: Arrays from Numba simulation

        Returns:
            List of trade dicts compatible with _calculate_portfolio_metrics
        """
        exit_reason_map = {0: 'sl', 1: 'tp', 2: 'signal', 3: 'time_exit', 4: 'end'}
        direction_map = {1: 'long', -1: 'short'}

        trades = []
        for i in range(n_trades):
            symbol_idx = int(trade_symbol_idx[i])
            entry_idx = int(trade_entry_idx[i])
            symbol = symbols[symbol_idx]
            direction = direction_map.get(int(trade_direction[i]), 'long')
            leverage = int(trade_leverage[i])
            entry_price = float(trade_entry_price[i])
            exit_price = float(trade_exit_price[i])
            pnl = float(trade_pnl[i])

            # Calculate size and margin from entry data
            size_pct = sizes_2d[entry_idx, symbol_idx]
            # Approximate margin (was equity * size_pct at entry time)
            # We use initial_capital as approximation since we don't track per-trade equity
            margin = self.initial_capital * size_pct
            notional = margin * leverage
            size = notional / entry_price

            trades.append({
                'symbol': symbol,
                'entry_idx': entry_idx,
                'exit_idx': int(trade_exit_idx[i]),
                'entry_price': entry_price,
                'exit_price': exit_price,
                'size': size,
                'margin': margin,
                'leverage': leverage,
                'notional': notional,
                'pnl': pnl,
                'return_on_margin': pnl / margin if margin > 0 else 0,
                'fees': notional * self.fee_rate * 2,
                'exit_reason': exit_reason_map.get(int(trade_exit_reason[i]), 'unknown'),
                'direction': direction,
            })

        return trades

    def backtest_python(
        self,
        strategy: StrategyCore,
        data: Dict[str, pd.DataFrame],
        max_positions: Optional[int] = None
    ) -> Dict:
        """
        Original Python implementation of backtest (kept for reference/debugging).

        Use backtest() for production - it uses Numba and is 20-50x faster.
        """
        # Get max_positions from config if not provided
        if max_positions is None:
            # Handle both Config object (with dot notation) and raw dict
            if hasattr(self.config, '_raw_config'):
                max_positions = self.config.get('risk.limits.max_open_positions_per_subaccount')
            else:
                # Raw dict - navigate manually
                max_positions = self.config.get('risk', {}).get('limits', {}).get('max_open_positions_per_subaccount')

            # Must have a value for simulation
            if max_positions is None:
                max_positions = 10

        strategy_name = strategy.__class__.__name__
        logger.info(
            f"[{strategy_name}] Running Python portfolio backtest "
            f"({len(data)} symbols, max_positions={max_positions})"
        )

        # Profiling timers
        _t_start = time.perf_counter()
        _t_align = 0.0
        _t_signals = 0.0
        _t_simulation = 0.0

        # Align all dataframes to common timestamp index
        _t0 = time.perf_counter()
        aligned_data = self._align_dataframes(data)
        _t_align = time.perf_counter() - _t0

        if aligned_data is None:
            return self._empty_results()

        common_index = aligned_data['_index']
        symbols = [s for s in aligned_data.keys() if s != '_index']

        # Track state across time
        open_positions = {}  # symbol -> {entry_price, entry_idx, size, sl, tp}
        closed_trades = []
        equity = self.initial_capital
        equity_curve = [equity]

        # Generate signals for all symbols upfront
        _t0 = time.perf_counter()
        all_signals = {}
        for symbol in symbols:
            df = aligned_data[symbol]
            entries, exits, sizes, sl_pcts, tp_pcts, signal_meta = self._generate_signals_fast(
                strategy, df, symbol
            )
            all_signals[symbol] = {
                'entries': entries,
                'exits': exits,
                'sizes': sizes,
                'sl_pcts': sl_pcts,
                'tp_pcts': tp_pcts,
                'close': df['close'],
                'high': df['high'],
                'low': df['low'],
                'signal_meta': signal_meta,
            }
        _t_signals = time.perf_counter() - _t0

        # Simulate bar by bar (original Python loop)
        _t0 = time.perf_counter()
        for i, timestamp in enumerate(common_index):
            # 1. Update trailing stops for open positions BEFORE checking exits
            for symbol, pos in open_positions.items():
                if not pos.get('trailing_sl'):
                    continue

                sig = all_signals[symbol]
                current_high = sig['high'].iloc[i]
                current_price = sig['close'].iloc[i]
                direction = pos.get('direction', 'long')

                # Check activation (must be in profit by activation_pct)
                if not pos.get('trailing_active', False):
                    activation_pct = pos.get('trailing_activation_pct', 0.01)
                    if direction == 'long':
                        profit_pct = (current_price - pos['entry_price']) / pos['entry_price']
                    else:
                        profit_pct = (pos['entry_price'] - current_price) / pos['entry_price']

                    if profit_pct >= activation_pct:
                        pos['trailing_active'] = True
                        pos['high_water_mark'] = current_high if direction == 'long' else current_price
                    continue  # Don't update SL until activated

                # Update high water mark
                if direction == 'long':
                    if current_high > pos.get('high_water_mark', 0):
                        pos['high_water_mark'] = current_high
                    # Calculate new trailing SL from high water mark
                    trail_pct = pos.get('trailing_stop_pct', 0.02)
                    new_sl = pos['high_water_mark'] * (1 - trail_pct)
                    # Only move SL up, never down
                    if new_sl > pos['sl']:
                        pos['sl'] = new_sl
                else:  # short
                    if current_price < pos.get('high_water_mark', float('inf')):
                        pos['high_water_mark'] = current_price
                    trail_pct = pos.get('trailing_stop_pct', 0.02)
                    new_sl = pos['high_water_mark'] * (1 + trail_pct)
                    if new_sl < pos['sl']:
                        pos['sl'] = new_sl

            # 2. Check exits for open positions (SL/TP/signal/time)
            positions_to_close = []
            for symbol, pos in open_positions.items():
                sig = all_signals[symbol]
                current_price = sig['close'].iloc[i]
                current_high = sig['high'].iloc[i]
                current_low = sig['low'].iloc[i]
                direction = pos.get('direction', 'long')

                # Check TIME_BASED exit first
                if pos.get('exit_after_bars') is not None:
                    bars_held = i - pos['entry_idx']
                    if bars_held >= pos['exit_after_bars']:
                        if direction == 'long':
                            pnl = (current_price - pos['entry_price']) * pos['size']
                        else:
                            pnl = (pos['entry_price'] - current_price) * pos['size']
                        positions_to_close.append((symbol, current_price, 'time_exit', pnl))
                        continue

                # Check stop loss using LOW for longs, HIGH for shorts
                # This correctly detects intrabar SL hits
                if direction == 'long':
                    if current_low <= pos['sl']:
                        pnl = (pos['sl'] - pos['entry_price']) * pos['size']
                        positions_to_close.append((symbol, pos['sl'], 'sl', pnl))
                        continue
                else:  # short
                    if current_high >= pos['sl']:
                        pnl = (pos['entry_price'] - pos['sl']) * pos['size']
                        positions_to_close.append((symbol, pos['sl'], 'sl', pnl))
                        continue

                # Check take profit using HIGH for longs, LOW for shorts
                # This correctly detects intrabar TP hits (critical for pattern-based strategies)
                if pos['tp'] is not None:
                    if direction == 'long' and current_high >= pos['tp']:
                        pnl = (pos['tp'] - pos['entry_price']) * pos['size']
                        positions_to_close.append((symbol, pos['tp'], 'tp', pnl))
                        continue
                    elif direction == 'short' and current_low <= pos['tp']:
                        pnl = (pos['entry_price'] - pos['tp']) * pos['size']
                        positions_to_close.append((symbol, pos['tp'], 'tp', pnl))
                        continue

                # Check exit signal
                if sig['exits'].iloc[i]:
                    if direction == 'long':
                        pnl = (current_price - pos['entry_price']) * pos['size']
                    else:
                        pnl = (pos['entry_price'] - current_price) * pos['size']
                    positions_to_close.append((symbol, current_price, 'signal', pnl))

            # Close positions (apply slippage + fees)
            for symbol, exit_price, reason, raw_pnl in positions_to_close:
                pos = open_positions.pop(symbol)
                direction = pos.get('direction', 'long')
                leverage = pos.get('leverage', 1)
                margin = pos.get('margin', 0)

                # Apply slippage to exit price (adverse direction)
                if direction == 'long':
                    slipped_exit = exit_price * (1 - self.slippage)
                else:
                    slipped_exit = exit_price * (1 + self.slippage)

                # Recalculate PnL with slippage
                if direction == 'long':
                    pnl = (slipped_exit - pos['entry_price']) * pos['size']
                else:
                    pnl = (pos['entry_price'] - slipped_exit) * pos['size']

                # Apply fees (entry + exit)
                notional = pos['entry_price'] * pos['size']
                fees = notional * self.fee_rate * 2  # Entry + exit
                pnl -= fees

                # Return on margin (leveraged return)
                return_on_margin = pnl / margin if margin > 0 else 0

                equity += pnl
                closed_trades.append({
                    'symbol': symbol,
                    'entry_idx': pos['entry_idx'],
                    'exit_idx': i,
                    'entry_price': pos['entry_price'],
                    'exit_price': slipped_exit,
                    'size': pos['size'],
                    'margin': margin,
                    'leverage': leverage,
                    'notional': notional,
                    'pnl': pnl,
                    'return_on_margin': return_on_margin,
                    'fees': fees,
                    'exit_reason': reason,
                    'direction': direction,
                })

            # 3. Check for new entries (if slots available)
            if len(open_positions) < max_positions:
                available_slots = max_positions - len(open_positions)

                # Collect potential entries
                potential_entries = []
                for symbol in symbols:
                    if symbol in open_positions:
                        continue  # Already have position

                    sig = all_signals[symbol]
                    if sig['entries'].iloc[i]:
                        # Get signal metadata for this bar
                        meta = sig['signal_meta'].get(i, {})
                        potential_entries.append({
                            'symbol': symbol,
                            'price': sig['close'].iloc[i],
                            'size_pct': sig['sizes'].iloc[i],
                            'sl_pct': sig['sl_pcts'].iloc[i],
                            'tp_pct': sig['tp_pcts'].iloc[i] if pd.notna(sig['tp_pcts'].iloc[i]) else None,
                            'meta': meta,
                        })

                # Take first N entries (could add priority logic here)
                for entry in potential_entries[:available_slots]:
                    symbol = entry['symbol']
                    price = entry['price']
                    meta = entry['meta']
                    direction = meta.get('direction', 'long')

                    # Apply slippage to entry price (adverse direction)
                    if direction == 'long':
                        slipped_entry = price * (1 + self.slippage)
                    else:
                        slipped_entry = price * (1 - self.slippage)

                    # Calculate leverage: min(signal leverage, coin max leverage)
                    target_leverage = meta.get('leverage', 1)
                    coin_max_leverage = self._get_coin_max_leverage(symbol)
                    actual_leverage = min(target_leverage, coin_max_leverage)

                    # Calculate position size with leverage
                    # margin = % of equity allocated to this position
                    # notional = margin * leverage (actual exposure)
                    # size = notional / price (in coin units)
                    margin = equity * entry['size_pct']
                    notional = margin * actual_leverage
                    size = notional / slipped_entry

                    # Calculate SL/TP prices (direction-aware, from slipped entry)
                    if direction == 'long':
                        sl_price = slipped_entry * (1 - entry['sl_pct'])
                        tp_price = slipped_entry * (1 + entry['tp_pct']) if entry['tp_pct'] else None
                    else:  # short
                        sl_price = slipped_entry * (1 + entry['sl_pct'])
                        tp_price = slipped_entry * (1 - entry['tp_pct']) if entry['tp_pct'] else None

                    pos_data = {
                        'entry_price': slipped_entry,
                        'entry_idx': i,
                        'size': size,
                        'margin': margin,
                        'leverage': actual_leverage,
                        'sl': sl_price,
                        'tp': tp_price,
                        'direction': direction,
                    }

                    # Add trailing SL metadata if applicable
                    if meta.get('sl_type') == StopLossType.TRAILING:
                        pos_data['trailing_sl'] = True
                        pos_data['trailing_stop_pct'] = meta.get('trailing_stop_pct', 0.02)
                        pos_data['trailing_activation_pct'] = meta.get('trailing_activation_pct', 0.01)
                        pos_data['trailing_active'] = False
                        pos_data['high_water_mark'] = price

                    # Add TIME_BASED exit metadata if applicable
                    if meta.get('exit_type') == ExitType.TIME_BASED:
                        pos_data['exit_after_bars'] = meta.get('exit_after_bars', 20)

                    open_positions[symbol] = pos_data

            equity_curve.append(equity)
        _t_simulation = time.perf_counter() - _t0

        # Close any remaining positions at last price (apply slippage + fees)
        for symbol, pos in list(open_positions.items()):
            sig = all_signals[symbol]
            exit_price = sig['close'].iloc[-1]
            direction = pos.get('direction', 'long')
            leverage = pos.get('leverage', 1)
            margin = pos.get('margin', 0)

            # Apply slippage to exit price
            if direction == 'long':
                slipped_exit = exit_price * (1 - self.slippage)
                pnl = (slipped_exit - pos['entry_price']) * pos['size']
            else:
                slipped_exit = exit_price * (1 + self.slippage)
                pnl = (pos['entry_price'] - slipped_exit) * pos['size']

            # Apply fees
            notional = pos['entry_price'] * pos['size']
            fees = notional * self.fee_rate * 2
            pnl -= fees

            # Return on margin (leveraged return)
            return_on_margin = pnl / margin if margin > 0 else 0

            equity += pnl
            closed_trades.append({
                'symbol': symbol,
                'entry_idx': pos['entry_idx'],
                'exit_idx': len(common_index) - 1,
                'entry_price': pos['entry_price'],
                'exit_price': slipped_exit,
                'size': pos['size'],
                'margin': margin,
                'leverage': leverage,
                'notional': notional,
                'pnl': pnl,
                'return_on_margin': return_on_margin,
                'fees': fees,
                'exit_reason': 'end',
                'direction': direction,
            })

        # Calculate metrics
        metrics = self._calculate_portfolio_metrics(
            closed_trades,
            equity_curve,
            self.initial_capital,
            timeframe=timeframe
        )
        metrics['max_positions_used'] = max_positions
        metrics['symbols_count'] = len(symbols)

        # Log profiling results
        _t_total = time.perf_counter() - _t_start
        logger.info(
            f"[{strategy_name}] Backtest complete: {len(closed_trades)} trades, {len(symbols)} symbols, "
            f"{len(common_index)} bars | "
            f"Time: {_t_total:.2f}s (align={_t_align:.2f}s, signals={_t_signals:.2f}s, sim={_t_simulation:.2f}s)"
        )

        return metrics

    def _align_dataframes(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Align multiple dataframes to common timestamp index

        Returns dict with aligned dataframes plus '_index' key for timestamps
        """
        if not data:
            return None

        # Set timestamp as index for all dataframes
        indexed_data = {}
        for symbol, df in data.items():
            if 'timestamp' in df.columns:
                df_copy = df.set_index('timestamp')
            else:
                df_copy = df.copy()
            indexed_data[symbol] = df_copy

        # Find common index (intersection of all timestamps)
        indices = [set(df.index) for df in indexed_data.values()]
        common_idx = sorted(set.intersection(*indices))

        # Minimum common data points - adaptive for holdout periods
        # 20 bars minimum allows for warmup + some signal generation
        min_common_bars = 20
        if len(common_idx) < min_common_bars:
            logger.warning(f"Insufficient common data points: {len(common_idx)} < {min_common_bars}")
            return None

        # Create aligned dict
        aligned = {'_index': common_idx}
        for symbol, df in indexed_data.items():
            aligned[symbol] = df.loc[common_idx]

        return aligned

    def _calculate_portfolio_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[float],
        initial_capital: float,
        timeframe: Optional[str] = None
    ) -> Dict:
        """
        Calculate metrics from trade list and equity curve

        Args:
            trades: List of trade dicts
            equity_curve: Equity curve (one value per bar)
            initial_capital: Starting capital
            timeframe: Timeframe string ('15m', '1h', etc.) for correct Sharpe annualization
        """
        if not trades:
            return self._empty_results()

        # Basic trade stats
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # PnL stats
        pnls = [t['pnl'] for t in trades]
        total_pnl = sum(pnls)
        avg_pnl = np.mean(pnls)
        total_return = total_pnl / initial_capital

        # Expectancy: (Win% × Avg Win%) - (Loss% × Avg Loss%)
        # Calculate PnL as percentage of trade notional for each trade
        win_pcts = []
        loss_pcts = []
        for t in trades:
            notional = t.get('notional', 0)
            if notional > 0:
                pnl_pct = t['pnl'] / notional
                if t['pnl'] > 0:
                    win_pcts.append(pnl_pct)
                else:
                    loss_pcts.append(abs(pnl_pct))

        avg_win_pct = np.mean(win_pcts) if win_pcts else 0.0
        avg_loss_pct = np.mean(loss_pcts) if loss_pcts else 0.0
        # Sanitize to avoid NaN
        avg_win_pct = float(np.nan_to_num(avg_win_pct, nan=0.0))
        avg_loss_pct = float(np.nan_to_num(avg_loss_pct, nan=0.0))
        # Official expectancy formula
        expectancy = (win_rate * avg_win_pct) - ((1 - win_rate) * avg_loss_pct)

        # Drawdown - protect against division by zero and negative equity
        equity_arr = np.array(equity_curve)
        # Ensure equity never goes below 0 for drawdown calculation
        equity_arr = np.maximum(equity_arr, 0.0)
        running_max = np.maximum.accumulate(equity_arr)
        with np.errstate(divide='ignore', invalid='ignore'):
            # Correct formula: (peak - current) / peak = positive when underwater
            drawdowns = np.where(running_max > 0,
                                 (running_max - equity_arr) / running_max,
                                 0.0)
        # Max drawdown is the maximum value (already positive)
        max_drawdown = np.nanmax(drawdowns)
        # Clamp to [0, 1] range
        max_drawdown = min(max(max_drawdown, 0.0), 1.0)

        # Sharpe ratio - TRADE-BASED calculation (more robust than bar-by-bar)
        # Bar-by-bar Sharpe is inflated when few trades spread across many bars
        # (most bars have return=0, artificially lowering std)
        # Trade-based Sharpe uses actual trade returns and annualizes by trade frequency
        n_bars = len(equity_curve) - 1
        if total_trades >= 3:  # Need at least 3 trades for meaningful Sharpe
            # Calculate trade returns (PnL / margin for leveraged return)
            trade_returns = [t.get('return_on_margin', t['pnl'] / t['margin'])
                            for t in trades if t.get('margin', 0) > 0]

            if len(trade_returns) >= 3:
                trade_returns = np.array(trade_returns)
                mean_trade_return = np.mean(trade_returns)
                std_trade_return = np.std(trade_returns)

                if std_trade_return > 1e-10:
                    # Annualize: estimate trades per year from backtest frequency
                    # trades_per_year = total_trades / (n_bars / bars_per_year)
                    if timeframe:
                        bars_per_year = {
                            '1d': 365, '4h': 2190, '1h': 8760,
                            '30m': 17520, '15m': 35040, '5m': 105120
                        }.get(timeframe, 365)
                    else:
                        bars_per_year = 365

                    backtest_years = n_bars / bars_per_year if bars_per_year > 0 else 1.0
                    trades_per_year = total_trades / backtest_years if backtest_years > 0 else total_trades

                    # Sharpe = mean / std * sqrt(trades_per_year)
                    # Cap annualization factor to avoid inflation
                    # Max sqrt(250) ~= 15.8 (reasonable for daily trading)
                    annualization = np.sqrt(min(trades_per_year, 250))
                    sharpe = mean_trade_return / std_trade_return * annualization
                else:
                    sharpe = 0.0
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        # SANITY CHECK: Sharpe must be consistent with total_return
        # Even with trade-based calculation, extreme losses should have negative Sharpe
        if total_return < -0.5:  # Lost more than 50%
            sharpe = min(sharpe, -abs(total_return) * 2)  # At -100% loss, Sharpe <= -2
        elif total_return < 0 and sharpe > 0:
            sharpe = 0.0

        # Profit factor
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Average leverage used
        leverages = [t.get('leverage', 1) for t in trades]
        avg_leverage = np.mean(leverages) if leverages else 1.0

        return {
            'total_return': sanitize_float(total_return),
            'sharpe_ratio': sanitize_float(sharpe),
            'max_drawdown': sanitize_float(max_drawdown),
            'total_trades': total_trades,
            'win_rate': sanitize_float(win_rate),
            'expectancy': sanitize_float(expectancy),
            'profit_factor': sanitize_float(profit_factor, default=1.0),
            'avg_leverage': sanitize_float(avg_leverage, default=1.0),
            'final_equity': equity_curve[-1] if equity_curve else initial_capital,
            'trades': trades,
        }

    def _generate_signals_fast(
        self,
        strategy: StrategyCore,
        data: pd.DataFrame,
        symbol: str = None
    ) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series, Dict]:
        """
        Generate entry/exit signals from strategy class attributes.

        VECTORIZED: Reads signals from entry_signal column and parameters
        from strategy class attributes. No per-bar Python loops.

        All strategies MUST:
        1. Populate 'entry_signal' column in calculate_indicators()
        2. Have class attributes: direction, sl_pct, tp_pct, leverage, exit_after_bars

        Args:
            strategy: StrategyCore instance
            data: OHLCV DataFrame with high, low, close columns
            symbol: Symbol name for logging

        Returns:
            (entries, exits, sizes, sl_pcts, tp_pcts, signal_meta)
        """
        n = len(data)

        # Initialize output arrays
        entries_arr = np.zeros(n, dtype=bool)
        exits_arr = np.zeros(n, dtype=bool)
        sizes_arr = np.zeros(n, dtype=np.float64)
        sl_pcts_arr = np.full(n, np.nan, dtype=np.float64)
        tp_pcts_arr = np.full(n, np.nan, dtype=np.float64)
        signal_meta = {}

        # PHASE 1: Calculate indicators ONCE on full dataframe
        try:
            df = strategy.calculate_indicators(data)
        except Exception as e:
            logger.error(f"calculate_indicators() failed for {symbol}: {e}")
            raise ValueError(f"Strategy calculate_indicators() failed: {e}")

        # Read strategy class attributes (REQUIRED - no fallbacks)
        signal_column = getattr(strategy, 'signal_column', 'entry_signal')
        direction = getattr(strategy, 'direction', 'long')
        sl_pct = getattr(strategy, 'sl_pct', None)
        tp_pct = getattr(strategy, 'tp_pct', None)
        leverage = getattr(strategy, 'leverage', 1)
        exit_after_bars = getattr(strategy, 'exit_after_bars', 20)

        # Validate signal column exists
        if signal_column not in df.columns:
            raise ValueError(
                f"Strategy must populate '{signal_column}' column in calculate_indicators(). "
                f"Available columns: {list(df.columns)}"
            )

        # Read entry signals as boolean array
        entry_signal = df[signal_column].values.astype(bool)

        # Apply warmup - adaptive to ensure signals are possible
        # For short data (holdout ~30 bars), reduce warmup to leave room for signals
        # Minimum 10 bars after warmup for signal generation
        min_signal_bars = 10
        warmup_bars = min(100, max(20, len(entry_signal) - min_signal_bars))
        if warmup_bars > 0 and warmup_bars < len(entry_signal):
            entry_signal[:warmup_bars] = False

        # Set entries array
        entries_arr = entry_signal

        # Get entry indices for vectorized operations
        entry_indices = np.where(entries_arr)[0]

        # Fill arrays for all entries (same params for all)
        sl_pcts_arr[entry_indices] = sl_pct
        tp_pcts_arr[entry_indices] = tp_pct

        # Position sizing: risk_pct / sl_pct, capped at 1.0
        risk_pct = self.risk_manager.risk_per_trade_pct
        position_size = min(risk_pct / sl_pct, 1.0)
        sizes_arr[entry_indices] = position_size

        # Build metadata dict for all entries (same params)
        base_meta = {
            'direction': direction,
            'sl_type': StopLossType.PERCENTAGE,
            'exit_type': ExitType.TIME_BASED,
            'exit_after_bars': exit_after_bars,
            'leverage': leverage,
        }

        for i in entry_indices:
            signal_meta[i] = base_meta.copy()

        # Convert to pandas Series for compatibility
        entries = pd.Series(entries_arr, index=data.index)
        exits = pd.Series(exits_arr, index=data.index)
        sizes = pd.Series(sizes_arr, index=data.index)
        sl_pcts = pd.Series(sl_pcts_arr, index=data.index)
        tp_pcts = pd.Series(tp_pcts_arr, index=data.index)

        return entries, exits, sizes, sl_pcts, tp_pcts, signal_meta

    def _extract_metrics(self, portfolio, n_signals: int) -> Dict:
        """
        Extract comprehensive metrics from portfolio

        Args:
            portfolio: Portfolio object
            n_signals: Number of entry signals generated

        Returns:
            Dict with all metrics
        """
        stats = portfolio.stats()

        # Core metrics
        total_return = portfolio.total_return() if hasattr(portfolio, 'total_return') else 0.0
        sharpe = portfolio.sharpe_ratio() if hasattr(portfolio, 'sharpe_ratio') else 0.0
        sortino = portfolio.sortino_ratio() if hasattr(portfolio, 'sortino_ratio') else 0.0
        max_dd = portfolio.max_drawdown() if hasattr(portfolio, 'max_drawdown') else 0.0

        # Trade statistics
        trades = portfolio.trades if hasattr(portfolio, 'trades') else None

        # Handle win_rate (might be property or method)
        if trades is not None:
            try:
                win_rate = trades.win_rate() if callable(trades.win_rate) else trades.win_rate
            except:
                win_rate = 0.0
        else:
            win_rate = 0.0

        total_trades = trades.count() if trades is not None else 0

        # Handle expectancy
        if trades is not None and hasattr(trades, 'expectancy'):
            try:
                expectancy = trades.expectancy() if callable(trades.expectancy) else trades.expectancy
            except:
                expectancy = 0.0
        else:
            expectancy = 0.0

        # Handle profit_factor
        if trades is not None and hasattr(trades, 'profit_factor'):
            try:
                profit_factor = trades.profit_factor() if callable(trades.profit_factor) else trades.profit_factor
            except:
                profit_factor = 0.0
        else:
            profit_factor = 0.0

        # Custom metrics
        ed_ratio = self._calculate_ed_ratio(expectancy, max_dd)
        consistency = self._calculate_consistency(portfolio)

        return {
            # Returns
            'total_return': sanitize_float(total_return),
            'cagr': sanitize_float(self._calculate_cagr(portfolio)),

            # Risk-adjusted
            'sharpe_ratio': sanitize_float(sharpe),
            'sortino_ratio': sanitize_float(sortino),
            'max_drawdown': sanitize_float(max_dd),

            # Trade stats
            'total_trades': int(total_trades),
            'win_rate': sanitize_float(win_rate),
            'expectancy': sanitize_float(expectancy),
            'profit_factor': sanitize_float(profit_factor, default=1.0),

            # Custom
            'ed_ratio': sanitize_float(ed_ratio),
            'consistency': sanitize_float(consistency),

            # Metadata
            'n_signals_generated': int(n_signals),
            'signal_execution_rate': sanitize_float(total_trades / n_signals) if n_signals > 0 else 0.0,
        }

    def _extract_trades(self, portfolio) -> List[Dict]:
        """
        Extract individual trade records

        Returns:
            List of trade dicts
        """
        trades = portfolio.trades if hasattr(portfolio, 'trades') else None

        if trades is None or trades.count() == 0:
            return []

        trade_list = []

        for i in range(trades.count()):
            try:
                trade = {
                    'entry_idx': int(trades.entry_idx[i]) if hasattr(trades, 'entry_idx') else i,
                    'exit_idx': int(trades.exit_idx[i]) if hasattr(trades, 'exit_idx') else i,
                    'entry_price': float(trades.entry_price[i]) if hasattr(trades, 'entry_price') else 0.0,
                    'exit_price': float(trades.exit_price[i]) if hasattr(trades, 'exit_price') else 0.0,
                    'size': float(trades.size[i]) if hasattr(trades, 'size') else 0.0,
                    'pnl': float(trades.pnl[i]) if hasattr(trades, 'pnl') else 0.0,
                    'return': float(trades.returns[i]) if hasattr(trades, 'returns') else 0.0,
                }
                trade_list.append(trade)
            except Exception as e:
                logger.debug(f"Could not extract trade {i}: {e}")
                continue

        return trade_list

    def _calculate_ed_ratio(self, expectancy: float, max_dd: float) -> float:
        """
        Calculate Expectancy/Drawdown ratio (edge efficiency)

        Higher = better edge relative to risk
        """
        if max_dd == 0 or max_dd > 1:
            return 0.0

        return expectancy / max_dd

    def _calculate_consistency(self, portfolio) -> float:
        """
        Calculate consistency (% of time in profit)

        Returns value between 0 and 1
        """
        try:
            equity_curve = portfolio.value()
            initial_value = equity_curve.iloc[0]

            in_profit = (equity_curve > initial_value).sum()
            total_periods = len(equity_curve)

            return in_profit / total_periods if total_periods > 0 else 0.0
        except:
            return 0.0

    def _calculate_cagr(self, portfolio) -> float:
        """
        Calculate Compound Annual Growth Rate

        Returns annualized return
        """
        try:
            total_return = portfolio.total_return()
            equity_curve = portfolio.value()

            # Calculate years
            n_periods = len(equity_curve)
            # Assume daily data if not specified
            years = n_periods / 365

            if years > 0:
                cagr = (1 + total_return) ** (1 / years) - 1
                return float(cagr)
        except:
            pass

        return 0.0

    def _empty_results(self) -> Dict:
        """
        Return empty results structure

        Used when backtest fails or has no trades
        """
        return {
            'total_return': 0.0,
            'cagr': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'total_trades': 0,
            'win_rate': 0.0,
            'expectancy': 0.0,
            'profit_factor': 0.0,
            'avg_leverage': 1.0,
            'ed_ratio': 0.0,
            'consistency': 0.0,
            'n_signals_generated': 0,
            'signal_execution_rate': 0.0,
            'trades': [],
        }

    # Alias for backward compatibility
    backtest_portfolio = backtest


