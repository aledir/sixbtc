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
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import random

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
from src.generator.strategy_builder import StrategyBuilder
from src.generator.pattern_fetcher import PatternFetcher
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
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

        # Backpressure configuration
        self.max_pending_queue = generation_config.get('max_pending_queue', 500)
        self.backpressure_check_interval = generation_config.get('backpressure_check_interval', 60)

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

        # Paths
        self.pending_dir = Path(self.config['directories']['strategies']) / 'pending'
        self.pending_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"ContinuousGeneratorProcess initialized: "
            f"{self.parallel_threads} threads, backpressure at {self.max_pending_queue} pending"
        )

    @property
    def strategy_builder(self) -> StrategyBuilder:
        """Lazy-init strategy builder"""
        if self._strategy_builder is None:
            self._strategy_builder = StrategyBuilder(self.config)
        return self._strategy_builder

    def _check_backpressure(self) -> Tuple[bool, int]:
        """
        Check if we should pause generation due to queue buildup.

        Returns:
            (should_pause, pending_count) tuple
        """
        try:
            with get_session() as session:
                pending_count = session.query(Strategy).filter(
                    Strategy.status.in_(["GENERATED", "VALIDATED"])
                ).count()

            if pending_count >= self.max_pending_queue:
                return (True, pending_count)
            return (False, pending_count)

        except Exception as e:
            logger.error(f"Failed to check backpressure: {e}")
            return (False, 0)

    def _fetch_unused_patterns(self) -> List:
        """
        Fetch all Tier 1 patterns that haven't been used yet.

        Returns:
            List of unused Pattern objects
        """
        try:
            all_patterns = self.pattern_fetcher.get_tier_1_patterns(limit=100)

            if not all_patterns:
                logger.debug("No patterns available from pattern-discovery")
                return []

            used_ids = self.strategy_processor.get_used_pattern_ids()
            unused = [p for p in all_patterns if p.id not in used_ids]

            logger.info(
                f"Found {len(unused)} unused patterns "
                f"(out of {len(all_patterns)} total Tier 1)"
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
        """Main continuous generation loop with backpressure"""
        logger.info("Starting continuous generation loop (backpressure-based)")

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Check backpressure before generating
            should_pause, pending_count = self._check_backpressure()

            if should_pause:
                logger.info(
                    f"Backpressure: {pending_count} strategies pending "
                    f"(max {self.max_pending_queue}), pausing generation"
                )
                await asyncio.sleep(self.backpressure_check_interval)
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
                            logger.warning(f"Generation failed for task {task_id}")
                    except Exception as e:
                        logger.error(f"Task {task_id} error: {e}")

            await asyncio.sleep(0.1)

        logger.info("Generation loop ended")

    def _generate_batch(self) -> Tuple[bool, int, str]:
        """
        Generate ALL strategy variations from one template.

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

            # Select random strategy type and timeframe
            strategy_types = ['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']
            timeframes = self.config.get('timeframes', ['15m', '30m', '1h', '4h', '1d'])

            strategy_type = random.choice(strategy_types)
            timeframe = random.choice(timeframes)

            # Smart pattern selection
            use_patterns, selected_patterns = self._should_use_patterns()

            # Generate ALL variations
            results = self.strategy_builder.generate_strategies(
                strategy_type=strategy_type,
                timeframe=timeframe,
                use_patterns=use_patterns,
                patterns=selected_patterns
            )

            if not results:
                logger.warning("No valid strategies generated")
                return (False, 0, "")

            # Save all strategies
            saved_count = 0
            template_id = results[0].template_id or results[0].strategy_id[:8]

            for result in results:
                if not result.validation_passed:
                    continue

                strategy_name = f"Strategy_{strategy_type}_{result.strategy_id}"
                file_path = self.pending_dir / f"{strategy_name}.py"

                with open(file_path, 'w') as f:
                    f.write(result.code)

                self._save_to_database(
                    name=strategy_name,
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    code=result.code,
                    ai_provider=result.ai_provider,
                    pattern_based=use_patterns,
                    pattern_ids=result.patterns_used,
                    template_id=result.template_id,
                    parameters=result.parameters
                )
                saved_count += 1

            logger.info(
                f"Saved {saved_count}/{len(results)} strategies "
                f"from template {template_id}"
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
        parameters: Optional[dict] = None
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
                    parameters=parameters
                )
                session.add(strategy)
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
