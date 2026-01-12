"""
5 Take Profit Types - map to Signal.tp_type in strategies/base.py

Types:
- pct: Fixed percentage from entry
- rr_ratio: Risk/Reward ratio based on SL
- atr: ATR-based dynamic target
- structure: Based on price structure (resistance/support)
- fib: Fibonacci extension
"""

from dataclasses import dataclass, field


@dataclass
class TakeProfitConfig:
    """Definition of a take profit type configuration."""

    id: str                                    # e.g., "TP_01"
    name: str                                  # e.g., "Fixed Percentage"
    tp_type: str                               # Maps to TakeProfitType enum value
    params: dict = field(default_factory=dict)  # Parameter options
    requires_calculation: bool = False          # If True, needs price calculation in generate_signal
    signal_kwargs_template: str = ""            # Template for Signal kwargs


# =============================================================================
# TAKE PROFIT CONFIGURATIONS (5)
# =============================================================================

TP_CONFIGS = [
    # TP_01: Fixed Percentage
    TakeProfitConfig(
        id="TP_01",
        name="Fixed Percentage",
        tp_type="pct",
        params={"tp_pct": [0.02, 0.03, 0.04, 0.05, 0.08, 0.10]},
        requires_calculation=False,
        signal_kwargs_template="'tp_pct': {tp_pct}",
    ),
    # TP_02: Risk Multiple (R:R Ratio)
    TakeProfitConfig(
        id="TP_02",
        name="Risk Multiple",
        tp_type="rr_ratio",
        params={"rr_ratio": [1.5, 2.0, 2.5, 3.0]},
        requires_calculation=False,
        signal_kwargs_template="'rr_ratio': {rr_ratio}",
    ),
    # TP_03: ATR-Based
    TakeProfitConfig(
        id="TP_03",
        name="ATR-Based",
        tp_type="atr",
        params={"atr_mult": [2.0, 3.0, 4.0, 5.0]},
        requires_calculation=False,
        signal_kwargs_template="'atr_take_multiplier': {atr_mult}",
    ),
    # TP_04: Structure High/Low
    TakeProfitConfig(
        id="TP_04",
        name="Structure High/Low",
        tp_type="structure",
        params={"lookback": [10, 20, 50]},
        requires_calculation=True,
        signal_kwargs_template="'tp_price': tp_price",
    ),
    # TP_05: Fibonacci Extension
    TakeProfitConfig(
        id="TP_05",
        name="Fibonacci Extension",
        tp_type="pct",
        params={"fib_level": [1.618, 2.0, 2.618]},
        requires_calculation=True,
        signal_kwargs_template="'tp_pct': tp_pct_calculated",
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tp_config_by_id(tp_id: str) -> TakeProfitConfig | None:
    """Get a specific TP config by ID."""
    for tp in TP_CONFIGS:
        if tp.id == tp_id:
            return tp
    return None


def get_tp_calculation_code(config: TakeProfitConfig, direction: str, params: dict) -> str:
    """
    Generate the calculation code for TP types that require it.

    Args:
        config: The TakeProfitConfig
        direction: 'LONG' or 'SHORT'
        params: Resolved parameter values

    Returns:
        Python code string to calculate tp_price or tp_pct_calculated
    """
    if config.id == "TP_04":
        # Structure High/Low
        lookback = params.get('lookback', 20)
        if direction == 'LONG':
            return f'tp_price = df["high"].iloc[-{lookback}:].max()'
        else:
            return f'tp_price = df["low"].iloc[-{lookback}:].min()'

    elif config.id == "TP_05":
        # Fibonacci Extension
        fib_level = params.get('fib_level', 1.618)
        return f'''# Calculate swing range for Fibonacci
recent_high = df["high"].iloc[-50:].max()
recent_low = df["low"].iloc[-50:].min()
swing_range = (recent_high - recent_low) / df["close"].iloc[-1]
tp_pct_calculated = swing_range * {fib_level}'''

    return ""
