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
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import importlib.util
import tempfile
import sys

from src.config import load_config
from src.database import get_session, Strategy, BacktestResult, StrategyProcessor
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.backtester.parametric_backtest import ParametricBacktester
from src.data.coin_registry import get_registry, get_active_pairs
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

        # Process configuration - NO defaults (Fast Fail principle)
        self.parallel_threads = self.config.get_required('backtesting.parallel_threads')

        # Pipeline backpressure configuration (downstream = TESTED queue)
        self.tested_limit = self.config.get_required('pipeline.queue_limits.tested')
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

        # Tracking: Future -> (strategy_id, strategy_name)
        self.active_futures: Dict[Future, Tuple[str, str]] = {}

        # Components - use injected or create new (Dependency Injection pattern)
        self.engine = engine or BacktestEngine(self.config._raw_config)
        cache_dir = self.config.get_required('directories.data') + '/binance'
        self.data_loader = data_loader or BacktestDataLoader(cache_dir)
        self.processor = processor or StrategyProcessor(process_id=f"backtester-{os.getpid()}")

        # Parametric backtester - use injected or create new (Dependency Injection)
        self.parametric_enabled = self.config.get_required('generation.parametric.enabled')
        self.parametric_top_k = self.config.get_required('generation.parametric.top_k')
        if self.parametric_enabled:
            self.parametric_backtester = parametric_backtester or ParametricBacktester(self.config._raw_config)
            # Override parameter space from config if provided (only if we created it)
            if parametric_backtester is None:
                param_space = self.config.get('generation.parametric.parameter_space', {})
                if param_space:
                    self.parametric_backtester.set_parameter_space(param_space)
            logger.info(
                f"Parametric backtesting ENABLED: "
                f"{self.parametric_backtester._count_combinations()} combinations, "
                f"top {self.parametric_top_k} saved"
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

        # Holdout validation thresholds
        self.holdout_max_degradation = self.config.get_required('backtesting.holdout.max_degradation')
        self.holdout_min_sharpe = self.config.get_required('backtesting.holdout.min_sharpe')
        self.holdout_recency_weight = self.config.get_required('backtesting.holdout.recency_weight')
        self.min_holdout_trades = self.config.get_required('backtesting.holdout.min_trades')

        # Initial capital for expectancy normalization
        self.initial_capital = self.config.get_required('backtesting.initial_capital')

        # Preloaded data cache: {(symbols_hash, timeframe): data}
        self._data_cache: Dict[str, Dict[str, any]] = {}

        # CoinRegistry handles caching and invalidation
        # No need for local pairs cache anymore

        logger.info(
            f"ContinuousBacktesterProcess initialized: "
            f"{self.parallel_threads} threads, {len(self.timeframes)} TFs, {self.max_coins} coins, "
            f"downstream limit {self.tested_limit} TESTED"
        )

    def _get_backtest_pairs(self) -> List[str]:
        """
        Load top N pairs from CoinRegistry.

        CoinRegistry handles:
        - Caching with automatic invalidation
        - Volume filtering (min $1M by default)
        - Sorting by volume descending

        Returns:
            List of symbol names (e.g., ['BTC', 'ETH', ...])
        """
        pairs = get_active_pairs(limit=self.max_coins)

        if not pairs:
            logger.warning("No pairs in CoinRegistry, using default pairs")
            return ['BTC', 'ETH', 'SOL', 'ARB', 'AVAX']

        return pairs

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
        ).get('min_tradable_coins', 10)

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

        # Level 3: Coverage filter (>= 90% data for training+holdout period)
        total_days = self.training_days + self.holdout_days
        min_coverage = 0.90

        validated_coins = []
        for coin in cached_coins:
            info = cache_reader.get_cache_info(coin, timeframe)
            if info and info.get('days', 0) >= total_days * min_coverage:
                validated_coins.append(coin)

            if len(validated_coins) >= min_coins * 2:
                # Have enough, stop checking (preserve edge order)
                break

        if len(validated_coins) < min_coins:
            logger.warning(
                f"Coverage filter: {len(validated_coins)}/{len(cached_coins)} coins with "
                f">= {min_coverage:.0%} coverage for {total_days}d (need {min_coins})"
            )
            return None, f"insufficient_coverage:{len(validated_coins)}/{min_coins}"

        logger.info(
            f"Validated {len(validated_coins)} pattern coins "
            f"(from {len(pattern_coins)} original, {min_coins} required)"
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
        training_cache_key = f"{timeframe}_training"
        holdout_cache_key = f"{timeframe}_holdout"

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
                holdout_days=self.holdout_days
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
                f"TST={depths.get('TESTED', 0)}/{self.tested_limit} "
                f"LIVE={depths.get('LIVE', 0)}"
            )
            self._last_log_time = now
        except Exception as e:
            logger.debug(f"Failed to log pipeline status: {e}")

    async def run_continuous(self):
        """Main continuous backtesting loop with downstream backpressure"""
        logger.info("Starting continuous backtesting loop (with downstream backpressure)")

        while not self.shutdown_event.is_set() and not self.force_exit:
            # Log pipeline status periodically
            self._log_pipeline_status()

            # Process completed backtests first (free up slots)
            done_futures = []
            for f in list(self.active_futures.keys()):
                if f.done():
                    done_futures.append(f)

            for future in done_futures:
                strategy_id, strategy_name = self.active_futures.pop(future)
                try:
                    success, reason = future.result()
                    if success:
                        logger.info(f"Strategy {strategy_name} TESTED")
                    else:
                        logger.info(f"Strategy {strategy_name} FAILED: {reason}")
                except Exception as e:
                    logger.error(f"Backtest error for {strategy_name}: {e}")

            # Check downstream backpressure (TESTED queue)
            tested_count = self.processor.count_available("TESTED")
            if tested_count >= self.tested_limit:
                cooldown = self.processor.calculate_backpressure_cooldown(
                    tested_count,
                    self.tested_limit,
                    self.base_cooldown,
                    self.cooldown_increment,
                    self.max_cooldown
                )
                logger.info(
                    f"Downstream backpressure: {tested_count} TESTED "
                    f"(limit {self.tested_limit}), waiting {cooldown}s"
                )
                await asyncio.sleep(cooldown)
                continue

            # Only claim new strategies if we have free worker slots
            # This prevents claiming more strategies than we can process
            if len(self.active_futures) >= self.parallel_threads:
                # All workers busy, wait before checking again
                await asyncio.sleep(1)
                continue

            # Claim a strategy for backtesting
            strategy = self.processor.claim_strategy("VALIDATED")

            if strategy is None:
                # No strategies to backtest, wait and retry
                await asyncio.sleep(5)
                continue

            # Submit backtest task
            future = self.executor.submit(
                self._backtest_strategy_all_tf,
                strategy.id,
                strategy.name,
                strategy.code,
                strategy.timeframe,
                strategy.pattern_coins
            )
            self.active_futures[future] = (str(strategy.id), strategy.name)

            await asyncio.sleep(0.1)

        logger.info("Backtesting loop ended")

    def _backtest_strategy_all_tf(
        self,
        strategy_id,
        strategy_name: str,
        code: str,
        original_tf: str,
        pattern_coins: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Run training/holdout backtest on all timeframes and select optimal TF.

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

            for tf in self.timeframes:
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
                    # Non-pattern strategy: use volume-based pairs
                    pairs = self._get_backtest_pairs()
                    if not pairs:
                        logger.warning(f"[{strategy_name}] {tf}: No pairs available")
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
                    if self.parametric_enabled:
                        # Parametric: test multiple SL/TP/leverage combinations
                        # Pass is_pattern_based to select appropriate parameter space
                        is_pattern_based = pattern_coins is not None and len(pattern_coins) > 0
                        parametric_results = self._run_parametric_backtest(
                            strategy_instance, training_data, tf, is_pattern_based
                        )
                        if not parametric_results:
                            logger.warning(f"No parametric results for {tf}")
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
                holdout_result = None
                try:
                    if holdout_data and len(holdout_data) >= 5:
                        holdout_result = self._run_multi_symbol_backtest(
                            strategy_instance, holdout_data, tf
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

                # Save training backtest result
                training_backtest_id = self._save_backtest_result(
                    strategy_id, training_result, pairs, tf,
                    is_optimal=False,
                    period_type='training',
                    period_days=self.training_days
                )

                # Save holdout backtest result
                holdout_backtest_id = None
                if holdout_result and holdout_result.get('total_trades', 0) > 0:
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

            # Mark optimal backtest
            if optimal_tf in tf_backtest_ids:
                self._mark_optimal_backtest(tf_backtest_ids[optimal_tf])

            # Promote to TESTED
            self.processor.release_strategy(strategy_id, "TESTED")

            optimal_result = tf_results[optimal_tf]
            return (
                True,
                f"Optimal TF: {optimal_tf}, "
                f"Final Score {optimal_result.get('final_score', 0):.2f}, "
                f"Trades {optimal_result.get('total_trades', 0)}"
            )

        except Exception as e:
            logger.error(f"Backtest error for {strategy_name}: {e}", exc_info=True)
            self.processor.mark_failed(strategy_id, str(e), delete=True)
            return (False, str(e))

    def _run_multi_symbol_backtest(
        self,
        strategy_instance,
        data: Dict[str, any],
        timeframe: str
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

        Returns:
            Portfolio metrics with position-limited simulation
        """
        # Filter out empty/insufficient data
        valid_data = {
            symbol: df for symbol, df in data.items()
            if not df.empty and len(df) >= 100
        }

        if not valid_data:
            return {'total_trades': 0}

        # Use backtest_portfolio for realistic position-limited simulation
        try:
            result = self.engine.backtest(
                strategy=strategy_instance,
                data=valid_data,
                max_positions=None  # Uses config value
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
        Run parametric backtest testing multiple SL/TP/leverage/exit combinations.

        Extracts entry signals from the strategy once, then tests N parameter
        combinations using the Numba-optimized ParametricBacktester.

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
            # AI STRATEGY: use absolute ranges for crypto
            space = self.parametric_backtester.build_absolute_space()

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
            logger.warning("No entry signals found for parametric backtest")
            return []

        logger.info(
            f"Running parametric backtest: {n_bars} bars, {n_symbols} symbols, "
            f"{total_signals} signals, {self.parametric_backtester._count_combinations()} combinations"
        )

        # Run parametric backtest
        try:
            results_df = self.parametric_backtester.backtest_pattern(
                pattern_signals=entries_2d,
                ohlc_data={'close': close_2d, 'high': high_2d, 'low': low_2d},
                directions=directions_2d,
            )
        except Exception as e:
            logger.error(f"Parametric backtest failed: {e}")
            return []

        # Get top K results
        top_results = self.parametric_backtester.get_top_k(results_df, self.parametric_top_k)

        # Convert to list of dicts matching expected format
        # Use float() to convert np.float64 to native Python float (required for DB)
        results = []
        for _, row in top_results.iterrows():
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
                f"Parametric backtest complete: {len(results)} combinations passed | "
                f"Best: Sharpe={best['sharpe_ratio']:.2f}, Trades={best['total_trades']}, "
                f"SL={best['params']['sl_pct']:.1%}, TP={best['params']['tp_pct']:.1%}"
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

        # Calculate training base score
        # Normalize expectancy to percentage of initial capital
        training_expectancy_pct = (training_expectancy / self.initial_capital) * 100 if self.initial_capital > 0 else 0

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

            # Normalize expectancy to percentage of initial capital
            holdout_expectancy_pct = (holdout_expectancy / self.initial_capital) * 100 if self.initial_capital > 0 else 0
            holdout_score = (
                0.5 * holdout_sharpe +
                0.3 * holdout_expectancy_pct +
                0.2 * holdout_win_rate
            )
        else:
            holdout_sharpe = 0
            holdout_win_rate = 0
            holdout_expectancy = 0
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
                    # Link to holdout result
                    if holdout_backtest_id:
                        bt.recent_result_id = holdout_backtest_id

                    # Store final metrics (reuse existing columns)
                    bt.weighted_sharpe = final_result.get('final_score')
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
        """Extract class name from strategy code"""
        import re
        match = re.search(r'class\s+(Strategy_\w+)\s*\(', code)
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
            logger.info("Backtester process terminated")
