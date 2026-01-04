"""
Task execution tracking helper.

Provides context manager for automatic database tracking of scheduled tasks.
"""
from contextlib import contextmanager
from datetime import datetime, UTC
from typing import Optional, Any, Dict
import logging

from src.database import get_session, ScheduledTaskExecution

logger = logging.getLogger(__name__)


class TaskExecutionTracker:
    """Helper to track task execution metrics"""

    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.metadata: Dict[str, Any] = {}

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to task execution"""
        self.metadata[key] = value

    def get_metadata(self) -> dict:
        """Get all metadata"""
        return self.metadata


@contextmanager
def track_task_execution(
    task_name: str,
    task_type: str = 'scheduler',
    triggered_by: str = 'system'
):
    """
    Context manager to track scheduled task execution.

    Usage:
        with track_task_execution('cleanup_stale_processing') as tracker:
            # Do work
            tracker.add_metadata('cleaned_count', 5)

    Args:
        task_name: Name of the task (e.g., 'cleanup_stale_processing')
        task_type: Type of task ('scheduler', 'data_update', 'manual')
        triggered_by: Who triggered it ('system', 'user:email', 'api')

    Yields:
        TaskExecutionTracker instance for adding metadata

    Raises:
        Re-raises any exception after logging to database
    """
    started_at = datetime.now(UTC)
    execution_id = None
    tracker = None

    with get_session() as session:
        # Create execution record
        execution = ScheduledTaskExecution(
            task_name=task_name,
            task_type=task_type,
            status='RUNNING',
            started_at=started_at,
            triggered_by=triggered_by
        )
        session.add(execution)
        session.commit()
        session.refresh(execution)

        execution_id = execution.id
        tracker = TaskExecutionTracker(str(execution_id))

        logger.info(f"Task started: {task_name} (execution_id={execution_id})")

    try:
        # Yield tracker to caller
        yield tracker

        # Success - update execution record
        completed_at = datetime.now(UTC)
        duration = (completed_at - started_at).total_seconds()

        with get_session() as session:
            execution = session.query(ScheduledTaskExecution).filter(
                ScheduledTaskExecution.id == execution_id
            ).first()

            if execution:
                execution.status = 'SUCCESS'
                execution.completed_at = completed_at
                execution.duration_seconds = duration
                execution.task_metadata = tracker.get_metadata()
                session.commit()

                logger.info(
                    f"Task completed: {task_name} "
                    f"(duration={duration:.2f}s, execution_id={execution_id})"
                )

    except Exception as e:
        # Failure - log error
        completed_at = datetime.now(UTC)
        duration = (completed_at - started_at).total_seconds()

        with get_session() as session:
            execution = session.query(ScheduledTaskExecution).filter(
                ScheduledTaskExecution.id == execution_id
            ).first()

            if execution:
                execution.status = 'FAILED'
                execution.completed_at = completed_at
                execution.duration_seconds = duration
                execution.error_message = str(e)
                execution.task_metadata = tracker.get_metadata() if tracker else {}
                session.commit()

        logger.error(
            f"Task failed: {task_name} (error={e}, execution_id={execution_id})",
            exc_info=True
        )

        # Re-raise to preserve original behavior
        raise


def get_task_history(
    task_name: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 50
) -> list:
    """
    Get recent task execution history.

    Args:
        task_name: Filter by task name (optional)
        task_type: Filter by task type (optional)
        limit: Max results to return

    Returns:
        List of ScheduledTaskExecution records
    """
    with get_session() as session:
        query = session.query(ScheduledTaskExecution)

        if task_name:
            query = query.filter(ScheduledTaskExecution.task_name == task_name)

        if task_type:
            query = query.filter(ScheduledTaskExecution.task_type == task_type)

        executions = (
            query
            .order_by(ScheduledTaskExecution.started_at.desc())
            .limit(limit)
            .all()
        )

        return executions
