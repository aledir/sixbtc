"""
Strategies API routes

GET /api/strategies - List strategies with filters
GET /api/strategies/{id} - Strategy detail
GET /api/strategies/{id}/backtest - Backtest results
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from src.api.schemas import (
    BacktestMetrics,
    DegradationPoint,
    DegradationResponse,
    RankedStrategy,
    RankingResponse,
    StrategiesResponse,
    StrategyDetail,
    StrategyListItem,
)
from src.database import Strategy, BacktestResult, Trade, get_session
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/strategies", response_model=StrategiesResponse)
async def list_strategies(
    status: Optional[str] = Query(None, description="Filter by status"),
    strategy_type: Optional[str] = Query(None, alias="type", description="Filter by type (MOM, REV, TRN, etc.)"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    limit: int = Query(50, ge=1, le=500, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List strategies with optional filters.

    Supports filtering by status, type, timeframe.
    Returns paginated results.
    """
    try:
        with get_session() as session:
            query = session.query(Strategy)

            # Apply filters
            if status:
                query = query.filter(Strategy.status == status.upper())
            if strategy_type:
                query = query.filter(Strategy.strategy_type == strategy_type.upper())
            if timeframe:
                query = query.filter(Strategy.timeframe == timeframe)

            # Get total count before pagination
            total = query.count()

            # Order by created_at descending (newest first)
            query = query.order_by(desc(Strategy.created_at))

            # Apply pagination
            strategies = query.offset(offset).limit(limit).all()

            # Convert to response format
            items = []
            for s in strategies:
                # Get best backtest result for sharpe/win_rate
                best_backtest = session.query(BacktestResult).filter(
                    BacktestResult.strategy_id == s.id,
                    BacktestResult.period_type == 'full',
                ).order_by(desc(BacktestResult.sharpe_ratio)).first()

                sharpe = best_backtest.sharpe_ratio if best_backtest else None
                win_rate = best_backtest.win_rate if best_backtest else None
                total_trades = best_backtest.total_trades if best_backtest else None

                items.append(StrategyListItem(
                    id=s.id,
                    name=s.name,
                    strategy_type=s.strategy_type,
                    timeframe=s.timeframe,
                    status=s.status,
                    sharpe_ratio=sharpe,
                    win_rate=win_rate,
                    total_trades=total_trades,
                    total_pnl=s.total_pnl_live,
                    created_at=s.created_at,
                ))

            return StrategiesResponse(
                items=items,
                total=total,
                limit=limit,
                offset=offset,
            )

    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/rankings/backtest", response_model=RankingResponse)
