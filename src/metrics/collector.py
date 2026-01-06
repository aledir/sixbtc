"""
Pipeline Metrics Collector (Event-Based)

Collects pipeline metrics from the strategy_events table.
Events persist even when strategies are deleted, enabling accurate metrics.

Metrics collected:
- Queue depths (counts by status)
- Throughput (strategies/hour by stage)
- Success rates (REAL rates from events, not approximations)
- Failure breakdowns (WHY strategies failed)
- Timing metrics (duration per phase)
- Quality metrics (avg Sharpe, win rate, expectancy)
- Pattern vs AI breakdown
"""

import time
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any

from sqlalchemy import select, func, and_, or_

from src.config import load_config
from src.database import get_session, PipelineMetricsSnapshot, Strategy
from src.database.models import StrategyEvent

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

        # Collection interval (default: 5 minutes = 300 seconds)
        metrics_config = self.config.get('metrics', {})
        self.interval_seconds = metrics_config.get('collection_interval', 300)
        self.log_detail_interval = metrics_config.get('detail_log_interval', 300)  # 5min
        self._last_detail_log = datetime.min.replace(tzinfo=UTC)

        # Queue limits from pipeline config
        pipeline_config = self.config.get('pipeline', {})
        queue_limits = pipeline_config.get('queue_limits', {})
        self.limit_generated = queue_limits.get('generated', 100)
        self.limit_validated = queue_limits.get('validated', 50)

        # ACTIVE pool limit from active_pool config
        active_pool_config = self.config.get('active_pool', {})
        self.limit_active = active_pool_config.get('max_size', 300)

        # LIVE limit from rotator config
        rotator_config = self.config.get('rotator', {})
        self.limit_live = rotator_config.get('max_live_strategies', 10)

        logger.info(f"MetricsCollector initialized (interval: {self.interval_seconds}s)")

    def collect_snapshot(self) -> None:
        """Collect current pipeline metrics and save to database."""
        try:
            with get_session() as session:
                # Time window for event-based metrics (last collection interval)
                window_start = datetime.now(UTC) - timedelta(seconds=self.interval_seconds)

                # Get queue depths (current counts)
                queue_depths = self._get_queue_depths(session)

                # Calculate throughput from events
                throughput = self._calculate_throughput_from_events(session, window_start)

                # Calculate utilization
                utilization = self._calculate_utilization(queue_depths)

                # Calculate SUCCESS RATES from events (accurate!)
                success_rates = self._calculate_success_rates_from_events(session, window_start)

                # Get failure breakdown
                failures = self._get_failure_breakdown(session, window_start)

                # Get timing metrics
                timing = self._get_timing_metrics(session, window_start)

                # Get overall status
                overall_status = self._get_overall_status(queue_depths, success_rates)

                # Get quality metrics
                quality = self._get_quality_metrics(session)

                # Pattern vs AI breakdown
                pattern_ai = self._get_pattern_ai_breakdown(session)

                # Create snapshot
                snapshot = PipelineMetricsSnapshot(
                    timestamp=datetime.now(UTC),

                    # Queue depths
                    queue_generated=queue_depths.get('GENERATED', 0),
                    queue_validated=queue_depths.get('VALIDATED', 0),
                    queue_active=queue_depths.get('ACTIVE', 0),
                    queue_live=queue_depths.get('LIVE', 0),
                    queue_retired=queue_depths.get('RETIRED', 0),
                    queue_failed=queue_depths.get('FAILED', 0),

                    # Throughput
                    throughput_generation=throughput.get('generation'),
                    throughput_validation=throughput.get('validation'),
                    throughput_backtesting=throughput.get('backtesting'),

                    # Utilization
                    utilization_generated=utilization.get('generated'),
                    utilization_validated=utilization.get('validated'),
                    utilization_active=utilization.get('active'),

                    # Success rates (from events!)
                    success_rate_validation=success_rates.get('validation'),
                    success_rate_backtesting=success_rates.get('backtesting'),

                    # Bottleneck - not used
                    bottleneck_stage=None,

                    # Overall status
                    overall_status=overall_status,

                    # Quality
                    avg_sharpe=quality.get('sharpe'),
                    avg_win_rate=quality.get('win_rate'),
                    avg_expectancy=quality.get('expectancy'),

                    # Pattern vs AI
                    pattern_count=pattern_ai.get('pattern', 0),
                    ai_count=pattern_ai.get('ai', 0),
                )

                session.add(snapshot)
                session.commit()

                # Log output
                self._log_metrics(
                    queue_depths, throughput, success_rates, failures, timing
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

    def _calculate_throughput_from_events(
        self, session, since: datetime
    ) -> Dict[str, Optional[float]]:
        """
        Calculate throughput from events.

        Counts completed events per stage in the time window.
        """
        # Generation: count generation.created events
        gen_count = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'generation',
                    StrategyEvent.event_type == 'created',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        # Validation: count validation.completed events
        val_count = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'validation',
                    StrategyEvent.event_type == 'completed',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        # Backtesting: count pool.entered events (strategies that made it through)
        bt_count = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'pool',
                    StrategyEvent.event_type == 'entered',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        # Convert to per-hour rate
        window_hours = self.interval_seconds / 3600
        return {
            'generation': gen_count / window_hours if gen_count else None,
            'validation': val_count / window_hours if val_count else None,
            'backtesting': bt_count / window_hours if bt_count else None,
        }

    def _calculate_utilization(self, queue_depths: Dict[str, int]) -> Dict[str, float]:
        """Calculate queue utilization (0.0-1.0)."""
        return {
            'generated': queue_depths.get('GENERATED', 0) / self.limit_generated if self.limit_generated > 0 else 0.0,
            'validated': queue_depths.get('VALIDATED', 0) / self.limit_validated if self.limit_validated > 0 else 0.0,
            'active': queue_depths.get('ACTIVE', 0) / self.limit_active if self.limit_active > 0 else 0.0,
        }

    def _calculate_success_rates_from_events(
        self, session, since: datetime
    ) -> Dict[str, Optional[float]]:
        """
        Calculate REAL success rates from events.

        This is accurate because events persist even when strategies are deleted.
        """
        # Validation success rate
        val_passed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'validation',
                    StrategyEvent.event_type == 'completed',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        val_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'validation',
                    StrategyEvent.status == 'failed',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        val_total = val_passed + val_failed
        val_rate = val_passed / val_total if val_total > 0 else None

        # Backtest success rate (pool entries vs rejections + score failures)
        pool_entered = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'pool',
                    StrategyEvent.event_type == 'entered',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        pool_rejected = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'pool',
                    StrategyEvent.event_type == 'rejected',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        score_rejected = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'backtest',
                    StrategyEvent.event_type == 'score_rejected',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        shuffle_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'shuffle_test',
                    StrategyEvent.status == 'failed',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        mw_failed = session.execute(
            select(func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'multi_window',
                    StrategyEvent.status == 'failed',
                    StrategyEvent.timestamp >= since
                )
            )
        ).scalar() or 0

        bt_failed = pool_rejected + score_rejected + shuffle_failed + mw_failed
        bt_total = pool_entered + bt_failed
        bt_rate = pool_entered / bt_total if bt_total > 0 else None

        return {
            'validation': val_rate,
            'backtesting': bt_rate,
        }

    def _get_failure_breakdown(
        self, session, since: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get breakdown of failures by stage and reason.

        Returns dict with failures per stage.
        """
        failures = {}

        # Validation failures by phase
        val_failures = session.execute(
            select(StrategyEvent.event_type, func.count(StrategyEvent.id))
            .where(
                and_(
                    StrategyEvent.stage == 'validation',
                    StrategyEvent.status == 'failed',
                    StrategyEvent.timestamp >= since
                )
            )
            .group_by(StrategyEvent.event_type)
        ).all()

        failures['validation'] = [
            {'type': event_type, 'count': count}
            for event_type, count in val_failures
        ]

        # Backtest failures
        bt_failure_types = [
            ('backtest', 'score_rejected', 'score_below_threshold'),
            ('shuffle_test', 'failed', 'shuffle_fail'),
            ('multi_window', 'failed', 'multi_window_fail'),
            ('pool', 'rejected', 'pool_rejected'),
        ]

        bt_failures = []
        for stage, event_type, label in bt_failure_types:
            count = session.execute(
                select(func.count(StrategyEvent.id))
                .where(
                    and_(
                        StrategyEvent.stage == stage,
                        or_(
                            StrategyEvent.event_type == event_type,
                            StrategyEvent.status == 'failed'
                        ) if event_type == 'failed' else StrategyEvent.event_type == event_type,
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar() or 0

            if count > 0:
                bt_failures.append({'type': label, 'count': count})

        failures['backtesting'] = bt_failures

        return failures

    def _get_timing_metrics(
        self, session, since: datetime
    ) -> Dict[str, Optional[float]]:
        """
        Get average timing metrics per phase.

        Returns avg duration in milliseconds.
        """
        timing = {}

        stages = ['validation', 'shuffle_test', 'multi_window']
        for stage in stages:
            avg_ms = session.execute(
                select(func.avg(StrategyEvent.duration_ms))
                .where(
                    and_(
                        StrategyEvent.stage == stage,
                        StrategyEvent.duration_ms.isnot(None),
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar()

            timing[stage] = float(avg_ms) if avg_ms is not None else None

        return timing

    def _get_overall_status(
        self,
        queue_depths: Dict[str, int],
        success_rates: Dict[str, Optional[float]]
    ) -> str:
        """
        Determine overall system health status.

        Returns: 'healthy', 'degraded', or 'critical'
        """
        active_count = queue_depths.get('ACTIVE', 0)
        live_count = queue_depths.get('LIVE', 0)
        bt_rate = success_rates.get('backtesting')

        # Critical: no ACTIVE strategies and backtest rate is very low
        if active_count == 0 and live_count == 0:
            if bt_rate is not None and bt_rate < 0.01:
                return 'critical'
            return 'degraded'

        # Degraded: ACTIVE pool very low or backtest rate very low
        if active_count < 10:
            return 'degraded'

        return 'healthy'

    def _get_quality_metrics(self, session) -> Dict[str, Optional[float]]:
        """Get average quality metrics from ACTIVE strategies."""
        from src.database.models import BacktestResult

        result = session.execute(
            select(
                func.avg(BacktestResult.weighted_sharpe_pure),
                func.avg(BacktestResult.weighted_win_rate),
                func.avg(BacktestResult.weighted_expectancy),
            )
            .join(Strategy, BacktestResult.strategy_id == Strategy.id)
            .where(Strategy.status == 'ACTIVE')
        ).first()

        if result:
            return {
                'sharpe': float(result[0]) if result[0] is not None else None,
                'win_rate': float(result[1]) if result[1] is not None else None,
                'expectancy': float(result[2]) if result[2] is not None else None,
            }

        return {'sharpe': None, 'win_rate': None, 'expectancy': None}

    def _get_pattern_ai_breakdown(self, session) -> Dict[str, int]:
        """Count strategies by source (pattern vs AI)."""
        pattern_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.ai_provider == 'pattern')
        ).scalar() or 0

        ai_count = session.execute(
            select(func.count(Strategy.id))
            .where(
                (Strategy.ai_provider != 'pattern') | (Strategy.ai_provider.is_(None))
            )
        ).scalar() or 0

        return {
            'pattern': pattern_count,
            'ai': ai_count,
        }

    def _log_metrics(
        self,
        queue_depths: Dict[str, int],
        throughput: Dict[str, Optional[float]],
        success_rates: Dict[str, Optional[float]],
        failures: Dict[str, List[Dict]],
        timing: Dict[str, Optional[float]]
    ) -> None:
        """Log metrics in detailed format."""
        now = datetime.now(UTC)
        should_log_detail = (now - self._last_detail_log).total_seconds() >= self.log_detail_interval

        # Get current counts
        g = queue_depths.get('GENERATED', 0)
        v = queue_depths.get('VALIDATED', 0)
        a = queue_depths.get('ACTIVE', 0)
        l = queue_depths.get('LIVE', 0)
        r = queue_depths.get('RETIRED', 0)
        f = queue_depths.get('FAILED', 0)

        # Get throughput (per hour)
        gen_tp = throughput.get('generation') or 0
        val_tp = throughput.get('validation') or 0
        bt_tp = throughput.get('backtesting') or 0

        # Convert hourly to interval (5min = 1/12 of hour)
        interval_hours = self.interval_seconds / 3600
        gen_interval = int(gen_tp * interval_hours)
        val_interval = int(val_tp * interval_hours)
        bt_interval = int(bt_tp * interval_hours)

        # Get success rates
        val_rate = success_rates.get('validation')
        bt_rate = success_rates.get('backtesting')

        # Get timing
        gen_time = timing.get('generation')
        val_time = timing.get('validation')
        bt_time = timing.get('backtesting')

        # Overall status
        status = self._get_overall_status(queue_depths, success_rates).upper()

        # Format timing strings
        def fmt_time(ms: Optional[float]) -> str:
            if ms is None:
                return "N/A"
            if ms >= 1000:
                return f"{ms/1000:.1f}s"
            return f"{ms:.0f}ms"

        # Build failure breakdown strings
        val_fails = failures.get('validation', [])
        bt_fails = failures.get('backtesting', [])

        val_fail_str = ""
        if val_fails:
            parts = [f"{f['type']}={f['count']}" for f in val_fails[:3]]
            val_fail_str = f" | fail: {' '.join(parts)}"

        bt_fail_str = ""
        if bt_fails:
            parts = [f"{f['type']}={f['count']}" for f in bt_fails[:3]]
            bt_fail_str = f" | fail: {' '.join(parts)}"

        # Count passed/failed in interval
        val_ok = int(val_interval * (val_rate or 0)) if val_rate else 0
        val_ko = val_interval - val_ok
        bt_ok = int(bt_interval * (bt_rate or 0)) if bt_rate else 0
        bt_ko = bt_interval - bt_ok

        # Log compact format (always)
        interval_min = self.interval_seconds // 60
        logger.info(f"Pipeline: {status} | {interval_min}min")
        logger.info(f"  GEN:  +{gen_interval} ({fmt_time(gen_time)}) | queue={g}/{self.limit_generated}")

        if val_rate is not None:
            logger.info(f"  VAL:  +{val_ok} OK +{val_ko} FAIL ({fmt_time(val_time)}){val_fail_str} | queue={v}/{self.limit_validated}")
        else:
            logger.info(f"  VAL:  +{val_interval} ({fmt_time(val_time)}) | queue={v}/{self.limit_validated}")

        if bt_rate is not None:
            logger.info(f"  BT:   +{bt_ok} OK +{bt_ko} FAIL ({fmt_time(bt_time)}){bt_fail_str} | queue={v}")
        else:
            logger.info(f"  BT:   +{bt_interval} ({fmt_time(bt_time)}) | queue={v}")

        logger.info(f"  POOL: {a}/{self.limit_active}")
        logger.info(f"  LIVE: {l}/{self.limit_live} | retired={r} failed={f}")

        # Log detailed breakdown periodically
        if should_log_detail:
            self._last_detail_log = now
            self._log_detailed_metrics(failures, timing, success_rates)

    def _log_detailed_metrics(
        self,
        failures: Dict[str, List[Dict]],
        timing: Dict[str, Optional[float]],
        success_rates: Dict[str, Optional[float]]
    ) -> None:
        """Log detailed breakdown every N minutes."""
        logger.info("=" * 70)
        logger.info("DETAILED METRICS BREAKDOWN")
        logger.info("=" * 70)

        # Validation failure breakdown
        val_fails = failures.get('validation', [])
        if val_fails:
            logger.info("VALIDATION FAILURES:")
            for f in val_fails:
                pct = f.get('percentage', 0)
                logger.info(f"  - {f['type']}: {f['count']} ({pct:.1f}%)")

        # Backtest failure breakdown
        bt_fails = failures.get('backtesting', [])
        if bt_fails:
            logger.info("BACKTEST FAILURES:")
            for f in bt_fails:
                pct = f.get('percentage', 0)
                logger.info(f"  - {f['type']}: {f['count']} ({pct:.1f}%)")

        # Timing breakdown
        if any(v is not None for v in timing.values()):
            logger.info("TIMING (avg per operation):")
            for stage, ms in timing.items():
                if ms is not None:
                    if ms >= 1000:
                        logger.info(f"  - {stage}: {ms/1000:.1f}s")
                    else:
                        logger.info(f"  - {stage}: {ms:.0f}ms")

        # Success rates
        logger.info("SUCCESS RATES:")
        for stage, rate in success_rates.items():
            if rate is not None:
                logger.info(f"  - {stage}: {rate:.1%}")
            else:
                logger.info(f"  - {stage}: N/A (no data)")

        logger.info("=" * 70)

    def get_funnel_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get pipeline funnel metrics for the specified time period.

        Returns conversion rates through each stage.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            # Count events at each stage
            generated = session.execute(
                select(func.count(StrategyEvent.id))
                .where(
                    and_(
                        StrategyEvent.stage == 'generation',
                        StrategyEvent.event_type == 'created',
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar() or 0

            validated = session.execute(
                select(func.count(StrategyEvent.id))
                .where(
                    and_(
                        StrategyEvent.stage == 'validation',
                        StrategyEvent.event_type == 'completed',
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar() or 0

            pool_entered = session.execute(
                select(func.count(StrategyEvent.id))
                .where(
                    and_(
                        StrategyEvent.stage == 'pool',
                        StrategyEvent.event_type == 'entered',
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar() or 0

            deployed = session.execute(
                select(func.count(StrategyEvent.id))
                .where(
                    and_(
                        StrategyEvent.stage == 'deployment',
                        StrategyEvent.event_type == 'succeeded',
                        StrategyEvent.timestamp >= since
                    )
                )
            ).scalar() or 0

            return {
                'period_hours': hours,
                'stages': [
                    {
                        'name': 'Generated',
                        'count': generated,
                        'conversion_rate': 1.0
                    },
                    {
                        'name': 'Validated',
                        'count': validated,
                        'conversion_rate': validated / generated if generated > 0 else 0
                    },
                    {
                        'name': 'Active Pool',
                        'count': pool_entered,
                        'conversion_rate': pool_entered / validated if validated > 0 else 0
                    },
                    {
                        'name': 'Deployed',
                        'count': deployed,
                        'conversion_rate': deployed / pool_entered if pool_entered > 0 else 0
                    },
                ]
            }

    def get_failure_analysis(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get detailed failure analysis for the specified time period.

        Returns failure counts and reasons by stage.
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        with get_session() as session:
            # Get all failure events with event_data
            failures = session.execute(
                select(
                    StrategyEvent.stage,
                    StrategyEvent.event_type,
                    StrategyEvent.event_data
                )
                .where(
                    and_(
                        StrategyEvent.status == 'failed',
                        StrategyEvent.timestamp >= since
                    )
                )
            ).all()

            # Aggregate by stage and reason
            by_stage: Dict[str, Dict[str, int]] = {}
            for stage, event_type, event_data in failures:
                if stage not in by_stage:
                    by_stage[stage] = {}

                reason = event_type
                if event_data and 'reason' in event_data:
                    reason = event_data['reason']

                by_stage[stage][reason] = by_stage[stage].get(reason, 0) + 1

            return {
                'period_hours': hours,
                'by_stage': by_stage,
                'total_failures': len(failures)
            }

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
