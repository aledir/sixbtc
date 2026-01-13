"""
Pattern Generator - Main class for pattern-based strategy generation.

Generates ~15,000-20,000 unique trading strategies using:
- 50% Parametric: Single blocks with varied parameters
- 30% Template: 2-3 blocks combined with AND logic
- 20% Innovative: Sequential, multi-lookback, volatility regime

Output naming: PGnStrat_{type}_{hash}
Database field: generation_mode = "pattern_gen"
"""

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from src.generator.pattern_gen.formula_composer import ComposedFormula, FormulaComposer
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class PatternGenResult:
    """Result of pattern-gen strategy generation."""

    code: str
    strategy_id: str
    strategy_type: str                  # 'THR', 'CRS', 'VOL', 'PRC', 'STA'
    timeframe: str
    base_code_hash: str
    formula_hash: str
    generation_mode: str = "pattern_gen"
    ai_provider: str = "pattern_gen"
    direction: str = "long"
    pattern_name: str = ""
    blocks_used: List[str] = field(default_factory=list)
    composition_type: str = "parametric"
    is_genetic: bool = False            # True if from genetic evolution
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


class PatternGenGenerator:
    """
    Pattern-based strategy generator.

    Uses FormulaComposer to create trading formulas from building blocks,
    then renders them into complete strategy code via Jinja2 template.
    """

    # Default timeframes matching sixbtc config
    DEFAULT_TIMEFRAMES = ['15m', '30m', '1h', '2h']

    # SL/TP/Leverage parameter ranges for strategy generation
    SL_RANGE = [0.02, 0.03, 0.04, 0.05]
    TP_RANGE = [0.03, 0.04, 0.06, 0.08]
    LEVERAGE_RANGE = [2, 3, 5]
    EXIT_BARS_RANGE = [20, 40, 60, 0]  # 0 = no time exit

    def __init__(self, config: dict, seed: Optional[int] = None):
        """
        Initialize generator.

        Args:
            config: Application config dict (from config.yaml)
            seed: Optional random seed for reproducibility
        """
        self.config = config
        self.rng = random.Random(seed)
        self.seed = seed
        self.composer = FormulaComposer(seed=seed)

        # Load ratios from config (or defaults)
        gen_config = config.get('generation', {})
        self.pattern_gen_config = gen_config.get('strategy_sources', {}).get('pattern_gen', {})

        self.parametric_ratio = self.pattern_gen_config.get('parametric_ratio', 0.50)
        self.template_ratio = self.pattern_gen_config.get('template_ratio', 0.30)
        self.innovative_ratio = self.pattern_gen_config.get('innovative_ratio', 0.20)

        # Genetic config (Phase 2)
        genetic_config = self.pattern_gen_config.get('genetic', {})
        self.genetic_enabled = genetic_config.get('enabled', False)
        self.genetic_min_pool_size = genetic_config.get('min_pool_size', 50)
        self.smart_ratio = genetic_config.get('smart_ratio', 0.70)
        self.genetic_ratio = genetic_config.get('genetic_ratio', 0.30)

        # Lazy init genetic generator
        self._genetic_generator = None

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        template_dir.mkdir(exist_ok=True)

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Get configured timeframes
        trading_config = config.get('trading', {})
        timeframes_config = trading_config.get('timeframes', {})
        self.timeframes = list(timeframes_config.values()) if timeframes_config else self.DEFAULT_TIMEFRAMES

        genetic_status = "enabled" if self.genetic_enabled else "disabled"
        logger.info(
            f"PatternGenGenerator initialized: ratios={self.parametric_ratio:.0%}/"
            f"{self.template_ratio:.0%}/{self.innovative_ratio:.0%}, "
            f"genetic={genetic_status}, {len(self.timeframes)} timeframes"
        )

    @property
    def genetic_generator(self):
        """Lazy-init genetic generator."""
        if self._genetic_generator is None:
            from src.generator.pattern_gen.genetic_generator import GeneticPatternGenerator
            self._genetic_generator = GeneticPatternGenerator(self.config, seed=self.seed)
        return self._genetic_generator

    def _get_generation_mode(self) -> str:
        """
        Adaptive mode selection.

        Phases:
        - Bootstrap (pool < min_pool_size): Smart only
        - Smart exhausted: Genetic only
        - Normal: smart_ratio / genetic_ratio

        Returns:
            'smart' or 'genetic'
        """
        if not self.genetic_enabled:
            return 'smart'

        # Check pool size
        pool_size = self._count_active_pattern_gen()
        if pool_size < self.genetic_min_pool_size:
            return 'smart'  # Bootstrap phase

        # Check if smart exhausted (dedup cache full)
        estimated_max = self._estimate_max_patterns()
        if self.composer.get_cache_size() >= estimated_max * 0.9:  # 90% exhausted
            return 'genetic'

        # Ratio-based selection
        return 'smart' if self.rng.random() < self.smart_ratio else 'genetic'

    def _count_active_pattern_gen(self) -> int:
        """Count ACTIVE strategies from pattern_gen."""
        try:
            from src.database import get_session, Strategy
            with get_session() as session:
                return session.query(Strategy).filter(
                    Strategy.status == 'ACTIVE',
                    Strategy.generation_mode == 'pattern_gen'
                ).count()
        except Exception:
            return 0

    def _estimate_max_patterns(self) -> int:
        """Estimate maximum unique smart patterns."""
        estimates = self.estimate_total_strategies()
        return estimates.get('total_base', 1000)

    def generate(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        count: int = 1,
    ) -> List[PatternGenResult]:
        """
        Generate pattern-based strategies using adaptive mode.

        Automatically selects between Smart and Genetic generation
        based on pool size and exhaustion state.

        Args:
            timeframe: Target timeframe (random if None)
            direction: 'long', 'short', or 'bidi' (random if None)
            count: Number of strategies to generate

        Returns:
            List of PatternGenResult with generated strategy code
        """
        mode = self._get_generation_mode()

        if mode == 'genetic':
            # Use genetic generator
            genetic_results = self.genetic_generator.generate(
                timeframe=timeframe,
                direction=direction,
                count=count
            )
            # Convert GeneticResult to PatternGenResult for uniform interface
            return [self._convert_genetic_result(r) for r in genetic_results]
        else:
            # Use smart generator
            return self._generate_smart(timeframe, direction, count)

    def _convert_genetic_result(self, genetic_result) -> PatternGenResult:
        """Convert GeneticResult to PatternGenResult."""
        return PatternGenResult(
            code=genetic_result.code,
            strategy_id=genetic_result.strategy_id,
            strategy_type=genetic_result.strategy_type,
            timeframe=genetic_result.timeframe,
            base_code_hash=genetic_result.base_code_hash,
            formula_hash=genetic_result.formula_hash,
            generation_mode=genetic_result.generation_mode,
            ai_provider=genetic_result.ai_provider,
            direction=genetic_result.direction,
            pattern_name=genetic_result.pattern_name,
            blocks_used=genetic_result.blocks_used,
            composition_type='genetic',
            is_genetic=True,
            validation_passed=genetic_result.validation_passed,
            validation_errors=genetic_result.validation_errors,
            parameters=genetic_result.parameters,
        )

    def _generate_smart(
        self,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        count: int = 1,
    ) -> List[PatternGenResult]:
        """
        Generate using Smart (parametric/template/innovative) method.

        This is the original generate logic.
        """
        if timeframe is None:
            timeframe = self.rng.choice(self.timeframes)

        if direction is None:
            direction = self.rng.choice(['long', 'short'])

        # Calculate counts based on ratios
        parametric_count = max(1, int(count * self.parametric_ratio))
        template_count = max(1, int(count * self.template_ratio))
        innovative_count = max(0, count - parametric_count - template_count)

        # Compose formulas
        formulas = self.composer.compose_all(
            parametric_count=parametric_count,
            template_count=template_count,
            innovative_count=innovative_count,
            direction=direction,
        )

        # Shuffle and limit
        self.rng.shuffle(formulas)
        formulas = formulas[:count]

        # Render each formula into strategy code
        results = []
        for formula in formulas:
            result = self._render_strategy(formula, timeframe)
            if result:
                results.append(result)

        logger.info(
            f"PatternGen (smart): generated {len(results)} strategies "
            f"({timeframe}, {direction})"
        )

        return results

    def generate_batch(
        self,
        batch_size: int = 10,
        timeframe: Optional[str] = None,
    ) -> List[PatternGenResult]:
        """
        Generate a batch of strategies with mixed directions.

        Args:
            batch_size: Total number of strategies
            timeframe: Target timeframe (random if None)

        Returns:
            List of PatternGenResult
        """
        if timeframe is None:
            timeframe = self.rng.choice(self.timeframes)

        # Split batch between long and short
        long_count = batch_size // 2
        short_count = batch_size - long_count

        results = []
        results.extend(self.generate(timeframe, 'long', long_count))
        results.extend(self.generate(timeframe, 'short', short_count))

        return results

    def _render_strategy(
        self,
        formula: ComposedFormula,
        timeframe: str,
    ) -> Optional[PatternGenResult]:
        """
        Render a composed formula into complete strategy code.

        Args:
            formula: The composed formula
            timeframe: Target timeframe

        Returns:
            PatternGenResult or None if rendering fails
        """
        try:
            # Generate unique strategy ID from formula hash + random suffix
            random_suffix = hashlib.sha256(
                f"{formula.formula_id}{self.rng.random()}".encode()
            ).hexdigest()[:4]
            strategy_id = f"{formula.formula_id}{random_suffix}"

            # Pick random exit parameters
            sl_pct = self.rng.choice(self.SL_RANGE)
            tp_pct = self.rng.choice(self.TP_RANGE)
            leverage = self.rng.choice(self.LEVERAGE_RANGE)
            exit_bars = self.rng.choice(self.EXIT_BARS_RANGE)

            # Execution type based on exit bars
            # close_based: time exit is primary (exit_bars > 0)
            # touch_based: SL/TP are primary (exit_bars == 0)
            execution_type = 'close_based' if exit_bars > 0 else 'touch_based'

            # Class name: PGnStrat_{type}_{id}
            class_name = f"PGnStrat_{formula.strategy_type}_{strategy_id}"

            # Prepare template context
            context = {
                'class_name': class_name,
                'strategy_id': strategy_id,
                'strategy_type': formula.strategy_type,
                'pattern_name': formula.name,
                'direction': formula.direction,
                'timeframe': timeframe,
                'composition_type': formula.composition_type,
                'blocks_used': formula.blocks_used,
                'lookback': formula.lookback,
                'indicator_code': formula.indicator_code,
                'entry_signal_code': formula.entry_signal_code,
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

            # Compute base code hash (for dedup and shuffle test caching)
            base_code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]

            return PatternGenResult(
                code=code,
                strategy_id=strategy_id,
                strategy_type=formula.strategy_type,
                timeframe=timeframe,
                base_code_hash=base_code_hash,
                formula_hash=formula.formula_id,
                direction=formula.direction,
                pattern_name=formula.name,
                blocks_used=formula.blocks_used,
                composition_type=formula.composition_type,
                parameters={
                    'sl_pct': sl_pct,
                    'tp_pct': tp_pct,
                    'leverage': leverage,
                    'exit_bars': exit_bars,
                    'formula_params': formula.params,
                },
            )

        except Exception as e:
            logger.error(f"Failed to render strategy from {formula.name}: {e}")
            return None

    def estimate_total_strategies(self) -> dict:
        """
        Estimate total number of unique strategies possible.

        Returns:
            Dict with estimates by composition type
        """
        from src.generator.pattern_gen.building_blocks import (
            ALL_BLOCKS,
            BLOCKS_BY_CATEGORY,
        )

        # Parametric: each block × param combinations
        parametric_count = 0
        for block in ALL_BLOCKS:
            combos = 1
            for values in block.params.values():
                if isinstance(values, list):
                    combos *= len(values)
            parametric_count += combos

        # Template: pairs of compatible blocks
        template_count = 0
        for block in ALL_BLOCKS:
            for cat in block.combinable_with:
                template_count += len(BLOCKS_BY_CATEGORY.get(cat, []))

        # Innovative: roughly 30% of template possibilities
        innovative_count = int(template_count * 0.3)

        # Per timeframe and direction
        multiplier = len(self.timeframes) * 2  # long + short

        return {
            'parametric': parametric_count,
            'template': template_count,
            'innovative': innovative_count,
            'total_base': parametric_count + template_count + innovative_count,
            'total_with_tf_dir': (parametric_count + template_count + innovative_count) * multiplier,
        }

    def get_dedup_cache_size(self) -> int:
        """Get current size of deduplication cache."""
        return self.composer.get_cache_size()

    def clear_dedup_cache(self) -> None:
        """Clear the deduplication cache."""
        self.composer.clear_cache()
