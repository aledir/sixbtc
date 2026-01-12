"""
6 Trailing Stop Configurations.

Trailing stops activate after a profit threshold is reached,
then trail the price at a specified distance.
"""

from dataclasses import dataclass, field


@dataclass
class TrailingConfig:
    """Definition of a trailing stop configuration."""

    id: str                                     # e.g., "TS_01"
    name: str                                   # e.g., "Percentage Trail"
    activation_type: str                        # "pct" or "atr"
    activation_params: dict = field(default_factory=dict)  # e.g., {"act_pct": [0.01, 0.02]}
    trail_type: str = "pct"                     # "pct" or "atr"
    trail_params: dict = field(default_factory=dict)  # e.g., {"trail_pct": [0.01, 0.015]}
    breakeven_first: bool = False               # If True, move to breakeven before trailing
    signal_kwargs_template: str = ""            # Template for Signal kwargs


# =============================================================================
# TRAILING STOP CONFIGURATIONS (6)
# =============================================================================

TRAILING_CONFIGS = [
    # TS_01: Percentage Trail
    TrailingConfig(
        id="TS_01",
        name="Percentage Trail",
        activation_type="pct",
        activation_params={"act_pct": [0.01, 0.015, 0.02, 0.03]},
        trail_type="pct",
        trail_params={"trail_pct": [0.005, 0.01, 0.015, 0.02]},
        breakeven_first=False,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_stop_pct': {trail_pct}",
    ),
    # TS_02: ATR Trail
    TrailingConfig(
        id="TS_02",
        name="ATR Trail",
        activation_type="pct",
        activation_params={"act_pct": [0.01, 0.015, 0.02]},
        trail_type="atr",
        trail_params={"trail_atr_mult": [1.5, 2.0, 2.5]},
        breakeven_first=False,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_atr_multiplier': {trail_atr_mult}",
    ),
    # TS_03: Breakeven + Trail
    TrailingConfig(
        id="TS_03",
        name="Breakeven Then Trail",
        activation_type="pct",
        activation_params={"act_pct": [0.01, 0.015]},
        trail_type="pct",
        trail_params={"trail_pct": [0.01, 0.015]},
        breakeven_first=True,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_stop_pct': {trail_pct}",
    ),
    # TS_04: Tight Trail (scalping)
    TrailingConfig(
        id="TS_04",
        name="Tight Trail",
        activation_type="pct",
        activation_params={"act_pct": [0.005, 0.0075, 0.01]},
        trail_type="pct",
        trail_params={"trail_pct": [0.003, 0.005, 0.0075]},
        breakeven_first=False,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_stop_pct': {trail_pct}",
    ),
    # TS_05: Wide Trail (trend following)
    TrailingConfig(
        id="TS_05",
        name="Wide Trail",
        activation_type="pct",
        activation_params={"act_pct": [0.03, 0.04, 0.05]},
        trail_type="pct",
        trail_params={"trail_pct": [0.02, 0.025, 0.03]},
        breakeven_first=False,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_stop_pct': {trail_pct}",
    ),
    # TS_06: Chandelier Exit Style
    TrailingConfig(
        id="TS_06",
        name="Chandelier Exit",
        activation_type="pct",
        activation_params={"act_pct": [0.01, 0.015]},
        trail_type="atr",
        trail_params={"trail_atr_mult": [2.0, 2.5, 3.0]},
        breakeven_first=False,
        signal_kwargs_template="'trailing_activation_pct': {act_pct}, 'trailing_atr_multiplier': {trail_atr_mult}",
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_trailing_config_by_id(ts_id: str) -> TrailingConfig | None:
    """Get a specific trailing config by ID."""
    for ts in TRAILING_CONFIGS:
        if ts.id == ts_id:
            return ts
    return None


def get_all_param_combinations(config: TrailingConfig) -> list[dict]:
    """
    Get all parameter combinations for a trailing config.

    Returns list of dicts with resolved parameters.
    """
    import itertools

    # Combine activation and trail params
    all_params = {**config.activation_params, **config.trail_params}

    if not all_params:
        return [{}]

    keys = list(all_params.keys())
    values = [all_params[k] for k in keys]

    combinations = []
    for combo in itertools.product(*values):
        combinations.append(dict(zip(keys, combo)))

    return combinations
