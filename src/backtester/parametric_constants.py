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

    # 4h: Medium-term positions
    # SL 4-15%, TP 0-30%, exit 0-64h
    '4h': {
        'sl_pct': [0.04, 0.06, 0.08, 0.10, 0.15],
        'tp_pct': [0, 0.08, 0.12, 0.18, 0.25, 0.30],
        'exit_bars': [0, 2, 4, 8, 16],
    },

    # 1d: Long-term directional
    # SL 6-15%, TP 0-30%, exit 0-5d
    '1d': {
        'sl_pct': [0.06, 0.08, 0.10, 0.12, 0.15],
        'tp_pct': [0, 0.10, 0.15, 0.20, 0.25, 0.30],
        'exit_bars': [0, 1, 2, 3, 5],
    },
}


def get_param_space(timeframe: str) -> Dict[str, List]:
    """
    Get parameter space for a timeframe.

    Args:
        timeframe: Timeframe string ('5m', '15m', '30m', '1h', '4h', '1d')

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
