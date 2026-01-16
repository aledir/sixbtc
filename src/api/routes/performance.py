"""
Performance analytics API endpoints
"""
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta, UTC
from sqlalchemy import func, and_

from src.database import get_session, PerformanceSnapshot, Subaccount
from src.api.schemas import PerformanceEquityResponse, EquityPoint

router = APIRouter()

# Cache for equity curve (expensive DB query)
_equity_cache: Dict[str, Any] = {}
_equity_cache_time: Dict[str, float] = {}
EQUITY_CACHE_TTL_SECONDS = 60  # Cache for 60 seconds


@router.get("/performance/equity", response_model=PerformanceEquityResponse)
async def get_equity_curve(
    period: str = Query("24h", description="Time period: 1h, 6h, 24h, 7d, 30d, all"),
    strategy_id: str = Query(None, description="Optional: filter by strategy"),
):
    """
    Get equity curve for portfolio or specific strategy

    Returns time-series of portfolio value (equity) over time.
    Portfolio equity comes from PerformanceSnapshot with strategy_id=NULL
    Cached for 30 seconds to reduce DB load.
    """
    # Check cache
    cache_key = f"{period}_{strategy_id or 'portfolio'}"
    now = time.time()
    if cache_key in _equity_cache:
        if (now - _equity_cache_time.get(cache_key, 0)) < EQUITY_CACHE_TTL_SECONDS:
            return _equity_cache[cache_key]

    with get_session() as session:
        # Parse period to timedelta
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "all": None,  # No time filter
        }

        if period not in period_map:
            raise HTTPException(status_code=400, detail=f"Invalid period: {period}. Use: 1h, 6h, 24h, 7d, 30d, all")

        td = period_map[period]
        cutoff = datetime.now(UTC) - td if td else None

        # Build query - portfolio snapshots have strategy_id=NULL
        if strategy_id:
            query = session.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.strategy_id == strategy_id
            ).order_by(PerformanceSnapshot.snapshot_time)
        else:
            # Portfolio-level snapshots (strategy_id is NULL)
            query = session.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.strategy_id == None
            ).order_by(PerformanceSnapshot.snapshot_time)

        if cutoff:
            query = query.filter(PerformanceSnapshot.snapshot_time >= cutoff)

        snapshots = query.all()

        if not snapshots:
            # Return empty curve with current portfolio value from subaccounts
            total_balance = session.query(func.sum(Subaccount.balance)).scalar() or 0
            total_unrealized = session.query(func.sum(Subaccount.unrealized_pnl)).scalar() or 0
            current_equity = total_balance + total_unrealized

            response = PerformanceEquityResponse(
                period=period,
                subaccount_id=None,
                data_points=[
                    EquityPoint(
                        timestamp=datetime.now(UTC).isoformat(),
                        equity=current_equity,
                        balance=current_equity,
                        unrealized_pnl=0.0,
                        realized_pnl=0.0,
                        total_pnl=0.0,
                    )
                ],
                start_equity=current_equity,
                end_equity=current_equity,
                peak_equity=current_equity,
                max_drawdown=0.0,
                current_drawdown=0.0,
                total_return=0.0,
            )

            # Cache the result
            _equity_cache[cache_key] = response
            _equity_cache_time[cache_key] = now

            return response

        # Convert snapshots to EquityPoint
        data_points = []
        for snap in snapshots:
            # Use total_capital as equity (portfolio value)
            equity = snap.total_capital or 0.0

            data_points.append(
                EquityPoint(
                    timestamp=snap.snapshot_time.isoformat(),
                    equity=equity,
                    balance=snap.available_capital or 0.0,
                    unrealized_pnl=snap.total_exposure or 0.0,  # Approx
                    realized_pnl=snap.total_pnl_usd or 0.0,
                    total_pnl=snap.total_pnl_usd or 0.0,
                )
            )

        # Calculate metrics
        start_equity = data_points[0].equity
        end_equity = data_points[-1].equity
        peak_equity = max(p.equity for p in data_points)

        # Calculate max drawdown
        max_dd = 0.0
        peak = start_equity
        for point in data_points:
            if point.equity > peak:
                peak = point.equity
            dd = (peak - point.equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Current drawdown
        current_dd = (peak_equity - end_equity) / peak_equity if peak_equity > 0 else 0

        # Total return
        total_return = (end_equity - start_equity) / start_equity if start_equity > 0 else 0

        response = PerformanceEquityResponse(
            period=period,
            subaccount_id=None,
            data_points=data_points,
            start_equity=start_equity,
            end_equity=end_equity,
            peak_equity=peak_equity,
            max_drawdown=max_dd,
            current_drawdown=current_dd,
            total_return=total_return,
        )

        # Cache the result
        _equity_cache[cache_key] = response
        _equity_cache_time[cache_key] = now

        return response


@router.get("/performance/drawdown", response_model=dict)
async def get_drawdown_series(
    period: str = Query("24h", description="Time period: 1h, 6h, 24h, 7d, 30d, all"),
    strategy_id: str = Query(None, description="Optional: filter by strategy"),
):
    """
    Get drawdown time-series

    Returns percentage drawdown from peak at each timestamp.
    Useful for drawdown charts showing risk exposure over time.
    """
    with get_session() as session:
        # Parse period
        period_map = {
            "1h": timedelta(hours=1),
            "6h": timedelta(hours=6),
            "24h": timedelta(hours=24),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30),
            "all": None,
        }

        if period not in period_map:
            raise HTTPException(status_code=400, detail=f"Invalid period: {period}")

        td = period_map[period]
        cutoff = datetime.now(UTC) - td if td else None

        # Build query
        if strategy_id:
            query = session.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.strategy_id == strategy_id
            ).order_by(PerformanceSnapshot.snapshot_time)
        else:
            query = session.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.strategy_id == None
            ).order_by(PerformanceSnapshot.snapshot_time)

        if cutoff:
            query = query.filter(PerformanceSnapshot.snapshot_time >= cutoff)

        snapshots = query.all()

        if not snapshots:
            return {
                "period": period,
                "strategy_id": strategy_id,
                "data_points": [],
            }

        # Calculate drawdown series
        data_points = []
        peak = snapshots[0].total_capital or 0.0

        for snap in snapshots:
            equity = snap.total_capital or 0.0

            if equity > peak:
                peak = equity

            drawdown_pct = (peak - equity) / peak if peak > 0 else 0

            data_points.append({
                "timestamp": snap.snapshot_time.isoformat(),
                "drawdown_pct": drawdown_pct,
                "equity": equity,
                "peak": peak,
            })

        return {
            "period": period,
            "strategy_id": strategy_id,
            "data_points": data_points,
            "max_drawdown": max(p["drawdown_pct"] for p in data_points) if data_points else 0,
            "current_drawdown": data_points[-1]["drawdown_pct"] if data_points else 0,
        }
