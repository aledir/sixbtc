"""
Coin registry and pairs update endpoints.
"""
from fastapi import APIRouter

from src.data.coin_registry import get_registry
from src.database import get_session, PairsUpdateLog, ScheduledTaskExecution
from src.api.schemas import (
    CoinRegistryStatsResponse,
    PairsUpdateHistoryResponse,
    PairsUpdateDetailResponse
)

router = APIRouter()


@router.get("/coins/registry/stats", response_model=CoinRegistryStatsResponse)
async def get_coin_registry_stats():
    """
    Get CoinRegistry cache statistics.

    Returns:
    - Total coins in cache
    - Active coins count
    - Cache age
    - Last DB update timestamp
    """
    registry = get_registry()
    stats = registry.get_cache_stats()

    return CoinRegistryStatsResponse(
        total_coins=stats['total_coins'],
        active_coins=stats['active_coins'],
        cache_age_seconds=stats['cache_age_seconds'],
        db_updated_at=stats['db_updated_at'].isoformat() if stats['db_updated_at'] else None
    )


@router.get("/coins/pairs/history", response_model=PairsUpdateHistoryResponse)
async def get_pairs_update_history(limit: int = 20):
    """
    Get history of pairs update operations.

    Returns list of recent pairs updates with detailed metrics.
    """
    with get_session() as session:
        # Join task executions with pairs update logs
        updates = (
            session.query(ScheduledTaskExecution, PairsUpdateLog)
            .join(
                PairsUpdateLog,
                ScheduledTaskExecution.id == PairsUpdateLog.execution_id
            )
            .filter(ScheduledTaskExecution.task_name == 'update_pairs')
            .order_by(ScheduledTaskExecution.started_at.desc())
            .limit(limit)
            .all()
        )

        return PairsUpdateHistoryResponse(
            updates=[
                PairsUpdateDetailResponse(
                    execution_id=str(exec.id),
                    started_at=exec.started_at.isoformat(),
                    completed_at=exec.completed_at.isoformat() if exec.completed_at else None,
                    duration_seconds=exec.duration_seconds,
                    status=exec.status,
                    total_pairs=log.total_pairs,
                    new_pairs=log.new_pairs,
                    updated_pairs=log.updated_pairs,
                    deactivated_pairs=log.deactivated_pairs,
                    top_10_symbols=log.top_10_symbols or []
                )
                for exec, log in updates
            ],
            total=len(updates)
        )
