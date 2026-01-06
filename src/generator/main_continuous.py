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

        # Pipeline backpressure configuration (new multi-level system)
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        backpressure_config = pipeline_config.get('backpressure', {})
        monitoring_config = pipeline_config.get('monitoring', {})

        self.generated_limit = queue_limits.get('generated', 100)
        self.check_interval = backpressure_config.get('check_interval', 10)
        self.base_cooldown = backpressure_config.get('base_cooldown', 30)
        self.max_cooldown = backpressure_config.get('max_cooldown', 120)
        self.cooldown_increment = backpressure_config.get('cooldown_increment', 2)
        self.log_interval = monitoring_config.get('log_interval', 30)
        self._last_log_time = datetime.min

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

        logger.info(
            f"ContinuousGeneratorProcess initialized: "
            f"{self.parallel_threads} threads, backpressure at {self.generated_limit} GENERATED"
        )

    @property
    def strategy_builder(self) -> StrategyBuilder:
        """Lazy-init strategy builder"""
        if self._strategy_builder is None:
            self._strategy_builder = StrategyBuilder(self.config)
        return self._strategy_builder

    def _check_backpressure(self) -> Tuple[bool, int, int]:
        """
        Check if we should pause generation due to GENERATED queue buildup.

        Only checks GENERATED queue - validator handles VALIDATED queue.
        Uses progressive cooldown based on how much over limit.

        Returns:
            (should_pause, generated_count, cooldown_seconds) tuple
        """
        try:
            generated_count = self.strategy_processor.count_available("GENERATED")

            if generated_count >= self.generated_limit:
                cooldown = self.strategy_processor.calculate_backpressure_cooldown(
                    generated_count,
                    self.generated_limit,
                    self.base_cooldown,
                    self.cooldown_increment,
                    self.max_cooldown
                )
                return (True, generated_count, cooldown)

            return (False, generated_count, 0)

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
            logger.info(
                f"Pipeline: GEN={depths.get('GENERATED', 0)}/{self.generated_limit} "
                f"VAL={depths.get('VALIDATED', 0)} ACT={depths.get('ACTIVE', 0)} "
                f"LIVE={depths.get('LIVE', 0)}"
            )
            self._last_log_time = now
        except Exception as e:
            logger.debug(f"Failed to log pipeline status: {e}")

    def _fetch_unused_patterns(self) -> List:
        """
        Fetch all Tier 1 patterns that haven't been used yet.

        Uses multi-target expansion to create virtual patterns for each
        Tier 1 target (e.g., one pattern with 3 targets -> 3 virtual patterns).

        Returns:
            List of unused Pattern objects (including virtual patterns)
        """
        try:
            # Get multi-target config
            multi_target_config = self.config.get('pattern_discovery', {}).get('multi_target', {})
            expand_enabled = multi_target_config.get('enabled', True)
            min_edge = multi_target_config.get('min_edge_for_expansion', 0.05)
            max_targets = multi_target_config.get('max_targets_per_pattern', 5)

            # Fetch patterns with multi-target expansion
            all_patterns = self.pattern_fetcher.get_tier_1_patterns_expanded(
                limit=100,
                expand_multi_target=expand_enabled,
                min_edge_for_expansion=min_edge,
                max_targets_per_pattern=max_targets
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
            selected = [random.choice(unused_patterns)]

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

    async def run_continuous(self):
        """Main continuous generation loop with multi-level backpressure"""
        logger.info("Starting continuous generation loop (multi-level backpressure)")

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Log pipeline status periodically
            self._log_pipeline_status()

            # Check backpressure with progressive cooldown
            should_pause, generated_count, cooldown = self._check_backpressure()

            if should_pause:
                logger.info(
                    f"Backpressure: {generated_count} GENERATED "
                    f"(limit {self.generated_limit}), cooling down {cooldown}s"
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
        Generate strategy variations from one template, respecting backpressure.

        Returns:
            (success, count, template_id) tuple
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

            # Select random strategy type and timeframe
            strategy_types = ['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']
            timeframes = self.config['timeframes']

            strategy_type = random.choice(strategy_types)
            timeframe = random.choice(timeframes)

            # Smart pattern selection
            use_patterns, selected_patterns = self._should_use_patterns()

            # Check AI daily limit (only for AI-based, not pattern-based)
            if not use_patterns and self.ai_tracker:
                if not self.ai_tracker.can_call():
                    wait_seconds = seconds_until_midnight()
                    logger.info(
                        f"AI daily limit reached ({self.ai_tracker.count}/{self.ai_tracker.max_calls}). "
                        f"Waiting {wait_seconds/3600:.1f}h until reset."
                    )
                    return (False, 0, "daily_limit")

            # Generate strategies with capacity limit
            results = self.strategy_builder.generate_strategies(
                strategy_type=strategy_type,
                timeframe=timeframe,
                use_patterns=use_patterns,
                patterns=selected_patterns,
                max_strategies=remaining_capacity
            )

            if not results:
                # This is normal when patterns are filtered out (e.g., insufficient coins)
                logger.debug("No valid strategies generated")
                return (False, 0, "")

            # Record AI call if successful (only for AI-based)
            if not use_patterns and self.ai_tracker:
                self.ai_tracker.record_call()
                logger.debug(
                    f"AI calls today: {self.ai_tracker.count}/{self.ai_tracker.max_calls}"
                )

            # Save all strategies
            saved_count = 0
            template_id = results[0].template_id or results[0].strategy_id[:8]
            # Get base_code_hash from first result (all should have same hash)
            base_code_hash = getattr(results[0], 'base_code_hash', None)

            for result in results:
                if not result.validation_passed:
                    continue

                # Use different prefix for pattern-based vs template-based strategies
                prefix = "PatStrat" if use_patterns else "Strategy"
                strategy_name = f"{prefix}_{strategy_type}_{result.strategy_id}"

                self._save_to_database(
                    name=strategy_name,
                    strategy_type=strategy_type,
                    timeframe=result.timeframe,  # Use result's TF (from pattern), not random
                    code=result.code,
                    ai_provider=result.ai_provider,
                    pattern_based=use_patterns,
                    pattern_ids=result.patterns_used,
                    template_id=result.template_id,
                    parameters=result.parameters,
                    pattern_coins=getattr(result, 'pattern_coins', None),
                    base_code_hash=getattr(result, 'base_code_hash', base_code_hash)
                )
                saved_count += 1

            logger.info(
                f"Saved {saved_count}/{len(results)} strategies "
                f"from template {template_id} (hash: {base_code_hash[:8] if base_code_hash else 'N/A'})"
            )

            return (True, saved_count, template_id)

        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            return (False, 0, str(e))

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
        pattern_coins: Optional[list] = None,
        base_code_hash: Optional[str] = None
    ):
        """Save generated strategy to database"""
        try:
            # Convert empty strings to None for UUID fields
            if template_id == '' or template_id is None:
                template_id = None

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
                    pattern_coins=pattern_coins,
                    base_code_hash=base_code_hash
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
                    base_code_hash=base_code_hash
                )

            logger.debug(f"Saved strategy {name} to database")
        except Exception as e:
            logger.error(f"Failed to save strategy {name} to database: {e}", exc_info=True)

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
