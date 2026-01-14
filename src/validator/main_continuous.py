"""
Continuous Validator Process

Validates generated strategies through 3-phase pipeline (pre-backtest):
1. Syntax validation
2. Lookahead AST detection
3. Execution validation

Strategies that pass are promoted to VALIDATED for backtesting.
Shuffle test is run post-backtest in backtester (only for high-scoring strategies).
"""

import asyncio
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Dict, Optional, Tuple

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
from src.validator.syntax_validator import SyntaxValidator
from src.validator.lookahead_detector import LookaheadDetector
from src.validator.execution_validator import ExecutionValidator
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()
setup_logging(
    log_file='logs/validator.log',
    log_level=_config.get_required('logging.level'),
)

logger = get_logger(__name__)


class ContinuousValidatorProcess:
    """
    Continuous strategy validation process.

    Claims GENERATED strategies and runs 3-phase validation:
    1. Syntax validation
    2. Lookahead AST detection
    3. Execution validation

    Strategies that pass all phases are promoted to VALIDATED.
    Strategies that fail are deleted.
    """

    def __init__(
        self,
        syntax_validator: Optional[SyntaxValidator] = None,
        lookahead_detector: Optional[LookaheadDetector] = None,
        execution_validator: Optional[ExecutionValidator] = None,
        processor: Optional[StrategyProcessor] = None
    ):
        """
        Initialize the validator process with dependency injection.

        Args:
            syntax_validator: SyntaxValidator instance (created if not provided)
            lookahead_detector: LookaheadDetector instance (created if not provided)
            execution_validator: ExecutionValidator instance (created if not provided)
            processor: StrategyProcessor instance (created if not provided)
        """
        self.config = load_config()
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration - NO defaults (Fast Fail principle)
        self.parallel_threads = self.config.get_required('validation.parallel_threads')

        # Pipeline backpressure configuration (downstream = VALIDATED queue)
        self.validated_limit = self.config.get_required('pipeline.queue_limits.validated')
        self.base_cooldown = self.config.get_required('pipeline.backpressure.base_cooldown')
        self.max_cooldown = self.config.get_required('pipeline.backpressure.max_cooldown')
        self.cooldown_increment = self.config.get_required('pipeline.backpressure.cooldown_increment')
        self.log_interval = self.config.get_required('pipeline.monitoring.log_interval')
        self._last_log_time = datetime.min

        # ThreadPoolExecutor for parallel validation
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Validator"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}

        # Validators - use injected or create new (Dependency Injection pattern)
        self.syntax_validator = syntax_validator or SyntaxValidator()
        self.lookahead_detector = lookahead_detector or LookaheadDetector()
        self.execution_validator = execution_validator or ExecutionValidator()

        # Strategy processor for claiming
        self.processor = processor or StrategyProcessor(process_id=f"validator-{os.getpid()}")

        logger.info(
            f"ContinuousValidatorProcess initialized: {self.parallel_threads} threads, "
            f"downstream limit {self.validated_limit} VALIDATED"
        )

    def _log_pipeline_status(self):
        """Log pipeline status periodically for monitoring"""
        now = datetime.now()
        if (now - self._last_log_time).total_seconds() < self.log_interval:
            return

        try:
            depths = self.processor.get_queue_depths()
            logger.info(
                f"Pipeline: GEN={depths.get('GENERATED', 0)} "
                f"VAL={depths.get('VALIDATED', 0)}/{self.validated_limit} "
                f"ACT={depths.get('ACTIVE', 0)} LIVE={depths.get('LIVE', 0)}"
            )
            self._last_log_time = now
        except Exception as e:
            logger.debug(f"Failed to log pipeline status: {e}")

    async def run_continuous(self):
        """Main continuous validation loop with downstream backpressure"""
        logger.info("Starting continuous validation loop (with downstream backpressure)")

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Log pipeline status periodically
            self._log_pipeline_status()

            # Process completed validations first (free up slots)
            done_futures = []
            for f in list(self.active_futures.keys()):
                if f.done():
                    done_futures.append(f)

            for future in done_futures:
                strategy_id = self.active_futures.pop(future)
                try:
                    success, reason = future.result()
                    if success:
                        logger.info(f"Strategy {strategy_id} VALIDATED")
                    else:
                        logger.info(f"Strategy {strategy_id} FAILED: {reason}")
                except Exception as e:
                    logger.error(f"Validation error for {strategy_id}: {e}")

            # Check downstream backpressure (VALIDATED queue)
            validated_count = self.processor.count_available("VALIDATED")
            if validated_count >= self.validated_limit:
                cooldown = self.processor.calculate_backpressure_cooldown(
                    validated_count,
                    self.validated_limit,
                    self.base_cooldown,
                    self.cooldown_increment,
                    self.max_cooldown
                )
                logger.info(
                    f"Downstream backpressure: {validated_count} VALIDATED "
                    f"(limit {self.validated_limit}), waiting {cooldown}s"
                )
                await asyncio.sleep(cooldown)
                continue

            # Only claim new strategies if we have free worker slots
            # This prevents claiming more strategies than we can process
            if len(self.active_futures) >= self.parallel_threads:
                # All workers busy, wait before checking again
                await asyncio.sleep(1)
                continue

            # Claim a strategy for validation
            strategy = self.processor.claim_strategy("GENERATED")

            if strategy is None:
                # No strategies to validate, wait and retry
                await asyncio.sleep(5)
                continue

            # Submit validation task
            future = self.executor.submit(
                self._validate_strategy,
                strategy.id,
                strategy.name,
                strategy.code,
                strategy.base_code_hash
            )
            self.active_futures[future] = str(strategy.id)

            await asyncio.sleep(0.1)

        logger.info("Validation loop ended")

    def _validate_strategy(
        self,
        strategy_id,
        strategy_name: str,
        code: str,
        base_code_hash: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Run 3-phase pre-backtest validation on a strategy.

        Phases:
        1. Syntax validation (AST parse, inheritance, methods)
        2. Lookahead AST detection (forbidden patterns)
        3. Execution validation (runtime test)

        Note: Shuffle test moved to backtester (post-scoring, only for high scores).

        Args:
            strategy_id: Strategy UUID
            strategy_name: Strategy name for logging
            code: Strategy code to validate
            base_code_hash: Hash of base code (unused, kept for API compatibility)

        Returns:
            (passed, reason) tuple
        """
        import time
        from src.database.event_tracker import EventTracker

        total_start = time.time()

        try:
            # Phase 1: Syntax validation
            logger.debug(f"[{strategy_name}] Phase 1: Syntax validation")
            phase_start = time.time()
            syntax_result = self.syntax_validator.validate(code)
            phase_ms = int((time.time() - phase_start) * 1000)

            if not syntax_result.passed:
                EventTracker.validation_failed(
                    strategy_id, strategy_name, "syntax",
                    reason=str(syntax_result.errors),
                    duration_ms=phase_ms,
                    errors=syntax_result.errors
                )
                self._delete_strategy(strategy_id, f"Syntax: {syntax_result.errors}")
                return (False, f"Syntax: {syntax_result.errors}")

            EventTracker.validation_passed(
                strategy_id, strategy_name, "syntax",
                duration_ms=phase_ms,
                class_name=syntax_result.class_name
            )
            class_name = syntax_result.class_name

            # Phase 2: Lookahead detection (AST-based)
            logger.debug(f"[{strategy_name}] Phase 2: Lookahead detection")
            phase_start = time.time()
            lookahead_result = self.lookahead_detector.validate(code)
            phase_ms = int((time.time() - phase_start) * 1000)

            if not lookahead_result.passed:
                EventTracker.validation_failed(
                    strategy_id, strategy_name, "lookahead",
                    reason=str(lookahead_result.violations),
                    duration_ms=phase_ms,
                    violations=lookahead_result.violations
                )
                self._delete_strategy(strategy_id, f"Lookahead: {lookahead_result.violations}")
                return (False, f"Lookahead: {lookahead_result.violations}")

            EventTracker.validation_passed(
                strategy_id, strategy_name, "lookahead",
                duration_ms=phase_ms
            )

            # Phase 3: Execution validation
            logger.debug(f"[{strategy_name}] Phase 3: Execution validation")
            phase_start = time.time()
            exec_result = self.execution_validator.validate(code, class_name, None)
            phase_ms = int((time.time() - phase_start) * 1000)

            if not exec_result.passed:
                EventTracker.validation_failed(
                    strategy_id, strategy_name, "execution",
                    reason=str(exec_result.errors),
                    duration_ms=phase_ms,
                    errors=exec_result.errors
                )
                self._delete_strategy(strategy_id, f"Execution: {exec_result.errors}")
                return (False, f"Execution: {exec_result.errors}")

            EventTracker.validation_passed(
                strategy_id, strategy_name, "execution",
                duration_ms=phase_ms
            )

            # All 3 phases passed - promote to VALIDATED
            # Note: Shuffle test will run in backtester after scoring
            total_ms = int((time.time() - total_start) * 1000)
            EventTracker.validation_completed(strategy_id, strategy_name, total_ms)

            self.processor.release_strategy(strategy_id, "VALIDATED")
            logger.debug(f"[{strategy_name}] Passed pre-backtest validation (3 phases)")
            return (True, "All phases passed")

        except Exception as e:
            logger.error(f"Validation error for {strategy_name}: {e}", exc_info=True)
            EventTracker.validation_failed(
                strategy_id, strategy_name, "unknown",
                reason=str(e)
            )
            self.processor.mark_failed(strategy_id, str(e), delete=True)
            return (False, str(e))

    def _delete_strategy(self, strategy_id, reason: str):
        """Delete failed strategy"""
        self.processor.mark_failed(strategy_id, reason, delete=True)

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True

        # Release any claimed strategies
        self.processor.release_all_by_process()

        # Cancel active futures
        for future in list(self.active_futures.keys()):
            future.cancel()

        # Shutdown executor
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
            logger.info("Validator process terminated")
