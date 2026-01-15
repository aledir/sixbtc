"""
Genetic Unger Generator - Evolves strategies from ACTIVE pool.

Uses deferred fitness: strategies in ACTIVE pool have already been
backtested and scored. We evolve their component combinations to
discover new profitable strategies.

Output naming: UggStrat_{type}_{hash}
Database field: generation_mode = "unger_genetic"
"""

import hashlib
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from src.database import get_session, Strategy, MarketRegime
from src.generator.coin_direction_selector import CoinDirectionSelector
from src.generator.unger.catalogs import (
    get_entry_by_id,
    get_filter_by_id,
    get_mechanism_by_id,
    get_sl_config_by_id,
    get_tp_config_by_id,
    get_trailing_config_by_id,
    get_exit_by_id,
    get_exits_by_direction,
    get_compatible_filters,
    EXIT_MECHANISMS,
    SL_CONFIGS,
    TP_CONFIGS,
    TRAILING_CONFIGS,
)
from src.generator.unger.composer import StrategyBlueprint, StrategyComposer
from src.generator.unger.genetic_operators import (
    UngerGeneticIndividual,
    tournament_selection,
    filter_pool_by_direction,
    crossover_components,
    mutate_entry,
    mutate_filters,
    mutate_exit_mechanism,
    mutate_configs,
    mutate_params,
)
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class UngerGeneticResult:
    """Result of genetic Unger strategy generation."""

    code: str
    strategy_id: str
    strategy_type: str              # 'BRK', 'CRS', 'THR', 'VOL', 'CDL', 'REV'
    timeframe: str
    trading_coins: list[str]
    entry_name: str
    exit_mechanism_name: str
    base_code_hash: str
    generation_mode: str = "unger_genetic"
    ai_provider: str = "unger"
    direction: str = "long"
    parent_ids: List[str] = field(default_factory=list)
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    # Compatibility
    regime_type: str = "MIXED"
    pattern_num: int = 0
    pattern_name: str = ""

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.parameters is None:
            self.parameters = {}
        if self.parent_ids is None:
            self.parent_ids = []


