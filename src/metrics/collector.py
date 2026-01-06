"""
Pipeline Metrics Collector

Runs continuously, collecting pipeline state snapshots every 5 minutes.
Stores to database for historical analysis and trend visualization.
"""

import time
import logging
from datetime import datetime, UTC
from typing import Dict, Optional

from sqlalchemy import select, func

from src.config import load_config
from src.database import get_session, PipelineMetricsSnapshot, Strategy

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects pipeline metrics snapshots at regular intervals.

    Metrics collected:
    - Queue depths (counts by status)
    - Throughput (strategies/hour by stage)
    - Utilization (percentage of queue limits)
    - Success rates (validation, backtesting)
    - Bottleneck detection
    - Overall system health
    - Quality metrics (avg Sharpe, win rate, expectancy)
    - Pattern vs AI breakdown
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
        """Collect current pipeline metrics and save to database"""
        try:
            with get_session() as session:
                # Get queue depths
                queue_depths = self._get_queue_depths(session)

                # Calculate throughput (strategies/hour)
                throughput = self._calculate_throughput(session)

                # Calculate utilization
                utilization = self._calculate_utilization(queue_depths)

                # Calculate success rates (pass rate through pipeline stages)
                success_rates = self._calculate_success_rates(session)

                # Get overall status (based on ACTIVE pool, not queue utilization)
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

                    # Success rates (strategies that passed each stage)
                    success_rate_validation=success_rates.get('validation'),
                    success_rate_backtesting=success_rates.get('backtesting'),

                    # Bottleneck - not used (misleading), kept for schema compatibility
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

                # Build readable log message
                g_count = queue_depths.get('GENERATED', 0)
                v_count = queue_depths.get('VALIDATED', 0)
                a_count = queue_depths.get('ACTIVE', 0)
                l_count = queue_depths.get('LIVE', 0)

                # Success rates as percentages
                val_rate = success_rates.get('validation')
                bt_rate = success_rates.get('backtesting')
                val_str = f"{val_rate:.0%}" if val_rate is not None else "N/A"
                bt_str = f"{bt_rate:.0%}" if bt_rate is not None else "N/A"

                logger.info(
                    f"Snapshot: {overall_status.upper()} | "
                    f"G:{g_count} V:{v_count} A:{a_count}/{self.limit_active} L:{l_count}/{self.limit_live} | "
                    f"Pass rates: val={val_str} bt={bt_str}"
                )

        except Exception as e:
            logger.error(f"Failed to collect metrics snapshot: {e}", exc_info=True)

    def _get_queue_depths(self, session) -> Dict[str, int]:
        """Get count of strategies by status"""
        result = session.execute(
            select(Strategy.status, func.count(Strategy.id))
            .group_by(Strategy.status)
        ).all()

        # status is already a string, not an Enum - no need for .value
        return {status: count for status, count in result}

    def _calculate_throughput(self, session) -> Dict[str, Optional[float]]:
        """
        Calculate strategies/hour throughput for each stage.

        Based on strategies that transitioned in the last hour.
        """
        # Get timestamp 1 hour ago
        one_hour_ago = datetime.now(UTC).timestamp() - 3600

        # Count strategies generated in last hour
        gen_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.created_at >= datetime.fromtimestamp(one_hour_ago, tz=UTC))
        ).scalar()

        # Count strategies validated in last hour
        val_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.validation_completed_at >= datetime.fromtimestamp(one_hour_ago, tz=UTC))
        ).scalar() if Strategy.validation_completed_at else None

        # Count strategies backtested in last hour (entered ACTIVE)
        test_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.last_backtested_at >= datetime.fromtimestamp(one_hour_ago, tz=UTC))
        ).scalar()

        return {
            'generation': float(gen_count) if gen_count else None,
            'validation': float(val_count) if val_count else None,
            'backtesting': float(test_count) if test_count else None,
        }

    def _calculate_utilization(self, queue_depths: Dict[str, int]) -> Dict[str, float]:
        """Calculate queue utilization (0.0-1.0)"""
        return {
            'generated': queue_depths.get('GENERATED', 0) / self.limit_generated if self.limit_generated > 0 else 0.0,
            'validated': queue_depths.get('VALIDATED', 0) / self.limit_validated if self.limit_validated > 0 else 0.0,
            'active': queue_depths.get('ACTIVE', 0) / self.limit_active if self.limit_active > 0 else 0.0,
        }

    def _calculate_success_rates(self, session) -> Dict[str, Optional[float]]:
        """
        Calculate success rates for each pipeline stage.

        Success rate = strategies that passed / strategies that were processed

        Returns dict with 'validation' and 'backtesting' rates (0.0-1.0)
        """
        from sqlalchemy import or_

        # Validation success rate:
        # Passed = currently VALIDATED or beyond (ACTIVE, LIVE)
        # Failed = deleted by validator (we can't count these directly)
        # Approximate: use ratio of VALIDATED+ACTIVE+LIVE vs total ever generated
        validated_or_beyond = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status.in_(['VALIDATED', 'ACTIVE', 'LIVE']))
        ).scalar() or 0

        total_strategies = session.execute(
            select(func.count(Strategy.id))
        ).scalar() or 0

        # Validation rate: strategies that passed validation / total
        # Note: GENERATED strategies haven't been validated yet
        generated_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status == 'GENERATED')
        ).scalar() or 0

        processed_by_validator = total_strategies - generated_count
        val_rate = validated_or_beyond / processed_by_validator if processed_by_validator > 0 else None

        # Backtesting success rate:
        # Passed = ACTIVE or LIVE (made it through backtest)
        # Failed = deleted by backtester
        active_or_live = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.status.in_(['ACTIVE', 'LIVE']))
        ).scalar() or 0

        # Processed by backtester = strategies that left VALIDATED status
        # We can approximate by: ACTIVE + LIVE (passed) vs what was VALIDATED
        # For better tracking, we'd need historical data
        # Approximate: ACTIVE+LIVE / (ACTIVE+LIVE+VALIDATED was processed)
        # Since we delete failed strategies, we can't get exact count

        # Use last_backtested_at to count strategies that were backtested
        backtested_count = session.execute(
            select(func.count(Strategy.id))
            .where(Strategy.last_backtested_at.isnot(None))
        ).scalar() or 0

        bt_rate = active_or_live / backtested_count if backtested_count > 0 else None

        return {
            'validation': val_rate,
            'backtesting': bt_rate,
        }

    def _get_overall_status(
        self,
        queue_depths: Dict[str, int],
        success_rates: Dict[str, Optional[float]]
    ) -> str:
        """
        Determine overall system health status.

        Based on:
        - ACTIVE pool size (primary indicator of system health)
        - Success rates (if too low, something is wrong)

        Returns: 'healthy', 'degraded', or 'critical'
        """
        active_count = queue_depths.get('ACTIVE', 0)
        live_count = queue_depths.get('LIVE', 0)
        bt_rate = success_rates.get('backtesting')

        # Critical: no ACTIVE strategies and backtest rate is very low
        if active_count == 0 and live_count == 0:
            if bt_rate is not None and bt_rate < 0.01:
                return 'critical'  # Pipeline producing nothing
            return 'degraded'  # No strategies yet, but might be starting up

        # Degraded: ACTIVE pool very low or backtest rate very low
        if active_count < 10:
            return 'degraded'

        # Healthy: ACTIVE pool has strategies
        return 'healthy'

    def _get_quality_metrics(self, session) -> Dict[str, Optional[float]]:
        """Get average quality metrics from ACTIVE strategies"""
        from src.database.models import BacktestResult

        # Get latest backtest for each ACTIVE strategy
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
        """Count strategies by source (pattern vs AI)"""
        # Strategies with ai_provider = pattern-based
        # Strategies without ai_provider or with other value = AI-based

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

    def run(self) -> None:
        """Main collection loop (runs forever)"""
        logger.info(f"Metrics collector started (interval: {self.interval_seconds}s)")

        while True:
            try:
                self.collect_snapshot()
            except Exception as e:
                logger.error(f"Metrics collection failed: {e}", exc_info=True)

            time.sleep(self.interval_seconds)


def main():
    """Entry point for running as a service"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    collector = MetricsCollector()
    collector.run()


if __name__ == '__main__':
    main()
