"""
Continuous Backtester Process

Backtests validated strategies using VectorBT.
- Multi-pair backtesting (top 100 coins by volume)
- Timeframe optimization (test all TFs, select optimal)
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
from src.backtester.vectorbt_engine import VectorBTBacktester
from src.backtester.data_loader import BacktestDataLoader
from src.data.pairs_updater import get_current_pairs
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
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

        # Process configuration
        proc_config = self.config.get('processes', {}).get('backtester', {})
        self.parallel_threads = proc_config.get('parallel_threads', 10)

        # ThreadPoolExecutor for parallel backtesting
        self.executor = ThreadPoolExecutor(
            max_workers=self.parallel_threads,
            thread_name_prefix="Backtester"
        )

        # Tracking
        self.active_futures: Dict[Future, str] = {}

        # Components
        self.engine = VectorBTBacktester(self.config)
        cache_dir = self.config.get('directories', {}).get('data', 'data')
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

        # Dual period configuration
        self.lookback_days = bt_config.get('lookback_days', 180)
        self.recent_period_days = bt_config.get('recent_period_days', 60)
        self.full_period_weight = bt_config.get('full_period_weight', 0.60)
        self.recent_period_weight = bt_config.get('recent_period_weight', 0.40)

        # Preloaded data cache: {(symbols_hash, timeframe): data}
        self._data_cache: Dict[str, Dict[str, any]] = {}

        logger.info(
            f"ContinuousBacktesterProcess initialized: "
            f"{self.parallel_threads} threads, {len(self.timeframes)} TFs, {self.pairs_count} pairs"
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

    def _get_multi_symbol_data(self, pairs: List[str], timeframe: str) -> Dict[str, any]:
        """
        Get multi-symbol data (cached)

        Args:
            pairs: List of symbol names
            timeframe: Timeframe to load

        Returns:
            Dict mapping symbol -> DataFrame
        """
        cache_key = f"{timeframe}_full"

        if cache_key not in self._data_cache:
            try:
                data = self.data_loader.load_multi_symbol(
                    pairs, timeframe, self.lookback_days
                )
                self._data_cache[cache_key] = data
                logger.info(f"Loaded {len(data)} symbols for {timeframe}")
            except Exception as e:
                logger.error(f"Failed to load multi-symbol data for {timeframe}: {e}")
                return {}

        return self._data_cache.get(cache_key, {})

    def _get_dual_period_data(
        self,
        pairs: List[str],
        timeframe: str
    ) -> Tuple[Dict[str, any], Dict[str, any]]:
        """
        Get dual-period data (full + recent) for multi-symbol backtesting

        Args:
            pairs: List of symbol names
            timeframe: Timeframe to load

        Returns:
            Tuple of (full_data_dict, recent_data_dict)
        """
        full_cache_key = f"{timeframe}_full"
        recent_cache_key = f"{timeframe}_recent"

        # Check if both are cached
        if full_cache_key in self._data_cache and recent_cache_key in self._data_cache:
            return (
                self._data_cache[full_cache_key],
                self._data_cache[recent_cache_key]
            )

        try:
            full_data, recent_data = self.data_loader.load_multi_symbol_dual_periods(
                symbols=pairs,
                timeframe=timeframe,
                full_period_days=self.lookback_days,
                recent_period_days=self.recent_period_days
            )

            self._data_cache[full_cache_key] = full_data
            self._data_cache[recent_cache_key] = recent_data

            logger.info(
                f"Loaded dual-period data for {timeframe}: "
                f"{len(full_data)} symbols (full), {len(recent_data)} symbols (recent)"
            )

            return full_data, recent_data

        except Exception as e:
            logger.error(f"Failed to load dual-period data for {timeframe}: {e}")
            return {}, {}

    async def run_continuous(self):
        """Main continuous backtesting loop"""
        logger.info("Starting continuous backtesting loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
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
                strategy.timeframe
            )
            self.active_futures[future] = str(strategy.id)

            # Process completed backtests
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

            await asyncio.sleep(0.1)

        logger.info("Backtesting loop ended")

    def _backtest_strategy_all_tf(
        self,
        strategy_id,
        strategy_name: str,
        code: str,
        original_tf: str
    ) -> Tuple[bool, str]:
        """
        Run dual-period backtest on all timeframes and select optimal TF.

        Dual-period backtesting:
        1. Backtest on FULL period (e.g., 180 days)
        2. Backtest on RECENT period (e.g., 60 days)
        3. Calculate weighted score: 60% full + 40% recent
        4. Apply recency penalty if recent << full

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

            # Load pairs
            pairs = self._get_backtest_pairs()
            if not pairs:
                self._delete_strategy(strategy_id, "No pairs available")
                return (False, "No pairs available")

            # Test all timeframes with dual-period backtesting
            tf_results = {}
            tf_backtest_ids = {}

            for tf in self.timeframes:
                logger.info(f"[{strategy_name}] Testing {tf} on {len(pairs)} pairs (dual period)...")

                # Load dual-period data
                full_data, recent_data = self._get_dual_period_data(pairs, tf)

                if not full_data or len(full_data) < 5:
                    logger.warning(f"Insufficient data for {tf}, skipping")
                    continue

                # Run FULL period backtest
                try:
                    full_result = self._run_multi_symbol_backtest(
                        strategy_instance, full_data, tf
                    )
                except Exception as e:
                    logger.error(f"Full period backtest failed for {tf}: {e}")
                    continue

                if full_result is None or full_result.get('total_trades', 0) == 0:
                    logger.warning(f"No trades in full period for {tf}")
                    continue

                # Run RECENT period backtest
                try:
                    recent_result = self._run_multi_symbol_backtest(
                        strategy_instance, recent_data, tf
                    )
                except Exception as e:
                    logger.warning(f"Recent period backtest failed for {tf}: {e}")
                    recent_result = None

                # Calculate weighted metrics
                weighted_result = self._calculate_weighted_metrics(
                    full_result, recent_result
                )

                tf_results[tf] = weighted_result

                # Save both backtest results
                full_backtest_id = self._save_backtest_result(
                    strategy_id, full_result, pairs, tf,
                    is_optimal=False,
                    period_type='full',
                    period_days=self.lookback_days
                )

                recent_backtest_id = None
                if recent_result and recent_result.get('total_trades', 0) > 0:
                    recent_backtest_id = self._save_backtest_result(
                        strategy_id, recent_result, pairs, tf,
                        is_optimal=False,
                        period_type='recent',
                        period_days=self.recent_period_days
                    )

                    # Update full result with recent_result_id and weighted metrics
                    self._update_full_result_with_weighted(
                        full_backtest_id,
                        recent_backtest_id,
                        weighted_result
                    )

                tf_backtest_ids[tf] = full_backtest_id

                logger.info(
                    f"[{strategy_name}] {tf}: "
                    f"Full: {full_result['total_trades']} trades, Sharpe {full_result.get('sharpe_ratio', 0):.2f} | "
                    f"Recent: {recent_result.get('total_trades', 0) if recent_result else 0} trades | "
                    f"Weighted Sharpe: {weighted_result.get('weighted_sharpe', 0):.2f}, "
                    f"Recency Penalty: {weighted_result.get('recency_penalty', 0):.1%}"
                )

            # Find optimal timeframe using weighted scores
            optimal_tf = self._find_optimal_timeframe_dual(tf_results)

            if optimal_tf is None:
                self._delete_strategy(strategy_id, "No TF passed thresholds")
                return (False, "No TF passed thresholds")

            # Update strategy with optimal TF
            self._update_strategy_optimal_tf(strategy_id, optimal_tf, pairs)

            # Mark optimal backtest
            if optimal_tf in tf_backtest_ids:
                self._mark_optimal_backtest(tf_backtest_ids[optimal_tf])

            # Promote to TESTED
            self.processor.release_strategy(strategy_id, "TESTED")

            optimal_result = tf_results[optimal_tf]
            return (
                True,
                f"Optimal TF: {optimal_tf}, "
                f"Weighted Sharpe {optimal_result.get('weighted_sharpe', 0):.2f}, "
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
        Run backtest across multiple symbols and aggregate results

        Args:
            strategy_instance: StrategyCore instance
            data: Dict mapping symbol -> DataFrame
            timeframe: Timeframe being tested

        Returns:
            Aggregated metrics dictionary
        """
        all_metrics = []
        total_trades = 0
        total_pnl = 0.0

        for symbol, df in data.items():
            if df.empty or len(df) < 100:
                continue

            try:
                result = self.engine.backtest(strategy_instance, df, symbol)
                if result and result.get('total_trades', 0) > 0:
                    all_metrics.append(result)
                    total_trades += result.get('total_trades', 0)
                    total_pnl += result.get('total_pnl', 0)
            except Exception as e:
                logger.debug(f"Backtest failed for {symbol}: {e}")
                continue

        if not all_metrics:
            return {'total_trades': 0}

        # Aggregate metrics (weighted by number of trades)
        def weighted_avg(key: str) -> float:
            if total_trades == 0:
                return 0.0
            return sum(
                m.get(key, 0) * m.get('total_trades', 0)
                for m in all_metrics
            ) / total_trades

        return {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'sharpe_ratio': weighted_avg('sharpe_ratio'),
            'win_rate': weighted_avg('win_rate'),
            'expectancy': weighted_avg('expectancy'),
            'max_drawdown': max(m.get('max_drawdown', 0) for m in all_metrics),
            'profit_factor': weighted_avg('profit_factor'),
            'consistency': weighted_avg('consistency'),
            'symbols_traded': len(all_metrics),
            'symbol_breakdown': {
                m.get('symbol', 'unknown'): m for m in all_metrics
            }
        }

    def _calculate_weighted_metrics(
        self,
        full_result: Dict,
        recent_result: Optional[Dict]
    ) -> Dict:
        """
        Calculate weighted metrics from full and recent period results

        Formula:
            weighted_sharpe = full_sharpe * 0.60 + recent_sharpe * 0.40
            recency_ratio = recent_sharpe / full_sharpe
            recency_penalty = max(0, 1 - recency_ratio) * 0.20  # up to 20%
            final_score = weighted_sharpe * (1 - recency_penalty)

        Returns:
            Dict with weighted metrics
        """
        full_sharpe = full_result.get('sharpe_ratio', 0)
        full_win_rate = full_result.get('win_rate', 0)
        full_expectancy = full_result.get('expectancy', 0)

        # If no recent data, use full metrics only
        if recent_result is None or recent_result.get('total_trades', 0) == 0:
            return {
                **full_result,
                'weighted_sharpe': full_sharpe,
                'weighted_win_rate': full_win_rate,
                'weighted_expectancy': full_expectancy,
                'recency_ratio': 1.0,
                'recency_penalty': 0.0,
            }

        recent_sharpe = recent_result.get('sharpe_ratio', 0)
        recent_win_rate = recent_result.get('win_rate', 0)
        recent_expectancy = recent_result.get('expectancy', 0)

        # Calculate weighted metrics
        weighted_sharpe = (
            full_sharpe * self.full_period_weight +
            recent_sharpe * self.recent_period_weight
        )
        weighted_win_rate = (
            full_win_rate * self.full_period_weight +
            recent_win_rate * self.recent_period_weight
        )
        weighted_expectancy = (
            full_expectancy * self.full_period_weight +
            recent_expectancy * self.recent_period_weight
        )

        # Calculate recency ratio (how recent compares to full)
        if full_sharpe > 0:
            recency_ratio = recent_sharpe / full_sharpe
        else:
            recency_ratio = 1.0 if recent_sharpe >= 0 else 0.0

        # Recency penalty: up to 20% if recent performance is significantly worse
        recency_penalty = max(0, 1 - recency_ratio) * 0.20

        # Combine into result
        return {
            **full_result,
            'weighted_sharpe': weighted_sharpe,
            'weighted_win_rate': weighted_win_rate,
            'weighted_expectancy': weighted_expectancy,
            'recency_ratio': recency_ratio,
            'recency_penalty': recency_penalty,
            'recent_trades': recent_result.get('total_trades', 0),
            'recent_sharpe': recent_sharpe,
            'recent_win_rate': recent_win_rate,
        }

    def _find_optimal_timeframe_dual(self, tf_results: Dict[str, Dict]) -> Optional[str]:
        """
        Find TF with best weighted performance that passes all thresholds.

        Uses weighted_sharpe with recency penalty for scoring.

        Returns:
            Optimal timeframe string or None if none pass
        """
        best_tf = None
        best_score = -float('inf')

        for tf, results in tf_results.items():
            # Check thresholds using weighted metrics
            total_trades = results.get('total_trades', 0)
            weighted_sharpe = results.get('weighted_sharpe', 0)
            weighted_win_rate = results.get('weighted_win_rate', 0)
            max_dd = results.get('max_drawdown', 1)
            weighted_expectancy = results.get('weighted_expectancy', 0)
            recency_penalty = results.get('recency_penalty', 0)

            # Must pass all thresholds
            if total_trades < self.min_trades:
                logger.debug(f"{tf}: Failed trades threshold ({total_trades} < {self.min_trades})")
                continue
            if weighted_sharpe < self.min_sharpe:
                logger.debug(f"{tf}: Failed sharpe threshold ({weighted_sharpe:.2f} < {self.min_sharpe})")
                continue
            if weighted_win_rate < self.min_win_rate:
                logger.debug(f"{tf}: Failed win_rate threshold ({weighted_win_rate:.2%} < {self.min_win_rate:.2%})")
                continue
            if max_dd > self.max_drawdown:
                logger.debug(f"{tf}: Failed drawdown threshold ({max_dd:.2%} > {self.max_drawdown:.2%})")
                continue
            if weighted_expectancy < self.min_expectancy:
                logger.debug(f"{tf}: Failed expectancy threshold ({weighted_expectancy:.4f} < {self.min_expectancy})")
                continue

            # Calculate final score with recency penalty
            base_score = (
                0.5 * weighted_sharpe +
                0.3 * weighted_expectancy * 100 +
                0.2 * weighted_win_rate
            )
            score = base_score * (1 - recency_penalty)

            logger.debug(
                f"{tf}: Score {score:.2f} (base={base_score:.2f}, penalty={recency_penalty:.1%})"
            )

            if score > best_score:
                best_score = score
                best_tf = tf

        if best_tf:
            logger.info(f"Optimal TF: {best_tf} with score {best_score:.2f}")

        return best_tf

    def _update_full_result_with_weighted(
        self,
        full_backtest_id: str,
        recent_backtest_id: str,
        weighted_result: Dict
    ):
        """
        Update full period backtest result with weighted metrics and recent_result_id
        """
        if not full_backtest_id:
            return

        try:
            with get_session() as session:
                bt = session.query(BacktestResult).filter(
                    BacktestResult.id == full_backtest_id
                ).first()

                if bt:
                    bt.weighted_sharpe = weighted_result.get('weighted_sharpe')
                    bt.weighted_win_rate = weighted_result.get('weighted_win_rate')
                    bt.weighted_expectancy = weighted_result.get('weighted_expectancy')
                    bt.recency_ratio = weighted_result.get('recency_ratio')
                    bt.recency_penalty = weighted_result.get('recency_penalty')

                    if recent_backtest_id:
                        bt.recent_result_id = recent_backtest_id

                    session.commit()
        except Exception as e:
            logger.error(f"Failed to update full result with weighted metrics: {e}")

    def _find_optimal_timeframe(self, tf_results: Dict[str, Dict]) -> Optional[str]:
        """
        Find TF with best performance that passes all thresholds.

        Uses composite score: 0.5*sharpe + 0.3*edge + 0.2*win_rate

        Returns:
            Optimal timeframe string or None if none pass
        """
        best_tf = None
        best_score = -float('inf')

        for tf, results in tf_results.items():
            # Check thresholds
            total_trades = results.get('total_trades', 0)
            sharpe = results.get('sharpe_ratio', 0)
            win_rate = results.get('win_rate', 0)
            max_dd = results.get('max_drawdown', 1)
            expectancy = results.get('expectancy', 0)

            # Must pass all thresholds
            if total_trades < self.min_trades:
                logger.debug(f"{tf}: Failed trades threshold ({total_trades} < {self.min_trades})")
                continue
            if sharpe < self.min_sharpe:
                logger.debug(f"{tf}: Failed sharpe threshold ({sharpe:.2f} < {self.min_sharpe})")
                continue
            if win_rate < self.min_win_rate:
                logger.debug(f"{tf}: Failed win_rate threshold ({win_rate:.2%} < {self.min_win_rate:.2%})")
                continue
            if max_dd > self.max_drawdown:
                logger.debug(f"{tf}: Failed drawdown threshold ({max_dd:.2%} > {self.max_drawdown:.2%})")
                continue
            if expectancy < self.min_expectancy:
                logger.debug(f"{tf}: Failed expectancy threshold ({expectancy:.4f} < {self.min_expectancy})")
                continue

            # Calculate composite score
            score = (
                0.5 * sharpe +
                0.3 * expectancy * 100 +  # Scale expectancy
                0.2 * win_rate
            )

            logger.debug(f"{tf}: Score {score:.2f} (sharpe={sharpe:.2f}, exp={expectancy:.4f}, wr={win_rate:.2%})")

            if score > best_score:
                best_score = score
                best_tf = tf

        if best_tf:
            logger.info(f"Optimal TF: {best_tf} with score {best_score:.2f}")

        return best_tf

    def _save_backtest_result(
        self,
        strategy_id,
        result: Dict,
        pairs: List[str],
        timeframe: str,
        is_optimal: bool = False,
        period_type: str = 'full',
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
            period_type: 'full' or 'recent'
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
                    period_days = self.lookback_days if period_type == 'full' else self.recent_period_days

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
