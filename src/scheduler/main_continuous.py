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
from typing import Dict, List, Set

from src.config import load_config
from src.database import get_session, Strategy, StrategyProcessor
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
            'cleanup_old_failed': 24,  # Daily
            'generate_daily_report': 24,  # Daily
            'refresh_data_cache': 4,  # Every 4 hours
        }

        # Configurable tasks (check enabled flag)
        scheduler_config = self.config._raw_config.get('scheduler', {}).get('tasks', {})

        zombie_config = scheduler_config.get('cleanup_zombie_processes', {})
        if zombie_config.get('enabled', False):
            self.tasks['cleanup_zombie_processes'] = zombie_config['interval_hours']

        restart_config = scheduler_config.get('daily_restart_services', {})
        if restart_config.get('enabled', False):
            self.tasks['daily_restart_services'] = restart_config['interval_hours']
            self.restart_hour = restart_config['restart_hour']

        # Agent wallet renewal (renew expiring credentials)
        renew_config = scheduler_config.get('renew_agent_wallets', {})
        if renew_config.get('enabled', False):
            self.tasks['renew_agent_wallets'] = renew_config['interval_hours']
            self.renew_agent_hour = renew_config.get('run_hour', 3)

        # Subaccount fund check (topup from master if low)
        funds_config = scheduler_config.get('check_subaccount_funds', {})
        if funds_config.get('enabled', False):
            self.tasks['check_subaccount_funds'] = funds_config['interval_hours']
            self.check_funds_hour = funds_config.get('run_hour', 4)

        # Cleanup /tmp directory
        tmp_config = scheduler_config.get('cleanup_tmp_dir', {})
        if tmp_config.get('enabled', False):
            self.tasks['cleanup_tmp_dir'] = tmp_config['interval_hours']
            self.cleanup_tmp_hour = tmp_config.get('run_hour', 5)
            self.cleanup_tmp_max_age = tmp_config.get('max_age_hours', 24)

        # Market regime detection (Unger method)
        regime_config = self.config._raw_config.get('regime', {})
        if regime_config.get('enabled', False):
            self.tasks['refresh_market_regimes'] = 24  # Daily
            self.regime_run_hour = 1  # Run at 01:00 UTC

        # Initialize last run times (use timezone-aware datetime)
        for task in self.tasks:
            self.last_run[task] = datetime.min.replace(tzinfo=UTC)

        logger.info(
            f"ContinuousSchedulerProcess initialized: {len(self.tasks)} tasks"
        )

    async def run_continuous(self):
        """Main continuous scheduler loop"""
        logger.info("Starting continuous scheduler loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                now = datetime.now(UTC)

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
        """Run a scheduled task with tracking"""
        with track_task_execution(task_name, task_type='scheduler') as tracker:
            if task_name == 'cleanup_stale_processing':
                result = await self._cleanup_stale_processing()
                tracker.add_metadata('released_count', result.get('released', 0))

            elif task_name == 'cleanup_old_failed':
                result = await self._cleanup_old_failed()
                tracker.add_metadata('deleted_count', result.get('deleted', 0))

            elif task_name == 'generate_daily_report':
                result = await self._generate_daily_report()
                tracker.add_metadata('strategy_counts', result.get('counts', {}))
                tracker.add_metadata('live_strategies', result.get('live_strategies', 0))

            elif task_name == 'refresh_data_cache':
                result = await self._refresh_data_cache()
                tracker.add_metadata('refreshed_timeframes', result.get('timeframes', []))

            elif task_name == 'cleanup_zombie_processes':
                result = await self._cleanup_zombie_processes()
                tracker.add_metadata('killed_count', result.get('killed', 0))

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

            else:
                logger.warning(f"Unknown task: {task_name}")

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
        """Clean up old FAILED strategies"""
        with get_session() as session:
            cutoff = datetime.now(UTC) - timedelta(days=7)

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

            return {'deleted': len(old_failed)}

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

    async def _cleanup_zombie_processes(self) -> dict:
        """
        Kill zombie processes that accumulate over time.

        Targets:
        - Vite dev server instances (multiple can spawn from restarts)
        - Only kills processes NOT in the supervisor process tree
        """
        killed = 0

        try:
            # Get current supervisor-managed frontend PID and all its descendants
            result = subprocess.run(
                ['supervisorctl', 'pid', 'sixbtc:frontend'],
                capture_output=True,
                text=True
            )
            supervisor_pid = result.stdout.strip() if result.returncode == 0 else None

            # Get all descendants of supervisor frontend process
            protected_pids: Set[str] = set()
            if supervisor_pid:
                protected_pids.add(supervisor_pid)
                # Get all child PIDs recursively using pgrep -P
                result = subprocess.run(
                    ['pgrep', '-P', supervisor_pid],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    for child in result.stdout.strip().split('\n'):
                        if child.strip():
                            protected_pids.add(child.strip())
                            # Also get grandchildren
                            result2 = subprocess.run(
                                ['pgrep', '-P', child.strip()],
                                capture_output=True,
                                text=True
                            )
                            if result2.returncode == 0:
                                for grandchild in result2.stdout.strip().split('\n'):
                                    if grandchild.strip():
                                        protected_pids.add(grandchild.strip())

            # Find all vite processes
            result = subprocess.run(
                ['pgrep', '-f', 'vite.*5173'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {'killed': 0}

            vite_pids = result.stdout.strip().split('\n')

            for pid in vite_pids:
                pid = pid.strip()
                if not pid or not pid.isdigit():
                    continue

                # Skip protected processes (supervisor tree)
                if pid in protected_pids:
                    continue

                # Kill the zombie process
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                    logger.info(f"Killed zombie vite process: PID {pid}")
                except (ProcessLookupError, PermissionError):
                    pass

            if killed > 0:
                logger.info(f"Cleanup complete: killed {killed} zombie processes")
            else:
                logger.debug("No zombie processes found")

        except Exception as e:
            logger.error(f"Zombie cleanup failed: {e}")

        return {'killed': killed}

    async def _daily_restart_services(self) -> dict:
        """
        Restart all sixbtc services once per day.

        Only runs at the configured restart_hour. No default - config required.
        Skips restarting the scheduler itself (would interrupt this task).
        """
        # Check if it's the right hour (exact match only)
        current_hour = datetime.now(UTC).hour
        target_hour = self.restart_hour  # No default - must be in config

        if current_hour != target_hour:
            logger.debug(
                f"Skipping daily restart: current hour {current_hour}, target {target_hour}"
            )
            return {'restarted': False, 'reason': 'wrong_hour'}

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

        Only runs at the configured run_hour. No default - config required.
        """
        # Check if it's the right hour
        current_hour = datetime.now(UTC).hour
        target_hour = getattr(self, 'renew_agent_hour', 3)

        if current_hour != target_hour:
            logger.debug(
                f"Skipping agent renewal: current hour {current_hour}, target {target_hour}"
            )
            return {'renewed': 0, 'failed': 0, 'reason': 'wrong_hour'}

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

        Only runs at the configured run_hour. No default - config required.
        """
        # Check if it's the right hour
        current_hour = datetime.now(UTC).hour
        target_hour = getattr(self, 'check_funds_hour', 4)

        if current_hour != target_hour:
            logger.debug(
                f"Skipping fund check: current hour {current_hour}, target {target_hour}"
            )
            return {'checked': 0, 'topped_up': 0, 'reason': 'wrong_hour'}

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

        Only runs at the configured run_hour.
        Deletes files older than max_age_hours.
        """
        # Check if it's the right hour
        current_hour = datetime.now(UTC).hour
        target_hour = getattr(self, 'cleanup_tmp_hour', 5)

        if current_hour != target_hour:
            logger.debug(
                f"Skipping tmp cleanup: current hour {current_hour}, target {target_hour}"
            )
            return {'deleted_files': 0, 'deleted_bytes': 0, 'reason': 'wrong_hour'}

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

        Only runs at the configured regime_run_hour (default 01:00 UTC).
        """
        # Check if it's the right hour
        current_hour = datetime.now(UTC).hour
        target_hour = getattr(self, 'regime_run_hour', 1)

        if current_hour != target_hour:
            logger.debug(
                f"Skipping regime refresh: current hour {current_hour}, target {target_hour}"
            )
            return {'trend': 0, 'reversal': 0, 'mixed': 0, 'reason': 'wrong_hour'}

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
