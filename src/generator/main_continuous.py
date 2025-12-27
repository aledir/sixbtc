"""
Continuous Generator Process

Generates trading strategies using AI in a continuous loop.
Uses ThreadPoolExecutor for parallel generation with daily limits.
"""

import asyncio
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from datetime import datetime, timedelta
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
    max_bytes=_config.get('logging', {}).get('max_bytes', 10485760),
    backup_count=_config.get('logging', {}).get('backup_count', 5),
    module_levels=_config.get('logging', {}).get('modules')
)

logger = get_logger(__name__)


class ContinuousGeneratorProcess:
    """
    Continuous strategy generation process.

    Features:
    - ThreadPoolExecutor for parallel AI calls
    - Daily generation limits
    - Automatic slot reservation
    - Graceful shutdown handling
    """

    def __init__(self):
        """Initialize the generator process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from generation section)
        generation_config = self.config.get('generation', {})
        self.parallel_threads = generation_config.get('parallel_threads', 1)
        self.daily_limit = generation_config.get('templates_per_day', 20)
        self.min_interval = generation_config.get('min_interval_seconds', 0)
        self._last_generation_time = datetime.min

        # ThreadPoolExecutor for parallel generation
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Generator"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}
        self.daily_count = 0
        self.daily_count_lock = threading.Lock()
        self.last_reset_date = datetime.now().date()

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
            f"{self.parallel_threads} threads, {self.daily_limit}/day limit"
        )

    @property
    def strategy_builder(self) -> StrategyBuilder:
        """Lazy-init strategy builder"""
        if self._strategy_builder is None:
            self._strategy_builder = StrategyBuilder(self.config)
        return self._strategy_builder

    def _fetch_unused_patterns(self) -> List:
        """
        Fetch all Tier 1 patterns that haven't been used yet.

        "Unused" means not yet used by the generator to create a strategy,
        regardless of when the pattern was discovered.

        Returns:
            List of unused Pattern objects
        """
        try:
            # Get all Tier 1 production patterns
            all_patterns = self.pattern_fetcher.get_tier_1_patterns(limit=100)

            if not all_patterns:
                logger.debug("No patterns available from pattern-discovery")
                return []

            # Filter out already-used patterns
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
        """
        Get patterns that haven't been used yet.

        Uses caching to avoid hitting pattern-discovery API too frequently.

        Returns:
            List of unused Pattern objects
        """
        now = datetime.now()
        cache_age = (now - self._last_cache_refresh).total_seconds()

        # Use cache if fresh and not empty
        if cache_age < self._cache_refresh_interval and self._unused_patterns_cache:
            return self._unused_patterns_cache

        # Refresh cache
        self._unused_patterns_cache = self._fetch_unused_patterns()
        self._last_cache_refresh = now

        return self._unused_patterns_cache

    def _should_use_patterns(self) -> Tuple[bool, List]:
        """
        Decide whether to use pattern-based or custom AI generation.

        Logic:
        1. Fetch unused patterns (not yet used by generator)
        2. If unused patterns exist -> pattern-based generation
        3. If all patterns used -> custom AI generation

        Returns:
            (use_patterns: bool, patterns: list) tuple
        """
        unused_patterns = self._get_unused_patterns()

        if unused_patterns:
            # Select 2-3 patterns for this strategy
            num_patterns = min(random.randint(2, 3), len(unused_patterns))
            selected = random.sample(unused_patterns, num_patterns)

            # Remove selected patterns from cache (mark as "will be used")
            selected_ids = {p.id for p in selected}
            self._unused_patterns_cache = [
                p for p in self._unused_patterns_cache
                if p.id not in selected_ids
            ]

            logger.info(
                f"Using {len(selected)} patterns for generation: "
                f"{[p.name for p in selected]}"
            )
            return (True, selected)
        else:
            logger.info("All patterns used, using custom AI generation")
            return (False, [])

    def _reset_daily_count_if_needed(self):
        """Reset daily counter at midnight"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            with self.daily_count_lock:
                self.daily_count = 0
                self.last_reset_date = today
                logger.info("Daily count reset to 0")

    def reserve_slot(self) -> bool:
        """
        Atomically reserve a generation slot.

        Returns:
            True if slot reserved, False if daily limit reached
        """
        with self.daily_count_lock:
            self._reset_daily_count_if_needed()
            if self.daily_count >= self.daily_limit:
                return False
            self.daily_count += 1
            return True

    def release_slot(self):
        """Release a slot if generation failed"""
        with self.daily_count_lock:
            self.daily_count = max(0, self.daily_count - 1)

    async def run_continuous(self):
        """Main continuous generation loop"""
        logger.info("Starting continuous generation loop")

        # Initial population: start N workers
        for i in range(self.parallel_threads):
            if self.shutdown_event.is_set():
                break

            if not self.reserve_slot():
                logger.info("Daily limit reached on startup")
                break

            future = self.executor.submit(self._generate_one, slot_reserved=True)
            self.active_futures[future] = f"gen_{i}"

        # Main loop: maintain N active workers
        while not self.shutdown_event.is_set() and not self.force_exit:
            # If no active tasks and limit reached, wait until midnight
            if not self.active_futures:
                if not self.reserve_slot():
                    await self._wait_until_midnight()
                    continue
                else:
                    self.release_slot()  # Was just a check

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
                        success, strategy_id = future.result()
                        if success:
                            logger.info(f"Generated strategy: {strategy_id}")
                        else:
                            logger.warning(f"Generation failed for task {task_id}")
                    except Exception as e:
                        logger.error(f"Task {task_id} error: {e}")

                    # Start new task to replace completed one
                    if not self.shutdown_event.is_set() and self.reserve_slot():
                        new_future = self.executor.submit(self._generate_one, slot_reserved=True)
                        self.active_futures[new_future] = f"gen_{len(self.active_futures)}"

            await asyncio.sleep(0.1)

        logger.info("Generation loop ended")

    def _generate_one(self, slot_reserved: bool = False) -> Tuple[bool, str]:
        """
        Generate a single strategy.

        Smart pattern selection:
        - If unused patterns exist -> use pattern-based generation
        - If all patterns used -> custom AI generation (no patterns)

        Args:
            slot_reserved: Whether a slot was reserved for this generation

        Returns:
            (success, strategy_id) tuple
        """
        try:
            # Throttling: ensure minimum interval between generations
            now = datetime.now()
            elapsed = (now - self._last_generation_time).total_seconds()
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                logger.debug(f"Throttling: waiting {wait_time:.1f}s before next generation")
                import time
                time.sleep(wait_time)
            self._last_generation_time = datetime.now()

            # Select random strategy type and timeframe
            # Available strategy types (not from config - these are code categories)
            strategy_types = ['MOM', 'REV', 'TRN', 'BRE', 'VOL', 'SCA']
            # Get timeframes from global config
            timeframes = self.config.get('timeframes', ['15m', '30m', '1h', '4h', '1d'])

            strategy_type = random.choice(strategy_types)
            timeframe = random.choice(timeframes)

            # Smart pattern selection: use patterns only if NEW ones available
            use_patterns, selected_patterns = self._should_use_patterns()

            # Generate strategy with or without patterns
            result = self.strategy_builder.generate_strategy(
                strategy_type=strategy_type,
                timeframe=timeframe,
                use_patterns=use_patterns,
                patterns=selected_patterns  # Pass selected patterns directly
            )

            if not result.validation_passed:
                logger.warning(
                    f"Generated strategy failed validation: {result.validation_errors}"
                )
                return (False, "")

            # Save to pending directory
            strategy_name = f"Strategy_{strategy_type}_{result.strategy_id}"
            file_path = self.pending_dir / f"{strategy_name}.py"

            with open(file_path, 'w') as f:
                f.write(result.code)

            # Save to database with GENERATED status
            self._save_to_database(
                name=strategy_name,
                strategy_type=strategy_type,
                timeframe=timeframe,
                code=result.code,
                ai_provider=result.ai_provider,
                pattern_based=use_patterns,
                pattern_ids=result.patterns_used
            )

            return (True, strategy_name)

        except Exception as e:
            logger.error(f"Generation error: {e}", exc_info=True)
            if slot_reserved:
                self.release_slot()
            return (False, str(e))

    def _save_to_database(
        self,
        name: str,
        strategy_type: str,
        timeframe: str,
        code: str,
        ai_provider: str,
        pattern_based: bool,
        pattern_ids: list
    ):
        """Save generated strategy to database"""
        try:
            with get_session() as session:
                strategy = Strategy(
                    name=name,
                    strategy_type=strategy_type,
                    timeframe=timeframe,
                    status="GENERATED",
                    code=code,
                    ai_provider=ai_provider,
                    pattern_based=pattern_based,
                    pattern_ids=pattern_ids
                )
                session.add(strategy)
            logger.debug(f"Saved strategy {name} to database")
        except Exception as e:
            logger.error(f"Failed to save strategy {name} to database: {e}", exc_info=True)

    async def _wait_until_midnight(self):
        """Wait until next day (midnight reset)"""
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (tomorrow - now).total_seconds()

        logger.info(f"Daily limit reached, waiting {wait_seconds/3600:.1f}h until midnight")

        # Wait in small chunks to allow shutdown
        while wait_seconds > 0 and not self.shutdown_event.is_set():
            sleep_time = min(60, wait_seconds)
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True

        # Cancel active futures
        for future in list(self.active_futures.keys()):
            future.cancel()

        # Shutdown executor without waiting
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
