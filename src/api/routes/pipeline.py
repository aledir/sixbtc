"""
Pipeline Health API Routes

Endpoints for monitoring pipeline health and performance.
"""
from datetime import datetime, timedelta, UTC
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func

from src.api.schemas import (
    PipelineHealthResponse,
    PipelineStageHealth,
    PipelineStatsResponse,
    PipelineTimeSeriesPoint,
    QualityDistributionResponse,
    QualityDistribution,
    QualityBucket,
)
from src.config import load_config
from src.database import get_session, Strategy, BacktestResult
from src.database.pipeline_metrics import PipelineMetrics
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/pipeline/health", response_model=PipelineHealthResponse)
async def get_pipeline_health():
    """
    Get real-time pipeline health status

    Returns queue depths, processing rates, bottlenecks, and critical issues
    for all pipeline stages.
    """
    try:
        with get_session() as session:
            config = load_config()._raw_config

            # Get queue depths
            depths = PipelineMetrics.get_queue_depths(session)

            # Get limits from config (NO hardcoding!)
            limits_config = config['pipeline']['queue_limits']
            active_pool_config = config.get('active_pool', {})
            rotator_config = config.get('rotator', {})
            limits = {
                'GENERATED': limits_config['generated'],
                'VALIDATED': limits_config['validated'],
                'ACTIVE': active_pool_config.get('max_size', 300),
                'LIVE': rotator_config.get('max_live_strategies', 10),
            }

            # Build stage health for each pipeline stage
            stages = []

            # Stage 1: Generation
            stage_data = _build_stage_health(
                session=session,
                stage_name="generation",
                status="GENERATED",
                queue_depth=depths['GENERATED'],
                queue_limit=limits['GENERATED'],
                config=config
            )
            stages.append(stage_data)

            # Stage 2: Validation
            stage_data = _build_stage_health(
                session=session,
                stage_name="validation",
                status="VALIDATED",
                queue_depth=depths['VALIDATED'],
                queue_limit=limits['VALIDATED'],
                config=config
            )
            stages.append(stage_data)

            # Stage 3: Active Pool (backtested strategies)
            stage_data = _build_stage_health(
                session=session,
                stage_name="active_pool",
                status="ACTIVE",
                queue_depth=depths.get('ACTIVE', 0),
                queue_limit=limits['ACTIVE'],
                config=config
            )
            stages.append(stage_data)

            # Stage 4: Live (deployed strategies)
            stage_data = _build_stage_health(
                session=session,
                stage_name="live",
                status="LIVE",
                queue_depth=depths.get('LIVE', 0),
                queue_limit=limits['LIVE'],
                config=config
            )
            stages.append(stage_data)

            # Detect bottleneck
            bottleneck = PipelineMetrics.detect_bottleneck(depths, limits)

            # Get critical issues
            critical_issues = PipelineMetrics.get_critical_issues(
                queue_depths=depths,
                queue_limits=limits,
                session=session,
                hours=1
            )

            # Overall status
            overall_status = PipelineMetrics.get_overall_status(
                queue_depths=depths,
                queue_limits=limits,
                critical_issues=critical_issues
            )

            # End-to-end throughput
            throughput = PipelineMetrics.get_end_to_end_throughput(session, hours=1)

            return PipelineHealthResponse(
                timestamp=datetime.now(UTC),
                overall_status=overall_status,
                stages=stages,
                bottleneck=bottleneck,
                throughput_strategies_per_hour=throughput,
                critical_issues=critical_issues
            )

    except Exception as e:
        logger.error(f"Error in /pipeline/health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _build_stage_health(
    session,
    stage_name: str,
    status: str,
    queue_depth: int,
    queue_limit: int,
    config: dict
) -> PipelineStageHealth:
    """
    Build health metrics for a single pipeline stage

    Args:
        session: Database session
        stage_name: Stage name (generation, validation, etc.)
        status: Strategy status for this stage
        queue_depth: Current queue depth
        queue_limit: Configured limit
        config: Full config dict

    Returns:
        PipelineStageHealth object
    """
    # Calculate utilization
    utilization = (queue_depth / queue_limit * 100) if queue_limit > 0 else 0

    # Determine status
    if utilization >= 100:
        status_str = "backpressure"
    elif utilization >= 80:
        status_str = "warning"
    elif queue_depth > 0 and PipelineMetrics.calculate_throughput(session, status, 1) == 0:
        status_str = "stalled"
    else:
        status_str = "healthy"

    # Processing rate (strategies/hour)
    processing_rate = PipelineMetrics.calculate_throughput(session, status, hours=1)

    # Avg processing time (if available)
    # NOTE: For now, return None since we don't have completion timestamps populated yet
    avg_processing_time = None

    # Workers (TODO: get from config or runtime monitoring)
    # For now, use placeholder values
    active_workers = 1
    max_workers = config.get('backtesting', {}).get('parallel_workers', 10) if stage_name == 'backtesting' else 1

    # Success/failure rates
    success_rate = PipelineMetrics.calculate_success_rate(session, status, hours=1)
    failure_rate = PipelineMetrics.calculate_failure_rate(session, status, hours=1)

    # Recent activity (last hour and 24h)
    processed_1h = PipelineMetrics.calculate_throughput(session, status, hours=1)
    processed_24h = PipelineMetrics.calculate_throughput(session, status, hours=24)

    # Failed count (last hour)
    one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    failed_1h = session.query(Strategy).filter(
        Strategy.status == 'FAILED',
        Strategy.created_at >= one_hour_ago
    ).count()

    return PipelineStageHealth(
        stage=stage_name,
        status=status_str,
        queue_depth=queue_depth,
        queue_limit=queue_limit,
        utilization_pct=round(utilization, 1),
        processing_rate=round(processing_rate, 2),
        avg_processing_time=avg_processing_time,
        active_workers=active_workers,
        max_workers=max_workers,
        success_rate=round(success_rate, 1),
        failure_rate=round(failure_rate, 1),
        processed_last_hour=int(processed_1h),
        processed_last_24h=int(processed_24h * 24),
        failed_last_hour=failed_1h
    )


