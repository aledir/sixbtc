"""
Metrics API Routes

Historical pipeline analytics and time-series data.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from src.database import get_db, PipelineMetricsSnapshot
from src.database.models import StrategyEvent
from src.metrics.collector import MetricsCollector

# Singleton MetricsCollector instance for /snapshot endpoint
_metrics_collector: Optional[MetricsCollector] = None

# Cache for expensive snapshot computation
_snapshot_cache: Dict = {}
_snapshot_cache_time: Optional[datetime] = None
SNAPSHOT_CACHE_TTL_SECONDS = 60  # Cache for 60 seconds (expensive computation)

def get_metrics_collector() -> MetricsCollector:
    """Get or create singleton MetricsCollector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def _refresh_snapshot_cache() -> None:
    """
    Refresh the snapshot cache. Called by background task.

    This function is designed to be called from a thread pool executor
    since it performs blocking I/O (database queries).
    """
    global _snapshot_cache, _snapshot_cache_time

    import time
    import logging

    start = time.time()
    collector = get_metrics_collector()
    _snapshot_cache = collector.get_full_snapshot()
    _snapshot_cache_time = datetime.now(UTC)
    elapsed = time.time() - start
    logging.getLogger(__name__).info(f"Snapshot refreshed in {elapsed:.1f}s (background)")


