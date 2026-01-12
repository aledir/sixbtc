"""
5 Stop Loss Types - map to Signal.sl_type in strategies/base.py

Types:
- pct: Fixed percentage from entry
- atr: ATR-based dynamic stop
- structure: Based on price structure (swing low/high)
- volatility: Standard deviation based
- trailing: Trailing stop with activation
"""

from dataclasses import dataclass, field


@dataclass
class StopLossConfig:
    """Definition of a stop loss type configuration."""

    id: str                                    # e.g., "SL_01"
    name: str                                  # e.g., "Fixed Percentage"
    sl_type: str                               # Maps to StopLossType enum value
    params: dict = field(default_factory=dict)  # Parameter options
    requires_calculation: bool = False          # If True, needs price calculation in generate_signal
    signal_kwargs_template: str = ""            # Template for Signal kwargs


# =============================================================================
# STOP LOSS CONFIGURATIONS (5)
# =============================================================================

SL_CONFIGS = [
    # SL_01: Fixed Percentage
    StopLossConfig(
        id="SL_01",
        name="Fixed Percentage",
        sl_type="pct",
        params={"sl_pct": [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05]},
        requires_calculation=False,
        signal_kwargs_template="'sl_pct': {sl_pct}",
    ),
    # SL_02: ATR-Based
    StopLossConfig(
        id="SL_02",
        name="ATR-Based",
        sl_type="atr",
        params={"atr_mult": [1.0, 1.5, 2.0, 2.5, 3.0]},
        requires_calculation=False,
        signal_kwargs_template="'atr_stop_multiplier': {atr_mult}",
    ),
    # SL_03: Structure Low/High
    StopLossConfig(
        id="SL_03",
        name="Structure Low/High",
        sl_type="structure",
        params={"lookback": [3, 5, 10]},
        requires_calculation=True,
        signal_kwargs_template="'sl_price': sl_price",
    ),
    # SL_04: Swing Low/High
    StopLossConfig(
        id="SL_04",
        name="Swing Low/High",
        sl_type="structure",
        params={"swing_lookback": [10, 20]},
        requires_calculation=True,
        signal_kwargs_template="'sl_price': sl_price",
    ),
    # SL_05: Volatility (Std Dev)
    StopLossConfig(
        id="SL_05",
        name="Volatility Std Dev",
        sl_type="pct",
        params={"std_mult": [1.5, 2.0, 2.5]},
        requires_calculation=True,
        signal_kwargs_template="'sl_pct': sl_pct_calculated",
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_sl_config_by_id(sl_id: str) -> StopLossConfig | None:
    """Get a specific SL config by ID."""
    for sl in SL_CONFIGS:
        if sl.id == sl_id:
            return sl
    return None


def get_sl_calculation_code(config: StopLossConfig, direction: str, params: dict) -> str:
    """
    Generate the calculation code for SL types that require it.

    Args:
        config: The StopLossConfig
        direction: 'LONG' or 'SHORT'
        params: Resolved parameter values

    Returns:
        Python code string to calculate sl_price or sl_pct_calculated
    """
    if config.id == "SL_03":
        # Structure Low/High
        lookback = params.get('lookback', 5)
        if direction == 'LONG':
            return f'sl_price = df["low"].iloc[-{lookback}:].min()'
        else:
            return f'sl_price = df["high"].iloc[-{lookback}:].max()'

    elif config.id == "SL_04":
        # Swing Low/High
        lookback = params.get('swing_lookback', 10)
        if direction == 'LONG':
            return f'''# Find swing low
lows = df["low"].iloc[-{lookback}*3:]
swing_lows = lows[(lows.shift(1) > lows) & (lows.shift(-1) > lows)]
sl_price = swing_lows.iloc[-1] if len(swing_lows) > 0 else df["low"].iloc[-{lookback}:].min()'''
        else:
            return f'''# Find swing high
highs = df["high"].iloc[-{lookback}*3:]
swing_highs = highs[(highs.shift(1) < highs) & (highs.shift(-1) < highs)]
sl_price = swing_highs.iloc[-1] if len(swing_highs) > 0 else df["high"].iloc[-{lookback}:].max()'''

    elif config.id == "SL_05":
        # Volatility Std Dev
        std_mult = params.get('std_mult', 2.0)
        return f'''std_pct = df["close"].pct_change().rolling(20).std().iloc[-1]
sl_pct_calculated = std_pct * {std_mult}'''

    return ""