@router.get("/pipeline/stats", response_model=PipelineStatsResponse)
async def get_pipeline_stats(
    period: str = Query("24h", description="Time period: 24h, 7d, 30d")
):
    """
    Get historical pipeline statistics

    Returns time-series data for throughput, queue depths, and failures
    over the specified period.
    """
    try:
        # Parse period
        period_map = {
            "24h": 24,
            "7d": 24 * 7,
            "30d": 24 * 30,
        }
        hours = period_map.get(period, 24)

        with get_session() as session:
            # For simplicity, return hourly aggregates
            # In production, might want to sample less frequently for longer periods

            data_points = []
            since = datetime.now(UTC) - timedelta(hours=hours)

            # Get current queue depths as latest data point
            depths = PipelineMetrics.get_queue_depths(session)

            for status_name, db_status in [
                ("generation", "GENERATED"),
                ("validation", "VALIDATED"),
                ("active_pool", "ACTIVE"),
                ("live", "LIVE"),
            ]:
                # Current throughput
                throughput = PipelineMetrics.calculate_throughput(session, db_status, hours=1)

                # Current queue
                queue = depths[db_status]

                # Failures
                failures = session.query(Strategy).filter(
                    Strategy.status == 'FAILED',
                    Strategy.created_at >= since
                ).count()

                data_points.append(
                    PipelineTimeSeriesPoint(
                        timestamp=datetime.now(UTC),
                        stage=status_name,
                        throughput=round(throughput, 2),
                        avg_processing_time=None,  # Not yet available
                        queue_depth=queue,
                        failures=failures
                    )
                )

            # Totals
            total_generated = depths['GENERATED']
            total_validated = depths['VALIDATED']
            total_active = depths.get('ACTIVE', 0)
            total_live = depths.get('LIVE', 0)

            # Overall throughput
            overall_throughput = PipelineMetrics.get_end_to_end_throughput(session, hours=1)

            # Bottleneck
            config = load_config()._raw_config
            limits_config = config['pipeline']['queue_limits']
            active_pool_config = config.get('active_pool', {})
            rotator_config = config.get('rotator', {})
            limits = {
                'GENERATED': limits_config['generated'],
                'VALIDATED': limits_config['validated'],
                'ACTIVE': active_pool_config.get('max_size', 300),
                'LIVE': rotator_config.get('max_live_strategies', 10),
            }
            bottleneck = PipelineMetrics.detect_bottleneck(depths, limits) or "none"

            return PipelineStatsResponse(
                period_hours=hours,
                data_points=data_points,
                total_generated=total_generated,
                total_validated=total_validated,
                total_active=total_active,
                total_live=total_live,
                overall_throughput=round(overall_throughput, 2),
                bottleneck_stage=bottleneck
            )

    except Exception as e:
        logger.error(f"Error in /pipeline/stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/quality-distribution", response_model=QualityDistributionResponse)
