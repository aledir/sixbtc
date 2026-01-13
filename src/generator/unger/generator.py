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
from src.utils import get_logger

from .composer import StrategyBlueprint, StrategyComposer
from .catalogs import ALL_ENTRIES, get_entries_by_direction

logger = get_logger(__name__)


@dataclass
class UngerGeneratedStrategy:
    """Result of Unger v2 strategy generation."""

    code: str
    strategy_id: str
    strategy_type: str  # 'BRK', 'CRS', 'THR', 'VOL', 'CDL', 'REV'
    timeframe: str
    pattern_coins: list[str]
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

        logger.info(
            f"UngerGenerator v2 initialized: {len(self.timeframes)} timeframes, "
            f"~15-30M possible strategies"
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
            direction: 'LONG', 'SHORT', 'BIDI' (None = random)
            regime_type: 'TREND' or 'REVERSAL' for coin selection (None = all coins)
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

            # Select direction (bias toward LONG/SHORT over BIDI)
            if direction:
                dir_ = direction
            else:
                dir_ = random.choice(['LONG', 'LONG', 'SHORT', 'SHORT', 'BIDI'])

            # Get coins based on regime or all
            if regime_type:
                coins = self.get_regime_coins(regime_type)
                if not coins:
                    # Fallback to opposite regime
                    fallback = 'REVERSAL' if regime_type == 'TREND' else 'TREND'
                    coins = self.get_regime_coins(fallback)
            else:
                # Mix from both regimes
                trend_coins = self.get_regime_coins('TREND')
                reversal_coins = self.get_regime_coins('REVERSAL')
                coins = list(set(trend_coins + reversal_coins))

            # Fallback to all tradeable coins
            if not coins:
                coins = self.get_all_tradeable_coins()

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
                logger.error(f"Failed to render strategy: {e}")
                continue

            # Build result
            result = UngerGeneratedStrategy(
                code=code,
                strategy_id=blueprint.strategy_id,
                strategy_type=blueprint.get_strategy_type(),
                timeframe=tf,
                pattern_coins=blueprint.pattern_coins,
                entry_name=blueprint.entry_condition.name,
                exit_mechanism_name=blueprint.exit_mechanism.name,
                base_code_hash=blueprint.compute_hash(),
                parameters={
                    'entry_params': blueprint.entry_params,
                    'sl_params': blueprint.sl_params,
                    'tp_params': blueprint.tp_params,
                    'exit_params': blueprint.exit_params,
                    'trailing_params': blueprint.trailing_params,
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

        # Convert Python boolean operators to pandas bitwise operators
        # Use word boundaries to avoid replacing within identifiers
        result = re.sub(r'\)\s+and\s+\(', ') & (', result)
        result = re.sub(r'\)\s+or\s+\(', ') | (', result)

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
            # Template expects (filter, filter_params, filter_logic) - 3 elements
            processed_filters.append((flt, flt_params, processed_logic))

        # Pre-process exit condition logic
        exit_logic = None
        if bp.exit_condition and bp.exit_params:
            exit_logic = self._substitute_params(
                bp.exit_condition.logic_template,
                bp.exit_params
            )

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
            pattern_coins=bp.pattern_coins,
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

    def generate_regime_aware(
        self,
        strategies_per_group: int = 10,
        max_coins_per_group: int = 30,
    ) -> list[UngerGeneratedStrategy]:
        """
        Generate strategies based on regime for all coin groups.

        Flow:
        1. Calculate regime for every coin
        2. Group coins by (type, direction)
        3. For each group: select top N coins by volume
        4. For each group: generate strategies with coherent entry categories

        Args:
            strategies_per_group: Strategies to generate per regime group
            max_coins_per_group: Max coins to use per group (top by volume)

        Returns:
            List of generated strategies from all groups
        """
        from src.generator.regime.detector import RegimeDetector

        # Get config
        regime_config = self.config.get('regime', {})
        window_days = regime_config.get('window_days', 90)

        detector = RegimeDetector(window_days=window_days)

        # 1. Calculate regime for all coins
        all_regimes = detector.get_all_regimes()

        if not all_regimes:
            logger.warning("No coin regimes available, skipping regime-aware generation")
            return []

        # 2. Group by (type, direction)
        groups = detector.group_by_regime(all_regimes)

        results = []

        # 3-4. For each group
        for (regime_type, direction), coins in groups.items():
            if not coins:
                continue

            # Select top N by volume
            selected_coins = self._select_top_by_volume(coins, max_coins_per_group)

            if not selected_coins:
                logger.debug(f"No coins with volume data for regime ({regime_type}, {direction})")
                continue

            # Get allowed entry categories for this regime
            allowed_categories = self.REGIME_ENTRY_CATEGORIES.get(regime_type)

            # Determine allowed directions
            if direction == 'BOTH':
                allowed_directions = ['LONG', 'SHORT']
            else:
                allowed_directions = [direction]

            # Log
            logger.info(
                f"Regime ({regime_type}, {direction}): {len(selected_coins)} coins, "
                f"generating {strategies_per_group} strategies"
            )

            # Generate strategies - divide equally between directions
            strategies_per_direction = strategies_per_group // len(allowed_directions)

            for dir_ in allowed_directions:
                for _ in range(strategies_per_direction):
                    strategy = self._generate_for_regime(
                        coins=selected_coins,
                        direction=dir_,
                        allowed_categories=allowed_categories,
                        regime_type=regime_type,
                    )
                    if strategy:
                        results.append(strategy)

        logger.info(f"Regime-aware generation complete: {len(results)} strategies")
        return results

    def _select_top_by_volume(self, coins: list[str], limit: int) -> list[str]:
        """
        Select top N coins by 24h volume.

        Args:
            coins: List of coin symbols
            limit: Maximum coins to return

        Returns:
            List of symbols sorted by volume descending
        """
        try:
            with get_session() as session:
                db_coins = session.query(Coin).filter(
                    Coin.symbol.in_(coins),
                    Coin.volume_24h.isnot(None),
                    Coin.volume_24h > 0,
                ).order_by(Coin.volume_24h.desc()).limit(limit).all()

                return [c.symbol for c in db_coins]
        except Exception as e:
            logger.warning(f"Failed to query coins by volume: {e}")
            # Fallback: return first N coins
            return coins[:limit]

    def _generate_for_regime(
        self,
        coins: list[str],
        direction: str,
        allowed_categories: list[str] | None,
        regime_type: str,
    ) -> UngerGeneratedStrategy | None:
        """
        Generate a single strategy for a specific regime.

        Args:
            coins: Coins to use for this strategy
            direction: LONG or SHORT
            allowed_categories: Entry categories allowed (None = all)
            regime_type: TREND, REVERSAL, or MIXED

        Returns:
            Generated strategy or None if failed
        """
        # Filter entries by allowed categories and direction
        if allowed_categories:
            entries = [
                e for e in ALL_ENTRIES
                if e.category in allowed_categories
                and (e.direction == direction or e.direction == 'BIDI')
            ]
        else:
            entries = get_entries_by_direction(direction)

        if not entries:
            logger.debug(f"No entries for regime {regime_type}, direction {direction}")
            return None

        # Select random entry
        entry = random.choice(entries)

        # Select random timeframe
        tf = random.choice(self.timeframes)

        try:
            # Compose blueprint with entry override
            blueprint = self.composer.compose_random(
                timeframe=tf,
                direction=direction,
                coins=coins,
                entry_override=entry,
            )

            # Render to code
            code = self._render_strategy(blueprint)

            return UngerGeneratedStrategy(
                code=code,
                strategy_id=blueprint.strategy_id,
                strategy_type=blueprint.get_strategy_type(),
                timeframe=tf,
                pattern_coins=coins,
                entry_name=entry.name,
                exit_mechanism_name=blueprint.exit_mechanism.name,
                base_code_hash=blueprint.compute_hash(),
                regime_type=regime_type,
            )
        except Exception as e:
            logger.error(f"Failed to generate strategy for regime {regime_type}: {e}")
            return None
