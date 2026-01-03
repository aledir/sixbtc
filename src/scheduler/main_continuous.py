"""
Continuous Scheduler Process

Coordinates scheduled tasks across the system:
1. Data refresh schedules
2. Maintenance tasks
3. Report generation
4. System health summary
"""

import asyncio
import os
import signal
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()
setup_logging(
    log_file='logs/scheduler.log',
    log_level=_config.get_required('logging.level'),
)

logger = get_logger(__name__)


class ContinuousSchedulerProcess:
    """
    Continuous scheduler process.

    Manages periodic tasks that don't fit in other processes.
    """

    def __init__(self):
        """Initialize the scheduler process"""
        self.config = load_config()
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Task tracking
        self.last_run: Dict[str, datetime] = {}

        # Scheduled tasks and their intervals (hours)
        self.tasks = {
            'cleanup_stale_processing': 0.5,  # Every 30 min
            'cleanup_old_failed': 24,  # Daily
            'generate_daily_report': 24,  # Daily
            'refresh_data_cache': 4,  # Every 4 hours
        }

        # Initialize last run times
        for task in self.tasks:
            self.last_run[task] = datetime.min

        logger.info(
            f"ContinuousSchedulerProcess initialized: {len(self.tasks)} tasks"
        )

    async def run_continuous(self):
        """Main continuous scheduler loop"""
        logger.info("Starting continuous scheduler loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                now = datetime.utcnow()

                # Check each task
                for task_name, interval_hours in self.tasks.items():
                    last = self.last_run[task_name]
                    if (now - last).total_seconds() >= interval_hours * 3600:
                        await self._run_task(task_name)
                        self.last_run[task_name] = now

            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)

            # Sleep for a minute before checking again
            await asyncio.sleep(60)

        logger.info("Scheduler loop ended")

    async def _run_task(self, task_name: str):
        """Run a scheduled task"""
        logger.info(f"Running scheduled task: {task_name}")

        try:
            if task_name == 'cleanup_stale_processing':
                await self._cleanup_stale_processing()

            elif task_name == 'cleanup_old_failed':
                await self._cleanup_old_failed()

            elif task_name == 'generate_daily_report':
                await self._generate_daily_report()

            elif task_name == 'refresh_data_cache':
                await self._refresh_data_cache()

            else:
                logger.warning(f"Unknown task: {task_name}")

        except Exception as e:
            logger.error(f"Task {task_name} failed: {e}", exc_info=True)

    async def _cleanup_stale_processing(self):
        """Release strategies stuck in processing"""
        processor = StrategyProcessor(process_id=f"scheduler-{os.getpid()}")

        with get_session() as session:
            cutoff = datetime.utcnow() - timedelta(minutes=30)

            stale = (
                session.query(Strategy)
                .filter(
                    Strategy.processing_by.isnot(None),
                    Strategy.processing_started_at < cutoff
                )
                .all()
            )

            for s in stale:
                logger.warning(f"Releasing stale processing: {s.name}")
                s.processing_by = None
                s.processing_started_at = None

            if stale:
                logger.info(f"Released {len(stale)} stale processing claims")

    async def _cleanup_old_failed(self):
        """Clean up old FAILED strategies"""
        with get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=7)

            old_failed = (
                session.query(Strategy)
                .filter(
                    Strategy.status == "FAILED",
                    Strategy.created_at < cutoff
                )
                .all()
            )

            for s in old_failed:
                session.delete(s)

            if old_failed:
                logger.info(f"Cleaned up {len(old_failed)} old failed strategies")

    async def _generate_daily_report(self):
        """Generate daily performance report"""
        with get_session() as session:
            # Count strategies by status
            status_counts = {}
            for status in ["GENERATED", "VALIDATED", "TESTED", "SELECTED", "LIVE", "RETIRED", "FAILED"]:
                count = session.query(Strategy).filter(Strategy.status == status).count()
                if count > 0:
                    status_counts[status] = count

            # Get live performance summary
            live_strategies = session.query(Strategy).filter(Strategy.status == "LIVE").count()

            logger.info("=== DAILY REPORT ===")
            logger.info(f"Strategy counts: {status_counts}")
            logger.info(f"Live strategies: {live_strategies}")
            logger.info("===================")

    async def _refresh_data_cache(self):
        """Refresh market data cache"""
        try:
            from src.backtester.data_loader import BacktestDataLoader

            cache_dir = self.config.get_required('directories.data') + '/binance'
            loader = BacktestDataLoader(cache_dir=cache_dir)

            # Refresh BTC data for configured timeframes only - NO defaults
            timeframes = self.config.get_required('timeframes')

            for tf in timeframes:
                try:
                    data = loader.load_single_symbol('BTC', tf, days=30)
                    logger.debug(f"Refreshed BTC {tf} data: {len(data)} bars")
                except Exception as e:
                    # Cache not found is expected - data scheduler handles downloads
                    logger.debug(f"BTC {tf} data not in cache: {e}")

            logger.info("Data cache refresh complete")

        except Exception as e:
            logger.error(f"Data refresh failed: {e}")

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
            logger.info("Scheduler process terminated")
