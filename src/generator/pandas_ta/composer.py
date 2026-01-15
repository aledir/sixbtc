"""
Pandas-TA Strategy Composer

PtaBlueprint: Complete definition of a strategy before code generation.
PtaComposer: Generates random but coherent strategy blueprints using pandas_ta indicators.

Reuses exit mechanisms (11 logics), SL/TP/EC/TS from Unger catalogs.
"""

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional, Literal

from .catalogs import (
    # Indicators
    PtaIndicator,
    INDICATORS,
    INDICATORS_BY_ID,
    get_indicators_by_category,
    get_indicators_by_regime,
    get_indicators_by_direction,
    # Conditions
    ConditionType,
    INDICATOR_THRESHOLDS,
    get_conditions_for_category,
    get_thresholds_for_indicator,
    get_direction_for_condition,
    get_opposite_threshold,
    # Compatibility
    are_compatible,
    are_all_compatible,
    get_compatible_indicators,
    is_recommended_combo,
    filter_by_category_compatibility,
    filter_by_direction_compatibility,
)

# Reuse exit components from Unger
from src.generator.unger.catalogs import (
    # Exit Mechanisms
    ExitMechanism,
    EXIT_MECHANISMS,
    # SL/TP/Trailing
    StopLossConfig,
    SL_CONFIGS,
    TakeProfitConfig,
    TP_CONFIGS,
    TrailingConfig,
    TRAILING_CONFIGS,
    # Exit Conditions
    ExitCondition,
    EXIT_CONDITIONS,
    get_exits_by_direction,
)


@dataclass
class PtaEntryCondition:
    """
    A resolved entry condition for a pandas_ta indicator.

    Contains:
    - The indicator (PtaIndicator)
    - The condition type (threshold_below, crossed_above, etc.)
    - Resolved parameter values
    - The threshold value for the condition
    - The opposite threshold for BIDI strategies
    """

    indicator: PtaIndicator
    condition_type: ConditionType
    indicator_params: dict         # Resolved indicator parameters (e.g., {"length": 14})
    threshold: float               # Threshold value for condition (e.g., 30 for RSI < 30)
    threshold_high: Optional[float] = None  # For BETWEEN conditions
    threshold_opposite: Optional[float] = None  # For BIDI: opposite threshold (e.g., 70 for RSI)


