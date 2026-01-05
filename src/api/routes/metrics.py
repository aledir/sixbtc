"""
Metrics API Routes

Historical pipeline analytics and time-series data.
"""

from datetime import datetime, timedelta, UTC
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.database import get_session, PipelineMetricsSnapshot

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/timeseries")
async def get_metrics_timeseries(
    period: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    metric: str = Query("queue_depths", pattern="^(queue_depths|throughput|quality|utilization)$"),
    session: Session = Depends(get_session)
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
                'tested': s.queue_tested,
                'selected': s.queue_selected,
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
                'classification': s.throughput_classification,
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
    session: Session = Depends(get_session)
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
            'avg_generated': round(result.avg_generated, 1) if result.avg_generated else 0,
            'avg_validated': round(result.avg_validated, 1) if result.avg_validated else 0,
            'avg_active': round(result.avg_active, 1) if result.avg_active else 0,
        },
        'utilization': {
            'max_generated': round(result.max_util_gen, 2) if result.max_util_gen else 0,
            'max_validated': round(result.max_util_val, 2) if result.max_util_val else 0,
            'max_active': round(result.max_util_active, 2) if result.max_util_active else 0,
        },
        'quality': {
            'avg_sharpe': round(result.avg_sharpe, 2) if result.avg_sharpe else None,
            'avg_win_rate': round(result.avg_win_rate, 3) if result.avg_win_rate else None,
        }
    }


@router.get("/alerts")
async def get_metric_alerts(
    session: Session = Depends(get_session)
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
        alerts.append({
            'severity': 'critical',
            'type': 'system_critical',
            'message': 'System status: CRITICAL',
            'duration_minutes': 0,
            'bottleneck': recent_snapshots[0].bottleneck_stage,
        })

    return {
        'timestamp': datetime.now(UTC).isoformat(),
        'alerts_count': len(alerts),
        'alerts': alerts
    }


@router.get("/current")
async def get_current_metrics(
    session: Session = Depends(get_session)
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
        'breakdown': {
            'pattern_strategies': latest.pattern_count,
            'ai_strategies': latest.ai_count,
        }
    }
