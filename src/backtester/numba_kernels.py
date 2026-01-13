"""
Numba-optimized kernels for parametric backtesting.

These functions are JIT-compiled with Numba for maximum performance.
All heavy computation is done here instead of Python loops.
"""

from numba import jit, prange
import numpy as np


@jit(nopython=True, cache=True, parallel=True)
def calculate_swing_low_high_numba(
    high: np.ndarray,
    low: np.ndarray,
    lookback: int
) -> tuple:
    """
    Calculate swing low/high arrays with Numba parallelization.

    Uses explicit loops instead of np.min/np.max on slices for better
    performance in Numba (avoids temporary allocations).

    Args:
        high: High prices array (n_bars, n_symbols)
        low: Low prices array (n_bars, n_symbols)
        lookback: Number of bars to look back for swing detection

    Returns:
        Tuple of (swing_low, swing_high) arrays, same shape as input
    """
    n_bars, n_symbols = low.shape
    swing_low = np.empty((n_bars, n_symbols), dtype=np.float64)
    swing_high = np.empty((n_bars, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):  # Parallel across symbols
        for i in range(n_bars):
            start_idx = max(0, i - lookback)

            # Explicit loop for min (faster than np.min on slice in Numba)
            min_val = low[start_idx, j]
            for k in range(start_idx + 1, i + 1):
                if low[k, j] < min_val:
                    min_val = low[k, j]
            swing_low[i, j] = min_val

            # Explicit loop for max
            max_val = high[start_idx, j]
            for k in range(start_idx + 1, i + 1):
                if high[k, j] > max_val:
                    max_val = high[k, j]
            swing_high[i, j] = max_val

    return swing_low, swing_high


@jit(nopython=True, cache=True, parallel=True)
def calculate_atr_at_bars_numba(
    atr: np.ndarray,
    signal_bars: np.ndarray
) -> np.ndarray:
    """
    Extract ATR values at specific signal bar indices.

    Args:
        atr: ATR array (n_bars, n_symbols)
        signal_bars: Bar indices where signals occur (n_signals, n_symbols)

    Returns:
        ATR values at signal bars (n_signals, n_symbols)
    """
    n_signals, n_symbols = signal_bars.shape
    result = np.empty((n_signals, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_signals):
            bar_idx = signal_bars[i, j]
            if 0 <= bar_idx < atr.shape[0]:
                result[i, j] = atr[bar_idx, j]
            else:
                result[i, j] = np.nan

    return result


@jit(nopython=True, cache=True, parallel=True)
def convert_sl_structure_to_pct_numba(
    entry_prices: np.ndarray,
    swing_low: np.ndarray,
    swing_high: np.ndarray,
    signal_bars: np.ndarray,
    directions: np.ndarray,
    buffer_pct: float
) -> np.ndarray:
    """
    Convert STRUCTURE-based stop loss to percentage.

    For LONG: SL = swing_low * (1 - buffer)
    For SHORT: SL = swing_high * (1 + buffer)

    Args:
        entry_prices: Entry prices (n_signals, n_symbols)
        swing_low: Pre-calculated swing lows (n_bars, n_symbols)
        swing_high: Pre-calculated swing highs (n_bars, n_symbols)
        signal_bars: Bar indices of signals (n_signals, n_symbols)
        directions: Trade directions, 1=LONG, -1=SHORT (n_signals, n_symbols)
        buffer_pct: Buffer percentage (e.g., 0.002 = 0.2%)

    Returns:
        SL percentages (n_signals, n_symbols), clamped to [0.5%, 20%]
    """
    n_signals, n_symbols = entry_prices.shape
    sl_pcts = np.empty((n_signals, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_signals):
            bar_idx = signal_bars[i, j]

            # Invalid bar index - use fallback
            if bar_idx < 0 or bar_idx >= swing_low.shape[0]:
                sl_pcts[i, j] = 0.02  # 2% fallback
                continue

            entry = entry_prices[i, j]
            direction = directions[i, j]

            if direction > 0:  # LONG
                sl_price = swing_low[bar_idx, j] * (1.0 - buffer_pct)
                sl_pcts[i, j] = (entry - sl_price) / entry
            else:  # SHORT
                sl_price = swing_high[bar_idx, j] * (1.0 + buffer_pct)
                sl_pcts[i, j] = (sl_price - entry) / entry

            # Clamp to reasonable range [0.5%, 20%]
            if sl_pcts[i, j] < 0.005:
                sl_pcts[i, j] = 0.005
            elif sl_pcts[i, j] > 0.20:
                sl_pcts[i, j] = 0.20

    return sl_pcts


@jit(nopython=True, cache=True, parallel=True)
def calculate_atr_full_numba(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14
) -> np.ndarray:
    """
    Calculate ATR for all bars/symbols using Numba.

    Uses EMA smoothing for ATR calculation.

    Args:
        high: High prices (n_bars, n_symbols)
        low: Low prices (n_bars, n_symbols)
        close: Close prices (n_bars, n_symbols)
        period: ATR period (default 14)

    Returns:
        atr: (n_bars, n_symbols) - ATR values, first `period` bars are NaN
    """
    n_bars, n_symbols = close.shape
    atr = np.empty((n_bars, n_symbols), dtype=np.float64)
    alpha = 2.0 / (period + 1)

    for j in prange(n_symbols):
        # First bar: TR = high - low
        atr[0, j] = high[0, j] - low[0, j]

        # Calculate True Range and EMA for rest
        for i in range(1, n_bars):
            high_low = high[i, j] - low[i, j]
            high_close = abs(high[i, j] - close[i - 1, j])
            low_close = abs(low[i, j] - close[i - 1, j])

            # True Range is max of the three
            tr = high_low
            if high_close > tr:
                tr = high_close
            if low_close > tr:
                tr = low_close

            # EMA smoothing
            atr[i, j] = alpha * tr + (1.0 - alpha) * atr[i - 1, j]

        # Set warmup period to NaN
        for i in range(period):
            atr[i, j] = np.nan

    return atr


@jit(nopython=True, cache=True, parallel=True)
def convert_sl_atr_to_pct_numba(
    entries: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    atr_multiplier: float,
    fallback_pct: float = 0.02
) -> np.ndarray:
    """
    Convert ATR-based SL to percentage for all entries.

    Args:
        entries: (n_bars, n_symbols) bool - entry signals
        close: (n_bars, n_symbols) close prices
        atr: (n_bars, n_symbols) ATR values
        atr_multiplier: Multiplier for ATR
        fallback_pct: Fallback SL if ATR invalid (default 2%)

    Returns:
        sl_pcts: (n_bars, n_symbols) - SL percentages
    """
    n_bars, n_symbols = close.shape
    sl_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_bars):
            if entries[i, j]:
                atr_val = atr[i, j]
                close_val = close[i, j]
                if atr_val > 0.0 and close_val > 0.0 and not np.isnan(atr_val):
                    sl_pcts[i, j] = (atr_val * atr_multiplier) / close_val
                else:
                    sl_pcts[i, j] = fallback_pct

    return sl_pcts


@jit(nopython=True, cache=True, parallel=True)
def convert_tp_atr_to_pct_numba(
    entries: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray,
    atr_multiplier: float,
    fallback_pct: float = 0.04
) -> np.ndarray:
    """
    Convert ATR-based TP to percentage for all entries.

    Args:
        entries: (n_bars, n_symbols) bool - entry signals
        close: (n_bars, n_symbols) close prices
        atr: (n_bars, n_symbols) ATR values
        atr_multiplier: Multiplier for ATR
        fallback_pct: Fallback TP if ATR invalid (default 4%)

    Returns:
        tp_pcts: (n_bars, n_symbols) - TP percentages
    """
    n_bars, n_symbols = close.shape
    tp_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_bars):
            if entries[i, j]:
                atr_val = atr[i, j]
                close_val = close[i, j]
                if atr_val > 0.0 and close_val > 0.0 and not np.isnan(atr_val):
                    tp_pcts[i, j] = (atr_val * atr_multiplier) / close_val
                else:
                    tp_pcts[i, j] = fallback_pct

    return tp_pcts


@jit(nopython=True, cache=True, parallel=True)
def convert_tp_rr_to_pct_numba(
    entries: np.ndarray,
    sl_pcts: np.ndarray,
    rr_ratio: float
) -> np.ndarray:
    """
    Convert RR_RATIO TP to percentage (TP = SL * ratio).

    Args:
        entries: (n_bars, n_symbols) bool - entry signals
        sl_pcts: (n_bars, n_symbols) SL percentages
        rr_ratio: Risk-reward ratio

    Returns:
        tp_pcts: (n_bars, n_symbols) - TP percentages
    """
    n_bars, n_symbols = sl_pcts.shape
    tp_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_bars):
            if entries[i, j]:
                tp_pcts[i, j] = sl_pcts[i, j] * rr_ratio

    return tp_pcts


