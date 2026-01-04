"""
Pipeline Performance Calculation Helpers

Pure functions for calculating pipeline health metrics.
Used by pipeline health API endpoints.
"""
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database.models import Strategy, BacktestResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineMetrics:
    """
    Pure calculation functions for pipeline metrics

    All functions are static/pure - no side effects, no state.
    Takes session and config as parameters (dependency injection).
    """

    @staticmethod
    def get_queue_depths(session: Session) -> Dict[str, int]:
        """
        Get current queue depth for each pipeline stage

        Args:
            session: Database session

        Returns:
            Dict mapping status to count
            Example: {"GENERATED": 100, "VALIDATED": 50, "TESTED": 37, "SELECTED": 0}
        """
        depths = {}
        statuses = ['GENERATED', 'VALIDATED', 'TESTED', 'SELECTED', 'LIVE', 'RETIRED', 'FAILED']

        for status in statuses:
            count = session.query(Strategy).filter(Strategy.status == status).count()
            depths[status] = count

        return depths

    @staticmethod
    def calculate_throughput(
        session: Session,
        status: str,
        hours: int = 1
    ) -> float:
        """
        Calculate processing throughput (strategies/hour) for a stage

        Measures how many strategies passed through this status in last N hours.

        Args:
            session: Database session
            status: Pipeline status to measure
            hours: Time window in hours

        Returns:
            Strategies per hour (float)
        """
        if hours <= 0:
            return 0.0

        since = datetime.now(UTC) - timedelta(hours=hours)

        # Count strategies created in time window that reached or passed this status
        # (Current status is this OR any status after it)
        next_statuses = {
            'GENERATED': ['GENERATED', 'VALIDATED', 'TESTED', 'SELECTED', 'LIVE', 'RETIRED'],
            'VALIDATED': ['VALIDATED', 'TESTED', 'SELECTED', 'LIVE', 'RETIRED'],
            'TESTED': ['TESTED', 'SELECTED', 'LIVE', 'RETIRED'],
            'SELECTED': ['SELECTED', 'LIVE', 'RETIRED'],
            'LIVE': ['LIVE', 'RETIRED'],
        }

        status_list = next_statuses.get(status, [status])

        count = session.query(Strategy).filter(
            Strategy.created_at >= since,
            Strategy.status.in_(status_list)
        ).count()

        return count / hours

    @staticmethod
    def calculate_avg_processing_time(
        session: Session,
        from_field: str,
        to_field: str,
        hours: int = 1
    ) -> Optional[float]:
        """
        Calculate average processing time between two timestamp fields

        Args:
            session: Database session
            from_field: Start timestamp field name (e.g., 'created_at')
            to_field: End timestamp field name (e.g., 'tested_at')
            hours: Look back N hours

        Returns:
            Average seconds between timestamps, or None if no data
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        # Get strategies with both timestamps set
        strategies = session.query(Strategy).filter(
            getattr(Strategy, from_field).isnot(None),
            getattr(Strategy, to_field).isnot(None),
            getattr(Strategy, from_field) >= since
        ).all()

        if not strategies:
            return None

        # Calculate time deltas
        durations = []
        for strategy in strategies:
            start = getattr(strategy, from_field)
            end = getattr(strategy, to_field)
            if start and end and end > start:
                duration = (end - start).total_seconds()
                durations.append(duration)

        if not durations:
            return None

        return sum(durations) / len(durations)

    @staticmethod
    def calculate_success_rate(
        session: Session,
        status: str,
        hours: int = 1
    ) -> float:
        """
        Calculate success rate for a pipeline stage

        Success = strategies that progressed past this status
        Failure = strategies that ended in FAILED status at this stage

        Args:
            session: Database session
            status: Pipeline status to measure
            hours: Time window in hours

        Returns:
            Success rate as percentage (0-100)
        """
        since = datetime.now(UTC) - timedelta(hours=hours)

        # Total attempted (reached this status OR failed)
        total = session.query(Strategy).filter(
            Strategy.created_at >= since,
            Strategy.status.in_([status, 'FAILED'])
        ).count()

        if total == 0:
            return 100.0  # No data = assume healthy

        # Failed count
        failed = session.query(Strategy).filter(
            Strategy.created_at >= since,
            Strategy.status == 'FAILED'
        ).count()

        # Success rate
        success_rate = ((total - failed) / total) * 100
        return round(success_rate, 1)

    @staticmethod
    def calculate_failure_rate(
        session: Session,
        status: str,
        hours: int = 1
    ) -> float:
        """
        Calculate failure rate for a pipeline stage

        Args:
            session: Database session
            status: Pipeline status to measure
            hours: Time window in hours

        Returns:
            Failure rate as percentage (0-100)
        """
        success_rate = PipelineMetrics.calculate_success_rate(session, status, hours)
        return 100.0 - success_rate

    @staticmethod
    def detect_bottleneck(
        queue_depths: Dict[str, int],
        queue_limits: Dict[str, int]
    ) -> Optional[str]:
        """
        Identify bottlenecked pipeline stage

        A stage is bottlenecked if its utilization >= 80%

        Args:
            queue_depths: Current queue depth per status
            queue_limits: Configured limits per status

        Returns:
            Status name of bottlenecked stage, or None
        """
        utilizations = {}

        for status, depth in queue_depths.items():
            status_lower = status.lower()
            limit = queue_limits.get(status_lower, 0)

            if limit > 0:
                utilization = (depth / limit) * 100
                utilizations[status] = utilization

        if not utilizations:
            return None

        # Find max utilization
        max_status = max(utilizations, key=utilizations.get)
        max_utilization = utilizations[max_status]

        # Return if >= 80% utilized
        if max_utilization >= 80:
            return max_status

        return None

    @staticmethod
    def get_critical_issues(
        queue_depths: Dict[str, int],
        queue_limits: Dict[str, int],
        session: Session,
        hours: int = 1
    ) -> List[str]:
        """
        Identify critical pipeline issues

        Args:
            queue_depths: Current queue depths
            queue_limits: Configured limits
            session: Database session
            hours: Time window for metrics

        Returns:
            List of human-readable critical issue messages
        """
        issues = []

        # Check for backpressure (queue at/over limit)
        for status, depth in queue_depths.items():
            status_lower = status.lower()
            limit = queue_limits.get(status_lower, 0)

            if limit > 0 and depth >= limit:
                overflow = depth - limit
                issues.append(
                    f"BACKPRESSURE in {status}: {depth}/{limit} strategies "
                    f"({overflow} over limit)"
                )

        # Check for stalled pipeline (no processing in last hour)
        for status in ['GENERATED', 'VALIDATED', 'TESTED']:
            throughput = PipelineMetrics.calculate_throughput(session, status, hours)
            if queue_depths.get(status, 0) > 0 and throughput == 0:
                issues.append(
                    f"STALLED {status}: {queue_depths[status]} strategies in queue "
                    f"but 0 processed in last {hours}h"
                )

        # Check for high failure rate (>20%)
        for status in ['GENERATED', 'VALIDATED', 'TESTED']:
            failure_rate = PipelineMetrics.calculate_failure_rate(session, status, hours)
            if failure_rate > 20:
                issues.append(
                    f"HIGH FAILURE RATE in {status}: {failure_rate:.1f}% failing"
                )

        return issues

    @staticmethod
    def get_overall_status(
        queue_depths: Dict[str, int],
        queue_limits: Dict[str, int],
        critical_issues: List[str]
    ) -> str:
        """
        Determine overall pipeline health status

        Args:
            queue_depths: Current queue depths
            queue_limits: Configured limits
            critical_issues: List of critical issues

        Returns:
            "healthy", "degraded", or "critical"
        """
        # Critical if any critical issues
        if len(critical_issues) > 0:
            return "critical"

        # Degraded if any queue utilization > 80%
        for status, depth in queue_depths.items():
            status_lower = status.lower()
            limit = queue_limits.get(status_lower, 0)

            if limit > 0:
                utilization = (depth / limit) * 100
                if utilization >= 80:
                    return "degraded"

        return "healthy"

    @staticmethod
    def get_end_to_end_throughput(
        session: Session,
        hours: int = 1
    ) -> float:
        """
        Calculate end-to-end pipeline throughput

        Measures strategies that went from GENERATED to TESTED/SELECTED/LIVE
        in the time window.

        Args:
            session: Database session
            hours: Time window in hours

        Returns:
            Strategies/hour that completed full pipeline
        """
        if hours <= 0:
            return 0.0

        since = datetime.now(UTC) - timedelta(hours=hours)

        # Count strategies created in window that reached TESTED or beyond
        count = session.query(Strategy).filter(
            Strategy.created_at >= since,
            Strategy.status.in_(['TESTED', 'SELECTED', 'LIVE', 'RETIRED'])
        ).count()

        return count / hours
