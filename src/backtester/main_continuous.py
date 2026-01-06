"""
Continuous Backtester Process

Backtests validated strategies with portfolio simulation.
- Multi-pair backtesting (top 30 coins by volume)
- Timeframe optimization (test all TFs, select optimal)
- Training/Holdout split for anti-overfitting
- Uses ThreadPoolExecutor for parallel backtesting
"""

import asyncio
import os
import signal
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
import importlib.util
import tempfile
import sys

# Suppress pandas FutureWarning about fillna downcasting (from AI-generated strategies)
warnings.filterwarnings('ignore', category=FutureWarning, message='.*Downcasting.*fillna.*')

from src.config import load_config
from src.database import get_session, Strategy, BacktestResult, StrategyProcessor
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.backtester.parametric_backtest import ParametricBacktester
from src.data.coin_registry import get_registry, get_active_pairs
from src.scorer import BacktestScorer, PoolManager
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()
setup_logging(
    log_file='logs/backtester.log',
    log_level=_config.get_required('logging.level'),
)

logger = get_logger(__name__)


class ContinuousBacktesterProcess:
    """
    Continuous backtesting process.

    Claims VALIDATED strategies and runs multi-pair backtests.
    Tests all timeframes and selects optimal TF.
    Strategies that pass thresholds are promoted to TESTED.
    """

    def __init__(
        self,
        engine: Optional[BacktestEngine] = None,
        data_loader: Optional[BacktestDataLoader] = None,
        processor: Optional[StrategyProcessor] = None,
        parametric_backtester: Optional[ParametricBacktester] = None
    ):
        """
        Initialize the backtester process with dependency injection.

        Args:
            engine: BacktestEngine instance (created if not provided)
            data_loader: BacktestDataLoader instance (created if not provided)
            processor: StrategyProcessor instance (created if not provided)
            parametric_backtester: ParametricBacktester instance (created if enabled and not provided)
        """
        self.config = load_config()
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration - Thread allocation (4+1 elastic model)
        # Try new config structure first, fallback to legacy
        if self.config.get('backtesting.threads.validated'):
            self.validated_threads = self.config.get_required('backtesting.threads.validated')
            self.retest_threads = self.config.get_required('backtesting.threads.retest')
            self.parallel_threads = self.validated_threads + self.retest_threads
        else:
            # Legacy config: all threads for VALIDATED
            self.parallel_threads = self.config.get_required('backtesting.parallel_threads')
            self.validated_threads = self.parallel_threads
            self.retest_threads = 0

        # Re-backtest configuration
        self.retest_interval_days = self.config.get('backtesting.retest.interval_days', 3)

        # ACTIVE pool configuration
        self.pool_max_size = self.config.get('active_pool.max_size', 300)
        self.pool_min_score = self.config.get('active_pool.min_score', 40)

        # Pipeline backpressure configuration (downstream = ACTIVE pool)
        self.active_limit = self.pool_max_size  # Use pool size as limit
        self.base_cooldown = self.config.get_required('pipeline.backpressure.base_cooldown')
        self.max_cooldown = self.config.get_required('pipeline.backpressure.max_cooldown')
        self.cooldown_increment = self.config.get_required('pipeline.backpressure.cooldown_increment')
        self.log_interval = self.config.get_required('pipeline.monitoring.log_interval')
        self._last_log_time = datetime.min

        # ThreadPoolExecutor for parallel backtesting
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Backtester"
        )

        # Components - use injected or create new (Dependency Injection pattern)
        self.engine = engine or BacktestEngine(self.config._raw_config)
        cache_dir = self.config.get_required('directories.data') + '/binance'
        self.data_loader = data_loader or BacktestDataLoader(cache_dir)
        self.processor = processor or StrategyProcessor(process_id=f"backtester-{os.getpid()}")

        # Parametric backtester - use injected or create new (Dependency Injection)
        self.parametric_enabled = self.config.get_required('generation.parametric.enabled')
        if self.parametric_enabled:
            self.parametric_backtester = parametric_backtester or ParametricBacktester(self.config._raw_config)
            # Override parameter space from config if provided (only if we created it)
            if parametric_backtester is None:
                param_space = self.config.get('generation.parametric.parameter_space', {})
                if param_space:
                    self.parametric_backtester.set_parameter_space(param_space)
            logger.info(
                f"Parametric backtesting ENABLED: "
                f"{self.parametric_backtester._count_strategies()} candidate strategies, "
                f"all passing threshold saved"
            )
        else:
            self.parametric_backtester = None

        # Backtest thresholds - NO defaults
        self.min_sharpe = self.config.get_required('backtesting.thresholds.min_sharpe')
        self.min_win_rate = self.config.get_required('backtesting.thresholds.min_win_rate')
        self.max_drawdown = self.config.get_required('backtesting.thresholds.max_drawdown')
        self.min_trades = self.config.get_required('backtesting.thresholds.min_total_trades')
        self.min_expectancy = self.config.get_required('backtesting.thresholds.min_expectancy')

        # Timeframes (top-level in config) - NO defaults
        self.timeframes = self.config.get_required('timeframes')

        # Pairs count (from backtesting section)
        self.max_coins = self.config.get_required('backtesting.max_coins')

        # Training/Holdout configuration
        self.training_days = self.config.get_required('backtesting.training_days')
        self.holdout_days = self.config.get_required('backtesting.holdout_days')
        self.min_coverage_pct = self.config.get_required('backtesting.min_coverage_pct')

        # Holdout validation thresholds
        self.holdout_max_degradation = self.config.get_required('backtesting.holdout.max_degradation')
        self.holdout_min_sharpe = self.config.get_required('backtesting.holdout.min_sharpe')
        self.holdout_recency_weight = self.config.get_required('backtesting.holdout.recency_weight')
        self.min_holdout_trades = self.config.get_required('backtesting.holdout.min_trades')

        # Initial capital for expectancy normalization
        self.initial_capital = self.config.get_required('backtesting.initial_capital')

        # SCORER and PoolManager for post-backtest scoring and pool management
        self.scorer = BacktestScorer(self.config._raw_config)
        self.pool_manager = PoolManager(self.config._raw_config)

        # Preloaded data cache: {(symbols_hash, timeframe): data}
        self._data_cache: Dict[str, Dict[str, any]] = {}

        # CoinRegistry handles caching and invalidation
        # No need for local pairs cache anymore

        logger.info(
            f"ContinuousBacktesterProcess initialized: "
            f"{self.validated_threads} VALIDATED threads + {self.retest_threads} elastic thread, "
            f"{len(self.timeframes)} TFs, {self.max_coins} coins, "
            f"retest every {self.retest_interval_days}d, pool max {self.pool_max_size}"
        )

    def _scroll_down_coverage(
        self,
        coins: List[str],
        timeframe: str,
        target_count: int = None,
        min_count: int = 5
    ) -> Tuple[Optional[List[str]], str]:
        """
        UNIFIED scroll-down logic for both Pattern and AI strategies.

        Iterates through coins (ordered by edge OR volume) and selects
        first N coins with sufficient data coverage.

        Args:
            coins: List of coins to check (already filtered for liquidity + cache)
            timeframe: Timeframe to validate
            target_count: Target number of pairs (default: self.max_coins = 30)
            min_count: Minimum acceptable pairs (default: 5)

        Returns:
            (validated_coins, status) - validated_coins is None if rejected
        """
        if target_count is None:
            target_count = self.max_coins  # 30

        # Get cache reader
        from src.backtester.cache_reader import BacktestCacheReader
        cache_reader = BacktestCacheReader(self.data_loader.cache_dir)

        # Check coverage for ALL coins (scroll-down logic)
        total_days = self.training_days + self.holdout_days
        min_days_required = total_days * self.min_coverage_pct

        validated_coins = []
        for coin in coins:  # Iterate ALL coins (no early break)
            info = cache_reader.get_cache_info(coin, timeframe)
            if info and info.get('days', 0) >= min_days_required:
                validated_coins.append(coin)

        # Check minimum threshold
        if len(validated_coins) < min_count:
            return None, f"insufficient_coverage:{len(validated_coins)}/{min_count}"

        # Limit to target_count (but accept less if that's all we have)
        final_coins = validated_coins[:target_count]

        return final_coins, "validated"

    def _get_backtest_pairs(self, timeframe: str) -> Tuple[Optional[List[str]], str]:
        """
        Load pairs for AI-based backtesting with UNIFIED scroll-down logic.

        Gets extended list (2x target), filters for liquidity + cache,
        then uses unified scroll-down to find 30 with sufficient coverage.

        Returns:
            (validated_pairs, status) - pairs is None if rejected
        """
        target_count = self.max_coins  # 30
        extended_limit = target_count * 2  # 60 pairs buffer

        # Get volume-sorted pairs from CoinRegistry
        pairs = get_active_pairs(limit=extended_limit)

        if not pairs:
            logger.warning("No pairs in CoinRegistry, using default pairs")
            pairs = ['BTC', 'ETH', 'SOL', 'ARB', 'AVAX']

        # Filter for cache existence
        from src.backtester.cache_reader import BacktestCacheReader, CacheNotFoundError
        try:
            cache_reader = BacktestCacheReader(self.data_loader.cache_dir)
            cached_symbols = set(cache_reader.list_cached_symbols(timeframe))
        except CacheNotFoundError:
            return None, "cache_not_found"

        cached_pairs = [p for p in pairs if p in cached_symbols]

        if not cached_pairs:
            return None, "no_cached_pairs"

        # UNIFIED scroll-down logic (same as Pattern strategies)
        validated_pairs, status = self._scroll_down_coverage(
            coins=cached_pairs,
            timeframe=timeframe,
            target_count=target_count,
            min_count=5
        )

        if validated_pairs:
            logger.info(
                f"AI pair selection: {len(validated_pairs)} pairs validated "
                f"(from {len(pairs)} volume-sorted, target: {target_count})"
            )

        return validated_pairs, status

    def _validate_pattern_coins(
        self,
        pattern_coins: List[str],
        timeframe: str
    ) -> Tuple[Optional[List[str]], str]:
        """
        Validate pattern coins for backtest/live consistency.

        Three-level validation (all required):
        1. Liquidity: coin must be in active trading pairs (volume >= threshold)
        2. Cache: coin must have cached OHLCV data
        3. Coverage: coin must have >= 90% data coverage for training+holdout period

        NO FALLBACK: If insufficient coins pass validation, returns None.
        This ensures backtest coins = live coins = pattern edge preserved.

        Args:
            pattern_coins: List of coins from pattern's coin_performance (ordered by edge)
            timeframe: Timeframe to validate data coverage for

        Returns:
            (validated_coins, rejection_reason) - validated_coins is None if rejected
        """
        if not pattern_coins:
            return None, "no_pattern_coins"

        min_coins = self.config.get('pattern_discovery', {}).get(
            'coin_selection', {}
        ).get('min_tradable_coins', 1)  # Trust Pattern Discovery Tier 1 validation

        # Level 1: Liquidity filter (active trading pairs from CoinRegistry)
        active_coins = set(get_active_pairs())
        liquid_coins = [c for c in pattern_coins if c in active_coins]

        if len(liquid_coins) < min_coins:
            logger.warning(
                f"Liquidity filter: {len(liquid_coins)}/{len(pattern_coins)} coins liquid "
                f"(need {min_coins})"
            )
            return None, f"insufficient_liquidity:{len(liquid_coins)}/{min_coins}"

        # Level 2: Cache filter (data must exist in cache)
        from src.backtester.cache_reader import BacktestCacheReader, CacheNotFoundError
        try:
            cache_reader = BacktestCacheReader(self.data_loader.cache_dir)
            cached_symbols = set(cache_reader.list_cached_symbols(timeframe))
        except CacheNotFoundError:
            return None, "cache_not_found"

        cached_coins = [c for c in liquid_coins if c in cached_symbols]

        if len(cached_coins) < min_coins:
            logger.warning(
                f"Cache filter: {len(cached_coins)}/{len(liquid_coins)} coins cached "
                f"(need {min_coins})"
            )
            return None, f"insufficient_cache:{len(cached_coins)}/{min_coins}"

        # Level 3: Coverage filter using UNIFIED scroll-down logic
        target_count = self.max_coins  # 30 pairs target
        # Accept if at least 80% of cached coins have coverage (min 1)
        min_count = max(1, int(len(cached_coins) * 0.8))

        validated_coins, status = self._scroll_down_coverage(
            coins=cached_coins,
            timeframe=timeframe,
            target_count=target_count,
            min_count=min_count
        )

        if not validated_coins:
            logger.warning(
                f"Coverage filter: {status} for pattern coins "
                f"(from {len(cached_coins)} cached, need {min_count})"
            )
            return None, status

        logger.info(
            f"Validated {len(validated_coins)} pattern coins "
            f"(from {len(pattern_coins)} edge-sorted, target: {target_count})"
        )

        return validated_coins, "validated"

    def _get_training_holdout_data(
        self,
        pairs: List[str],
        timeframe: str
    ) -> Tuple[Dict[str, any], Dict[str, any]]:
        """
        Get training/holdout data for multi-symbol backtesting

        Data is split into NON-OVERLAPPING periods:
        - Training: older data for backtest metrics (365 days)
        - Holdout: recent data for validation (30 days) - NEVER seen during training

        Args:
            pairs: List of symbol names
            timeframe: Timeframe to load

        Returns:
            Tuple of (training_data_dict, holdout_data_dict)
        """
        # Cache key includes pairs hash - different strategies have different pairs
        pairs_hash = hash(tuple(sorted(pairs)))
        training_cache_key = f"{timeframe}_{pairs_hash}_training"
        holdout_cache_key = f"{timeframe}_{pairs_hash}_holdout"

        # Check if both are cached
        if training_cache_key in self._data_cache and holdout_cache_key in self._data_cache:
            return (
                self._data_cache[training_cache_key],
                self._data_cache[holdout_cache_key]
            )

        try:
            training_data, holdout_data = self.data_loader.load_multi_symbol_training_holdout(
                symbols=pairs,
                timeframe=timeframe,
                training_days=self.training_days,
                holdout_days=self.holdout_days,
                target_count=self.max_coins  # Scroll through pairs to find 30 with valid data
            )

            self._data_cache[training_cache_key] = training_data
            self._data_cache[holdout_cache_key] = holdout_data

            logger.info(
                f"Loaded training/holdout data for {timeframe}: "
                f"{len(training_data)} symbols ({self.training_days}d training, {self.holdout_days}d holdout)"
            )

            return training_data, holdout_data

        except Exception as e:
            logger.error(f"Failed to load training/holdout data for {timeframe}: {e}")
            return {}, {}

    def _log_pipeline_status(self):
        """Log pipeline status periodically for monitoring"""
        now = datetime.now()
        if (now - self._last_log_time).total_seconds() < self.log_interval:
            return

        try:
            depths = self.processor.get_queue_depths()
            logger.info(
                f"Pipeline: GEN={depths.get('GENERATED', 0)} "
                f"VAL={depths.get('VALIDATED', 0)} "
                f"ACTIVE={depths.get('ACTIVE', 0)}/{self.active_limit} "
                f"LIVE={depths.get('LIVE', 0)}"
            )
            self._last_log_time = now
        except Exception as e:
            logger.debug(f"Failed to log pipeline status: {e}")

    async def run_continuous(self):
        """
        Main continuous backtesting loop with 4+1 elastic thread model.

        Thread allocation:
        - 4 threads: dedicated to VALIDATED strategies (new backtests)
        - 1 elastic thread: prioritizes re-backtest of ACTIVE strategies,
          helps VALIDATED when no re-backtest needed

        Downstream backpressure: monitors ACTIVE pool size.
        """
        logger.info(
            f"Starting continuous backtesting loop "
            f"({self.validated_threads} VALIDATED + {self.retest_threads} elastic threads)"
        )

        # Track futures by type
        validated_futures: Dict[Future, Tuple[str, str]] = {}  # Future -> (strategy_id, name)
        retest_futures: Dict[Future, Tuple[str, str]] = {}

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Log pipeline status periodically
            self._log_pipeline_status()

            # Process completed backtests (both types)
            for futures_dict, future_type in [
                (validated_futures, "VALIDATED"),
                (retest_futures, "RETEST")
            ]:
                done_futures = [f for f in futures_dict if f.done()]
                for future in done_futures:
                    strategy_id, strategy_name = futures_dict.pop(future)
                    try:
                        success, reason = future.result()
                        if success:
                            logger.info(f"[{future_type}] {strategy_name} completed: {reason}")
                        else:
                            logger.info(f"[{future_type}] {strategy_name} failed: {reason}")
                    except Exception as e:
                        logger.error(f"[{future_type}] Backtest error for {strategy_name}: {e}")

            # Check downstream backpressure (ACTIVE pool)
            active_count = self.processor.count_available("ACTIVE")
            if active_count >= self.active_limit:
                cooldown = self.processor.calculate_backpressure_cooldown(
                    active_count,
                    self.active_limit,
                    self.base_cooldown,
                    self.cooldown_increment,
                    self.max_cooldown
                )
                logger.info(
                    f"Downstream backpressure: {active_count} ACTIVE "
                    f"(pool max {self.active_limit}), waiting {cooldown}s"
                )
                await asyncio.sleep(cooldown)
                continue

            total_futures = len(validated_futures) + len(retest_futures)

            # All workers busy
            if total_futures >= self.parallel_threads:
                await asyncio.sleep(1)
                continue

            # ELASTIC THREAD LOGIC:
            # 1. Always prioritize re-backtest if slot available and strategy needs it
            # 2. Otherwise, all slots process VALIDATED

            # Check for re-backtest opportunity (elastic behavior)
            if len(retest_futures) == 0 and self.retest_threads > 0:
                # No re-backtest running, check if any ACTIVE strategy needs re-test
                strategy_data = self._get_strategy_needing_retest()
                if strategy_data:
                    # Submit re-backtest task
                    future = self.executor.submit(
                        self._retest_strategy,
                        strategy_data['id'],
                        strategy_data['name'],
                        strategy_data['code'],
                        strategy_data['optimal_timeframe'],
                        strategy_data['backtest_pairs']
                    )
                    retest_futures[future] = (str(strategy_data['id']), strategy_data['name'])
                    logger.info(f"[RETEST] Started re-backtest for {strategy_data['name']}")
                    await asyncio.sleep(0.1)
                    continue

            # Process VALIDATED strategies
            # Elastic: if no re-backtest needed, elastic slot helps VALIDATED
            max_validated = self.validated_threads
            if len(retest_futures) == 0 and self.retest_threads > 0:
                max_validated = self.parallel_threads  # Elastic slot available for VALIDATED

            if len(validated_futures) < max_validated:
                strategy = self.processor.claim_strategy("VALIDATED")
                if strategy:
                    future = self.executor.submit(
                        self._backtest_strategy_all_tf,
                        strategy.id,
                        strategy.name,
                        strategy.code,
                        strategy.timeframe,
                        strategy.pattern_coins,
                        strategy.base_code_hash  # Pass hash to detect pre-parametrized strategies
                    )
                    validated_futures[future] = (str(strategy.id), strategy.name)
                    await asyncio.sleep(0.1)
                    continue

            # Nothing to do, wait
            await asyncio.sleep(5)

        logger.info("Backtesting loop ended")

    def _backtest_strategy_all_tf(
        self,
        strategy_id,
        strategy_name: str,
        code: str,
        original_tf: str,
        pattern_coins: Optional[List[str]] = None,
        base_code_hash: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Run training/holdout backtest on strategy.

        If base_code_hash is present, the strategy was pre-parametrized by the Generator.
        In this case, we skip parametric optimization and test only the assigned timeframe.

        Training/Holdout backtesting (unified approach):
        1. Backtest on TRAINING period (365 days) - for edge detection
        2. Backtest on HOLDOUT period (30 days) - NEVER seen during training
        3. Holdout serves TWO purposes:
           a) Anti-overfitting: if holdout crashes, strategy is overfitted
           b) Recency score: good holdout = strategy "in form" now
        4. Final score weighted: training metrics + holdout performance

        Returns:
            (passed, reason) tuple
        """
        try:
            # Load strategy instance
            class_name = self._extract_class_name(code)
            if not class_name:
                self._delete_strategy(strategy_id, "Could not extract class name")
                return (False, "Could not extract class name")

            strategy_instance = self._load_strategy_instance(code, class_name)
            if strategy_instance is None:
                self._delete_strategy(strategy_id, "Could not load strategy instance")
                return (False, "Could not load strategy instance")

            # Test all timeframes with training/holdout backtesting
            # Each TF validates its own coins (pattern-specific, no fallback)
            tf_results = {}
            tf_backtest_ids = {}
            tf_validated_coins = {}  # Track which coins were used per TF
            tf_optimal_params = {}  # Track optimal params per TF (from parametric)
            tf_all_parametric_results = {}  # Track ALL valid parametric results per TF
            tf_holdout_data = {}  # Track holdout data per TF (for additional parametric validation)

            # All strategies test ONLY their assigned timeframe
            # Parameters are embedded in code, no multi-TF optimization needed
            use_parametric = False  # Parametric disabled - params already in code

            for tf in [original_tf]:
                # Validate pattern coins for this timeframe (3-level validation)
                if pattern_coins:
                    validated_coins, validation_reason = self._validate_pattern_coins(
                        pattern_coins, tf
                    )
                    if validated_coins is None:
                        logger.info(
                            f"[{strategy_name}] {tf}: SKIPPED - {validation_reason}"
                        )
                        continue
                    pairs = validated_coins
                    logger.info(
                        f"[{strategy_name}] {tf}: Using {len(pairs)} validated pattern coins"
                    )
                else:
                    # Non-pattern strategy: use volume-based pairs with UNIFIED scroll-down
                    pairs, status = self._get_backtest_pairs(tf)
                    if not pairs:
                        logger.info(
                            f"[{strategy_name}] {tf}: SKIPPED - {status}"
                        )
                        continue

                logger.info(f"[{strategy_name}] Testing {tf} on {len(pairs)} pairs (training/holdout)...")

                # Load training/holdout data (NON-OVERLAPPING)
                training_data, holdout_data = self._get_training_holdout_data(pairs, tf)

                # Coins already validated, but check data loading succeeded
                if not training_data or len(training_data) < 5:
                    logger.warning(f"Insufficient training data for {tf}, skipping")
                    continue

                # Store validated coins for this TF
                tf_validated_coins[tf] = list(training_data.keys())

                # Run TRAINING period backtest
                try:
                    if use_parametric:
                        # Parametric: generate strategies with different SL/TP/leverage parameters
                        # Pass is_pattern_based to select appropriate parameter space
                        is_pattern_based = pattern_coins is not None and len(pattern_coins) > 0
                        parametric_results = self._run_parametric_backtest(
                            strategy_instance, training_data, tf, is_pattern_based
                        )
                        if not parametric_results:
                            # Details already logged by _run_parametric_backtest
                            logger.info(f"[{strategy_name}] {tf}: Skipped (no params passed thresholds)")
                            continue
                        # Use best result (first in sorted list)
                        training_result = parametric_results[0]
                        # Store optimal params for later update
                        optimal_params = training_result.get('params', {})
                        logger.info(
                            f"[{strategy_name}] {tf}: Parametric found optimal params: "
                            f"SL={optimal_params.get('sl_pct', 0):.1%}, "
                            f"TP={optimal_params.get('tp_pct', 0):.1%}, "
                            f"leverage={optimal_params.get('leverage', 1)}, "
                            f"exit_bars={optimal_params.get('exit_bars', 0)}"
                        )
                    else:
                        # Standard: use strategy's original parameters
                        training_result = self._run_multi_symbol_backtest(
                            strategy_instance, training_data, tf
                        )
                        optimal_params = None
                except Exception as e:
                    logger.error(f"Training backtest failed for {tf}: {e}")
                    continue

                if training_result is None or training_result.get('total_trades', 0) == 0:
                    logger.warning(f"No trades in training period for {tf}")
                    continue

                # Run HOLDOUT period backtest (validation)
                # Use min_bars=20 for holdout (30 days on 1d = only 30 bars)
                holdout_result = None
                try:
                    if holdout_data and len(holdout_data) >= 5:
                        holdout_result = self._run_multi_symbol_backtest(
                            strategy_instance, holdout_data, tf,
                            min_bars=20  # Lower threshold for holdout period
                        )
                except Exception as e:
                    logger.warning(f"Holdout backtest failed for {tf}: {e}")
                    holdout_result = None

                # Validate holdout and calculate final metrics
                validation = self._validate_holdout(training_result, holdout_result)

                if not validation['passed']:
                    logger.info(
                        f"[{strategy_name}] {tf}: REJECTED - {validation['reason']}"
                    )
                    continue

                # Combine training + holdout into final result
                final_result = self._calculate_final_metrics(
                    training_result, holdout_result, validation
                )

                tf_results[tf] = final_result

                # Store optimal params if parametric was used
                if optimal_params:
                    tf_optimal_params[tf] = optimal_params
                    # Also store ALL parametric results for this TF (for holdout validation)
                    tf_all_parametric_results[tf] = parametric_results

                # Store holdout data for this TF (needed for additional parametric validation)
                tf_holdout_data[tf] = holdout_data

                # Save training backtest result
                training_backtest_id = self._save_backtest_result(
                    strategy_id, training_result, pairs, tf,
                    is_optimal=False,
                    period_type='training',
                    period_days=self.training_days
                )

                # Save holdout backtest result (ALWAYS save, even with 0 trades)
                # 0 trades is DATA (pattern dormant in recent period), not failure
                holdout_backtest_id = None
                if holdout_result:
                    holdout_backtest_id = self._save_backtest_result(
                        strategy_id, holdout_result, pairs, tf,
                        is_optimal=False,
                        period_type='holdout',
                        period_days=self.holdout_days
                    )

                    # Link training result to holdout and add validation metrics
                    self._update_training_with_holdout(
                        training_backtest_id,
                        holdout_backtest_id,
                        final_result
                    )

                tf_backtest_ids[tf] = training_backtest_id

                holdout_trades = holdout_result.get('total_trades', 0) if holdout_result else 0
                holdout_sharpe = holdout_result.get('sharpe_ratio', 0) if holdout_result else 0
                logger.info(
                    f"[{strategy_name}] {tf}: "
                    f"Training: {training_result['total_trades']} trades, Sharpe {training_result.get('sharpe_ratio', 0):.2f} | "
                    f"Holdout: {holdout_trades} trades, Sharpe {holdout_sharpe:.2f} | "
                    f"Final Score: {final_result.get('final_score', 0):.2f}"
                )

            # Find optimal timeframe using final scores
            optimal_tf = self._find_optimal_timeframe(tf_results)

            if optimal_tf is None:
                self._delete_strategy(strategy_id, "No TF passed thresholds")
                return (False, "No TF passed thresholds")

            # Get validated coins for optimal TF (these are the coins to use in live trading)
            optimal_tf_coins = tf_validated_coins.get(optimal_tf, [])

            # Get optimal params for optimal TF (from parametric backtest)
            optimal_params_for_tf = tf_optimal_params.get(optimal_tf)

            # Update strategy with optimal TF, validated coins, and optimal params
            self._update_strategy_optimal_tf(
                strategy_id, optimal_tf, optimal_tf_coins, optimal_params_for_tf
            )

            # Run walk-forward analysis for stability validation
            # Skip for 1d/4h timeframes - windows too small for meaningful walk-forward
            wf_skipped = False
            if optimal_tf in ('1d', '4h'):
                logger.info(f"[{strategy_name}] Walk-forward skipped for {optimal_tf} (insufficient bars per window)")
                wf_stability = None
                wf_skipped = True
            else:
                logger.info(
                    f"[{strategy_name}] Running walk-forward analysis on {optimal_tf} "
                    f"for stability validation"
                )

                wf_stability = self._run_walk_forward_analysis(
                    strategy_instance=strategy_instance,
                    optimal_tf=optimal_tf,
                    validated_coins=optimal_tf_coins,
                    optimal_params=optimal_params_for_tf
                )

            if wf_stability is not None:
                # Update the optimal TF backtest result with walk-forward stability
                optimal_tf_backtest_id = tf_backtest_ids.get(optimal_tf)
                if optimal_tf_backtest_id:
                    self._update_backtest_with_walkforward(
                        optimal_tf_backtest_id,
                        wf_stability
                    )

                    logger.info(
                        f"[{strategy_name}] Walk-forward stability: {wf_stability:.3f} "
                        f"({'stable' if wf_stability < 0.15 else 'unstable'})"
                    )
                else:
                    logger.warning(f"[{strategy_name}] No backtest ID found for optimal TF {optimal_tf}")
            elif not wf_skipped:
                # Only warn if walk-forward actually failed (not skipped)
                logger.warning(f"[{strategy_name}] Walk-forward analysis failed")

            # Process additional parametric strategies (if any)
            # Each parameter set generates an independent strategy
            additional_results = tf_all_parametric_results.get(optimal_tf, [])[1:]  # Skip first
            if additional_results:
                logger.info(
                    f"Validating {len(additional_results)} additional parametric strategies "
                    f"with holdout testing (anti-overfitting)"
                )

                # Get holdout data for optimal TF
                holdout_data_for_tf = tf_holdout_data.get(optimal_tf)
                if not holdout_data_for_tf:
                    logger.warning(f"No holdout data for {optimal_tf}, skipping additional parametric validation")
                else:
                    for i, param_result in enumerate(additional_results, start=2):
                        # Run holdout validation for this strategy
                        try:
                            # Load strategy instance and apply these params
                            strategy_instance_for_holdout = self._load_strategy_instance(code, class_name)
                            if not strategy_instance_for_holdout:
                                continue

                            # Apply parameters to instance
                            params = param_result['params']
                            strategy_instance_for_holdout.sl_pct = params.get('sl_pct', 0.02)
                            strategy_instance_for_holdout.tp_pct = params.get('tp_pct', 0.03)
                            strategy_instance_for_holdout.leverage = params.get('leverage', 1)
                            strategy_instance_for_holdout.exit_after_bars = params.get('exit_bars', 0)

                            # Run holdout backtest with these params (min_bars=20 for 1d support)
                            holdout_result_for_params = self._run_multi_symbol_backtest(
                                strategy_instance_for_holdout, holdout_data_for_tf, optimal_tf,
                                min_bars=20  # Lower threshold for holdout period
                            )

                            # Validate holdout performance
                            validation_for_params = self._validate_holdout(
                                param_result, holdout_result_for_params
                            )

                            if not validation_for_params['passed']:
                                logger.info(
                                    f"Parametric strategy #{i} REJECTED on holdout: "
                                    f"{validation_for_params['reason']}"
                                )
                                continue  # Skip this strategy (overfitted)

                            # Calculate final metrics (training + holdout)
                            final_result_for_params = self._calculate_final_metrics(
                                param_result, holdout_result_for_params, validation_for_params
                            )

                            # Create independent strategy from parameter set
                            parametric_strategy_id = self._create_parametric_strategy(
                                strategy_id,
                                params,
                                strategy_num=i,
                                param_result=param_result,
                                holdout_result=holdout_result_for_params,
                                validation=validation_for_params
                            )

                            if parametric_strategy_id:
                                # Save training backtest
                                training_bt_id = self._save_backtest_result(
                                    parametric_strategy_id,
                                    param_result,
                                    optimal_tf_coins,
                                    optimal_tf,
                                    period_type='training'
                                )

                                # Save holdout backtest
                                if holdout_result_for_params:
                                    holdout_bt_id = self._save_backtest_result(
                                        parametric_strategy_id,
                                        holdout_result_for_params,
                                        optimal_tf_coins,
                                        optimal_tf,
                                        period_type='holdout'
                                    )

                                    # Link training to holdout
                                    self._update_training_with_holdout(
                                        training_bt_id,
                                        holdout_bt_id,
                                        final_result_for_params
                                    )

                                # Update strategy with optimal TF and pairs
                                self._update_strategy_optimal_tf(
                                    parametric_strategy_id, optimal_tf, optimal_tf_coins, None
                                )

                                logger.info(
                                    f"Parametric strategy {i} PASSED holdout validation: "
                                    f"Final score {final_result_for_params.get('final_score', 0):.2f}"
                                )

                        except Exception as e:
                            logger.error(f"Failed to validate parametric strategy #{i}: {e}")
                            continue

            # Mark optimal backtest
            if optimal_tf in tf_backtest_ids:
                self._mark_optimal_backtest(tf_backtest_ids[optimal_tf])

            # Promote to ACTIVE pool using leaderboard logic
            optimal_backtest_id = tf_backtest_ids.get(optimal_tf)
            if optimal_backtest_id:
                # Get backtest result for scoring
                with get_session() as session:
                    backtest_result = session.query(BacktestResult).filter(
                        BacktestResult.id == optimal_backtest_id
                    ).first()

                    if backtest_result:
                        # Try to enter ACTIVE pool (handles leaderboard logic)
                        entered, pool_reason = self._promote_to_active_pool(
                            strategy_id, backtest_result
                        )

                        if entered:
                            # Update last_backtested_at
                            strategy = session.query(Strategy).filter(
                                Strategy.id == strategy_id
                            ).first()
                            if strategy:
                                strategy.last_backtested_at = datetime.now(UTC)
                                session.commit()

                            optimal_result = tf_results[optimal_tf]
                            return (
                                True,
                                f"Entered ACTIVE pool: {pool_reason}, "
                                f"TF={optimal_tf}, Score={optimal_result.get('final_score', 0):.1f}"
                            )
                        else:
                            # Strategy didn't make it into pool (score too low)
                            return (
                                False,
                                f"Rejected from ACTIVE pool: {pool_reason}"
                            )

            # Fallback: no optimal backtest found (shouldn't happen)
            self.processor.release_strategy(strategy_id, "RETIRED")
            return (False, "No optimal backtest result found")

        except Exception as e:
            logger.error(f"Backtest error for {strategy_name}: {e}", exc_info=True)
            self.processor.mark_failed(strategy_id, str(e), delete=True)
            return (False, str(e))

    def _run_multi_symbol_backtest(
        self,
        strategy_instance,
        data: Dict[str, any],
        timeframe: str,
        min_bars: int = 100
    ) -> Dict:
        """
        Run portfolio backtest with realistic position limits

        Uses backtest_portfolio which simulates real trading constraints:
        - Maximum concurrent positions (from config)
        - Shared capital pool
        - Position priority based on signal order

        This ensures backtest results match live trading behavior.

        Args:
            strategy_instance: StrategyCore instance
            data: Dict mapping symbol -> DataFrame
            timeframe: Timeframe being tested
            min_bars: Minimum bars required per symbol (default 100, use 20 for walk-forward)

        Returns:
            Portfolio metrics with position-limited simulation
        """
        # Filter out empty/insufficient data
        valid_data = {
            symbol: df for symbol, df in data.items()
            if not df.empty and len(df) >= min_bars
        }

        if not valid_data:
            return {'total_trades': 0}

        # Use backtest_portfolio for realistic position-limited simulation
        try:
            result = self.engine.backtest(
                strategy=strategy_instance,
                data=valid_data,
                max_positions=None,  # Uses config value
                timeframe=timeframe  # For correct Sharpe annualization
            )
            return result
        except Exception as e:
            import traceback
            logger.error(f"Portfolio backtest failed: {e}\n{traceback.format_exc()}")
            return {'total_trades': 0}

    def _run_parametric_backtest(
        self,
        strategy_instance,
        data: Dict[str, any],
        timeframe: str,
        is_pattern_based: bool = False
    ) -> List[Dict]:
        """
        Run parametric backtest generating strategies with different SL/TP/leverage/exit.

        Extracts entry signals from the strategy once, then tests N parameter sets
        using the Numba-optimized ParametricBacktester to generate candidate strategies.

        TWO APPROACHES based on strategy origin:

        1. PATTERN STRATEGIES (is_pattern_based=True):
           - Have validated base values from pattern-discovery (magnitude, SL, holding)
           - Use build_pattern_centered_space() to explore variations AROUND base
           - Rationale: Pattern's edge is proven, optimize management params

        2. AI STRATEGIES (is_pattern_based=False):
           - No validated base values, AI invented the params
           - Use build_absolute_space() with fixed reasonable ranges
           - Rationale: Must search wider space to find what works

        Both approaches: 5x5x5x3 = 375 combinations

        Args:
            strategy_instance: StrategyCore instance
            data: Dict mapping symbol -> DataFrame
            timeframe: Timeframe being tested
            is_pattern_based: True for pattern strategies, False for AI strategies

        Returns:
            List of top K results with different parameters
        """
        import numpy as np

        if not self.parametric_enabled or self.parametric_backtester is None:
            # Fallback to single backtest with strategy's original params
            result = self._run_multi_symbol_backtest(strategy_instance, data, timeframe)
            return [result] if result.get('total_trades', 0) > 0 else []

        # Build parameter space based on strategy origin
        if is_pattern_based:
            # PATTERN STRATEGY: center on validated pattern values
            base_tp_pct = getattr(strategy_instance, 'tp_pct', 0.05)
            base_sl_pct = getattr(strategy_instance, 'sl_pct', 0.15)
            base_exit_bars = getattr(strategy_instance, 'exit_after_bars', 20)
            base_leverage = getattr(strategy_instance, 'leverage', 1)

            space = self.parametric_backtester.build_pattern_centered_space(
                base_tp_pct=base_tp_pct,
                base_sl_pct=base_sl_pct,
                base_exit_bars=base_exit_bars,
                base_leverage=base_leverage
            )
        else:
            # AI STRATEGY: use timeframe-scaled absolute ranges
            space = self.parametric_backtester.build_absolute_space(timeframe)

        self.parametric_backtester.set_parameter_space(space)

        # Filter out empty/insufficient data
        valid_data = {
            symbol: df for symbol, df in data.items()
            if not df.empty and len(df) >= 100
        }

        if not valid_data:
            return []

        # Sort symbols for consistent ordering
        symbols = sorted(valid_data.keys())
        n_symbols = len(symbols)

        # Find common index (intersection of all symbol indices)
        common_index = None
        for symbol in symbols:
            df = valid_data[symbol]
            if common_index is None:
                common_index = df.index
            else:
                common_index = common_index.intersection(df.index)

        if len(common_index) < 100:
            logger.warning(f"Insufficient common data for parametric backtest: {len(common_index)} bars")
            return []

        n_bars = len(common_index)

        # Build aligned 2D arrays (n_bars, n_symbols)
        close_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        high_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        low_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        entries_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        directions_2d = np.zeros((n_bars, n_symbols), dtype=np.int8)

        # Get strategy direction
        direction = getattr(strategy_instance, 'direction', 'long')
        dir_value = 1 if direction == 'long' else -1

        for j, symbol in enumerate(symbols):
            df = valid_data[symbol].loc[common_index].copy()

            # Calculate indicators and extract signals
            try:
                df_with_indicators = strategy_instance.calculate_indicators(df)
                signal_column = getattr(strategy_instance, 'signal_column', 'entry_signal')

                if signal_column in df_with_indicators.columns:
                    entries_2d[:, j] = df_with_indicators[signal_column].values.astype(bool)
                else:
                    entries_2d[:, j] = False
            except Exception as e:
                logger.warning(f"Failed to calculate indicators for {symbol}: {e}")
                entries_2d[:, j] = False

            # Fill OHLC data
            close_2d[:, j] = df['close'].values
            high_2d[:, j] = df['high'].values
            low_2d[:, j] = df['low'].values
            directions_2d[:, j] = dir_value

        # Apply warmup (first 100 bars = no signal)
        entries_2d[:100, :] = False

        # Count signals
        total_signals = entries_2d.sum()
        if total_signals == 0:
            logger.info("No entry signals found for parametric backtest (strategy conditions not met)")
            return []

        logger.info(
            f"Running parametric backtest: {n_bars} bars, {n_symbols} symbols, "
            f"{total_signals} signals, {self.parametric_backtester._count_strategies()} candidate strategies"
        )

        # Set timeframe for correct Sharpe annualization
        self.parametric_backtester.set_timeframe(timeframe)

        # Build max_leverages array from CoinRegistry (per-coin limits)
        registry = get_registry()
        max_leverages = np.zeros(n_symbols, dtype=np.int32)
        for j, symbol in enumerate(symbols):
            try:
                max_leverages[j] = registry.get_max_leverage(symbol)
            except Exception:
                # Fallback if coin not found (shouldn't happen with proper setup)
                max_leverages[j] = 10
                logger.warning(f"Could not get max_leverage for {symbol}, using default 10")

        # Run parametric backtest
        try:
            results_df = self.parametric_backtester.backtest_pattern(
                pattern_signals=entries_2d,
                ohlc_data={'close': close_2d, 'high': high_2d, 'low': low_2d},
                directions=directions_2d,
                max_leverages=max_leverages,
            )
        except Exception as e:
            logger.error(f"Parametric backtest failed: {e}")
            return []

        # Filter by threshold - save ALL strategies that pass
        valid_results = results_df[
            (results_df['sharpe'] >= self.min_sharpe) &
            (results_df['win_rate'] >= self.min_win_rate) &
            (results_df['expectancy'] >= self.min_expectancy) &
            (results_df['max_drawdown'] <= self.max_drawdown) &
            (results_df['total_trades'] >= self.min_trades)
        ].copy()

        # Convert to list of dicts matching expected format
        # Use float() to convert np.float64 to native Python float (required for DB)
        results = []
        for _, row in valid_results.iterrows():
            result = {
                'sharpe_ratio': float(row['sharpe']),
                'max_drawdown': float(row['max_drawdown']),
                'win_rate': float(row['win_rate']),
                'expectancy': float(row['expectancy']),
                'total_trades': int(row['total_trades']),
                'total_return': float(row['total_return']),
                'parametric_score': float(row['score']),
                # Store the parameters used
                'params': {
                    'sl_pct': float(row['sl_pct']),
                    'tp_pct': float(row['tp_pct']),
                    'leverage': int(row['leverage']),
                    'exit_bars': int(row['exit_bars']),
                },
            }
            results.append(result)

        if results:
            best = results[0]
            logger.info(
                f"Parametric: generated {len(results)} strategies | "
                f"Best: Sharpe={best['sharpe_ratio']:.2f}, Trades={best['total_trades']}, "
                f"SL={best['params']['sl_pct']:.1%}, TP={best['params']['tp_pct']:.1%}"
            )
        else:
            # Explain WHY no results passed thresholds
            n_tested = len(results_df)
            if n_tested > 0:
                best_sharpe = results_df['sharpe'].max()
                best_wr = results_df['win_rate'].max()
                max_trades = results_df['total_trades'].max()
                best_expectancy = results_df['expectancy'].max()
                min_dd = results_df['max_drawdown'].min()
                logger.info(
                    f"Parametric: 0/{n_tested} passed thresholds | "
                    f"Best metrics: Sharpe={best_sharpe:.2f} (need {self.min_sharpe}), "
                    f"WR={best_wr:.1%} (need {self.min_win_rate:.1%}), "
                    f"Trades={max_trades} (need {self.min_trades}), "
                    f"Expectancy={best_expectancy:.4f} (need {self.min_expectancy}), "
                    f"MinDD={min_dd:.1%} (need <{self.max_drawdown:.0%})"
                )

        return results

    def _validate_holdout(
        self,
        training_result: Dict,
        holdout_result: Optional[Dict]
    ) -> Dict:
        """
        Validate holdout performance for anti-overfitting check

        Holdout validation serves TWO purposes:
        1. Anti-overfitting: reject if holdout crashes vs training
        2. Recency: good holdout = strategy in form now

        CRITICAL: Training must have positive Sharpe first - if training Sharpe
        is negative or below threshold, strategy has no edge regardless of holdout.

        Returns:
            Dict with 'passed', 'reason', 'degradation', 'holdout_bonus'
        """
        training_sharpe = training_result.get('sharpe_ratio', 0)

        # CRITICAL: Training must show edge first
        # If training Sharpe is negative, strategy has no edge - reject early
        if training_sharpe < self.min_sharpe:
            return {
                'passed': False,
                'reason': f'Training Sharpe too low: {training_sharpe:.2f} < {self.min_sharpe}',
                'degradation': 0.0,
                'holdout_bonus': 0.0,
            }

        # Check holdout trades - penalize low activity instead of rejecting
        # This allows strategies to pass when market conditions don't match pattern
        # (e.g., flat market for momentum patterns), but with lower final score
        holdout_trades = holdout_result.get('total_trades', 0) if holdout_result else 0
        if holdout_trades == 0:
            # No holdout trades = pattern not active in recent period
            # Pass with heavy penalty - training edge is still valid
            logger.debug(
                f"No holdout trades - pattern dormant in current market. "
                f"Passing with -30% penalty."
            )
            return {
                'passed': True,
                'reason': 'No holdout trades - pattern dormant',
                'degradation': 0.5,
                'holdout_bonus': -0.30,  # Heavy penalty for dormant patterns
            }

        if holdout_trades < self.min_holdout_trades:
            # Some trades but below threshold - moderate penalty
            return {
                'passed': True,
                'reason': f'Low holdout trades: {holdout_trades} < {self.min_holdout_trades}',
                'degradation': 0.3,
                'holdout_bonus': -0.15,
            }

        holdout_sharpe = holdout_result.get('sharpe_ratio', 0)

        # Calculate degradation (how much worse is holdout vs training)
        # Guard against division by zero when training_sharpe is exactly 0
        if training_sharpe == 0:
            # No edge in training = cannot calculate degradation meaningfully
            # Treat as neutral (no degradation, no bonus)
            degradation = 0.0
        else:
            degradation = (training_sharpe - holdout_sharpe) / training_sharpe

        # Anti-overfitting check: reject if holdout crashes vs training
        if degradation > self.holdout_max_degradation:
            return {
                'passed': False,
                'reason': f'Overfitted: holdout {degradation:.0%} worse than training',
                'degradation': degradation,
                'holdout_bonus': 0.0,
            }

        # Check minimum holdout Sharpe (must also show edge in recent period)
        if holdout_sharpe < self.holdout_min_sharpe:
            return {
                'passed': False,
                'reason': f'Holdout Sharpe too low: {holdout_sharpe:.2f} < {self.holdout_min_sharpe}',
                'degradation': degradation,
                'holdout_bonus': 0.0,
            }

        # Calculate holdout bonus (good holdout = higher final score)
        # Bonus is positive if holdout >= training, zero if worse
        if degradation <= 0:
            # Holdout better than training = big bonus
            holdout_bonus = min(0.20, abs(degradation) * 0.5)
        else:
            # Holdout worse but within tolerance = small penalty
            holdout_bonus = -degradation * 0.10

        return {
            'passed': True,
            'reason': 'Holdout validated',
            'degradation': degradation,
            'holdout_bonus': holdout_bonus,
        }

    def _calculate_final_metrics(
        self,
        training_result: Dict,
        holdout_result: Optional[Dict],
        validation: Dict
    ) -> Dict:
        """
        Calculate final metrics combining training and holdout

        Final score formula:
        - Base score from training metrics
        - Weighted by holdout performance (recency_weight)
        - Adjusted by holdout bonus/penalty

        Returns:
            Dict with all metrics + final_score
        """
        training_sharpe = training_result.get('sharpe_ratio', 0)
        training_win_rate = training_result.get('win_rate', 0)
        training_expectancy = training_result.get('expectancy', 0)
        training_max_drawdown = training_result.get('max_drawdown', 0)

        # Calculate training base score
        # Bug fix: expectancy is already a percentage from backtest_engine.py
        # No division needed - dividing by initial_capital was corrupting the metric
        training_expectancy_pct = training_expectancy

        training_score = (
            0.5 * training_sharpe +
            0.3 * training_expectancy_pct +
            0.2 * training_win_rate
        )

        # Get holdout metrics
        if holdout_result and holdout_result.get('total_trades', 0) > 0:
            holdout_sharpe = holdout_result.get('sharpe_ratio', 0)
            holdout_win_rate = holdout_result.get('win_rate', 0)
            holdout_expectancy = holdout_result.get('expectancy', 0)
            holdout_max_drawdown = holdout_result.get('max_drawdown', 0)

            # Bug fix: expectancy is already a percentage
            holdout_expectancy_pct = holdout_expectancy
            holdout_score = (
                0.5 * holdout_sharpe +
                0.3 * holdout_expectancy_pct +
                0.2 * holdout_win_rate
            )
        else:
            holdout_sharpe = 0
            holdout_win_rate = 0
            holdout_expectancy = 0
            holdout_max_drawdown = training_max_drawdown  # Use training if no holdout
            holdout_expectancy_pct = 0  # Bug fix: must be defined for weighted calculation
            holdout_score = training_score  # Neutral if no holdout

        # Calculate weighted final score
        # Holdout has higher weight because it represents "now"
        training_weight = 1 - self.holdout_recency_weight
        final_score = (
            training_score * training_weight +
            holdout_score * self.holdout_recency_weight
        )

        # Apply holdout bonus/penalty
        holdout_bonus = validation.get('holdout_bonus', 0)
        final_score = final_score * (1 + holdout_bonus)

        # Calculate weighted metrics for classifier (training 40% + holdout 60%)
        # Each metric weighted individually (not composite) for accurate classification
        weighted_sharpe_pure = (training_sharpe * 0.4) + (holdout_sharpe * 0.6) if holdout_sharpe is not None else training_sharpe
        weighted_expectancy = (training_expectancy_pct * 0.4) + (holdout_expectancy_pct * 0.6) if holdout_expectancy_pct is not None else training_expectancy_pct
        weighted_win_rate = (training_win_rate * 0.4) + (holdout_win_rate * 0.6) if holdout_win_rate is not None else training_win_rate
        weighted_max_drawdown = (training_max_drawdown * 0.4) + (holdout_max_drawdown * 0.6)

        # Walk-forward stability: check if available from optimization
        weighted_walk_forward_stability = training_result.get('walk_forward_stability')

        return {
            **training_result,
            # Training metrics
            'training_sharpe': training_sharpe,
            'training_win_rate': training_win_rate,
            'training_expectancy': training_expectancy,
            'training_score': training_score,
            # Holdout metrics
            'holdout_sharpe': holdout_sharpe,
            'holdout_win_rate': holdout_win_rate,
            'holdout_expectancy': holdout_expectancy,
            'holdout_score': holdout_score,
            'holdout_trades': holdout_result.get('total_trades', 0) if holdout_result else 0,
            # Validation metrics
            'degradation': validation.get('degradation', 0),
            'holdout_bonus': holdout_bonus,
            # Final score
            'final_score': final_score,
            # Individual weighted metrics for classifier
            'weighted_sharpe_pure': weighted_sharpe_pure,
            'weighted_expectancy': weighted_expectancy,
            'weighted_win_rate': weighted_win_rate,
            'weighted_walk_forward_stability': weighted_walk_forward_stability,
            'weighted_max_drawdown': weighted_max_drawdown,
        }

    def _update_training_with_holdout(
        self,
        training_backtest_id: str,
        holdout_backtest_id: str,
        final_result: Dict
    ):
        """
        Update training backtest result with holdout reference and final metrics
        """
        if not training_backtest_id:
            return

        try:
            with get_session() as session:
                bt = session.query(BacktestResult).filter(
                    BacktestResult.id == training_backtest_id
                ).first()

                if bt:
                    # Link to holdout result (even if 0 trades)
                    if holdout_backtest_id:
                        bt.recent_result_id = holdout_backtest_id

                    # Store final metrics (ALWAYS - final_result exists even with 0 holdout trades)
                    # FAST FAIL: If final_score is None, crash (indicates bug in _calculate_final_metrics)
                    final_score = final_result.get('final_score')
                    if final_score is None:
                        raise ValueError(
                            f"final_score is None for training backtest {training_backtest_id} "
                            f"(holdout_id={holdout_backtest_id}). "
                            f"This indicates a bug in _calculate_final_metrics(). "
                            f"All strategies must have a final_score calculated."
                        )

                    bt.weighted_sharpe = final_score

                    # Save individual weighted metrics for classifier
                    bt.weighted_sharpe_pure = final_result.get('weighted_sharpe_pure')
                    bt.weighted_expectancy = final_result.get('weighted_expectancy')
                    bt.weighted_win_rate = final_result.get('weighted_win_rate')
                    bt.weighted_walk_forward_stability = final_result.get('weighted_walk_forward_stability')
                    bt.weighted_max_drawdown = final_result.get('weighted_max_drawdown')

                    bt.recency_ratio = 1 - final_result.get('degradation', 0)
                    bt.recency_penalty = -final_result.get('holdout_bonus', 0)

                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update training result with holdout: {e}")

    def _find_optimal_timeframe(self, tf_results: Dict[str, Dict]) -> Optional[str]:
        """
        Find TF with best performance that passes all thresholds.

        Uses final_score which combines training + holdout performance.

        Returns:
            Optimal timeframe string or None if none pass
        """
        best_tf = None
        best_score = -float('inf')

        for tf, results in tf_results.items():
            # Check thresholds (based on training metrics)
            total_trades = results.get('total_trades', 0)
            training_sharpe = results.get('training_sharpe', results.get('sharpe_ratio', 0))
            training_win_rate = results.get('training_win_rate', results.get('win_rate', 0))
            max_dd = results.get('max_drawdown', 1)
            training_expectancy = results.get('training_expectancy', results.get('expectancy', 0))

            # Must pass all thresholds
            if total_trades < self.min_trades:
                logger.debug(f"{tf}: Failed trades threshold ({total_trades} < {self.min_trades})")
                continue
            if training_sharpe < self.min_sharpe:
                logger.debug(f"{tf}: Failed sharpe threshold ({training_sharpe:.2f} < {self.min_sharpe})")
                continue
            if training_win_rate < self.min_win_rate:
                logger.debug(f"{tf}: Failed win_rate threshold ({training_win_rate:.2%} < {self.min_win_rate:.2%})")
                continue
            if max_dd > self.max_drawdown:
                logger.debug(f"{tf}: Failed drawdown threshold ({max_dd:.2%} > {self.max_drawdown:.2%})")
                continue
            if training_expectancy < self.min_expectancy:
                logger.debug(f"{tf}: Failed expectancy threshold ({training_expectancy:.4f} < {self.min_expectancy})")
                continue

            # Use final_score (combines training + holdout)
            score = results.get('final_score', 0)

            logger.debug(
                f"{tf}: Final Score {score:.2f} "
                f"(training={results.get('training_score', 0):.2f}, "
                f"holdout={results.get('holdout_score', 0):.2f}, "
                f"bonus={results.get('holdout_bonus', 0):.1%})"
            )

            if score > best_score:
                best_score = score
                best_tf = tf

        if best_tf:
            logger.info(f"Optimal TF: {best_tf} with final score {best_score:.2f}")

        return best_tf

    def _run_walk_forward_analysis(
        self,
        strategy_instance,
        optimal_tf: str,
        validated_coins: List[str],
        optimal_params: Optional[Dict]
    ) -> Optional[float]:
        """
        Run walk-forward analysis to calculate strategy stability.

        Creates 4 expanding windows to test consistency across time:
        - Window 1: Train 75%, Test 6.25%
        - Window 2: Train 81.25%, Test 6.25%
        - Window 3: Train 87.5%, Test 6.25%
        - Window 4: Train 93.75%, Test 6.25%

        Stability = std_dev(edge across windows) - lower is better

        Args:
            strategy_instance: Strategy to test
            optimal_tf: Optimal timeframe
            validated_coins: Coins that passed validation
            optimal_params: Optimal parameters from parametric backtest

        Returns:
            Stability score (std dev of edge) or None if failed
        """
        try:
            import numpy as np
            from src.backtester.cache_reader import BacktestCacheReader

            # Create cache reader for loading training data
            cache_reader = BacktestCacheReader(self.data_loader.cache_dir)

            # Load full training data for all validated coins
            training_data = {}
            for symbol in validated_coins:
                df = cache_reader.read(
                    symbol=symbol,
                    timeframe=optimal_tf,
                    days=self.training_days
                )
                if not df.empty:
                    training_data[symbol] = df

            if len(training_data) < 5:
                logger.warning("Walk-forward: insufficient symbols (need >= 5)")
                return None

            # Apply optimal params to strategy if available
            if optimal_params:
                strategy_instance.sl_pct = optimal_params.get('sl_pct', 0.02)
                strategy_instance.tp_pct = optimal_params.get('tp_pct', 0.03)
                strategy_instance.leverage = optimal_params.get('leverage', 1)
                strategy_instance.exit_after_bars = optimal_params.get('exit_bars', 0)

            # OPTIMIZED: Run walk-forward on ALL symbols together (4 backtests total, not 120)
            # Pick a reference symbol to split the time windows
            reference_symbol = list(training_data.keys())[0]
            reference_df = training_data[reference_symbol]

            # Create 4 expanding windows based on time
            windows_splits = self.data_loader.walk_forward_split(reference_df, n_windows=4)

            # Extract timestamps for each window
            window_timestamps = []
            for train_df, test_df in windows_splits:
                if len(test_df) > 0:
                    test_start = test_df['timestamp'].min()
                    test_end = test_df['timestamp'].max()
                    window_timestamps.append((test_start, test_end))

            if len(window_timestamps) < 4:
                logger.warning("Walk-forward: insufficient time windows")
                return None

            # Run 4 backtests (one per window, all symbols together)
            edge_per_window = []
            valid_windows = 0

            for window_idx, (test_start, test_end) in enumerate(window_timestamps):
                # Filter all symbols to this time window
                window_data = {}
                for symbol, df in training_data.items():
                    window_df = df[(df['timestamp'] >= test_start) & (df['timestamp'] <= test_end)]
                    if not window_df.empty:
                        window_data[symbol] = window_df

                if len(window_data) < 5:  # Need minimum symbols
                    logger.info(f"Walk-forward window {window_idx+1}: skipped (only {len(window_data)} symbols)")
                    continue

                # Log window size for debugging
                window_bars = min(len(df) for df in window_data.values())
                logger.info(f"Walk-forward window {window_idx+1}: {len(window_data)} symbols, {window_bars} bars")

                # Backtest this window on all symbols (min_bars=20 for small WF windows)
                result = self._run_multi_symbol_backtest(
                    strategy_instance,
                    window_data,
                    optimal_tf,
                    min_bars=20  # Relaxed for walk-forward windows
                )

                # Accept if we have at least 1 trade (relaxed from 3)
                trades = result.get('total_trades', 0) if result else 0
                if trades >= 1:
                    edge = result.get('expectancy', 0)
                    edge_per_window.append(edge)
                    valid_windows += 1
                    logger.info(f"Walk-forward window {window_idx+1}: PASSED edge={edge:.3f}, trades={trades}")
                else:
                    logger.info(f"Walk-forward window {window_idx+1}: FAILED trades={trades}")

            # Need at least 3 valid windows (relaxed from 4)
            if valid_windows < 3:
                logger.warning(f"Walk-forward: only {valid_windows}/4 windows completed (need >= 3)")
                return None

            # Stability = standard deviation of edge across windows
            # Lower is better (consistent performance across time)
            stability = float(np.std(edge_per_window))

            logger.info(
                f"Walk-forward edges: {[f'{e:.2%}' for e in edge_per_window]}, "
                f"stability: {stability:.3f} ({valid_windows}/4 windows)"
            )

            return stability

        except Exception as e:
            logger.error(f"Walk-forward analysis failed: {e}")
            return None

    def _update_backtest_with_walkforward(
        self,
        backtest_id: str,
        wf_stability: float
    ):
        """
        Update backtest result with walk-forward stability.

        Args:
            backtest_id: BacktestResult UUID
            wf_stability: Walk-forward stability score
        """
        try:
            from src.database.models import BacktestResult
            with get_session() as session:
                bt = session.query(BacktestResult).filter(
                    BacktestResult.id == backtest_id
                ).first()

                if bt:
                    bt.walk_forward_stability = wf_stability
                    bt.weighted_walk_forward_stability = wf_stability
                    session.commit()
                    logger.debug(f"Updated backtest {backtest_id} with walk-forward stability: {wf_stability:.3f}")

        except Exception as e:
            logger.error(f"Failed to update walk-forward stability: {e}")

    def _to_python_type(self, value):
        """
        Convert numpy types to Python native types for database storage.

        PostgreSQL doesn't understand numpy types (np.float64, np.int64, etc.)
        and throws 'schema "np" does not exist' error.
        """
        import numpy as np
        if value is None:
            return None
        if isinstance(value, (np.integer, np.floating)):
            return float(value) if isinstance(value, np.floating) else int(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.bool_):
            return bool(value)
        return value

    def _save_backtest_result(
        self,
        strategy_id,
        result: Dict,
        pairs: List[str],
        timeframe: str,
        is_optimal: bool = False,
        period_type: str = 'training',
        period_days: Optional[int] = None
    ) -> Optional[str]:
        """
        Save backtest results to database

        Args:
            strategy_id: Strategy UUID
            result: Backtest metrics dictionary
            pairs: List of symbols tested
            timeframe: Timeframe tested
            is_optimal: Whether this is the optimal TF
            period_type: 'training' or 'holdout'
            period_days: Number of days in this period

        Returns:
            BacktestResult UUID
        """
        try:
            with get_session() as session:
                # Get start/end dates from symbol_breakdown if available
                start_date = datetime.now()
                end_date = datetime.now()

                # Determine period_days if not provided
                if period_days is None:
                    period_days = self.training_days if period_type == 'training' else self.holdout_days

                # Convert numpy types to Python native (PostgreSQL doesn't understand np.float64)
                bt_result = BacktestResult(
                    strategy_id=strategy_id,
                    lookback_days=period_days,
                    initial_capital=self.config.get('backtesting', {}).get('initial_capital', 10000),
                    start_date=start_date,
                    end_date=end_date,

                    # Aggregate metrics (converted from numpy)
                    total_trades=self._to_python_type(result.get('total_trades', 0)),
                    win_rate=self._to_python_type(result.get('win_rate')),
                    sharpe_ratio=self._to_python_type(result.get('sharpe_ratio')),
                    expectancy=self._to_python_type(result.get('expectancy')),
                    max_drawdown=self._to_python_type(result.get('max_drawdown')),
                    final_equity=self._to_python_type(result.get('final_equity')),
                    total_return_pct=self._to_python_type(result.get('total_return')),

                    # Multi-pair/TF fields
                    symbols_tested=pairs,
                    timeframe_tested=timeframe,
                    is_optimal_tf=is_optimal,
                    per_symbol_results=result.get('symbol_breakdown', {}),

                    # Dual-period fields
                    period_type=period_type,
                    period_days=period_days,

                    # Raw metrics
                    raw_metrics=result
                )
                session.add(bt_result)
                session.flush()  # Get ID before commit
                result_id = str(bt_result.id)
                session.commit()

                return result_id
        except Exception as e:
            logger.error(f"Failed to save backtest result: {e}")
            return None

    def _update_strategy_optimal_tf(
        self,
        strategy_id,
        optimal_tf: str,
        pairs: List[str],
        optimal_params: Optional[Dict] = None
    ):
        """
        Update strategy with optimal TF, pairs, and parameters from parametric backtest.

        If optimal_params is provided (from parametric backtest), updates the strategy's
        sl_pct, tp_pct, leverage, and exit_after_bars in the code.

        Args:
            strategy_id: Strategy UUID
            optimal_tf: Best performing timeframe
            pairs: Validated coins for this timeframe
            optimal_params: Dict with sl_pct, tp_pct, leverage, exit_bars (from parametric)
        """
        try:
            with get_session() as session:
                strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if strategy:
                    strategy.optimal_timeframe = optimal_tf
                    strategy.backtest_pairs = pairs
                    strategy.backtest_date = datetime.now(UTC)
                    strategy.tested_at = datetime.now(UTC)
                    strategy.backtest_completed_at = datetime.now(UTC)
                    strategy.processing_completed_at = datetime.now(UTC)

                    # Update strategy code with optimal params from parametric backtest
                    if optimal_params:
                        updated_code = self._update_strategy_params(
                            strategy.code, optimal_params
                        )
                        if updated_code:
                            strategy.code = updated_code

                    session.commit()

                    params_str = ""
                    if optimal_params:
                        params_str = (
                            f", params: SL={optimal_params.get('sl_pct', 0):.1%}, "
                            f"TP={optimal_params.get('tp_pct', 0):.1%}, "
                            f"lev={optimal_params.get('leverage', 1)}"
                        )

                    logger.info(
                        f"Updated strategy {strategy.name}: "
                        f"optimal_tf={optimal_tf}, pairs={len(pairs)}{params_str}"
                    )
        except Exception as e:
            logger.error(f"Failed to update strategy: {e}")

    def _create_parametric_strategy(
        self,
        template_strategy_id: UUID,
        params: Dict,
        strategy_num: int,
        param_result: Optional[Dict] = None,
        holdout_result: Optional[Dict] = None,
        validation: Optional[Dict] = None
    ) -> Optional[UUID]:
        """
        Create an independent strategy from a parameter set.

        Each parameter set generates a unique, independent strategy.
        Name is generated using hash of parameters for uniqueness.

        Args:
            template_strategy_id: UUID of template strategy (code source)
            params: Dict with sl_pct, tp_pct, leverage, exit_bars
            strategy_num: Sequence number (for logging only)
            param_result: Training backtest metrics (optional)
            holdout_result: Holdout backtest metrics (optional)
            validation: Holdout validation results (optional)

        Returns:
            UUID of new strategy, or None if failed
        """
        try:
            import hashlib
            from src.database.models import Strategy

            with get_session() as session:
                # Get template strategy (source of code)
                template = session.query(Strategy).filter(
                    Strategy.id == template_strategy_id
                ).first()

                if not template:
                    logger.error(f"Template strategy {template_strategy_id} not found")
                    return None

                # Generate unique name using new strategy UUID
                # This guarantees uniqueness even with race conditions
                new_id = uuid4()

                # Create independent strategy
                strategy = Strategy()
                strategy.id = new_id
                # Use first 8 chars of UUID for guaranteed uniqueness
                strategy.name = f"Strategy_{template.strategy_type}_{str(new_id)[:8]}"
                strategy.strategy_type = template.strategy_type
                strategy.ai_provider = template.ai_provider
                strategy.timeframe = template.timeframe  # Will be updated with optimal TF
                strategy.status = "GENERATED"  # Must go through validator → backtester pipeline

                # Update code with these parameters
                updated_code = self._update_strategy_params(template.code, params)
                if not updated_code:
                    logger.warning(f"Failed to update code for strategy {strategy.name}")
                    return None

                strategy.code = updated_code

                # Store parametric backtest metrics as metadata (for comparison with official backtest)
                if param_result and validation:
                    strategy.parametric_backtest_metrics = {
                        'training_sharpe': param_result.get('sharpe'),
                        'training_win_rate': param_result.get('win_rate'),
                        'training_expectancy': param_result.get('expectancy'),
                        'holdout_sharpe': holdout_result.get('sharpe') if holdout_result else None,
                        'holdout_degradation': validation.get('degradation_pct'),
                        'tested_at': datetime.now(UTC).isoformat()
                    }

                strategy.template_id = template.template_id
                strategy.pattern_ids = template.pattern_ids
                strategy.generation_mode = 'template'  # Mark as template-generated
                strategy.parameters = params  # Store parameters used
                strategy.created_at = datetime.now(UTC)
                # Other timestamps (tested_at, backtest_completed_at) will be set by validator/backtester

                session.add(strategy)
                session.commit()

                logger.info(
                    f"Created parametric strategy {strategy.name} with params: "
                    f"SL={params.get('sl_pct', 0):.1%}, "
                    f"TP={params.get('tp_pct', 0):.1%}, "
                    f"lev={params.get('leverage', 1)}"
                )

                return strategy.id

        except Exception as e:
            logger.error(f"Failed to create parametric strategy: {e}")
            return None

    def _update_strategy_params(self, code: str, params: Dict) -> Optional[str]:
        """
        Update strategy class attributes with optimal parameters from parametric backtest.

        Replaces the class-level sl_pct, tp_pct, leverage, exit_after_bars with
        the values found during parametric optimization.

        Args:
            code: Strategy source code
            params: Dict with sl_pct, tp_pct, leverage, exit_bars

        Returns:
            Updated code or None if update failed
        """
        import re

        try:
            updated = code

            # Update sl_pct
            if 'sl_pct' in params:
                updated = re.sub(
                    r'(\s+sl_pct\s*=\s*)[\d.]+',
                    rf'\g<1>{params["sl_pct"]}',
                    updated
                )

            # Update tp_pct
            if 'tp_pct' in params:
                updated = re.sub(
                    r'(\s+tp_pct\s*=\s*)[\d.]+',
                    rf'\g<1>{params["tp_pct"]}',
                    updated
                )

            # Update leverage
            if 'leverage' in params:
                updated = re.sub(
                    r'(\s+leverage\s*=\s*)\d+',
                    rf'\g<1>{int(params["leverage"])}',
                    updated
                )

            # Update exit_after_bars
            if 'exit_bars' in params:
                updated = re.sub(
                    r'(\s+exit_after_bars\s*=\s*)\d+',
                    rf'\g<1>{int(params["exit_bars"])}',
                    updated
                )

            # Verify syntax is still valid
            import ast
            ast.parse(updated)

            return updated

        except Exception as e:
            logger.warning(f"Failed to update strategy params: {e}")
            return None

    def _mark_optimal_backtest(self, backtest_id: str):
        """Mark a backtest result as optimal TF"""
        try:
            with get_session() as session:
                bt = session.query(BacktestResult).filter(
                    BacktestResult.id == backtest_id
                ).first()

                if bt:
                    bt.is_optimal_tf = True
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to mark optimal backtest: {e}")

    def _extract_class_name(self, code: str) -> Optional[str]:
        """Extract class name from strategy code (supports Strategy_ and PatStrat_)"""
        import re
        match = re.search(r'class\s+((?:Strategy|PatStrat)_\w+)\s*\(', code)
        return match.group(1) if match else None

    def _load_strategy_instance(self, code: str, class_name: str):
        """Load strategy instance from code"""
        temp_path = None
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
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)

    def _delete_strategy(self, strategy_id, reason: str):
        """Delete failed strategy"""
        self.processor.mark_failed(strategy_id, reason, delete=True)

    # ========================================================================
    # RE-BACKTEST METHODS (for ACTIVE pool freshness)
    # ========================================================================

    def _get_strategy_needing_retest(self) -> Optional[Strategy]:
        """
        Get one ACTIVE strategy that needs re-testing (FIFO order).

        Returns the oldest strategy (by last_backtested_at) that exceeds
        the retest_interval_days threshold.

        Returns:
            Strategy model or None if no strategies need re-testing
        """
        from datetime import timedelta

        threshold = datetime.now(UTC) - timedelta(days=self.retest_interval_days)

        with get_session() as session:
            strategy = (
                session.query(Strategy)
                .filter(Strategy.status == 'ACTIVE')
                .filter(Strategy.last_backtested_at < threshold)
                .order_by(Strategy.last_backtested_at.asc())  # FIFO: oldest first
                .first()
            )

            if strategy:
                # Return detached copy
                return {
                    'id': strategy.id,
                    'name': strategy.name,
                    'code': strategy.code,
                    'optimal_timeframe': strategy.optimal_timeframe,
                    'backtest_pairs': strategy.backtest_pairs,
                    'last_backtested_at': strategy.last_backtested_at,
                    'score_backtest': strategy.score_backtest,
                }

        return None

    def _retest_strategy(
        self,
        strategy_id: UUID,
        strategy_name: str,
        code: str,
        optimal_tf: str,
        pairs: List[str]
    ) -> Tuple[bool, str]:
        """
        Re-backtest an ACTIVE strategy on its optimal TF only.

        Simplified version of _backtest_strategy_all_tf:
        - Only tests optimal TF (not all 6 TFs)
        - Uses same parameters (no parametric)
        - Training + holdout (365 + 30 days)
        - All 30 coins

        After re-backtest:
        1. Calculate new score
        2. Update last_backtested_at
        3. If score < min_score -> RETIRED
        4. If score < min(pool) and pool full -> RETIRED
        5. Otherwise stays in ACTIVE with updated score

        Returns:
            (success, reason) tuple
        """
        try:
            logger.info(f"[RETEST] {strategy_name}: Starting re-backtest on {optimal_tf}")

            # Load strategy instance
            class_name = self._extract_class_name(code)
            if not class_name:
                return (False, "Could not extract class name")

            strategy_instance = self._load_strategy_instance(code, class_name)
            if strategy_instance is None:
                return (False, "Could not load strategy instance")

            # Validate pairs (same 3-level validation as initial backtest)
            validated_pairs, status = self._scroll_down_coverage(
                coins=pairs,
                timeframe=optimal_tf,
                target_count=self.max_coins,
                min_count=5
            )

            if validated_pairs is None:
                logger.warning(f"[RETEST] {strategy_name}: pairs validation failed ({status})")
                # Mark strategy for retirement (data quality degraded)
                self.pool_manager._retire_strategy(
                    strategy_id,
                    f"Re-test failed: {status}"
                )
                return (False, f"Pair validation failed: {status}")

            # Load training/holdout data
            training_data, holdout_data = self._get_training_holdout_data(
                validated_pairs, optimal_tf
            )

            if not training_data or len(training_data) < 5:
                logger.warning(f"[RETEST] {strategy_name}: insufficient training data")
                return (False, "Insufficient training data")

            # Run training backtest (no parametric - use existing params)
            training_result = self._run_multi_symbol_backtest(
                strategy_instance, training_data, optimal_tf
            )

            if training_result is None or training_result.get('total_trades', 0) == 0:
                logger.warning(f"[RETEST] {strategy_name}: no trades in training")
                return (False, "No trades in training period")

            # Run holdout backtest (min_bars=20 for 1d timeframe support)
            holdout_result = None
            if holdout_data and len(holdout_data) >= 5:
                holdout_result = self._run_multi_symbol_backtest(
                    strategy_instance, holdout_data, optimal_tf,
                    min_bars=20  # Lower threshold for holdout period
                )

            # Validate holdout
            validation = self._validate_holdout(training_result, holdout_result)

            if not validation['passed']:
                logger.info(f"[RETEST] {strategy_name}: holdout failed ({validation['reason']})")
                self.pool_manager._retire_strategy(strategy_id, f"Re-test holdout: {validation['reason']}")
                return (False, f"Holdout validation failed: {validation['reason']}")

            # Calculate final metrics
            final_result = self._calculate_final_metrics(
                training_result, holdout_result, validation
            )

            # Calculate new score using SCORER
            new_score = self.scorer.score({
                'expectancy': final_result.get('weighted_expectancy', 0),
                'sharpe_ratio': final_result.get('weighted_sharpe_pure', 0),
                'consistency': final_result.get('weighted_win_rate', 0),
                'wf_stability': final_result.get('weighted_walk_forward_stability', 1.0),
            })

            logger.info(
                f"[RETEST] {strategy_name}: new score {new_score:.1f} "
                f"(sharpe={final_result.get('weighted_sharpe_pure', 0):.2f})"
            )

            # Update backtest result (save new metrics)
            self._save_backtest_result(
                strategy_id, training_result, validated_pairs, optimal_tf,
                is_optimal=True, period_type='training', period_days=self.training_days
            )

            # Revalidate pool membership with new score
            still_active, reason = self.pool_manager.revalidate_after_retest(
                strategy_id, new_score
            )

            if still_active:
                logger.info(f"[RETEST] {strategy_name}: PASSED - {reason}")
                return (True, reason)
            else:
                logger.info(f"[RETEST] {strategy_name}: RETIRED - {reason}")
                return (False, reason)

        except Exception as e:
            logger.error(f"[RETEST] {strategy_name}: error - {e}", exc_info=True)
            return (False, str(e))

    def _promote_to_active_pool(
        self,
        strategy_id: UUID,
        backtest_result: BacktestResult
    ) -> Tuple[bool, str]:
        """
        Attempt to promote a strategy to the ACTIVE pool after backtest.

        Calculates score and uses PoolManager for leaderboard logic.

        Args:
            strategy_id: Strategy UUID
            backtest_result: BacktestResult with optimal TF metrics

        Returns:
            (success, reason) tuple
        """
        try:
            # Calculate score from backtest result
            score = self.scorer.score_from_backtest_result(backtest_result)

            # Try to enter pool (handles leaderboard logic)
            success, reason = self.pool_manager.try_enter_pool(strategy_id, score)

            return (success, reason)

        except ValueError as e:
            logger.warning(f"Cannot calculate score for {strategy_id}: {e}")
            return (False, str(e))

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True

        # Release any claimed strategies
        self.processor.release_all_by_process()

        # Shutdown executor (cancels pending futures)
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

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
            logger.info("Backtester process terminated")