async def get_quality_distribution():
    """
    Get strategy quality distribution across pipeline stages

    Returns distribution of strategies by quality buckets (Sharpe ranges),
    strategy type, and timeframe for each stage.
    """
    try:
        with get_session() as session:
            distributions = []

            # Analyze ACTIVE and LIVE stages
            for status in ['ACTIVE', 'LIVE']:
                # Get strategies at this stage with backtest results
                strategies = session.query(Strategy, BacktestResult).join(
                    BacktestResult,
                    Strategy.id == BacktestResult.strategy_id
                ).filter(
                    Strategy.status == status,
                    BacktestResult.period_type == 'full'  # Use full-period backtest
                ).all()

                if not strategies:
                    # Empty distribution
                    distributions.append(
                        QualityDistribution(
                            stage=status,
                            buckets=[],
                            by_type={},
                            by_timeframe={}
                        )
                    )
                    continue

                # Quality buckets by Sharpe ratio
                buckets_data = {
                    "0-20": [],
                    "20-40": [],
                    "40-60": [],
                    "60-80": [],
                    "80-100": [],
                }

                by_type = {}
                by_timeframe = {}

                for strategy, backtest in strategies:
                    sharpe = backtest.sharpe_ratio or 0
                    win_rate = backtest.win_rate or 0

                    # Determine bucket (by Sharpe * 100 for simplicity)
                    # In real system, use composite score
                    score = min(sharpe * 50, 100)  # Rough mapping

                    if score < 20:
                        bucket_name = "0-20"
                    elif score < 40:
                        bucket_name = "20-40"
                    elif score < 60:
                        bucket_name = "40-60"
                    elif score < 80:
                        bucket_name = "60-80"
                    else:
                        bucket_name = "80-100"

                    buckets_data[bucket_name].append((sharpe, win_rate))

                    # Count by type
                    by_type[strategy.strategy_type] = by_type.get(strategy.strategy_type, 0) + 1

                    # Count by timeframe
                    by_timeframe[strategy.timeframe] = by_timeframe.get(strategy.timeframe, 0) + 1

                # Build buckets
                buckets = []
                for range_name, data in buckets_data.items():
                    if data:
                        avg_sharpe = sum(s for s, w in data) / len(data)
                        avg_win_rate = sum(w for s, w in data) / len(data)
                    else:
                        avg_sharpe = 0.0
                        avg_win_rate = 0.0

                    buckets.append(
                        QualityBucket(
                            range=range_name,
                            count=len(data),
                            avg_sharpe=round(avg_sharpe, 2),
                            avg_win_rate=round(avg_win_rate, 3)
                        )
                    )

                distributions.append(
                    QualityDistribution(
                        stage=status,
                        buckets=buckets,
                        by_type=by_type,
                        by_timeframe=by_timeframe
                    )
                )

            return QualityDistributionResponse(distributions=distributions)

    except Exception as e:
        logger.error(f"Error in /strategies/quality-distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