@jit(nopython=True, cache=True, parallel=True)
def convert_sl_structure_to_pct_2d_numba(
    entries: np.ndarray,
    close: np.ndarray,
    directions: np.ndarray,
    swing_low: np.ndarray,
    swing_high: np.ndarray,
    min_pct: float = 0.005,
    max_pct: float = 0.20
) -> np.ndarray:
    """
    Convert STRUCTURE SL to percentage for 2D arrays (used by parametric backtest).

    Args:
        entries: (n_bars, n_symbols) bool - entry signals
        close: (n_bars, n_symbols) close prices (entry prices)
        directions: (n_bars, n_symbols) int8 - 1=long, -1=short
        swing_low: (n_bars, n_symbols) swing lows
        swing_high: (n_bars, n_symbols) swing highs
        min_pct: Minimum SL percentage (default 0.5%)
        max_pct: Maximum SL percentage (default 20%)

    Returns:
        sl_pcts: (n_bars, n_symbols) - SL percentages
    """
    n_bars, n_symbols = close.shape
    sl_pcts = np.zeros((n_bars, n_symbols), dtype=np.float64)

    for j in prange(n_symbols):
        for i in range(n_bars):
            if entries[i, j]:
                entry_price = close[i, j]
                direction = directions[i, j]

                if direction > 0:  # LONG
                    sl_price = swing_low[i, j]
                    sl_pct = (entry_price - sl_price) / entry_price
                else:  # SHORT
                    sl_price = swing_high[i, j]
                    sl_pct = (sl_price - entry_price) / entry_price

                # Clamp to range
                if sl_pct < min_pct:
                    sl_pct = min_pct
                elif sl_pct > max_pct:
                    sl_pct = max_pct

                sl_pcts[i, j] = sl_pct

    return sl_pcts


