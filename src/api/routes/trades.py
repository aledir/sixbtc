"""
Trades API routes

GET /api/trades - List trades with filters
GET /api/trades/summary - Aggregated trade statistics
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import desc, func

from src.api.schemas import TradeItem, TradesResponse, TradesSummary
from src.database import Trade, Strategy, get_session
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/trades", response_model=TradesResponse)
async def list_trades(
    status: Optional[str] = Query(None, description="Filter: open or closed"),
    strategy_id: Optional[UUID] = Query(None, description="Filter by strategy ID"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    subaccount_id: Optional[int] = Query(None, description="Filter by subaccount"),
    days: Optional[int] = Query(None, description="Only trades from last N days"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List trades with optional filters.

    Supports filtering by status (open/closed), strategy, symbol, subaccount.
    """
    try:
        with get_session() as session:
            query = session.query(Trade)

            # Apply filters
            if status == "open":
                query = query.filter(Trade.exit_time.is_(None))
            elif status == "closed":
                query = query.filter(Trade.exit_time.isnot(None))

            if strategy_id:
                query = query.filter(Trade.strategy_id == strategy_id)

            if symbol:
                query = query.filter(Trade.symbol == symbol.upper())

            if subaccount_id is not None:
                query = query.filter(Trade.subaccount_id == subaccount_id)

            if days:
                cutoff = datetime.now(UTC) - timedelta(days=days)
                query = query.filter(Trade.entry_time >= cutoff)

            # Get total count
            total = query.count()

            # Order by entry_time descending
            trades = query.order_by(desc(Trade.entry_time)).offset(offset).limit(limit).all()

            # Get strategy names
            strategy_ids = {t.strategy_id for t in trades}
            strategies = {}
            if strategy_ids:
                strats = session.query(Strategy).filter(Strategy.id.in_(strategy_ids)).all()
                strategies = {s.id: s.name for s in strats}

            # Convert to response format
            items = []
            for t in trades:
                trade_status = "open" if t.exit_time is None else "closed"
                items.append(TradeItem(
                    id=t.id,
                    strategy_id=t.strategy_id,
                    strategy_name=strategies.get(t.strategy_id),
                    symbol=t.symbol,
                    side=t.direction.lower() if t.direction else "unknown",
                    status=trade_status,
                    entry_price=t.entry_price,
                    exit_price=t.exit_price,
                    size=t.entry_size,
                    pnl=t.pnl_usd,
                    pnl_pct=t.pnl_pct,
                    subaccount_index=t.subaccount_id,
                    opened_at=t.entry_time,
                    closed_at=t.exit_time,
                ))

            return TradesResponse(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )

    except Exception as e:
        logger.error(f"Error listing trades: {e}")
        return TradesResponse(items=[], total=0, limit=limit, offset=offset)


@router.get("/trades/summary", response_model=TradesSummary)
async def get_trades_summary(
    days: Optional[int] = Query(None, description="Only include trades from last N days"),
    strategy_id: Optional[UUID] = Query(None, description="Filter by strategy ID"),
):
    """
    Get aggregated trade statistics.

    Returns win rate, total PnL, avg PnL, etc.
    """
    try:
        with get_session() as session:
            query = session.query(Trade).filter(Trade.exit_time.isnot(None))  # Only closed trades

            if days:
                cutoff = datetime.now(UTC) - timedelta(days=days)
                query = query.filter(Trade.exit_time >= cutoff)

            if strategy_id:
                query = query.filter(Trade.strategy_id == strategy_id)

            trades = query.all()

            if not trades:
                return TradesSummary()

            total_trades = len(trades)
            winning_trades = len([t for t in trades if (t.pnl_usd or 0) > 0])
            losing_trades = len([t for t in trades if (t.pnl_usd or 0) < 0])
            win_rate = winning_trades / total_trades if total_trades > 0 else 0

            pnl_values = [t.pnl_usd or 0 for t in trades]
            total_pnl = sum(pnl_values)
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
            best_trade = max(pnl_values) if pnl_values else 0
            worst_trade = min(pnl_values) if pnl_values else 0

            return TradesSummary(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                total_pnl=total_pnl,
                avg_pnl=avg_pnl,
                best_trade=best_trade,
                worst_trade=worst_trade,
            )

    except Exception as e:
        logger.error(f"Error getting trades summary: {e}")
        return TradesSummary()
