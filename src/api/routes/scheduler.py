"""
Scheduler monitoring and control endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta, UTC
from typing import Optional

from src.database import get_session, ScheduledTaskExecution
from src.api.schemas import (
    TaskExecutionListResponse,
    TaskExecutionDetailResponse,
    TaskStatsResponse,
    TaskTriggerRequest,
    TaskTriggerResponse
)
from src.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/scheduler/tasks", response_model=TaskExecutionListResponse)
async def get_task_executions(
    task_name: Optional[str] = Query(None, description="Filter by task name"),
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Max results")
):
    """
    Get list of recent task executions.

    Query Parameters:
    - task_name: Filter by specific task (e.g., 'cleanup_stale_processing')
    - task_type: Filter by type ('scheduler', 'data_update', 'manual')
    - status: Filter by status ('SUCCESS', 'FAILED', 'RUNNING')
    - limit: Max results (default 50, max 500)
    """
    with get_session() as session:
        query = session.query(ScheduledTaskExecution)

        if task_name:
            query = query.filter(ScheduledTaskExecution.task_name == task_name)
        if task_type:
            query = query.filter(ScheduledTaskExecution.task_type == task_type)
        if status:
            query = query.filter(ScheduledTaskExecution.status == status)

        executions = (
            query
            .order_by(ScheduledTaskExecution.started_at.desc())
            .limit(limit)
            .all()
        )

        return TaskExecutionListResponse(
            executions=[
                TaskExecutionDetailResponse(
                    id=str(e.id),
                    task_name=e.task_name,
                    task_type=e.task_type,
                    status=e.status,
                    started_at=e.started_at.isoformat(),
                    completed_at=e.completed_at.isoformat() if e.completed_at else None,
                    duration_seconds=e.duration_seconds,
                    error_message=e.error_message,
                    metadata=e.task_metadata or {},
                    triggered_by=e.triggered_by or 'system'
                )
                for e in executions
            ],
            total=len(executions)
        )


@router.get("/scheduler/tasks/{task_name}/stats", response_model=TaskStatsResponse)
async def get_task_stats(
    task_name: str,
    period_hours: int = Query(24, ge=1, le=720, description="Period in hours")
):
    """
    Get statistics for a specific task over time period.

    Returns:
    - Total executions
    - Success/failure counts
    - Average duration
    - Failure rate
    - Recent executions
    """
    with get_session() as session:
        cutoff = datetime.now(UTC) - timedelta(hours=period_hours)

        executions = (
            session.query(ScheduledTaskExecution)
            .filter(
                ScheduledTaskExecution.task_name == task_name,
                ScheduledTaskExecution.started_at >= cutoff
            )
            .all()
        )

        if not executions:
            raise HTTPException(
                status_code=404,
                detail=f"No executions found for task '{task_name}' in last {period_hours}h"
            )

        total = len(executions)
        successes = [e for e in executions if e.status == 'SUCCESS']
        failures = [e for e in executions if e.status == 'FAILED']

        avg_duration = (
            sum(e.duration_seconds for e in successes if e.duration_seconds)
            / len(successes)
            if successes else None
        )

        return TaskStatsResponse(
            task_name=task_name,
            period_hours=period_hours,
            total_executions=total,
            successful_executions=len(successes),
            failed_executions=len(failures),
            avg_duration_seconds=avg_duration,
            failure_rate=len(failures) / total if total > 0 else 0,
            last_execution=executions[0].started_at.isoformat() if executions else None
        )


@router.post("/scheduler/tasks/{task_name}/trigger", response_model=TaskTriggerResponse)
async def trigger_task_manually(
    task_name: str,
    request: TaskTriggerRequest
):
    """
    Manually trigger a scheduled task.

    WARNING: This immediately executes the task. Use with caution.
    """
    logger.warning(f"Manual task trigger requested: {task_name} by {request.triggered_by}")

    # Validate task name
    valid_tasks = [
        'update_pairs',
        'cleanup_stale_processing',
        'cleanup_old_failed',
        'refresh_data_cache'
    ]

    if task_name not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Must be one of: {', '.join(valid_tasks)}"
        )

    try:
        # Import appropriate function based on task
        if task_name == 'update_pairs':
            from src.data.pairs_updater import PairsUpdater
            updater = PairsUpdater()
            result = updater.update(triggered_by=request.triggered_by)
            execution_id = None  # Would need to extract from tracker

        elif task_name in ['cleanup_stale_processing', 'cleanup_old_failed', 'refresh_data_cache']:
            raise HTTPException(
                status_code=501,
                detail=f"Manual trigger for '{task_name}' not yet implemented"
            )

        return TaskTriggerResponse(
            success=True,
            message=f"Task '{task_name}' triggered successfully",
            execution_id=execution_id
        )

    except Exception as e:
        logger.error(f"Failed to trigger task {task_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scheduler/health")
async def get_scheduler_health():
    """
    Get overall scheduler health status.

    Returns:
    - Active tasks count
    - Recent failures
    - Last execution times
    """
    with get_session() as session:
        # Last 1 hour
        cutoff = datetime.now(UTC) - timedelta(hours=1)

        recent = (
            session.query(ScheduledTaskExecution)
            .filter(ScheduledTaskExecution.started_at >= cutoff)
            .all()
        )

        failures = [e for e in recent if e.status == 'FAILED']
        running = [e for e in recent if e.status == 'RUNNING']

        # Get last execution for each known task
        task_names = [
            'update_pairs',
            'cleanup_stale_processing',
            'cleanup_old_failed',
            'generate_daily_report',
            'refresh_data_cache'
        ]

        last_runs = {}
        for task in task_names:
            last = (
                session.query(ScheduledTaskExecution)
                .filter(ScheduledTaskExecution.task_name == task)
                .order_by(ScheduledTaskExecution.started_at.desc())
                .first()
            )
            if last:
                last_runs[task] = {
                    'last_run': last.started_at.isoformat(),
                    'status': last.status,
                    'duration': last.duration_seconds
                }

        return {
            'status': 'unhealthy' if len(failures) > 5 else 'healthy',
            'recent_executions_1h': len(recent),
            'recent_failures_1h': len(failures),
            'currently_running': len(running),
            'last_executions': last_runs
        }
