"""
Genetic Pattern Generator - Evolves patterns from ACTIVE pool.

Uses deferred fitness: strategies in ACTIVE pool have already been
backtested and scored. We evolve their block combinations to
discover new profitable patterns.

Output naming: PGgStrat_{type}_{hash}
"""

import hashlib
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from src.data.coin_registry import get_top_coins_by_volume
from src.database import get_session, Strategy
from src.generator.coin_direction_selector import CoinDirectionSelector
from src.generator.pattern_gen.building_blocks import BLOCKS_BY_ID
from src.generator.pattern_gen.formula_composer import ComposedFormula, FormulaComposer
from src.generator.pattern_gen.genetic_operators import (
    GeneticIndividual,
    crossover_blocks,
    filter_pool_by_direction,
    mutate_blocks,
    mutate_params,
    tournament_selection,
)
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class GeneticResult:
    """Result of genetic pattern generation."""

    code: str
    strategy_id: str
    strategy_type: str              # Unified 5 types: TRD, MOM, REV, VOL, CDL
    timeframe: str
    base_code_hash: str
    formula_hash: str
    trading_coins: List[str]        # Top coins by volume at generation time
    generation_mode: str = "pattern_gen_genetic"
    ai_provider: str = "pattern_gen"
    direction: str = "long"
    pattern_name: str = ""
    blocks_used: List[str] = field(default_factory=list)
    composition_type: str = "genetic"
    is_genetic: bool = True
    parent_ids: List[str] = field(default_factory=list)
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.parameters is None:
            self.parameters = {}
        if self.blocks_used is None:
            self.blocks_used = []
        if self.parent_ids is None:
            self.parent_ids = []


