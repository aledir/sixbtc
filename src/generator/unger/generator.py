"""
Unger Generator v2 - Diversified Strategy Factory

Generates millions of unique trading strategies using:
- 68 Entry Conditions (7 categories)
- 32 Entry Filters (5 categories with compatibility rules)
- 15 Exit Conditions
- 5 SL Types + 5 TP Types + 6 Trailing Configs
- 11 Exit Mechanisms (TP/EC/TS with AND/OR logic)
- 4 Timeframes x 3 Directions

Total: ~15-30 million base strategies, expandable with parametric backtest.
"""

import hashlib
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from src.database import get_session, MarketRegime, Coin
from src.generator.coin_direction_selector import CoinDirectionSelector
from src.utils import get_logger

from .composer import StrategyBlueprint, StrategyComposer
from .catalogs import ALL_ENTRIES, get_entries_by_direction
from .lookback import compute_lookback

logger = get_logger(__name__)


@dataclass
class UngerGeneratedStrategy:
    """Result of Unger v2 strategy generation."""

    code: str
    strategy_id: str
    strategy_type: str  # 'BRK', 'CRS', 'THR', 'VOL', 'CDL', 'REV'
    timeframe: str
    trading_coins: list[str]
    entry_name: str
    exit_mechanism_name: str
    base_code_hash: str
    generation_mode: str = "unger"
    ai_provider: str = "unger"
    validation_passed: bool = True
    validation_errors: list[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    # Compatibility with old interface
    regime_type: str = ""
    pattern_num: int = 0
    pattern_name: str = ""

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.parameters is None:
            self.parameters = {}


class UngerGenerator:
    """
    Unger Generator v2 - Produces diversified strategies from component catalogs.

    Key differences from v1:
    - 68 entry conditions (vs 16 in v1)
    - 32 entry filters with compatibility rules
    - 11 exit mechanisms with AND/OR logic
    - Full SL/TP/EC/TS configuration
    - ~15-30 million possible base strategies
    """

    # Default timeframes if not in config
    DEFAULT_TIMEFRAMES = ['15m', '30m', '1h', '2h']
    DEFAULT_DIRECTIONS = ['LONG', 'SHORT', 'BIDI']

    # Regime → Entry Categories mapping
    # TREND: trend-following strategies (breakout, crossover, momentum)
    # REVERSAL: mean-reversion strategies (threshold, candlestick patterns)
    # MIXED: all categories allowed
    REGIME_ENTRY_CATEGORIES = {
        'TREND': ['breakout', 'crossover', 'volatility', 'trend_advanced', 'momentum_advanced'],
        'REVERSAL': ['mean_reversion', 'threshold', 'candlestick', 'volume_flow'],
        'MIXED': None,  # None = all categories
    }

    def __init__(self, config: dict):
        """
        Initialize generator with config.

        Args:
            config: Application config dict (from config.yaml)
        """
        self.config = config
        self.composer = StrategyComposer(config)

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = self.jinja_env.get_template("unger_v2.j2")

        # Get configured timeframes
        trading_config = config.get('trading', {})
        timeframes_config = trading_config.get('timeframes', {})
        self.timeframes = list(timeframes_config.values()) if timeframes_config else self.DEFAULT_TIMEFRAMES

        # Initialize coin/direction selector
        self.selector = CoinDirectionSelector(config, 'unger')

        regime_mode = "regime-aware" if self.selector.use_regime else "volume-based"
        logger.info(
            f"UngerGenerator v2 initialized: {len(self.timeframes)} timeframes, "
            f"coin selection: {regime_mode}, ~15-30M possible strategies"
        )

    def get_regime_coins(self, regime_type: str) -> list[str]:
        """
        Query coins for a market regime.

        Args:
            regime_type: 'TREND' or 'REVERSAL'

        Returns:
            List of coin symbols in this regime
        """
        regime_config = self.config.get('regime', {})
        min_strength = regime_config.get('min_strength', 0.5)

        try:
            with get_session() as session:
                regimes = session.query(MarketRegime).filter(
                    MarketRegime.regime_type == regime_type,
                    MarketRegime.strength >= min_strength,
                ).all()
                return [r.symbol for r in regimes]
        except Exception as e:
            logger.warning(f"Failed to query regime coins: {e}")
            return []

    def get_all_tradeable_coins(self) -> list[str]:
        """Get all tradeable coins from coin registry."""
        try:
            with get_session() as session:
                from src.database import Coin
                coins = session.query(Coin).filter(
                    Coin.is_active == True,
                    Coin.max_leverage > 0,
                ).all()
                return [c.symbol for c in coins]
        except Exception as e:
            logger.warning(f"Failed to query tradeable coins: {e}")
            return []

    def get_direction_groups(self) -> dict[str, list[str]]:
        """
        Query MarketRegime and group symbols by direction.

        Returns:
            {"LONG": [...], "SHORT": [...], "BOTH": [...]}
        """
        regime_config = self.config.get('regime', {})
        min_strength = regime_config.get('min_strength', 0.5)

        groups: dict[str, list[str]] = {"LONG": [], "SHORT": [], "BOTH": []}
        try:
            with get_session() as session:
                regimes = session.query(MarketRegime).filter(
                    MarketRegime.strength >= min_strength
                ).all()
                for r in regimes:
                    if r.direction in groups:
                        groups[r.direction].append(r.symbol)
            return groups
        except Exception as e:
            logger.warning(f"Failed to query direction groups: {e}")
            return groups

    def select_direction_and_coins(self) -> tuple[str, list[str]]:
        """
        Select direction and coins based on regime with 50/50 BIDI diversity.

        Logic:
        - Bearish regime (SHORT dominant): 50% SHORT + 50% BIDI
        - Bullish regime (LONG dominant): 50% LONG + 50% BIDI
        - BIDI is neutral, never goes against regime

        Returns:
            (direction, coins) - e.g., ("BIDI", ["BTC", "ETH", ...])
        """
        groups = self.get_direction_groups()

        # Filter empty groups
        non_empty = {d: coins for d, coins in groups.items() if coins}

        if not non_empty:
            # Fallback: no regime data available
            from src.data.coin_registry import get_top_coins_by_volume
            top_coins_limit = self.config['trading']['top_coins_limit']
            logger.info(f"No regime direction data, falling back to top {top_coins_limit} coins by volume")
            return "LONG", get_top_coins_by_volume(top_coins_limit)

        # Separate directional (LONG/SHORT) from neutral (BOTH)
        directional = {d: c for d, c in non_empty.items() if d in ('LONG', 'SHORT')}
        has_bidi = 'BOTH' in non_empty and len(non_empty['BOTH']) > 0

        # If only BOTH available, use BIDI
        if not directional:
            logger.debug(f"Only BOTH available ({len(groups['BOTH'])} coins) -> BIDI")
            return "BIDI", groups['BOTH']

        # Find dominant directional regime (LONG or SHORT)
        max_size = max(len(c) for c in directional.values())
        candidates = [d for d, c in directional.items() if len(c) == max_size]
        dominant = random.choice(candidates)

        # 50/50 split: dominant direction vs BIDI (if BOTH has coins)
        if has_bidi and random.random() < 0.50:
            direction = "BIDI"
            coins = groups['BOTH']
        else:
            direction = dominant
            coins = groups[dominant]

        logger.debug(
            f"Direction groups: LONG={len(groups['LONG'])}, SHORT={len(groups['SHORT'])}, "
            f"BOTH={len(groups['BOTH'])} | dominant={dominant} -> selected {direction}"
        )

        return direction, coins

    def generate(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        regime_type: Optional[str] = None,
        count: int = 1,
        seed: Optional[int] = None,
    ) -> list[UngerGeneratedStrategy]:
        """
        Generate N diversified strategies.

        Args:
            timeframe: Target timeframe (None = random from config)
            direction: 'LONG', 'SHORT', 'BIDI' (None = selector-driven)
            regime_type: 'TREND' or 'REVERSAL' for coin selection (only used when market_regime.enabled)
            count: Number of strategies to generate
            seed: Random seed for reproducibility

        Returns:
            List of UngerGeneratedStrategy objects
        """
        if seed is not None:
            self.composer.set_seed(seed)

        results = []

        for _ in range(count):
            # Select timeframe
            tf = timeframe or random.choice(self.timeframes)

            # Select direction and coins via selector
            # Selector handles both volume-based and regime-based modes
            dir_, coins = self.selector.select(direction_override=direction)

            if not coins:
                logger.warning("No coins available for strategy generation")
                continue

            # Compose strategy blueprint
            try:
                blueprint = self.composer.compose_random(
                    timeframe=tf,
                    direction=dir_,
                    coins=coins,
                )
            except Exception as e:
                logger.error(f"Failed to compose blueprint: {e}")
                continue

            # Render to code
            try:
                code = self._render_strategy(blueprint)
            except Exception as e:
                logger.error(
                    f"Failed to render strategy: {e} | "
                    f"entry={blueprint.entry_condition.id}, "
                    f"filters={[f[0].id for f in blueprint.entry_filters]}, "
                    f"exit={blueprint.exit_mechanism.id}"
                )
                continue

            # Build result
            result = UngerGeneratedStrategy(
                code=code,
                strategy_id=blueprint.strategy_id,
                strategy_type=blueprint.get_strategy_type(),
                timeframe=tf,
                trading_coins=blueprint.trading_coins,
                entry_name=blueprint.entry_condition.name,
                exit_mechanism_name=blueprint.exit_mechanism.name,
                base_code_hash=blueprint.compute_hash(),
                parameters={
                    # Parameter values
                    'entry_params': blueprint.entry_params,
                    'filter_params': [f[1] for f in blueprint.entry_filters],  # List of filter param dicts
                    'sl_params': blueprint.sl_params,
                    'tp_params': blueprint.tp_params,
                    'exit_params': blueprint.exit_params,
                    'trailing_params': blueprint.trailing_params,
                    # Component IDs (for genetic operations)
                    'entry_id': blueprint.entry_condition.id,
                    'entry_category': blueprint.entry_condition.category,
                    'filter_ids': [f[0].id for f in blueprint.entry_filters],
                    'exit_mechanism_id': blueprint.exit_mechanism.id,
                    'sl_config_id': blueprint.sl_config.id,
                    'tp_config_id': blueprint.tp_config.id if blueprint.tp_config else None,
                    'exit_condition_id': blueprint.exit_condition.id if blueprint.exit_condition else None,
                    'trailing_config_id': blueprint.trailing_config.id if blueprint.trailing_config else None,
                    'composition_type': 'unger',
                },
                regime_type=regime_type or 'MIXED',
                pattern_num=0,
                pattern_name=blueprint.entry_condition.id,
            )
            results.append(result)

            logger.debug(
                f"Generated {blueprint.get_class_name()}: "
                f"{blueprint.describe()}"
            )

        return results

    def _substitute_params(self, template: str, params: dict) -> str:
        """
        Replace {param} placeholders with actual values.

        Args:
            template: String with {param} placeholders
            params: Dict of param_name -> value

        Returns:
            String with placeholders replaced
        """
        result = template
        for key, value in params.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result

    def _vectorize_logic(self, logic: str) -> str:
        """
        Convert point-in-time logic to vectorized logic for calculate_indicators().

        Transforms:
        - df["col"].iloc[-1] → df["col"]
        - df["col"].iloc[-2] → df["col"].shift(1)
        - df["col"].iloc[-N] → df["col"].shift(N-1)
        - variable.iloc[-1] → variable
        - variable.iloc[-2] → variable.shift(1)
        - df["col"].iloc[-N-1:-1].max() → df["col"].shift(1).rolling(N).max()
        - entry_condition = X → entry_signal = X
        - and → &  (for pandas Series boolean ops)
        - or → |
        """
        result = logic

        # Handle slice patterns like df["col"].iloc[-N-1:-1].max()
        # Convert to df["col"].shift(1).rolling(N).max()
        slice_pattern = r'(\w+(?:\["[^"]+"\])?(?:\.[^.]+)*)\.iloc\[-(\d+)-1:-1\]\.(max|min)\(\)'
        def replace_slice(m):
            expr, n, func = m.groups()
            return f'{expr}.shift(1).rolling({n}).{func}()'
        result = re.sub(slice_pattern, replace_slice, result)

        # Handle slice patterns like df["col"].iloc[-N:-1].max() (without -1 in first part)
        # Convert to df["col"].shift(1).rolling(N-1).max()
        slice_pattern2 = r'(\w+(?:\["[^"]+"\])?(?:\.[^.]+)*)\.iloc\[-(\d+):-1\]\.(max|min)\(\)'
        def replace_slice2(m):
            expr, n, func = m.groups()
            n = int(n)
            return f'{expr}.shift(1).rolling({n-1}).{func}()'
        result = re.sub(slice_pattern2, replace_slice2, result)

        # Handle df["col"].iloc[-N] patterns (specific index)
        # df["col"].iloc[-1] → df["col"]
        # df["col"].iloc[-2] → df["col"].shift(1)
        iloc_pattern = r'(df\["[^"]+"\])\.iloc\[-(\d+)\]'
        def replace_iloc_df(m):
            expr, n = m.groups()
            n = int(n)
            if n == 1:
                return expr  # Current bar
            else:
                return f'{expr}.shift({n-1})'
        result = re.sub(iloc_pattern, replace_iloc_df, result)

        # Handle variable.iloc[-N] patterns (intermediate variables like atr, ma_fast)
        var_iloc_pattern = r'(\b[a-z_][a-z0-9_]*(?:\[[^\]]+\])?)\.iloc\[-(\d+)\]'
        def replace_iloc_var(m):
            expr, n = m.groups()
            n = int(n)
            if n == 1:
                return expr
            else:
                return f'{expr}.shift({n-1})'
        result = re.sub(var_iloc_pattern, replace_iloc_var, result, flags=re.IGNORECASE)

        # Handle function_call(...).iloc[-1] patterns
        # e.g., UngerPatterns.pattern_65(df).iloc[-1] → UngerPatterns.pattern_65(df)
        func_iloc_pattern = r'(\w+(?:\.\w+)*\([^)]*\))\.iloc\[-1\]'
        result = re.sub(func_iloc_pattern, r'\1', result)

        # Convert min(df["col1"], df["col2"]) → df[["col1", "col2"]].min(axis=1)
        # This handles cases where .iloc[-1] was removed from min(df["col"].iloc[-1], df["col2"].iloc[-1])
        min_max_pattern = r'(min|max)\(df\["([^"]+)"\],\s*df\["([^"]+)"\]\)'
        def replace_min_max(m):
            func, col1, col2 = m.groups()
            return f'df[["{col1}", "{col2}"]].{func}(axis=1)'
        result = re.sub(min_max_pattern, replace_min_max, result)

        # Convert Python boolean operators to pandas bitwise operators
        # Use word boundaries to avoid replacing within identifiers like "random" or "pandas"
        result = re.sub(r'\band\b', '&', result)
        result = re.sub(r'\bor\b', '|', result)

        # Rename entry_condition to entry_signal for vectorized output
        result = result.replace('entry_condition', 'entry_signal')

        return result

    def _vectorize_filter_logic(self, logic: str) -> str:
        """
        Convert filter logic to vectorized form.

        Similar to _vectorize_logic but keeps filter_pass as the variable name.
        """
        result = self._vectorize_logic(logic)
        # Filter logic uses filter_pass, not entry_condition
        result = result.replace('entry_signal', 'filter_pass')
        return result

    def _render_strategy(self, bp: StrategyBlueprint) -> str:
        """
        Render blueprint to Python strategy code.

        Args:
            bp: StrategyBlueprint with all components

        Returns:
            Python source code string
        """
        # BIDI: render with dual entries
        if bp.direction == 'BIDI' and bp.entry_condition_long:
            return self._render_bidi_strategy(bp)

        # Pre-process logic templates with parameter substitution
        entry_logic = self._substitute_params(
            bp.entry_condition.logic_template,
            bp.entry_params
        )
        # Create vectorized version for calculate_indicators()
        entry_logic_vectorized = self._vectorize_logic(entry_logic)

        # Pre-process filter logic templates
        processed_filters = []
        for flt, flt_params in bp.entry_filters:
            processed_logic = self._substitute_params(
                flt.logic_template,
                flt_params
            )
            # Vectorize filter logic for calculate_indicators()
            processed_logic_vectorized = self._vectorize_filter_logic(processed_logic)
            # Template expects (filter, filter_params, filter_logic, filter_logic_vectorized) - 4 elements
            processed_filters.append((flt, flt_params, processed_logic, processed_logic_vectorized))

        # Pre-process exit condition logic
        exit_logic = None
        if bp.exit_condition and bp.exit_params:
            exit_logic = self._substitute_params(
                bp.exit_condition.logic_template,
                bp.exit_params
            )

        # Compute lookback automatically from indicators and params
        # This ensures correct lookback even if catalog value is wrong
        try:
            computed_lookback = compute_lookback(
                bp.entry_condition.indicators_used,
                bp.entry_params
            )
        except ValueError as e:
            # Unknown indicator - use declared lookback with safety margin
            logger.warning(f"Lookback computation failed: {e}")
            computed_lookback = bp.entry_condition.lookback_required + 20

        # Use max of computed and declared lookback
        final_lookback = max(computed_lookback, bp.entry_condition.lookback_required)

        return self.template.render(
            # Meta
            strategy_id=bp.strategy_id,
            class_name=bp.get_class_name(),
            strategy_type=bp.get_strategy_type(),
            timeframe=bp.timeframe,
            direction=bp.direction,
            generated_at=datetime.now(timezone.utc).isoformat(),
            # Entry
            entry=bp.entry_condition,
            entry_params=bp.entry_params,
            entry_logic=entry_logic,
            entry_logic_vectorized=entry_logic_vectorized,
            computed_lookback=final_lookback,  # Auto-computed from indicators
            filters=processed_filters,
            # Exit
            exit_mechanism=bp.exit_mechanism,
            sl_config=bp.sl_config,
            sl_params=bp.sl_params,
            tp_config=bp.tp_config,
            tp_params=bp.tp_params,
            exit_condition=bp.exit_condition,
            exit_params=bp.exit_params,
            exit_logic=exit_logic,
            trailing=bp.trailing_config,
            trailing_params=bp.trailing_params,
            # Coins
            trading_coins=bp.trading_coins,
            # BIDI flag (for template)
            is_bidi=False,
        )

    def _render_bidi_strategy(self, bp: StrategyBlueprint) -> str:
        """
        Render BIDI strategy with separate LONG/SHORT entries.

        Args:
            bp: StrategyBlueprint with entry_condition_long and entry_condition_short

        Returns:
            Python source code string
        """
        # Process LONG entry
        entry_logic_long = self._substitute_params(
            bp.entry_condition_long.logic_template,
            bp.entry_params_long
        )
        entry_logic_long_vectorized = self._vectorize_logic(entry_logic_long)

        # Process SHORT entry
        entry_logic_short = self._substitute_params(
            bp.entry_condition_short.logic_template,
            bp.entry_params_short
        )
        entry_logic_short_vectorized = self._vectorize_logic(entry_logic_short)

        # Pre-process filter logic templates (filters apply to both directions)
        processed_filters = []
        for flt, flt_params in bp.entry_filters:
            processed_logic = self._substitute_params(
                flt.logic_template,
                flt_params
            )
            processed_logic_vectorized = self._vectorize_filter_logic(processed_logic)
            processed_filters.append((flt, flt_params, processed_logic, processed_logic_vectorized))

        # Pre-process exit condition logic
        exit_logic = None
        if bp.exit_condition and bp.exit_params:
            exit_logic = self._substitute_params(
                bp.exit_condition.logic_template,
                bp.exit_params
            )

        # Compute lookback from both entries (use max)
        try:
            lookback_long = compute_lookback(
                bp.entry_condition_long.indicators_used,
                bp.entry_params_long
            )
            lookback_short = compute_lookback(
                bp.entry_condition_short.indicators_used,
                bp.entry_params_short
            )
            computed_lookback = max(lookback_long, lookback_short)
        except ValueError as e:
            logger.warning(f"Lookback computation failed: {e}")
            computed_lookback = max(
                bp.entry_condition_long.lookback_required,
                bp.entry_condition_short.lookback_required
            ) + 20

        final_lookback = max(
            computed_lookback,
            bp.entry_condition_long.lookback_required,
            bp.entry_condition_short.lookback_required
        )

        return self.template.render(
            # Meta
            strategy_id=bp.strategy_id,
            class_name=bp.get_class_name(),
            strategy_type=bp.get_strategy_type(),
            timeframe=bp.timeframe,
            direction=bp.direction,
            generated_at=datetime.now(timezone.utc).isoformat(),
            # BIDI flag
            is_bidi=True,
            # LONG entry
            entry_long=bp.entry_condition_long,
            entry_params_long=bp.entry_params_long,
            entry_logic_long=entry_logic_long,
            entry_logic_long_vectorized=entry_logic_long_vectorized,
            # SHORT entry
            entry_short=bp.entry_condition_short,
            entry_params_short=bp.entry_params_short,
            entry_logic_short=entry_logic_short,
            entry_logic_short_vectorized=entry_logic_short_vectorized,
            # Keep entry for backward compat (used by some template sections)
            entry=bp.entry_condition_long,
            entry_params=bp.entry_params_long,
            entry_logic=entry_logic_long,
            entry_logic_vectorized=entry_logic_long_vectorized,
            computed_lookback=final_lookback,
            filters=processed_filters,
            # Exit
            exit_mechanism=bp.exit_mechanism,
            sl_config=bp.sl_config,
            sl_params=bp.sl_params,
            tp_config=bp.tp_config,
            tp_params=bp.tp_params,
            exit_condition=bp.exit_condition,
            exit_params=bp.exit_params,
            exit_logic=exit_logic,
            trailing=bp.trailing_config,
            trailing_params=bp.trailing_params,
            # Coins
            trading_coins=bp.trading_coins,
        )

    def generate_batch(
        self,
        count: int,
        diverse: bool = True,
    ) -> list[UngerGeneratedStrategy]:
        """
        Generate a batch of strategies with optional diversity.

        When diverse=True, distributes across timeframes and directions.

        Args:
            count: Total number of strategies
            diverse: Whether to enforce diversity

        Returns:
            List of generated strategies
        """
        if not diverse:
            return self.generate(count=count)

        results = []
        directions = ['LONG', 'SHORT', 'BIDI']
        regimes = ['TREND', 'REVERSAL']

        # Distribute across timeframes, directions, and regimes
        per_combo = max(1, count // (len(self.timeframes) * len(directions) * len(regimes)))

        for tf in self.timeframes:
            for dir_ in directions:
                for regime in regimes:
                    batch = self.generate(
                        timeframe=tf,
                        direction=dir_,
                        regime_type=regime,
                        count=per_combo,
                    )
                    results.extend(batch)

                    if len(results) >= count:
                        return results[:count]

        return results