def warmup_numba_kernels():
    """
    Warm up Numba JIT compilation by calling functions with dummy data.

    Call this at startup to avoid compilation delay on first real use.
    With cache=True, compiled code is saved to disk for subsequent runs.
    """
    # Small arrays for fast compilation
    h = np.random.rand(100, 5).astype(np.float64)
    l = np.random.rand(100, 5).astype(np.float64)
    c = np.random.rand(100, 5).astype(np.float64) + 100
    entries = np.zeros((100, 5), dtype=np.bool_)
    entries[50, :] = True
    directions = np.ones((100, 5), dtype=np.int8)
    signal_bars = np.array([[50, 50, 50, 50, 50]], dtype=np.int64)
    entry_prices = np.random.rand(1, 5).astype(np.float64) + 100
    directions_1d = np.ones((1, 5), dtype=np.float64)

    # Trigger compilation for all functions
    _ = calculate_swing_low_high_numba(h, l, 10)

    atr = calculate_atr_full_numba(h, l, c, 14)
    _ = calculate_atr_at_bars_numba(atr, signal_bars)

    swing_low, swing_high = calculate_swing_low_high_numba(h, l, 10)
    _ = convert_sl_structure_to_pct_numba(
        entry_prices, swing_low, swing_high,
        signal_bars, directions_1d, 0.002
    )

    _ = convert_sl_atr_to_pct_numba(entries, c, atr, 2.0)
    _ = convert_tp_atr_to_pct_numba(entries, c, atr, 3.0)

    sl_pcts = np.full((100, 5), 0.02, dtype=np.float64)
    _ = convert_tp_rr_to_pct_numba(entries, sl_pcts, 2.0)

    _ = convert_sl_structure_to_pct_2d_numba(entries, c, directions, swing_low, swing_high)