async def get_backtest_ranking(
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """
    Get backtest ranking for ACTIVE strategies.

    Returns strategies ordered by backtest score (combination of Edge,
    Sharpe, Consistency, and Drawdown penalty).
    """
    try:
        with get_session() as session:
            # Query ACTIVE strategies ordered by score_backtest
            strategies = (
                session.query(Strategy)
                .filter(
                    Strategy.status == 'ACTIVE',
                    Strategy.score_backtest.isnot(None),
                )
                .order_by(desc(Strategy.score_backtest))
                .limit(limit)
                .all()
            )

            # Build ranking list
            ranking = []
            for s in strategies:
                # Get backtest result for additional metrics
                backtest = session.query(BacktestResult).filter(
                    BacktestResult.strategy_id == s.id,
                    BacktestResult.period_type == 'full',
                ).first()

                ranking.append({
                    'id': str(s.id),
                    'name': s.name,
                    'strategy_type': s.strategy_type,
                    'timeframe': s.timeframe,
                    'score': s.score_backtest,
                    'sharpe': backtest.sharpe_ratio if backtest else None,
                    'win_rate': backtest.win_rate if backtest else None,
                    'expectancy': backtest.expectancy if backtest else None,
                    'max_drawdown': backtest.max_drawdown if backtest else None,
                    'total_trades': backtest.total_trades if backtest else None,
                })

            # Calculate averages
            avg_score = sum(s['score'] or 0 for s in ranking) / max(len(ranking), 1)
            avg_sharpe = sum(s['sharpe'] or 0 for s in ranking) / max(len(ranking), 1)

            return RankingResponse(
                ranking_type="backtest",
                count=len(ranking),
                strategies=ranking,
                avg_score=avg_score,
                avg_sharpe=avg_sharpe,
            )

    except Exception as e:
        logger.error(f"Error getting backtest ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/rankings/live", response_model=RankingResponse)
async def get_live_ranking(
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
):
    """
    Get live ranking for LIVE strategies.

    Returns strategies ordered by live score (based on actual trading performance).
    Only includes strategies with minimum number of trades.
    """
    try:
        with get_session() as session:
            # Query LIVE strategies ordered by score_live
            strategies = (
                session.query(Strategy)
                .filter(
                    Strategy.status == 'LIVE',
                    Strategy.score_live.isnot(None),
                )
                .order_by(desc(Strategy.score_live))
                .limit(limit)
                .all()
            )

            # Build ranking list
            ranking = []
            for s in strategies:
                ranking.append({
                    'id': str(s.id),
                    'name': s.name,
                    'strategy_type': s.strategy_type,
                    'timeframe': s.timeframe,
                    'score': s.score_live,
                    'sharpe': s.sharpe_live,
                    'win_rate': s.win_rate_live,
                    'total_pnl': s.total_pnl_live,
                    'total_trades': s.total_trades_live,
                    'live_since': s.live_since.isoformat() if s.live_since else None,
                })

            # Calculate averages
            avg_score = sum(s['score'] or 0 for s in ranking) / max(len(ranking), 1)
            avg_sharpe = sum(s['sharpe'] or 0 for s in ranking) / max(len(ranking), 1)
            avg_pnl = sum(s['total_pnl'] or 0 for s in ranking) / max(len(ranking), 1)

            return RankingResponse(
                ranking_type="live",
                count=len(ranking),
                strategies=ranking,
                avg_score=avg_score,
                avg_sharpe=avg_sharpe,
                avg_pnl=avg_pnl,
            )

    except Exception as e:
        logger.error(f"Error getting live ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/degradation", response_model=DegradationResponse)
async def get_degradation_analysis(
    threshold: float = Query(0.3, ge=0, le=1, description="Degradation threshold (default 30%)"),
):
    """
    Get degradation analysis for LIVE strategies.

    Returns:
    - Scatter plot data (backtest_score vs live_score)
    - Worst degraders (degradation > threshold)
    - Strategies that should potentially be retired
    """
    try:
        with get_session() as session:
            # Get all LIVE strategies with both backtest and live scores
            live_strategies = (
                session.query(Strategy)
                .filter(
                    Strategy.status == 'LIVE',
                    Strategy.score_backtest.isnot(None),
                    Strategy.score_live.isnot(None),
                )
                .all()
            )

            # Build data points
            all_points = []
            degrading = []
            total_degradation = 0.0

            for s in live_strategies:
                # Calculate degradation if not already calculated
                degradation = s.live_degradation_pct
                if degradation is None and s.score_backtest and s.score_live:
                    degradation = (s.score_backtest - s.score_live) / s.score_backtest

                point = DegradationPoint(
                    id=s.id,
                    name=s.name,
                    strategy_type=s.strategy_type,
                    timeframe=s.timeframe,
                    score_backtest=s.score_backtest,
                    score_live=s.score_live,
                    degradation_pct=degradation,
                    total_pnl=s.total_pnl_live,
                    total_trades_live=s.total_trades_live,
                    live_since=s.live_since,
                )

                all_points.append(point)

                if degradation is not None:
                    total_degradation += degradation
                    if degradation > threshold:
                        degrading.append(point)

            # Calculate average
            avg_degradation = total_degradation / max(len(live_strategies), 1)

            # Sort worst degraders by degradation (descending)
            worst = sorted(
                [p for p in all_points if p.degradation_pct is not None],
                key=lambda p: p.degradation_pct or 0,
                reverse=True,
            )[:10]  # Top 10 worst

            return DegradationResponse(
                total_live_strategies=len(live_strategies),
                degrading_count=len(degrading),
                avg_degradation=avg_degradation,
                worst_degraders=worst,
                all_points=all_points,
            )

    except Exception as e:
        logger.error(f"Error getting degradation analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(strategy_id: UUID):
    """
    Get full strategy detail including code and backtest.
    """
    try:
        with get_session() as session:
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")

            # Get best backtest result
            backtest = session.query(BacktestResult).filter(
                BacktestResult.strategy_id == strategy_id,
                BacktestResult.period_type == 'full',
            ).order_by(desc(BacktestResult.sharpe_ratio)).first()

            backtest_metrics = None
            if backtest:
                backtest_metrics = BacktestMetrics(
                    sharpe_ratio=backtest.sharpe_ratio,
                    win_rate=backtest.win_rate,
                    expectancy=backtest.expectancy,
                    max_drawdown=backtest.max_drawdown,
                    total_trades=backtest.total_trades,
                    total_return=backtest.total_return_pct,
                    ed_ratio=None,  # TODO: Calculate if available
                    consistency=None,  # TODO: Calculate if available
                    period_type=backtest.period_type,
                    period_days=backtest.period_days,
                )

            return StrategyDetail(
                id=strategy.id,
                name=strategy.name,
                strategy_type=strategy.strategy_type,
                timeframe=strategy.timeframe,
                status=strategy.status,
                code=strategy.code,
                pattern_ids=strategy.pattern_ids,
                trading_coins=strategy.trading_coins,
                created_at=strategy.created_at,
                updated_at=strategy.tested_at,
                backtest=backtest_metrics,
                live_pnl=strategy.total_pnl_live,
                live_trades=strategy.total_trades_live,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/{strategy_id}/backtest")
async def get_strategy_backtest(strategy_id: UUID):
    """
    Get detailed backtest results for a strategy.

    Returns full and recent period results with per-symbol breakdown.
    """
    try:
        with get_session() as session:
            # Check strategy exists
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")

            # Get all backtest results
            results = session.query(BacktestResult).filter(
                BacktestResult.strategy_id == strategy_id
            ).order_by(desc(BacktestResult.created_at)).all()

            if not results:
                return {"results": [], "strategy_name": strategy.name}

            # Format results
            formatted = []
            for r in results:
                formatted.append({
                    "id": str(r.id),
                    "period_type": r.period_type,
                    "period_days": r.period_days,
                    "lookback_days": r.lookback_days,
                    "start_date": r.start_date.isoformat() if r.start_date else None,
                    "end_date": r.end_date.isoformat() if r.end_date else None,
                    "sharpe_ratio": r.sharpe_ratio,
                    "win_rate": r.win_rate,
                    "expectancy": r.expectancy,
                    "max_drawdown": r.max_drawdown,
                    "total_trades": r.total_trades,
                    "total_return_pct": r.total_return_pct,
                    "final_equity": r.final_equity,
                    "walk_forward_stability": r.walk_forward_stability,
                    "lookahead_check_passed": r.lookahead_check_passed,
                    "shuffle_test_passed": r.shuffle_test_passed,
                    "per_symbol_results": r.per_symbol_results,
                    "symbols_tested": r.symbols_tested,
                    "timeframe_tested": r.timeframe_tested,
                    "weighted_sharpe": r.weighted_sharpe,
                    "weighted_win_rate": r.weighted_win_rate,
                    "recency_ratio": r.recency_ratio,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                })

            return {
                "strategy_name": strategy.name,
                "results": formatted,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backtest for {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/{strategy_id}/trades")
async def get_strategy_trades(
    strategy_id: UUID,
    status: Optional[str] = Query(None, description="Filter by status (open/closed)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get trades for a specific strategy.
    """
    try:
        with get_session() as session:
            # Check strategy exists
            strategy = session.query(Strategy).filter(
                Strategy.id == strategy_id
            ).first()

            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")

            query = session.query(Trade).filter(Trade.strategy_id == strategy_id)

            # Filter by open/closed
            if status == "open":
                query = query.filter(Trade.exit_time.is_(None))
            elif status == "closed":
                query = query.filter(Trade.exit_time.isnot(None))

            total = query.count()
            trades = query.order_by(desc(Trade.entry_time)).offset(offset).limit(limit).all()

            items = []
            for t in trades:
                items.append({
                    "id": str(t.id),
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                    "entry_price": t.entry_price,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "exit_price": t.exit_price,
                    "size": t.entry_size,
                    "pnl_usd": t.pnl_usd,
                    "pnl_pct": t.pnl_pct,
                    "subaccount_id": t.subaccount_id,
                    "exit_reason": t.exit_reason,
                })

            return {
                "strategy_name": strategy.name,
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trades for strategy {strategy_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
