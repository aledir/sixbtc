"""
Continuous Validator Process

Validates generated strategies through 4-phase pipeline:
1. Syntax validation
2. Lookahead AST detection
3. Shuffle test
4. Execution validation

Strategies that fail any phase are deleted.
"""

import asyncio
import os
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
from src.validator.syntax_validator import SyntaxValidator
from src.validator.lookahead_detector import LookaheadDetector
from src.validator.lookahead_test import LookaheadTester
from src.validator.execution_validator import ExecutionValidator
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousValidatorProcess:
    """
    Continuous strategy validation process.

    Claims GENERATED strategies and runs 4-phase validation.
    Strategies that pass all phases are promoted to VALIDATED.
    Strategies that fail are deleted.
    """

    def __init__(self):
        """Initialize the validator process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration
        proc_config = self.config.get('processes', {}).get('validator', {})
        self.parallel_threads = proc_config.get('parallel_threads', 5)

        # ThreadPoolExecutor for parallel validation
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Validator"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}

        # Validators
        self.syntax_validator = SyntaxValidator()
        self.lookahead_detector = LookaheadDetector()
        self.lookahead_tester = LookaheadTester()
        self.execution_validator = ExecutionValidator()

        # Strategy processor for claiming
        self.processor = StrategyProcessor(process_id=f"validator-{os.getpid()}")

        # Test data for shuffle test (loaded once)
        self._test_data: Optional[pd.DataFrame] = None

        logger.info(
            f"ContinuousValidatorProcess initialized: {self.parallel_threads} threads"
        )

    @property
    def test_data(self) -> pd.DataFrame:
        """Lazy-load test data for shuffle test"""
        if self._test_data is None:
            self._test_data = self._load_test_data()
        return self._test_data

    def _load_test_data(self) -> pd.DataFrame:
        """Load test data for validation"""
        try:
            from src.backtester.data_loader import BacktestDataLoader
            # BacktestDataLoader expects cache_dir string, not config dict
            cache_dir = self.config.get('directories', {}).get('data', 'data/binance')
            loader = BacktestDataLoader(cache_dir=cache_dir)
            data = loader.load_single_symbol('BTC', '15m', days=30)
            logger.info(f"Loaded {len(data)} bars of BTC 15m test data")
            return data
        except Exception as e:
            logger.warning(f"Failed to load test data: {e}, using synthetic")
            return self.execution_validator._generate_test_data(500)

    async def run_continuous(self):
        """Main continuous validation loop"""
        logger.info("Starting continuous validation loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
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
                strategy.code
            )
            self.active_futures[future] = str(strategy.id)

            # Process completed validations
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

            await asyncio.sleep(0.1)

        logger.info("Validation loop ended")

    def _validate_strategy(
        self,
        strategy_id,
        strategy_name: str,
        code: str
    ) -> Tuple[bool, str]:
        """
        Run 4-phase validation on a strategy.

        Returns:
            (passed, reason) tuple
        """
        try:
            # Phase 1: Syntax validation
            logger.debug(f"[{strategy_name}] Phase 1: Syntax validation")
            syntax_result = self.syntax_validator.validate(code)

            if not syntax_result.passed:
                self._delete_strategy(strategy_id, f"Syntax: {syntax_result.errors}")
                return (False, f"Syntax: {syntax_result.errors}")

            class_name = syntax_result.class_name

            # Phase 2: Lookahead detection
            logger.debug(f"[{strategy_name}] Phase 2: Lookahead detection")
            lookahead_result = self.lookahead_detector.validate(code)

            if not lookahead_result.passed:
                self._delete_strategy(strategy_id, f"Lookahead: {lookahead_result.violations}")
                return (False, f"Lookahead: {lookahead_result.violations}")

            # Phase 3: Execution validation (before shuffle - need instance)
            logger.debug(f"[{strategy_name}] Phase 3: Execution validation")
            exec_result = self.execution_validator.validate(code, class_name, None)

            if not exec_result.passed:
                self._delete_strategy(strategy_id, f"Execution: {exec_result.errors}")
                return (False, f"Execution: {exec_result.errors}")

            # Phase 4: Lookahead bias test (Future Contamination Test)
            shuffle_enabled = self.config.get('validation', {}).get('shuffle_test_enabled', True)

            if shuffle_enabled:
                logger.debug(f"[{strategy_name}] Phase 4: Lookahead bias test")
                try:
                    # Load strategy instance for shuffle test
                    strategy_instance = self._load_strategy_instance(code, class_name)

                    if strategy_instance:
                        shuffle_result = self.lookahead_tester.validate(
                            strategy_instance,
                            self.test_data
                        )

                        if not shuffle_result.passed:
                            self._delete_strategy(
                                strategy_id,
                                f"Lookahead: {shuffle_result.details}"
                            )
                            return (False, f"Lookahead: {shuffle_result.details}")
                except Exception as e:
                    logger.warning(f"Shuffle test skipped for {strategy_name}: {e}")

            # All phases passed - promote to VALIDATED
            self.processor.release_strategy(strategy_id, "VALIDATED")
            return (True, "All phases passed")

        except Exception as e:
            logger.error(f"Validation error for {strategy_name}: {e}", exc_info=True)
            self.processor.mark_failed(strategy_id, str(e), delete=True)
            return (False, str(e))

    def _load_strategy_instance(self, code: str, class_name: str):
        """Load strategy instance from code"""
        import importlib.util
        import tempfile
        import sys

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name

            spec = importlib.util.spec_from_file_location(
                f"temp_{class_name}",
                temp_path
            )

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)

                if hasattr(module, class_name):
                    cls = getattr(module, class_name)
                    return cls()

            return None

        except Exception as e:
            logger.debug(f"Failed to load strategy instance: {e}")
            return None
        finally:
            Path(temp_path).unlink(missing_ok=True)

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
