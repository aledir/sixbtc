"""
Subaccounts API routes

GET /api/subaccounts - List all subaccounts
GET /api/subaccounts/{id} - Get specific subaccount
"""
from typing import List

from fastapi import APIRouter, HTTPException

from src.api.schemas import SubaccountInfo, SubaccountsResponse
from src.config.loader import load_config
from src.database import Subaccount, Strategy, Trade, get_session
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_total_subaccounts() -> int:
    """Get total subaccounts from config."""
    config = load_config()
    return config.get_required('hyperliquid.subaccounts.count')


def get_subaccount_data(session, subaccount: Subaccount) -> SubaccountInfo:
    """Convert DB subaccount to API response format."""
    strategy_name = None
    if subaccount.strategy_id:
        strategy = session.query(Strategy).filter(
            Strategy.id == subaccount.strategy_id
        ).first()
        if strategy:
            strategy_name = strategy.name

    # Map DB status to API status
    if subaccount.status == "ACTIVE":
        status = "active"
    elif subaccount.status == "PAUSED":
        status = "idle"
    else:
        status = "error"

    # If no strategy assigned, mark as idle
    if not subaccount.strategy_id:
        status = "idle"

    # Calculate PnL percentage
    allocated = subaccount.allocated_capital or 0
    pnl = subaccount.total_pnl or 0
    pnl_pct = (pnl / allocated * 100) if allocated > 0 else 0

    return SubaccountInfo(
        index=subaccount.id,
        status=status,
        strategy_id=subaccount.strategy_id,
        strategy_name=strategy_name,
        balance=subaccount.current_balance or 0,
        pnl=pnl,
        pnl_pct=pnl_pct,
        open_positions=subaccount.open_positions_count or 0,
        last_trade_at=subaccount.last_trade_at,
    )


@router.get("/subaccounts", response_model=SubaccountsResponse)
async def list_subaccounts():
    """
    Get all subaccounts with their current status.

    Returns configured number of subaccounts (from config).
    """
    total = get_total_subaccounts()

    try:
        with get_session() as session:
            subaccounts = session.query(Subaccount).order_by(Subaccount.id).all()

            # If no subaccounts exist, create default ones
            if not subaccounts:
                items = []
                for i in range(1, total + 1):
                    items.append(SubaccountInfo(
                        index=i,
                        status="idle",
                        strategy_id=None,
                        strategy_name=None,
                        balance=0,
                        pnl=0,
                        pnl_pct=0,
                        open_positions=0,
                        last_trade_at=None,
                    ))
                return SubaccountsResponse(
                    items=items,
                    total_balance=0,
                    total_pnl=0,
                )

            items = [get_subaccount_data(session, s) for s in subaccounts]

            total_balance = sum(s.balance for s in items)
            total_pnl = sum(s.pnl for s in items)

            return SubaccountsResponse(
                items=items,
                total_balance=total_balance,
                total_pnl=total_pnl,
            )

    except Exception as e:
        logger.error(f"Error listing subaccounts: {e}")
        # Return empty default response
        items = []
        for i in range(1, total + 1):
            items.append(SubaccountInfo(
                index=i,
                status="idle",
                strategy_id=None,
                strategy_name=None,
                balance=0,
                pnl=0,
                pnl_pct=0,
                open_positions=0,
                last_trade_at=None,
            ))
        return SubaccountsResponse(items=items, total_balance=0, total_pnl=0)


@router.get("/subaccounts/{subaccount_id}", response_model=SubaccountInfo)
async def get_subaccount(subaccount_id: int):
    """
    Get details for a specific subaccount.
    """
    total = get_total_subaccounts()
    if subaccount_id < 1 or subaccount_id > total:
        raise HTTPException(status_code=400, detail=f"Subaccount ID must be between 1 and {total}")

    try:
        with get_session() as session:
            subaccount = session.query(Subaccount).filter(
                Subaccount.id == subaccount_id
            ).first()

            if not subaccount:
                # Return empty subaccount
                return SubaccountInfo(
                    index=subaccount_id,
                    status="idle",
                    strategy_id=None,
                    strategy_name=None,
                    balance=0,
                    pnl=0,
                    pnl_pct=0,
                    open_positions=0,
                    last_trade_at=None,
                )

            return get_subaccount_data(session, subaccount)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subaccount {subaccount_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
