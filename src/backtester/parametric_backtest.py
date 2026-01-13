"""
Parametric Strategy Generator with Numba Parallelization

Generates N strategies from parameter space using parallel testing.
Shares OHLC data across all strategies for memory efficiency.

TERMINOLOGY:
- "Parameter combination" = one SET of (SL, TP, leverage, exit_bars)
- "Strategy" = complete entity created from template + parameter set
- This module generates STRATEGIES by testing parameter combinations

Usage:
    backtester = ParametricBacktester(config)
    results = backtester.backtest_pattern(
        pattern_signals=signals,  # (n_bars, n_symbols) boolean array
        ohlc_data={'close': ..., 'high': ..., 'low': ...},
        directions=directions,  # (n_bars, n_symbols) int8 array: 1=long, -1=short
    )
    # results is DataFrame with metrics for each generated strategy
"""

import itertools
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numba import jit, prange

from src.backtester.parametric_constants import (
    PARAM_SPACE, LEVERAGE_VALUES,
    ATR_SL_MULTIPLIERS, ATR_TP_MULTIPLIERS, RR_RATIOS,
    TRAILING_STOP_PCTS, TRAILING_ACTIVATION_PCTS,
    STRUCTURE_LOOKBACKS, BREAKEVEN_BUFFER,
    TYPICAL_ATR_PCT, STRUCTURE_SL_ESTIMATE,
)
from src.backtester.numba_kernels import (
    calculate_swing_low_high_numba,
    calculate_atr_full_numba,
    convert_sl_atr_to_pct_numba,
    convert_tp_atr_to_pct_numba,
    convert_tp_rr_to_pct_numba,
    convert_sl_structure_to_pct_2d_numba,
)
from src.strategies.base import StopLossType, TakeProfitType
from src.utils.risk_calculator import calculate_safe_leverage

logger = logging.getLogger(__name__)


# =============================================================================
# PRE-CALCULATION FUNCTIONS (Python, called before Numba kernel)
# =============================================================================

def _calculate_atr_at_bars(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14
) -> np.ndarray:
    """
    Calculate ATR for all bars/symbols using Numba-optimized kernel.

    Args:
        high: (n_bars, n_symbols) high prices
        low: (n_bars, n_symbols) low prices
        close: (n_bars, n_symbols) close prices
        period: ATR period (default 14)

    Returns:
        atr: (n_bars, n_symbols) float64 - ATR values
    """
    return calculate_atr_full_numba(high, low, close, period)


