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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import importlib.util
import tempfile
import sys

from src.config import load_config
from src.database import get_session, Strategy, BacktestResult, StrategyProcessor
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.data_loader import BacktestDataLoader
from src.data.pairs_updater import get_current_pairs
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file='logs/backtester.log',
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousBacktesterProcess:
    """
    Continuous backtesting process.

    Claims VALIDATED strategies and runs multi-pair VectorBT backtests.
    Tests all timeframes and selects optimal TF.
    Strategies that pass thresholds are promoted to TESTED.
    """

    def __init__(self):
        """Initialize the backtester process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from backtesting section)
        backtesting_config = self.config.get('backtesting', {})
        self.parallel_threads = backtesting_config.get('parallel_threads', 10)

        # Pipeline backpressure configuration (downstream = TESTED queue)
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        backpressure_config = pipeline_config.get('backpressure', {})
        monitoring_config = pipeline_config.get('monitoring', {})

        self.tested_limit = queue_limits.get('tested', 30)
        self.base_cooldown = backpressure_config.get('base_cooldown', 30)
        self.max_cooldown = backpressure_config.get('max_cooldown', 120)
        self.cooldown_increment = backpressure_config.get('cooldown_increment', 2)
        self.log_interval = monitoring_config.get('log_interval', 30)
        self._last_log_time = datetime.min

        # ThreadPoolExecutor for parallel backtesting
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Backtester"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}

        # Components
        self.engine = BacktestEngine(self.config)
        # Use data.cache_dir (where BinanceDataDownloader saves files) or default to data/binance
        cache_dir = self.config.get('data', {}).get('cache_dir', 'data/binance')
        self.data_loader = BacktestDataLoader(cache_dir)
        self.processor = StrategyProcessor(process_id=f"backtester-{os.getpid()}")

        # Backtest thresholds
        bt_config = self.config.get('backtesting', {})
        thresholds = bt_config.get('thresholds', {})
        self.min_sharpe = thresholds.get('min_sharpe', 1.0)
        self.min_win_rate = thresholds.get('min_win_rate', 0.55)
        self.max_drawdown = thresholds.get('max_drawdown', 0.30)
        self.min_trades = thresholds.get('min_total_trades', 100)
        self.min_expectancy = thresholds.get('min_expectancy', 0.02)

        # Timeframes
        self.timeframes = self.config.get('trading', {}).get('timeframes', {}).get('available', ['15m', '1h', '4h'])

        # Pairs count (from backtesting section, NOT data_scheduler)
        self.pairs_count = bt_config.get('backtest_pairs_count', 100)

        # Training/Holdout configuration (unified approach)
        self.training_days = bt_config.get('training_days', 365)
        self.holdout_days = bt_config.get('holdout_days', 30)

        # Holdout validation thresholds
        holdout_config = bt_config.get('holdout', {})
        self.holdout_max_degradation = holdout_config.get('max_degradation', 0.50)
        self.holdout_min_sharpe = holdout_config.get('min_sharpe', 0.3)
        self.holdout_recency_weight = holdout_config.get('recency_weight', 0.60)

        # Preloaded data cache: {(symbols_hash, timeframe): data}
        self._data_cache: Dict[str, Dict[str, any]] = {}

        logger.info(
            f"ContinuousBacktesterProcess initialized: "
            f"{self.parallel_threads} threads, {len(self.timeframes)} TFs, {self.pairs_count} pairs, "
            f"downstream limit {self.tested_limit} TESTED"
        )

    def _get_backtest_pairs(self) -> List[str]:
        """
        Load top N pairs from database (coins table).

        Returns:
            List of symbol names (e.g., ['BTC', 'ETH', ...])
        """
        pairs = get_current_pairs()

        if not pairs:
            logger.warning("No pairs in database, using default pairs")
            return ['BTC', 'ETH', 'SOL', 'ARB', 'AVAX']

        # Take top N pairs
        pairs = pairs[:self.pairs_count]

        logger.info(f"Loaded {len(pairs)} pairs from database")
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

        # Level 1: Liquidity filter (active trading pairs from DB)
        active_coins = set(get_current_pairs())
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
                strategy_id = self.active_futures.pop(future)
                try:
                    success, reason = future.result()
                    if success:
                        logger.info(f"Strategy {strategy_id} TESTED")
                    else:
                        logger.info(f"Strategy {strategy_id} FAILED: {reason}")
                except Exception as e:
                    logger.error(f"Backtest error for {strategy_id}: {e}")

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
            self.active_futures[future] = str(strategy.id)

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
                    training_result = self._run_multi_symbol_backtest(
                        strategy_instance, training_data, tf
                    )
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

            # Update strategy with optimal TF and its validated coins
            self._update_strategy_optimal_tf(strategy_id, optimal_tf, optimal_tf_coins)

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
            result = self.engine.backtest_portfolio(
                strategy=strategy_instance,
                data=valid_data,
                max_positions=None  # Uses config value
            )
            return result
        except Exception as e:
            import traceback
            logger.error(f"Portfolio backtest failed: {e}\n{traceback.format_exc()}")
            return {'total_trades': 0}

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

        Returns:
            Dict with 'passed', 'reason', 'degradation', 'holdout_bonus'
        """
        training_sharpe = training_result.get('sharpe_ratio', 0)

        # If no holdout data, pass but with neutral score
        if holdout_result is None or holdout_result.get('total_trades', 0) == 0:
            return {
                'passed': True,
                'reason': 'No holdout data (neutral)',
                'degradation': 0.0,
                'holdout_bonus': 0.0,
            }

        holdout_sharpe = holdout_result.get('sharpe_ratio', 0)

        # Calculate degradation (how much worse is holdout vs training)
        if training_sharpe > 0:
            degradation = (training_sharpe - holdout_sharpe) / training_sharpe
        else:
            degradation = 0.0 if holdout_sharpe >= 0 else 1.0

        # Anti-overfitting check: reject if holdout crashes
        if degradation > self.holdout_max_degradation:
            return {
                'passed': False,
                'reason': f'Overfitted: holdout {degradation:.0%} worse than training',
                'degradation': degradation,
                'holdout_bonus': 0.0,
            }

        # Check minimum holdout Sharpe
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
        training_score = (
            0.5 * training_sharpe +
            0.3 * training_expectancy * 100 +
            0.2 * training_win_rate
        )

        # Get holdout metrics
        if holdout_result and holdout_result.get('total_trades', 0) > 0:
            holdout_sharpe = holdout_result.get('sharpe_ratio', 0)
            holdout_win_rate = holdout_result.get('win_rate', 0)
            holdout_expectancy = holdout_result.get('expectancy', 0)

            holdout_score = (
                0.5 * holdout_sharpe +
                0.3 * holdout_expectancy * 100 +
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

                bt_result = BacktestResult(
                    strategy_id=strategy_id,
                    lookback_days=period_days,
                    initial_capital=self.config.get('backtesting', {}).get('initial_capital', 10000),
                    start_date=start_date,
                    end_date=end_date,

                    # Aggregate metrics
                    total_trades=result.get('total_trades', 0),
                    win_rate=result.get('win_rate'),
                    sharpe_ratio=result.get('sharpe_ratio'),
                    expectancy=result.get('expectancy'),
                    max_drawdown=result.get('max_drawdown'),
                    final_equity=result.get('final_equity'),
                    total_return_pct=result.get('total_return'),

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
        pairs: List[str]
    ):
        """Update strategy with optimal TF and audit trail"""
        try:
            with get_session() as session:
                strategy = session.query(Strategy).filter(
                    Strategy.id == strategy_id
                ).first()

                if strategy:
                    strategy.optimal_timeframe = optimal_tf
                    strategy.backtest_pairs = pairs
                    strategy.backtest_date = datetime.utcnow()
                    strategy.tested_at = datetime.utcnow()
                    session.commit()

                    logger.info(
                        f"Updated strategy {strategy.name}: "
                        f"optimal_tf={optimal_tf}, pairs={len(pairs)}"
                    )
        except Exception as e:
            logger.error(f"Failed to update strategy: {e}")

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
