"""
Template Analytics API routes
"""
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, desc

from src.database import get_session, StrategyTemplate, Strategy
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/templates")
async def list_templates():
    """
    List all strategy templates with performance stats
    """
    try:
        with get_session() as session:
            templates = session.query(StrategyTemplate).all()

            items = []
            for t in templates:
                # Count strategies generated from this template
                total_generated = session.query(Strategy).filter(
                    Strategy.template_id == t.id
                ).count()

                # Count by status
                tested = session.query(Strategy).filter(
                    Strategy.template_id == t.id,
                    Strategy.status == 'TESTED'
                ).count()

                selected = session.query(Strategy).filter(
                    Strategy.template_id == t.id,
                    Strategy.status == 'SELECTED'
                ).count()

                live = session.query(Strategy).filter(
                    Strategy.template_id == t.id,
                    Strategy.status == 'LIVE'
                ).count()

                items.append({
                    'id': str(t.id),
                    'name': t.name,
                    'strategy_type': t.strategy_type,
                    'timeframe': t.timeframe,
                    'structure_id': t.structure_id,
                    'total_generated': total_generated,
                    'tested': tested,
                    'selected': selected,
                    'live': live,
                    'success_rate': selected / max(tested, 1),
                    'created_at': t.created_at.isoformat() if t.created_at else None,
                })

            return {
                'items': items,
                'total': len(items),
            }

    except Exception as e:
        logger.error(f"Error listing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
