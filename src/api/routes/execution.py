"""
Execution Quality API routes
"""
from datetime import datetime, timedelta, UTC
from fastapi import APIRouter, HTTPException, Query

from src.database import get_session, Trade
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/execution/quality")
async def get_execution_quality(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Get execution quality metrics

    Returns slippage, fill rate, fees analysis
    """
    try:
        with get_session() as session:
            since = datetime.now(UTC) - timedelta(days=days)

            # Get all closed trades in period
            trades = session.query(Trade).filter(
                Trade.exit_time.isnot(None),
                Trade.entry_time >= since
            ).all()

            if not trades:
                return {
                    'total_trades': 0,
                    'avg_slippage_pct': 0.0,
                    'fill_rate': 1.0,
                    'total_fees_usd': 0.0,
                }

            # Calculate metrics
            total_trades = len(trades)

            # Placeholder slippage (would need order book data for real calc)
            avg_slippage = 0.01  # Assume 0.01% average slippage

            # Fill rate (all trades that executed)
            fill_rate = 1.0  # Hyperliquid has 100% fill rate typically

            # Fees
            total_fees = sum(
                abs(t.entry_size * t.entry_price * 0.0004) +  # Entry fee 0.04%
                abs(t.entry_size * (t.exit_price or t.entry_price) * 0.0004)  # Exit fee
                for t in trades
            )

            return {
                'total_trades': total_trades,
                'avg_slippage_pct': avg_slippage,
                'fill_rate': fill_rate,
                'total_fees_usd': total_fees,
                'avg_fee_per_trade': total_fees / max(total_trades, 1),
            }

    except Exception as e:
        logger.error(f"Error getting execution quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))
