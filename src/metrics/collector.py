"""
Pipeline Metrics Collector (Event-Based)

Collects pipeline metrics from the strategy_events table.
Events persist even when strategies are deleted, enabling accurate metrics.

Log format (11 lines per snapshot):
- status: overall health + issue
- state: current counts by DB status
- funnel_24h: conversion rates through pipeline
- timing_avg: average processing times
- throughput_1min: recent processing rates
- failures_24h: failure breakdown by type
- backpressure: queue status and bottlenecks
- pool_stats: ACTIVE pool statistics
- pool_quality: quality metrics (edge, sharpe, winrate, dd)
- retest_24h: re-backtest statistics
- live_rotation: LIVE deployment statistics
"""

import time
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy import select, func, and_, or_, desc

from src.config import load_config
from src.database import get_session, PipelineMetricsSnapshot, Strategy
from src.database.models import StrategyEvent, BacktestResult

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects pipeline metrics from events at regular intervals.

    Uses strategy_events table for accurate metrics:
    - Success rates calculated from passed/failed events
    - Failure reasons tracked and aggregated
    - Timing information from event durations
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize metrics collector.

        Args:
            config: Configuration dict (if None, loads from file)
        """
        if config is None:
            config = load_config()

        self.config = config._raw_config if hasattr(config, '_raw_config') else config

        # Collection interval (default: 1 minute = 60 seconds)
        metrics_config = self.config.get('metrics', {})
        self.interval_seconds = metrics_config.get('collection_interval', 60)

        # Queue limits from pipeline config
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        self.limit_generated = queue_limits.get('generated', 500)
        self.limit_validated = queue_limits.get('validated', 500)

        # ACTIVE pool limit from active_pool config
        active_pool_config = self.config.get('active_pool', {})
        self.limit_active = active_pool_config.get('max_size', 300)
        self.pool_min_score = active_pool_config.get('min_score', 40)

        # LIVE limit from rotator config
        rotator_config = self.config.get('rotator', {})
        self.limit_live = rotator_config.get('max_live_strategies', 10)

        # Backtesting config for retest
        backtesting_config = self.config.get('backtesting', {})
        self.retest_interval_days = backtesting_config.get('retest', {}).get('interval_days', 3)

        logger.info(f"MetricsCollector initialized (interval: {self.interval_seconds}s)")

    def collect_snapshot(self) -> None:
        """Collect current pipeline metrics and save to database."""
        try:
            with get_session() as session:
                # Time windows
                now = datetime.now(UTC)
                window_1min = now - timedelta(seconds=self.interval_seconds)
                window_24h = now - timedelta(hours=24)

                # Collect all metrics
                queue_depths = self._get_queue_depths(session)
                funnel = self._get_funnel_24h(session, window_24h)
                timing = self._get_timing_avg_24h(session, window_24h)
                throughput = self._get_throughput_interval(session, window_1min)
                failures = self._get_failures_24h(session, window_24h)
                backpressure = self._get_backpressure_status(session, queue_depths)
                pool_stats = self._get_pool_stats(session)
                pool_quality = self._get_pool_quality(session)
                retest_stats = self._get_retest_stats_24h(session, window_24h)
                live_stats = self._get_live_rotation_stats(session, window_24h)

                # Determine overall status
                status, issue = self._get_status_and_issue(
                    queue_depths, backpressure, throughput
                )

                # Save snapshot to database
                self._save_snapshot(
                    session, queue_depths, throughput, funnel, pool_quality, status
                )

                # Log metrics in new format
                self._log_metrics(
                    status=status,
                    issue=issue,
                    queue_depths=queue_depths,
                    funnel=funnel,
                    timing=timing,
                    throughput=throughput,
                    failures=failures,
                    backpressure=backpressure,
                    pool_stats=pool_stats,
                    pool_quality=pool_quality,
                    retest_stats=retest_stats,
                    live_stats=live_stats,
                )

        except Exception as e:
            logger.error(f"Failed to collect metrics snapshot: {e}", exc_info=True)

    def _get_queue_depths(self, session) -> Dict[str, int]:
        """Get count of strategies by status."""
        result = session.execute(
            select(Strategy.status, func.count(Strategy.id))
            .group_by(Strategy.status)
        ).all()

        return {status: count for status, count in result}

    def _get_funnel_24h(self, session, since: datetime) -> Dict[str, Any]:
        """
        Get pipeline funnel metrics for last 24h.

        Returns counts and pass rates for each stage.
        """
        # Generated
        generated = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'created',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Validated (passed validation)
        validated = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.event_type == 'completed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Backtested (completed backtest: scored OR parametric_failed)
        backtested = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type.in_(['scored', 'parametric_failed']),
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score OK (passed score threshold)
        score_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.event_type == 'started',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle OK
        shuffle_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window OK
        mw_ok = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool entries
        pool_entered = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'entered',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Calculate pass rates
        def pct(num: int, denom: int) -> Optional[int]:
            if denom == 0:
                return None
            return int(round(100 * num / denom))

        return {
            'generated': generated,
            'validated': validated,
            'validated_pct': pct(validated, generated),
            'backtested': backtested,
            'backtested_pct': pct(backtested, validated),
            'score_ok': score_ok,
            'score_ok_pct': pct(score_ok, backtested),
            'shuffle_ok': shuffle_ok,
            'shuffle_ok_pct': pct(shuffle_ok, score_ok),
            'mw_ok': mw_ok,
            'mw_ok_pct': pct(mw_ok, shuffle_ok),
            'pool': pool_entered,
            'pool_pct': pct(pool_entered, mw_ok if mw_ok > 0 else shuffle_ok),
        }

    def _get_timing_avg_24h(self, session, since: datetime) -> Dict[str, Optional[float]]:
        """Get average timing metrics per phase for last 24h."""
        timing = {}

        stages = [
            ('validation', 'validation'),
            ('backtest', 'backtest'),
            ('shuffle_test', 'shuffle'),
            ('multi_window', 'multiwindow'),
        ]

        for db_stage, key in stages:
            avg_ms = session.execute(
                select(func.avg(StrategyEvent.duration_ms))
                .where(and_(
                    StrategyEvent.stage == db_stage,
                    StrategyEvent.duration_ms.isnot(None),
                    StrategyEvent.timestamp >= since
                ))
            ).scalar()

            timing[key] = float(avg_ms) if avg_ms is not None else None

        return timing

    def _get_throughput_interval(
        self, session, since: datetime
    ) -> Dict[str, int]:
        """Get throughput (counts) for each stage in the interval."""
        # Generation
        gen = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'generation',
                StrategyEvent.event_type == 'created',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Validation completed
        val = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.event_type == 'completed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Backtest completed (scored OR parametric_failed)
        # Counts all backtests that ran, not just those that passed thresholds
        bt = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type.in_(['scored', 'parametric_failed']),
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score passed (shuffle started)
        score = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.event_type == 'started',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle passed
        shuf = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window passed
        mw = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'passed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool entered
        pool = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'entered',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        return {
            'gen': gen,
            'val': val,
            'bt': bt,
            'score': score,
            'shuf': shuf,
            'mw': mw,
            'pool': pool,
        }

    def _get_failures_24h(self, session, since: datetime) -> Dict[str, int]:
        """Get failure counts by type for last 24h."""
        # Validation failures
        validation_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Score rejected
        score_reject = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'backtest',
                StrategyEvent.event_type == 'score_rejected',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Shuffle failed
        shuffle_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'shuffle_test',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Multi-window failed
        mw_fail = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'multi_window',
                StrategyEvent.status == 'failed',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Pool rejected
        pool_reject = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'pool',
                StrategyEvent.event_type == 'rejected',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        return {
            'validation': validation_fail,
            'score_reject': score_reject,
            'shuffle_fail': shuffle_fail,
            'mw_fail': mw_fail,
            'pool_reject': pool_reject,
        }

    def _get_backpressure_status(
        self, session, queue_depths: Dict[str, int]
    ) -> Dict[str, Any]:
        """Get backpressure status (queue depths and processing counts)."""
        gen_count = queue_depths.get('GENERATED', 0)
        val_count = queue_depths.get('VALIDATED', 0)

        # Count strategies currently being processed
        bt_processing = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.status == 'VALIDATED',
                Strategy.processing_by.isnot(None)
            ))
        ).scalar() or 0

        bt_waiting = val_count - bt_processing

        # Check if queues are full
        gen_full = gen_count >= self.limit_generated
        val_full = val_count >= self.limit_validated

        return {
            'gen_queue': gen_count,
            'gen_limit': self.limit_generated,
            'gen_full': gen_full,
            'val_queue': val_count,
            'val_limit': self.limit_validated,
            'bt_waiting': bt_waiting,
            'bt_processing': bt_processing,
        }

    def _get_pool_stats(self, session) -> Dict[str, Any]:
        """Get ACTIVE pool statistics."""
        # Pool size
        pool_size = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'ACTIVE')
        ).scalar() or 0

        # Score stats
        score_stats = session.execute(
            select(
                func.min(Strategy.score_backtest),
                func.max(Strategy.score_backtest),
                func.avg(Strategy.score_backtest),
            )
            .where(Strategy.status == 'ACTIVE')
        ).first()

        return {
            'size': pool_size,
            'limit': self.limit_active,
            'score_min': float(score_stats[0]) if score_stats[0] else None,
            'score_max': float(score_stats[1]) if score_stats[1] else None,
            'score_avg': float(score_stats[2]) if score_stats[2] else None,
        }

    def _get_pool_quality(self, session) -> Dict[str, Any]:
        """Get quality metrics for ACTIVE pool strategies."""
        result = session.execute(
            select(
                func.avg(BacktestResult.weighted_expectancy),
                func.avg(BacktestResult.weighted_sharpe_pure),
                func.avg(BacktestResult.weighted_win_rate),
                func.avg(BacktestResult.weighted_max_drawdown),
            )
            .join(Strategy, BacktestResult.strategy_id == Strategy.id)
            .where(Strategy.status == 'ACTIVE')
        ).first()

        if result and result[0] is not None:
            return {
                'edge_avg': float(result[0]) if result[0] else None,
                'sharpe_avg': float(result[1]) if result[1] else None,
                'winrate_avg': float(result[2]) if result[2] else None,
                'dd_avg': float(result[3]) if result[3] else None,
            }

        return {
            'edge_avg': None,
            'sharpe_avg': None,
            'winrate_avg': None,
            'dd_avg': None,
        }

    def _get_retest_stats_24h(self, session, since: datetime) -> Dict[str, Any]:
        """Get re-backtest statistics for last 24h."""
        # Count retest events (look for stage=backtest with retest indicator)
        # Retest events are tracked via the strategy's last_backtested_at update
        # We look for strategies that were ACTIVE and got retested

        # For now, we use a simpler approach: count strategies with
        # last_backtested_at in the last 24h that are ACTIVE or RETIRED
        retested = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.last_backtested_at >= since,
                Strategy.status.in_(['ACTIVE', 'RETIRED'])
            ))
        ).scalar() or 0

        # Passed = still ACTIVE after retest
        passed = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.last_backtested_at >= since,
                Strategy.status == 'ACTIVE'
            ))
        ).scalar() or 0

        # Retired from retest
        retired = session.execute(
            select(func.count(Strategy.id))
            .where(and_(
                Strategy.retired_at >= since,
                Strategy.status == 'RETIRED'
            ))
        ).scalar() or 0

        return {
            'tested': retested,
            'passed': passed,
            'retired': retired,
        }

    def _get_live_rotation_stats(self, session, since: datetime) -> Dict[str, Any]:
        """Get LIVE rotation statistics."""
        # Current LIVE count
        live_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'LIVE')
        ).scalar() or 0

        # Deployed in last 24h
        deployed_24h = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'deployment',
                StrategyEvent.event_type == 'succeeded',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Retired from LIVE in last 24h
        retired_24h = session.execute(
            select(func.count(StrategyEvent.id))
            .where(and_(
                StrategyEvent.stage == 'live',
                StrategyEvent.event_type == 'retired',
                StrategyEvent.timestamp >= since
            ))
        ).scalar() or 0

        # Average age of LIVE strategies (days)
        avg_age_result = session.execute(
            select(func.avg(
                func.extract('epoch', func.now() - Strategy.live_since) / 86400
            ))
            .where(and_(
                Strategy.status == 'LIVE',
                Strategy.live_since.isnot(None)
            ))
        ).scalar()

        avg_age = float(avg_age_result) if avg_age_result else None

        return {
            'live': live_count,
            'limit': self.limit_live,
            'deployed_24h': deployed_24h,
            'retired_24h': retired_24h,
            'avg_age_days': avg_age,
        }

    def _get_status_and_issue(
        self,
        queue_depths: Dict[str, int],
        backpressure: Dict[str, Any],
        throughput: Dict[str, int],
    ) -> Tuple[str, Optional[str]]:
        """Determine overall status and issue description."""
        active = queue_depths.get('ACTIVE', 0)
        live = queue_depths.get('LIVE', 0)
        bt_waiting = backpressure.get('bt_waiting', 0)
        bt_processing = backpressure.get('bt_processing', 0)

        # Check for issues
        issues = []

        # Backtest stalled
        if bt_waiting > 0 and bt_processing == 0 and throughput.get('bt', 0) == 0:
            issues.append(f"Backtest stalled ({bt_waiting} waiting)")

        # Generator queue full
        if backpressure.get('gen_full', False):
            issues.append("Generator queue full")

        # No ACTIVE strategies
        if active == 0 and live == 0:
            issues.append("No ACTIVE strategies")

        # Determine status
        if not issues:
            return 'HEALTHY', None
        elif 'stalled' in ' '.join(issues).lower() or active == 0:
            return 'DEGRADED', issues[0]
        else:
            return 'DEGRADED', issues[0]

    def _save_snapshot(
        self,
        session,
        queue_depths: Dict[str, int],
        throughput: Dict[str, int],
        funnel: Dict[str, Any],
        pool_quality: Dict[str, Any],
        status: str,
    ) -> None:
        """Save metrics snapshot to database."""
        # Calculate utilization
        gen_util = queue_depths.get('GENERATED', 0) / self.limit_generated if self.limit_generated > 0 else 0
        val_util = queue_depths.get('VALIDATED', 0) / self.limit_validated if self.limit_validated > 0 else 0
        active_util = queue_depths.get('ACTIVE', 0) / self.limit_active if self.limit_active > 0 else 0

        # Calculate success rates
        val_rate = funnel['validated_pct'] / 100 if funnel['validated_pct'] else None
        bt_rate = funnel['pool_pct'] / 100 if funnel['pool_pct'] else None

        snapshot = PipelineMetricsSnapshot(
            timestamp=datetime.now(UTC),
            queue_generated=queue_depths.get('GENERATED', 0),
            queue_validated=queue_depths.get('VALIDATED', 0),
            queue_active=queue_depths.get('ACTIVE', 0),
            queue_live=queue_depths.get('LIVE', 0),
            queue_retired=queue_depths.get('RETIRED', 0),
            queue_failed=queue_depths.get('FAILED', 0),
            throughput_generation=throughput.get('gen', 0) * 60,  # per hour
            throughput_validation=throughput.get('val', 0) * 60,
            throughput_backtesting=throughput.get('bt', 0) * 60,
            utilization_generated=gen_util,
            utilization_validated=val_util,
            utilization_active=active_util,
            success_rate_validation=val_rate,
            success_rate_backtesting=bt_rate,
            bottleneck_stage=None,
            overall_status=status.lower(),
            avg_sharpe=pool_quality.get('sharpe_avg'),
            avg_win_rate=pool_quality.get('winrate_avg'),
            avg_expectancy=pool_quality.get('edge_avg'),
            pattern_count=0,
            ai_count=0,
        )

        session.add(snapshot)
        session.commit()

    def _log_metrics(
        self,
        status: str,
        issue: Optional[str],
        queue_depths: Dict[str, int],
        funnel: Dict[str, Any],
        timing: Dict[str, Optional[float]],
        throughput: Dict[str, int],
        failures: Dict[str, int],
        backpressure: Dict[str, Any],
        pool_stats: Dict[str, Any],
        pool_quality: Dict[str, Any],
        retest_stats: Dict[str, Any],
        live_stats: Dict[str, Any],
    ) -> None:
        """Log metrics in Unix standard format (11 lines)."""

        # Helper functions
        def fmt_pct(val: Optional[int]) -> str:
            return f"{val}%" if val is not None else "--"

        def fmt_time(ms: Optional[float]) -> str:
            if ms is None:
                return "--"
            if ms >= 1000:
                return f"{ms/1000:.1f}s"
            return f"{int(ms)}ms"

        def fmt_float(val: Optional[float], decimals: int = 1) -> str:
            if val is None:
                return "--"
            return f"{val:.{decimals}f}"

        def fmt_pct_float(val: Optional[float]) -> str:
            if val is None:
                return "--"
            return f"{val*100:.0f}%"

        # 1. status
        if issue:
            logger.info(f'status={status} issue="{issue}"')
        else:
            logger.info(f'status={status}')

        # 2. state
        g = queue_depths.get('GENERATED', 0)
        v = queue_depths.get('VALIDATED', 0)
        a = queue_depths.get('ACTIVE', 0)
        l = queue_depths.get('LIVE', 0)
        r = queue_depths.get('RETIRED', 0)
        f = queue_depths.get('FAILED', 0)
        logger.info(f'state generated={g} validated={v} active={a} live={l} retired={r} failed={f}')

        # 3. funnel_24h
        logger.info(
            f'funnel_24h '
            f'generated={funnel["generated"]} '
            f'validated={funnel["validated"]}/{fmt_pct(funnel["validated_pct"])} '
            f'backtested={funnel["backtested"]}/{fmt_pct(funnel["backtested_pct"])} '
            f'score_ok={funnel["score_ok"]}/{fmt_pct(funnel["score_ok_pct"])} '
            f'shuffle_ok={funnel["shuffle_ok"]}/{fmt_pct(funnel["shuffle_ok_pct"])} '
            f'mw_ok={funnel["mw_ok"]}/{fmt_pct(funnel["mw_ok_pct"])} '
            f'pool={funnel["pool"]}/{fmt_pct(funnel["pool_pct"])}'
        )

        # 4. timing_avg
        logger.info(
            f'timing_avg '
            f'validation={fmt_time(timing.get("validation"))} '
            f'backtest={fmt_time(timing.get("backtest"))} '
            f'shuffle={fmt_time(timing.get("shuffle"))} '
            f'multiwindow={fmt_time(timing.get("multiwindow"))}'
        )

        # 5. throughput_1min
        logger.info(
            f'throughput_1min '
            f'gen=+{throughput["gen"]} '
            f'val=+{throughput["val"]} '
            f'bt=+{throughput["bt"]} '
            f'score=+{throughput["score"]} '
            f'shuf=+{throughput["shuf"]} '
            f'mw=+{throughput["mw"]} '
            f'pool=+{throughput["pool"]}'
        )

        # 6. failures_24h
        logger.info(
            f'failures_24h '
            f'validation={failures["validation"]} '
            f'score_reject={failures["score_reject"]} '
            f'shuffle_fail={failures["shuffle_fail"]} '
            f'mw_fail={failures["mw_fail"]} '
            f'pool_reject={failures["pool_reject"]}'
        )

        # 7. backpressure
        gen_status = "(full)" if backpressure["gen_full"] else ""
        logger.info(
            f'backpressure '
            f'gen_queue={backpressure["gen_queue"]}/{backpressure["gen_limit"]}{gen_status} '
            f'val_queue={backpressure["val_queue"]}/{backpressure["val_limit"]} '
            f'bt_waiting={backpressure["bt_waiting"]} '
            f'bt_processing={backpressure["bt_processing"]}'
        )

        # 8. pool_stats
        logger.info(
            f'pool_stats '
            f'size={pool_stats["size"]}/{pool_stats["limit"]} '
            f'score_min={fmt_float(pool_stats["score_min"])} '
            f'score_max={fmt_float(pool_stats["score_max"])} '
            f'score_avg={fmt_float(pool_stats["score_avg"])}'
        )

        # 9. pool_quality
        edge_str = f'{pool_quality["edge_avg"]*100:.1f}%' if pool_quality["edge_avg"] else "--"
        logger.info(
            f'pool_quality '
            f'edge_avg={edge_str} '
            f'sharpe_avg={fmt_float(pool_quality["sharpe_avg"])} '
            f'winrate_avg={fmt_pct_float(pool_quality["winrate_avg"])} '
            f'dd_avg={fmt_pct_float(pool_quality["dd_avg"])}'
        )

        # 10. retest_24h
        logger.info(
            f'retest_24h '
            f'tested={retest_stats["tested"]} '
            f'passed={retest_stats["passed"]} '
            f'retired={retest_stats["retired"]}'
        )

        # 11. live_rotation
        avg_age_str = f'{live_stats["avg_age_days"]:.1f}d' if live_stats["avg_age_days"] else "--"
        logger.info(
            f'live_rotation '
            f'live={live_stats["live"]}/{live_stats["limit"]} '
            f'deployed_24h={live_stats["deployed_24h"]} '
            f'retired_24h={live_stats["retired_24h"]} '
            f'avg_live_age={avg_age_str}'
        )

    # =========================================================================
    # PUBLIC API METHODS (for external use)
    # =========================================================================

    def get_funnel_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get pipeline funnel metrics for the specified time period.

        Returns conversion rates through each stage.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            return self._get_funnel_24h(session, since)

    def get_failure_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get detailed failure analysis for the specified time period.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            return self._get_failures_24h(session, since)

    def run(self) -> None:
        """Main collection loop (runs forever)."""
        logger.info(f"Metrics collector started (interval: {self.interval_seconds}s)")

        while True:
            try:
                self.collect_snapshot()
            except Exception as e:
                logger.error(f"Metrics collection failed: {e}", exc_info=True)

            time.sleep(self.interval_seconds)


def main():
    """Entry point for running as a service."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    collector = MetricsCollector()
    collector.run()


if __name__ == '__main__':
    main()