class GeneticUngerGenerator:
    """
    Genetic generator with deferred fitness for Unger strategies.

    Pool = ACTIVE strategies with generation_mode='unger' and score >= min_pool_score
    Fitness = backtest score (already calculated by backtester)
    """

    DEFAULT_TIMEFRAMES = ['15m', '30m', '1h', '2h']

    def __init__(self, config: dict, seed: Optional[int] = None):
        """
        Initialize genetic generator.

        Args:
            config: Application config dict
            seed: Optional random seed for reproducibility
        """
        self.config = config
        self.rng = random.Random(seed)

        # Get genetic config
        gen_config = config.get('generation', {})
        unger_config = gen_config.get('strategy_sources', {}).get('unger', {})
        genetic_config = unger_config.get('genetic', {})

        self.min_pool_score = genetic_config.get('min_pool_score', 40)
        self.min_pool_size = genetic_config.get('min_pool_size', 50)
        self.tournament_size = genetic_config.get('tournament_size', 3)
        self.mutation_rate = genetic_config.get('mutation_rate', 0.20)
        self.crossover_rate = genetic_config.get('crossover_rate', 0.80)

        # Composer for blueprint operations
        self.composer = StrategyComposer(config)

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.template = self.jinja_env.get_template("unger_v2.j2")

        # Pool cache
        self._pool_cache: List[UngerGeneticIndividual] = []
        self._pool_cache_time: Optional[datetime] = None
        self._pool_refresh_interval = 300  # 5 minutes

        # Get configured timeframes
        trading_config = config.get('trading', {})
        timeframes_config = trading_config.get('timeframes', {})
        self.timeframes = list(timeframes_config.values()) if timeframes_config else self.DEFAULT_TIMEFRAMES

        # Initialize coin/direction selector (uses 'unger' config for market_regime setting)
        self.selector = CoinDirectionSelector(config, 'unger')

        regime_mode = "regime-aware" if self.selector.use_regime else "volume-based"
        logger.info(
            f"GeneticUngerGenerator initialized: "
            f"pool_score>={self.min_pool_score}, pool_size>={self.min_pool_size}, "
            f"mutation={self.mutation_rate:.0%}, crossover={self.crossover_rate:.0%}, "
            f"coin selection: {regime_mode}"
        )

    def get_pool(self, force_refresh: bool = False) -> List[UngerGeneticIndividual]:
        """
        Get genetic pool from ACTIVE unger strategies.

        Only includes strategies with required component metadata.

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            List of UngerGeneticIndividual from ACTIVE pool
        """
        now = datetime.now(timezone.utc)

        # Check cache validity
        if not force_refresh and self._pool_cache_time:
            age = (now - self._pool_cache_time).total_seconds()
            if age < self._pool_refresh_interval and self._pool_cache:
                return self._pool_cache

        # Refresh from database
        try:
            with get_session() as session:
                strategies = session.query(Strategy).filter(
                    Strategy.status == 'ACTIVE',
                    Strategy.generation_mode == 'unger',
                    Strategy.score_backtest >= self.min_pool_score
                ).all()

                pool = []
                for s in strategies:
                    individual = self._extract_individual_from_strategy(s)
                    if individual:
                        pool.append(individual)

                self._pool_cache = pool
                self._pool_cache_time = now

                logger.debug(f"Genetic pool refreshed: {len(pool)} unger individuals")
                return pool

        except Exception as e:
            logger.error(f"Failed to load genetic pool: {e}")
            return self._pool_cache or []

    def _extract_individual_from_strategy(
        self,
        strategy: Strategy
    ) -> Optional[UngerGeneticIndividual]:
        """
        Extract genetic individual from strategy.

        Requires strategy to have component metadata in parameters.

        Args:
            strategy: Strategy model instance

        Returns:
            UngerGeneticIndividual or None if metadata missing
        """
        if not strategy.parameters:
            return None

        params = strategy.parameters

        # Check for required component IDs
        entry_id = params.get('entry_id')
        if not entry_id:
            return None

        # Get entry to verify it exists
        entry = get_entry_by_id(entry_id)
        if not entry:
            return None

        return UngerGeneticIndividual(
            strategy_id=str(strategy.id),
            entry_id=entry_id,
            filter_ids=params.get('filter_ids', []),
            exit_mechanism_id=params.get('exit_mechanism_id', 1),
            sl_config_id=params.get('sl_config_id', 'SL_FIXED'),
            tp_config_id=params.get('tp_config_id'),
            exit_condition_id=params.get('exit_condition_id'),
            trailing_config_id=params.get('trailing_config_id'),
            entry_params=params.get('entry_params', {}),
            filter_params=params.get('filter_params', []),
            sl_params=params.get('sl_params', {}),
            tp_params=params.get('tp_params'),
            exit_params=params.get('exit_params'),
            trailing_params=params.get('trailing_params'),
            fitness=strategy.score_backtest or 0,
            direction=self._detect_direction(strategy.code),
            timeframe=strategy.timeframe,
            entry_category=params.get('entry_category', ''),
        )

    def _detect_direction(self, code: str) -> str:
        """Detect direction from strategy code."""
        if not code:
            return 'LONG'
        code_upper = code.upper()
        if "DIRECTION = 'SHORT'" in code_upper or 'DIRECTION="SHORT"' in code_upper:
            return 'SHORT'
        if "DIRECTION = 'BIDI'" in code_upper or 'DIRECTION="BIDI"' in code_upper:
            return 'BIDI'
        return 'LONG'

    def generate(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        count: int = 1,
    ) -> List[UngerGeneticResult]:
        """
        Generate evolved strategies from genetic pool.

        Args:
            timeframe: Target timeframe (random if None)
            direction: 'LONG', 'SHORT', 'BIDI' or None (selector-driven)
            count: Number of strategies to generate

        Returns:
            List of UngerGeneticResult with evolved strategy code
        """
        pool = self.get_pool()

        if len(pool) < self.min_pool_size:
            logger.debug(
                f"Genetic pool too small ({len(pool)} < {self.min_pool_size}), "
                f"cannot evolve"
            )
            return []

        # Resolve parameters
        if timeframe is None:
            timeframe = self.rng.choice(self.timeframes)

        # Use selector for direction (handles both volume-based and regime-based)
        if direction is None:
            direction, _ = self.selector.select()
            # Note: we get coins separately per-strategy in _build_blueprint_from_components

        # Filter pool by direction
        filtered_pool = filter_pool_by_direction(pool, direction)
        if len(filtered_pool) < 2:
            logger.debug(f"Not enough {direction} individuals in pool")
            return []

        results = []
        for _ in range(count):
            result = self._evolve_one(filtered_pool, timeframe, direction)
            if result:
                results.append(result)

        if results:
            logger.info(
                f"Unger genetic: evolved {len(results)} strategies "
                f"({timeframe}, {direction})"
            )

        return results

    def _evolve_one(
        self,
        pool: List[UngerGeneticIndividual],
        timeframe: str,
        direction: str,
    ) -> Optional[UngerGeneticResult]:
        """
        Evolve a single strategy from pool.

        Args:
            pool: Filtered genetic pool
            timeframe: Target timeframe
            direction: Target direction

        Returns:
            UngerGeneticResult or None if evolution fails
        """
        try:
            # Selection (tournament)
            parent1 = tournament_selection(pool, self.tournament_size, self.rng)
            parent2 = tournament_selection(pool, self.tournament_size, self.rng)

            # Crossover
            if self.rng.random() < self.crossover_rate:
                components = crossover_components(parent1, parent2, self.rng)
            else:
                # No crossover - clone parent1
                components = {
                    'entry_id': parent1.entry_id,
                    'entry_params': parent1.entry_params.copy(),
                    'entry_category': parent1.entry_category,
                    'filter_ids': parent1.filter_ids.copy(),
                    'filter_params': [p.copy() for p in parent1.filter_params],
                    'exit_mechanism_id': parent1.exit_mechanism_id,
                    'sl_config_id': parent1.sl_config_id,
                    'sl_params': parent1.sl_params.copy(),
                    'tp_config_id': parent1.tp_config_id,
                    'tp_params': parent1.tp_params.copy() if parent1.tp_params else None,
                    'exit_condition_id': parent1.exit_condition_id,
                    'exit_params': parent1.exit_params.copy() if parent1.exit_params else None,
                    'trailing_config_id': parent1.trailing_config_id,
                    'trailing_params': parent1.trailing_params.copy() if parent1.trailing_params else None,
                }

            # Mutations
            components = mutate_entry(components, direction, self.mutation_rate, self.rng)
            components = mutate_filters(components, direction, self.mutation_rate, self.rng)
            components = mutate_exit_mechanism(components, self.mutation_rate, self.rng)
            components = mutate_configs(components, self.mutation_rate, self.rng)

            # Mutate parameters
            components['entry_params'] = mutate_params(
                components['entry_params'], self.mutation_rate, self.rng
            )
            components['sl_params'] = mutate_params(
                components['sl_params'], self.mutation_rate, self.rng
            )
            if components['tp_params']:
                components['tp_params'] = mutate_params(
                    components['tp_params'], self.mutation_rate, self.rng
                )

            # Build blueprint from evolved components
            blueprint = self._build_blueprint_from_components(
                components, timeframe, direction
            )

            if not blueprint:
                return None

            # Render to strategy code
            return self._render_strategy(
                blueprint=blueprint,
                parent_ids=[parent1.strategy_id, parent2.strategy_id]
            )

        except Exception as e:
            logger.error(f"Unger evolution failed: {e}")
            return None

    def _build_blueprint_from_components(
        self,
        components: dict,
        timeframe: str,
        direction: str,
    ) -> Optional[StrategyBlueprint]:
        """
        Build StrategyBlueprint from evolved component IDs.

        Args:
            components: Dict with component IDs and params
            timeframe: Target timeframe
            direction: Target direction

        Returns:
            StrategyBlueprint or None if components invalid
        """
        try:
            # Get entry
            entry = get_entry_by_id(components['entry_id'])
            if not entry:
                return None

            # Get filters
            entry_filters = []
            for i, fid in enumerate(components['filter_ids']):
                f = get_filter_by_id(fid)
                if f:
                    params = components['filter_params'][i] if i < len(components['filter_params']) else {}
                    entry_filters.append((f, params))

            # Get exit mechanism
            mechanism = get_mechanism_by_id(components['exit_mechanism_id'])
            if not mechanism:
                mechanism = EXIT_MECHANISMS[0]

            # Get SL config
            sl_config = get_sl_config_by_id(components['sl_config_id'])
            if not sl_config:
                sl_config = SL_CONFIGS[0]

            # Get TP config (if used)
            tp_config = None
            tp_params = None
            if mechanism.uses_tp and components['tp_config_id']:
                tp_config = get_tp_config_by_id(components['tp_config_id'])
                tp_params = components['tp_params'] or {}

            # Get exit condition (if used)
            exit_cond = None
            exit_params = None
            if mechanism.uses_ec and components['exit_condition_id']:
                exit_cond = get_exit_by_id(components['exit_condition_id'])
                exit_params = components['exit_params'] or {}

            # Get trailing config (if used)
            trailing = None
            trailing_params = None
            if mechanism.uses_ts and components['trailing_config_id']:
                trailing = get_trailing_config_by_id(components['trailing_config_id'])
                trailing_params = components['trailing_params'] or {}

            # Get coins from market_regimes by direction
            coins = self._get_coins_by_direction(direction)

            return StrategyBlueprint(
                strategy_id=uuid.uuid4().hex[:8],
                timeframe=timeframe,
                direction=direction,
                entry_condition=entry,
                entry_params=components['entry_params'],
                entry_filters=entry_filters,
                exit_mechanism=mechanism,
                sl_config=sl_config,
                sl_params=components['sl_params'],
                tp_config=tp_config,
                tp_params=tp_params,
                exit_condition=exit_cond,
                exit_params=exit_params,
                trailing_config=trailing,
                trailing_params=trailing_params,
                trading_coins=coins,
            )

        except Exception as e:
            logger.error(f"Failed to build blueprint: {e}")
            return None

    def _get_coins_by_direction(self, direction: str) -> List[str]:
        """
        Get coins for a strategy direction using selector.

        Uses the coin/direction selector which handles both:
        - Volume-based mode (top N by volume)
        - Regime-based mode (query market_regimes)

        Args:
            direction: 'LONG', 'SHORT', or 'BIDI'

        Returns:
            List of coin symbols
        """
        _, coins = self.selector.select(direction_override=direction)
        if coins:
            return coins

        # Ultimate fallback
        logger.warning(f"No coins available for direction={direction}, using defaults")
        return ['BTC', 'ETH', 'SOL']

    def _render_strategy(
        self,
        blueprint: StrategyBlueprint,
        parent_ids: List[str],
    ) -> Optional[UngerGeneticResult]:
        """
        Render evolved blueprint into complete strategy code.

        Args:
            blueprint: Strategy blueprint from evolution
            parent_ids: Parent strategy IDs (for lineage)

        Returns:
            UngerGeneticResult or None if rendering fails
        """
        try:
            # Generate class name: UggStrat_{type}_{id}
            class_name = f"UggStrat_{blueprint.get_strategy_type()}_{blueprint.strategy_id}"

            # Prepare template context
            context = self._build_template_context(blueprint, class_name)

            # Render template
            code = self.template.render(**context)

            # Compute base code hash
            base_code_hash = hashlib.sha256(code.encode()).hexdigest()[:12]

            return UngerGeneticResult(
                code=code,
                strategy_id=blueprint.strategy_id,
                strategy_type=blueprint.get_strategy_type(),
                timeframe=blueprint.timeframe,
                trading_coins=blueprint.trading_coins,
                entry_name=blueprint.entry_condition.name,
                exit_mechanism_name=blueprint.exit_mechanism.name,
                base_code_hash=base_code_hash,
                direction=blueprint.direction.lower(),
                parent_ids=parent_ids,
                parameters={
                    # Parameter values
                    'entry_params': blueprint.entry_params,
                    'sl_params': blueprint.sl_params,
                    'tp_params': blueprint.tp_params,
                    'exit_params': blueprint.exit_params,
                    'trailing_params': blueprint.trailing_params,
                    # Component IDs (for future genetic operations)
                    'entry_id': blueprint.entry_condition.id,
                    'entry_category': blueprint.entry_condition.category,
                    'filter_ids': [f[0].id for f in blueprint.entry_filters],
                    'exit_mechanism_id': blueprint.exit_mechanism.id,
                    'sl_config_id': blueprint.sl_config.id,
                    'tp_config_id': blueprint.tp_config.id if blueprint.tp_config else None,
                    'exit_condition_id': blueprint.exit_condition.id if blueprint.exit_condition else None,
                    'trailing_config_id': blueprint.trailing_config.id if blueprint.trailing_config else None,
                    'composition_type': 'unger_genetic',
                    'parent_ids': parent_ids,
                },
            )

        except Exception as e:
            logger.error(f"Failed to render genetic strategy: {e}")
            return None

    def _build_template_context(
        self,
        blueprint: StrategyBlueprint,
        class_name: str,
    ) -> dict:
        """Build Jinja2 template context from blueprint."""
        # Entry logic
        entry_logic = self._substitute_params(
            blueprint.entry_condition.logic_template,
            blueprint.entry_params
        )

        # Filters
        filters = []
        for f, params in blueprint.entry_filters:
            filter_logic = self._substitute_params(f.logic_template, params)
            filters.append((f, params, filter_logic))

        # Exit logic
        exit_logic = None
        if blueprint.exit_condition:
            exit_logic = self._substitute_params(
                blueprint.exit_condition.logic_template,
                blueprint.exit_params or {}
            )

        return {
            'class_name': class_name,
            'timeframe': blueprint.timeframe,
            'direction': blueprint.direction,
            'entry': blueprint.entry_condition,
            'entry_params': blueprint.entry_params,
            'entry_logic': entry_logic,
            'filters': filters,
            'exit_mechanism': blueprint.exit_mechanism,
            'sl_config': blueprint.sl_config,
            'sl_params': blueprint.sl_params,
            'tp_config': blueprint.tp_config,
            'tp_params': blueprint.tp_params,
            'exit_condition': blueprint.exit_condition,
            'exit_params': blueprint.exit_params,
            'exit_logic': exit_logic,
            'trailing': blueprint.trailing_config,
            'trailing_params': blueprint.trailing_params,
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }

    def _substitute_params(self, template: str, params: dict) -> str:
        """Replace {param} placeholders with actual values."""
        result = template
        for key, value in params.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result
