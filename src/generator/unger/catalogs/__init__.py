"""
Unger Catalogs - Complete component library for strategy generation.

Components:
- 128 Entry Conditions (entries.py) - 68 base + 60 pandas_ta advanced
- 92 Entry Filters (filters.py) - 32 indicator-based + 60 Unger patterns
- 15 Exit Conditions (exits.py)
- 5 SL Types (sl_types.py)
- 5 TP Types (tp_types.py)
- 6 Trailing Configs (trailing.py)
- 11 Exit Mechanisms (exit_mechanisms.py)
"""

# Entry Conditions
from .entries import (
    EntryCondition,
    ALL_ENTRIES,
    BREAKOUT_ENTRIES,
    CROSSOVER_ENTRIES,
    THRESHOLD_ENTRIES,
    VOLATILITY_ENTRIES,
    CANDLESTICK_ENTRIES,
    MEAN_REVERSION_ENTRIES,
    TREND_ADVANCED_ENTRIES,
    MOMENTUM_ADVANCED_ENTRIES,
    VOLUME_FLOW_ENTRIES,
    get_entries_by_category,
    get_entries_by_direction,
    get_entry_by_id,
    get_category_counts as get_entry_category_counts,
)

# Entry Filters
from .filters import (
    EntryFilter,
    ALL_FILTERS,
    TREND_FILTERS,
    MOMENTUM_FILTERS,
    VOLATILITY_FILTERS,
    VOLUME_FILTERS,
    STRUCTURE_FILTERS,
    UNGER_PATTERN_FILTERS,
    get_compatible_filters,
    get_filters_by_category,
    get_filter_by_id,
    get_category_counts as get_filter_category_counts,
)

# Exit Conditions
from .exits import (
    ExitCondition,
    EXIT_CONDITIONS,
    REVERSAL_EXITS,
    TIME_EXITS,
    PROFIT_PROTECTION_EXITS,
    get_exits_by_category,
    get_exits_by_direction,
    get_exit_by_id,
    get_category_counts as get_exit_category_counts,
)

# Stop Loss Types
from .sl_types import (
    StopLossConfig,
    SL_CONFIGS,
    get_sl_config_by_id,
    get_sl_calculation_code,
)

# Take Profit Types
from .tp_types import (
    TakeProfitConfig,
    TP_CONFIGS,
    get_tp_config_by_id,
    get_tp_calculation_code,
)

# Trailing Stop Configs
from .trailing import (
    TrailingConfig,
    TRAILING_CONFIGS,
    get_trailing_config_by_id,
    get_all_param_combinations as get_trailing_param_combinations,
)

# Exit Mechanisms
from .exit_mechanisms import (
    ExitMechanism,
    EXIT_MECHANISMS,
    get_mechanism_by_id,
    get_mechanisms_with_tp,
    get_mechanisms_with_ec,
    get_mechanisms_with_ts,
    get_simple_mechanisms,
    get_or_mechanisms,
)


__all__ = [
    # Entry Conditions
    "EntryCondition",
    "ALL_ENTRIES",
    "BREAKOUT_ENTRIES",
    "CROSSOVER_ENTRIES",
    "THRESHOLD_ENTRIES",
    "VOLATILITY_ENTRIES",
    "CANDLESTICK_ENTRIES",
    "MEAN_REVERSION_ENTRIES",
    "TREND_ADVANCED_ENTRIES",
    "MOMENTUM_ADVANCED_ENTRIES",
    "VOLUME_FLOW_ENTRIES",
    "get_entries_by_category",
    "get_entries_by_direction",
    "get_entry_by_id",
    "get_entry_category_counts",
    # Entry Filters
    "EntryFilter",
    "ALL_FILTERS",
    "TREND_FILTERS",
    "MOMENTUM_FILTERS",
    "VOLATILITY_FILTERS",
    "VOLUME_FILTERS",
    "STRUCTURE_FILTERS",
    "UNGER_PATTERN_FILTERS",
    "get_compatible_filters",
    "get_filters_by_category",
    "get_filter_by_id",
    "get_filter_category_counts",
    # Exit Conditions
    "ExitCondition",
    "EXIT_CONDITIONS",
    "REVERSAL_EXITS",
    "TIME_EXITS",
    "PROFIT_PROTECTION_EXITS",
    "get_exits_by_category",
    "get_exits_by_direction",
    "get_exit_by_id",
    "get_exit_category_counts",
    # Stop Loss Types
    "StopLossConfig",
    "SL_CONFIGS",
    "get_sl_config_by_id",
    "get_sl_calculation_code",
    # Take Profit Types
    "TakeProfitConfig",
    "TP_CONFIGS",
    "get_tp_config_by_id",
    "get_tp_calculation_code",
    # Trailing Stop Configs
    "TrailingConfig",
    "TRAILING_CONFIGS",
    "get_trailing_config_by_id",
    "get_trailing_param_combinations",
    # Exit Mechanisms
    "ExitMechanism",
    "EXIT_MECHANISMS",
    "get_mechanism_by_id",
    "get_mechanisms_with_tp",
    "get_mechanisms_with_ec",
    "get_mechanisms_with_ts",
    "get_simple_mechanisms",
    "get_or_mechanisms",
]
