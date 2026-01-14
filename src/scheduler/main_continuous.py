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
import shutil
import signal
import subprocess
import threading
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Dict, List

from src.config import load_config
from src.database import get_session, Strategy, StrategyEvent, StrategyProcessor
from src.scheduler.task_tracker import track_task_execution
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
        # Core tasks (always enabled)
        self.tasks = {
            'cleanup_stale_processing': 0.5,  # Every 30 min
            'generate_daily_report': 24,  # Daily
            'refresh_data_cache': 4,  # Every 4 hours
        }

        # Configurable tasks (check enabled flag)
        scheduler_config = self.config._raw_config.get('scheduler', {}).get('tasks', {})

        restart_config = scheduler_config.get('daily_restart_services', {})
        if restart_config.get('enabled', False):
            self.tasks['daily_restart_services'] = restart_config['interval_hours']
            self.restart_hour = restart_config['restart_hour']
            self.restart_minute = restart_config.get('restart_minute', 0)

        # Agent wallet renewal (renew expiring credentials)
        renew_config = scheduler_config.get('renew_agent_wallets', {})
        if renew_config.get('enabled', False):
            self.tasks['renew_agent_wallets'] = renew_config['interval_hours']
            self.renew_agent_hour = renew_config.get('run_hour', 3)
            self.renew_agent_minute = renew_config.get('run_minute', 0)

        # Subaccount fund check (topup from master if low)
        funds_config = scheduler_config.get('check_subaccount_funds', {})
        if funds_config.get('enabled', False):
            self.tasks['check_subaccount_funds'] = funds_config['interval_hours']
            self.check_funds_hour = funds_config.get('run_hour', 4)
            self.check_funds_minute = funds_config.get('run_minute', 0)

        # Cleanup /tmp directory
        tmp_config = scheduler_config.get('cleanup_tmp_dir', {})
        if tmp_config.get('enabled', False):
            self.tasks['cleanup_tmp_dir'] = tmp_config['interval_hours']
            self.cleanup_tmp_hour = tmp_config.get('run_hour', 5)
            self.cleanup_tmp_minute = tmp_config.get('run_minute', 0)
            self.cleanup_tmp_max_age = tmp_config.get('max_age_hours', 24)

        # Cleanup old StrategyEvent records
        events_config = scheduler_config.get('cleanup_old_events', {})
        if events_config.get('enabled', False):
            self.tasks['cleanup_old_events'] = events_config['interval_hours']
            self.cleanup_events_hour = events_config.get('run_hour', 6)
            self.cleanup_events_minute = events_config.get('run_minute', 0)
            self.cleanup_events_max_age_days = events_config.get('max_age_days', 7)

        # Cleanup stale strategies (stuck in GENERATED/VALIDATED)
        stale_config = scheduler_config.get('cleanup_stale_strategies', {})
        if stale_config.get('enabled', False):
            self.tasks['cleanup_stale_strategies'] = stale_config['interval_hours']
            self.cleanup_stale_hour = stale_config.get('run_hour', 6)
            self.cleanup_stale_minute = stale_config.get('run_minute', 0)
            self.cleanup_stale_max_age_days = stale_config.get('max_age_days', 1)

        # Cleanup old FAILED strategies
        failed_config = scheduler_config.get('cleanup_old_failed', {})
        if failed_config.get('enabled', False):
            self.tasks['cleanup_old_failed'] = failed_config['interval_hours']
            self.cleanup_failed_hour = failed_config.get('run_hour', 2)
            self.cleanup_failed_minute = failed_config.get('run_minute', 0)
            self.cleanup_failed_max_age_days = failed_config.get('max_age_days', 7)

        # Cleanup old RETIRED strategies
        retired_config = scheduler_config.get('cleanup_old_retired', {})
        if retired_config.get('enabled', False):
            self.tasks['cleanup_old_retired'] = retired_config['interval_hours']
            self.cleanup_retired_hour = retired_config.get('run_hour', 2)
            self.cleanup_retired_minute = retired_config.get('run_minute', 10)
            self.cleanup_retired_max_age_days = retired_config.get('max_age_days', 7)

        # Market regime detection (Unger method)
        # Runs 2x daily AFTER download_data (02:30 and 14:30 UTC)
        regime_config = self.config._raw_config.get('regime', {})
        if regime_config.get('enabled', False):
            self.tasks['refresh_market_regimes'] = 12  # Every 12 hours
            self.regime_run_hours = [2, 14]  # Run at 02:30 and 14:30 UTC
            self.regime_run_minute = 30

        # Data scheduler (pairs update + OHLCV download)
        data_sched_config = self.config._raw_config.get('data_scheduler', {})
        if data_sched_config.get('enabled', False):
            # update_pairs: runs at update_pairs_hours:update_pairs_minute (e.g., 01:45 and 13:45)
            self.update_pairs_hours = data_sched_config.get('update_pairs_hours', [1, 13])
            self.update_pairs_minute = data_sched_config.get('update_pairs_minute', 45)
            # download_data: runs at download_data_hours:download_data_minute (e.g., 02:00 and 14:00)
            self.download_data_hours = data_sched_config.get('download_data_hours', [2, 14])
            self.download_data_minute = data_sched_config.get('download_data_minute', 0)
            # Check every hour to see if it's time to run
            self.tasks['update_pairs'] = 1  # Check every hour
            self.tasks['download_data'] = 1  # Check every hour

        # Initialize last run times (use timezone-aware datetime)
        for task in self.tasks:
            self.last_run[task] = datetime.min.replace(tzinfo=UTC)

        # Tasks with fixed schedules (hour:minute)
        # These only run at specific times, not on interval
        self.fixed_schedule_tasks = {
            'daily_restart_services': (self.restart_hour, getattr(self, 'restart_minute', 0)) if hasattr(self, 'restart_hour') else None,
            'renew_agent_wallets': (getattr(self, 'renew_agent_hour', 3), getattr(self, 'renew_agent_minute', 0)) if 'renew_agent_wallets' in self.tasks else None,
            'check_subaccount_funds': (getattr(self, 'check_funds_hour', 4), getattr(self, 'check_funds_minute', 0)) if 'check_subaccount_funds' in self.tasks else None,
            'cleanup_tmp_dir': (getattr(self, 'cleanup_tmp_hour', 5), getattr(self, 'cleanup_tmp_minute', 0)) if 'cleanup_tmp_dir' in self.tasks else None,
            'cleanup_old_events': (getattr(self, 'cleanup_events_hour', 6), getattr(self, 'cleanup_events_minute', 0)) if 'cleanup_old_events' in self.tasks else None,
            'cleanup_stale_strategies': (getattr(self, 'cleanup_stale_hour', 6), getattr(self, 'cleanup_stale_minute', 0)) if 'cleanup_stale_strategies' in self.tasks else None,
            'cleanup_old_failed': (getattr(self, 'cleanup_failed_hour', 2), getattr(self, 'cleanup_failed_minute', 0)) if 'cleanup_old_failed' in self.tasks else None,
            'cleanup_old_retired': (getattr(self, 'cleanup_retired_hour', 2), getattr(self, 'cleanup_retired_minute', 10)) if 'cleanup_old_retired' in self.tasks else None,
            # Note: refresh_market_regimes uses multi-hour scheduling like download_data
        }
        # Remove None entries
        self.fixed_schedule_tasks = {k: v for k, v in self.fixed_schedule_tasks.items() if v is not None}

        logger.info(
            f"ContinuousSchedulerProcess initialized: {len(self.tasks)} tasks, "
            f"{len(self.fixed_schedule_tasks)} with fixed schedules"
        )

    async def run_continuous(self):
        """Main continuous scheduler loop"""
        logger.info("Starting continuous scheduler loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                now = datetime.now(UTC)

                # Check each task
                for task_name, interval_hours in self.tasks.items():
                    should_run, reason = self._should_run_task(task_name, now)

                    if should_run:
                        result = await self._run_task(task_name)
                        # Always update last_run after actual execution
                        self.last_run[task_name] = now

            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)

            # Sleep for a minute before checking again
            await asyncio.sleep(60)

        logger.info("Scheduler loop ended")

    def _should_run_task(self, task_name: str, now: datetime) -> tuple[bool, str]:
        """
        Determine if a task should run now.

        For fixed-schedule tasks: check if it's the right hour:minute AND not already run today
        For interval tasks: check if enough time has passed since last run

        Returns:
            (should_run, reason) tuple
        """
        last = self.last_run[task_name]

        # Check if this is a fixed-schedule task
        if task_name in self.fixed_schedule_tasks:
            target_hour, target_minute = self.fixed_schedule_tasks[task_name]

            # Check if we're in the right time window (5-minute window)
            in_window = (
                now.hour == target_hour and
                target_minute <= now.minute < target_minute + 5
            )

            if not in_window:
                return False, 'wrong_time'

            # Check if already run today (compare dates)
            if last.date() == now.date():
                return False, 'already_run_today'

            return True, 'scheduled_time'

        # Special handling for data scheduler tasks (update_pairs, download_data)
        # Each has its own hours and minute configuration
        if task_name == 'update_pairs':
            target_hours = getattr(self, 'update_pairs_hours', [1, 13])
            target_minute = getattr(self, 'update_pairs_minute', 45)

            # Check if current hour is in target hours
            if now.hour not in target_hours:
                return False, 'wrong_hour'

            # Check if we're in the right minute window (5-minute window)
            if not (target_minute <= now.minute < target_minute + 5):
                return False, 'wrong_minute'

            # Check if already run in this hour today
            if last.hour == now.hour and last.date() == now.date():
                return False, 'already_run_this_hour'

            return True, 'data_update_time'

        if task_name == 'download_data':
            target_hours = getattr(self, 'download_data_hours', [2, 14])
            target_minute = getattr(self, 'download_data_minute', 0)

            # Check if current hour is in target hours
            if now.hour not in target_hours:
                return False, 'wrong_hour'

            # Check if we're in the right minute window (5-minute window)
            if not (target_minute <= now.minute < target_minute + 5):
                return False, 'wrong_minute'

            # Check if already run in this hour today
            if last.hour == now.hour and last.date() == now.date():
                return False, 'already_run_this_hour'

            return True, 'data_update_time'

        # Regime detection runs 2x daily AFTER download_data (02:30 and 14:30 UTC)
        if task_name == 'refresh_market_regimes':
            target_hours = getattr(self, 'regime_run_hours', [2, 14])
            target_minute = getattr(self, 'regime_run_minute', 30)

            # Check if current hour is in target hours
            if now.hour not in target_hours:
                return False, 'wrong_hour'

            # Check if we're in the right minute window (5-minute window)
            if not (target_minute <= now.minute < target_minute + 5):
                return False, 'wrong_minute'

            # Check if already run in this hour today
            if last.hour == now.hour and last.date() == now.date():
                return False, 'already_run_this_hour'

            return True, 'regime_update_time'

        # Regular interval-based task
        interval_hours = self.tasks.get(task_name, 24)
        elapsed_seconds = (now - last).total_seconds()

        if elapsed_seconds >= interval_hours * 3600:
            return True, 'interval_elapsed'

        return False, 'interval_not_elapsed'

    async def _run_task(self, task_name: str) -> dict:
        """Run a scheduled task with tracking. Returns task result dict."""
        result = {}

        with track_task_execution(task_name, task_type='scheduler') as tracker:
            if task_name == 'cleanup_stale_processing':
                result = await self._cleanup_stale_processing()
                tracker.add_metadata('released_count', result.get('released', 0))

            elif task_name == 'cleanup_old_failed':
                result = await self._cleanup_old_failed()
                tracker.add_metadata('deleted_count', result.get('deleted', 0))

            elif task_name == 'cleanup_old_retired':
                result = await self._cleanup_old_retired()
                tracker.add_metadata('deleted_count', result.get('deleted', 0))

            elif task_name == 'generate_daily_report':
                result = await self._generate_daily_report()
                tracker.add_metadata('strategy_counts', result.get('counts', {}))
                tracker.add_metadata('live_strategies', result.get('live_strategies', 0))

            elif task_name == 'refresh_data_cache':
                result = await self._refresh_data_cache()
                tracker.add_metadata('refreshed_timeframes', result.get('timeframes', []))

            elif task_name == 'daily_restart_services':
                result = await self._daily_restart_services()
                tracker.add_metadata('restarted', result.get('restarted', False))

            elif task_name == 'renew_agent_wallets':
                result = await self._renew_agent_wallets()
                tracker.add_metadata('renewed', result.get('renewed', 0))
                tracker.add_metadata('failed', result.get('failed', 0))

            elif task_name == 'check_subaccount_funds':
                result = await self._check_subaccount_funds()
                tracker.add_metadata('checked', result.get('checked', 0))
                tracker.add_metadata('topped_up', result.get('topped_up', 0))

            elif task_name == 'cleanup_tmp_dir':
                result = await self._cleanup_tmp_dir()
                tracker.add_metadata('deleted_files', result.get('deleted_files', 0))
                tracker.add_metadata('deleted_bytes', result.get('deleted_bytes', 0))

            elif task_name == 'refresh_market_regimes':
                result = await self._refresh_market_regimes()
                tracker.add_metadata('trend', result.get('trend', 0))
                tracker.add_metadata('reversal', result.get('reversal', 0))
                tracker.add_metadata('mixed', result.get('mixed', 0))

            elif task_name == 'cleanup_old_events':
                result = await self._cleanup_old_events()
                tracker.add_metadata('deleted_count', result.get('deleted', 0))

            elif task_name == 'cleanup_stale_strategies':
                result = await self._cleanup_stale_strategies()
                tracker.add_metadata('deleted_count', result.get('deleted', 0))

            elif task_name == 'update_pairs':
                result = await self._update_pairs()
                tracker.add_metadata('updated', result.get('updated', 0))
                tracker.add_metadata('new_pairs', result.get('new_pairs', 0))

            elif task_name == 'download_data':
                result = await self._download_data()
                tracker.add_metadata('downloaded', result.get('downloaded', 0))
                tracker.add_metadata('symbols', result.get('symbols', 0))

            else:
                logger.warning(f"Unknown task: {task_name}")
                result = {'reason': 'unknown_task'}

        return result

    async def _cleanup_stale_processing(self) -> dict:
        """Release strategies stuck in processing"""
        processor = StrategyProcessor(process_id=f"scheduler-{os.getpid()}")

        with get_session() as session:
            cutoff = datetime.now(UTC) - timedelta(minutes=30)

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

            return {'released': len(stale)}

    async def _cleanup_old_failed(self) -> dict:
        """
        Clean up old FAILED strategies.

        Deletes FAILED strategies older than max_age_days (configurable, default 7).
        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        max_age_days = getattr(self, 'cleanup_failed_max_age_days', 7)
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

        with get_session() as session:
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
                logger.info(
                    f"Cleaned up {len(old_failed)} old FAILED strategies "
                    f"(older than {max_age_days} days)"
                )
            else:
                logger.debug("No old FAILED strategies to clean")

            return {'deleted': len(old_failed)}

    async def _cleanup_old_retired(self) -> dict:
        """
        Clean up old RETIRED strategies.

        Deletes RETIRED strategies older than max_age_days (configurable, default 7).
        RETIRED strategies are those evicted from the pool - safe to delete after retention.
        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        max_age_days = getattr(self, 'cleanup_retired_max_age_days', 7)
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

        with get_session() as session:
            old_retired = (
                session.query(Strategy)
                .filter(
                    Strategy.status == "RETIRED",
                    Strategy.retired_at < cutoff
                )
                .all()
            )

            for s in old_retired:
                session.delete(s)

            if old_retired:
                logger.info(
                    f"Cleaned up {len(old_retired)} old RETIRED strategies "
                    f"(older than {max_age_days} days)"
                )
            else:
                logger.debug("No old RETIRED strategies to clean")

            return {'deleted': len(old_retired)}

    async def _generate_daily_report(self) -> dict:
        """Generate daily performance report"""
        with get_session() as session:
            # Count strategies by status
            status_counts = {}
            for status in ["GENERATED", "VALIDATED", "ACTIVE", "LIVE", "RETIRED", "FAILED"]:
                count = session.query(Strategy).filter(Strategy.status == status).count()
                if count > 0:
                    status_counts[status] = count

            # Get live performance summary
            live_strategies = session.query(Strategy).filter(Strategy.status == "LIVE").count()

            logger.info("=== DAILY REPORT ===")
            logger.info(f"Strategy counts: {status_counts}")
            logger.info(f"Live strategies: {live_strategies}")
            logger.info("===================")

            return {
                'counts': status_counts,
                'live_strategies': live_strategies
            }

    async def _refresh_data_cache(self) -> dict:
        """Refresh market data cache"""
        refreshed_timeframes = []

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
                    refreshed_timeframes.append(tf)
                except Exception as e:
                    # Cache not found is expected - data scheduler handles downloads
                    logger.debug(f"BTC {tf} data not in cache: {e}")

            logger.info("Data cache refresh complete")

        except Exception as e:
            logger.error(f"Data refresh failed: {e}")

        return {'timeframes': refreshed_timeframes}

    async def _daily_restart_services(self) -> dict:
        """
        Restart all sixbtc services once per day.

        Runs at the configured restart_hour:restart_minute (checked by _should_run_task).
        Skips restarting the scheduler itself (would interrupt this task).
        """
        try:
            logger.info("Starting daily services restart...")

            # Get list of sixbtc services (excluding scheduler)
            result = subprocess.run(
                ['supervisorctl', 'status'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error("Failed to get supervisor status")
                return {'restarted': False, 'reason': 'supervisor_error'}

            # Parse services to restart
            services_to_restart = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('sixbtc:') and 'RUNNING' in line:
                    service = line.split()[0]
                    # Skip scheduler (would kill this process)
                    if 'scheduler' not in service:
                        services_to_restart.append(service)

            if not services_to_restart:
                logger.info("No services to restart")
                return {'restarted': False, 'reason': 'no_services'}

            # Restart services one by one
            restarted = []
            for service in services_to_restart:
                result = subprocess.run(
                    ['supervisorctl', 'restart', service],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    restarted.append(service)
                    logger.info(f"Restarted {service}")
                else:
                    logger.warning(f"Failed to restart {service}: {result.stderr}")

                # Small delay between restarts
                await asyncio.sleep(2)

            logger.info(f"Daily restart complete: {len(restarted)} services restarted")
            return {'restarted': True, 'services': restarted, 'count': len(restarted)}

        except Exception as e:
            logger.error(f"Daily restart failed: {e}")
            return {'restarted': False, 'reason': str(e)}

    async def _renew_agent_wallets(self) -> dict:
        """
        Renew expiring agent wallet credentials.

        Checks for credentials expiring within the renewal window (default 30 days)
        and creates new agent wallets to replace them.

        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        try:
            from src.credentials.agent_manager import AgentManager

            manager = AgentManager(self.config._raw_config)
            result = manager.renew_all_expiring()

            if result['renewed'] > 0:
                logger.info(
                    f"Agent wallet renewal complete: renewed={result['renewed']}, "
                    f"failed={result['failed']}"
                )

                # Notify executor to reload credentials
                # (it will pick up new credentials on next cycle)
                if result['renewed'] > 0:
                    logger.info("Executor should call client.reload_credentials() to use new wallets")

            return result

        except ImportError as e:
            logger.error(f"AgentManager not available: {e}")
            return {'renewed': 0, 'failed': 0, 'reason': 'import_error'}
        except Exception as e:
            logger.error(f"Agent wallet renewal failed: {e}")
            return {'renewed': 0, 'failed': 0, 'reason': str(e)}

    async def _check_subaccount_funds(self) -> dict:
        """
        Check subaccount balances and execute topup from master if needed.

        Policy:
        - Topup only from master, NEVER between subaccounts
        - Respect master reserve (never drain below threshold)
        - Alert on low/insufficient funds

        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        try:
            from src.funds.manager import FundManager

            manager = FundManager(self.config._raw_config)
            result = manager.check_all_subaccounts()

            logger.info(
                f"Fund check complete: checked={result['checked']}, "
                f"healthy={result['healthy']}, topped_up={result['topped_up']}, "
                f"partial={result['partial_topup']}, skipped={result['skipped']}"
            )

            # Log alerts
            for alert in result.get('alerts', []):
                if alert['level'] == 'critical':
                    logger.critical(
                        f"FUND ALERT [{alert['name']}]: {alert['message']}"
                    )
                elif alert['level'] == 'warning':
                    logger.warning(
                        f"Fund warning [{alert['name']}]: {alert['message']}"
                    )

            return result

        except ImportError as e:
            logger.error(f"FundManager not available: {e}")
            return {'checked': 0, 'topped_up': 0, 'reason': 'import_error'}
        except Exception as e:
            logger.error(f"Fund check failed: {e}")
            return {'checked': 0, 'topped_up': 0, 'reason': str(e)}

    async def _cleanup_tmp_dir(self) -> dict:
        """
        Clean up old files from /tmp directory.

        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        Deletes files older than max_age_hours.
        """
        deleted_files = 0
        deleted_bytes = 0
        max_age_hours = getattr(self, 'cleanup_tmp_max_age', 24)
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        try:
            tmp_path = Path('/tmp')

            for item in tmp_path.iterdir():
                try:
                    # Skip system-critical files/dirs
                    if item.name.startswith('.') or item.name in (
                        'systemd-private-*', 'snap.*', 'ssh-*'
                    ):
                        continue

                    # Check modification time
                    stat = item.stat()
                    if stat.st_mtime < cutoff_time:
                        if item.is_file():
                            size = stat.st_size
                            item.unlink()
                            deleted_files += 1
                            deleted_bytes += size
                        elif item.is_dir():
                            # Recursively delete directory
                            size = sum(
                                f.stat().st_size for f in item.rglob('*') if f.is_file()
                            )
                            shutil.rmtree(item)
                            deleted_files += 1
                            deleted_bytes += size

                except (PermissionError, FileNotFoundError, OSError):
                    # Skip files we can't access or that disappeared
                    continue

            if deleted_files > 0:
                mb_deleted = deleted_bytes / (1024 * 1024)
                logger.info(
                    f"Cleaned /tmp: {deleted_files} items, {mb_deleted:.2f} MB freed"
                )
            else:
                logger.debug("No old files to clean in /tmp")

        except Exception as e:
            logger.error(f"Tmp cleanup failed: {e}")

        return {'deleted_files': deleted_files, 'deleted_bytes': deleted_bytes}

    async def _refresh_market_regimes(self) -> dict:
        """
        Refresh market regime detection for all active pairs.

        Uses Unger's breakout vs reversal method to classify each market as:
        - TREND: Breakout test profitable
        - REVERSAL: Reversal test profitable
        - MIXED: No clear signal

        Results are saved to market_regimes table for use by Unger Generator.

        Runs at the configured regime_run_hour (checked by _should_run_task).
        """
        try:
            from src.generator.regime.detector import refresh_market_regimes

            result = refresh_market_regimes()

            if result.get('enabled', True):
                logger.info(
                    f"Market regime refresh complete: "
                    f"TREND={result.get('trend', 0)}, "
                    f"REVERSAL={result.get('reversal', 0)}, "
                    f"MIXED={result.get('mixed', 0)}"
                )
            else:
                logger.debug("Market regime detection is disabled")

            return result

        except ImportError as e:
            logger.error(f"RegimeDetector not available: {e}")
            return {'trend': 0, 'reversal': 0, 'mixed': 0, 'reason': 'import_error'}
        except Exception as e:
            logger.error(f"Market regime refresh failed: {e}")
            return {'trend': 0, 'reversal': 0, 'mixed': 0, 'reason': str(e)}

    async def _cleanup_old_events(self) -> dict:
        """
        Clean up old StrategyEvent records.

        Events are useful for debugging and pattern recycling but grow fast.
        Deletes events older than max_age_days (configurable, default 7 days).

        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        max_age_days = getattr(self, 'cleanup_events_max_age_days', 7)
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

        try:
            with get_session() as session:
                # Count before delete for logging
                old_events_count = (
                    session.query(StrategyEvent)
                    .filter(StrategyEvent.timestamp < cutoff)
                    .count()
                )

                if old_events_count > 0:
                    # Delete in batches to avoid long locks
                    batch_size = 10000
                    total_deleted = 0

                    while True:
                        deleted = (
                            session.query(StrategyEvent)
                            .filter(StrategyEvent.timestamp < cutoff)
                            .limit(batch_size)
                            .delete(synchronize_session=False)
                        )
                        session.commit()
                        total_deleted += deleted

                        if deleted < batch_size:
                            break

                    logger.info(
                        f"Cleaned up {total_deleted} old strategy events "
                        f"(older than {max_age_days} days)"
                    )
                    return {'deleted': total_deleted}
                else:
                    logger.debug("No old strategy events to clean")
                    return {'deleted': 0}

        except Exception as e:
            logger.error(f"Events cleanup failed: {e}")
            return {'deleted': 0, 'reason': str(e)}

    async def _cleanup_stale_strategies(self) -> dict:
        """
        Clean up strategies stuck in intermediate states.

        Strategies in GENERATED or VALIDATED that haven't been processed
        for max_age_days are likely orphaned (validator/backtester crash, etc.).
        Safe to delete as they will never be processed.

        Runs at the configured run_hour:run_minute (checked by _should_run_task).
        """
        max_age_days = getattr(self, 'cleanup_stale_max_age_days', 1)
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)

        try:
            with get_session() as session:
                stale_strategies = (
                    session.query(Strategy)
                    .filter(
                        Strategy.status.in_(['GENERATED', 'VALIDATED']),
                        Strategy.created_at < cutoff
                    )
                    .all()
                )

                if stale_strategies:
                    for s in stale_strategies:
                        logger.debug(f"Deleting stale strategy: {s.name} (status={s.status})")
                        session.delete(s)

                    logger.info(
                        f"Cleaned up {len(stale_strategies)} stale strategies "
                        f"(GENERATED/VALIDATED older than {max_age_days} days)"
                    )
                    return {'deleted': len(stale_strategies)}
                else:
                    logger.debug("No stale strategies to clean")
                    return {'deleted': 0}

        except Exception as e:
            logger.error(f"Stale strategies cleanup failed: {e}")
            return {'deleted': 0, 'reason': str(e)}

    async def _update_pairs(self) -> dict:
        """
        Update trading pairs from Hyperliquid/Binance.

        Runs at configured update_hours (checked by _should_run_task).
        """
        try:
            from src.data.pairs_updater import PairsUpdater

            logger.info("Starting scheduled pairs update...")
            updater = PairsUpdater()
            result = updater.update()

            updated = result.get('updated', 0)
            new_pairs = result.get('new', 0)
            total = len(result.get('pair_whitelist', []))

            logger.info(
                f"Pairs update complete: {total} pairs "
                f"({new_pairs} new, {updated} updated)"
            )

            return {
                'updated': updated,
                'new_pairs': new_pairs,
                'total': total,
            }

        except Exception as e:
            logger.error(f"Pairs update failed: {e}", exc_info=True)
            return {'updated': 0, 'reason': str(e)}

    async def _download_data(self) -> dict:
        """
        Download OHLCV data for all active pairs.

        Runs at configured update_hours + 5 minutes (checked by _should_run_task).
        Runs after pairs update to ensure we have the latest pair list.
        """
        try:
            from src.data.binance_downloader import BinanceDataDownloader

            logger.info("Starting scheduled OHLCV data download...")
            downloader = BinanceDataDownloader()

            # Cleanup obsolete pairs first
            deleted = downloader.cleanup_obsolete_pairs()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} obsolete pair files")

            # Download all pairs/timeframes
            downloader.download_for_pairs()

            # Get stats
            from src.data.coin_registry import get_active_pairs
            symbols = get_active_pairs()

            logger.info(f"Data download complete: {len(symbols)} symbols")

            return {
                'downloaded': 1,
                'symbols': len(symbols),
                'cleaned': deleted,
            }

        except Exception as e:
            logger.error(f"Data download failed: {e}", exc_info=True)
            return {'downloaded': 0, 'reason': str(e)}

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