def _calculate_swing_low_high(
    high: np.ndarray,
    low: np.ndarray,
    lookback: int = 10
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate swing low/high for structure-based SL using Numba-optimized kernel.

    Args:
        high: (n_bars, n_symbols) high prices
        low: (n_bars, n_symbols) low prices
        lookback: Number of bars to look back

    Returns:
        swing_low: (n_bars, n_symbols) - lowest low in lookback
        swing_high: (n_bars, n_symbols) - highest high in lookback
    """
    return calculate_swing_low_high_numba(high, low, lookback)


def _convert_sl_to_pct(
    sl_type: StopLossType,
    entries: np.ndarray,
    close: np.ndarray,
    directions: np.ndarray,
    sl_pct: float = None,
    atr: np.ndarray = None,
    atr_multiplier: float = None,
    swing_low: np.ndarray = None,
    swing_high: np.ndarray = None,
    trailing_pct: float = None,
) -> np.ndarray:
    """
    Convert any SL type to percentage values per entry bar using Numba kernels.

    Args:
        sl_type: Type of stop loss
        entries: (n_bars, n_symbols) bool - entry signals
        close: (n_bars, n_symbols) close prices
        directions: (n_bars, n_symbols) int8 - 1=long, -1=short
        sl_pct: For PERCENTAGE type
        atr: For ATR type - pre-calculated ATR array
        atr_multiplier: For ATR type
        swing_low: For STRUCTURE type
        swing_high: For STRUCTURE type
        trailing_pct: For TRAILING type (initial distance)

    Returns:
        sl_pcts: (n_bars, n_symbols) float64 - SL as decimal (0.02 = 2%)
    """
    n_bars, n_symbols = close.shape

    if sl_type == StopLossType.PERCENTAGE:
        sl_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)
        sl_pcts[entries] = sl_pct

    elif sl_type == StopLossType.ATR:
        # Numba-optimized ATR to percentage conversion
        sl_pcts = convert_sl_atr_to_pct_numba(entries, close, atr, atr_multiplier)

    elif sl_type == StopLossType.STRUCTURE:
        # Numba-optimized STRUCTURE to percentage conversion
        sl_pcts = convert_sl_structure_to_pct_2d_numba(
            entries, close, directions, swing_low, swing_high
        )

    elif sl_type == StopLossType.TRAILING:
        sl_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)
        sl_pcts[entries] = trailing_pct

    else:
        sl_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    return sl_pcts


def _convert_tp_to_pct(
    tp_type: Optional[TakeProfitType],
    entries: np.ndarray,
    close: np.ndarray,
    directions: np.ndarray,
    sl_pcts: np.ndarray,
    tp_pct: float = None,
    atr: np.ndarray = None,
    atr_multiplier: float = None,
    rr_ratio: float = None,
) -> np.ndarray:
    """
    Convert any TP type to percentage values per entry bar using Numba kernels.

    Args:
        tp_type: Type of take profit (can be None)
        entries: (n_bars, n_symbols) bool - entry signals
        close: (n_bars, n_symbols) close prices
        directions: (n_bars, n_symbols) int8 - 1=long, -1=short
        sl_pcts: (n_bars, n_symbols) - SL percentages (needed for RR_RATIO)
        tp_pct: For PERCENTAGE type
        atr: For ATR type - pre-calculated ATR array
        atr_multiplier: For ATR type
        rr_ratio: For RR_RATIO type

    Returns:
        tp_pcts: (n_bars, n_symbols) float64 - TP as decimal
    """
    n_bars, n_symbols = close.shape

    if tp_type is None or tp_type == TakeProfitType.PERCENTAGE:
        tp_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)
        if tp_pct is not None:
            tp_pcts[entries] = tp_pct

    elif tp_type == TakeProfitType.ATR:
        # Numba-optimized ATR to percentage conversion
        tp_pcts = convert_tp_atr_to_pct_numba(entries, close, atr, atr_multiplier)

    elif tp_type == TakeProfitType.RR_RATIO:
        # Numba-optimized RR_RATIO conversion
        tp_pcts = convert_tp_rr_to_pct_numba(entries, sl_pcts, rr_ratio)

    else:
        tp_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    return tp_pcts


@dataclass
class ParametricResult:
    """Result from parametric backtest"""
    sl_pct: float
    tp_pct: float
    leverage: int
    exit_bars: int
    sharpe: float
    max_drawdown: float
    win_rate: float
    expectancy: float
    total_trades: int
    total_return: float
    score: float
    # Extended fields for multi-type SL/TP support
    sl_type: StopLossType = StopLossType.PERCENTAGE
    tp_type: Optional[TakeProfitType] = TakeProfitType.PERCENTAGE
    params: dict = field(default_factory=dict)  # Full params for reconstruction


# =============================================================================
# NUMBA KERNELS
# =============================================================================

@jit(nopython=True, cache=True)
def _simulate_single_param_set(
    close: np.ndarray,      # (n_bars, n_symbols)
    high: np.ndarray,       # (n_bars, n_symbols)
    low: np.ndarray,        # (n_bars, n_symbols)
    entries: np.ndarray,    # (n_bars, n_symbols) bool
    directions: np.ndarray, # (n_bars, n_symbols) int8
    sl_pct: float,
    tp_pct: float,
    leverage: int,          # Target leverage from strategy
    max_leverages: np.ndarray,  # (n_symbols,) per-coin max leverage from CoinRegistry
    exit_bars: int,
    initial_capital: float,
    fee_rate: float,
    slippage: float,
    max_positions: int,
    risk_pct: float,
    min_notional: float,
    funding_cumsum: np.ndarray,  # (n_bars, n_symbols) cumulative funding rates
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Simulate one parameter set across all symbols.

    Returns:
        equity_curve: (n_bars+1,) float64
        trade_pnls: (max_trades,) float64
        trade_wins: (max_trades,) bool - True if trade was profitable
    """
    n_bars, n_symbols = close.shape
    max_trades = n_bars * n_symbols  # Upper bound

    # Equity curve
    equity = initial_capital
    equity_curve = np.zeros(n_bars + 1, dtype=np.float64)
    equity_curve[0] = equity

    # Trade tracking
    trade_pnls = np.zeros(max_trades, dtype=np.float64)
    trade_wins = np.zeros(max_trades, dtype=np.bool_)
    n_trades = 0

    # Position state per symbol
    pos_entry_idx = np.full(n_symbols, -1, dtype=np.int64)
    pos_entry_price = np.zeros(n_symbols, dtype=np.float64)
    pos_size = np.zeros(n_symbols, dtype=np.float64)
    pos_direction = np.zeros(n_symbols, dtype=np.int8)
    pos_sl = np.zeros(n_symbols, dtype=np.float64)
    pos_tp = np.zeros(n_symbols, dtype=np.float64)
    pos_margin = np.zeros(n_symbols, dtype=np.float64)  # Margin used per position

    n_open = 0
    margin_used = 0.0  # Total margin currently in use

    for i in range(n_bars):
        # 1. Check exits for open positions
        for j in range(n_symbols):
            if pos_entry_idx[j] < 0:
                continue

            direction = pos_direction[j]
            current_high = high[i, j]
            current_low = low[i, j]

            should_close = False
            exit_price = close[i, j]

            # Time-based exit
            bars_held = i - pos_entry_idx[j]
            if exit_bars > 0 and bars_held >= exit_bars:
                should_close = True

            # Stop loss check (using high/low for intrabar detection)
            if not should_close:
                if direction == 1 and current_low <= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]
                elif direction == -1 and current_high >= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]

            # Take profit check
            if not should_close and pos_tp[j] > 0:
                if direction == 1 and current_high >= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]
                elif direction == -1 and current_low <= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]

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

                # Apply funding costs (O(1) lookup using cumsum)
                entry_idx = pos_entry_idx[j]
                if entry_idx > 0:
                    total_funding = funding_cumsum[i, j] - funding_cumsum[entry_idx - 1, j]
                else:
                    total_funding = funding_cumsum[i, j]
                funding_cost = notional * total_funding
                if direction == 1:  # Long pays when rate positive
                    pnl -= funding_cost
                else:  # Short receives when rate positive
                    pnl += funding_cost

                equity += pnl

                # Record trade as percentage of notional (for expectancy calculation)
                if n_trades < max_trades:
                    # Store PnL as percentage of trade notional, not absolute USD
                    trade_pnl_pct = pnl / notional if notional > 0 else 0.0
                    trade_pnls[n_trades] = trade_pnl_pct
                    trade_wins[n_trades] = pnl > 0
                    n_trades += 1

                # Clear position and release margin
                margin_used -= pos_margin[j]
                pos_margin[j] = 0.0
                pos_entry_idx[j] = -1
                n_open -= 1

        # 2. Check for new entries
        if n_open < max_positions:
            for j in range(n_symbols):
                if n_open >= max_positions:
                    break
                if pos_entry_idx[j] >= 0:
                    continue  # Already have position
                if not entries[i, j]:
                    continue

                direction = directions[i, j]
                if direction == 0:
                    continue

                price = close[i, j]

                # Apply slippage
                if direction == 1:
                    slipped_entry = price * (1.0 + slippage)
                else:
                    slipped_entry = price * (1.0 - slippage)

                # Risk-based position sizing with margin tracking
                # Step 1: Calculate target notional based on risk
                risk_amount = equity * risk_pct
                if sl_pct > 0:
                    notional = risk_amount / sl_pct
                else:
                    continue  # Skip if no SL defined

                # Step 2: Calculate actual leverage (capped by per-coin max)
                actual_lev = leverage
                if max_leverages[j] < leverage:
                    actual_lev = max_leverages[j]
                if actual_lev < 1:
                    actual_lev = 1

                # Step 3: Calculate margin needed
                margin_needed = notional / actual_lev

                # Step 3b: Apply dynamic cap (diversification)
                # Each trade uses at most 1/max_positions of equity
                max_margin_per_trade = equity / max_positions
                if margin_needed > max_margin_per_trade:
                    margin_needed = max_margin_per_trade
                    notional = margin_needed * actual_lev  # Adjust notional

                # Step 4: Check margin available (simulate exchange rejection)
                margin_available = equity - margin_used
                if margin_needed > margin_available:
                    continue  # Skip - insufficient margin

                # Step 5: Check minimum notional (Hyperliquid requirement)
                if notional < min_notional:
                    continue  # Skip - trade too small

                # Step 6: Calculate position size
                size = notional / slipped_entry

                # Calculate SL/TP prices
                if direction == 1:
                    sl_price = slipped_entry * (1.0 - sl_pct)
                    tp_price = slipped_entry * (1.0 + tp_pct) if tp_pct > 0 else 0.0
                else:
                    sl_price = slipped_entry * (1.0 + sl_pct)
                    tp_price = slipped_entry * (1.0 - tp_pct) if tp_pct > 0 else 0.0

                # Store position and track margin
                pos_entry_idx[j] = i
                pos_entry_price[j] = slipped_entry
                pos_size[j] = size
                pos_direction[j] = direction
                pos_sl[j] = sl_price
                pos_tp[j] = tp_price
                pos_margin[j] = margin_needed
                margin_used += margin_needed
                n_open += 1

        equity_curve[i + 1] = equity

    # Close remaining positions at end
    for j in range(n_symbols):
        if pos_entry_idx[j] < 0:
            continue

        exit_price = close[n_bars - 1, j]
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

        # Apply funding costs (O(1) lookup using cumsum)
        entry_idx = pos_entry_idx[j]
        exit_idx = n_bars - 1
        if entry_idx > 0:
            total_funding = funding_cumsum[exit_idx, j] - funding_cumsum[entry_idx - 1, j]
        else:
            total_funding = funding_cumsum[exit_idx, j]
        funding_cost = notional * total_funding
        if direction == 1:  # Long
            pnl -= funding_cost
        else:  # Short
            pnl += funding_cost

        equity += pnl

        # Record trade as percentage of notional (for expectancy calculation)
        if n_trades < max_trades:
            trade_pnl_pct = pnl / notional if notional > 0 else 0.0
            trade_pnls[n_trades] = trade_pnl_pct
            trade_wins[n_trades] = pnl > 0
            n_trades += 1

    equity_curve[n_bars] = equity

    # Trim arrays
    trade_pnls = trade_pnls[:n_trades]
    trade_wins = trade_wins[:n_trades]

    return equity_curve, trade_pnls, trade_wins


