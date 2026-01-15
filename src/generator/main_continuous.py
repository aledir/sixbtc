"""
Continuous Generator Process

Generates trading strategies using AI in a continuous loop.
Uses backpressure-based flow control instead of arbitrary daily limits.
"""

import asyncio
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
import random

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
from src.generator.strategy_builder import StrategyBuilder
from src.generator.pattern_fetcher import PatternFetcher
from src.generator.ai_call_tracker import AICallTracker, seconds_until_midnight
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file='logs/generator.log',
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousGeneratorProcess:
    """
    Continuous strategy generation process.

    Features:
    - ThreadPoolExecutor for parallel AI calls
    - Backpressure-based flow control (pauses when queue is full)
    - Generates ALL parametric variations per template
    - Graceful shutdown handling
    """

    def __init__(self):
        """Initialize the generator process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration
        generation_config = self.config.get('generation', {})
        self.parallel_threads = generation_config.get('parallel_threads', 1)
        self.min_interval = generation_config.get('min_interval_seconds', 0)
        self._last_generation_time = datetime.min

        # Pipeline backpressure configuration (hysteresis system)
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        backpressure_config = pipeline_config.get('backpressure', {})
        monitoring_config = pipeline_config.get('monitoring', {})
        validated_bp = pipeline_config.get('validated_backpressure', {})

        self.generated_limit = queue_limits.get('generated', 100)
        self.check_interval = backpressure_config.get('check_interval', 10)
        self.base_cooldown = backpressure_config.get('base_cooldown', 30)
        self.max_cooldown = backpressure_config.get('max_cooldown', 120)
        self.cooldown_increment = backpressure_config.get('cooldown_increment', 2)
        self.log_interval = monitoring_config.get('log_interval', 30)
        self._last_log_time = datetime.min

        # Hysteresis backpressure for VALIDATED queue
        self.validated_low = validated_bp.get('low_threshold', 20)
        self.validated_high = validated_bp.get('high_threshold', 50)
        self._generating = True  # Hysteresis state: True = generating, False = paused

        # ThreadPoolExecutor for parallel generation
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Generator"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}

        # Strategy builder (lazy init to avoid import issues)
        self._strategy_builder: Optional[StrategyBuilder] = None

        # Pattern fetcher for checking available patterns
        pattern_api_url = self.config['pattern_discovery']['api_url']
        self.pattern_fetcher = PatternFetcher(api_url=pattern_api_url)

        # Strategy processor for database queries
        self.strategy_processor = StrategyProcessor(process_id="generator")

        # Cache for unused patterns (refreshed periodically)
        self._unused_patterns_cache: list = []
        self._cache_refresh_interval = 300  # 5 minutes
        self._last_cache_refresh = datetime.min

        # AI Call Tracker (daily limit)
        ai_limit_config = self.config['ai']['daily_limit']
        if ai_limit_config['enabled']:
            self.ai_tracker = AICallTracker(
                max_calls=ai_limit_config['max_calls']
            )
            logger.info(
                f"AI daily limit enabled: {ai_limit_config['max_calls']} calls/day"
            )
        else:
            self.ai_tracker = None
            logger.info("AI daily limit disabled")

        # Round-robin source selection
        self._source_index = 0
        self._enabled_sources = self._get_enabled_sources()

        logger.info(
            f"ContinuousGeneratorProcess initialized: "
            f"{self.parallel_threads} threads, "
            f"backpressure: GEN={self.generated_limit}, VAL=[{self.validated_low}-{self.validated_high}], "
            f"sources: {self._enabled_sources}"
        )

    @property
    def strategy_builder(self) -> StrategyBuilder:
        """Lazy-init strategy builder"""
        if self._strategy_builder is None:
            self._strategy_builder = StrategyBuilder(self.config)
        return self._strategy_builder

    def _check_backpressure(self) -> Tuple[bool, int, int]:
        """
        Check if we should pause generation using hysteresis logic.

        Hysteresis prevents oscillation between generating/pausing:
        - If generating and validated_queue > high_threshold → pause
        - If paused and validated_queue < low_threshold → resume
        - Otherwise maintain current state

        Also checks GENERATED queue with simple threshold.

        Returns:
            (should_pause, queue_count, cooldown_seconds) tuple
        """
        try:
            generated_count = self.strategy_processor.count_available("GENERATED")
            validated_count = self.strategy_processor.count_available("VALIDATED")

            # Hysteresis logic for VALIDATED queue (the real bottleneck)
            if self._generating and validated_count > self.validated_high:
                # Was generating, queue too full -> pause
                self._generating = False
                logger.info(
                    f"Backpressure: VALIDATED queue high ({validated_count} > {self.validated_high}), "
                    f"pausing generation"
                )
            elif not self._generating and validated_count < self.validated_low:
                # Was paused, queue drained enough -> resume
                self._generating = True
                logger.info(
                    f"Backpressure: VALIDATED queue low ({validated_count} < {self.validated_low}), "
                    f"resuming generation"
                )

            # If hysteresis says pause, use cooldown
            if not self._generating:
                return (True, validated_count, self.base_cooldown)

            # Also check GENERATED queue (simple threshold, not hysteresis)
            if generated_count >= self.generated_limit:
                cooldown = self.strategy_processor.calculate_backpressure_cooldown(
                    generated_count,
                    self.generated_limit,
                    self.base_cooldown,
                    self.cooldown_increment,
                    self.max_cooldown
                )
                return (True, generated_count, cooldown)

            return (False, generated_count + validated_count, 0)

        except Exception as e:
            logger.error(f"Failed to check backpressure: {e}")
            return (False, 0, 0)

    def _log_pipeline_status(self):
        """Log pipeline status periodically for monitoring"""
        now = datetime.now()
        if (now - self._last_log_time).total_seconds() < self.log_interval:
            return

        try:
            depths = self.strategy_processor.get_queue_depths()
            val_count = depths.get('VALIDATED', 0)
            state = "GEN" if self._generating else "PAUSE"
            logger.info(
                f"Pipeline [{state}]: GEN={depths.get('GENERATED', 0)}/{self.generated_limit} "
                f"VAL={val_count}/[{self.validated_low}-{self.validated_high}] "
                f"ACT={depths.get('ACTIVE', 0)} LIVE={depths.get('LIVE', 0)}"
            )
            self._last_log_time = now
        except Exception as e:
            logger.debug(f"Failed to log pipeline status: {e}")

    def _fetch_unused_patterns(self) -> List:
        """
        Fetch all Tier 1 patterns that haven't been used yet.

        Uses multi-target expansion to create virtual patterns for each
        validated target (e.g., one pattern with 3 targets -> 3 virtual patterns).

        Fetches from multiple tiers based on config (tiers.enabled).

        Returns:
            List of unused Pattern objects (including virtual patterns)
        """
        try:
            # Get pattern_discovery config section
            pd_config = self.config.get('pattern_discovery', {})
            multi_target_config = pd_config.get('multi_target', {})
            expand_enabled = multi_target_config.get('enabled', True)

            # Fetch patterns from all enabled tiers with multi-target expansion
            all_patterns = self.pattern_fetcher.get_multi_tier_patterns_expanded(
                config=pd_config,
                limit_per_tier=50,  # 50 per tier, sorted by weighted score
                expand_multi_target=expand_enabled
            )

            if not all_patterns:
                # Pattern API unavailable or no patterns - not an error
                # Fall back to AI-only generation (valid generation method)
                logger.warning("No patterns available from pattern-discovery API, will use AI-only generation")
                return []

            # Get patterns that have been used (all time)
            used_ids = self.strategy_processor.get_used_pattern_ids()
            unused = [p for p in all_patterns if p.id not in used_ids]

            # Log expansion stats
            base_count = len([p for p in all_patterns if not p.is_virtual])
            virtual_count = len([p for p in all_patterns if p.is_virtual])

            logger.info(
                f"Found {len(unused)} unused patterns "
                f"(out of {len(all_patterns)} total: {base_count} base + {virtual_count} virtual)"
            )

            return unused

        except Exception as e:
            logger.error(f"Failed to fetch patterns: {e}")
            return []

    def _get_unused_patterns(self) -> list:
        """Get patterns that haven't been used yet (cached)."""
        now = datetime.now()
        cache_age = (now - self._last_cache_refresh).total_seconds()

        if cache_age < self._cache_refresh_interval and self._unused_patterns_cache:
            return self._unused_patterns_cache

        self._unused_patterns_cache = self._fetch_unused_patterns()
        self._last_cache_refresh = now

        return self._unused_patterns_cache

    def _should_use_patterns(self) -> Tuple[bool, List]:
        """
        Decide whether to use pattern-based or custom AI generation.

        Returns:
            (use_patterns, patterns) tuple
        """
        unused_patterns = self._get_unused_patterns()

        if unused_patterns:
            # Use exactly 1 pattern per strategy (no combining)
            # DETERMINISTIC: sort by id for reproducible order (not random)
            sorted_patterns = sorted(unused_patterns, key=lambda p: p.id)
            selected = [sorted_patterns[0]]

            # Remove from cache
            self._unused_patterns_cache = [
                p for p in self._unused_patterns_cache
                if p.id != selected[0].id
            ]

            logger.info(f"Using pattern for generation: {selected[0].name}")
            return (True, selected)
        else:
            logger.info("All patterns used, using custom AI generation")
            return (False, [])

    def _is_source_enabled(self, source_name: str) -> bool:
        """Check if a generation source is enabled in config."""
        sources = self.config.get('generation', {}).get('strategy_sources', {})
        return sources.get(source_name, {}).get('enabled', False)

    def _get_enabled_sources(self) -> List[str]:
        """
        Get list of enabled generation sources in priority order.

        Order: pattern, pattern_gen, unger, pandas_ta, ai_free, ai_assigned
        This order determines round-robin sequence.

        Returns:
            List of enabled source names
        """
        all_sources = ['pattern', 'pattern_gen', 'unger', 'pandas_ta', 'ai_free', 'ai_assigned']
        return [s for s in all_sources if self._is_source_enabled(s)]

    def _get_next_source(self) -> Optional[str]:
        """
        Get next source in round-robin rotation.

        Returns:
            Source name or None if no sources enabled
        """
        if not self._enabled_sources:
            return None

        source = self._enabled_sources[self._source_index % len(self._enabled_sources)]
        self._source_index += 1
        return source

    def _should_use_unger(self) -> Tuple[bool, Optional[str]]:
        """
        Check if should use Unger regime-based generation.

        Returns:
            (use_unger, regime_type) tuple.
            If no regime coins available, returns (True, None) to let
            the generator use its internal fallback to all tradeable coins.
        """
        if not self._is_source_enabled('unger'):
            return (False, None)

        try:
            from src.generator.unger import UngerGenerator

            unger_gen = UngerGenerator(self.config)
            trend_coins = unger_gen.get_regime_coins('TREND')
            reversal_coins = unger_gen.get_regime_coins('REVERSAL')

            if trend_coins or reversal_coins:
                # Select regime with more coins, or random if equal
                if len(trend_coins) > len(reversal_coins):
                    regime_type = "TREND"
                elif len(reversal_coins) > len(trend_coins):
                    regime_type = "REVERSAL"
                else:
                    regime_type = random.choice(["TREND", "REVERSAL"])

                logger.info(
                    f"Unger available: TREND={len(trend_coins)}, REVERSAL={len(reversal_coins)}, "
                    f"selected={regime_type}"
                )
                return (True, regime_type)

            # No regime coins, but generator has fallback to all tradeable coins
            logger.info("No regime coins, Unger will use all tradeable coins fallback")
            return (True, None)

        except Exception as e:
            logger.warning(f"Unger check failed: {e}")
            return (False, None)

    def _generate_unger_batch(self, timeframe: str, regime_type: Optional[str]) -> Tuple[bool, int, str]:
        """
        Generate Unger v2 strategies for given regime type.

        Uses the new Unger Generator v2 with:
        - 128 entry conditions (9 categories)
        - 92 entry filters (6 categories)
        - 11 exit mechanisms
        - ~15-30M possible strategies

        When genetic mode is enabled and ACTIVE pool is sufficient,
        uses ratio to mix smart (random combination) and genetic (crossover/mutation).

        Args:
            timeframe: Target timeframe
            regime_type: 'TREND', 'REVERSAL', or None (uses all tradeable coins)

        Returns:
            (success, count, template_id) tuple
        """
        try:
            from src.generator.unger import UngerGenerator, GeneticUngerGenerator

            gen_start = time.time()

            # Check if genetic mode should be used
            use_genetic = self._should_use_unger_genetic()

            if use_genetic:
                # Use genetic generator (evolves from ACTIVE pool)
                genetic_gen = GeneticUngerGenerator(self.config)
                direction = random.choice(['long', 'short'])

                results = genetic_gen.generate(
                    timeframe=timeframe,
                    direction=direction,
                    count=1
                )

                if results:
                    gen_duration_ms = int((time.time() - gen_start) * 1000)
                    return self._save_unger_results(results, gen_duration_ms, is_genetic=True)

                # Fallback to smart if genetic failed (empty pool, etc.)
                logger.debug("Genetic generation returned no results, falling back to smart")

            # Smart mode: random combination from catalog
            unger_gen = UngerGenerator(self.config)

            # Generate one strategy for the regime (None = mixed/all coins fallback)
            results = unger_gen.generate(
                timeframe=timeframe,
                regime_type=regime_type,
                count=1
            )

            gen_duration_ms = int((time.time() - gen_start) * 1000)

            if not results:
                logger.debug(f"No Unger strategy generated for {regime_type or 'MIXED'}")
                return (False, 0, "no_results")

            return self._save_unger_results(results, gen_duration_ms, is_genetic=False)

        except Exception as e:
            logger.error(f"Unger generation error: {e}", exc_info=True)
            return (False, 0, str(e))

    def _should_use_unger_genetic(self) -> bool:
        """
        Determine if genetic mode should be used for Unger generation.

        Uses smart_ratio/genetic_ratio from config with probabilistic selection.
        Requires sufficient ACTIVE pool of unger strategies.

        Returns:
            True if should use genetic mode this iteration
        """
        try:
            unger_config = self.config.get('generation', {}).get('strategy_sources', {}).get('unger', {})
            genetic_config = unger_config.get('genetic', {})

            if not genetic_config.get('enabled', False):
                return False

            min_pool_size = genetic_config.get('min_pool_size', 50)
            genetic_ratio = genetic_config.get('genetic_ratio', 0.30)

            # Check ACTIVE pool size for unger strategies
            from sqlalchemy import select, func
            from src.database.models import Strategy
            from src.database.connection import get_session

            with get_session() as session:
                pool_count = session.execute(
                    select(func.count(Strategy.id)).where(
                        Strategy.status == 'ACTIVE',
                        Strategy.generation_mode == 'unger'
                    )
                ).scalar() or 0

            if pool_count < min_pool_size:
                return False

            # Probabilistic selection based on ratio
            return random.random() < genetic_ratio

        except Exception as e:
            logger.debug(f"Genetic check failed: {e}")
            return False

    def _save_unger_results(
        self,
        results: list,
        gen_duration_ms: int,
        is_genetic: bool
    ) -> Tuple[bool, int, str]:
        """
        Save Unger generation results to database.

        Args:
            results: List of UngerGeneratedStrategy or UngerGeneticResult
            gen_duration_ms: Generation duration in milliseconds
            is_genetic: True if from genetic generator

        Returns:
            (success, count, source_name) tuple
        """
        saved_count = 0
        for result in results:
            # Determine prefix and mode based on genetic flag
            if is_genetic:
                prefix = "UggStrat"
                gen_mode = "unger_genetic"
            else:
                prefix = "UngStrat"
                gen_mode = "unger"

            strategy_name = f"{prefix}_{result.strategy_type}_{result.strategy_id}"

            self._save_to_database(
                name=strategy_name,
                strategy_type=result.strategy_type,
                timeframe=result.timeframe,
                code=result.code,
                ai_provider="unger",
                pattern_based=False,
                pattern_ids=[],
                template_id=None,
                parameters=result.parameters,
                trading_coins=getattr(result, 'trading_coins', None),
                base_code_hash=result.base_code_hash,
                generation_mode=gen_mode,
                duration_ms=gen_duration_ms,
                leverage=None
            )
            saved_count += 1

            # Log with appropriate details
            if is_genetic:
                parent_ids = getattr(result, 'parent_ids', [])
                logger.info(
                    f"Saved {strategy_name} "
                    f"(genetic, {result.direction}, parents={len(parent_ids)})"
                )
            else:
                logger.info(
                    f"Saved {strategy_name} "
                    f"({result.regime_type}, {len(result.trading_coins)} coins, "
                    f"entry={result.entry_name}, exit={result.exit_mechanism_name})"
                )

        source_name = "unger_genetic" if is_genetic else "unger"
        return (True, saved_count, source_name)

    async def run_continuous(self):
        """Main continuous generation loop with multi-level backpressure"""
        logger.info("Starting continuous generation loop (multi-level backpressure)")

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Log pipeline status periodically
            self._log_pipeline_status()

            # Check backpressure with progressive cooldown
            should_pause, generated_count, cooldown = self._check_backpressure()

            if should_pause:
                # Log state (hysteresis logs transition, this logs ongoing pause)
                gen_count = self.strategy_processor.count_available("GENERATED")
                val_count = self.strategy_processor.count_available("VALIDATED")
                logger.debug(
                    f"Backpressure active: GEN={gen_count}/{self.generated_limit} "
                    f"VAL={val_count}/[{self.validated_low}-{self.validated_high}], "
                    f"cooldown {cooldown}s"
                )
                await asyncio.sleep(cooldown)
                continue

            # Start generation tasks up to parallel_threads
            while len(self.active_futures) < self.parallel_threads:
                if self.shutdown_event.is_set():
                    break

                future = self.executor.submit(self._generate_batch)
                self.active_futures[future] = f"gen_{len(self.active_futures)}"

            # Wait for any task to complete
            if self.active_futures:
                try:
                    done_futures = []
                    for future in as_completed(list(self.active_futures.keys()), timeout=1):
                        done_futures.append(future)
                        break
                except TimeoutError:
                    await asyncio.sleep(0.1)
                    continue
                except Exception:
                    await asyncio.sleep(0.1)
                    continue

                # Process completed futures
                for future in done_futures:
                    if future not in self.active_futures:
                        continue

                    task_id = self.active_futures.pop(future)

                    try:
                        success, count, template_id = future.result()
                        if success:
                            logger.info(f"Generated {count} strategies from template {template_id}")
                        else:
                            # Normal when patterns filtered out - not a real failure
                            logger.debug(f"No strategy generated for task {task_id}")
                    except Exception as e:
                        logger.error(f"Task {task_id} error: {e}")

            await asyncio.sleep(0.1)

        logger.info("Generation loop ended")

    def _generate_batch(self) -> Tuple[bool, int, str]:
        """
        Generate strategies using round-robin source selection.

        Cycles through enabled sources: pattern → unger → ai_free → ai_assigned
        Skips sources that are not available (exhausted patterns, AI limit, etc.)

        Returns:
            (success, count, source_name) tuple
        """
        try:
            # Throttling
            now = datetime.now()
            elapsed = (now - self._last_generation_time).total_seconds()
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Throttling: waiting {wait_time:.1f}s")
                time.sleep(wait_time)
            self._last_generation_time = datetime.now()

            # Calculate remaining capacity (backpressure-aware)
            generated_count = self.strategy_processor.count_available("GENERATED")
            remaining_capacity = max(0, self.generated_limit - generated_count)

            if remaining_capacity == 0:
                logger.debug("No remaining capacity, skipping generation")
                return (False, 0, "backpressure")

            # Get next source from round-robin
            source = self._get_next_source()
            if not source:
                logger.warning("No generation sources enabled")
                return (False, 0, "no_sources")

            # Select random timeframe (used by all sources)
            timeframes = self.config['timeframes']
            timeframe = random.choice(timeframes)

            # Dispatch to appropriate generator based on source
            if source == 'pattern':
                return self._generate_from_pattern(timeframe, remaining_capacity)
            elif source == 'pattern_gen':
                return self._generate_from_pattern_gen(timeframe)
            elif source == 'unger':
                return self._generate_from_unger(timeframe)
            elif source == 'pandas_ta':
                return self._generate_from_pandas_ta(timeframe)
            elif source == 'ai_free':
                return self._generate_from_ai(timeframe, remaining_capacity, source='ai_free')
            elif source == 'ai_assigned':
                return self._generate_from_ai(timeframe, remaining_capacity, source='ai_assigned')
            else:
                logger.error(f"Unknown source: {source}")
                return (False, 0, f"unknown_{source}")

        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            return (False, 0, str(e))

    def _generate_from_pattern(self, timeframe: str, remaining_capacity: int) -> Tuple[bool, int, str]:
        """Generate strategy from pattern-discovery API."""
        use_patterns, selected_patterns = self._should_use_patterns()

        if not use_patterns:
            logger.debug("No unused patterns available, skipping pattern source")
            return (False, 0, "pattern_exhausted")

        # Use pattern's timeframe (validated on that TF), not random timeframe
        pattern = selected_patterns[0]
        pattern_tf = getattr(pattern, 'timeframe', timeframe)

        return self._generate_with_builder(
            timeframe=pattern_tf,  # Use pattern's validated timeframe
            remaining_capacity=remaining_capacity,
            use_patterns=True,
            patterns=selected_patterns,
            generation_mode="pattern",
            force_source="pattern"
        )

    def _generate_from_unger(self, timeframe: str) -> Tuple[bool, int, str]:
        """Generate strategy using Unger regime-based method."""
        use_unger, regime_type = self._should_use_unger()

        if not use_unger:
            logger.debug("Unger source disabled or unavailable")
            return (False, 0, "unger_disabled")

        return self._generate_unger_batch(timeframe, regime_type)

    def _generate_from_pandas_ta(self, timeframe: str) -> Tuple[bool, int, str]:
        """
        Generate strategy using pandas_ta indicator combinations.

        Uses PandasTaGenerator to create strategies from:
        - 50+ pandas_ta indicators
        - Compatibility matrices for sensible combinations
        - 1-3 indicators per strategy (max to avoid overfitting)
        - Reused exit mechanisms from Unger

        Args:
            timeframe: Target timeframe

        Returns:
            (success, count, source_name) tuple
        """
        try:
            from src.generator.pandas_ta import PandasTaGenerator

            gen_start = time.time()
            pta_gen = PandasTaGenerator(self.config)

            # Select random regime (or None for mixed)
            regime_type = random.choice(['TREND', 'REVERSAL', None])

            # Generate one strategy
            results = pta_gen.generate(
                timeframe=timeframe,
                regime_type=regime_type,
                count=1
            )

            gen_duration_ms = int((time.time() - gen_start) * 1000)

            if not results:
                logger.debug("No pandas_ta strategy generated")
                return (False, 0, "pandas_ta_empty")

            # Save strategies
            saved_count = 0
            for result in results:
                # PtaStrat_ prefix for pandas_ta strategies
                strategy_name = f"PtaStrat_{result.strategy_type}_{result.strategy_id}"

                self._save_to_database(
                    name=strategy_name,
                    strategy_type=result.strategy_type,
                    timeframe=result.timeframe,
                    code=result.code,
                    ai_provider="pandas_ta",
                    pattern_based=False,
                    pattern_ids=[],
                    template_id=None,
                    parameters=result.parameters,
                    trading_coins=result.trading_coins,
                    base_code_hash=result.base_code_hash,
                    generation_mode="pandas_ta",
                    duration_ms=gen_duration_ms,
                    leverage=None
                )
                saved_count += 1

                logger.info(
                    f"Saved PtaStrat_{result.strategy_type}_{result.strategy_id} "
                    f"({result.regime_type}, {len(result.entry_indicators)} indicators: "
                    f"{'+'.join(result.entry_indicators)})"
                )

            return (True, saved_count, "pandas_ta")

        except Exception as e:
            logger.error(f"Pandas-TA generation error: {e}", exc_info=True)
            return (False, 0, str(e))

    def _generate_from_pattern_gen(self, timeframe: str) -> Tuple[bool, int, str]:
        """
        Generate strategy using internal pattern generator (pattern_gen).

        Uses FormulaComposer to create trading formulas from building blocks,
        then renders them into complete strategy code.

        Args:
            timeframe: Target timeframe

        Returns:
            (success, count, source_name) tuple
        """
        try:
            from src.generator.pattern_gen import PatternGenGenerator

            gen_start = time.time()
            pattern_gen = PatternGenGenerator(self.config)

            # Generate one strategy
            results = pattern_gen.generate(
                timeframe=timeframe,
                direction=random.choice(['long', 'short']),
                count=1
            )

            gen_duration_ms = int((time.time() - gen_start) * 1000)

            if not results:
                logger.debug("No pattern_gen strategy generated")
                return (False, 0, "pattern_gen_empty")

            # Save strategies
            saved_count = 0
            for result in results:
                # Determine prefix: PGnStrat_ = smart, PGgStrat_ = genetic
                is_genetic = getattr(result, 'is_genetic', False)
                prefix = "PGgStrat" if is_genetic else "PGnStrat"
                strategy_name = f"{prefix}_{result.strategy_type}_{result.strategy_id}"

                # Use generation_mode from result (pattern_gen or pattern_gen_genetic)
                gen_mode = getattr(result, 'generation_mode', 'pattern_gen')

                self._save_to_database(
                    name=strategy_name,
                    strategy_type=result.strategy_type,
                    timeframe=result.timeframe,
                    code=result.code,
                    ai_provider="pattern_gen",
                    pattern_based=False,
                    pattern_ids=[],
                    template_id=None,
                    parameters=result.parameters,
                    trading_coins=result.trading_coins,
                    base_code_hash=result.base_code_hash,
                    generation_mode=gen_mode,
                    duration_ms=gen_duration_ms,
                    leverage=result.parameters.get('leverage')
                )
                saved_count += 1

                mode_str = "genetic" if is_genetic else result.composition_type
                logger.info(
                    f"Saved {prefix}_{result.strategy_type}_{result.strategy_id} "
                    f"({mode_str}, {result.direction}, blocks={result.blocks_used})"
                )

            return (True, saved_count, "pattern_gen")

        except Exception as e:
            logger.error(f"Pattern-gen generation error: {e}", exc_info=True)
            return (False, 0, str(e))

    def _generate_from_ai(
        self, timeframe: str, remaining_capacity: int, source: str
    ) -> Tuple[bool, int, str]:
        """Generate strategy using AI (ai_free or ai_assigned)."""
        # Check AI daily limit
        if self.ai_tracker and not self.ai_tracker.can_call():
            wait_seconds = seconds_until_midnight()
            logger.info(
                f"AI daily limit reached ({self.ai_tracker.count}/{self.ai_tracker.max_calls}). "
                f"Waiting {wait_seconds/3600:.1f}h until reset."
            )
            return (False, 0, "ai_daily_limit")

        return self._generate_with_builder(
            timeframe=timeframe,
            remaining_capacity=remaining_capacity,
            use_patterns=False,
            patterns=[],
            generation_mode=source,
            force_source=source
        )

    def _generate_with_builder(
        self,
        timeframe: str,
        remaining_capacity: int,
        use_patterns: bool,
        patterns: list,
        generation_mode: str,
        force_source: Optional[str] = None
    ) -> Tuple[bool, int, str]:
        """
        Generate strategies using StrategyBuilder.

        Shared logic for pattern and AI-based generation.
        """
        # Select random strategy type
        strategy_types = ['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']
        strategy_type = random.choice(strategy_types)

        # Track generation time
        gen_start = time.time()

        # Generate strategies with capacity limit
        results = self.strategy_builder.generate_strategies(
            strategy_type=strategy_type,
            timeframe=timeframe,
            use_patterns=use_patterns,
            patterns=patterns,
            max_strategies=remaining_capacity,
            force_source=force_source
        )

        gen_duration_ms = int((time.time() - gen_start) * 1000)

        if not results:
            logger.debug(f"No valid strategies generated from {generation_mode}")
            return (False, 0, generation_mode)

        # Record AI call if successful (only for AI-based)
        if not use_patterns and self.ai_tracker:
            self.ai_tracker.record_call()
            logger.debug(
                f"AI calls today: {self.ai_tracker.count}/{self.ai_tracker.max_calls}"
            )

        # Save all strategies
        saved_count = 0
        template_id = results[0].template_id or results[0].strategy_id[:8]
        base_code_hash = getattr(results[0], 'base_code_hash', None)

        for result in results:
            result_mode = getattr(result, 'generation_mode', None) or generation_mode

            if not result.validation_passed:
                from src.database.event_tracker import EventTracker
                EventTracker.generation_failed(
                    strategy_type=strategy_type,
                    timeframe=result.timeframe,
                    generation_mode=result_mode,
                    error='; '.join(result.validation_errors) if result.validation_errors else None
                )
                continue

            # Determine prefix based on generation mode
            # Pat = pattern, Ung = unger, Ugg = unger_genetic, AIF = ai_free, AIA = ai_assigned
            prefix_map = {
                'pattern': 'PatStrat',
                'pattern_gen': 'PGnStrat',
                'unger': 'UngStrat',
                'unger_genetic': 'UggStrat',
                'ai_free': 'AIFStrat',
                'ai_assigned': 'AIAStrat',
            }
            prefix = prefix_map.get(result_mode, 'Strategy')
            actual_type = getattr(result, 'strategy_type', strategy_type)
            strategy_name = f"{prefix}_{actual_type}_{result.strategy_id}"

            self._save_to_database(
                name=strategy_name,
                strategy_type=actual_type,
                timeframe=result.timeframe,
                code=result.code,
                ai_provider=result.ai_provider,
                pattern_based=use_patterns,
                pattern_ids=result.patterns_used,
                template_id=result.template_id,
                parameters=result.parameters,
                trading_coins=getattr(result, 'trading_coins', None),
                base_code_hash=getattr(result, 'base_code_hash', base_code_hash),
                generation_mode=result_mode,
                duration_ms=gen_duration_ms,
                leverage=getattr(result, 'leverage', None)
            )
            saved_count += 1

        logger.info(
            f"[{generation_mode}] Saved {saved_count}/{len(results)} strategies "
            f"(hash: {base_code_hash[:8] if base_code_hash else 'N/A'})"
        )

        return (True, saved_count, generation_mode)

    def _detect_direction(self, code: str) -> str:
        """
        Detect trading direction from strategy code.

        Analyzes class attributes and Signal() calls to determine if strategy trades:
        - LONG: Only long positions
        - SHORT: Only short positions
        - BIDIR: Both directions

        Returns:
            Direction string: "LONG", "SHORT", or "BIDIR"
        """
        code_lower = code.lower()

        # Check for explicit BIDI/BIDIR class attribute first
        # Unger strategies use: direction = 'bidi' (class attribute)
        has_bidi = (
            "direction='bidi'" in code_lower or
            'direction="bidi"' in code_lower or
            "direction = 'bidi'" in code_lower or
            'direction = "bidi"' in code_lower
        )
        if has_bidi:
            return "BIDIR"

        # Check both Signal() calls and class attribute definitions
        # Pattern strategies use: direction = 'long' (class attribute)
        # AI strategies may use: direction='long' (in Signal call)
        has_long = (
            "direction='long'" in code_lower or
            'direction="long"' in code_lower or
            "direction = 'long'" in code_lower or
            'direction = "long"' in code_lower
        )
        has_short = (
            "direction='short'" in code_lower or
            'direction="short"' in code_lower or
            "direction = 'short'" in code_lower or
            'direction = "short"' in code_lower
        )

        if has_long and has_short:
            return "BIDIR"
        elif has_short:
            return "SHORT"
        else:
            return "LONG"  # Default to LONG if unclear

    def _save_to_database(
        self,
        name: str,
        strategy_type: str,
        timeframe: str,
        code: str,
        ai_provider: str,
        pattern_based: bool,
        pattern_ids: list,
        template_id: Optional[str] = None,
        parameters: Optional[dict] = None,
        trading_coins: Optional[list] = None,
        base_code_hash: Optional[str] = None,
        generation_mode: Optional[str] = None,
        duration_ms: Optional[int] = None,
        leverage: Optional[int] = None
    ) -> bool:
        """Save generated strategy to database. Returns True if saved, False if duplicate."""
        try:
            # Deduplication check: skip if hash already exists
            if base_code_hash:
                with get_session() as session:
                    exists = session.query(Strategy.id).filter(
                        Strategy.base_code_hash == base_code_hash
                    ).first()
                    if exists:
                        logger.debug(f"Duplicate strategy skipped: {name} (hash: {base_code_hash[:8]})")
                        return False

            # Convert empty strings to None for UUID fields
            if template_id == '' or template_id is None:
                template_id = None

            # Detect direction from code
            direction = self._detect_direction(code)

            with get_session() as session:
                strategy = Strategy(
                    name=name,
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    status="GENERATED",
                    code=code,
                    ai_provider=ai_provider,
                    pattern_based=pattern_based,
                    pattern_ids=pattern_ids,
                    template_id=template_id,
                    parameters=parameters,
                    trading_coins=trading_coins,
                    base_code_hash=base_code_hash,
                    generation_mode=generation_mode
                )
                session.add(strategy)
                session.flush()  # Get ID before commit

                # Emit generation event
                from src.database.event_tracker import EventTracker
                EventTracker.generation_created(
                    strategy_id=strategy.id,
                    strategy_name=name,
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    ai_provider=ai_provider,
                    pattern_based=pattern_based,
                    base_code_hash=base_code_hash,
                    generation_mode=generation_mode,
                    direction=direction,
                    duration_ms=duration_ms,
                    leverage=leverage,
                    pattern_ids=pattern_ids
                )

            logger.debug(f"Saved strategy {name} to database")
            return True
        except Exception as e:
            logger.error(f"Failed to save strategy {name} to database: {e}", exc_info=True)
            return False

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True

        for future in list(self.active_futures.keys()):
            future.cancel()

        if self.executor:
            self.executor.shutdown(wait=False)

        os._exit(0)

    def run(self):
        """Main entry point"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Generator process terminated")
