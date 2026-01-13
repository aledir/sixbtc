"""
Strategy Structure Detection

Detects the structure of a strategy (SL type, TP type, exit mechanisms)
to enable structure-aware parametric optimization.

Instead of forcing all strategies to use percentage-based SL/TP,
this module detects what the strategy actually uses and returns
which parameters should be optimized.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging

from src.strategies.base import StopLossType, TakeProfitType, ExitType

logger = logging.getLogger(__name__)


# =============================================================================
# PARAMETER RANGES FOR EACH TYPE
# =============================================================================

PARAM_RANGES: Dict[str, List[Any]] = {
    # SL percentage params
    'sl_pct': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06],

    # SL ATR params
    'atr_stop_multiplier': [1.5, 2.0, 2.5, 3.0, 4.0, 5.0],

    # SL Trailing params
    'trailing_stop_pct': [0.01, 0.015, 0.02, 0.025, 0.03, 0.04],
    'trailing_activation_pct': [0.005, 0.01, 0.015, 0.02, 0.025],

    # TP percentage params
    'tp_pct': [0.0, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10, 0.15],

    # TP RR ratio params
    'rr_ratio': [1.5, 2.0, 2.5, 3.0, 4.0],

    # TP ATR params
    'atr_take_multiplier': [2.0, 3.0, 4.0, 5.0, 6.0],

    # Common params
    'leverage': [1, 2, 3, 5, 10, 20],
    'exit_bars': [0, 8, 12, 20, 40, 60, 100],
}

# Per-timeframe exit_bars scaling
EXIT_BARS_BY_TIMEFRAME: Dict[str, List[int]] = {
    '15m': [0, 8, 16, 24, 48, 96],      # 0, 2h, 4h, 6h, 12h, 24h
    '30m': [0, 4, 8, 12, 24, 48],       # 0, 2h, 4h, 6h, 12h, 24h
    '1h':  [0, 4, 6, 12, 24, 48],       # 0, 4h, 6h, 12h, 24h, 48h
    '2h':  [0, 3, 6, 12, 24, 36],       # 0, 6h, 12h, 24h, 48h, 72h
    '4h':  [0, 3, 6, 12, 18, 24],       # 0, 12h, 24h, 48h, 72h, 96h
}


# =============================================================================
# STRATEGY STRUCTURE DATACLASS
# =============================================================================

@dataclass
class StrategyStructure:
    """
    Detected structure of a strategy for parametric optimization.

    Attributes:
        sl_type: Type of stop loss (PERCENTAGE, ATR, STRUCTURE, TRAILING)
        tp_type: Type of take profit (PERCENTAGE, RR_RATIO, ATR, None)
        uses_trailing: Whether trailing stop is enabled
        uses_time_exit: Whether time-based exit is enabled
        optimizable_params: List of parameter names that can be optimized
        fixed_params: Dict of parameters that should not be changed
        original_values: Original parameter values from strategy
    """
    sl_type: StopLossType
    tp_type: Optional[TakeProfitType]
    uses_trailing: bool
    uses_time_exit: bool
    optimizable_params: List[str] = field(default_factory=list)
    fixed_params: Dict[str, Any] = field(default_factory=dict)
    original_values: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_percentage_based(self) -> bool:
        """
        Check if strategy uses percentage-based SL/TP params.

        NOTE: Trailing stop is an ADDITIONAL exit mechanism, not a replacement
        for the primary SL. A strategy with sl_type=PERCENTAGE + trailing is
        still percentage-based for optimization purposes.

        Only sl_type=TRAILING means the trailing IS the primary SL.
        """
        return (
            self.sl_type == StopLossType.PERCENTAGE and
            (self.tp_type is None or self.tp_type == TakeProfitType.PERCENTAGE)
            # uses_trailing does NOT disqualify - it's additive, not substitutive
        )


# =============================================================================
# DETECTION FUNCTION
# =============================================================================

def detect_structure(strategy_instance) -> StrategyStructure:
    """
    Detect the structure of a strategy from its class attributes.

    Args:
        strategy_instance: Instantiated strategy object

    Returns:
        StrategyStructure with detected types and optimizable parameters
    """
    # Read SL type
    sl_type = getattr(strategy_instance, 'sl_type', StopLossType.PERCENTAGE)
    if isinstance(sl_type, str):
        try:
            sl_type = StopLossType(sl_type)
        except ValueError:
            sl_type = StopLossType.PERCENTAGE

    # Read TP type (may not exist)
    tp_type = getattr(strategy_instance, 'tp_type', None)
    if isinstance(tp_type, str):
        try:
            tp_type = TakeProfitType(tp_type)
        except ValueError:
            tp_type = None

    # Check for trailing stop
    trailing_pct = getattr(strategy_instance, 'trailing_stop_pct', None)
    trailing_act = getattr(strategy_instance, 'trailing_activation_pct', None)
    uses_trailing = trailing_pct is not None and trailing_pct > 0

    # Check for time-based exit
    exit_bars = getattr(strategy_instance, 'exit_after_bars', 0)
    uses_time_exit = exit_bars is not None and exit_bars > 0

    # Build list of optimizable parameters
    optimizable = []
    fixed = {}
    original = {}

    # Leverage is always optimizable
    optimizable.append('leverage')
    original['leverage'] = getattr(strategy_instance, 'LEVERAGE', None) or \
                           getattr(strategy_instance, 'leverage', 1)

    # SL parameters based on type
    if sl_type == StopLossType.PERCENTAGE:
        optimizable.append('sl_pct')
        original['sl_pct'] = getattr(strategy_instance, 'SL_PCT', None) or \
                             getattr(strategy_instance, 'sl_pct', 0.02)

    elif sl_type == StopLossType.ATR:
        optimizable.append('atr_stop_multiplier')
        original['atr_stop_multiplier'] = getattr(strategy_instance, 'atr_stop_multiplier', 2.0)
        # ATR period is usually fixed
        fixed['atr_period'] = getattr(strategy_instance, 'atr_period', 14)

    elif sl_type == StopLossType.TRAILING:
        optimizable.extend(['trailing_stop_pct', 'trailing_activation_pct'])
        original['trailing_stop_pct'] = trailing_pct or 0.02
        original['trailing_activation_pct'] = trailing_act or 0.01

    elif sl_type == StopLossType.STRUCTURE:
        # Structure-based SL is price-dependent, not optimizable
        # Keep the lookback parameter as fixed
        fixed['sl_lookback'] = getattr(strategy_instance, 'sl_lookback', 10)
        logger.debug(f"Structure-based SL detected - SL not optimizable")

    elif sl_type == StopLossType.VOLATILITY:
        # Volatility-based could optimize std multiplier
        optimizable.append('sl_std_multiplier')
        original['sl_std_multiplier'] = getattr(strategy_instance, 'sl_std_multiplier', 2.0)

    # TP parameters based on type
    if tp_type == TakeProfitType.PERCENTAGE:
        optimizable.append('tp_pct')
        original['tp_pct'] = getattr(strategy_instance, 'TP_PCT', None) or \
                             getattr(strategy_instance, 'tp_pct', 0.04)

    elif tp_type == TakeProfitType.RR_RATIO:
        optimizable.append('rr_ratio')
        original['rr_ratio'] = getattr(strategy_instance, 'rr_ratio', 2.0)

    elif tp_type == TakeProfitType.ATR:
        optimizable.append('atr_take_multiplier')
        original['atr_take_multiplier'] = getattr(strategy_instance, 'atr_take_multiplier', 3.0)

    elif tp_type is None:
        # No TP - must have time exit or exit conditions
        original['tp_pct'] = 0.0

    # Time-based exit
    if uses_time_exit:
        optimizable.append('exit_bars')
        original['exit_bars'] = exit_bars
    else:
        # Even if not using time exit, include it as option
        # (parametric might find value > 0 works better)
        optimizable.append('exit_bars')
        original['exit_bars'] = 0

    # Additional trailing params if trailing is used alongside other SL
    if uses_trailing and sl_type != StopLossType.TRAILING:
        if 'trailing_stop_pct' not in optimizable:
            optimizable.append('trailing_stop_pct')
            original['trailing_stop_pct'] = trailing_pct or 0.02
        if 'trailing_activation_pct' not in optimizable:
            optimizable.append('trailing_activation_pct')
            original['trailing_activation_pct'] = trailing_act or 0.01

    return StrategyStructure(
        sl_type=sl_type,
        tp_type=tp_type,
        uses_trailing=uses_trailing,
        uses_time_exit=uses_time_exit,
        optimizable_params=optimizable,
        fixed_params=fixed,
        original_values=original,
    )


def build_parameter_space(
    structure: StrategyStructure,
    timeframe: str = '1h',
    max_leverage: int = 20,
) -> Dict[str, List[Any]]:
    """
    Build parameter space based on detected structure.

    Args:
        structure: Detected strategy structure
        timeframe: Strategy timeframe (for exit_bars scaling)
        max_leverage: Maximum leverage cap

    Returns:
        Dict of parameter name -> list of values to test
    """
    space = {}

    for param in structure.optimizable_params:
        if param == 'leverage':
            # Cap leverage at max_leverage
            space['leverage'] = [l for l in PARAM_RANGES['leverage'] if l <= max_leverage]

        elif param == 'exit_bars':
            # Use timeframe-specific values
            space['exit_bars'] = EXIT_BARS_BY_TIMEFRAME.get(
                timeframe,
                PARAM_RANGES['exit_bars']
            )

        elif param in PARAM_RANGES:
            space[param] = PARAM_RANGES[param]

        else:
            logger.warning(f"Unknown param '{param}' - skipping")

    return space


def get_param_count(structure: StrategyStructure, timeframe: str = '1h') -> int:
    """Calculate total number of parameter combinations for this structure."""
    space = build_parameter_space(structure, timeframe)
    count = 1
    for values in space.values():
        count *= len(values)
    return count