router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/timeseries")
async def get_metrics_timeseries(
    period: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    metric: str = Query("queue_depths", pattern="^(queue_depths|throughput|quality|utilization|success_rates)$"),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get time-series data for specified metric over period.

    Returns data points at 5-min intervals (or hourly for 7d+).

    Args:
        period: Time period (1h, 6h, 24h, 7d, 30d)
        metric: Metric type (queue_depths, throughput, quality, utilization)
        session: Database session

    Returns:
        Dict with period, metric, and data array
    """
    # Parse period to hours
    hours_map = {'1h': 1, '6h': 6, '24h': 24, '7d': 168, '30d': 720}
    hours = hours_map[period]
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Query snapshots
    query = select(PipelineMetricsSnapshot).where(
        PipelineMetricsSnapshot.timestamp >= since
    ).order_by(PipelineMetricsSnapshot.timestamp)

    result = session.execute(query)
    snapshots = result.scalars().all()

    # Format response based on metric type
    if metric == "queue_depths":
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'generated': s.queue_generated,
                'validated': s.queue_validated,
                'active': s.queue_active,
                'live': s.queue_live,
                'retired': s.queue_retired,
                'failed': s.queue_failed,
            }
            for s in snapshots
        ]
    elif metric == "throughput":
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'generation': s.throughput_generation,
                'validation': s.throughput_validation,
                'backtesting': s.throughput_backtesting,
            }
            for s in snapshots
        ]
    elif metric == "quality":
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'avg_sharpe': s.avg_sharpe,
                'avg_win_rate': s.avg_win_rate,
                'avg_expectancy': s.avg_expectancy,
            }
            for s in snapshots
        ]
    elif metric == "utilization":
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'generated': s.utilization_generated,
                'validated': s.utilization_validated,
                'active': s.utilization_active,
            }
            for s in snapshots
        ]
    elif metric == "success_rates":
        data = [
            {
                'timestamp': s.timestamp.isoformat(),
                'validation': s.success_rate_validation,
                'backtesting': s.success_rate_backtesting,
            }
            for s in snapshots
        ]
    else:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}")

    return {
        'period': period,
        'metric': metric,
        'data_points': len(data),
        'data': data
    }


@router.get("/aggregated")
async def get_aggregated_metrics(
    period: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get aggregated metrics (avg, min, max) over period.

    Useful for summary statistics and reports.

    Args:
        period: Time period (1h, 6h, 24h, 7d, 30d)
        session: Database session

    Returns:
        Dict with aggregated statistics
    """
    # Parse period
    hours_map = {'1h': 1, '6h': 6, '24h': 24, '7d': 168, '30d': 720}
    hours = hours_map[period]
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Aggregate query
    result = session.execute(
        select(
            func.avg(PipelineMetricsSnapshot.queue_generated).label('avg_generated'),
            func.avg(PipelineMetricsSnapshot.queue_validated).label('avg_validated'),
            func.avg(PipelineMetricsSnapshot.queue_active).label('avg_active'),
            func.max(PipelineMetricsSnapshot.utilization_generated).label('max_util_gen'),
            func.max(PipelineMetricsSnapshot.utilization_validated).label('max_util_val'),
            func.max(PipelineMetricsSnapshot.utilization_active).label('max_util_active'),
            func.avg(PipelineMetricsSnapshot.avg_sharpe).label('avg_sharpe'),
            func.avg(PipelineMetricsSnapshot.avg_win_rate).label('avg_win_rate'),
            func.avg(PipelineMetricsSnapshot.success_rate_validation).label('avg_success_val'),
            func.avg(PipelineMetricsSnapshot.success_rate_backtesting).label('avg_success_bt'),
            func.count(PipelineMetricsSnapshot.id).label('snapshots_count'),
        )
        .where(PipelineMetricsSnapshot.timestamp >= since)
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="No data found for period")

    return {
        'period': period,
        'snapshots_analyzed': result.snapshots_count,
        'queue_depths': {
            'avg_generated': float(round(result.avg_generated, 1)) if result.avg_generated else 0.0,
            'avg_validated': float(round(result.avg_validated, 1)) if result.avg_validated else 0.0,
            'avg_active': float(round(result.avg_active, 1)) if result.avg_active else 0.0,
        },
        'utilization': {
            'max_generated': float(round(result.max_util_gen, 2)) if result.max_util_gen else 0.0,
            'max_validated': float(round(result.max_util_val, 2)) if result.max_util_val else 0.0,
            'max_active': float(round(result.max_util_active, 2)) if result.max_util_active else 0.0,
        },
        'quality': {
            'avg_sharpe': float(round(result.avg_sharpe, 2)) if result.avg_sharpe else None,
            'avg_win_rate': float(round(result.avg_win_rate, 3)) if result.avg_win_rate else None,
        },
        'success_rates': {
            'avg_validation': float(round(result.avg_success_val, 3)) if result.avg_success_val else None,
            'avg_backtesting': float(round(result.avg_success_bt, 3)) if result.avg_success_bt else None,
        }
    }


@router.get("/alerts")
async def get_metric_alerts(
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get current metric-based alerts.

    Checks:
    - Backpressure > 90% for > 1h
    - Throughput < 5 strat/h for > 2h
    - Quality degradation (Sharpe < 0.3 for > 24h)

    Args:
        session: Database session

    Returns:
        Dict with alerts array
    """
    alerts = []

    # Get last hour of snapshots
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    recent_snapshots = session.execute(
        select(PipelineMetricsSnapshot)
        .where(PipelineMetricsSnapshot.timestamp >= one_hour_ago)
        .order_by(PipelineMetricsSnapshot.timestamp.desc())
    ).scalars().all()

    if not recent_snapshots:
        return {'alerts': []}

    # Check backpressure (active pool > 90% for 1h)
    high_pressure_count = sum(
        1 for s in recent_snapshots
        if s.utilization_active and s.utilization_active > 0.9
    )

    if high_pressure_count >= len(recent_snapshots) * 0.8:  # 80% of samples
        alerts.append({
            'severity': 'warning',
            'type': 'backpressure',
            'message': 'ACTIVE pool > 90% for 1 hour',
            'duration_minutes': 60,
            'current_value': recent_snapshots[0].utilization_active,
        })

    # Check throughput degradation (backtesting < 5 strat/h)
    low_throughput = [
        s for s in recent_snapshots
        if s.throughput_backtesting and s.throughput_backtesting < 5.0
    ]

    if len(low_throughput) >= len(recent_snapshots) * 0.8:
        avg_throughput = sum(s.throughput_backtesting for s in low_throughput) / len(low_throughput)
        alerts.append({
            'severity': 'info',
            'type': 'low_throughput',
            'message': f'Backtesting throughput < 5 strategies/hour',
            'duration_minutes': 60,
            'current_value': round(avg_throughput, 1),
        })

    # Check quality degradation (last 24h avg Sharpe < 0.3)
    one_day_ago = datetime.now(UTC) - timedelta(hours=24)
    quality_check = session.execute(
        select(func.avg(PipelineMetricsSnapshot.avg_sharpe))
        .where(
            PipelineMetricsSnapshot.timestamp >= one_day_ago,
            PipelineMetricsSnapshot.avg_sharpe.is_not(None)
        )
    ).scalar()

    if quality_check and quality_check < 0.3:
        alerts.append({
            'severity': 'warning',
            'type': 'quality_degradation',
            'message': 'Average Sharpe < 0.3 for 24 hours',
            'duration_minutes': 1440,
            'current_value': round(quality_check, 2),
        })

    # Check system status
    if recent_snapshots[0].overall_status == 'critical':
        alert = {
            'severity': 'critical',
            'type': 'system_critical',
            'message': 'System status: CRITICAL',
            'duration_minutes': 0,
        }
        if recent_snapshots[0].bottleneck_stage:
            alert['bottleneck'] = recent_snapshots[0].bottleneck_stage
        alerts.append(alert)

    return {
        'timestamp': datetime.now(UTC).isoformat(),
        'alerts_count': len(alerts),
        'alerts': alerts
    }


@router.get("/current")
async def get_current_metrics(
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get most recent metrics snapshot.

    Returns:
        Dict with current pipeline state
    """
    # Get latest snapshot
    latest = session.execute(
        select(PipelineMetricsSnapshot)
        .order_by(PipelineMetricsSnapshot.timestamp.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not latest:
        raise HTTPException(status_code=404, detail="No metrics data available")

    return {
        'timestamp': latest.timestamp.isoformat(),
        'overall_status': latest.overall_status,
        'bottleneck_stage': latest.bottleneck_stage,
        'queue_depths': {
            'generated': latest.queue_generated,
            'validated': latest.queue_validated,
            'active': latest.queue_active,
            'live': latest.queue_live,
            'retired': latest.queue_retired,
            'failed': latest.queue_failed,
        },
        'utilization': {
            'generated': latest.utilization_generated,
            'validated': latest.utilization_validated,
            'active': latest.utilization_active,
        },
        'throughput': {
            'generation': latest.throughput_generation,
            'validation': latest.throughput_validation,
            'backtesting': latest.throughput_backtesting,
        },
        'quality': {
            'avg_sharpe': latest.avg_sharpe,
            'avg_win_rate': latest.avg_win_rate,
            'avg_expectancy': latest.avg_expectancy,
        },
        'success_rates': {
            'validation': latest.success_rate_validation,
            'backtesting': latest.success_rate_backtesting,
        },
        'breakdown': {
            'pattern_strategies': latest.pattern_count,
            'ai_strategies': latest.ai_count,
        }
    }


# =============================================================================
# EVENT-BASED ENDPOINTS (New)
# =============================================================================

@router.get("/events")
async def get_events(
    hours: int = Query(24, ge=1, le=168),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get recent pipeline events with optional filters.

    Args:
        hours: Look back period in hours (1-168)
        stage: Filter by stage (generation, validation, backtest, etc.)
        status: Filter by status (started, passed, failed, completed)
        limit: Max events to return (1-1000)
        session: Database session

    Returns:
        Dict with events array
    """
    since = datetime.now(UTC) - timedelta(hours=hours)

    query = select(StrategyEvent).where(
        StrategyEvent.timestamp >= since
    )

    if stage:
        query = query.where(StrategyEvent.stage == stage)
    if status:
        query = query.where(StrategyEvent.status == status)

    query = query.order_by(StrategyEvent.timestamp.desc()).limit(limit)

    result = session.execute(query)
    events = result.scalars().all()

    return {
        'period_hours': hours,
        'filters': {'stage': stage, 'status': status},
        'count': len(events),
        'events': [
            {
                'id': str(e.id),
                'timestamp': e.timestamp.isoformat(),
                'strategy_name': e.strategy_name,
                'stage': e.stage,
                'event_type': e.event_type,
                'status': e.status,
                'duration_ms': e.duration_ms,
                'metadata': e.event_data,
            }
            for e in events
        ]
    }


@router.get("/funnel")
async def get_pipeline_funnel(
    hours: int = Query(24, ge=1, le=168),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get pipeline conversion funnel metrics.

    Shows how many strategies pass through each stage and conversion rates.

    Args:
        hours: Look back period in hours (1-168)
        session: Database session

    Returns:
        Dict with funnel stages and conversion rates
    """
    since = datetime.now(UTC) - timedelta(hours=hours)

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

    validation_failed = session.execute(
        select(func.count(StrategyEvent.id))
        .where(
            and_(
                StrategyEvent.stage == 'validation',
                StrategyEvent.status == 'failed',
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

    backtest_failed = session.execute(
        select(func.count(StrategyEvent.id))
        .where(
            and_(
                StrategyEvent.stage.in_(['backtest', 'shuffle_test', 'multi_window', 'pool']),
                StrategyEvent.status == 'failed',
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

    retired = session.execute(
        select(func.count(StrategyEvent.id))
        .where(
            and_(
                StrategyEvent.stage == 'live',
                StrategyEvent.event_type == 'retired',
                StrategyEvent.timestamp >= since
            )
        )
    ).scalar() or 0

    return {
        'period_hours': hours,
        'funnel': [
            {
                'stage': 'Generated',
                'count': generated,
                'conversion_rate': 1.0,
            },
            {
                'stage': 'Validated',
                'count': validated,
                'failed': validation_failed,
                'conversion_rate': validated / generated if generated > 0 else 0,
            },
            {
                'stage': 'Active Pool',
                'count': pool_entered,
                'failed': backtest_failed,
                'conversion_rate': pool_entered / validated if validated > 0 else 0,
            },
            {
                'stage': 'Deployed (LIVE)',
                'count': deployed,
                'conversion_rate': deployed / pool_entered if pool_entered > 0 else 0,
            },
        ],
        'overall_conversion': generated > 0 and deployed / generated or 0,
        'retired_count': retired,
    }


@router.get("/failures")
async def get_failure_breakdown(
    hours: int = Query(24, ge=1, le=168),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get detailed failure breakdown by stage and reason.

    Shows WHY strategies failed, not just counts.

    Args:
        hours: Look back period in hours (1-168)
        session: Database session

    Returns:
        Dict with failure breakdown by stage
    """
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Get all failure events
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

    # Aggregate by stage
    by_stage: Dict[str, Dict[str, int]] = {}
    for stage, event_type, event_data in failures:
        if stage not in by_stage:
            by_stage[stage] = {}

        # Get reason from event_data if available
        reason = event_type
        if event_data and isinstance(event_data, dict) and 'reason' in event_data:
            reason = event_data['reason']

        by_stage[stage][reason] = by_stage[stage].get(reason, 0) + 1

    # Format response
    breakdown = []
    for stage, reasons in by_stage.items():
        stage_total = sum(reasons.values())
        breakdown.append({
            'stage': stage,
            'total': stage_total,
            'reasons': [
                {'reason': r, 'count': c, 'percentage': c / stage_total if stage_total > 0 else 0}
                for r, c in sorted(reasons.items(), key=lambda x: x[1], reverse=True)
            ]
        })

    # Sort by total failures
    breakdown.sort(key=lambda x: x['total'], reverse=True)

    return {
        'period_hours': hours,
        'total_failures': len(failures),
        'by_stage': breakdown,
    }


@router.get("/timing")
async def get_timing_metrics(
    hours: int = Query(24, ge=1, le=168),
    session: Session = Depends(get_db)
) -> Dict:
    """
    Get timing metrics per pipeline stage.

    Shows average, min, max duration for each phase.

    Args:
        hours: Look back period in hours (1-168)
        session: Database session

    Returns:
        Dict with timing breakdown by stage
    """
    since = datetime.now(UTC) - timedelta(hours=hours)

    stages = ['validation', 'shuffle_test', 'multi_window']
    timing = {}

    for stage in stages:
        result = session.execute(
            select(
                func.avg(StrategyEvent.duration_ms).label('avg'),
                func.min(StrategyEvent.duration_ms).label('min'),
                func.max(StrategyEvent.duration_ms).label('max'),
                func.count(StrategyEvent.id).label('count'),
            )
            .where(
                and_(
                    StrategyEvent.stage == stage,
                    StrategyEvent.duration_ms.isnot(None),
                    StrategyEvent.timestamp >= since
                )
            )
        ).first()

        if result and result.count > 0:
            timing[stage] = {
                'avg_ms': round(result.avg, 1) if result.avg else None,
                'min_ms': result.min,
                'max_ms': result.max,
                'sample_count': result.count,
            }

    return {
        'period_hours': hours,
        'timing': timing,
    }


@router.get("/snapshot")
async def get_full_snapshot() -> Dict:
    """
    Get the full real-time pipeline snapshot.

    Returns the complete computed metrics snapshot, same data that the
    metrics service logs every 60 seconds. This is the richest endpoint
    for dashboard display.

    Data is pre-computed by a background task and refreshed every 60 seconds.
    Never blocks the request - returns cached data or loading state.

    Includes:
    - Pipeline status and trading mode
    - Capital summary (main + subaccounts)
    - Generator stats (24h breakdown by source, type, direction, timeframe)
    - Validator stats (queue, pass/fail by source)
    - Parametric stats (combos tested, pass/fail rates, fail reasons)
    - IS/OOS backtest stats (pass rates, avg metrics, fail reasons)
    - Score, Shuffle, WFA, Robustness stats
    - Pool stats (size, quality metrics, distribution by source)
    - Live stats (strategy count, diversity)
    - Per-subaccount details (balance, PnL, drawdown, positions)
    - Scheduler task status

    Returns:
        Dict with full snapshot data (or loading state if not ready)
    """
    global _snapshot_cache, _snapshot_cache_time

    # Return cached data if available (background task keeps it fresh)
    if _snapshot_cache and _snapshot_cache_time:
        return _snapshot_cache

    # Snapshot not ready yet - return loading state instead of blocking
    return {
        'status': 'LOADING',
        'issue': 'Initial snapshot computation in progress...',
        'timestamp': datetime.now(UTC).isoformat(),
        'trading_mode': 'UNKNOWN',
        'capital': {'total': 0, 'main_account': 0, 'subaccounts': 0},
        'queue_depths': {},
        'generator': {},
        'validator': {},
        'pool': {},
        'live': {},
        'subaccounts': [],
    }