class GeneticPatternGenerator:
    """
    Genetic generator with deferred fitness.

    Pool = ACTIVE strategies with score >= min_pool_score
    Fitness = backtest score (already calculated by backtester)
    """

    # Default timeframes
    DEFAULT_TIMEFRAMES = ['15m', '30m', '1h', '2h']

    # SL/TP/Leverage ranges (same as smart generator)
    SL_RANGE = [0.02, 0.03, 0.04, 0.05]
    TP_RANGE = [0.03, 0.04, 0.06, 0.08]
    LEVERAGE_RANGE = [2, 3, 5]
    EXIT_BARS_RANGE = [20, 40, 60, 0]

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
        pattern_gen_config = gen_config.get('strategy_sources', {}).get('pattern_gen', {})
        genetic_config = pattern_gen_config.get('genetic', {})

        self.min_pool_score = genetic_config.get('min_pool_score', 40)
        self.min_pool_size = genetic_config.get('min_pool_size', 50)
        self.tournament_size = genetic_config.get('tournament_size', 3)
        self.mutation_rate = genetic_config.get('mutation_rate', 0.20)
        self.crossover_rate = genetic_config.get('crossover_rate', 0.80)
        self.top_coins_limit = config['trading']['top_coins_limit']

        # Formula composer for creating formulas from blocks
        self.composer = FormulaComposer(seed=seed)

        # Setup Jinja2 environment (reuse smart generator's template)
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Pool cache
        self._pool_cache: List[GeneticIndividual] = []
        self._pool_cache_time: Optional[datetime] = None
        self._pool_refresh_interval = 300  # 5 minutes

        # Get configured timeframes
        trading_config = config.get('trading', {})
        timeframes_config = trading_config.get('timeframes', {})
        self.timeframes = list(timeframes_config.values()) if timeframes_config else self.DEFAULT_TIMEFRAMES

        # Initialize coin/direction selector (uses 'pattern_gen' config for market_regime setting)
        self.selector = CoinDirectionSelector(config, 'pattern_gen')

        regime_mode = "regime-aware" if self.selector.use_regime else "volume-based"
        logger.info(
            f"GeneticPatternGenerator initialized: "
            f"pool_score>={self.min_pool_score}, pool_size>={self.min_pool_size}, "
            f"mutation={self.mutation_rate:.0%}, crossover={self.crossover_rate:.0%}, "
            f"coin selection: {regime_mode}"
        )

    def get_pool(self, force_refresh: bool = False) -> List[GeneticIndividual]:
        """
        Get genetic pool from ACTIVE pattern_gen strategies.

        Caches pool for _pool_refresh_interval seconds.

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            List of GeneticIndividual from ACTIVE pool
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
                    Strategy.generation_mode == 'pattern_gen',
                    Strategy.score_backtest >= self.min_pool_score
                ).all()

                pool = []
                for s in strategies:
                    blocks = self._extract_blocks_from_strategy(s)
                    if blocks:
                        pool.append(GeneticIndividual(
                            strategy_id=str(s.id),
                            blocks=blocks,
                            params=s.parameters.get('formula_params', {}) if s.parameters else {},
                            fitness=s.score_backtest or 0,
                            direction=self._detect_direction(s.code),
                            timeframe=s.timeframe
                        ))

                self._pool_cache = pool
                self._pool_cache_time = now

                logger.debug(f"Genetic pool refreshed: {len(pool)} individuals")
                return pool

        except Exception as e:
            logger.error(f"Failed to load genetic pool: {e}")
            return self._pool_cache or []

    def _extract_blocks_from_strategy(self, strategy: Strategy) -> List[str]:
        """
        Extract block IDs from strategy code/parameters.

        Looks for:
        1. parameters['blocks_used'] (if saved during generation)
        2. Pattern in docstring: "Blocks: RSI_OVERSOLD, VOLUME_SPIKE"
        """
        # Try parameters first (most reliable)
        if strategy.parameters and 'blocks_used' in strategy.parameters:
            blocks = strategy.parameters['blocks_used']
            if blocks and isinstance(blocks, list):
                return blocks

        # Parse from code docstring
        if strategy.code:
            match = re.search(r'Blocks:\s*([A-Z_,\s]+)', strategy.code)
            if match:
                blocks_str = match.group(1)
                blocks = [b.strip() for b in blocks_str.split(',') if b.strip()]
                # Validate block IDs
                return [b for b in blocks if b in BLOCKS_BY_ID]

        return []

    def _detect_direction(self, code: str) -> str:
        """Detect direction from strategy code."""
        code_lower = code.lower() if code else ""
        if "direction = 'short'" in code_lower or "direction='short'" in code_lower:
            return 'short'
        return 'long'

    def generate(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        count: int = 1,
    ) -> List[GeneticResult]:
        """
        Generate evolved strategies from genetic pool.

        Args:
            timeframe: Target timeframe (random if None)
            direction: 'long', 'short', or None (random)
            count: Number of strategies to generate

        Returns:
            List of GeneticResult with evolved strategy code
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
            dir_from_selector, _ = self.selector.select()
            direction = dir_from_selector.lower()  # pattern_gen uses lowercase

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
                f"Genetic: evolved {len(results)} strategies "
                f"({timeframe}, {direction})"
            )

        return results

    def _evolve_one(
        self,
        pool: List[GeneticIndividual],
        timeframe: str,
        direction: str,
    ) -> Optional[GeneticResult]:
        """
        Evolve a single strategy from pool.

        Args:
            pool: Filtered genetic pool
            timeframe: Target timeframe
            direction: Target direction

        Returns:
            GeneticResult or None if evolution fails
        """
        try:
            # Selection (tournament)
            parent1 = tournament_selection(pool, self.tournament_size, self.rng)
            parent2 = tournament_selection(pool, self.tournament_size, self.rng)

            # Crossover
            if self.rng.random() < self.crossover_rate:
                child_blocks = crossover_blocks(parent1, parent2, self.rng)
            else:
                # No crossover - clone parent1
                child_blocks = parent1.blocks.copy()

            # Mutation
            child_blocks = mutate_blocks(child_blocks, self.mutation_rate, self.rng)

            if not child_blocks:
                return None

            # Compose formula from evolved blocks
            formula = self.composer.compose_from_blocks(
                block_ids=child_blocks,
                direction=direction
            )

            if not formula:
                return None

            # Render to strategy code
            return self._render_strategy(
                formula=formula,
                timeframe=timeframe,
                parent_ids=[parent1.strategy_id, parent2.strategy_id]
            )

        except Exception as e:
            logger.error(f"Evolution failed: {e}")
            return None

    def _render_strategy(
        self,
        formula: ComposedFormula,
        timeframe: str,
        parent_ids: List[str],
    ) -> Optional[GeneticResult]:
        """
        Render evolved formula into complete strategy code.

        Args:
            formula: Composed formula from evolution
            timeframe: Target timeframe
            parent_ids: Parent strategy IDs (for lineage)

        Returns:
            GeneticResult or None if rendering fails
        """
        try:
            # Generate unique strategy ID (8 char UUID, consistent with other generators)
            strategy_id = uuid.uuid4().hex[:8]

            # Pick random exit parameters
            sl_pct = self.rng.choice(self.SL_RANGE)
            tp_pct = self.rng.choice(self.TP_RANGE)
            leverage = self.rng.choice(self.LEVERAGE_RANGE)
            exit_bars = self.rng.choice(self.EXIT_BARS_RANGE)

            # close_based: time exit is primary (exit_bars > 0)
            # touch_based: SL/TP are primary (exit_bars == 0)
            execution_type = 'close_based' if exit_bars > 0 else 'touch_based'

            # Class name: PGgStrat_{type}_{id}
            class_name = f"PGgStrat_{formula.strategy_type}_{strategy_id}"

            # Prepare template context
            context = {
                'class_name': class_name,
                'strategy_id': strategy_id,
                'strategy_type': formula.strategy_type,
                'pattern_name': f"Evolved: {formula.name}",
                'direction': formula.direction,
                'timeframe': timeframe,
                'composition_type': 'genetic',
                'blocks_used': formula.blocks_used,
                'lookback': formula.lookback,
                'indicator_code': formula.indicator_code,
                'entry_signal_code': formula.entry_signal_code,
                'indicators': formula.indicators,  # For indicator_columns
                'sl_pct': sl_pct,
                'tp_pct': tp_pct,
                'leverage': leverage,
                'exit_bars': exit_bars,
                'execution_type': execution_type,
                'generated_at': datetime.now(timezone.utc).isoformat(),
            }

            # Render template
            template = self.jinja_env.get_template("pattern_gen_strategy.j2")
            code = template.render(**context)

            # Compute base code hash
            base_code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]

            # Get coins via selector (direction from formula)
            strategy_direction = formula.direction.upper()
            _, coins = self.selector.select(direction_override=strategy_direction)

            return GeneticResult(
                code=code,
                strategy_id=strategy_id,
                strategy_type=formula.strategy_type,
                timeframe=timeframe,
                base_code_hash=base_code_hash,
                formula_hash=formula.formula_id,
                trading_coins=coins,
                direction=formula.direction,
                pattern_name=f"Evolved: {formula.name}",
                blocks_used=formula.blocks_used,
                composition_type='genetic',
                is_genetic=True,
                parent_ids=parent_ids,
                parameters={
                    'sl_pct': sl_pct,
                    'tp_pct': tp_pct,
                    'leverage': leverage,
                    'exit_bars': exit_bars,
                    'formula_params': formula.params,
                    'parent_ids': parent_ids,
                    'blocks_used': formula.blocks_used,
                },
            )

        except Exception as e:
            logger.error(f"Failed to render genetic strategy: {e}")
            return None

    def get_pool_stats(self) -> dict:
        """
        Get statistics about the genetic pool.

        Returns:
            Dict with pool statistics
        """
        pool = self.get_pool()

        if not pool:
            return {
                'size': 0,
                'min_fitness': 0,
                'max_fitness': 0,
                'avg_fitness': 0,
                'unique_blocks': 0,
                'directions': {'long': 0, 'short': 0},
            }

        fitnesses = [ind.fitness for ind in pool]
        all_blocks = set()
        directions = {'long': 0, 'short': 0}

        for ind in pool:
            all_blocks.update(ind.blocks)
            if ind.direction in directions:
                directions[ind.direction] += 1

        return {
            'size': len(pool),
            'min_fitness': min(fitnesses),
            'max_fitness': max(fitnesses),
            'avg_fitness': sum(fitnesses) / len(fitnesses),
            'unique_blocks': len(all_blocks),
            'directions': directions,
        }
