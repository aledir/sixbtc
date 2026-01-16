"""
Positions API routes

GET /api/positions - Get all open positions from Hyperliquid (real-time)
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import PositionInfo, PositionsResponse
from src.config.loader import load_config
from src.database import Subaccount, Strategy, get_session
from src.executor.hyperliquid_client import HyperliquidClient
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_hyperliquid_client() -> HyperliquidClient:
    """Get or create HyperliquidClient instance."""
    return HyperliquidClient()


def get_total_subaccounts() -> int:
    """Get total subaccounts from config."""
    config = load_config()
    return config.get_required('hyperliquid.subaccounts.count')


@router.get("/positions", response_model=PositionsResponse)
async def get_all_positions(
    subaccount_id: Optional[int] = Query(None, description="Filter by subaccount ID"),
):
    """
    Get all open positions from Hyperliquid.

    Fetches real-time position data directly from the exchange.

    Args:
        subaccount_id: Optional filter for specific subaccount (1-N)

    Returns:
        PositionsResponse with all positions and aggregated stats
    """
    total_subaccounts = get_total_subaccounts()

    # Validate subaccount_id if provided
    if subaccount_id is not None:
        if subaccount_id < 1 or subaccount_id > total_subaccounts:
            raise HTTPException(
                status_code=400,
                detail=f"Subaccount ID must be between 1 and {total_subaccounts}"
            )

    all_positions: List[PositionInfo] = []

    try:
        client = get_hyperliquid_client()

        # Get strategy names for each subaccount from DB
        subaccount_strategies = {}
        with get_session() as session:
            subaccounts = session.query(Subaccount).all()
            for sub in subaccounts:
                if sub.strategy_id:
                    strategy = session.query(Strategy).filter(
                        Strategy.id == sub.strategy_id
                    ).first()
                    if strategy:
                        subaccount_strategies[sub.id] = strategy.name

        # Determine which subaccounts to query
        if subaccount_id is not None:
            subaccount_ids = [subaccount_id]
        else:
            subaccount_ids = list(range(1, total_subaccounts + 1))

        # Fetch positions from each subaccount
        for sub_id in subaccount_ids:
            try:
                positions = client.get_positions(sub_id)

                for pos in positions:
                    all_positions.append(PositionInfo(
                        subaccount_id=sub_id,
                        strategy_name=subaccount_strategies.get(sub_id),
                        symbol=pos.symbol,
                        side=pos.side,
                        size=pos.size,
                        entry_price=pos.entry_price,
                        mark_price=pos.current_price,
                        unrealized_pnl=pos.unrealized_pnl,
                        leverage=pos.leverage,
                        liquidation_price=pos.liquidation_price,
                        margin_used=pos.margin_used,
                    ))

            except Exception as e:
                logger.warning(f"Failed to get positions for subaccount {sub_id}: {e}")
                continue

        # Calculate aggregates
        total_unrealized_pnl = sum(p.unrealized_pnl for p in all_positions)
        total_margin_used = sum(p.margin_used for p in all_positions)

        return PositionsResponse(
            positions=all_positions,
            total_unrealized_pnl=total_unrealized_pnl,
            total_positions=len(all_positions),
            total_margin_used=total_margin_used,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        # Return empty response on error
        return PositionsResponse(
            positions=[],
            total_unrealized_pnl=0.0,
            total_positions=0,
            total_margin_used=0.0,
        )