@dataclass
class PtaBlueprint:
    """
    Complete blueprint of a pandas-ta strategy before code generation.

    Contains all components needed to generate a strategy class:
    - 1-3 entry conditions (indicator + condition type + params)
    - Exit mechanism defining TP/EC/TS usage
    - SL/TP/EC/TS configurations with resolved parameters
    - Metadata (timeframe, direction, coins)
    """

    # Meta
    strategy_id: str
    timeframe: str
    direction: str  # 'LONG', 'SHORT', 'BIDI'
    regime_type: str  # 'TREND', 'REVERSAL', 'MIXED'

    # Entry (1-3 indicators with conditions)
    entry_conditions: list[PtaEntryCondition]

    # Exit Mechanism (reused from Unger)
    exit_mechanism: ExitMechanism

    # Stop Loss (always required)
    sl_config: StopLossConfig
    sl_params: dict

    # Take Profit (optional, depends on exit_mechanism)
    tp_config: Optional[TakeProfitConfig] = None
    tp_params: Optional[dict] = None

    # Exit Condition (optional, depends on exit_mechanism)
    exit_condition: Optional[ExitCondition] = None
    exit_params: Optional[dict] = None

    # Trailing Stop (optional, depends on exit_mechanism)
    trailing_config: Optional[TrailingConfig] = None
    trailing_params: Optional[dict] = None

    # Coins from market regime
    trading_coins: list[str] = field(default_factory=list)

    # BIDI support: separate LONG/SHORT conditions (only used when direction='BIDI')
    entry_conditions_long: list[PtaEntryCondition] = field(default_factory=list)
    entry_conditions_short: list[PtaEntryCondition] = field(default_factory=list)

    def compute_hash(self) -> str:
        """
        Compute unique hash for this strategy combination.

        Used for:
        - Caching shuffle test results (base code property)
        - Deduplication of identical strategies
        """
        # Include entry conditions in hash
        entry_parts = []
        for ec in self.entry_conditions:
            entry_parts.append(ec.indicator.id)
            entry_parts.append(ec.condition_type.value)
            entry_parts.append(str(sorted(ec.indicator_params.items())))
            entry_parts.append(str(ec.threshold))
            if ec.threshold_high:
                entry_parts.append(str(ec.threshold_high))

        components = [
            # Entry conditions
            "|".join(entry_parts),
            # Direction
            self.direction,
            # Exit mechanism
            str(self.exit_mechanism.id),
            # SL
            self.sl_config.id,
            str(sorted(self.sl_params.items())),
            # TP
            self.tp_config.id if self.tp_config else "",
            str(sorted(self.tp_params.items())) if self.tp_params else "",
            # EC
            self.exit_condition.id if self.exit_condition else "",
            str(sorted(self.exit_params.items())) if self.exit_params else "",
            # TS
            self.trailing_config.id if self.trailing_config else "",
            str(sorted(self.trailing_params.items())) if self.trailing_params else "",
        ]
        return hashlib.md5("".join(components).encode()).hexdigest()[:12]

    def get_strategy_type(self) -> str:
        """
        Determine strategy type prefix from first indicator's category.

        Uses unified 5-type system: TRD, MOM, REV, VOL, CDL

        Returns:
            One of: TRD, MOM, REV, VOL, CDL

        Raises:
            ValueError: If category is unknown (no fallback - fail fast)
        """
        if not self.entry_conditions:
            raise ValueError("No entry conditions - cannot determine strategy type")

        first_cat = self.entry_conditions[0].indicator.category
        # Unified 5-type mapping
        category_map = {
            "momentum": "MOM",
            "trend": "TRD",
            "crossover": "TRD",  # Crossovers are trend-following
            "volatility": "REV",  # Volatility bands = mean reversion
            "volume": "VOL",
            "statistics": "REV",  # Statistical indicators = mean reversion
            "candle": "CDL",  # Candlestick patterns
            "cycle": "REV",  # Cycle indicators = mean reversion
        }
        if first_cat not in category_map:
            raise ValueError(
                f"Unknown indicator category: '{first_cat}'. "
                f"Add mapping in pandas_ta/composer.py"
            )
        return category_map[first_cat]

    def get_class_name(self) -> str:
        """Generate strategy class name."""
        return f"PtaStrat_{self.get_strategy_type()}_{self.strategy_id}"

    def describe(self) -> str:
        """Human-readable description."""
        entry_desc = " + ".join([
            f"{ec.indicator.id}({ec.condition_type.value})"
            for ec in self.entry_conditions
        ])
        parts = [
            f"Entry: {entry_desc}",
            f"Dir: {self.direction}",
            f"Exit: {self.exit_mechanism.name}",
            f"SL: {self.sl_config.name}",
        ]
        if self.tp_config:
            parts.append(f"TP: {self.tp_config.name}")
        if self.exit_condition:
            parts.append(f"EC: {self.exit_condition.name}")
        if self.trailing_config:
            parts.append(f"TS: {self.trailing_config.name}")
        return " | ".join(parts)