@jit(nopython=True, cache=True)
def _simulate_single_param_set_v2(
    close: np.ndarray,           # (n_bars, n_symbols)
    high: np.ndarray,            # (n_bars, n_symbols)
    low: np.ndarray,             # (n_bars, n_symbols)
    entries: np.ndarray,         # (n_bars, n_symbols) bool
    directions: np.ndarray,      # (n_bars, n_symbols) int8
    sl_pcts: np.ndarray,         # (n_bars, n_symbols) - DYNAMIC per entry bar
    tp_pcts: np.ndarray,         # (n_bars, n_symbols) - DYNAMIC per entry bar
    leverage: int,
    max_leverages: np.ndarray,   # (n_symbols,) per-coin max
    exit_bars: int,
    initial_capital: float,
    fee_rate: float,
    slippage: float,
    max_positions: int,
    risk_pct: float,
    min_notional: float,
    is_trailing: bool,
    trailing_activation_pct: float,
    breakeven_buffer: float,
    funding_cumsum: np.ndarray,  # (n_bars, n_symbols) cumulative funding rates
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extended simulation kernel supporting per-bar SL/TP and trailing stops.

    Key changes from v1:
    - sl_pcts/tp_pcts are 2D arrays (read at entry bar)
    - pos_high_water_mark tracks high/low for trailing
    - Trailing updates SL dynamically during position

    Returns:
        equity_curve: (n_bars+1,) float64
        trade_pnls: (n_trades,) float64 - PnL as percentage of notional
        trade_wins: (n_trades,) bool - True if trade was profitable
    """
    n_bars, n_symbols = close.shape
    max_trades = n_bars * n_symbols

    # Equity tracking
    equity = initial_capital
    equity_curve = np.zeros(n_bars + 1, dtype=np.float64)
    equity_curve[0] = equity

    # Trade tracking
    trade_pnls = np.zeros(max_trades, dtype=np.float64)
    trade_wins = np.zeros(max_trades, dtype=np.bool_)
    n_trades = 0

    # Position state per symbol
    pos_entry_idx = np.full(n_symbols, -1, dtype=np.int64)
    pos_entry_price = np.zeros(n_symbols, dtype=np.float64)
    pos_size = np.zeros(n_symbols, dtype=np.float64)
    pos_direction = np.zeros(n_symbols, dtype=np.int8)
    pos_sl = np.zeros(n_symbols, dtype=np.float64)
    pos_tp = np.zeros(n_symbols, dtype=np.float64)
    pos_margin = np.zeros(n_symbols, dtype=np.float64)

    # Trailing stop state
    pos_high_water_mark = np.zeros(n_symbols, dtype=np.float64)
    pos_trailing_active = np.zeros(n_symbols, dtype=np.bool_)
    pos_trailing_pct = np.zeros(n_symbols, dtype=np.float64)

    n_open = 0
    margin_used = 0.0

    for i in range(n_bars):
        # 1. UPDATE TRAILING STOPS (before exit checks)
        if is_trailing:
            for j in range(n_symbols):
                if pos_entry_idx[j] < 0:
                    continue

                direction = pos_direction[j]
                current_high = high[i, j]
                current_low = low[i, j]
                current_price = close[i, j]

                # Check activation (must be in profit by activation_pct)
                if not pos_trailing_active[j]:
                    if direction == 1:  # Long
                        profit_pct = (current_price - pos_entry_price[j]) / pos_entry_price[j]
                    else:  # Short
                        profit_pct = (pos_entry_price[j] - current_price) / pos_entry_price[j]

                    if profit_pct >= trailing_activation_pct:
                        pos_trailing_active[j] = True
                        if direction == 1:
                            pos_high_water_mark[j] = current_high
                        else:
                            pos_high_water_mark[j] = current_low
                    continue

                # Update high water mark and SL
                if direction == 1:  # Long
                    if current_high > pos_high_water_mark[j]:
                        pos_high_water_mark[j] = current_high
                    # Calculate new trailing SL with breakeven buffer floor
                    theoretical_sl = pos_high_water_mark[j] * (1.0 - pos_trailing_pct[j])
                    floor_price = pos_entry_price[j] * (1.0 + breakeven_buffer)
                    new_sl = max(theoretical_sl, floor_price)
                    if new_sl > pos_sl[j]:
                        pos_sl[j] = new_sl
                else:  # Short
                    if current_low < pos_high_water_mark[j]:
                        pos_high_water_mark[j] = current_low
                    theoretical_sl = pos_high_water_mark[j] * (1.0 + pos_trailing_pct[j])
                    ceiling_price = pos_entry_price[j] * (1.0 - breakeven_buffer)
                    new_sl = min(theoretical_sl, ceiling_price)
                    if new_sl < pos_sl[j]:
                        pos_sl[j] = new_sl

        # 2. CHECK EXITS
        for j in range(n_symbols):
            if pos_entry_idx[j] < 0:
                continue

            direction = pos_direction[j]
            current_high = high[i, j]
            current_low = low[i, j]

            should_close = False
            exit_price = close[i, j]

            # Time-based exit
            bars_held = i - pos_entry_idx[j]
            if exit_bars > 0 and bars_held >= exit_bars:
                should_close = True

            # Stop loss check
            if not should_close:
                if direction == 1 and current_low <= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]
                elif direction == -1 and current_high >= pos_sl[j]:
                    should_close = True
                    exit_price = pos_sl[j]

            # Take profit check
            if not should_close and pos_tp[j] > 0:
                if direction == 1 and current_high >= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]
                elif direction == -1 and current_low <= pos_tp[j]:
                    should_close = True
                    exit_price = pos_tp[j]

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

                # Apply funding costs (O(1) lookup using cumsum)
                entry_idx = pos_entry_idx[j]
                if entry_idx > 0:
                    total_funding = funding_cumsum[i, j] - funding_cumsum[entry_idx - 1, j]
                else:
                    total_funding = funding_cumsum[i, j]
                funding_cost = notional * total_funding
                if direction == 1:  # Long pays when rate positive
                    pnl -= funding_cost
                else:  # Short receives when rate positive
                    pnl += funding_cost

                equity += pnl

                # Record trade
                if n_trades < max_trades:
                    trade_pnl_pct = pnl / notional if notional > 0 else 0.0
                    trade_pnls[n_trades] = trade_pnl_pct
                    trade_wins[n_trades] = pnl > 0
                    n_trades += 1

                # Clear position
                margin_used -= pos_margin[j]
                pos_margin[j] = 0.0
                pos_entry_idx[j] = -1
                pos_trailing_active[j] = False
                n_open -= 1

        # 3. CHECK ENTRIES
        if n_open < max_positions:
            for j in range(n_symbols):
                if n_open >= max_positions:
                    break
                if pos_entry_idx[j] >= 0:
                    continue
                if not entries[i, j]:
                    continue

                direction = directions[i, j]
                if direction == 0:
                    continue

                price = close[i, j]

                # Apply slippage
                if direction == 1:
                    slipped_entry = price * (1.0 + slippage)
                else:
                    slipped_entry = price * (1.0 - slippage)

                # GET SL/TP FROM 2D ARRAYS (per-entry bar)
                sl_pct = sl_pcts[i, j]
                tp_pct = tp_pcts[i, j]

                if sl_pct <= 0:
                    continue  # Invalid SL

                # Risk-based position sizing
                risk_amount = equity * risk_pct
                notional = risk_amount / sl_pct

                # Leverage capping
                actual_lev = leverage
                if max_leverages[j] < leverage:
                    actual_lev = max_leverages[j]
                if actual_lev < 1:
                    actual_lev = 1

                # Margin calculation
                margin_needed = notional / actual_lev

                # Diversification cap
                max_margin_per_trade = equity / max_positions
                if margin_needed > max_margin_per_trade:
                    margin_needed = max_margin_per_trade
                    notional = margin_needed * actual_lev

                # Margin check
                margin_available = equity - margin_used
                if margin_needed > margin_available:
                    continue

                # Min notional check
                if notional < min_notional:
                    continue

                size = notional / slipped_entry

                # Calculate SL/TP prices
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
                pos_direction[j] = direction
                pos_sl[j] = sl_price
                pos_tp[j] = tp_price
                pos_margin[j] = margin_needed
                margin_used += margin_needed
                n_open += 1

                # Initialize trailing state
                if is_trailing:
                    pos_high_water_mark[j] = price
                    pos_trailing_active[j] = False
                    pos_trailing_pct[j] = sl_pct

        equity_curve[i + 1] = equity

    # Close remaining positions at end
    for j in range(n_symbols):
        if pos_entry_idx[j] < 0:
            continue

        exit_price = close[n_bars - 1, j]
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

        # Apply funding costs (O(1) lookup using cumsum)
        entry_idx = pos_entry_idx[j]
        exit_idx = n_bars - 1
        if entry_idx > 0:
            total_funding = funding_cumsum[exit_idx, j] - funding_cumsum[entry_idx - 1, j]
        else:
            total_funding = funding_cumsum[exit_idx, j]
        funding_cost = notional * total_funding
        if direction == 1:  # Long
            pnl -= funding_cost
        else:  # Short
            pnl += funding_cost

        equity += pnl

        if n_trades < max_trades:
            trade_pnl_pct = pnl / notional if notional > 0 else 0.0
            trade_pnls[n_trades] = trade_pnl_pct
            trade_wins[n_trades] = pnl > 0
            n_trades += 1

    equity_curve[n_bars] = equity

    # Trim arrays
    trade_pnls = trade_pnls[:n_trades]
    trade_wins = trade_wins[:n_trades]

    return equity_curve, trade_pnls, trade_wins


@jit(nopython=True, cache=True)
def _calc_metrics(
    equity_curve: np.ndarray,
    trade_pnls: np.ndarray,
    trade_wins: np.ndarray,
    initial_capital: float,
    bars_per_year: float = 35040.0,  # Default: 15m crypto (96 bars/day * 365)
) -> Tuple[float, float, float, float, int, float]:
    """
    Calculate performance metrics from simulation results.

    Args:
        bars_per_year: Number of bars per year for Sharpe annualization.
            15m = 35040, 30m = 17520, 1h = 8760, 2h = 4380

    Returns:
        sharpe, max_drawdown, win_rate, expectancy, total_trades, total_return
    """
    n_trades = len(trade_pnls)

    if n_trades == 0:
        return 0.0, 0.0, 0.0, 0.0, 0, 0.0

    # Total return
    final_equity = equity_curve[-1]
    total_return = (final_equity - initial_capital) / initial_capital

    # Win rate
    wins = 0
    for i in range(n_trades):
        if trade_wins[i]:
            wins += 1
    win_rate = wins / n_trades

    # Expectancy: (Win% × Avg Win%) - (Loss% × Avg Loss%)
    # trade_pnls now contains PnL as percentage of trade notional
    avg_win_pct = 0.0
    avg_loss_pct = 0.0
    n_wins = 0
    n_losses = 0
    for i in range(n_trades):
        if trade_wins[i]:
            avg_win_pct += trade_pnls[i]
            n_wins += 1
        else:
            avg_loss_pct += abs(trade_pnls[i])
            n_losses += 1

    avg_win_pct = avg_win_pct / n_wins if n_wins > 0 else 0.0
    avg_loss_pct = avg_loss_pct / n_losses if n_losses > 0 else 0.0

    # Official expectancy formula
    expectancy = (win_rate * avg_win_pct) - ((1.0 - win_rate) * avg_loss_pct)

    # Max drawdown
    n_bars = len(equity_curve)
    running_max = equity_curve[0]
    max_dd = 0.0
    for i in range(1, n_bars):
        if equity_curve[i] > running_max:
            running_max = equity_curve[i]
        if running_max > 0:
            dd = (running_max - equity_curve[i]) / running_max
            if dd > max_dd:
                max_dd = dd

    # Clamp to [0, 1]
    if max_dd > 1.0:
        max_dd = 1.0
    if max_dd < 0.0:
        max_dd = 0.0

    # Sharpe ratio - TRADE-BASED calculation (more robust than bar-by-bar)
    # Bar-by-bar Sharpe is inflated when few trades spread across many bars
    # trade_pnls already contains PnL as percentage of trade notional
    n_bars = len(equity_curve)
    if n_trades >= 3:
        # Calculate mean and std of trade returns
        mean_trade_ret = 0.0
        for i in range(n_trades):
            mean_trade_ret += trade_pnls[i]
        mean_trade_ret /= n_trades

        var_trade_ret = 0.0
        for i in range(n_trades):
            var_trade_ret += (trade_pnls[i] - mean_trade_ret) ** 2
        var_trade_ret /= n_trades
        std_trade_ret = var_trade_ret ** 0.5

        if std_trade_ret > 1e-10:
            # Annualize based on trade frequency
            # trades_per_year = n_trades / (n_bars / bars_per_year)
            backtest_years = n_bars / bars_per_year if bars_per_year > 0 else 1.0
            trades_per_year = n_trades / backtest_years if backtest_years > 0 else n_trades

            # Cap annualization factor to avoid inflation
            # Max sqrt(250) ~= 15.8 (reasonable for daily trading)
            if trades_per_year > 250.0:
                trades_per_year = 250.0

            sharpe = mean_trade_ret / std_trade_ret * (trades_per_year ** 0.5)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # SANITY CHECK: Sharpe must be consistent with total_return
    if total_return < -0.5:  # Lost more than 50%
        max_sharpe = -abs(total_return) * 2.0
        if sharpe > max_sharpe:
            sharpe = max_sharpe
    elif total_return < 0.0 and sharpe > 0.0:
        sharpe = 0.0

    return sharpe, max_dd, win_rate, expectancy, n_trades, total_return


# =============================================================================
# MAIN CLASS
# =============================================================================

class ParametricBacktester:
    """
    Runs parametric backtests with Numba parallelization.

    Tests N parameter combinations in parallel to generate candidate strategies,
    sharing OHLC data for memory efficiency.
    """

    # Default parameter space (15m reference, will be scaled by timeframe)
    DEFAULT_PARAMETER_SPACE = {
        'sl_pct': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05],
        'tp_pct': [0, 0.02, 0.03, 0.05, 0.07, 0.10],  # 0 = no TP (rely on time exit)
        'leverage': [1, 2, 3, 5, 10, 20],  # Full range, capped by per-coin max at execution
        'exit_bars': [0, 10, 20, 50, 100],  # 0 = no time exit (for 15m reference)
    }

    # Timeframe to minutes mapping
    TF_TO_MINUTES = {
        '5m': 5,
        '15m': 15,
        '30m': 30,
        '1h': 60,
        '2h': 120,
    }

    def __init__(self, config: dict):
        """
        Initialize parametric backtester.

        Args:
            config: Full configuration dict
        """
        self.config = config

        # Load settings (crash if missing - CLAUDE.md Rule #3)
        bt_config = config['backtesting']
        self.initial_capital = bt_config['initial_capital']
        self.max_positions = config['risk']['limits']['max_open_positions_per_subaccount']

        hl_config = config['hyperliquid']  # Crash if missing (CLAUDE.md Rule #3)
        self.fee_rate = hl_config['fee_rate']
        self.slippage = hl_config['slippage']
        self.min_notional = hl_config['min_notional']

        risk_config = config['risk']['fixed_fractional']  # Crash if missing
        self.risk_pct = risk_config['risk_per_trade_pct']

        # Parameter space (can be overridden)
        self.parameter_space = self.DEFAULT_PARAMETER_SPACE.copy()

        # Scoring weights (match classifier)
        class_config = config.get('classification', {}).get('score_weights', {})
        self.score_weights = {
            'edge': class_config.get('edge', 0.50),
            'sharpe': class_config.get('sharpe', 0.25),
            'win_rate': class_config.get('win_rate', 0.15),
            'stability': class_config.get('stability', 0.10),
        }

        # Default bars_per_year for 15m (crypto 24/7)
        self.bars_per_year = 35040.0

        logger.info(
            f"ParametricBacktester initialized: "
            f"{self._count_strategies()} candidate strategies"
        )

    def set_timeframe(self, timeframe: str) -> None:
        """Set bars_per_year based on timeframe for correct Sharpe annualization."""
        tf_to_bars = {
            '5m': 105120,   # 12 bars/hour * 24 * 365
            '15m': 35040,   # 4 bars/hour * 24 * 365
            '30m': 17520,   # 2 bars/hour * 24 * 365
            '1h': 8760,     # 1 bar/hour * 24 * 365
            '2h': 4380,     # 0.5 bars/hour * 24 * 365
        }
        self.bars_per_year = float(tf_to_bars.get(timeframe, 35040))

    def _parse_timeframe_minutes(self, timeframe: str) -> int:
        """
        Parse timeframe string to minutes per bar.

        Args:
            timeframe: Timeframe string like '15m', '1h', '4h', '1d'

        Returns:
            Minutes per bar (e.g., 15 for '15m', 240 for '4h')
        """
        if timeframe in self.TF_TO_MINUTES:
            return self.TF_TO_MINUTES[timeframe]

        # Fallback: parse string format
        tf_lower = timeframe.lower()
        if tf_lower.endswith('m'):
            return int(tf_lower[:-1])
        elif tf_lower.endswith('h'):
            return int(tf_lower[:-1]) * 60
        elif tf_lower.endswith('d'):
            return int(tf_lower[:-1]) * 1440

        # Default to 15m if unknown
        logger.warning(f"Unknown timeframe '{timeframe}', defaulting to 15m")
        return 15

    def _count_strategies(self) -> int:
        """Count total candidate strategies (parameter combinations)"""
        count = 1
        for values in self.parameter_space.values():
            count *= len(values)
        return count

    def _generate_parameter_sets(self) -> Tuple[List[Tuple[float, float, int, int]], dict]:
        """
        Generate all parameter sets (each will create a strategy).

        TWO VALID MODES based on execution semantics:

        1. TOUCH_BASED (TP > 0): Pattern predicts price will TOUCH level
           - Filter: TP > SL for favorable R:R (break-even WR < 50%)
           - exit_bars can be 0 (TP is primary exit)

        2. CLOSE_BASED (TP = 0): Pattern predicts price at CLOSE of period
           - Filter: exit_bars > 0 (time exit is primary)
           - SL is for risk management only, not R:R optimization

        Common filters:
        - tp_pct=0 AND exit_bars=0: No exit condition except SL (invalid)
        - ANTI-LIQUIDATION: leverage must be safe given SL distance

        Returns:
            Tuple of (valid_sets, filter_stats) where filter_stats contains counts
        """
        all_combos = list(itertools.product(
            self.parameter_space['sl_pct'],
            self.parameter_space['tp_pct'],
            self.parameter_space['leverage'],
            self.parameter_space['exit_bars'],
        ))

        valid_sets = []
        no_exit_filtered = 0
        rr_filtered = 0
        liquidation_filtered = 0

        for sl, tp, lev, exit_b in all_combos:
            # FILTER 1: Must have an exit condition (not just SL)
            if tp == 0 and exit_b == 0:
                no_exit_filtered += 1
                continue

            # FILTER 2: Mode-specific validation
            if tp > 0:
                # TOUCH_BASED mode: require favorable R:R (TP > SL)
                if tp <= sl:
                    rr_filtered += 1
                    continue
            # CLOSE_BASED mode (tp == 0): exit_bars > 0 already guaranteed by FILTER 1

            # FILTER 3: ANTI-LIQUIDATION
            # Ensure SL triggers BEFORE liquidation (with 10% buffer)
            # Uses conservative max_leverage=20 (covers most coins)
            # Formula: safe_leverage = 1 / (sl_distance + maintenance_margin_rate)
            max_safe_lev = calculate_safe_leverage(
                sl_pct=sl,
                max_leverage=20,  # Conservative: most coins are 20-40x max
                buffer_pct=10.0,  # 10% buffer between SL and liquidation
            )
            if lev > max_safe_lev:
                liquidation_filtered += 1
                continue  # Skip: would be liquidated before SL triggers

            valid_sets.append((sl, tp, lev, exit_b))

        filter_stats = {
            'total_raw': len(all_combos),
            'no_exit_filtered': no_exit_filtered,
            'rr_filtered': rr_filtered,
            'liquidation_filtered': liquidation_filtered,
            'total_filtered': no_exit_filtered + rr_filtered + liquidation_filtered,
            'valid': len(valid_sets),
        }

        return valid_sets, filter_stats

    def _calculate_score(self, result: ParametricResult) -> float:
        """Calculate composite score matching classifier logic"""
        # Normalize edge (expectancy as % of capital)
        edge_pct = result.expectancy / self.initial_capital
        edge_norm = min(max(edge_pct / 0.10, 0), 1)  # 0-10% range

        # Normalize sharpe
        sharpe_norm = min(max(result.sharpe / 3.0, 0), 1)  # 0-3 range

        # Win rate is already normalized (0-1)
        win_rate_score = result.win_rate

        # Stability (inverse of drawdown)
        stability = 1.0 - result.max_drawdown

        score = (
            self.score_weights['edge'] * edge_norm +
            self.score_weights['sharpe'] * sharpe_norm +
            self.score_weights['win_rate'] * win_rate_score +
            self.score_weights['stability'] * stability
        )

        return min(max(score * 100, 0), 100)

    def backtest_pattern(
        self,
        pattern_signals: np.ndarray,
        ohlc_data: Dict[str, np.ndarray],
        directions: np.ndarray,
        max_leverages: np.ndarray,
        strategy_name: str = None,
        funding_cumsum: np.ndarray = None,
    ) -> pd.DataFrame:
        """
        Run parametric backtest for a pattern.

        Args:
            pattern_signals: (n_bars, n_symbols) boolean array of entry signals
            ohlc_data: Dict with 'close', 'high', 'low' arrays (n_bars, n_symbols)
            directions: (n_bars, n_symbols) int8 array: 1=long, -1=short
            max_leverages: (n_symbols,) int32 array - per-coin max leverage from CoinRegistry
            strategy_name: Optional strategy name for log prefixing

        Returns:
            DataFrame with metrics for each parameter combination, sorted by score
        """
        log_prefix = f"[{strategy_name}] " if strategy_name else ""
        close = ohlc_data['close'].astype(np.float64)
        high = ohlc_data['high'].astype(np.float64)
        low = ohlc_data['low'].astype(np.float64)
        entries = pattern_signals.astype(np.bool_)
        dirs = directions.astype(np.int8)
        max_levs = max_leverages.astype(np.int32)

        n_bars, n_symbols = close.shape

        # Generate valid parameter sets (applies filters)
        param_sets, filter_stats = self._generate_parameter_sets()

        logger.info(
            f"{log_prefix}Parametric: {n_bars} bars, {n_symbols} symbols, "
            f"{filter_stats['valid']}/{filter_stats['total_raw']} combos "
            f"(filtered: no_exit={filter_stats['no_exit_filtered']}, "
            f"R:R={filter_stats['rr_filtered']}, "
            f"anti-liq={filter_stats['liquidation_filtered']}), "
            f"max_lev={max_levs.min()}-{max_levs.max()}x"
        )

        results = []

        # Use provided funding_cumsum or zeros if not provided
        if funding_cumsum is None:
            funding_cumsum = np.zeros((n_bars, n_symbols), dtype=np.float64)

        for sl_pct, tp_pct, leverage, exit_bars in param_sets:
            # Run simulation (leverage capping done per-coin inside kernel)
            equity_curve, trade_pnls, trade_wins = _simulate_single_param_set(
                close, high, low, entries, dirs,
                sl_pct, tp_pct, leverage, max_levs, exit_bars,
                self.initial_capital, self.fee_rate, self.slippage,
                self.max_positions, self.risk_pct, self.min_notional,
                funding_cumsum,
            )

            # Calculate metrics
            sharpe, max_dd, win_rate, expectancy, n_trades, total_return = _calc_metrics(
                equity_curve, trade_pnls, trade_wins, self.initial_capital, self.bars_per_year
            )

            result = ParametricResult(
                sl_pct=sl_pct,
                tp_pct=tp_pct,
                leverage=leverage,  # Target leverage (capped per-coin at runtime)
                exit_bars=exit_bars,
                sharpe=sharpe,
                max_drawdown=max_dd,
                win_rate=win_rate,
                expectancy=expectancy,
                total_trades=n_trades,
                total_return=total_return,
                score=0.0,  # Will be calculated below
            )
            result.score = self._calculate_score(result)
            results.append(result)

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'sl_pct': r.sl_pct,
                'tp_pct': r.tp_pct,
                'leverage': r.leverage,
                'exit_bars': r.exit_bars,
                'sharpe': r.sharpe,
                'max_drawdown': r.max_drawdown,
                'win_rate': r.win_rate,
                'expectancy': r.expectancy,
                'total_trades': r.total_trades,
                'total_return': r.total_return,
                'score': r.score,
            }
            for r in results
        ])

        # Sort by score descending
        df = df.sort_values('score', ascending=False).reset_index(drop=True)

        logger.info(
            f"{log_prefix}Parametric complete: "
            f"Best score={df['score'].iloc[0]:.2f}, "
            f"Sharpe={df['sharpe'].iloc[0]:.2f}, "
            f"SL={df['sl_pct'].iloc[0]:.1%}, TP={df['tp_pct'].iloc[0]:.1%}, "
            f"Lev={df['leverage'].iloc[0]}, Exit={df['exit_bars'].iloc[0]}"
        )

        return df

    def get_top_k(self, df: pd.DataFrame, k: int = 5) -> pd.DataFrame:
        """Get top K candidate strategies"""
        return df.head(k).copy()

    def set_parameter_space(self, space: Dict[str, List]) -> None:
        """
        Override default parameter space.

        Args:
            space: Dict with 'sl_pct', 'tp_pct', 'leverage', 'exit_bars' lists
        """
        self.parameter_space.update(space)
        logger.info(f"Parameter space updated: {self._count_strategies()} candidate strategies")

    def build_execution_type_space(
        self,
        execution_type: str,
        base_magnitude: float,
        base_exit_bars: int,
        atr_signal_median: Optional[float] = None,
    ) -> Dict[str, List]:
        """
        Build parameter space constrained by execution type.

        This ensures parametric optimization stays aligned with the pattern's
        validated target semantics:

        TOUCH_BASED targets (target_max_*):
        - Pattern predicts price will TOUCH level
        - TP is PRIMARY exit (must be > 0)
        - Time exit is BACKSTOP (can be 0)
        - Optimize TP around validated magnitude

        CLOSE_BASED targets (all others):
        - Pattern predicts price at CLOSE of period
        - Time exit is PRIMARY (must be > 0)
        - TP is DISABLED (always 0)
        - SL based on ATR volatility (not magnitude) to avoid premature stops

        Args:
            execution_type: 'touch_based' or 'close_based'
            base_magnitude: Target magnitude as decimal (e.g., 0.02 for 2%)
            base_exit_bars: Holding period in bars
            atr_signal_median: Median ATR when pattern fires (price-normalized).
                               Used for close_based SL calculation.

        Returns:
            Parameter space dict with sl_pct, tp_pct, exit_bars, leverage
        """
        if execution_type == 'touch_based':
            # TP-BASED: Pattern predicts price will TOUCH level
            # TP must exist, centered around magnitude (no zero)
            tp_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5]
            tp_values = sorted(set([
                round(base_magnitude * mult, 4)
                for mult in tp_multipliers
            ]))
            tp_values = [v for v in tp_values if v > 0]  # No zero TP

            # SL constrained by max 2.5:1 ratio to TP
            # 2.5:1 requires ~71% WR to break even, reasonable for validated patterns
            max_sl = base_magnitude * 2.5
            sl_multipliers = [1.0, 1.5, 2.0, 2.5]
            sl_values = sorted(set([
                round(base_magnitude * mult, 4)
                for mult in sl_multipliers
                if base_magnitude * mult <= max_sl
            ]))

            # Exit as backstop (can be 0 = disabled)
            exit_multipliers = [0, 1.0, 1.5, 2.0]
            exit_values = sorted(set([
                max(0, int(base_exit_bars * mult))
                for mult in exit_multipliers
            ]))

            logger.info(
                f"Built touch_based space: "
                f"TP={[f'{p:.1%}' for p in tp_values]} (NO zero), "
                f"SL={[f'{p:.1%}' for p in sl_values]}, "
                f"exit={exit_values} (can be 0 = backstop disabled)"
            )

        else:  # close_based
            # TIME-BASED: Pattern predicts price will CLOSE at level
            # TP disabled, time exit is primary
            tp_values = [0.0]  # Only zero - no TP

            # SL based on VOLATILITY, not magnitude
            # For close_based, we hold until time exit - need SL wide enough
            # to avoid getting stopped by normal price fluctuations.
            #
            # ATR-based SL rationale:
            # - Pattern was validated with no SL (just time exit)
            # - Real trading needs SL for risk management
            # - SL should be based on expected volatility during holding period
            # - Use ATR * holding_period_factor as baseline
            #
            # Without ATR: fallback to wider magnitude multipliers
            if atr_signal_median and atr_signal_median > 0:
                # ATR-based SL: pattern fired at this volatility level
                # For close_based, the edge manifests at TIME EXIT (e.g., 24h)
                # SL must be wide enough to survive normal volatility until then
                # Typical 24h price swing: 3-5x daily ATR
                # Multipliers: 4x to 10x ATR for sufficient breathing room
                sl_multipliers = [4.0, 6.0, 8.0, 10.0]
                sl_base = atr_signal_median
                sl_values = sorted(set([
                    round(sl_base * mult, 4)
                    for mult in sl_multipliers
                ]))
                logger.info(
                    f"Built close_based space (ATR-based SL): "
                    f"TP=[0.00%] (DISABLED), "
                    f"SL={[f'{p:.1%}' for p in sl_values]} (ATR={atr_signal_median:.2%}), "
                    f"exit={base_exit_bars} bars"
                )
            else:
                # Fallback: use wider magnitude multipliers
                # These are less accurate but better than tight SL
                sl_multipliers = [4.0, 6.0, 8.0, 10.0]
                sl_values = sorted(set([
                    round(base_magnitude * mult, 4)
                    for mult in sl_multipliers
                ]))
                logger.info(
                    f"Built close_based space (magnitude-based SL, no ATR): "
                    f"TP=[0.00%] (DISABLED), "
                    f"SL={[f'{p:.1%}' for p in sl_values]} (wider), "
                    f"exit={base_exit_bars} bars"
                )

            # Exit MUST exist (no zero - time exit is primary)
            exit_multipliers = [0.5, 0.75, 1.0, 1.25, 1.5]
            exit_values = sorted(set([
                max(1, int(base_exit_bars * mult))
                for mult in exit_multipliers
            ]))

        # Standard leverage values
        leverage_values = LEVERAGE_VALUES.copy()

        return {
            'sl_pct': sl_values,
            'tp_pct': tp_values,
            'exit_bars': exit_values,
            'leverage': leverage_values,
        }

    def build_absolute_space(self, timeframe: str = '15m') -> Dict[str, List]:
        """
        Build parameter space for AI strategies using predefined constants.

        Each timeframe has its own empirically validated parameter ranges
        defined in parametric_constants.py.

        Leverage values are tested against per-coin max from CoinRegistry at runtime.

        Args:
            timeframe: Target timeframe (e.g., '15m', '4h', '1d')

        Returns:
            Parameter space dict for the timeframe

        Raises:
            ValueError: If timeframe not in PARAM_SPACE
        """
        if timeframe not in PARAM_SPACE:
            supported = list(PARAM_SPACE.keys())
            raise ValueError(
                f"Unsupported timeframe '{timeframe}'. Supported: {supported}"
            )

        # Get predefined space for this timeframe
        tf_space = PARAM_SPACE[timeframe]

        space = {
            'sl_pct': tf_space['sl_pct'].copy(),
            'tp_pct': tf_space['tp_pct'].copy(),
            'leverage': LEVERAGE_VALUES.copy(),
            'exit_bars': tf_space['exit_bars'].copy(),
        }

        # Calculate total combinations
        total = (
            len(space['sl_pct']) *
            len(space['tp_pct']) *
            len(space['leverage']) *
            len(space['exit_bars'])
        )
        # Minus invalid (tp=0 AND exit=0)
        invalid = len(space['sl_pct']) * len(space['leverage'])
        valid = total - invalid

        logger.info(
            f"Built absolute space for {timeframe}: "
            f"SL={[f'{p:.1%}' for p in space['sl_pct']]}, "
            f"TP={[f'{p:.1%}' for p in space['tp_pct']]}, "
            f"exit={space['exit_bars']}, lev={space['leverage']} "
            f"({valid} valid combinations)"
        )

        return space

    def build_structure_aware_space(
        self,
        structure: 'StrategyStructure',
        timeframe: str = '15m',
    ) -> Dict[str, List]:
        """
        Build parameter space based on detected strategy structure.

        For percentage-based SL/TP: full parametric optimization
        For non-percentage (ATR, structure, trailing): only optimize leverage + exit_bars

        The Numba kernel only supports percentage-based SL/TP calculations,
        so non-percentage strategies preserve their original SL/TP params.

        Args:
            structure: Detected StrategyStructure from strategy_structure.py
            timeframe: Target timeframe for exit_bars scaling

        Returns:
            Parameter space dict appropriate for this structure
        """
        from src.backtester.strategy_structure import PARAM_RANGES, EXIT_BARS_BY_TIMEFRAME
        from src.strategies.base import StopLossType, TakeProfitType

        # Get timeframe-specific exit bars
        exit_bars = EXIT_BARS_BY_TIMEFRAME.get(timeframe, PARAM_RANGES['exit_bars'])

        # Check if strategy is fully percentage-based (Numba kernel compatible)
        is_pct_based = structure.is_percentage_based

        if is_pct_based:
            # Full parametric optimization - use absolute space
            logger.info(
                f"Structure is percentage-based - using full parametric space"
            )
            return self.build_absolute_space(timeframe)

        # Non-percentage strategy: only optimize leverage and exit_bars
        # Preserve original SL/TP type and params
        sl_pct_original = structure.original_values.get('sl_pct', 0.02)
        tp_pct_original = structure.original_values.get('tp_pct', 0.0)

        space = {
            'sl_pct': [sl_pct_original],  # Keep original (single value)
            'tp_pct': [tp_pct_original],  # Keep original (single value)
            'leverage': LEVERAGE_VALUES.copy(),
            'exit_bars': exit_bars,
        }

        # Calculate combinations
        total = len(space['leverage']) * len(space['exit_bars'])

        logger.info(
            f"Structure is {structure.sl_type.value}-based SL - "
            f"optimizing only leverage and exit_bars "
            f"(preserving SL={sl_pct_original:.1%}, TP={tp_pct_original:.1%}) "
            f"({total} combinations)"
        )

        return space

    def _generate_typed_param_sets(
        self,
        sl_type: StopLossType,
        tp_type: Optional[TakeProfitType],
    ) -> Tuple[List[dict], dict]:
        """
        Generate parameter sets for typed SL/TP optimization.

        Returns:
            Tuple of (param_dicts, filter_stats) where each dict has
            type-specific parameters (atr_mult, rr_ratio, trailing_pct, etc.)
        """
        valid_sets = []
        filter_stats = {
            'total_raw': 0,
            'no_exit_filtered': 0,
            'liquidation_filtered': 0,
            'valid': 0,
        }

        # Get base parameters
        leverage_values = LEVERAGE_VALUES
        exit_bars_values = self.parameter_space.get('exit_bars', [0, 10, 20, 50, 100])

        # SL parameter values based on type
        if sl_type == StopLossType.PERCENTAGE:
            sl_params_list = [{'sl_pct': p} for p in self.parameter_space.get('sl_pct', [0.02])]
        elif sl_type == StopLossType.ATR:
            sl_params_list = [{'atr_multiplier': m} for m in ATR_SL_MULTIPLIERS]
        elif sl_type == StopLossType.STRUCTURE:
            sl_params_list = [{'lookback': lb} for lb in STRUCTURE_LOOKBACKS]
        elif sl_type == StopLossType.TRAILING:
            sl_params_list = [
                {'trailing_pct': t, 'activation_pct': a}
                for t in TRAILING_STOP_PCTS
                for a in TRAILING_ACTIVATION_PCTS
            ]
        else:
            sl_params_list = [{'sl_pct': 0.02}]  # Fallback

        # TP parameter values based on type
        if tp_type is None or tp_type == TakeProfitType.PERCENTAGE:
            tp_params_list = [{'tp_pct': p} for p in self.parameter_space.get('tp_pct', [0, 0.04])]
        elif tp_type == TakeProfitType.ATR:
            tp_params_list = [{'atr_multiplier': m} for m in ATR_TP_MULTIPLIERS]
        elif tp_type == TakeProfitType.RR_RATIO:
            tp_params_list = [{'rr_ratio': r} for r in RR_RATIOS]
        else:
            tp_params_list = [{'tp_pct': 0.0}]

        # Generate all combinations
        for sl_params in sl_params_list:
            for tp_params in tp_params_list:
                for lev in leverage_values:
                    for exit_b in exit_bars_values:
                        filter_stats['total_raw'] += 1

                        # FILTER 1: Must have exit condition (TP or time)
                        has_tp = tp_params.get('tp_pct', 0) > 0 or \
                                 tp_params.get('atr_multiplier', 0) > 0 or \
                                 tp_params.get('rr_ratio', 0) > 0
                        if not has_tp and exit_b == 0:
                            filter_stats['no_exit_filtered'] += 1
                            continue

                        # FILTER 2: ANTI-LIQUIDATION
                        # Estimate SL distance based on type for safe leverage calculation
                        if sl_type == StopLossType.PERCENTAGE:
                            estimated_sl = sl_params.get('sl_pct', 0.02)
                        elif sl_type == StopLossType.ATR:
                            # SL = ATR * multiplier, use typical ATR for estimation
                            estimated_sl = sl_params.get('atr_multiplier', 2.0) * TYPICAL_ATR_PCT
                        elif sl_type == StopLossType.STRUCTURE:
                            # Swing-based SL varies, use conservative estimate
                            estimated_sl = STRUCTURE_SL_ESTIMATE
                        elif sl_type == StopLossType.TRAILING:
                            # Trailing uses trailing_pct as initial SL distance
                            estimated_sl = sl_params.get('trailing_pct', 0.02)
                        else:
                            estimated_sl = 0.02

                        # Calculate safe leverage (same logic as _generate_parameter_sets)
                        max_safe_lev = calculate_safe_leverage(
                            sl_pct=estimated_sl,
                            max_leverage=20,
                            buffer_pct=10.0,
                        )
                        if lev > max_safe_lev:
                            filter_stats['liquidation_filtered'] += 1
                            continue

                        param_dict = {
                            'sl_type': sl_type,
                            'tp_type': tp_type,
                            'sl_params': sl_params,
                            'tp_params': tp_params,
                            'leverage': lev,
                            'exit_bars': exit_b,
                        }
                        valid_sets.append(param_dict)

        filter_stats['valid'] = len(valid_sets)
        return valid_sets, filter_stats

    def backtest_typed(
        self,
        pattern_signals: np.ndarray,
        ohlc_data: Dict[str, np.ndarray],
        directions: np.ndarray,
        max_leverages: np.ndarray,
        sl_type: StopLossType,
        tp_type: Optional[TakeProfitType] = TakeProfitType.PERCENTAGE,
        strategy_name: str = None,
        funding_cumsum: np.ndarray = None,
    ) -> pd.DataFrame:
        """
        Run parametric backtest with typed SL/TP support.

        This is the extended version of backtest_pattern() that supports
        all SL/TP types: ATR, STRUCTURE, TRAILING, RR_RATIO.

        Pre-calculation approach:
        - ATR/STRUCTURE values are converted to percentages BEFORE Numba kernel
        - TRAILING is handled dynamically inside the kernel with state tracking

        Args:
            pattern_signals: (n_bars, n_symbols) boolean array of entry signals
            ohlc_data: Dict with 'close', 'high', 'low' arrays (n_bars, n_symbols)
            directions: (n_bars, n_symbols) int8 array: 1=long, -1=short
            max_leverages: (n_symbols,) int32 array - per-coin max leverage
            sl_type: Type of stop loss (PERCENTAGE, ATR, STRUCTURE, TRAILING)
            tp_type: Type of take profit (PERCENTAGE, ATR, RR_RATIO, or None)
            strategy_name: Optional strategy name for log prefixing

        Returns:
            DataFrame with metrics for each parameter combination, sorted by score
        """
        log_prefix = f"[{strategy_name}] " if strategy_name else ""

        # Prepare arrays
        close = ohlc_data['close'].astype(np.float64)
        high = ohlc_data['high'].astype(np.float64)
        low = ohlc_data['low'].astype(np.float64)
        entries = pattern_signals.astype(np.bool_)
        dirs = directions.astype(np.int8)
        max_levs = max_leverages.astype(np.int32)

        n_bars, n_symbols = close.shape

        # Pre-calculate arrays if needed
        atr = None
        swing_low = None
        swing_high = None

        if sl_type == StopLossType.ATR or tp_type == TakeProfitType.ATR:
            atr = _calculate_atr_at_bars(high, low, close)
            logger.debug(f"{log_prefix}Pre-calculated ATR for {n_bars}x{n_symbols}")

        if sl_type == StopLossType.STRUCTURE:
            # Will be recalculated per lookback value
            pass

        # Generate typed parameter sets
        param_sets, filter_stats = self._generate_typed_param_sets(sl_type, tp_type)

        logger.info(
            f"{log_prefix}Typed parametric: {n_bars} bars, {n_symbols} symbols, "
            f"SL={sl_type.value}, TP={tp_type.value if tp_type else 'None'}, "
            f"{filter_stats['valid']}/{filter_stats['total_raw']} combos "
            f"(filtered: no_exit={filter_stats['no_exit_filtered']}, "
            f"anti-liq={filter_stats['liquidation_filtered']})"
        )

        # PRE-CALCULATE SWING CACHE for STRUCTURE-based SL
        # This avoids O(n_combos) recalculations - only O(n_lookbacks) = 4
        swing_cache = {}
        if sl_type == StopLossType.STRUCTURE:
            logger.debug(f"{log_prefix}Pre-calculating swing arrays for {len(STRUCTURE_LOOKBACKS)} lookbacks")
            for lookback in STRUCTURE_LOOKBACKS:
                swing_low_cached, swing_high_cached = calculate_swing_low_high_numba(high, low, lookback)
                swing_cache[lookback] = (swing_low_cached, swing_high_cached)
            logger.debug(f"{log_prefix}Swing cache ready")

        results = []

        # Use provided funding_cumsum or zeros if not provided
        if funding_cumsum is None:
            funding_cumsum = np.zeros((n_bars, n_symbols), dtype=np.float64)

        for params in param_sets:
            sl_params = params['sl_params']
            tp_params = params['tp_params']
            leverage = params['leverage']
            exit_bars = params['exit_bars']

            # Get structure arrays from pre-calculated cache
            if sl_type == StopLossType.STRUCTURE:
                lookback = sl_params.get('lookback', 10)
                swing_low, swing_high = swing_cache[lookback]

            # Convert SL to percentage array
            sl_pcts = _convert_sl_to_pct(
                sl_type=sl_type,
                entries=entries,
                close=close,
                directions=dirs,
                sl_pct=sl_params.get('sl_pct'),
                atr=atr,
                atr_multiplier=sl_params.get('atr_multiplier'),
                swing_low=swing_low,
                swing_high=swing_high,
                trailing_pct=sl_params.get('trailing_pct'),
            )

            # Convert TP to percentage array
            tp_pcts = _convert_tp_to_pct(
                tp_type=tp_type,
                entries=entries,
                close=close,
                directions=dirs,
                sl_pcts=sl_pcts,
                tp_pct=tp_params.get('tp_pct'),
                atr=atr,
                atr_multiplier=tp_params.get('atr_multiplier'),
                rr_ratio=tp_params.get('rr_ratio'),
            )

            # Determine trailing parameters
            is_trailing = sl_type == StopLossType.TRAILING
            trailing_activation_pct = sl_params.get('activation_pct', 0.01) if is_trailing else 0.0

            # Run simulation with v2 kernel
            equity_curve, trade_pnls, trade_wins = _simulate_single_param_set_v2(
                close, high, low, entries, dirs,
                sl_pcts, tp_pcts,
                leverage, max_levs, exit_bars,
                self.initial_capital, self.fee_rate, self.slippage,
                self.max_positions, self.risk_pct, self.min_notional,
                is_trailing, trailing_activation_pct, BREAKEVEN_BUFFER,
                funding_cumsum,
            )

            # Calculate metrics
            sharpe, max_dd, win_rate, expectancy, n_trades, total_return = _calc_metrics(
                equity_curve, trade_pnls, trade_wins, self.initial_capital, self.bars_per_year
            )

            # Build full params dict for reconstruction
            full_params = {
                'sl_type': sl_type.value,
                'tp_type': tp_type.value if tp_type else None,
                **sl_params,
                **tp_params,
                'leverage': leverage,
                'exit_bars': exit_bars,
            }

            # Extract representative sl_pct/tp_pct for ParametricResult
            # (median of non-zero values at entry bars)
            entry_sl_vals = sl_pcts[entries]
            entry_tp_vals = tp_pcts[entries]
            median_sl = float(np.median(entry_sl_vals[entry_sl_vals > 0])) if np.any(entry_sl_vals > 0) else 0.02
            median_tp = float(np.median(entry_tp_vals[entry_tp_vals > 0])) if np.any(entry_tp_vals > 0) else 0.0

            result = ParametricResult(
                sl_pct=median_sl,
                tp_pct=median_tp,
                leverage=leverage,
                exit_bars=exit_bars,
                sharpe=sharpe,
                max_drawdown=max_dd,
                win_rate=win_rate,
                expectancy=expectancy,
                total_trades=n_trades,
                total_return=total_return,
                score=0.0,
                sl_type=sl_type,
                tp_type=tp_type,
                params=full_params,
            )
            result.score = self._calculate_score(result)
            results.append(result)

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'sl_pct': r.sl_pct,
                'tp_pct': r.tp_pct,
                'leverage': r.leverage,
                'exit_bars': r.exit_bars,
                'sharpe': r.sharpe,
                'max_drawdown': r.max_drawdown,
                'win_rate': r.win_rate,
                'expectancy': r.expectancy,
                'total_trades': r.total_trades,
                'total_return': r.total_return,
                'score': r.score,
                'sl_type': r.sl_type.value,
                'tp_type': r.tp_type.value if r.tp_type else None,
                'params': r.params,
            }
            for r in results
        ])

        # Sort by score descending
        df = df.sort_values('score', ascending=False).reset_index(drop=True)

        if len(df) > 0:
            logger.info(
                f"{log_prefix}Typed parametric complete: "
                f"Best score={df['score'].iloc[0]:.2f}, "
                f"Sharpe={df['sharpe'].iloc[0]:.2f}, "
                f"SL={df['sl_pct'].iloc[0]:.1%}, TP={df['tp_pct'].iloc[0]:.1%}, "
                f"Lev={df['leverage'].iloc[0]}, Exit={df['exit_bars'].iloc[0]}"
            )
        else:
            logger.warning(f"{log_prefix}Typed parametric: no valid results")

        return df
