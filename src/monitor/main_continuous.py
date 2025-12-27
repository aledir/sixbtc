"""
Continuous Monitor Process

Monitors system health and performance:
1. Database connectivity
2. Strategy processing pipeline health
3. Live trading performance
4. Emergency stop conditions
"""

import asyncio
import os
import signal
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.config import load_config
from src.database import get_session, Strategy, Subaccount, Trade, PerformanceSnapshot, StrategyProcessor
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()._raw_config
setup_logging(
    log_file=_config.get('logging', {}).get('file', 'logs/sixbtc.log'),
    log_level=_config.get('logging', {}).get('level', 'INFO'),
)

logger = get_logger(__name__)


class ContinuousMonitorProcess:
    """
    Continuous system monitoring process.

    Tracks health metrics and triggers emergency stops when needed.
    """

    def __init__(self):
        """Initialize the monitor process"""
        self.config = load_config()._raw_config
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration (from monitoring section)
        monitoring_config = self.config.get('monitoring', {})
        self.check_interval_seconds = monitoring_config.get('check_interval_seconds', 30)

        # Emergency thresholds
        risk_config = self.config.get('risk', {}).get('emergency', {})
        self.max_portfolio_drawdown = risk_config.get('max_portfolio_drawdown', 0.30)
        self.max_daily_loss = risk_config.get('max_daily_loss', 0.10)

        # Processor for checking pipeline health
        self.processor = StrategyProcessor(process_id=f"monitor-{os.getpid()}")

        logger.info(
            f"ContinuousMonitorProcess initialized: "
            f"interval={self.check_interval_seconds}s"
        )

    async def run_continuous(self):
        """Main continuous monitoring loop"""
        logger.info("Starting continuous monitoring loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                # Run health checks
                health = await self._run_health_checks()

                # Check for emergency conditions
                await self._check_emergency_conditions()

                # Record health snapshot
                self._record_health_snapshot(health)

            except Exception as e:
                logger.error(f"Monitoring error: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval_seconds)

        logger.info("Monitoring loop ended")

    async def _run_health_checks(self) -> Dict:
        """Run all health checks"""
        health = {
            'timestamp': datetime.utcnow().isoformat(),
            'database': self._check_database(),
            'pipeline': self._check_pipeline(),
            'trading': self._check_trading(),
            'performance': self._get_performance_metrics()
        }

        # Log summary
        status = "HEALTHY" if all([
            health['database']['healthy'],
            health['pipeline']['healthy'],
            health['trading']['healthy']
        ]) else "UNHEALTHY"

        logger.info(
            f"Health check: {status} | "
            f"DB: {health['database']['healthy']} | "
            f"Pipeline: {health['pipeline']['healthy']} | "
            f"Trading: {health['trading']['healthy']}"
        )

        return health

    def _check_database(self) -> Dict:
        """Check database connectivity"""
        try:
            with get_session() as session:
                # Simple query to test connection
                session.execute("SELECT 1")

            return {'healthy': True, 'error': None}

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {'healthy': False, 'error': str(e)}

    def _check_pipeline(self) -> Dict:
        """Check strategy processing pipeline health"""
        try:
            stats = self.processor.get_processing_stats()

            # Check for stalled strategies
            stalled_count = 0
            with get_session() as session:
                cutoff = datetime.utcnow() - timedelta(minutes=30)
                stalled_count = (
                    session.query(Strategy)
                    .filter(
                        Strategy.processing_by.isnot(None),
                        Strategy.processing_started_at < cutoff
                    )
                    .count()
                )

            return {
                'healthy': stalled_count == 0,
                'stats': stats,
                'stalled_count': stalled_count
            }

        except Exception as e:
            logger.error(f"Pipeline health check failed: {e}")
            return {'healthy': False, 'error': str(e)}

    def _check_trading(self) -> Dict:
        """Check trading system health"""
        try:
            with get_session() as session:
                # Count active subaccounts
                active_count = (
                    session.query(Subaccount)
                    .filter(Subaccount.status == "ACTIVE")
                    .count()
                )

                # Count live strategies
                live_count = (
                    session.query(Strategy)
                    .filter(Strategy.status == "LIVE")
                    .count()
                )

                # Count recent trades (last 24h)
                cutoff = datetime.utcnow() - timedelta(hours=24)
                recent_trades = (
                    session.query(Trade)
                    .filter(Trade.entry_time >= cutoff)
                    .count()
                )

            return {
                'healthy': True,
                'active_subaccounts': active_count,
                'live_strategies': live_count,
                'trades_24h': recent_trades
            }

        except Exception as e:
            logger.error(f"Trading health check failed: {e}")
            return {'healthy': False, 'error': str(e)}

    def _get_performance_metrics(self) -> Dict:
        """Get current performance metrics"""
        try:
            with get_session() as session:
                # Get latest portfolio snapshot
                latest = (
                    session.query(PerformanceSnapshot)
                    .filter(PerformanceSnapshot.strategy_id.is_(None))
                    .order_by(PerformanceSnapshot.snapshot_time.desc())
                    .first()
                )

                if latest:
                    return {
                        'total_pnl': latest.total_pnl_usd,
                        'max_drawdown': latest.max_drawdown,
                        'pnl_24h': latest.pnl_24h,
                        'pnl_7d': latest.pnl_7d
                    }

                return {'total_pnl': 0, 'max_drawdown': 0, 'pnl_24h': 0, 'pnl_7d': 0}

        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {}

    async def _check_emergency_conditions(self):
        """Check for conditions requiring emergency stop"""
        try:
            with get_session() as session:
                # Get portfolio drawdown
                latest = (
                    session.query(PerformanceSnapshot)
                    .filter(PerformanceSnapshot.strategy_id.is_(None))
                    .order_by(PerformanceSnapshot.snapshot_time.desc())
                    .first()
                )

                if latest:
                    if latest.max_drawdown and latest.max_drawdown > self.max_portfolio_drawdown:
                        logger.critical(
                            f"EMERGENCY: Portfolio drawdown {latest.max_drawdown:.2%} > "
                            f"{self.max_portfolio_drawdown:.2%}"
                        )
                        await self._trigger_emergency_stop("Portfolio drawdown exceeded")

                    if latest.pnl_24h and latest.pnl_24h < -self.max_daily_loss * latest.total_capital:
                        logger.critical(
                            f"EMERGENCY: Daily loss ${-latest.pnl_24h:.2f} exceeds limit"
                        )
                        await self._trigger_emergency_stop("Daily loss limit exceeded")

        except Exception as e:
            logger.error(f"Emergency check failed: {e}")

    async def _trigger_emergency_stop(self, reason: str):
        """Trigger emergency stop of all trading"""
        logger.critical(f"TRIGGERING EMERGENCY STOP: {reason}")

        with get_session() as session:
            # Stop all subaccounts
            subaccounts = session.query(Subaccount).filter(Subaccount.status == "ACTIVE").all()

            for sa in subaccounts:
                sa.status = "STOPPED"
                logger.warning(f"Stopped subaccount {sa.id}")

            # Mark all live strategies as retired
            strategies = session.query(Strategy).filter(Strategy.status == "LIVE").all()

            for s in strategies:
                s.status = "RETIRED"
                s.retired_at = datetime.utcnow()
                logger.warning(f"Retired strategy {s.name}")

    def _record_health_snapshot(self, health: Dict):
        """Record health snapshot to database"""
        try:
            with get_session() as session:
                perf = health.get('performance', {})

                snapshot = PerformanceSnapshot(
                    strategy_id=None,  # Portfolio level
                    snapshot_time=datetime.utcnow(),
                    total_pnl_usd=perf.get('total_pnl', 0),
                    max_drawdown=perf.get('max_drawdown', 0),
                    pnl_24h=perf.get('pnl_24h', 0),
                    pnl_7d=perf.get('pnl_7d', 0)
                )
                session.add(snapshot)

        except Exception as e:
            logger.debug(f"Failed to record health snapshot: {e}")

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True
        os._exit(0)

    def run(self):
        """Main entry point"""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Monitor process terminated")
