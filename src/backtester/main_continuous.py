"""
Continuous Backtester Process

Backtests validated strategies with portfolio simulation.
- Multi-pair backtesting (top 30 coins by volume)
- Backtest on assigned timeframe with training/holdout validation
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
import time

# Suppress pandas FutureWarning about fillna downcasting (from AI-generated strategies)
warnings.filterwarnings('ignore', category=FutureWarning, message='.*Downcasting.*fillna.*')

import pandas as pd

from sqlalchemy.orm import joinedload

from src.config import load_config
from src.database import get_session, Strategy, BacktestResult, StrategyProcessor
from src.database.models import ValidationCache
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.backtester.parametric_backtest import ParametricBacktester
# NOTE: MultiWindowValidator removed - replaced by WFA with parameter re-optimization
from src.data.coin_registry import get_registry, get_active_pairs
from src.scorer import BacktestScorer, PoolManager
from src.validator.lookahead_test import LookaheadTester
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
    Backtests strategies on their assigned timeframe.
    Strategies that pass thresholds are promoted to ACTIVE.
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

        # In-sample/Out-of-sample configuration
        self.is_days = self.config.get_required('backtesting.is_days')
        self.oos_days = self.config.get_required('backtesting.oos_days')
        self.min_coverage_pct = self.config.get_required('backtesting.min_coverage_pct')

        # Out-of-sample validation thresholds
        self.oos_max_degradation = self.config.get_required('backtesting.out_of_sample.max_degradation')
        self.oos_min_sharpe = self.config.get_required('backtesting.out_of_sample.min_sharpe')
        self.oos_recency_weight = self.config.get_required('backtesting.out_of_sample.recency_weight')

        # Min trades per timeframe (parallel arrays)
        timeframes = self.config.get_required('timeframes')
        min_is = self.config.get_required('backtesting.min_trades.in_sample')
        min_oos = self.config.get_required('backtesting.min_trades.out_of_sample')
        self.min_trades_is = dict(zip(timeframes, min_is))
        self.min_trades_oos = dict(zip(timeframes, min_oos))

        # Initial capital for expectancy normalization
        self.initial_capital = self.config.get_required('backtesting.initial_capital')

        # Robustness validation (parameter stability check)
        self.robustness_enabled = self.config.get_required('backtesting.robustness.enabled')
        # Load thresholds per generation_mode
        self.robustness_thresholds = {
            'pattern': self.config.get('backtesting.robustness.min_threshold_pattern', 0.30),
            'optimized': self.config.get('backtesting.robustness.min_threshold_optimized', 0.40),
            'ai_free': self.config.get_required('backtesting.robustness.min_threshold'),
            'ai_assigned': self.config.get_required('backtesting.robustness.min_threshold'),
        }

        # SCORER and PoolManager for post-backtest scoring and pool management
        self.scorer = BacktestScorer(self.config._raw_config)
        self.pool_manager = PoolManager(self.config._raw_config)

        # Lookahead tester for post-scoring shuffle test (anti-lookahead)
        self.lookahead_tester = LookaheadTester()
        self._test_data: Optional[pd.DataFrame] = None  # Lazy loaded

        # NOTE: multi_window_validator removed - replaced by WFA with parameter re-optimization

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
        target_count: int = None
    ) -> Tuple[Optional[List[str]], str]:
        """
        UNIFIED scroll-down logic for both Pattern and AI strategies.

        Iterates through coins (ordered by edge OR volume) and selects
        first N coins with sufficient data coverage.

        Args:
            coins: List of coins to check (already filtered for liquidity + cache)
            timeframe: Timeframe to validate
            target_count: Target number of pairs (default: self.max_coins)

        Returns:
            (validated_coins, status) - validated_coins is None if no coins pass
        """
        if target_count is None:
            target_count = self.max_coins  # 30

        # Get cache reader
        from src.backtester.cache_reader import BacktestCacheReader
        cache_reader = BacktestCacheReader(self.data_loader.cache_dir)

        # Check coverage for ALL coins (scroll-down logic)
        total_days = self.is_days + self.oos_days
        min_days_required = total_days * self.min_coverage_pct

        validated_coins = []
        for coin in coins:  # Iterate ALL coins (no early break)
            info = cache_reader.get_cache_info(coin, timeframe)
            if info and info.get('days', 0) >= min_days_required:
                validated_coins.append(coin)

        if not validated_coins:
            return None, "no_coins_with_coverage"

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
            target_count=target_count
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

        # Level 1: Liquidity filter (active trading pairs from CoinRegistry)
        active_coins = set(get_active_pairs())
        liquid_coins = [c for c in pattern_coins if c in active_coins]

        if not liquid_coins:
            logger.warning(f"Liquidity filter: 0/{len(pattern_coins)} coins liquid")
            return None, "no_liquid_coins"

        # Level 2: Cache filter (data must exist in cache)
        from src.backtester.cache_reader import BacktestCacheReader, CacheNotFoundError
        try:
            cache_reader = BacktestCacheReader(self.data_loader.cache_dir)
            cached_symbols = set(cache_reader.list_cached_symbols(timeframe))
        except CacheNotFoundError:
            return None, "cache_not_found"

        cached_coins = [c for c in liquid_coins if c in cached_symbols]

        if not cached_coins:
            logger.warning(f"Cache filter: 0/{len(liquid_coins)} coins cached")
            return None, "no_cached_coins"

        # Level 3: Coverage filter using UNIFIED scroll-down logic
        validated_coins, status = self._scroll_down_coverage(
            coins=cached_coins,
            timeframe=timeframe,
            target_count=self.max_coins
        )

        if not validated_coins:
            logger.warning(f"Coverage filter: {status} (from {len(cached_coins)} cached)")
            return None, status

        logger.info(
            f"Validated {len(validated_coins)} pattern coins "
            f"(from {len(pattern_coins)} edge-sorted, target: {self.max_coins})"
        )

        return validated_coins, "validated"

    def _get_is_oos_data(
        self,
        pairs: List[str],
        timeframe: str
    ) -> Tuple[Dict[str, any], Dict[str, any]]:
        """
        Get in-sample/out-of-sample data for multi-symbol backtesting

        Data is split into NON-OVERLAPPING periods:
        - In-sample (IS): older data for backtest metrics (120 days)
        - Out-of-sample (OOS): recent data for validation (30 days) - NEVER seen during IS

        Args:
            pairs: List of symbol names
            timeframe: Timeframe to load

        Returns:
            Tuple of (is_data_dict, oos_data_dict)
        """
        # Cache key includes pairs hash - different strategies have different pairs
        pairs_hash = hash(tuple(sorted(pairs)))
        is_cache_key = f"{timeframe}_{pairs_hash}_is"
        oos_cache_key = f"{timeframe}_{pairs_hash}_oos"

        # Check if both are cached
        if is_cache_key in self._data_cache and oos_cache_key in self._data_cache:
            return (
                self._data_cache[is_cache_key],
                self._data_cache[oos_cache_key]
            )

        try:
            is_data, oos_data = self.data_loader.load_multi_symbol_is_oos(
                symbols=pairs,
                timeframe=timeframe,
                is_days=self.is_days,
                oos_days=self.oos_days,
                target_count=self.max_coins  # Scroll through pairs to find 30 with valid data
            )

            self._data_cache[is_cache_key] = is_data
            self._data_cache[oos_cache_key] = oos_data

            logger.info(
                f"Loaded IS/OOS data for {timeframe}: "
                f"{len(is_data)} symbols ({self.is_days}d IS, {self.oos_days}d OOS)"
            )

            return is_data, oos_data

        except Exception as e:
            logger.error(f"Failed to load IS/OOS data for {timeframe}: {e}")
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
                            logger.info(f"[{strategy_name}] {future_type} completed: {reason}")
                        else:
                            logger.info(f"[{strategy_name}] {future_type} failed: {reason}")
                    except Exception as e:
                        logger.error(f"[{strategy_name}] {future_type} error: {e}")

            # NOTE: No backpressure on ACTIVE pool - pool_manager handles eviction.
            # When pool is full and new strategy is better, worst gets retired.
            # Backtester should always process, let pool_manager decide membership.

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
                    logger.info(f"[{strategy_data['name']}] RETEST started")
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
                        self._backtest_strategy,
                        strategy.id,
                        strategy.name,
                        strategy.code,
                        strategy.timeframe,
                        strategy.pattern_coins,
                        strategy.base_code_hash,  # Pass hash to detect pre-parametrized strategies
                        strategy.generation_mode  # Pass for robustness threshold selection
                    )
                    validated_futures[future] = (str(strategy.id), strategy.name)
                    await asyncio.sleep(0.1)
                    continue

            # Nothing to do, wait
            await asyncio.sleep(5)

        logger.info("Backtesting loop ended")

    def _backtest_strategy(
        self,
        strategy_id,
        strategy_name: str,
        code: str,
        original_tf: str,
        pattern_coins: Optional[List[str]] = None,
        base_code_hash: Optional[str] = None,
        generation_mode: str = "ai_free"
    ) -> Tuple[bool, str]:
        """
        Run training/holdout backtest on strategy's assigned timeframe.

        No multi-TF optimization: each strategy tests ONLY its assigned timeframe
        (original_tf). Parametric optimization explores SL/TP/leverage parameter
        space to find optimal settings.

        In-sample/Out-of-sample backtesting flow:
        1. Backtest on IN-SAMPLE period (config: is_days) - for edge detection
        2. Backtest on OUT-OF-SAMPLE period (config: oos_days) - NEVER seen during IS
        3. OOS serves TWO purposes:
           a) Anti-overfitting: if OOS crashes, strategy is overfitted
           b) Recency score: good OOS = strategy "in form" now
        4. Final score weighted: IS metrics + OOS performance

        Returns:
            (passed, reason) tuple
        """
        from src.database.event_tracker import EventTracker

        # Emit backtest started event and track timing
        EventTracker.backtest_started(
            strategy_id, strategy_name, original_tf, base_code_hash
        )
        backtest_start_time = time.time()

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

            # Single-TF backtest results (no multi-TF optimization)
            backtest_result = None
            backtest_id = None
            validated_coins_list = []  # Coins used for backtest
            optimal_params = None  # Optimal params from parametric optimization
            all_parametric_results = []  # ALL valid parametric results
            oos_data_stored = None  # OOS data for additional validation

            # Strategy tests ONLY its assigned timeframe (no multi-TF optimization)
            assigned_tf = original_tf
            use_parametric = True

            # Begin single-timeframe backtest (previously a loop over [original_tf])
            # Validate pattern coins for this timeframe (3-level validation)
            if pattern_coins:
                validated_coins, validation_reason = self._validate_pattern_coins(
                    pattern_coins, assigned_tf
                )
                if validated_coins is None:
                    self._delete_strategy(strategy_id, validation_reason)
                    return (False, f"Pattern coin validation failed: {validation_reason}")
                pairs = validated_coins
                logger.info(
                    f"[{strategy_name}] {assigned_tf}: Using {len(pairs)} validated pattern coins"
                )
            else:
                # Non-pattern strategy: use volume-based pairs with UNIFIED scroll-down
                pairs, status = self._get_backtest_pairs(assigned_tf)
                if not pairs:
                    self._delete_strategy(strategy_id, status)
                    return (False, f"No backtest pairs: {status}")

            logger.info(f"[{strategy_name}] Testing {assigned_tf} on {len(pairs)} pairs (IS/OOS)...")

            # Load in-sample/out-of-sample data (NON-OVERLAPPING)
            is_data, oos_data = self._get_is_oos_data(pairs, assigned_tf)

            if not is_data:
                self._delete_strategy(strategy_id, "No IS data")
                return (False, f"No IS data loaded for {assigned_tf}")

            # Store validated coins
            validated_coins_list = list(is_data.keys())

            # STEP 1: PARAMETRIC OPTIMIZATION (screening)
            # Tests ~1050 combinations, finds best combo, discards #2-1050
            try:
                is_pattern_based = pattern_coins is not None and len(pattern_coins) > 0

                if use_parametric:
                    # Initial parametric to find best combo
                    parametric_results = self._run_parametric_backtest(
                        strategy_instance, is_data, assigned_tf, is_pattern_based,
                        strategy_id=strategy_id, strategy_name=strategy_name,
                        generation_mode=generation_mode
                    )

                    if not parametric_results:
                        self._delete_strategy(strategy_id, "No params passed thresholds")
                        return (False, "No parametric combinations passed thresholds")

                    # Best combo from initial parametric
                    initial_best = parametric_results[0]
                    initial_params = initial_best.get('params', {})
                    logger.info(
                        f"[{strategy_name}] {assigned_tf}: Parametric found best combo: "
                        f"SL={initial_params.get('sl_pct', 0):.1%}, "
                        f"TP={initial_params.get('tp_pct', 0):.1%}, "
                        f"leverage={initial_params.get('leverage', 1)}, "
                        f"exit_bars={initial_params.get('exit_bars', 0)}"
                    )

                    # Store for combinations_tested metric
                    all_parametric_results = parametric_results

                    # Apply best params from parametric to strategy instance
                    strategy_instance.sl_pct = initial_params.get('sl_pct', 0.02)
                    strategy_instance.tp_pct = initial_params.get('tp_pct', 0.03)
                    strategy_instance.leverage = initial_params.get('leverage', 1)
                    strategy_instance.exit_after_bars = initial_params.get('exit_bars', 0)

                    # STEP 2: Final IS backtest with best params for metrics
                    is_result = self._run_multi_symbol_backtest(
                        strategy_instance, is_data, assigned_tf
                    )

                else:
                    # Standard: use strategy's original parameters (no WFA)
                    is_result = self._run_multi_symbol_backtest(
                        strategy_instance, is_data, assigned_tf
                    )
                    optimal_params = None

            except Exception as e:
                self._delete_strategy(strategy_id, f"IS backtest failed: {e}")
                return (False, f"IS backtest failed for {assigned_tf}: {e}")

            if is_result is None or is_result.get('total_trades', 0) == 0:
                self._delete_strategy(strategy_id, "No trades in IS")
                return (False, f"No trades in IS period for {assigned_tf}")

            # Run OUT-OF-SAMPLE period backtest (validation)
            # Use min_bars=20 for OOS (30 days on 1d = only 30 bars)
            oos_result = None
            try:
                if oos_data and len(oos_data) >= 5:
                    oos_result = self._run_multi_symbol_backtest(
                        strategy_instance, oos_data, assigned_tf,
                        min_bars=20  # Lower threshold for OOS period
                    )
            except Exception as e:
                logger.warning(f"OOS backtest failed for {assigned_tf}: {e}")
                oos_result = None

            # Validate OOS and calculate final metrics
            validation = self._validate_oos(is_result, oos_result, assigned_tf)

            if not validation['passed']:
                self._delete_strategy(strategy_id, validation['reason'])
                return (False, f"OOS validation failed: {validation['reason']}")

            # Combine IS + OOS into final result
            final_result = self._calculate_final_metrics(
                is_result, oos_result, validation
            )

            backtest_result = final_result

            # Store parametric results if available (for combinations_tested metric)
            if parametric_results:
                all_parametric_results = parametric_results

            # Store OOS data (needed for additional parametric validation)
            oos_data_stored = oos_data

            # Save in-sample backtest result
            is_backtest_id = self._save_backtest_result(
                strategy_id, is_result, pairs, assigned_tf,
                period_type='in_sample',
                period_days=self.is_days
            )

            # Save out-of-sample backtest result (ALWAYS save, even with 0 trades)
            # 0 trades is DATA (pattern dormant in recent period), not failure
            oos_backtest_id = None
            if oos_result:
                oos_backtest_id = self._save_backtest_result(
                    strategy_id, oos_result, pairs, assigned_tf,
                    period_type='out_of_sample',
                    period_days=self.oos_days
                )

                # Link IS result to OOS and add validation metrics
                self._update_is_with_oos(
                    is_backtest_id,
                    oos_backtest_id,
                    final_result
                )

            backtest_id = is_backtest_id

            oos_trades = oos_result.get('total_trades', 0) if oos_result else 0
            oos_sharpe = oos_result.get('sharpe_ratio', 0) if oos_result else 0
            logger.info(
                f"[{strategy_name}] {assigned_tf}: "
                f"IS: {is_result['total_trades']} trades, Sharpe {is_result.get('sharpe_ratio', 0):.2f} | "
                f"OOS: {oos_trades} trades, Sharpe {oos_sharpe:.2f} | "
                f"Final Score: {final_result.get('final_score', 0):.2f}"
            )

            # assigned_tf already set from original_tf (no multi-TF optimization)
            # All threshold checks done above with early returns

            # Get validated coins (these are the coins to use in live trading)
            assigned_tf_coins = validated_coins_list

            # Get optimal params (from parametric backtest)
            optimal_params_for_tf = optimal_params

            # Update strategy with assigned TF, validated coins, and optimal params
            self._update_strategy_assigned_tf(
                strategy_id, assigned_tf, assigned_tf_coins, optimal_params_for_tf
            )

            # NOTE: WFA with parameter re-optimization is now done BEFORE OOS validation
            # (see _run_wfa_with_optimization call above)
            # Old WFA stability measurement removed - param stability is checked during WFA

            # Promote best combo to ACTIVE pool using leaderboard logic
            # NOTE: N-1 additional strategies path removed - only best combo proceeds
            # This ensures 1 base code → 1 validated strategy (diversified pool)
            if backtest_id:
                # Get backtest result for scoring (eager load strategy to avoid detached session issues)
                with get_session() as session:
                    db_backtest = session.query(BacktestResult).options(
                        joinedload(BacktestResult.strategy)
                    ).filter(
                        BacktestResult.id == backtest_id
                    ).first()

                    if db_backtest:
                        # Get degradation for recency bonus
                        degradation = backtest_result.get('degradation', 0.0)

                        # Get combinations_tested and robustness from parametric results (if parametric was used)
                        combinations = all_parametric_results[0].get('combinations_tested') if all_parametric_results else None
                        robustness = all_parametric_results[0].get('robustness_score', 0.5) if all_parametric_results else 0.5

                        # Try to enter ACTIVE pool (handles leaderboard logic)
                        entered, pool_reason = self._promote_to_active_pool(
                            strategy_id, db_backtest, backtest_start_time, degradation,
                            combinations_tested=combinations,
                            robustness_score=robustness
                        )

                        if entered:
                            # Update last_backtested_at
                            strategy = session.query(Strategy).filter(
                                Strategy.id == strategy_id
                            ).first()
                            if strategy:
                                strategy.last_backtested_at = datetime.now(UTC)
                                session.commit()

                            return (
                                True,
                                f"Entered ACTIVE pool: {pool_reason}, "
                                f"TF={assigned_tf}, Score={backtest_result.get('final_score', 0):.1f}"
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
            logger.error(f"[{strategy_name}] Backtest error: {e}", exc_info=True)
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
        is_pattern_based: bool = False,
        strategy_id=None,
        strategy_name: str = None,
        generation_mode: str = "ai_free"
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
            strategy_id: Strategy UUID for event tracking
            strategy_name: Strategy name for event tracking

        Returns:
            List of top K results with different parameters
        """
        import numpy as np

        # Track timing for metrics
        parametric_start_time = time.time()

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
            logger.info(f"[{strategy_name}] No entry signals found for parametric backtest")
            return []

        logger.info(
            f"[{strategy_name}] Running parametric: {n_bars} bars, {n_symbols} symbols, "
            f"{total_signals} signals, {self.parametric_backtester._count_strategies()} candidates"
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
                strategy_name=strategy_name,
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

        # Track total combinations tested (for metrics)
        combinations_tested = len(results_df)

        # Get parameter space for robustness calculation
        param_space = self.parametric_backtester.parameter_space

        # Convert to list of dicts matching expected format
        # Use float() to convert np.float64 to native Python float (required for DB)
        # Calculate robustness and filter if enabled
        results = []
        robustness_rejected = 0
        for _, row in valid_results.iterrows():
            params = {
                'sl_pct': float(row['sl_pct']),
                'tp_pct': float(row['tp_pct']),
                'leverage': int(row['leverage']),
                'exit_bars': int(row['exit_bars']),
            }

            # Calculate robustness for this parameter set
            if self.robustness_enabled:
                robustness_score = self._calculate_robustness_from_neighbors(
                    results_df, params, param_space
                )

                # Get threshold based on generation_mode
                threshold = self.robustness_thresholds.get(generation_mode, 0.50)

                # Filter by robustness threshold
                if robustness_score < threshold:
                    robustness_rejected += 1
                    logger.debug(
                        f"[{strategy_name}] Combo rejected by robustness: "
                        f"score={robustness_score:.2f} < threshold={threshold:.0%} "
                        f"(mode={generation_mode})"
                    )
                    continue
            else:
                robustness_score = 0.5  # Neutral default when disabled

            result = {
                'sharpe_ratio': float(row['sharpe']),
                'max_drawdown': float(row['max_drawdown']),
                'win_rate': float(row['win_rate']),
                'expectancy': float(row['expectancy']),
                'total_trades': int(row['total_trades']),
                'total_return': float(row['total_return']),
                'parametric_score': float(row['score']),
                'robustness_score': robustness_score,
                # Store the parameters used
                'params': params,
                # Track combinations tested (same for all results from this base strategy)
                'combinations_tested': combinations_tested,
            }
            results.append(result)

        # Log robustness filtering if any were rejected
        if robustness_rejected > 0:
            threshold = self.robustness_thresholds.get(generation_mode, 0.50)
            logger.info(
                f"[{strategy_name}] Robustness filter ({generation_mode}): {robustness_rejected} rejected "
                f"(threshold={threshold:.0%}), {len(results)} passed"
            )

        if results:
            best = results[0]
            logger.info(
                f"[{strategy_name}] Parametric: {len(results)} strategies | "
                f"Best: Sharpe={best['sharpe_ratio']:.2f}, Trades={best['total_trades']}, "
                f"Robustness={best['robustness_score']:.2f}, "
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
                    f"[{strategy_name}] Parametric: 0/{n_tested} passed | "
                    f"Best: Sharpe={best_sharpe:.2f} (need {self.min_sharpe}), "
                    f"WR={best_wr:.1%} (need {self.min_win_rate:.1%}), "
                    f"Trades={max_trades} (need {self.min_trades}), "
                    f"Exp={best_expectancy:.4f} (need {self.min_expectancy}), "
                    f"DD={min_dd:.1%} (need <{self.max_drawdown:.0%})"
                )

                # DEBUG: Show failure breakdown per threshold
                pass_sharpe = (results_df['sharpe'] >= self.min_sharpe).sum()
                pass_wr = (results_df['win_rate'] >= self.min_win_rate).sum()
                pass_trades = (results_df['total_trades'] >= self.min_trades).sum()
                pass_exp = (results_df['expectancy'] >= self.min_expectancy).sum()
                pass_dd = (results_df['max_drawdown'] <= self.max_drawdown).sum()
                logger.info(
                    f"[{strategy_name}]   Breakdown: Sharpe>={self.min_sharpe}: {pass_sharpe}/{n_tested}, "
                    f"WR>={self.min_win_rate:.0%}: {pass_wr}/{n_tested}, "
                    f"Trades>={self.min_trades}: {pass_trades}/{n_tested}, "
                    f"Exp>=0: {pass_exp}/{n_tested}, "
                    f"DD<={self.max_drawdown:.0%}: {pass_dd}/{n_tested}"
                )

                # DEBUG: Show top 5 combos by score and why they fail
                top5 = results_df.nlargest(5, 'score')
                for idx, row in top5.iterrows():
                    fails = []
                    if row['sharpe'] < self.min_sharpe:
                        fails.append(f"Sharpe={row['sharpe']:.2f}")
                    if row['win_rate'] < self.min_win_rate:
                        fails.append(f"WR={row['win_rate']:.1%}")
                    if row['total_trades'] < self.min_trades:
                        fails.append(f"Trades={row['total_trades']}")
                    if row['expectancy'] < self.min_expectancy:
                        fails.append(f"Exp={row['expectancy']:.4f}")
                    if row['max_drawdown'] > self.max_drawdown:
                        fails.append(f"DD={row['max_drawdown']:.1%}")
                    fail_str = ", ".join(fails) if fails else "ALL PASS?"
                    logger.info(
                        f"[{strategy_name}]   Top: SL={row['sl_pct']:.1%} TP={row['tp_pct']:.1%} "
                        f"Lev={row['leverage']} Exit={row['exit_bars']} | "
                        f"Score={row['score']:.1f} Sharpe={row['sharpe']:.2f} "
                        f"WR={row['win_rate']:.1%} Trades={row['total_trades']} | FAILS: {fail_str}"
                    )

                # Emit event for metrics tracking
                if strategy_id and strategy_name:
                    from src.database.event_tracker import EventTracker
                    duration_ms = int((time.time() - parametric_start_time) * 1000)
                    EventTracker.backtest_parametric_failed(
                        strategy_id=strategy_id,
                        strategy_name=strategy_name,
                        timeframe=timeframe,
                        reason="no_params_passed_thresholds",
                        best_sharpe=float(best_sharpe),
                        best_win_rate=float(best_wr),
                        combinations_tested=n_tested,
                        duration_ms=duration_ms
                    )

        return results

    def _calculate_robustness_from_neighbors(
        self,
        all_results: pd.DataFrame,
        best_params: dict,
        param_space: dict
    ) -> float:
        """
        Calculate robustness as fraction of neighbors that pass min_sharpe threshold.

        Neighbors are parameter combinations with ONE dimension different (adjacent in grid).
        This approach counts how many neighbors are "good enough" in absolute terms,
        rather than comparing to the best (which penalizes strategies with high best).

        Example:
            - Best has Sharpe 3.0, neighbors have [1.5, 1.2, 0.8, 1.4, 0.9, 1.1, 1.3, 0.7]
            - If min_sharpe = 0.3, then 8/8 neighbors pass → robustness = 1.0
            - Old method: avg(neighbors)/best = 1.1/3.0 = 0.37 (would barely pass!)

        Args:
            all_results: DataFrame with ALL parametric results (sorted by score desc)
            best_params: Dict with best parameter values {sl_pct, tp_pct, leverage, exit_bars}
            param_space: Dict with parameter grids {sl_pct: [...], tp_pct: [...], ...}

        Returns:
            Robustness score [0.0, 1.0] = fraction of neighbors passing min_sharpe
        """
        # Get best Sharpe
        best_sharpe = all_results.iloc[0]['sharpe']
        if best_sharpe <= 0:
            return 0.0  # No edge = not robust

        # Get grid values
        sl_values = param_space.get('sl_pct', [])
        tp_values = param_space.get('tp_pct', [])
        lev_values = param_space.get('leverage', [])
        exit_values = param_space.get('exit_bars', [])

        # Find indices of best params in grids
        try:
            best_sl_idx = sl_values.index(best_params['sl_pct'])
            best_tp_idx = tp_values.index(best_params['tp_pct'])
            best_lev_idx = lev_values.index(best_params['leverage'])
            best_exit_idx = exit_values.index(best_params['exit_bars'])
        except (ValueError, KeyError):
            # Param not in grid (shouldn't happen) - return neutral
            return 0.5

        # Build neighbor parameter sets (ONE dimension different, adjacent)
        neighbor_sharpes = []

        # SL neighbors
        for delta in [-1, 1]:
            idx = best_sl_idx + delta
            if 0 <= idx < len(sl_values):
                match = all_results[
                    (all_results['sl_pct'] == sl_values[idx]) &
                    (all_results['tp_pct'] == best_params['tp_pct']) &
                    (all_results['leverage'] == best_params['leverage']) &
                    (all_results['exit_bars'] == best_params['exit_bars'])
                ]
                if not match.empty:
                    neighbor_sharpes.append(match.iloc[0]['sharpe'])

        # TP neighbors
        for delta in [-1, 1]:
            idx = best_tp_idx + delta
            if 0 <= idx < len(tp_values):
                match = all_results[
                    (all_results['sl_pct'] == best_params['sl_pct']) &
                    (all_results['tp_pct'] == tp_values[idx]) &
                    (all_results['leverage'] == best_params['leverage']) &
                    (all_results['exit_bars'] == best_params['exit_bars'])
                ]
                if not match.empty:
                    neighbor_sharpes.append(match.iloc[0]['sharpe'])

        # Leverage neighbors
        for delta in [-1, 1]:
            idx = best_lev_idx + delta
            if 0 <= idx < len(lev_values):
                match = all_results[
                    (all_results['sl_pct'] == best_params['sl_pct']) &
                    (all_results['tp_pct'] == best_params['tp_pct']) &
                    (all_results['leverage'] == lev_values[idx]) &
                    (all_results['exit_bars'] == best_params['exit_bars'])
                ]
                if not match.empty:
                    neighbor_sharpes.append(match.iloc[0]['sharpe'])

        # Exit bars neighbors
        for delta in [-1, 1]:
            idx = best_exit_idx + delta
            if 0 <= idx < len(exit_values):
                match = all_results[
                    (all_results['sl_pct'] == best_params['sl_pct']) &
                    (all_results['tp_pct'] == best_params['tp_pct']) &
                    (all_results['leverage'] == best_params['leverage']) &
                    (all_results['exit_bars'] == exit_values[idx])
                ]
                if not match.empty:
                    neighbor_sharpes.append(match.iloc[0]['sharpe'])

        if not neighbor_sharpes:
            # No neighbors found (edge case) - return neutral
            return 0.5

        # Count neighbors that pass min_sharpe threshold
        neighbors_passing = sum(1 for s in neighbor_sharpes if s >= self.min_sharpe)
        total_neighbors = len(neighbor_sharpes)

        # Robustness = fraction of neighbors that are "good enough"
        robustness = neighbors_passing / total_neighbors

        return robustness

    def _validate_oos(
        self,
        is_result: Dict,
        oos_result: Optional[Dict],
        timeframe: str
    ) -> Dict:
        """
        Validate out-of-sample performance for anti-overfitting check

        OOS validation serves TWO purposes:
        1. Anti-overfitting: reject if OOS crashes vs IS
        2. Recency: good OOS = strategy in form now

        CRITICAL: IS must have positive Sharpe first - if IS Sharpe
        is negative or below threshold, strategy has no edge regardless of OOS.

        Args:
            is_result: In-sample period backtest results
            oos_result: Out-of-sample period backtest results
            timeframe: Strategy timeframe for min_trades lookup

        Returns:
            Dict with 'passed', 'reason', 'degradation', 'oos_bonus'
        """
        is_sharpe = is_result.get('sharpe_ratio', 0)
        is_trades = is_result.get('total_trades', 0)

        # Get min trades for this timeframe
        min_is = self.min_trades_is.get(timeframe, 300)
        min_oos = self.min_trades_oos.get(timeframe, 30)

        # CRITICAL: IS must have enough trades for statistical significance
        if is_trades < min_is:
            return {
                'passed': False,
                'reason': f'IS trades insufficient: {is_trades} < {min_is} (for {timeframe})',
                'degradation': 0.0,
                'oos_bonus': 0.0,
            }

        # CRITICAL: IS must show edge first
        # If IS Sharpe is negative, strategy has no edge - reject early
        if is_sharpe < self.min_sharpe:
            return {
                'passed': False,
                'reason': f'IS Sharpe too low: {is_sharpe:.2f} < {self.min_sharpe}',
                'degradation': 0.0,
                'oos_bonus': 0.0,
            }

        # Check OOS trades - REJECT if below minimum (no longer just penalty)
        oos_trades = oos_result.get('total_trades', 0) if oos_result else 0
        if oos_trades < min_oos:
            return {
                'passed': False,
                'reason': f'OOS trades insufficient: {oos_trades} < {min_oos} (for {timeframe})',
                'degradation': 0.0,
                'oos_bonus': 0.0,
            }

        oos_sharpe = oos_result.get('sharpe_ratio', 0)

        # Calculate degradation (how much worse is OOS vs IS)
        # Guard against division by zero when is_sharpe is exactly 0
        if is_sharpe == 0:
            # No edge in IS = cannot calculate degradation meaningfully
            # Treat as neutral (no degradation, no bonus)
            degradation = 0.0
        else:
            degradation = (is_sharpe - oos_sharpe) / is_sharpe

        # Anti-overfitting check: reject if OOS crashes vs IS
        if degradation > self.oos_max_degradation:
            return {
                'passed': False,
                'reason': f'Overfitted: OOS {degradation:.0%} worse than IS',
                'degradation': degradation,
                'oos_bonus': 0.0,
            }

        # Check minimum OOS Sharpe (must also show edge in recent period)
        if oos_sharpe < self.oos_min_sharpe:
            return {
                'passed': False,
                'reason': f'OOS Sharpe too low: {oos_sharpe:.2f} < {self.oos_min_sharpe}',
                'degradation': degradation,
                'oos_bonus': 0.0,
            }

        # Calculate OOS bonus (good OOS = higher final score)
        # Bonus is positive if OOS >= IS, zero if worse
        if degradation <= 0:
            # OOS better than IS = big bonus
            oos_bonus = min(0.20, abs(degradation) * 0.5)
        else:
            # OOS worse but within tolerance = small penalty
            oos_bonus = -degradation * 0.10

        return {
            'passed': True,
            'reason': 'OOS validated',
            'degradation': degradation,
            'oos_bonus': oos_bonus,
        }

    def _calculate_final_metrics(
        self,
        is_result: Dict,
        oos_result: Optional[Dict],
        validation: Dict
    ) -> Dict:
        """
        Calculate final metrics combining in-sample and out-of-sample

        Final score formula:
        - Base score from IS metrics
        - Weighted by OOS performance (recency_weight)
        - Adjusted by OOS bonus/penalty

        Returns:
            Dict with all metrics + final_score
        """
        is_sharpe = is_result.get('sharpe_ratio', 0)
        is_win_rate = is_result.get('win_rate', 0)
        is_expectancy = is_result.get('expectancy', 0)
        is_max_drawdown = is_result.get('max_drawdown', 0)

        # Calculate IS base score
        # Bug fix: expectancy is already a percentage from backtest_engine.py
        # No division needed - dividing by initial_capital was corrupting the metric
        is_expectancy_pct = is_expectancy

        is_score = (
            0.5 * is_sharpe +
            0.3 * is_expectancy_pct +
            0.2 * is_win_rate
        )

        # Get OOS metrics
        if oos_result and oos_result.get('total_trades', 0) > 0:
            oos_sharpe = oos_result.get('sharpe_ratio', 0)
            oos_win_rate = oos_result.get('win_rate', 0)
            oos_expectancy = oos_result.get('expectancy', 0)
            oos_max_drawdown = oos_result.get('max_drawdown', 0)

            # Bug fix: expectancy is already a percentage
            oos_expectancy_pct = oos_expectancy
            oos_score = (
                0.5 * oos_sharpe +
                0.3 * oos_expectancy_pct +
                0.2 * oos_win_rate
            )
        else:
            oos_sharpe = 0
            oos_win_rate = 0
            oos_expectancy = 0
            oos_max_drawdown = is_max_drawdown  # Use IS if no OOS
            oos_expectancy_pct = 0  # Bug fix: must be defined for weighted calculation
            oos_score = is_score  # Neutral if no OOS

        # Calculate weighted final score
        # OOS has higher weight because it represents "now"
        is_weight = 1 - self.oos_recency_weight
        final_score = (
            is_score * is_weight +
            oos_score * self.oos_recency_weight
        )

        # Apply OOS bonus/penalty
        oos_bonus = validation.get('oos_bonus', 0)
        final_score = final_score * (1 + oos_bonus)

        # Calculate weighted metrics for classifier (IS 40% + OOS 60%)
        # Each metric weighted individually (not composite) for accurate classification
        weighted_sharpe_pure = (is_sharpe * 0.4) + (oos_sharpe * 0.6) if oos_sharpe is not None else is_sharpe
        weighted_expectancy = (is_expectancy_pct * 0.4) + (oos_expectancy_pct * 0.6) if oos_expectancy_pct is not None else is_expectancy_pct
        weighted_win_rate = (is_win_rate * 0.4) + (oos_win_rate * 0.6) if oos_win_rate is not None else is_win_rate
        weighted_max_drawdown = (is_max_drawdown * 0.4) + (oos_max_drawdown * 0.6)

        # Walk-forward stability: check if available from optimization
        weighted_walk_forward_stability = is_result.get('walk_forward_stability')

        return {
            **is_result,
            # In-sample metrics
            'is_sharpe': is_sharpe,
            'is_win_rate': is_win_rate,
            'is_expectancy': is_expectancy,
            'is_score': is_score,
            # Out-of-sample metrics
            'oos_sharpe': oos_sharpe,
            'oos_win_rate': oos_win_rate,
            'oos_expectancy': oos_expectancy,
            'oos_score': oos_score,
            'oos_trades': oos_result.get('total_trades', 0) if oos_result else 0,
            # Validation metrics
            'degradation': validation.get('degradation', 0),
            'oos_bonus': oos_bonus,
            # Final score
            'final_score': final_score,
            # Individual weighted metrics for classifier
            'weighted_sharpe_pure': weighted_sharpe_pure,
            'weighted_expectancy': weighted_expectancy,
            'weighted_win_rate': weighted_win_rate,
            'weighted_walk_forward_stability': weighted_walk_forward_stability,
            'weighted_max_drawdown': weighted_max_drawdown,
        }

    def _update_is_with_oos(
        self,
        is_backtest_id: str,
        oos_backtest_id: str,
        final_result: Dict
    ):
        """
        Update in-sample backtest result with OOS reference and final metrics
        """
        if not is_backtest_id:
            return

        try:
            with get_session() as session:
                bt = session.query(BacktestResult).filter(
                    BacktestResult.id == is_backtest_id
                ).first()

                if bt:
                    # Link to OOS result (even if 0 trades)
                    if oos_backtest_id:
                        bt.recent_result_id = oos_backtest_id

                    # Store final metrics (ALWAYS - final_result exists even with 0 OOS trades)
                    # FAST FAIL: If final_score is None, crash (indicates bug in _calculate_final_metrics)
                    final_score = final_result.get('final_score')
                    if final_score is None:
                        raise ValueError(
                            f"final_score is None for IS backtest {is_backtest_id} "
                            f"(oos_id={oos_backtest_id}). "
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
                    bt.recency_penalty = -final_result.get('oos_bonus', 0)

                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update IS result with OOS: {e}")

    # NOTE: _run_walk_forward_analysis and _update_backtest_with_walkforward removed
    # Replaced by _run_wfa_with_optimization which does parameter re-optimization
    # and checks parameter stability across windows (not just edge stability)

    def _slice_data_by_percentage(
        self,
        data: Dict[str, pd.DataFrame],
        percentage: float
    ) -> Dict[str, pd.DataFrame]:
        """
        Slice data from beginning up to percentage of total length.

        Args:
            data: Dict mapping symbol -> DataFrame
            percentage: Fraction of data to include (0.25, 0.50, 0.75, 1.0)

        Returns:
            Dict with sliced DataFrames
        """
        sliced = {}
        for symbol, df in data.items():
            n_rows = int(len(df) * percentage)
            if n_rows > 0:
                sliced[symbol] = df.iloc[:n_rows].copy()
        return sliced

    def _run_wfa_fixed_params(
        self,
        strategy: 'Strategy',
        timeframe: str
    ) -> Tuple[bool, str]:
        """
        Walk-Forward Validation with FIXED parameters.

        Tests if the best combo (already embedded in strategy code after parametric)
        performs consistently across 4 expanding time windows.

        This is different from the old WFA which re-optimized parameters per window.
        Here we test if the SAME parameters work across different historical periods.

        Args:
            strategy: Strategy model with embedded parameters
            timeframe: Timeframe to test

        Returns:
            (passed: bool, reason: str)
        """
        try:
            # Get WFA validation config
            wfa_config = self.config._raw_config['backtesting'].get('wfa_validation', {})
            if not wfa_config.get('enabled', True):
                logger.debug(f"[{strategy.name}] WFA validation disabled, skipping")
                return (True, "wfa_disabled")

            window_percentages = wfa_config.get('window_percentages', [0.25, 0.50, 0.75, 1.0])
            min_profitable_windows = wfa_config.get('min_profitable_windows', 4)

            # Load strategy instance (has fixed params embedded)
            strategy_instance = self._load_strategy(strategy)
            if strategy_instance is None:
                return (False, "failed_to_load_strategy")

            # Load IS data for this timeframe
            is_data = self.data_loader.load_multi_symbol(
                symbols=self.symbols,
                timeframe=timeframe,
                days=self.is_days
            )

            if not is_data:
                return (False, "no_is_data")

            # Get min_expectancy threshold from config
            min_expectancy = self.config._raw_config['backtesting']['thresholds'].get(
                'min_expectancy', 0.002
            )

            profitable_windows = 0
            window_results = []

            logger.info(
                f"[{strategy.name}] WFA validation: testing fixed params on "
                f"{len(window_percentages)} windows"
            )

            for window_idx, window_pct in enumerate(window_percentages):
                # Slice data for this window
                window_data = self._slice_data_by_percentage(is_data, window_pct)

                if not window_data:
                    logger.warning(
                        f"[{strategy.name}] WFA window {window_idx+1}: no data at {window_pct:.0%}"
                    )
                    continue

                # Run backtest with FIXED params (no re-optimization)
                result = self._run_multi_symbol_backtest(
                    strategy_instance, window_data, timeframe, min_bars=20
                )

                if result is None:
                    logger.warning(
                        f"[{strategy.name}] WFA window {window_idx+1}: backtest failed"
                    )
                    continue

                window_expectancy = result.get('expectancy', 0)
                is_profitable = window_expectancy >= min_expectancy

                if is_profitable:
                    profitable_windows += 1

                window_results.append({
                    'window': window_idx + 1,
                    'pct': window_pct,
                    'expectancy': window_expectancy,
                    'profitable': is_profitable
                })

                logger.info(
                    f"[{strategy.name}] WFA window {window_idx+1}/{len(window_percentages)}: "
                    f"{window_pct:.0%} data, expectancy={window_expectancy:.4f}, "
                    f"profitable={'YES' if is_profitable else 'NO'}"
                )

            # Check if enough windows are profitable
            n_windows = len(window_percentages)
            if profitable_windows < min_profitable_windows:
                logger.info(
                    f"[{strategy.name}] WFA FAILED: only {profitable_windows}/{n_windows} "
                    f"windows profitable (need {min_profitable_windows})"
                )
                return (False, f"insufficient_profitable_windows:{profitable_windows}/{n_windows}")

            logger.info(
                f"[{strategy.name}] WFA PASSED: {profitable_windows}/{n_windows} windows profitable"
            )
            return (True, f"wfa_passed:{profitable_windows}/{n_windows}")

        except Exception as e:
            logger.error(f"[{strategy.name}] WFA validation error: {e}")
            import traceback
            traceback.print_exc()
            return (False, f"error:{str(e)}")

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
        period_type: str = 'training',
        period_days: Optional[int] = None
    ) -> Optional[str]:
        """
        Save backtest results to database.

        Note: is_assigned_tf is always True because each strategy has exactly
        one assigned timeframe (no TF optimization).

        Args:
            strategy_id: Strategy UUID
            result: Backtest metrics dictionary
            pairs: List of symbols tested
            timeframe: Timeframe tested
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
                    period_days = self.is_days if period_type == 'in_sample' else self.oos_days

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
                    is_assigned_tf=True,  # Always True - each strategy has one assigned TF
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

    def _update_strategy_assigned_tf(
        self,
        strategy_id,
        assigned_tf: str,
        pairs: List[str],
        optimal_params: Optional[Dict] = None
    ):
        """
        Update strategy with assigned TF, pairs, and parameters from parametric backtest.

        If optimal_params is provided (from parametric backtest), updates the strategy's
        sl_pct, tp_pct, leverage, and exit_after_bars in the code.

        Args:
            strategy_id: Strategy UUID
            assigned_tf: Best performing timeframe
            pairs: Validated coins for this timeframe
            optimal_params: Dict with sl_pct, tp_pct, leverage, exit_bars (from parametric)
        """
        try:
            with get_session() as session:
                strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if strategy:
                    strategy.optimal_timeframe = assigned_tf
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
                        f"[{strategy.name}] Updated: "
                        f"assigned_tf={assigned_tf}, pairs={len(pairs)}{params_str}"
                    )
        except Exception as e:
            logger.error(f"Failed to update strategy: {e}")

    # NOTE: _create_parametric_strategy removed - N-1 strategies path eliminated
    # Now only best combo proceeds, no creation of additional strategies

    def _update_strategy_params(
        self, code: str, params: Dict, new_class_name: str = None
    ) -> Optional[str]:
        """
        Update strategy class attributes with optimal parameters from parametric backtest.

        Replaces the class-level sl_pct, tp_pct, leverage, exit_after_bars with
        the values found during parametric optimization. Optionally renames the class.

        Args:
            code: Strategy source code
            params: Dict with sl_pct, tp_pct, leverage, exit_bars
            new_class_name: If provided, rename the class to this name

        Returns:
            Updated code or None if update failed
        """
        import re

        try:
            updated = code

            # Rename class if new name provided
            if new_class_name:
                updated = re.sub(
                    r'class\s+((?:Strategy|PatStrat)_\w+)\s*\(',
                    f'class {new_class_name}(',
                    updated
                )

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

    def _extract_class_name(self, code: str) -> Optional[str]:
        """Extract class name from strategy code (supports Strategy_ and PatStrat_)"""
        import re
        match = re.search(r'class\s+((?:Strategy|PatStrat)_\w+)\s*\(', code)
        return match.group(1) if match else None

    def _load_strategy_instance(self, code: str, class_name: str):
        """Load strategy instance from code"""
        temp_path = None
        try:
            # Check if code is valid
            if not code or len(code.strip()) < 50:
                logger.warning(f"[{class_name}] Code is empty or too short ({len(code) if code else 0} chars)")
                return None

            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_path = f.name

            spec = importlib.util.spec_from_file_location(
                f"temp_{class_name}",
                temp_path
            )

            if not spec or not spec.loader:
                logger.warning(f"[{class_name}] Could not create module spec")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            if hasattr(module, class_name):
                cls = getattr(module, class_name)
                return cls()
            else:
                # Log available classes in module
                available = [name for name in dir(module) if not name.startswith('_')]
                logger.warning(f"[{class_name}] Class not found in module. Available: {available[:5]}")
                return None

        except Exception as e:
            logger.warning(f"[{class_name}] Load failed: {type(e).__name__}: {e}")
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
        assigned_tf: str,
        pairs: List[str]
    ) -> Tuple[bool, str]:
        """
        Re-backtest an ACTIVE strategy on its assigned TF only.

        Simplified version of _backtest_strategy:
        - Only tests assigned TF (not all 6 TFs)
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
            logger.info(f"[{strategy_name}] RETEST: Starting on {assigned_tf}")

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
                timeframe=assigned_tf,
                target_count=self.max_coins
            )

            if validated_pairs is None:
                logger.warning(f"[{strategy_name}] RETEST: pairs validation failed ({status})")
                # Mark strategy for retirement (data quality degraded)
                self.pool_manager._retire_strategy(
                    strategy_id,
                    f"Re-test failed: {status}"
                )
                return (False, f"Pair validation failed: {status}")

            # Load IS/OOS data
            is_data, oos_data = self._get_is_oos_data(
                validated_pairs, assigned_tf
            )

            if not is_data:
                logger.warning(f"[{strategy_name}] RETEST: no IS data loaded")
                return (False, "No IS data")

            # Run IS backtest (no parametric - use existing params)
            is_result = self._run_multi_symbol_backtest(
                strategy_instance, is_data, assigned_tf
            )

            if is_result is None or is_result.get('total_trades', 0) == 0:
                logger.warning(f"[{strategy_name}] RETEST: no trades in IS")
                return (False, "No trades in IS period")

            # Run OOS backtest (min_bars=20 for 1d timeframe support)
            oos_result = None
            if oos_data and len(oos_data) >= 5:
                oos_result = self._run_multi_symbol_backtest(
                    strategy_instance, oos_data, assigned_tf,
                    min_bars=20  # Lower threshold for OOS period
                )

            # Validate OOS
            validation = self._validate_oos(is_result, oos_result, assigned_tf)

            if not validation['passed']:
                logger.info(f"[{strategy_name}] RETEST: OOS failed ({validation['reason']})")
                self.pool_manager._retire_strategy(strategy_id, f"Re-test OOS: {validation['reason']}")
                return (False, f"OOS validation failed: {validation['reason']}")

            # Calculate final metrics
            final_result = self._calculate_final_metrics(
                is_result, oos_result, validation
            )

            # Calculate new score using SCORER
            new_score = self.scorer.score({
                'expectancy': final_result.get('weighted_expectancy', 0),
                'sharpe_ratio': final_result.get('weighted_sharpe_pure', 0),
                'win_rate': final_result.get('weighted_win_rate', 0),
                'wf_stability': final_result.get('weighted_walk_forward_stability', 1.0),
            })

            logger.info(
                f"[{strategy_name}] RETEST: new_score={new_score:.1f} "
                f"(sharpe={final_result.get('weighted_sharpe_pure', 0):.2f})"
            )

            # Update backtest result (save new metrics)
            self._save_backtest_result(
                strategy_id, is_result, validated_pairs, assigned_tf,
                period_type='in_sample', period_days=self.is_days
            )

            # Revalidate pool membership with new score
            still_active, reason = self.pool_manager.revalidate_after_retest(
                strategy_id, new_score
            )

            if still_active:
                logger.info(f"[{strategy_name}] RETEST: PASSED - {reason}")
                return (True, reason)
            else:
                logger.info(f"[{strategy_name}] RETEST: RETIRED - {reason}")
                return (False, reason)

        except Exception as e:
            logger.error(f"[{strategy_name}] RETEST error: {e}", exc_info=True)
            return (False, str(e))

    def _promote_to_active_pool(
        self,
        strategy_id: UUID,
        backtest_result: BacktestResult,
        backtest_start_time: Optional[float] = None,
        degradation: float = 0.0,
        combinations_tested: Optional[int] = None,
        robustness_score: float = 0.5
    ) -> Tuple[bool, str]:
        """
        Attempt to promote a strategy to the ACTIVE pool after backtest.

        Flow:
        1. Calculate score from backtest result (6-component formula)
        2. If score < min_score -> reject (no shuffle test needed)
        3. Run shuffle test (cached by base_code_hash)
        4. If shuffle fails -> reject
        5. Run WFA validation with fixed params (NOT cached - per-strategy)
        6. If WFA fails -> reject
        7. Try to enter pool (leaderboard logic)

        Args:
            strategy_id: Strategy UUID
            backtest_result: BacktestResult with training period metrics
            backtest_start_time: Start time for duration calculation
            degradation: Holdout degradation [-0.5, +0.5] for recency component
            combinations_tested: Number of parametric combinations tested (for metrics)
            robustness_score: Parameter stability score [0, 1] (default 0.5 = neutral)

        Returns:
            (success, reason) tuple
        """
        from src.database.event_tracker import EventTracker

        try:
            # Calculate backtest duration
            duration_ms = None
            if backtest_start_time is not None:
                duration_ms = int((time.time() - backtest_start_time) * 1000)

            # Calculate score using 6-component formula
            score = self.scorer.score_from_backtest_result(
                backtest_result, degradation, robustness_score
            )
            strategy = backtest_result.strategy
            strategy_name = strategy.name if strategy else str(strategy_id)

            # Emit scoring event with duration (using training metrics, not weighted)
            # Include base_code_hash for metrics tracking (unique base count)
            base_hash = strategy.base_code_hash if strategy else None
            EventTracker.backtest_scored(
                strategy_id, strategy_name, score,
                sharpe=backtest_result.sharpe_ratio or 0,
                win_rate=backtest_result.win_rate or 0,
                expectancy=backtest_result.expectancy or 0,
                consistency=backtest_result.win_rate or 0,  # Consistency = win rate
                drawdown=backtest_result.max_drawdown or 0,
                duration_ms=duration_ms,
                combinations_tested=combinations_tested,
                base_code_hash=base_hash
            )

            # Check minimum score threshold first (avoid unnecessary shuffle test)
            if score < self.pool_min_score:
                logger.debug(f"[{strategy_id}] Score {score:.1f} < {self.pool_min_score}, skipping shuffle test")
                EventTracker.backtest_score_rejected(
                    strategy_id, strategy_name, score, self.pool_min_score,
                    duration_ms=duration_ms,
                    combinations_tested=combinations_tested,
                    base_code_hash=base_hash
                )
                return (False, f"score_below_threshold:{score:.1f}")

            # Run shuffle test (only for strategies that could enter pool)
            if not self._run_shuffle_test(strategy_id, strategy):
                return (False, "shuffle_test_failed")

            # Run WFA validation with fixed params
            # Tests if the best combo performs consistently across 4 time windows
            wfa_passed, wfa_reason = self._run_wfa_fixed_params(
                strategy, strategy.assigned_timeframe
            )
            if not wfa_passed:
                logger.info(f"[{strategy_name}] WFA validation failed: {wfa_reason}")
                return (False, f"wfa_validation_failed:{wfa_reason}")

            # Try to enter pool (handles leaderboard logic)
            EventTracker.pool_attempted(
                strategy_id, strategy_name, score,
                pool_size=self.pool_manager.get_pool_size()
            )

            success, reason = self.pool_manager.try_enter_pool(strategy_id, score)

            if success:
                EventTracker.pool_entered(
                    strategy_id, strategy_name, score,
                    pool_size=self.pool_manager.get_pool_size()
                )
            else:
                EventTracker.pool_rejected(
                    strategy_id, strategy_name, score, reason
                )

            return (success, reason)

        except ValueError as e:
            logger.warning(f"Cannot calculate score for {strategy_id}: {e}")
            return (False, str(e))

    @property
    def test_data(self) -> pd.DataFrame:
        """Lazy-load test data for lookahead test"""
        if self._test_data is None:
            self._test_data = self._load_test_data()
        return self._test_data

    def _load_test_data(self) -> pd.DataFrame:
        """
        Load test data for lookahead test validation.

        Uses minimum timeframe from config (most candles = most rigorous test).
        If lookahead passes on min TF, it passes on all higher TFs.

        Fast Fail: crashes if no data available (no synthetic fallback).
        Synthetic data would mask lookahead bias - strategies with lookahead
        could pass on random data where indicator values are already uncorrelated.
        """
        # Use minimum timeframe (most candles = most rigorous test)
        timeframes = self.config.get_required('timeframes')
        min_tf = min(timeframes, key=lambda tf: self.data_loader._timeframe_to_minutes(tf))

        data = self.data_loader.load_single_symbol('BTC', min_tf, days=30)
        if data.empty:
            raise RuntimeError(
                f"No BTC {min_tf} data in cache for lookahead test. "
                "Run data_scheduler to download data first."
            )
        logger.info(f"Loaded {len(data)} bars of BTC {min_tf} data for lookahead test")
        return data

    def _run_shuffle_test(self, strategy_id: UUID, strategy: Strategy) -> bool:
        """
        Run shuffle test on strategy. Uses cache by base_code_hash.

        Args:
            strategy_id: Strategy UUID
            strategy: Strategy model instance

        Returns:
            True if passed, False if failed
        """
        import time
        from src.database.event_tracker import EventTracker

        base_code_hash = strategy.base_code_hash
        start_time = time.time()

        # Check cache first
        cached_result = self._get_cached_shuffle_result(base_code_hash)
        if cached_result is not None:
            duration_ms = int((time.time() - start_time) * 1000)
            if cached_result:
                logger.debug(f"[{strategy.name}] Shuffle test PASSED (cached)")
                EventTracker.shuffle_test_passed(
                    strategy_id, strategy.name, cached=True,
                    duration_ms=duration_ms, base_code_hash=base_code_hash
                )
            else:
                logger.info(f"[{strategy.name}] Shuffle test FAILED (cached)")
                EventTracker.shuffle_test_failed(
                    strategy_id, strategy.name, reason="cached_failure",
                    cached=True, duration_ms=duration_ms, base_code_hash=base_code_hash
                )
            return cached_result

        # Cache miss - run actual shuffle test
        EventTracker.shuffle_test_started(
            strategy_id, strategy.name, cached=False, base_code_hash=base_code_hash
        )

        try:
            # Extract actual class name from code (may differ from strategy.name)
            class_name = self._extract_class_name(strategy.code)
            if not class_name:
                logger.warning(f"[{strategy.name}] Cannot extract class name from code")
                duration_ms = int((time.time() - start_time) * 1000)
                EventTracker.shuffle_test_failed(
                    strategy_id, strategy.name, reason="class_name_not_found",
                    duration_ms=duration_ms, base_code_hash=base_code_hash
                )
                return False

            strategy_instance = self._load_strategy_instance(strategy.code, class_name)

            if strategy_instance is None:
                logger.warning(f"[{strategy.name}] Cannot load instance for shuffle test (class: {class_name})")
                duration_ms = int((time.time() - start_time) * 1000)
                EventTracker.shuffle_test_failed(
                    strategy_id, strategy.name, reason="instance_load_failed",
                    duration_ms=duration_ms, base_code_hash=base_code_hash
                )
                return False

            result = self.lookahead_tester.validate(strategy_instance, self.test_data)
            duration_ms = int((time.time() - start_time) * 1000)

            # Cache the result
            self._cache_shuffle_result(base_code_hash, result.passed)

            if result.passed:
                logger.debug(f"[{strategy.name}] Shuffle test PASSED")
                EventTracker.shuffle_test_passed(
                    strategy_id, strategy.name, cached=False,
                    duration_ms=duration_ms, base_code_hash=base_code_hash
                )
            else:
                logger.info(f"[{strategy.name}] Shuffle test FAILED: {result.details}")
                EventTracker.shuffle_test_failed(
                    strategy_id, strategy.name, reason=str(result.details),
                    duration_ms=duration_ms, base_code_hash=base_code_hash
                )

            return result.passed

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Shuffle test error for {strategy.name}: {e}")
            EventTracker.shuffle_test_failed(
                strategy_id, strategy.name, reason=f"error:{e}",
                duration_ms=duration_ms, base_code_hash=base_code_hash
            )
            return False

    def _get_cached_shuffle_result(self, base_code_hash: Optional[str]) -> Optional[bool]:
        """
        Check if shuffle test result is cached for this base_code_hash.

        Returns:
            True if cached and passed, False if cached and failed, None if not cached
        """
        if not base_code_hash:
            return None

        try:
            with get_session() as session:
                cache_entry = session.query(ValidationCache).filter(
                    ValidationCache.code_hash == base_code_hash
                ).first()

                if cache_entry:
                    return cache_entry.shuffle_passed
                return None
        except Exception as e:
            logger.warning(f"Error reading validation cache: {e}")
            return None

    def _cache_shuffle_result(self, base_code_hash: Optional[str], passed: bool) -> None:
        """Save shuffle test result to cache."""
        if not base_code_hash:
            return

        try:
            with get_session() as session:
                existing = session.query(ValidationCache).filter(
                    ValidationCache.code_hash == base_code_hash
                ).first()

                if existing:
                    existing.shuffle_passed = passed
                    existing.validated_at = datetime.now(UTC)
                else:
                    cache_entry = ValidationCache(
                        code_hash=base_code_hash,
                        shuffle_passed=passed,
                        validated_at=datetime.now(UTC)
                    )
                    session.add(cache_entry)

            logger.debug(
                f"Cached shuffle result for {base_code_hash[:8]}: "
                f"{'PASSED' if passed else 'FAILED'}"
            )
        except Exception as e:
            logger.warning(f"Error writing validation cache: {e}")

    # NOTE: _run_multi_window_validation removed - replaced by WFA with parameter
    # re-optimization (see _run_wfa_with_optimization). WFA checks param stability
    # across 4 expanding windows, which is more rigorous than multi-window.

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
        # STEP 1: Validate backtester before starting
        logger.info("Running backtester validation...")
        from src.backtester.validate import validate_backtester
        if not validate_backtester():
            logger.critical("BACKTESTER VALIDATION FAILED - BLOCKING STARTUP")
            logger.critical("Fix the backtester bugs before running the daemon.")
            sys.exit(1)
        logger.info("Backtester validation passed - starting daemon")

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Backtester process terminated")
