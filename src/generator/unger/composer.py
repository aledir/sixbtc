"""
Strategy Composer - Combines catalog components into complete strategy blueprints.

StrategyBlueprint: Complete definition of a strategy before code generation.
StrategyComposer: Generates random but coherent strategy blueprints.
"""

import hashlib
import itertools
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .catalogs import (
    # Entry
    EntryCondition,
    ALL_ENTRIES,
    get_entries_by_direction,
    # Filters
    EntryFilter,
    get_compatible_filters,
    # Exits
    ExitCondition,
    EXIT_CONDITIONS,
    get_exits_by_direction,
    # SL/TP/Trailing
    StopLossConfig,
    SL_CONFIGS,
    TakeProfitConfig,
    TP_CONFIGS,
    TrailingConfig,
    TRAILING_CONFIGS,
    # Exit Mechanisms
    ExitMechanism,
    EXIT_MECHANISMS,
)


@dataclass
class StrategyBlueprint:
    """
    Complete blueprint of a strategy before code generation.

    Contains all components needed to generate a strategy class:
    - Entry condition with resolved parameters
    - 0-2 entry filters with resolved parameters
    - Exit mechanism defining TP/EC/TS usage
    - SL/TP/EC/TS configurations with resolved parameters
    - Metadata (timeframe, direction, coins)
    """

    # Meta
    strategy_id: str
    timeframe: str
    direction: str  # 'LONG', 'SHORT', 'BIDI'

    # Entry
    entry_condition: EntryCondition
    entry_params: dict  # Resolved parameter values

    # Exit Mechanism
    exit_mechanism: ExitMechanism

    # Stop Loss (always required)
    sl_config: StopLossConfig
    sl_params: dict

    # Fields with defaults must come after fields without defaults
    entry_filters: list[tuple[EntryFilter, dict]] = field(default_factory=list)

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
    pattern_coins: list[str] = field(default_factory=list)

    def compute_hash(self) -> str:
        """
        Compute unique hash for this strategy combination.

        Used for:
        - Caching shuffle test results (base code property)
        - Deduplication of identical strategies
        """
        components = [
            self.entry_condition.id,
            str(sorted(self.entry_params.items())),
            str([f[0].id for f in self.entry_filters]),
            str([str(sorted(f[1].items())) for f in self.entry_filters]),
            str(self.exit_mechanism.id),
            self.sl_config.id,
            str(sorted(self.sl_params.items())),
            self.tp_config.id if self.tp_config else "",
            str(sorted(self.tp_params.items())) if self.tp_params else "",
            self.exit_condition.id if self.exit_condition else "",
            str(sorted(self.exit_params.items())) if self.exit_params else "",
            self.trailing_config.id if self.trailing_config else "",
            str(sorted(self.trailing_params.items())) if self.trailing_params else "",
        ]
        return hashlib.md5("".join(components).encode()).hexdigest()[:12]

    def get_strategy_type(self) -> str:
        """
        Determine strategy type prefix from entry category.

        Returns:
            BRK (breakout), CRS (crossover), THR (threshold),
            VOL (volatility), CDL (candlestick), REV (mean_reversion)
        """
        category_map = {
            "breakout": "BRK",
            "crossover": "CRS",
            "threshold": "THR",
            "volatility": "VOL",
            "candlestick": "CDL",
            "mean_reversion": "REV",
        }
        return category_map.get(self.entry_condition.category, "UNG")

    def get_class_name(self) -> str:
        """Generate strategy class name."""
        return f"UngStrat_{self.get_strategy_type()}_{self.strategy_id}"

    def describe(self) -> str:
        """Human-readable description."""
        parts = [
            f"Entry: {self.entry_condition.name}",
            f"Filters: {len(self.entry_filters)}",
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


class StrategyComposer:
    """
    Generates strategy blueprints by combining catalog components.

    Ensures:
    - Filter compatibility (no overlapping indicators with entry)
    - Exit mechanism coherence (uses components defined by mechanism)
    - Direction consistency (entry, filters, exits match direction)
    """

    def __init__(self, config: dict):
        """
        Initialize composer with config.

        Args:
            config: Application config dict (from config.yaml)
        """
        self.config = config
        self._rng = random.Random()

    def set_seed(self, seed: int) -> None:
        """Set random seed for reproducibility."""
        self._rng.seed(seed)

    def compose_random(
        self,
        timeframe: str,
        direction: str,
        coins: list[str],
        num_filters: Optional[int] = None,
        entry_override: Optional[EntryCondition] = None,
    ) -> StrategyBlueprint:
        """
        Generate a random but coherent strategy blueprint.

        Args:
            timeframe: Target timeframe (e.g., '15m', '1h')
            direction: 'LONG', 'SHORT', or 'BIDI'
            coins: List of coins for this strategy
            num_filters: Number of filters (0-2), None for random
            entry_override: Force specific entry condition (for regime-aware generation)

        Returns:
            Complete StrategyBlueprint ready for code generation
        """
        # 1. Select Entry Condition (or use override)
        if entry_override:
            entry = entry_override
        else:
            entries = get_entries_by_direction(direction)
            entry = self._rng.choice(entries)
        entry_params = self._resolve_params(entry.params)

        # 2. Select 0-2 Entry Filters (orthogonal categories, no overlapping indicators)
        if num_filters is None:
            num_filters = self._rng.choice([0, 0, 1, 1, 1, 2])  # Weighted toward 1

        compatible_filters = get_compatible_filters(entry, direction)
        selected_filters = self._select_orthogonal_filters(
            compatible_filters, num_filters
        )

        # 3. Select Exit Mechanism
        exit_mech = self._rng.choice(EXIT_MECHANISMS)

        # 4. Select SL (always required)
        sl_config = self._rng.choice(SL_CONFIGS)
        sl_params = self._resolve_params(sl_config.params)

        # 5. Select TP (if used by mechanism)
        tp_config = None
        tp_params = None
        if exit_mech.uses_tp:
            tp_config = self._rng.choice(TP_CONFIGS)
            tp_params = self._resolve_params(tp_config.params)

        # 6. Select Exit Condition (if used by mechanism)
        exit_cond = None
        exit_params = None
        if exit_mech.uses_ec:
            valid_exits = get_exits_by_direction(direction)
            exit_cond = self._rng.choice(valid_exits)
            exit_params = self._resolve_params(exit_cond.params)

        # 7. Select Trailing Stop (if used by mechanism)
        trailing = None
        trailing_params = None
        if exit_mech.uses_ts:
            trailing = self._rng.choice(TRAILING_CONFIGS)
            trailing_params = self._resolve_params(
                {**trailing.activation_params, **trailing.trail_params}
            )

        # 8. Generate unique ID
        strategy_id = uuid.uuid4().hex[:8]

        return StrategyBlueprint(
            strategy_id=strategy_id,
            timeframe=timeframe,
            direction=direction,
            entry_condition=entry,
            entry_params=entry_params,
            entry_filters=selected_filters,
            exit_mechanism=exit_mech,
            sl_config=sl_config,
            sl_params=sl_params,
            tp_config=tp_config,
            tp_params=tp_params,
            exit_condition=exit_cond,
            exit_params=exit_params,
            trailing_config=trailing,
            trailing_params=trailing_params,
            pattern_coins=list(set(coins)),
        )

    def compose_exhaustive(
        self,
        timeframe: str,
        direction: str,
        coins: list[str],
        max_strategies: int = 1000,
    ) -> list[StrategyBlueprint]:
        """
        Generate strategies exhaustively (limited by max_strategies).

        Iterates through entry × filter × mechanism × SL/TP/EC/TS combinations.
        Useful for systematic exploration.

        Args:
            timeframe: Target timeframe
            direction: 'LONG', 'SHORT', or 'BIDI'
            coins: List of coins
            max_strategies: Maximum strategies to generate

        Returns:
            List of StrategyBlueprints
        """
        blueprints = []
        seen_hashes = set()

        entries = get_entries_by_direction(direction)

        for entry in entries:
            entry_param_combos = self._get_param_combinations(entry.params)
            compatible_filters = get_compatible_filters(entry, direction)

            for entry_params in entry_param_combos:
                # 0 filters
                for exit_mech in EXIT_MECHANISMS:
                    bp = self._build_blueprint(
                        timeframe, direction, coins, entry, entry_params,
                        [], exit_mech
                    )
                    if bp and bp.compute_hash() not in seen_hashes:
                        seen_hashes.add(bp.compute_hash())
                        blueprints.append(bp)
                        if len(blueprints) >= max_strategies:
                            return blueprints

                # 1 filter
                for f1 in compatible_filters:
                    f1_param_combos = self._get_param_combinations(f1.params)
                    for f1_params in f1_param_combos:
                        for exit_mech in EXIT_MECHANISMS:
                            bp = self._build_blueprint(
                                timeframe, direction, coins, entry, entry_params,
                                [(f1, f1_params)], exit_mech
                            )
                            if bp and bp.compute_hash() not in seen_hashes:
                                seen_hashes.add(bp.compute_hash())
                                blueprints.append(bp)
                                if len(blueprints) >= max_strategies:
                                    return blueprints

        return blueprints

    def _build_blueprint(
        self,
        timeframe: str,
        direction: str,
        coins: list[str],
        entry: EntryCondition,
        entry_params: dict,
        filters: list[tuple[EntryFilter, dict]],
        exit_mech: ExitMechanism,
    ) -> Optional[StrategyBlueprint]:
        """Build a single blueprint with random SL/TP/EC/TS selections."""
        # SL (always)
        sl_config = self._rng.choice(SL_CONFIGS)
        sl_params = self._resolve_params(sl_config.params)

        # TP
        tp_config = None
        tp_params = None
        if exit_mech.uses_tp:
            tp_config = self._rng.choice(TP_CONFIGS)
            tp_params = self._resolve_params(tp_config.params)

        # EC
        exit_cond = None
        exit_params = None
        if exit_mech.uses_ec:
            valid_exits = get_exits_by_direction(direction)
            if not valid_exits:
                return None
            exit_cond = self._rng.choice(valid_exits)
            exit_params = self._resolve_params(exit_cond.params)

        # TS
        trailing = None
        trailing_params = None
        if exit_mech.uses_ts:
            trailing = self._rng.choice(TRAILING_CONFIGS)
            trailing_params = self._resolve_params(
                {**trailing.activation_params, **trailing.trail_params}
            )

        return StrategyBlueprint(
            strategy_id=uuid.uuid4().hex[:8],
            timeframe=timeframe,
            direction=direction,
            entry_condition=entry,
            entry_params=entry_params,
            entry_filters=filters,
            exit_mechanism=exit_mech,
            sl_config=sl_config,
            sl_params=sl_params,
            tp_config=tp_config,
            tp_params=tp_params,
            exit_condition=exit_cond,
            exit_params=exit_params,
            trailing_config=trailing,
            trailing_params=trailing_params,
            pattern_coins=list(set(coins)),
        )

    def _select_orthogonal_filters(
        self,
        compatible_filters: list[EntryFilter],
        count: int,
    ) -> list[tuple[EntryFilter, dict]]:
        """
        Select N filters from different categories.

        Args:
            compatible_filters: List of filters compatible with entry
            count: Number of filters to select (0-2)

        Returns:
            List of (filter, resolved_params) tuples
        """
        if count == 0 or not compatible_filters:
            return []

        selected = []
        used_categories = set()

        # Shuffle for randomness
        shuffled = compatible_filters.copy()
        self._rng.shuffle(shuffled)

        for f in shuffled:
            if f.category not in used_categories:
                params = self._resolve_params(f.params)
                selected.append((f, params))
                used_categories.add(f.category)
                if len(selected) >= count:
                    break

        return selected

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

    def _get_param_combinations(self, params: dict) -> list[dict]:
        """
        Get all combinations of parameters.

        Args:
            params: Dict of {param_name: [list of possible values]}

        Returns:
            List of dicts, each with single values
        """
        if not params:
            return [{}]

        keys = list(params.keys())
        values = [params[k] for k in keys]

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations
