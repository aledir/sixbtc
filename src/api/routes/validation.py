"""
Validation Report API routes
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import func

from src.database import get_session, Strategy
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/validation/report")
async def get_validation_report():
    """
    Get validation pass/fail statistics
    """
    try:
        with get_session() as session:
            # Count strategies by validation status
            total = session.query(Strategy).filter(
                Strategy.status.in_(['VALIDATED', 'ACTIVE', 'LIVE', 'FAILED'])
            ).count()

            passed_lookahead = session.query(Strategy).filter(
                Strategy.status.in_(['VALIDATED', 'ACTIVE', 'LIVE']),
            ).count()

            failed = session.query(Strategy).filter(
                Strategy.status == 'FAILED'
            ).count()

            return {
                'total_validated': total,
                'passed': passed_lookahead,
                'failed': failed,
                'pass_rate': passed_lookahead / max(total, 1),
                'fail_rate': failed / max(total, 1),
            }

    except Exception as e:
        logger.error(f"Error getting validation report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