class PtaComposer:
    """
    Generates strategy blueprints by combining pandas_ta indicators.

    Ensures:
    - Indicator compatibility (no redundant combinations)
    - Direction consistency (entry matches requested direction)
    - Regime coherence (TREND or REVERSAL indicators)
    - Parameter diversity (market-sensible values)
    """

    def __init__(self, config: dict):
        """
        Initialize composer with config.

        Args:
            config: Application config dict (from config.yaml)
        """
        self.config = config
        self._rng = random.Random()

        # Weights for number of indicators
        self._num_indicator_weights = [0.30, 0.50, 0.20]  # 1, 2, 3 indicators

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)

    def compose(
        self,
        timeframe: str,
        direction: str,
        regime_type: str,
        coins: list[str],
        num_indicators: Optional[int] = None,
    ) -> PtaBlueprint:
        """
        Generate a random but coherent strategy blueprint.

        Args:
            timeframe: Target timeframe (e.g., '15m', '1h')
            direction: 'LONG', 'SHORT', or 'BIDI'
            regime_type: 'TREND', 'REVERSAL', or 'MIXED'
            coins: List of coins for this strategy
            num_indicators: Number of indicators (1-3), None for random

        Returns:
            Complete PtaBlueprint ready for code generation
        """
        # BIDI: use separate composition with dual condition sets
        if direction == 'BIDI':
            return self._compose_bidi(timeframe, regime_type, coins, num_indicators)

        # 1. Determine number of indicators
        if num_indicators is None:
            num_indicators = self._rng.choices([1, 2, 3], weights=self._num_indicator_weights)[0]
        num_indicators = min(max(1, num_indicators), 3)

        # 2. Get available indicators for regime and direction
        available = self._get_available_indicators(regime_type, direction)
        if not available:
            # Fallback to all indicators if none match
            available = list(INDICATORS)

        # 3. Build entry conditions
        entry_conditions = self._build_entry_conditions(
            available, num_indicators, direction
        )

        # 4. Select Exit Mechanism
        exit_mech = self._rng.choice(EXIT_MECHANISMS)

        # 5. Select SL (always required)
        sl_config = self._rng.choice(SL_CONFIGS)
        sl_params = self._resolve_params(sl_config.params)

        # 6. Select TP (if used by mechanism)
        tp_config = None
        tp_params = None
        if exit_mech.uses_tp:
            tp_config = self._rng.choice(TP_CONFIGS)
            tp_params = self._resolve_params(tp_config.params)

        # 7. Select Exit Condition (if used by mechanism)
        exit_cond = None
        exit_params = None
        if exit_mech.uses_ec:
            valid_exits = get_exits_by_direction(direction)
            if valid_exits:
                exit_cond = self._rng.choice(valid_exits)
                exit_params = self._resolve_params(exit_cond.params)

        # 8. Select Trailing Stop (if used by mechanism)
        trailing = None
        trailing_params = None
        if exit_mech.uses_ts:
            trailing = self._rng.choice(TRAILING_CONFIGS)
            trailing_params = self._resolve_params(
                {**trailing.activation_params, **trailing.trail_params}
            )

        # 9. Generate unique ID
        strategy_id = uuid.uuid4().hex[:8]

        return PtaBlueprint(
            strategy_id=strategy_id,
            timeframe=timeframe,
            direction=direction,
            regime_type=regime_type,
            entry_conditions=entry_conditions,
            exit_mechanism=exit_mech,
            sl_config=sl_config,
            sl_params=sl_params,
            tp_config=tp_config,
            tp_params=tp_params,
            exit_condition=exit_cond,
            exit_params=exit_params,
            trailing_config=trailing,
            trailing_params=trailing_params,
            trading_coins=list(set(coins)),
        )

    def _get_available_indicators(
        self,
        regime_type: str,
        direction: str,
    ) -> list[PtaIndicator]:
        """Get indicators compatible with regime and direction."""
        # Filter by regime
        if regime_type in ("TREND", "REVERSAL"):
            available = get_indicators_by_regime(regime_type)
        else:
            available = list(INDICATORS)

        # Filter by direction
        if direction != "BIDI":
            available = [
                ind for ind in available
                if ind.direction == direction or ind.direction == "BIDI"
            ]

        return available

    def _build_entry_conditions(
        self,
        available: list[PtaIndicator],
        count: int,
        direction: str,
    ) -> list[PtaEntryCondition]:
        """
        Build N entry conditions with compatible indicators.

        Ensures:
        - No incompatible pairs
        - Category diversity (different categories preferred)
        - Market-sensible thresholds
        """
        conditions = []
        selected_ids = []

        # Shuffle for randomness
        shuffled = available.copy()
        self._rng.shuffle(shuffled)

        for _ in range(count):
            # Find a compatible indicator
            candidate = None
            for ind in shuffled:
                if ind.id in selected_ids:
                    continue
                # Check compatibility with already selected
                if selected_ids:
                    compatible = all(
                        are_compatible(ind.id, sel_id)
                        for sel_id in selected_ids
                    )
                    if not compatible:
                        continue
                candidate = ind
                break

            if candidate is None:
                # No more compatible indicators
                break

            # Create entry condition
            condition = self._create_entry_condition(candidate, direction)
            conditions.append(condition)
            selected_ids.append(candidate.id)

        return conditions

    def _create_entry_condition(
        self,
        indicator: PtaIndicator,
        direction: str,
    ) -> PtaEntryCondition:
        """Create an entry condition for an indicator."""
        # Get valid condition types for this indicator's category
        valid_conditions = get_conditions_for_category(indicator.category)
        if not valid_conditions:
            valid_conditions = [ConditionType.THRESHOLD_BELOW, ConditionType.THRESHOLD_ABOVE]

        # NOTE: Direction filtering REMOVED to explore all possibilities
        # Let the backtest decide if unconventional combos work
        # (e.g., LONG with RSI > 80 momentum continuation)

        # Select condition type (all valid conditions equally likely)
        condition_type = self._rng.choice(valid_conditions)

        # Resolve indicator parameters
        indicator_params = self._resolve_params(indicator.params)

        # Get threshold
        thresholds = get_thresholds_for_indicator(indicator.id, condition_type)
        threshold = self._rng.choice(thresholds) if thresholds else 0

        # For BETWEEN, need two thresholds
        threshold_high = None
        if condition_type == ConditionType.BETWEEN:
            ind_thresholds = INDICATOR_THRESHOLDS.get(indicator.id, {})
            low_vals = ind_thresholds.get("neutral_low", ind_thresholds.get("oversold", [30]))
            high_vals = ind_thresholds.get("neutral_high", ind_thresholds.get("overbought", [70]))
            threshold = self._rng.choice(low_vals) if low_vals else 30
            threshold_high = self._rng.choice(high_vals) if high_vals else 70

        # Calculate opposite threshold for BIDI strategies
        # e.g., RSI < 30 (long) → RSI > 70 (short)
        threshold_opposite = get_opposite_threshold(indicator.id, threshold, condition_type)

        return PtaEntryCondition(
            indicator=indicator,
            condition_type=condition_type,
            indicator_params=indicator_params,
            threshold=threshold,
            threshold_high=threshold_high,
            threshold_opposite=threshold_opposite,
        )

    def _resolve_params(self, params: dict) -> dict:
        """
        Resolve parameter lists to single values.

        Args:
            params: Dict of {param_name: [list of possible values]}

        Returns:
            Dict of {param_name: single_value}
        """
        if not params:
            return {}
        return {k: self._rng.choice(v) for k, v in params.items()}

    def _compose_bidi(
        self,
        timeframe: str,
        regime_type: str,
        coins: list[str],
        num_indicators: Optional[int] = None,
    ) -> PtaBlueprint:
        """
        Compose a BIDI strategy with separate LONG and SHORT entry conditions.

        BIDI strategies have two independent entry logics:
        - LONG conditions (e.g., RSI < 30, price crossed above MA)
        - SHORT conditions (e.g., RSI > 70, price crossed below MA)

        The strategy generates long_signal and short_signal separately,
        and entry_signal = long_signal | short_signal.

        Args:
            timeframe: Target timeframe
            regime_type: 'TREND', 'REVERSAL', or 'MIXED'
            coins: List of coins for this strategy
            num_indicators: Number of indicators (1-3), None for random

        Returns:
            PtaBlueprint with populated entry_conditions_long and entry_conditions_short
        """
        # 1. Determine number of indicators
        if num_indicators is None:
            num_indicators = self._rng.choices([1, 2, 3], weights=self._num_indicator_weights)[0]
        num_indicators = min(max(1, num_indicators), 3)

        # 2. Get available indicators for regime (BIDI accepts all directions)
        if regime_type in ("TREND", "REVERSAL"):
            available = get_indicators_by_regime(regime_type)
        else:
            available = list(INDICATORS)

        if not available:
            available = list(INDICATORS)

        # 3. Build LONG entry conditions (favoring LONG-compatible thresholds)
        entry_conditions_long = self._build_directional_conditions(
            available, num_indicators, 'LONG'
        )

        # 4. Build SHORT entry conditions (favoring SHORT-compatible thresholds)
        entry_conditions_short = self._build_directional_conditions(
            available, num_indicators, 'SHORT'
        )

        # 5. Select Exit Mechanism
        exit_mech = self._rng.choice(EXIT_MECHANISMS)

        # 6. Select SL (always required)
        sl_config = self._rng.choice(SL_CONFIGS)
        sl_params = self._resolve_params(sl_config.params)

        # 7. Select TP (if used by mechanism)
        tp_config = None
        tp_params = None
        if exit_mech.uses_tp:
            tp_config = self._rng.choice(TP_CONFIGS)
            tp_params = self._resolve_params(tp_config.params)

        # 8. Select Exit Condition (if used by mechanism)
        # For BIDI, use LONG exit conditions (will check direction at runtime)
        exit_cond = None
        exit_params = None
        if exit_mech.uses_ec:
            valid_exits = get_exits_by_direction('LONG')
            if valid_exits:
                exit_cond = self._rng.choice(valid_exits)
                exit_params = self._resolve_params(exit_cond.params)

        # 9. Select Trailing Stop (if used by mechanism)
        trailing = None
        trailing_params = None
        if exit_mech.uses_ts:
            trailing = self._rng.choice(TRAILING_CONFIGS)
            trailing_params = self._resolve_params(
                {**trailing.activation_params, **trailing.trail_params}
            )

        # 10. Generate unique ID
        strategy_id = uuid.uuid4().hex[:8]

        return PtaBlueprint(
            strategy_id=strategy_id,
            timeframe=timeframe,
            direction='BIDI',
            regime_type=regime_type,
            # Use LONG as primary for get_strategy_type()
            entry_conditions=entry_conditions_long,
            entry_conditions_long=entry_conditions_long,
            entry_conditions_short=entry_conditions_short,
            exit_mechanism=exit_mech,
            sl_config=sl_config,
            sl_params=sl_params,
            tp_config=tp_config,
            tp_params=tp_params,
            exit_condition=exit_cond,
            exit_params=exit_params,
            trailing_config=trailing,
            trailing_params=trailing_params,
            trading_coins=list(set(coins)),
        )

    def _build_directional_conditions(
        self,
        available: list[PtaIndicator],
        count: int,
        direction: str,
    ) -> list[PtaEntryCondition]:
        """
        Build entry conditions specifically for a direction.

        For LONG: prefers threshold_below, crossed_above (oversold conditions)
        For SHORT: prefers threshold_above, crossed_below (overbought conditions)

        Args:
            available: List of available indicators
            count: Number of conditions to build
            direction: 'LONG' or 'SHORT'

        Returns:
            List of PtaEntryCondition tuned for the specified direction
        """
        conditions = []
        selected_ids = []

        # Shuffle for randomness
        shuffled = available.copy()
        self._rng.shuffle(shuffled)

        for _ in range(count):
            # Find a compatible indicator
            candidate = None
            for ind in shuffled:
                if ind.id in selected_ids:
                    continue
                # Check compatibility with already selected
                if selected_ids:
                    compatible = all(
                        are_compatible(ind.id, sel_id)
                        for sel_id in selected_ids
                    )
                    if not compatible:
                        continue
                candidate = ind
                break

            if candidate is None:
                break

            # Create directional entry condition
            condition = self._create_directional_condition(candidate, direction)
            conditions.append(condition)
            selected_ids.append(candidate.id)

        return conditions

    def _create_directional_condition(
        self,
        indicator: PtaIndicator,
        direction: str,
    ) -> PtaEntryCondition:
        """
        Create an entry condition specifically tuned for a direction.

        Args:
            indicator: The indicator to use
            direction: 'LONG' or 'SHORT'

        Returns:
            PtaEntryCondition with direction-appropriate condition and threshold
        """
        # Get valid condition types for this indicator's category
        valid_conditions = get_conditions_for_category(indicator.category)
        if not valid_conditions:
            valid_conditions = [ConditionType.THRESHOLD_BELOW, ConditionType.THRESHOLD_ABOVE]

        # Filter conditions to match direction
        # LONG: prefers threshold_below, crossed_above (buy low)
        # SHORT: prefers threshold_above, crossed_below (sell high)
        long_conditions = [
            ConditionType.THRESHOLD_BELOW,
            ConditionType.CROSSED_ABOVE,
            ConditionType.SLOPE_UP,
        ]
        short_conditions = [
            ConditionType.THRESHOLD_ABOVE,
            ConditionType.CROSSED_BELOW,
            ConditionType.SLOPE_DOWN,
        ]

        if direction == 'LONG':
            directional = [c for c in valid_conditions if c in long_conditions]
        else:
            directional = [c for c in valid_conditions if c in short_conditions]

        # Use directional conditions if available, otherwise use any valid
        if directional:
            condition_type = self._rng.choice(directional)
        else:
            condition_type = self._rng.choice(valid_conditions)

        # Resolve indicator parameters
        indicator_params = self._resolve_params(indicator.params)

        # Get threshold appropriate for direction
        thresholds = get_thresholds_for_indicator(indicator.id, condition_type)
        threshold = self._rng.choice(thresholds) if thresholds else 0

        # For BETWEEN, need two thresholds
        threshold_high = None
        if condition_type == ConditionType.BETWEEN:
            ind_thresholds = INDICATOR_THRESHOLDS.get(indicator.id, {})
            low_vals = ind_thresholds.get("neutral_low", ind_thresholds.get("oversold", [30]))
            high_vals = ind_thresholds.get("neutral_high", ind_thresholds.get("overbought", [70]))
            threshold = self._rng.choice(low_vals) if low_vals else 30
            threshold_high = self._rng.choice(high_vals) if high_vals else 70

        return PtaEntryCondition(
            indicator=indicator,
            condition_type=condition_type,
            indicator_params=indicator_params,
            threshold=threshold,
            threshold_high=threshold_high,
            threshold_opposite=None,  # Not needed for BIDI (we have separate conditions)
        )

    def compose_with_recommended_combo(
        self,
        timeframe: str,
        coins: list[str],
    ) -> Optional[PtaBlueprint]:
        """
        Generate a blueprint using a recommended indicator combination.

        Returns None if no recommended combo available.
        """
        from .catalogs.compatibility import RECOMMENDED_COMBOS

        if not RECOMMENDED_COMBOS:
            return None

        # Select a random recommended combo
        combo = self._rng.choice(list(RECOMMENDED_COMBOS.keys()))
        combo_info = RECOMMENDED_COMBOS[combo]

        # Get indicators for this combo
        indicator_ids = list(combo)
        indicators = [INDICATORS_BY_ID.get(ind_id) for ind_id in indicator_ids]
        indicators = [ind for ind in indicators if ind is not None]

        if not indicators:
            return None

        # Determine direction based on regime
        regime_type = combo_info.get("regime", "MIXED")
        direction = self._rng.choice(["LONG", "SHORT"])

        # Build entry conditions
        entry_conditions = []
        for ind in indicators:
            condition = self._create_entry_condition(ind, direction)
            entry_conditions.append(condition)

        # Build the rest of the blueprint
        exit_mech = self._rng.choice(EXIT_MECHANISMS)

        sl_config = self._rng.choice(SL_CONFIGS)
        sl_params = self._resolve_params(sl_config.params)

        tp_config = None
        tp_params = None
        if exit_mech.uses_tp:
            tp_config = self._rng.choice(TP_CONFIGS)
            tp_params = self._resolve_params(tp_config.params)

        exit_cond = None
        exit_params = None
        if exit_mech.uses_ec:
            valid_exits = get_exits_by_direction(direction)
            if valid_exits:
                exit_cond = self._rng.choice(valid_exits)
                exit_params = self._resolve_params(exit_cond.params)

        trailing = None
        trailing_params = None
        if exit_mech.uses_ts:
            trailing = self._rng.choice(TRAILING_CONFIGS)
            trailing_params = self._resolve_params(
                {**trailing.activation_params, **trailing.trail_params}
            )

        strategy_id = uuid.uuid4().hex[:8]

        return PtaBlueprint(
            strategy_id=strategy_id,
            timeframe=timeframe,
            direction=direction,
            regime_type=regime_type,
            entry_conditions=entry_conditions,
            exit_mechanism=exit_mech,
            sl_config=sl_config,
            sl_params=sl_params,
            tp_config=tp_config,
            tp_params=tp_params,
            exit_condition=exit_cond,
            exit_params=exit_params,
            trailing_config=trailing,
            trailing_params=trailing_params,
            trading_coins=list(set(coins)),
        )
