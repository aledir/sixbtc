"""
Parametric Backtest Constants

Per-timeframe parameter spaces for strategy optimization.
Values are empirically validated ranges for crypto trading.

NOT in config.yaml because:
- Technical optimization parameters, not user-configurable settings
- Values derived from market behavior analysis
- Changing requires backtesting expertise

Each timeframe has tuned SL/TP/exit_bars based on typical price movements.
Leverage values are tested against per-coin max from CoinRegistry at runtime.
"""

from typing import Dict, List

# Leverage values to test
# At runtime, each coin's max_leverage from CoinRegistry caps this
# Example: BTC max=50x uses up to 40, SHIB max=5x uses up to 5
LEVERAGE_VALUES: List[int] = [1, 2, 3, 5, 10, 20, 40]


# =============================================================================
# MULTI-TYPE SL/TP PARAMETERS
# =============================================================================

# ATR-based stop loss multipliers
# SL distance = ATR * multiplier
ATR_SL_MULTIPLIERS: List[float] = [1.5, 2.0, 2.5, 3.0, 4.0]

# ATR-based take profit multipliers
# TP distance = ATR * multiplier
ATR_TP_MULTIPLIERS: List[float] = [2.0, 3.0, 4.0, 5.0, 6.0]

# Risk-Reward ratio for TP calculation
# TP distance = SL distance * RR ratio
RR_RATIOS: List[float] = [1.5, 2.0, 2.5, 3.0, 4.0]

# Trailing stop percentages
# Initial distance and trail distance from high water mark
TRAILING_STOP_PCTS: List[float] = [0.01, 0.015, 0.02, 0.025, 0.03]

# Trailing stop activation thresholds
# Trailing activates when profit exceeds this percentage
TRAILING_ACTIVATION_PCTS: List[float] = [0.005, 0.01, 0.015, 0.02]

# Structure-based SL lookback periods
# Number of bars to look back for swing low/high
STRUCTURE_LOOKBACKS: List[int] = [5, 10, 15, 20]

# Breakeven buffer for trailing stops
# Prevents SL from going below entry + buffer (long) or above entry - buffer (short)
BREAKEVEN_BUFFER: float = 0.002  # 0.2%

# Typical ATR for crypto (price-normalized)
# Used to estimate SL distance for anti-liquidation filter when using ATR-based SL
# Crypto 24/7 markets typically have 1-2% daily ATR, we use conservative 1.5%
TYPICAL_ATR_PCT: float = 0.015  # 1.5%

# Conservative SL estimate for structure-based stops
# Swing-based SL can vary widely, use conservative estimate for anti-liq filter
STRUCTURE_SL_ESTIMATE: float = 0.02  # 2%


# Per-timeframe parameter spaces
# Format: {'sl_pct': [...], 'tp_pct': [...], 'exit_bars': [...]}
#
# Design rationale:
# - SL/TP scale with timeframe (higher TF = wider stops)
# - exit_bars maintain reasonable holding periods per TF
# - tp_pct=0 means no take-profit (rely on exit_bars or SL)
# - exit_bars=0 means no time exit (rely on SL/TP)

PARAM_SPACE: Dict[str, Dict[str, List]] = {
    # 5m: Scalping, tight stops, quick exits
    # SL 0.5-2%, TP 0-5%, exit 0-13h
    '5m': {
        'sl_pct': [0.005, 0.0075, 0.01, 0.015, 0.02],
        'tp_pct': [0, 0.01, 0.015, 0.02, 0.03, 0.05],
        'exit_bars': [0, 20, 40, 80, 160],
    },

    # 15m: Short-term momentum (reference timeframe)
    # SL 1-5%, TP 0-10%, exit 0-25h
    '15m': {
        'sl_pct': [0.01, 0.015, 0.02, 0.03, 0.05],
        'tp_pct': [0, 0.02, 0.03, 0.05, 0.07, 0.10],
        'exit_bars': [0, 10, 20, 50, 100],
    },

    # 30m: Intraday swings
    # SL 1.5-6%, TP 0-15%, exit 0-30h
    '30m': {
        'sl_pct': [0.015, 0.02, 0.03, 0.04, 0.06],
        'tp_pct': [0, 0.03, 0.04, 0.06, 0.10, 0.15],
        'exit_bars': [0, 6, 12, 30, 60],
    },

    # 1h: Short-term trends
    # SL 2-10%, TP 0-20%, exit 0-32h
    '1h': {
        'sl_pct': [0.02, 0.03, 0.04, 0.06, 0.10],
        'tp_pct': [0, 0.04, 0.06, 0.10, 0.15, 0.20],
        'exit_bars': [0, 4, 8, 16, 32],
    },

    # 2h: Medium-term swing trades
    # SL 3-10%, TP 0-25%, exit 0-48h
    '2h': {
        'sl_pct': [0.03, 0.04, 0.05, 0.07, 0.10],
        'tp_pct': [0, 0.06, 0.08, 0.12, 0.18, 0.25],
        'exit_bars': [0, 3, 6, 12, 24],
    },
}


def get_param_space(timeframe: str) -> Dict[str, List]:
    """
    Get parameter space for a timeframe.

    Args:
        timeframe: Timeframe string ('5m', '15m', '30m', '1h', '2h')

    Returns:
        Dict with 'sl_pct', 'tp_pct', 'exit_bars', 'leverage' lists

    Raises:
        ValueError: If timeframe not supported
    """
    if timeframe not in PARAM_SPACE:
        supported = list(PARAM_SPACE.keys())
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. "
            f"Supported: {supported}"
        )

    space = PARAM_SPACE[timeframe].copy()
    space['leverage'] = LEVERAGE_VALUES.copy()
    return space


def count_combinations(timeframe: str) -> int:
    """
    Count valid parameter combinations for a timeframe.

    Excludes invalid combinations (tp=0 AND exit_bars=0).

    Args:
        timeframe: Timeframe string

    Returns:
        Number of valid parameter combinations
    """
    space = get_param_space(timeframe)

    total = (
        len(space['sl_pct']) *
        len(space['tp_pct']) *
        len(space['leverage']) *
        len(space['exit_bars'])
    )

    # Subtract invalid: tp=0 combined with exit_bars=0
    invalid = len(space['sl_pct']) * len(space['leverage'])

    return total - invalid
