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
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.backtester.parametric_backtest import ParametricBacktester
# NOTE: detect_structure not used - all strategies forced to PERCENTAGE for Numba parametric
from src.strategies.base import StopLossType, TakeProfitType
# NOTE: MultiWindowValidator removed - replaced by WFA with parameter re-optimization
from src.data.coin_registry import get_registry, get_active_pairs
from src.data.funding_loader import FundingLoader
from src.scorer import BacktestScorer, PoolManager
from src.validator.lookahead_test import LookaheadTester
from src.utils import get_logger, setup_logging
from src.utils.strategy_files import sync_directories_with_db

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

        # Funding loader - lazy init
        self._funding_loader = None
        self.funding_enabled = self.config.get('funding.enabled', False)

        # Backtest thresholds - NO defaults
        self.min_sharpe = self.config.get_required('backtesting.thresholds.min_sharpe')
        self.min_win_rate = self.config.get_required('backtesting.thresholds.min_win_rate')
        self.max_drawdown = self.config.get_required('backtesting.thresholds.max_drawdown')
        self.min_trades = self.config.get_required('backtesting.thresholds.min_total_trades')
        self.min_expectancy = self.config.get_required('backtesting.thresholds.min_expectancy')

        # Timeframes (top-level in config) - NO defaults
        self.timeframes = self.config.get_required('timeframes')

        # In-sample/Out-of-sample configuration
        self.is_days = self.config.get_required('backtesting.is_days')
        self.oos_days = self.config.get_required('backtesting.oos_days')
        self.min_coverage_pct = self.config.get_required('backtesting.min_coverage_pct')

        # Out-of-sample validation thresholds
        # Note: OOS uses same thresholds as IS (min_sharpe, min_win_rate, etc.)
        # Only degradation and recency_weight are OOS-specific
        self.oos_max_degradation = self.config.get_required('backtesting.out_of_sample.max_degradation')
        self.oos_recency_weight = self.config.get_required('backtesting.out_of_sample.recency_weight')

        # Min trades per timeframe (parallel arrays)
        timeframes = self.config.get_required('timeframes')
        min_is = self.config.get_required('backtesting.min_trades.in_sample')
        min_oos = self.config.get_required('backtesting.min_trades.out_of_sample')
        self.min_trades_is = dict(zip(timeframes, min_is))
        self.min_trades_oos = dict(zip(timeframes, min_oos))

        # Max CI (statistical significance filter)
        # CI = 1.96 × sqrt(WR × (1-WR) / N) - lower CI = more confidence
        self.max_ci_is = self.config.get_required('backtesting.max_ci.in_sample')
        self.max_ci_oos = self.config.get_required('backtesting.max_ci.out_of_sample')

        # Initial capital for expectancy normalization
        self.initial_capital = self.config.get_required('backtesting.initial_capital')

        # SCORER and PoolManager for post-backtest scoring and pool management
        self.scorer = BacktestScorer(self.config._raw_config)
        self.pool_manager = PoolManager(self.config._raw_config)

        # Sync strategy files with DB at startup (ensures consistency)
        self._sync_strategy_files()

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
            f"{len(self.timeframes)} TFs, retest every {self.retest_interval_days}d, pool max {self.pool_max_size}"
        )

    def _sync_strategy_files(self):
        """Sync strategy files (pool/live dirs) with database at startup."""
        try:
            with get_session() as session:
                stats = sync_directories_with_db(session)
                if any(stats.values()):
                    logger.info(f"Strategy files synced: {stats}")
        except Exception as e:
            logger.warning(f"Failed to sync strategy files: {e}")

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
            target_count: Target number of pairs (default: all coins)

        Returns:
            (validated_coins, status) - validated_coins is None if no coins pass
        """
        if target_count is None:
            target_count = len(coins)  # Use all coins by default

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

    def _validate_trading_coins(
        self,
        trading_coins: List[str],
        timeframe: str
    ) -> Tuple[Optional[List[str]], str]:
        """
        Validate trading coins for backtest/live consistency.

        Three-level validation (all required):
        1. Liquidity: coin must be in active trading pairs (volume >= threshold)
        2. Cache: coin must have cached OHLCV data
        3. Coverage: coin must have >= 90% data coverage for training+holdout period

        NO FALLBACK: If insufficient coins pass validation, returns None.
        This ensures backtest coins = live coins = edge preserved.

        Args:
            trading_coins: Strategy's assigned coins (from generator)
            timeframe: Timeframe to validate data coverage for

        Returns:
            (validated_coins, rejection_reason) - validated_coins is None if rejected
        """
        if not trading_coins:
            return None, "no_trading_coins"

        # Level 1: Liquidity filter (active trading pairs from CoinRegistry)
        active_coins = set(get_active_pairs())
        liquid_coins = [c for c in trading_coins if c in active_coins]

        if not liquid_coins:
            logger.warning(f"Liquidity filter: 0/{len(trading_coins)} coins liquid")
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
        # Use ALL coins that pass (no artificial limit)
        validated_coins, status = self._scroll_down_coverage(
            coins=cached_coins,
            timeframe=timeframe,
            target_count=len(cached_coins)  # Take all coins with valid coverage
        )

        if not validated_coins:
            logger.warning(f"Coverage filter: {status} (from {len(cached_coins)} cached)")
            return None, status

        logger.info(
            f"Validated {len(validated_coins)} trading coins "
            f"(from {len(trading_coins)} assigned)"
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
            # Use all validated pairs from strategy's trading_coins
            is_data, oos_data = self.data_loader.load_multi_symbol_is_oos(
                symbols=pairs,
                timeframe=timeframe,
                is_days=self.is_days,
                oos_days=self.oos_days,
                target_count=len(pairs)  # Use all validated pairs
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
                        strategy_data['trading_coins']
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
                        strategy.trading_coins,
                        strategy.base_code_hash  # Pass hash to detect pre-parametrized strategies
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
        trading_coins: Optional[List[str]] = None,
        base_code_hash: Optional[str] = None
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

            # Detect SL/TP types from strategy for typed parametric backtest
            # This enables full parametric optimization for ATR, STRUCTURE, TRAILING, RR_RATIO
            detected_sl_type = getattr(strategy_instance, 'sl_type', StopLossType.PERCENTAGE)
            detected_tp_type = getattr(strategy_instance, 'tp_type', TakeProfitType.PERCENTAGE)
            use_typed_backtest = (
                detected_sl_type != StopLossType.PERCENTAGE or
                (detected_tp_type is not None and detected_tp_type != TakeProfitType.PERCENTAGE)
            )
            if use_typed_backtest:
                logger.info(
                    f"[{strategy_name}] Using typed parametric backtest: "
                    f"SL={detected_sl_type.value}, TP={detected_tp_type.value if detected_tp_type else 'None'}"
                )

            # Begin single-timeframe backtest (previously a loop over [original_tf])
            # Validate trading_coins (no fallback - generators must provide coins)
            if not trading_coins:
                self._delete_strategy(strategy_id, "no_trading_coins")
                return (False, "Strategy has no trading_coins assigned")

            validated_coins, validation_reason = self._validate_trading_coins(
                trading_coins, assigned_tf
            )
            if validated_coins is None:
                self._delete_strategy(strategy_id, validation_reason)
                return (False, f"Trading coins validation failed: {validation_reason}")
            pairs = validated_coins
            logger.info(
                f"[{strategy_name}] {assigned_tf}: Using {len(pairs)} validated trading coins"
            )

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
            # Supports all SL/TP types via typed parametric backtest:
            # - PERCENTAGE: standard optimization
            # - ATR, STRUCTURE, TRAILING: pre-calculated, then optimized
            # - RR_RATIO: TP = SL × ratio
            try:
                if use_parametric:
                    # Initial parametric to find best combo
                    parametric_results = self._run_parametric_backtest(
                        strategy_instance, is_data, assigned_tf,
                        strategy_id=strategy_id, strategy_name=strategy_name,
                        base_code_hash=base_code_hash,
                        sl_type=detected_sl_type if use_typed_backtest else None,
                        tp_type=detected_tp_type if use_typed_backtest else None,
                    )

                    if not parametric_results:
                        self._delete_strategy(strategy_id, "No params passed thresholds")
                        return (False, "No parametric combinations passed thresholds")

                    # Best combo from initial parametric
                    initial_best = parametric_results[0]
                    # BUG FIX: Standard parametric has params as direct keys (sl_pct, tp_pct, etc.)
                    # Typed parametric has nested 'params' dict. Handle both cases.
                    if 'params' in initial_best and initial_best['params']:
                        # Typed parametric: use nested params dict
                        initial_params = initial_best['params']
                    else:
                        # Standard parametric: params are direct keys in result dict
                        initial_params = {
                            'sl_pct': initial_best.get('sl_pct', 0.02),
                            'tp_pct': initial_best.get('tp_pct', 0.0),
                            'leverage': initial_best.get('leverage', 1),
                            'exit_bars': initial_best.get('exit_bars', 0),
                        }
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
                    # For typed strategies: preserve original sl_type, apply converted pct values
                    # For percentage strategies: use optimized sl_pct/tp_pct directly
                    if use_typed_backtest:
                        # Typed backtest: preserve original SL/TP types
                        # The parametric returns median sl_pct/tp_pct (pre-calculated from ATR/STRUCTURE)
                        # These are the EFFECTIVE percentages for the strategy's exit conditions
                        # Strategy code uses original type (ATR, STRUCTURE, etc.)
                        # Backtest/live will calculate SL/TP based on original type, not these pcts
                        strategy_instance.SL_PCT = initial_params.get('sl_pct', 0.02)
                        strategy_instance.TP_PCT = initial_params.get('tp_pct', 0.03)
                        # sl_type preserved from original strategy (not overwritten)
                    else:
                        # Standard percentage-based: set sl_type=PERCENTAGE
                        strategy_instance.sl_type = StopLossType.PERCENTAGE
                        strategy_instance.SL_PCT = initial_params.get('sl_pct', 0.02)
                        strategy_instance.TP_PCT = initial_params.get('tp_pct', 0.03)

                    # Common params always applied
                    strategy_instance.LEVERAGE = initial_params.get('leverage', 1)
                    strategy_instance.exit_after_bars = initial_params.get('exit_bars', 0)

                    # BUG FIX: Store optimal params for strategy code update
                    # Without this, _update_strategy_assigned_tf receives None and
                    # doesn't update the code - causing retest to use wrong params
                    optimal_params = initial_params

                    # DEBUG: Log strategy params before IS backtest
                    # Read UPPERCASE attrs (set by parametric) for accurate logging
                    logger.info(
                        f"[{strategy_name}] IS params: SL_PCT={strategy_instance.SL_PCT:.2%}, "
                        f"TP_PCT={strategy_instance.TP_PCT:.2%}, LEVERAGE={strategy_instance.LEVERAGE}, "
                        f"exit_bars={strategy_instance.exit_after_bars}, sl_type={strategy_instance.sl_type}"
                    )

                    # STEP 2: Final IS backtest with best params for metrics
                    is_start_time = time.time()  # Track IS phase timing (excludes parametric)
                    is_result = self._run_multi_symbol_backtest(
                        strategy_instance, is_data, assigned_tf
                    )

                    # DEBUG: Compare parametric vs IS trades
                    parametric_trades = initial_best.get('total_trades', 0)
                    is_trades = is_result.get('total_trades', 0)
                    is_sharpe = is_result.get('sharpe_ratio', 0)
                    is_signals = is_result.get('total_signals', 0)
                    # Get parametric signals from the initial run
                    parametric_signals = initial_best.get('total_signals', 0)
                    logger.debug(
                        f"[{strategy_name}] Parametric signals={parametric_signals}, "
                        f"IS signals={is_signals}, Parametric trades={parametric_trades}, IS trades={is_trades}"
                    )
                    if abs(parametric_trades - is_trades) > 50 or is_sharpe < 0:
                        logger.debug(
                            f"[{strategy_name}] DISCREPANCY: Parametric={parametric_trades} trades, "
                            f"IS={is_trades} trades, IS_Sharpe={is_sharpe:.2f}"
                        )

                else:
                    # Fallback: parametric disabled (should not happen normally)
                    # Force PERCENTAGE and use original params
                    is_start_time = time.time()
                    strategy_instance.sl_type = StopLossType.PERCENTAGE
                    is_result = self._run_multi_symbol_backtest(
                        strategy_instance, is_data, assigned_tf
                    )
                    optimal_params = {
                        'sl_pct': getattr(strategy_instance, 'SL_PCT', 0.02),
                        'tp_pct': getattr(strategy_instance, 'TP_PCT', 0.0),
                        'leverage': getattr(strategy_instance, 'LEVERAGE', 1),
                        'exit_bars': getattr(strategy_instance, 'exit_after_bars', 0),
                    }
                    logger.warning(f"[{strategy_name}] Parametric disabled, using original params")

            except Exception as e:
                self._delete_strategy(strategy_id, f"IS backtest failed: {e}")
                return (False, f"IS backtest failed for {assigned_tf}: {e}")

            if is_result is None or is_result.get('total_trades', 0) == 0:
                self._delete_strategy(strategy_id, "No trades in IS")
                return (False, f"No trades in IS period for {assigned_tf}")

            # Validate IS thresholds (same as PARAMETRIC)
            # This catches any discrepancies between PARAMETRIC kernel and BacktestEngine
            is_sharpe = is_result.get('sharpe_ratio', 0)
            is_win_rate = is_result.get('win_rate', 0)
            is_expectancy = is_result.get('expectancy', 0)
            is_max_drawdown = is_result.get('max_drawdown', 0)
            is_trades = is_result.get('total_trades', 0)
            min_trades_is_tf = self.min_trades_is.get(assigned_tf, self.min_trades)

            # Calculate CI for statistical significance
            is_ci = self._calculate_ci(is_win_rate, is_trades)

            # CUMULATIVE threshold check (like PARAMETRIC) - count ALL violations
            fail_types = {
                'sharpe': 1 if is_sharpe < self.min_sharpe else 0,
                'wr': 1 if is_win_rate < self.min_win_rate else 0,
                'exp': 1 if is_expectancy < self.min_expectancy else 0,
                'dd': 1 if is_max_drawdown > self.max_drawdown else 0,
                'trades': 1 if is_trades < min_trades_is_tf else 0,
                'ci': 1 if is_ci > self.max_ci_is else 0,
            }

            if sum(fail_types.values()) > 0:
                # Build reason listing ALL failed thresholds
                reasons = []
                if fail_types['sharpe']:
                    reasons.append(f"sharpe={is_sharpe:.2f}<{self.min_sharpe}")
                if fail_types['wr']:
                    reasons.append(f"wr={is_win_rate:.1%}<{self.min_win_rate:.1%}")
                if fail_types['exp']:
                    reasons.append(f"exp={is_expectancy:.4f}<{self.min_expectancy}")
                if fail_types['dd']:
                    reasons.append(f"dd={is_max_drawdown:.1%}>{self.max_drawdown:.0%}")
                if fail_types['trades']:
                    reasons.append(f"trades={is_trades}<{min_trades_is_tf}")
                if fail_types['ci']:
                    reasons.append(f"ci={is_ci:.1%}>{self.max_ci_is:.0%}")
                reason = "IS failed: " + ", ".join(reasons)

                from src.database.event_tracker import EventTracker
                is_duration_ms = int((time.time() - is_start_time) * 1000)
                EventTracker.backtest_is_failed(
                    strategy_id=strategy_id,
                    strategy_name=strategy_name,
                    timeframe=assigned_tf,
                    reason=reason,
                    fail_types=fail_types,
                    is_sharpe=is_sharpe,
                    is_win_rate=is_win_rate,
                    is_trades=is_trades,
                    is_expectancy=is_expectancy,
                    is_max_drawdown=is_max_drawdown,
                    base_code_hash=base_code_hash,
                    duration_ms=is_duration_ms,
                )
                self._delete_strategy(strategy_id, reason)
                return (False, reason)

            # IS passed - emit event with timing before proceeding to OOS
            is_duration_ms = int((time.time() - is_start_time) * 1000)
            from src.database.event_tracker import EventTracker
            EventTracker.backtest_is_passed(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                timeframe=assigned_tf,
                is_sharpe=is_sharpe,
                is_win_rate=is_win_rate,
                is_trades=is_trades,
                is_expectancy=is_expectancy,
                is_max_drawdown=is_max_drawdown,
                duration_ms=is_duration_ms,
                base_code_hash=base_code_hash,
            )

            # Run OUT-OF-SAMPLE period backtest (validation)
            # Use min_bars=20 for OOS (30 days on 1d = only 30 bars)
            oos_start_time = time.time()  # Track OOS phase timing
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
                # Emit event with IS/OOS metrics BEFORE deleting (for aggregate stats)
                from src.database.event_tracker import EventTracker
                oos_duration_ms = int((time.time() - oos_start_time) * 1000)
                EventTracker.backtest_oos_failed(
                    strategy_id=strategy_id,
                    strategy_name=strategy_name,
                    timeframe=assigned_tf,
                    reason=validation['reason'],
                    fail_types=validation.get('fail_types', {'sharpe': 0, 'wr': 0, 'exp': 0, 'dd': 0, 'trades': 0, 'degradation': 0}),
                    is_sharpe=is_result.get('sharpe_ratio', 0),
                    is_win_rate=is_result.get('win_rate', 0),
                    is_trades=is_result.get('total_trades', 0),
                    is_expectancy=is_result.get('expectancy', 0),
                    oos_sharpe=oos_result.get('sharpe_ratio') if oos_result else None,
                    oos_win_rate=oos_result.get('win_rate') if oos_result else None,
                    oos_trades=oos_result.get('total_trades') if oos_result else None,
                    oos_expectancy=oos_result.get('expectancy') if oos_result else None,
                    oos_max_drawdown=oos_result.get('max_drawdown') if oos_result else None,
                    base_code_hash=base_code_hash,
                    duration_ms=oos_duration_ms,
                )
                # Delete strategy (event persists for metrics)
                self._delete_strategy(strategy_id, validation['reason'])
                return (False, f"OOS validation failed: {validation['reason']}")

            # OOS passed - emit event with timing before proceeding to scoring
            oos_duration_ms = int((time.time() - oos_start_time) * 1000)
            EventTracker.backtest_oos_passed(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                timeframe=assigned_tf,
                is_sharpe=is_result.get('sharpe_ratio', 0),
                is_win_rate=is_result.get('win_rate', 0),
                is_trades=is_result.get('total_trades', 0),
                is_expectancy=is_result.get('expectancy', 0),
                oos_sharpe=oos_result.get('sharpe_ratio', 0),
                oos_win_rate=oos_result.get('win_rate', 0),
                oos_trades=oos_result.get('total_trades', 0),
                oos_expectancy=oos_result.get('expectancy', 0),
                oos_max_drawdown=oos_result.get('max_drawdown', 0),
                duration_ms=oos_duration_ms,
                base_code_hash=base_code_hash,
            )

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

            # Save backtest results (only for strategies that pass OOS validation)
            # Extract date ranges from data for accurate period tracking
            is_start, is_end = self._extract_date_range(is_data)
            is_backtest_id = self._save_backtest_result(
                strategy_id, is_result, pairs, assigned_tf,
                period_type='in_sample',
                period_days=self.is_days,
                start_date=is_start,
                end_date=is_end
            )

            oos_backtest_id = None
            if oos_result:
                oos_start, oos_end = self._extract_date_range(oos_data)
                oos_backtest_id = self._save_backtest_result(
                    strategy_id, oos_result, pairs, assigned_tf,
                    period_type='out_of_sample',
                    period_days=self.oos_days,
                    start_date=oos_start,
                    end_date=oos_end
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

                        # Get combinations_tested from parametric results (if parametric was used)
                        combinations = all_parametric_results[0].get('combinations_tested') if all_parametric_results else None

                        # Try to enter ACTIVE pool (handles leaderboard logic)
                        entered, pool_reason = self._promote_to_active_pool(
                            strategy_id, db_backtest, backtest_start_time, degradation,
                            combinations_tested=combinations
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
                            # Strategy didn't make it into pool
                            # Distinguish between RETIRED (valid but not good enough) vs FAILED (buggy)
                            if pool_reason.startswith("shuffle_test_failed"):
                                # Shuffle test failure = lookahead bias = bug in strategy
                                self.processor.mark_failed(strategy_id, pool_reason, delete=False)
                            else:
                                # score_below_threshold, wfa_validation_failed, pool rejection
                                # These are valid strategies that just don't meet criteria → RETIRED
                                self.pool_manager._retire_strategy(
                                    strategy_id,
                                    pool_reason,
                                    "score_below_min" if "score_below" in pool_reason else "pool_rejected"
                                )
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

    def _emit_empty_parametric_stats(
        self,
        base_code_hash: str,
        strategy_name: str,
        timeframe: str,
        start_time: float,
        reason: str = "unknown"
    ) -> None:
        """
        Emit parametric_stats event with zero counts for early failures.

        This ensures ALL strategies get a parametric_stats event for consistent
        metrics aggregation, even if they fail before completing parametric backtest.
        """
        if not base_code_hash:
            return

        from src.database.event_tracker import EventTracker
        duration_ms = int((time.time() - start_time) * 1000)

        empty_stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'fail_reasons': {'sharpe': 0, 'trades': 0, 'wr': 0, 'exp': 0, 'dd': 0},
            'failed_avg': {'sharpe': 0, 'wr': 0, 'exp': 0, 'trades': 0},
            'passed_avg': {'sharpe': 0, 'wr': 0, 'exp': 0, 'trades': 0},
            'early_exit_reason': reason,
        }

        EventTracker.backtest_parametric_stats(
            base_code_hash=base_code_hash,
            strategy_name=strategy_name or "unknown",
            timeframe=timeframe,
            combo_stats=empty_stats,
            duration_ms=duration_ms
        )

        logger.debug(f"[{strategy_name}] Emitted empty parametric_stats: {reason}")

    def _run_parametric_backtest(
        self,
        strategy_instance,
        data: Dict[str, any],
        timeframe: str,
        strategy_id=None,
        strategy_name: str = None,
        base_code_hash: str = None,
        sl_type: StopLossType = None,
        tp_type: TakeProfitType = None,
    ) -> List[Dict]:
        """
        Run parametric backtest generating strategies with different SL/TP/leverage/exit.

        Extracts entry signals from the strategy once, then tests N parameter sets
        using the Numba-optimized ParametricBacktester to generate candidate strategies.

        Parameter space selection based on execution_type:

        1. execution_type = 'touch_based' or 'close_based':
           - Uses build_execution_type_space() with specialized logic
           - touch_based: TP is primary exit (optimize around magnitude)
           - close_based: TIME EXIT is primary (TP=0, SL based on ATR)

        2. No execution_type:
           - Uses build_absolute_space() with per-timeframe ranges
           - Generic exploration of SL/TP/leverage/exit parameter space

        Args:
            strategy_instance: StrategyCore instance
            data: Dict mapping symbol -> DataFrame
            timeframe: Timeframe being tested
            strategy_id: Strategy UUID for event tracking
            strategy_name: Strategy name for event tracking
            base_code_hash: Hash for batch processing

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

        # Build parameter space based on execution_type
        # NOTE: Non-percentage strategies are filtered BEFORE calling this method
        # (use_parametric=False for ATR, structure, trailing strategies)
        # So this method only handles percentage-based strategies:
        # 1. execution_type (touch_based/close_based) → use execution_type_space
        # 2. Default → use absolute_space
        execution_type = getattr(strategy_instance, 'execution_type', None)

        if execution_type in ('touch_based', 'close_based'):
            # Strategy has execution_type: use specialized parameter space
            # - touch_based: TP is primary exit (optimize around magnitude)
            # - close_based: TIME EXIT is primary (TP=0, SL based on ATR)
            # CRITICAL: Read UPPERCASE attrs first (template definitions), then lowercase (base class defaults)
            base_tp_pct = getattr(strategy_instance, 'TP_PCT', None)
            if base_tp_pct is None:
                base_tp_pct = getattr(strategy_instance, 'tp_pct', 0.05)
            base_exit_bars = getattr(strategy_instance, 'exit_after_bars', 20)
            atr_signal_median = getattr(strategy_instance, 'atr_signal_median', None)

            logger.info(
                f"Using execution_type_space: type={execution_type}, "
                f"magnitude={base_tp_pct:.2%}, exit_bars={base_exit_bars}, "
                f"atr_median={atr_signal_median}"
            )
            space = self.parametric_backtester.build_execution_type_space(
                execution_type=execution_type,
                base_magnitude=base_tp_pct,
                base_exit_bars=base_exit_bars,
                atr_signal_median=atr_signal_median,
            )
        else:
            # No execution_type: use absolute space (generic per-timeframe ranges)
            logger.info(f"Using absolute_space for timeframe={timeframe}")
            space = self.parametric_backtester.build_absolute_space(timeframe)

        self.parametric_backtester.set_parameter_space(space)

        # Filter out empty/insufficient data
        valid_data = {
            symbol: df for symbol, df in data.items()
            if not df.empty and len(df) >= 100
        }

        if not valid_data:
            # Emit parametric_stats with zero counts for metrics consistency
            self._emit_empty_parametric_stats(
                base_code_hash, strategy_name, timeframe, parametric_start_time,
                reason="no_valid_data"
            )
            return []

        # Sort symbols for consistent ordering
        symbols = sorted(valid_data.keys())
        n_symbols = len(symbols)

        # Find common index (intersection of all symbol TIMESTAMPS, not RangeIndex!)
        # CRITICAL: DataFrames have timestamp as COLUMN, not index
        # We must use timestamp intersection like the engine does
        common_index = None
        for symbol in symbols:
            df = valid_data[symbol]
            if 'timestamp' in df.columns:
                # Use timestamp column for proper alignment
                ts_index = pd.DatetimeIndex(df['timestamp'])
                if common_index is None:
                    common_index = ts_index
                else:
                    common_index = common_index.intersection(ts_index)
            else:
                # Fallback to existing index if no timestamp column
                if common_index is None:
                    common_index = df.index
                else:
                    common_index = common_index.intersection(df.index)

        if len(common_index) < 100:
            logger.warning(f"Insufficient common data for parametric backtest: {len(common_index)} bars")
            return []

        n_bars = len(common_index)

        # PRE-FILTER DataFrames with fast-path optimization
        # If all symbols have exactly n_bars rows, they're already aligned (skip filtering)
        all_aligned = all(len(valid_data[s]) == n_bars for s in symbols)

        if all_aligned:
            # Fast path: data already aligned, just reset index
            filtered_data = {
                symbol: valid_data[symbol].reset_index(drop=True)
                for symbol in symbols
            }
        else:
            # Slow path: need to filter by common timestamps
            common_index_set = set(common_index)
            filtered_data = {}
            for symbol in symbols:
                raw_df = valid_data[symbol]
                if 'timestamp' in raw_df.columns:
                    mask = raw_df['timestamp'].isin(common_index_set)
                    filtered_data[symbol] = raw_df[mask].reset_index(drop=True)
                else:
                    filtered_data[symbol] = raw_df.loc[common_index].reset_index(drop=True)

        # Load funding rates if enabled
        funding_cumsum = None
        if self.funding_enabled:
            try:
                # Extract coin names (BTCUSDT -> BTC)
                coin_symbols = [s.replace('USDT', '').replace('PERP', '') for s in symbols]

                # Align funding to OHLCV timestamps
                funding_rates = self.funding_loader.get_funding_array_aligned(
                    symbols=coin_symbols,
                    timestamps=common_index,
                    timeframe=timeframe
                )

                # Pre-calculate cumsum for O(1) lookup in kernel
                funding_cumsum = np.cumsum(funding_rates, axis=0)

                logger.debug(
                    f"Funding loaded: {len(coin_symbols)} symbols, "
                    f"mean_rate={funding_rates.mean():.8f}"
                )
            except Exception as e:
                logger.warning(f"Failed to load funding rates: {e}")
                funding_cumsum = None

        # Build aligned 2D arrays (n_bars, n_symbols)
        close_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        high_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        low_2d = np.zeros((n_bars, n_symbols), dtype=np.float64)
        entries_2d = np.zeros((n_bars, n_symbols), dtype=np.bool_)
        directions_2d = np.zeros((n_bars, n_symbols), dtype=np.int8)

        # Get strategy direction
        direction = getattr(strategy_instance, 'direction', 'long')
        is_bidi = direction in ('both', 'bidi', 'bidir')
        # For non-BIDI: 1 for long, -1 for short
        dir_value = 1 if direction == 'long' else -1
        signal_column = getattr(strategy_instance, 'signal_column', 'entry_signal')

        # Process each symbol: calculate indicators and extract signals
        for j, symbol in enumerate(symbols):
            df = filtered_data[symbol]  # Already filtered, no copy needed

            # Calculate indicators
            try:
                df_with_indicators = strategy_instance.calculate_indicators(df)
            except Exception as e:
                logger.warning(f"Failed to calculate indicators for {symbol}: {e}")
                continue

            # Extract OHLC
            close_2d[:, j] = df['close'].values.astype(np.float64)
            high_2d[:, j] = df['high'].values.astype(np.float64)
            low_2d[:, j] = df['low'].values.astype(np.float64)

            # Extract entry signals
            if signal_column in df_with_indicators.columns:
                entries_2d[:, j] = df_with_indicators[signal_column].values.astype(bool)

            # Handle directions
            if is_bidi:
                has_long = 'long_signal' in df_with_indicators.columns
                has_short = 'short_signal' in df_with_indicators.columns
                if has_long and has_short:
                    long_signals = df_with_indicators['long_signal'].values.astype(bool)
                    short_signals = df_with_indicators['short_signal'].values.astype(bool)
                    directions_2d[:, j] = np.where(
                        long_signals, 1, np.where(short_signals, -1, 0)
                    ).astype(np.int8)
                else:
                    directions_2d[:, j] = 1
            else:
                directions_2d[:, j] = dir_value

        # Apply warmup (first 100 bars = no signal)
        entries_2d[:100, :] = False

        # Count signals
        total_signals = entries_2d.sum()
        if total_signals == 0:
            logger.info(f"[{strategy_name}] No entry signals found for parametric backtest")
            # Emit parametric_stats with zero counts for metrics consistency
            self._emit_empty_parametric_stats(
                base_code_hash, strategy_name, timeframe, parametric_start_time,
                reason="no_signals"
            )
            return []

        # DEBUG: Log parametric config for comparison with engine
        logger.info(
            f"[{strategy_name}] Parametric config: risk_pct={self.parametric_backtester.risk_pct:.4f}, "
            f"max_positions={self.parametric_backtester.max_positions}"
        )
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
        # Route to typed backtest if non-percentage SL/TP types are specified
        try:
            if sl_type is not None and sl_type != StopLossType.PERCENTAGE:
                # Use typed backtest for ATR, STRUCTURE, TRAILING, etc.
                results_df = self.parametric_backtester.backtest_typed(
                    pattern_signals=entries_2d,
                    ohlc_data={'close': close_2d, 'high': high_2d, 'low': low_2d},
                    directions=directions_2d,
                    max_leverages=max_leverages,
                    sl_type=sl_type,
                    tp_type=tp_type if tp_type else TakeProfitType.PERCENTAGE,
                    strategy_name=strategy_name,
                    funding_cumsum=funding_cumsum,
                )
            else:
                # Standard percentage-based parametric backtest
                results_df = self.parametric_backtester.backtest_pattern(
                    pattern_signals=entries_2d,
                    ohlc_data={'close': close_2d, 'high': high_2d, 'low': low_2d},
                    directions=directions_2d,
                    max_leverages=max_leverages,
                    strategy_name=strategy_name,
                    funding_cumsum=funding_cumsum,
                )
        except Exception as e:
            logger.error(f"Parametric backtest failed: {e}")
            # Emit parametric_stats with zero counts for metrics consistency
            self._emit_empty_parametric_stats(
                base_code_hash, strategy_name, timeframe, parametric_start_time,
                reason=f"exception:{str(e)[:50]}"
            )
            return []

        # Use IS min_trades for the timeframe (aligned with subsequent IS validation)
        # This prevents testing combos that will fail IS trades check anyway
        min_trades_tf = self.min_trades_is.get(timeframe, self.min_trades)

        # Filter by threshold - save ALL strategies that pass
        valid_results = results_df[
            (results_df['sharpe'] >= self.min_sharpe) &
            (results_df['win_rate'] >= self.min_win_rate) &
            (results_df['expectancy'] >= self.min_expectancy) &
            (results_df['max_drawdown'] <= self.max_drawdown) &
            (results_df['total_trades'] >= min_trades_tf)
        ].copy()

        # Track total combinations tested (for metrics)
        combinations_tested = len(results_df)

        # Calculate combo stats for metrics (CUMULATIVE - each combo counted for ALL violated thresholds)
        n_total = len(results_df)
        n_passed = len(valid_results)
        n_failed = n_total - n_passed

        # Failed combos = those NOT in valid_results
        failed_results = results_df[
            ~((results_df['sharpe'] >= self.min_sharpe) &
              (results_df['win_rate'] >= self.min_win_rate) &
              (results_df['expectancy'] >= self.min_expectancy) &
              (results_df['max_drawdown'] <= self.max_drawdown) &
              (results_df['total_trades'] >= min_trades_tf))
        ]

        # CUMULATIVE threshold violations (each combo counted for EACH threshold it violates)
        cum_fail_sharpe = int((results_df['sharpe'] < self.min_sharpe).sum())
        cum_fail_trades = int((results_df['total_trades'] < min_trades_tf).sum())
        cum_fail_wr = int((results_df['win_rate'] < self.min_win_rate).sum())
        cum_fail_exp = int((results_df['expectancy'] < self.min_expectancy).sum())
        cum_fail_dd = int((results_df['max_drawdown'] > self.max_drawdown).sum())

        # Avg metrics for failed combos
        if len(failed_results) > 0:
            failed_avg = {
                'sharpe': float(failed_results['sharpe'].mean()),
                'wr': float(failed_results['win_rate'].mean()),
                'exp': float(failed_results['expectancy'].mean()),
                'trades': float(failed_results['total_trades'].mean()),
            }
        else:
            failed_avg = {'sharpe': 0, 'wr': 0, 'exp': 0, 'trades': 0}

        # Avg metrics for passed combos
        if len(valid_results) > 0:
            passed_avg = {
                'sharpe': float(valid_results['sharpe'].mean()),
                'wr': float(valid_results['win_rate'].mean()),
                'exp': float(valid_results['expectancy'].mean()),
                'trades': float(valid_results['total_trades'].mean()),
            }
        else:
            passed_avg = {'sharpe': 0, 'wr': 0, 'exp': 0, 'trades': 0}

        # Build combo_stats dict for event tracking
        combo_stats = {
            'total': n_total,
            'passed': n_passed,
            'failed': n_failed,
            'fail_reasons': {
                'sharpe': cum_fail_sharpe,
                'trades': cum_fail_trades,
                'wr': cum_fail_wr,
                'exp': cum_fail_exp,
                'dd': cum_fail_dd,
            },
            'failed_avg': failed_avg,
            'passed_avg': passed_avg,
        }

        # Emit parametric_stats event for metrics aggregation (ALWAYS, regardless of results)
        if base_code_hash:
            from src.database.event_tracker import EventTracker
            duration_ms = int((time.time() - parametric_start_time) * 1000)
            EventTracker.backtest_parametric_stats(
                base_code_hash=base_code_hash,
                strategy_name=strategy_name or "unknown",
                timeframe=timeframe,
                combo_stats=combo_stats,
                duration_ms=duration_ms
            )

        # Convert to list of dicts matching expected format
        # Use float() to convert np.float64 to native Python float (required for DB)
        results = []
        for _, row in valid_results.iterrows():
            # Check if row has full params from typed backtest
            if 'params' in row and isinstance(row['params'], dict):
                # Use full params (includes sl_type, tp_type for typed backtest)
                params = row['params'].copy()
                # Ensure numeric types are native Python (not numpy)
                params['sl_pct'] = float(params.get('sl_pct', row['sl_pct']))
                params['tp_pct'] = float(params.get('tp_pct', row['tp_pct']))
                params['leverage'] = int(params.get('leverage', row['leverage']))
                params['exit_bars'] = int(params.get('exit_bars', row['exit_bars']))
            else:
                # Standard percentage-based backtest
                params = {
                    'sl_pct': float(row['sl_pct']),
                    'tp_pct': float(row['tp_pct']),
                    'leverage': int(row['leverage']),
                    'exit_bars': int(row['exit_bars']),
                }

            result = {
                'sharpe_ratio': float(row['sharpe']),
                'max_drawdown': float(row['max_drawdown']),
                'win_rate': float(row['win_rate']),
                'expectancy': float(row['expectancy']),
                'total_trades': int(row['total_trades']),
                'total_return': float(row['total_return']),
                'parametric_score': float(row['score']),
                # Store the parameters used
                'params': params,
                # Track combinations tested (same for all results from this base strategy)
                'combinations_tested': combinations_tested,
                # Track total signals for debugging
                'total_signals': int(total_signals),
                # Combo stats for metrics aggregation
                'combo_stats': combo_stats,
            }
            results.append(result)

        if results:
            best = results[0]
            logger.info(
                f"[{strategy_name}] Parametric: {len(results)} strategies | "
                f"Best: Sharpe={best['sharpe_ratio']:.2f}, Trades={best['total_trades']}, "
                f"SL={best['params']['sl_pct']:.1%}, TP={best['params']['tp_pct']:.1%}, "
                f"Exit={best['params']['exit_bars']}"
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
                    f"Trades={max_trades} (need {min_trades_tf}), "
                    f"Exp={best_expectancy:.4f} (need {self.min_expectancy}), "
                    f"DD={min_dd:.1%} (need <{self.max_drawdown:.0%})"
                )

                # Log cumulative fail reasons (from combo_stats already computed)
                fr = combo_stats['fail_reasons']
                fa = combo_stats['failed_avg']
                logger.info(
                    f"[{strategy_name}]   Fail reasons (cumulative): "
                    f"sharpe: {fr['sharpe']}, trades: {fr['trades']}, "
                    f"wr: {fr['wr']}, exp: {fr['exp']}, dd: {fr['dd']}"
                )
                logger.info(
                    f"[{strategy_name}]   Failed avg: "
                    f"sharpe={fa['sharpe']:.2f}, wr={fa['wr']:.1%}, "
                    f"exp={fa['exp']:.4f}, trades={fa['trades']:.0f}"
                )

                # DEBUG: Show top 5 combos by score and why they fail
                top5 = results_df.nlargest(5, 'score')
                for idx, row in top5.iterrows():
                    fails = []
                    if row['sharpe'] < self.min_sharpe:
                        fails.append(f"Sharpe={row['sharpe']:.2f}")
                    if row['win_rate'] < self.min_win_rate:
                        fails.append(f"WR={row['win_rate']:.1%}")
                    if row['total_trades'] < min_trades_tf:
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

                # Emit event for metrics tracking with combo_stats (CUMULATIVE)
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
                        combo_stats=combo_stats,
                        duration_ms=duration_ms
                    )

        return results

    @staticmethod
    def _calculate_ci(win_rate: float, n_trades: int) -> float:
        """
        Calculate Confidence Interval for win rate.

        Formula: CI = 1.96 × sqrt(WR × (1-WR) / N)

        Args:
            win_rate: Win rate (0-1)
            n_trades: Number of trades

        Returns:
            CI as decimal (e.g., 0.10 = 10% uncertainty)
        """
        if n_trades <= 0 or win_rate <= 0 or win_rate >= 1:
            return 1.0  # Max uncertainty if invalid inputs
        import math
        return 1.96 * math.sqrt(win_rate * (1 - win_rate) / n_trades)

    def _validate_oos(
        self,
        is_result: Dict,
        oos_result: Optional[Dict],
        timeframe: str
    ) -> Dict:
        """
        Validate out-of-sample performance with 6 thresholds + degradation check + CI filter.

        OOS validation applies the SAME thresholds as IS plus CI filter:
        1. sharpe >= min_sharpe (0.3)
        2. win_rate >= min_win_rate (35%)
        3. expectancy >= min_expectancy (0.002)
        4. max_drawdown <= max_drawdown (50%)
        5. trades >= min_trades_oos[timeframe]
        6. CI <= max_ci_oos (statistical significance)

        Plus degradation check: (is_sharpe - oos_sharpe) / is_sharpe <= 50%

        Note: IS thresholds are already validated before this function is called,
        so we only check OOS metrics here.

        Args:
            is_result: In-sample period backtest results (for degradation calc)
            oos_result: Out-of-sample period backtest results
            timeframe: Strategy timeframe for min_trades lookup

        Returns:
            Dict with 'passed', 'reason', 'fail_types', 'degradation', 'oos_bonus'
        """
        min_oos = self.min_trades_oos.get(timeframe, 30)

        # Get OOS metrics
        oos_trades = oos_result.get('total_trades', 0) if oos_result else 0
        oos_sharpe = oos_result.get('sharpe_ratio', 0) if oos_result else 0
        oos_win_rate = oos_result.get('win_rate', 0) if oos_result else 0
        oos_expectancy = oos_result.get('expectancy', 0) if oos_result else 0
        oos_max_drawdown = oos_result.get('max_drawdown', 0) if oos_result else 0

        # Get IS sharpe for degradation check
        is_sharpe = is_result.get('sharpe_ratio', 0)

        # Calculate degradation
        if is_sharpe > 0:
            degradation = (is_sharpe - oos_sharpe) / is_sharpe
        else:
            degradation = 0.0

        # Calculate CI for statistical significance
        oos_ci = self._calculate_ci(oos_win_rate, oos_trades)

        # CUMULATIVE threshold check (like PARAMETRIC) - count ALL violations
        fail_types = {
            'sharpe': 1 if oos_sharpe < self.min_sharpe else 0,
            'wr': 1 if oos_win_rate < self.min_win_rate else 0,
            'exp': 1 if oos_expectancy < self.min_expectancy else 0,
            'dd': 1 if oos_max_drawdown > self.max_drawdown else 0,
            'trades': 1 if oos_trades < min_oos else 0,
            'ci': 1 if oos_ci > self.max_ci_oos else 0,
            'degradation': 1 if (is_sharpe > 0 and degradation > self.oos_max_degradation) else 0,
        }

        if sum(fail_types.values()) > 0:
            # Build reason listing ALL failed thresholds
            reasons = []
            if fail_types['sharpe']:
                reasons.append(f"sharpe={oos_sharpe:.2f}<{self.min_sharpe}")
            if fail_types['wr']:
                reasons.append(f"wr={oos_win_rate:.1%}<{self.min_win_rate:.1%}")
            if fail_types['exp']:
                reasons.append(f"exp={oos_expectancy:.4f}<{self.min_expectancy}")
            if fail_types['dd']:
                reasons.append(f"dd={oos_max_drawdown:.1%}>{self.max_drawdown:.0%}")
            if fail_types['trades']:
                reasons.append(f"trades={oos_trades}<{min_oos}")
            if fail_types['ci']:
                reasons.append(f"ci={oos_ci:.1%}>{self.max_ci_oos:.0%}")
            if fail_types['degradation']:
                reasons.append(f"degradation={degradation:.0%}>{self.oos_max_degradation:.0%}")
            reason = "OOS failed: " + ", ".join(reasons)

            return {
                'passed': False,
                'reason': reason,
                'fail_types': fail_types,
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
            'fail_types': {'sharpe': 0, 'wr': 0, 'exp': 0, 'dd': 0, 'trades': 0, 'ci': 0, 'degradation': 0},
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
    ) -> Tuple[bool, str, float, float]:
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
            (passed: bool, reason: str, avg_sharpe: float, cv: float)
            - avg_sharpe: Average Sharpe ratio across windows
            - cv: Coefficient of variation (std/mean) of Sharpe ratios
        """
        try:
            # Get WFA validation config
            wfa_config = self.config._raw_config['backtesting'].get('wfa_validation', {})
            if not wfa_config.get('enabled', True):
                logger.debug(f"[{strategy.name}] WFA validation disabled, skipping")
                return (True, "wfa_disabled", 0.0, 0.0)

            window_percentages = wfa_config.get('window_percentages', [0.25, 0.50, 0.75, 1.0])
            min_profitable_windows = wfa_config.get('min_profitable_windows', 4)

            # CRITICAL: Reload strategy from DB to get updated code with optimal params
            # The strategy passed in via relationship may have stale code (loaded before
            # _update_strategy_assigned_tf committed the params update)
            from src.database.models import Strategy as StrategyModel
            with get_session() as fresh_session:
                fresh_strategy = fresh_session.query(StrategyModel).filter(
                    StrategyModel.id == strategy.id
                ).first()
                if not fresh_strategy:
                    return (False, "strategy_not_found", 0.0, 0.0)
                strategy_code = fresh_strategy.code
                strategy_trading_coins = fresh_strategy.trading_coins

            # Load strategy instance (has fixed params embedded)
            class_name = self._extract_class_name(strategy_code)
            if not class_name:
                return (False, "failed_to_extract_class_name", 0.0, 0.0)
            strategy_instance = self._load_strategy_instance(strategy_code, class_name)
            if strategy_instance is None:
                return (False, "failed_to_load_strategy", 0.0, 0.0)

            # Get symbols from strategy's trading_coins (same coins used for backtest)
            symbols = strategy_trading_coins or []
            if not symbols:
                return (False, "no_symbols_for_wfa", 0.0, 0.0)

            # Load IS data for this timeframe
            is_data = self.data_loader.load_multi_symbol(
                symbols=symbols,
                timeframe=timeframe,
                days=self.is_days
            )

            if not is_data:
                return (False, "no_is_data", 0.0, 0.0)

            # Get min_expectancy threshold from config
            min_expectancy = self.config._raw_config['backtesting']['thresholds'].get(
                'min_expectancy', 0.002
            )

            profitable_windows = 0
            window_results = []

            # DEBUG: Log params being used by WFA (read UPPERCASE first like BacktestEngine)
            wfa_sl = getattr(strategy_instance, 'SL_PCT', None) or getattr(strategy_instance, 'sl_pct', 0.02)
            wfa_tp = getattr(strategy_instance, 'TP_PCT', None) or getattr(strategy_instance, 'tp_pct', 0.04)
            wfa_lev = getattr(strategy_instance, 'LEVERAGE', None) or getattr(strategy_instance, 'leverage', 1)
            logger.info(
                f"[{strategy.name}] WFA validation: testing fixed params on "
                f"{len(window_percentages)} windows (sl={wfa_sl}, tp={wfa_tp}, lev={wfa_lev})"
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
                window_sharpe = result.get('sharpe_ratio', 0) or 0  # Handle None
                is_profitable = window_expectancy >= min_expectancy

                if is_profitable:
                    profitable_windows += 1

                window_results.append({
                    'window': window_idx + 1,
                    'pct': window_pct,
                    'expectancy': window_expectancy,
                    'sharpe': window_sharpe,
                    'profitable': is_profitable
                })

                logger.info(
                    f"[{strategy.name}] WFA window {window_idx+1}/{len(window_percentages)}: "
                    f"{window_pct:.0%} data, expectancy={window_expectancy:.4f}, "
                    f"sharpe={window_sharpe:.3f}, profitable={'YES' if is_profitable else 'NO'}"
                )

            # Calculate avg_sharpe and cv from window results
            sharpe_values = [w['sharpe'] for w in window_results]
            if sharpe_values:
                avg_sharpe = sum(sharpe_values) / len(sharpe_values)
                if len(sharpe_values) > 1 and avg_sharpe > 0:
                    # CV = coefficient of variation = std / mean
                    import statistics
                    std_sharpe = statistics.stdev(sharpe_values)
                    cv = std_sharpe / avg_sharpe
                else:
                    cv = 0.0
            else:
                avg_sharpe = 0.0
                cv = 0.0

            # Check if enough windows are profitable
            n_windows = len(window_percentages)
            if profitable_windows < min_profitable_windows:
                logger.info(
                    f"[{strategy.name}] WFA FAILED: only {profitable_windows}/{n_windows} "
                    f"windows profitable (need {min_profitable_windows})"
                )
                return (False, f"insufficient_profitable_windows:{profitable_windows}/{n_windows}", avg_sharpe, cv)

            logger.info(
                f"[{strategy.name}] WFA PASSED: {profitable_windows}/{n_windows} windows profitable, "
                f"avg_sharpe={avg_sharpe:.3f}, cv={cv:.3f}"
            )
            return (True, f"wfa_passed:{profitable_windows}/{n_windows}", avg_sharpe, cv)

        except Exception as e:
            logger.error(f"[{strategy.name}] WFA validation error: {e}")
            import traceback
            traceback.print_exc()
            return (False, f"error:{str(e)}", 0.0, 0.0)

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

    def _extract_date_range(self, data: Dict[str, pd.DataFrame]) -> tuple:
        """
        Extract start and end dates from backtest data.

        Args:
            data: Dict mapping symbol -> DataFrame with 'timestamp' column

        Returns:
            (start_date, end_date) tuple
        """
        if not data:
            return datetime.now(), datetime.now()

        all_starts = []
        all_ends = []

        for symbol, df in data.items():
            if df.empty or 'timestamp' not in df.columns:
                continue
            all_starts.append(df['timestamp'].iloc[0])
            all_ends.append(df['timestamp'].iloc[-1])

        if not all_starts:
            return datetime.now(), datetime.now()

        # Use the common range across all symbols
        start_date = max(all_starts)  # Latest start (intersection)
        end_date = min(all_ends)      # Earliest end (intersection)

        # Convert to datetime if needed
        if hasattr(start_date, 'to_pydatetime'):
            start_date = start_date.to_pydatetime()
        if hasattr(end_date, 'to_pydatetime'):
            end_date = end_date.to_pydatetime()

        return start_date, end_date

    def _save_backtest_result(
        self,
        strategy_id,
        result: Dict,
        pairs: List[str],
        timeframe: str,
        period_type: str = 'training',
        period_days: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
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
            start_date: Start date of backtest data range
            end_date: End date of backtest data range

        Returns:
            BacktestResult UUID
        """
        try:
            with get_session() as session:
                # Use provided dates or fallback to now (shouldn't happen)
                if start_date is None:
                    start_date = datetime.now()
                if end_date is None:
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

                        # Also update strategy.parameters with optimal params
                        # This ensures retest uses correct params (code is source of truth,
                        # but parameters dict is used for metrics/display)
                        # CRITICAL: Use flag_modified to ensure SQLAlchemy detects JSONB changes
                        from sqlalchemy.orm.attributes import flag_modified
                        if strategy.parameters is None:
                            strategy.parameters = {}
                        strategy.parameters['sl_pct'] = optimal_params.get('sl_pct')
                        strategy.parameters['tp_pct'] = optimal_params.get('tp_pct')
                        strategy.parameters['leverage'] = optimal_params.get('leverage')
                        strategy.parameters['exit_bars'] = optimal_params.get('exit_bars')
                        # Save sl_type/tp_type for typed strategies (for retest consistency)
                        if optimal_params.get('sl_type'):
                            strategy.parameters['sl_type'] = optimal_params.get('sl_type')
                        if optimal_params.get('tp_type'):
                            strategy.parameters['tp_type'] = optimal_params.get('tp_type')
                        flag_modified(strategy, 'parameters')

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
                    r'class\s+((?:Strategy|PatStrat|UngStrat|UggStrat|AIFStrat|AIAStrat|PGnStrat|PGgStrat|PtaStrat)_\w+)\s*\(',
                    f'class {new_class_name}(',
                    updated
                )

            # Update sl_pct (lowercase for AI templates)
            if 'sl_pct' in params:
                updated = re.sub(
                    r'(\s+sl_pct\s*=\s*)[\d.]+',
                    rf'\g<1>{params["sl_pct"]}',
                    updated
                )
                # Also update SL_PCT (uppercase for pattern_gen/unger/pandas_ta templates)
                updated = re.sub(
                    r'(\s+SL_PCT\s*=\s*)[\d.]+',
                    rf'\g<1>{params["sl_pct"]}',
                    updated
                )

            # Update tp_pct (lowercase for AI templates)
            if 'tp_pct' in params:
                updated = re.sub(
                    r'(\s+tp_pct\s*=\s*)[\d.]+',
                    rf'\g<1>{params["tp_pct"]}',
                    updated
                )
                # Also update TP_PCT (uppercase for pattern_gen/unger/pandas_ta templates)
                updated = re.sub(
                    r'(\s+TP_PCT\s*=\s*)[\d.]+',
                    rf'\g<1>{params["tp_pct"]}',
                    updated
                )

            # Update leverage (lowercase for AI templates)
            if 'leverage' in params:
                updated = re.sub(
                    r'(\s+leverage\s*=\s*)\d+',
                    rf'\g<1>{int(params["leverage"])}',
                    updated
                )
                # Also update LEVERAGE (uppercase for pattern_gen template)
                updated = re.sub(
                    r'(\s+LEVERAGE\s*=\s*)\d+',
                    rf'\g<1>{int(params["leverage"])}',
                    updated
                )

            # Update exit_after_bars (lowercase for AI templates that use exit_after_bars = N)
            if 'exit_bars' in params:
                updated = re.sub(
                    r'(\s+exit_after_bars\s*=\s*)\d+',
                    rf'\g<1>{int(params["exit_bars"])}',
                    updated
                )
                # Also update EXIT_BARS (uppercase for pattern_gen template)
                # Pattern: EXIT_BARS = N  (then exit_after_bars = EXIT_BARS references it)
                updated = re.sub(
                    r'(\s+EXIT_BARS\s*=\s*)\d+',
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
        """Extract class name from strategy code (supports all prefixes)"""
        import re
        match = re.search(r'class\s+((?:Strategy|PatStrat|UngStrat|UggStrat|AIFStrat|AIAStrat|PGnStrat|PGgStrat|PtaStrat)_\w+)\s*\(', code)
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
        """Delete failed strategy (removes from DB entirely)"""
        self.processor.mark_failed(strategy_id, reason, delete=True)

    def _fail_strategy(self, strategy_id, reason: str):
        """Mark strategy as FAILED but keep in DB (preserves BacktestResults for metrics)"""
        self.processor.mark_failed(strategy_id, reason, delete=False)

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
                    'trading_coins': strategy.trading_coins,
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

            # CRITICAL: Apply stored optimized parameters from database
            # The code contains template defaults, but optimal params are in strategy.parameters
            # For typed strategies: sl_type/tp_type are preserved from original strategy
            # For percentage strategies: sl_type defaults to PERCENTAGE
            with get_session() as param_session:
                strategy_record = param_session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()
                if strategy_record and strategy_record.parameters:
                    stored_params = strategy_record.parameters

                    # Apply sl_type: use stored if present, else PERCENTAGE
                    stored_sl_type = stored_params.get('sl_type')
                    if stored_sl_type:
                        # Typed strategy: preserve original sl_type
                        try:
                            strategy_instance.sl_type = StopLossType(stored_sl_type)
                        except ValueError:
                            strategy_instance.sl_type = StopLossType.PERCENTAGE
                    else:
                        # Legacy/percentage strategy
                        strategy_instance.sl_type = StopLossType.PERCENTAGE

                    strategy_instance.SL_PCT = stored_params.get('sl_pct', 0.02)
                    strategy_instance.TP_PCT = stored_params.get('tp_pct', 0.04)
                    strategy_instance.LEVERAGE = stored_params.get('leverage', 1)
                    strategy_instance.exit_after_bars = stored_params.get('exit_bars', 0)
                    logger.info(
                        f"[{strategy_name}] RETEST: Applied stored params: "
                        f"SL={stored_params.get('sl_pct'):.2%}, TP={stored_params.get('tp_pct'):.2%}, "
                        f"Lev={stored_params.get('leverage')}, Exit={stored_params.get('exit_bars')}, "
                        f"sl_type={strategy_instance.sl_type.value}"
                    )

            # Validate pairs (same 3-level validation as initial backtest)
            validated_pairs, status = self._scroll_down_coverage(
                coins=pairs,
                timeframe=assigned_tf,
                target_count=len(pairs)
            )

            if validated_pairs is None:
                logger.warning(f"[{strategy_name}] RETEST: pairs validation failed ({status})")
                # Mark strategy for retirement (data quality degraded)
                self.pool_manager._retire_strategy(
                    strategy_id,
                    f"Re-test failed: {status}",
                    "retest_failed"
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
                self.pool_manager._retire_strategy(strategy_id, f"Re-test OOS: {validation['reason']}", "retest_failed")
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
            is_start, is_end = self._extract_date_range(is_data)
            self._save_backtest_result(
                strategy_id, is_result, validated_pairs, assigned_tf,
                period_type='in_sample', period_days=self.is_days,
                start_date=is_start, end_date=is_end
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

    def _calculate_robustness(
        self,
        strategy: Strategy,
        is_sharpe: float,
        oos_sharpe: float,
        is_trades: int,
        oos_trades: int,
    ) -> float:
        """
        Calculate robustness score for strategy (0-1).

        Components:
        - OOS/IS ratio (50%): How well strategy generalizes to unseen data
        - Trade significance (35%): Statistical reliability from trade count
        - Simplicity (15%): Fewer indicators = less overfitting risk

        Args:
            strategy: Strategy object (for indicator count)
            is_sharpe: In-sample Sharpe ratio
            oos_sharpe: Out-of-sample Sharpe ratio
            is_trades: In-sample trade count
            oos_trades: Out-of-sample trade count

        Returns:
            Robustness score between 0 and 1
        """
        robustness_config = self.config.get('backtesting.robustness')
        weights = robustness_config['weights']
        trade_target = robustness_config['trade_significance_target']

        # 1. OOS/IS ratio (closer to 1 = less overfit)
        if is_sharpe > 0:
            oos_ratio = min(1.0, max(0, oos_sharpe / is_sharpe))
        else:
            oos_ratio = 0.0

        # 2. Trade significance (more trades = more reliable)
        total_trades = is_trades + oos_trades
        trade_score = min(1.0, total_trades / trade_target)

        # 3. Simplicity (fewer indicators = less overfit)
        # Count indicators from strategy parameters
        params = strategy.parameters or {}
        entry_indicators = params.get('entry_indicators', [])
        entry_conditions = params.get('entry_conditions', [])
        num_indicators = len(entry_indicators) if entry_indicators else len(entry_conditions) if entry_conditions else 1
        simplicity = 1.0 / num_indicators if num_indicators > 0 else 0.5

        # Weighted robustness score
        robustness = (
            weights['oos_ratio'] * oos_ratio +
            weights['trade_significance'] * trade_score +
            weights['simplicity'] * simplicity
        )

        return robustness

    def _promote_to_active_pool(
        self,
        strategy_id: UUID,
        backtest_result: BacktestResult,
        backtest_start_time: Optional[float] = None,
        degradation: float = 0.0,
        combinations_tested: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Attempt to promote a strategy to the ACTIVE pool after backtest.

        Flow:
        1. Calculate score from backtest result (5-component formula)
        2. If score < min_score -> reject (no shuffle test needed)
        3. Run shuffle test (lookahead bias detection)
        4. If shuffle fails -> reject
        5. Run WFA validation with fixed params (per-strategy)
        6. If WFA fails -> reject
        7. Try to enter pool (leaderboard logic)

        Args:
            strategy_id: Strategy UUID
            backtest_result: BacktestResult with training period metrics
            backtest_start_time: Start time for duration calculation
            degradation: Holdout degradation [-0.5, +0.5] for recency component
            combinations_tested: Number of parametric combinations tested (for metrics)

        Returns:
            (success, reason) tuple
        """
        from src.database.event_tracker import EventTracker

        try:
            # Calculate backtest duration
            duration_ms = None
            if backtest_start_time is not None:
                duration_ms = int((time.time() - backtest_start_time) * 1000)

            # Calculate score using 5-component formula
            score = self.scorer.score_from_backtest_result(
                backtest_result, degradation
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
            wfa_start = time.time()
            wfa_passed, wfa_reason, wfa_avg_sharpe, wfa_cv = self._run_wfa_fixed_params(
                strategy, strategy.optimal_timeframe
            )
            wfa_duration_ms = int((time.time() - wfa_start) * 1000)

            if not wfa_passed:
                EventTracker.multi_window_failed(
                    strategy_id=strategy_id,
                    strategy_name=strategy_name,
                    reason=wfa_reason,
                    duration_ms=wfa_duration_ms,
                    base_code_hash=base_hash
                )
                logger.info(f"[{strategy_name}] WFA validation failed: {wfa_reason}")
                return (False, f"wfa_validation_failed:{wfa_reason}")

            # WFA passed - emit event with calculated avg_sharpe and cv
            EventTracker.multi_window_passed(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                avg_sharpe=wfa_avg_sharpe,
                cv=wfa_cv,
                duration_ms=wfa_duration_ms,
                base_code_hash=base_hash
            )

            # === ROBUSTNESS CHECK (final gate before pool entry) ===
            # Query IS and OOS backtest results for robustness calculation
            with get_session() as session:
                is_bt = session.query(BacktestResult).filter(
                    BacktestResult.strategy_id == strategy_id,
                    BacktestResult.period_type == 'in_sample'
                ).first()
                oos_bt = session.query(BacktestResult).filter(
                    BacktestResult.strategy_id == strategy_id,
                    BacktestResult.period_type == 'out_of_sample'
                ).first()

                # Get metrics for robustness calculation
                is_sharpe = is_bt.sharpe_ratio if is_bt else 0
                oos_sharpe = oos_bt.sharpe_ratio if oos_bt else 0
                is_trades = is_bt.total_trades if is_bt else 0
                oos_trades = oos_bt.total_trades if oos_bt else 0

            # Calculate robustness score
            robustness = self._calculate_robustness(
                strategy, is_sharpe, oos_sharpe, is_trades, oos_trades
            )

            # Store robustness in strategy
            with get_session() as session:
                strat = session.query(Strategy).filter(Strategy.id == strategy_id).first()
                if strat:
                    strat.robustness_score = robustness
                    session.commit()

            # Check robustness threshold
            min_robustness = self.config.get('backtesting.robustness.min_threshold')

            if robustness < min_robustness:
                EventTracker.emit(
                    strategy_id=strategy_id,
                    strategy_name=strategy_name,
                    stage='robustness_check',
                    event_type='robustness_failed',
                    status='failed',
                    event_data={
                        'robustness': round(robustness, 3),
                        'threshold': min_robustness,
                        'oos_is_ratio': round(oos_sharpe / is_sharpe, 3) if is_sharpe > 0 else 0,
                        'is_sharpe': round(is_sharpe, 3),
                        'oos_sharpe': round(oos_sharpe, 3),
                        'total_trades': is_trades + oos_trades,
                    },
                    base_code_hash=base_hash
                )
                logger.info(
                    f"[{strategy_name}] Robustness check failed: "
                    f"{robustness:.2f} < {min_robustness} "
                    f"(OOS/IS={oos_sharpe/is_sharpe:.2f if is_sharpe > 0 else 0})"
                )
                return (False, f"robustness_below_threshold:{robustness:.2f}")

            # Robustness passed
            EventTracker.emit(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                stage='robustness_check',
                event_type='robustness_passed',
                status='passed',
                event_data={'robustness': round(robustness, 3)},
                base_code_hash=base_hash
            )
            logger.debug(f"[{strategy_name}] Robustness check passed: {robustness:.2f}")

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
    def funding_loader(self) -> FundingLoader:
        """Lazy init FundingLoader for funding rate data"""
        if self._funding_loader is None:
            self._funding_loader = FundingLoader()
        return self._funding_loader

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
        Run shuffle test on strategy to detect lookahead bias.

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

        EventTracker.shuffle_test_started(
            strategy_id, strategy.name, base_code_hash=base_code_hash
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

            if result.passed:
                logger.debug(f"[{strategy.name}] Shuffle test PASSED")
                EventTracker.shuffle_test_passed(
                    strategy_id, strategy.name,
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

        # STEP 2: Warm up Numba kernels to avoid compilation delay on first use
        logger.info("Warming up Numba kernels...")
        from src.backtester.numba_kernels import warmup_numba_kernels
        warmup_numba_kernels()
        logger.info("Numba kernels ready")

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Backtester process terminated")
