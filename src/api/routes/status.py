"""
Status API routes

GET /api/status - System status overview
"""
import subprocess
from datetime import datetime, timedelta, UTC
from typing import Dict, List

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    Alert,
    PipelineCounts,
    PortfolioSummary,
    ServiceInfo,
    StatusResponse,
)
from src.database import Strategy, Trade, PerformanceSnapshot, get_session
from src.utils import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_supervisor_status() -> List[ServiceInfo]:
    """
    Get status of sixbtc supervisor-managed services.

    Returns list of ServiceInfo objects (only sixbtc:* services).
    """
    services = []

    try:
        result = subprocess.run(
            ["supervisorctl", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue

            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                status_str = parts[1]

                # Only include sixbtc services
                if not name.startswith("sixbtc:"):
                    continue

                # Simplify name (remove sixbtc: prefix)
                display_name = name.replace("sixbtc:", "")

                # Map supervisor status to our status
                if status_str == "RUNNING":
                    status = "RUNNING"
                    # Parse PID and uptime if available
                    pid = None
                    uptime = None
                    if len(parts) >= 4 and "pid" in line:
                        try:
                            pid_str = line.split("pid ")[1].split(",")[0]
                            pid = int(pid_str)
                        except (IndexError, ValueError):
                            pass
                    if "uptime" in line:
                        try:
                            uptime_str = line.split("uptime ")[1].strip()
                            # Parse uptime format: "0:00:30" or "1 day, 2:30:15"
                            uptime = parse_uptime(uptime_str)
                        except (IndexError, ValueError):
                            pass
                elif status_str in ["STOPPED", "EXITED"]:
                    status = "STOPPED"
                    pid = None
                    uptime = None
                else:
                    status = "ERROR"
                    pid = None
                    uptime = None

                services.append(ServiceInfo(
                    name=display_name,
                    status=status,
                    pid=pid,
                    uptime_seconds=uptime,
                ))

    except subprocess.TimeoutExpired:
        logger.error("Supervisor status command timed out")
    except FileNotFoundError:
        logger.warning("supervisorctl not found, returning empty services list")
    except Exception as e:
        logger.error(f"Error getting supervisor status: {e}")

    return services


def parse_uptime(uptime_str: str) -> int:
    """
    Parse supervisor uptime string to seconds.

    Examples:
        "0:00:30" -> 30
        "1:23:45" -> 5025
        "1 day, 2:30:15" -> 95415
    """
    total_seconds = 0

    try:
        # Handle "X day(s), H:M:S" format
        if "day" in uptime_str:
            day_part, time_part = uptime_str.split(", ")
            days = int(day_part.split()[0])
            total_seconds += days * 86400
            uptime_str = time_part

        # Handle "H:M:S" format
        parts = uptime_str.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            total_seconds += hours * 3600 + minutes * 60 + seconds
    except (ValueError, IndexError):
        pass

    return total_seconds


def get_pipeline_counts() -> Dict[str, int]:
    """
    Get strategy counts by status.

    Returns dict with status -> count.
    """
    counts = {
        "GENERATED": 0,
        "VALIDATED": 0,
        "ACTIVE": 0,
        "LIVE": 0,
        "RETIRED": 0,
        "FAILED": 0,
    }

    try:
        with get_session() as session:
            for status in counts.keys():
                count = session.query(Strategy).filter(Strategy.status == status).count()
                counts[status] = count
    except Exception as e:
        logger.error(f"Error getting pipeline counts: {e}")

    return counts


def get_portfolio_summary() -> PortfolioSummary:
    """
    Get portfolio performance summary.

    Returns PortfolioSummary with PnL metrics.
    """
    try:
        with get_session() as session:
            now = datetime.now(UTC)
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            # Total PnL from all closed trades
            total_pnl = session.query(Trade).with_entities(
                Trade.pnl_usd
            ).filter(
                Trade.exit_time.isnot(None)
            ).all()
            total_pnl_sum = sum(t.pnl_usd or 0 for t in total_pnl)

            # PnL last 24h
            pnl_24h = session.query(Trade).with_entities(
                Trade.pnl_usd
            ).filter(
                Trade.exit_time >= day_ago
            ).all()
            pnl_24h_sum = sum(t.pnl_usd or 0 for t in pnl_24h)

            # PnL last 7d
            pnl_7d = session.query(Trade).with_entities(
                Trade.pnl_usd
            ).filter(
                Trade.exit_time >= week_ago
            ).all()
            pnl_7d_sum = sum(t.pnl_usd or 0 for t in pnl_7d)

            # Open positions count
            open_positions = session.query(Trade).filter(
                Trade.exit_time.is_(None)
            ).count()

            # Trades today
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            trades_today = session.query(Trade).filter(
                Trade.entry_time >= today_start
            ).count()

            # Calculate percentages (assume initial capital from latest snapshot)
            latest_snapshot = session.query(PerformanceSnapshot).filter(
                PerformanceSnapshot.strategy_id.is_(None)  # Portfolio-level
            ).order_by(PerformanceSnapshot.snapshot_time.desc()).first()

            initial_capital = 10000.0  # Default
            if latest_snapshot and latest_snapshot.total_capital:
                # Calculate initial from current minus PnL
                initial_capital = latest_snapshot.total_capital - total_pnl_sum

            total_pnl_pct = (total_pnl_sum / initial_capital * 100) if initial_capital > 0 else 0
            pnl_24h_pct = (pnl_24h_sum / initial_capital * 100) if initial_capital > 0 else 0
            pnl_7d_pct = (pnl_7d_sum / initial_capital * 100) if initial_capital > 0 else 0

            return PortfolioSummary(
                total_pnl=total_pnl_sum,
                total_pnl_pct=total_pnl_pct,
                pnl_24h=pnl_24h_sum,
                pnl_24h_pct=pnl_24h_pct,
                pnl_7d=pnl_7d_sum,
                pnl_7d_pct=pnl_7d_pct,
                max_drawdown=0.0,  # TODO: Calculate from snapshots
                open_positions=open_positions,
                trades_today=trades_today,
            )

    except Exception as e:
        logger.error(f"Error getting portfolio summary: {e}")
        return PortfolioSummary()


def get_system_alerts() -> List[Alert]:
    """
    Get system alerts and warnings.

    Checks for:
    - Stalled pipeline (too many strategies in queue)
    - High drawdown
    - Service errors
    """
    alerts = []

    try:
        with get_session() as session:
            # Check for pipeline bottleneck
            generated_count = session.query(Strategy).filter(
                Strategy.status == "GENERATED"
            ).count()

            if generated_count > 100:
                alerts.append(Alert(
                    level="warning",
                    message=f"Pipeline bottleneck: {generated_count} strategies waiting for validation",
                    timestamp=datetime.now(UTC),
                ))


    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        alerts.append(Alert(
            level="error",
            message=f"Error checking system status: {str(e)}",
            timestamp=datetime.now(UTC),
        ))

    return alerts


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get full system status.

    Returns pipeline counts, service states, portfolio summary, and alerts.
    """
    from src.api.main import get_uptime_seconds

    try:
        return StatusResponse(
            uptime_seconds=get_uptime_seconds(),
            pipeline=get_pipeline_counts(),
            services=get_supervisor_status(),
            portfolio=get_portfolio_summary(),
            alerts=get_system_alerts(),
        )
    except Exception as e:
        logger.error(f"Error in /status endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
