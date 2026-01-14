"""
Data Scheduler

Scheduled updates for trading pairs and historical OHLCV data.
Runs at configurable hours (default: 02:00 and 14:00 UTC).

Design Principles:
- KISS: Simple cron-like scheduling
- Fast Fail: Crash if critical operations fail
- No Defaults: Hours from config
"""

import logging
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.loader import load_config
from src.data.pairs_updater import PairsUpdater
from src.data.binance_downloader import BinanceDataDownloader

logger = logging.getLogger(__name__)


class DataScheduler:
    """
    Scheduled data updates for SixBTC.

    Jobs:
    1. Update trading_pairs.json (top 50 by volume)
    2. Download OHLCV data for all pairs/timeframes
    3. Cleanup obsolete pair data

    Schedule: Configurable hours (default 02:00, 14:00 UTC)
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize DataScheduler.

        Args:
            config: Configuration dict (loads from file if None)
        """
        self.config = config or load_config()._raw_config
        self.scheduler = BackgroundScheduler(timezone='UTC')
        self.shutdown_event = threading.Event()

        # Configuration
        sched_config = self.config.get('data_scheduler', {})
        self.update_hours = sched_config.get('update_hours', [2, 14])
        self.enabled = sched_config.get('enabled', True)

        # Components (lazy init)
        self._pairs_updater: Optional[PairsUpdater] = None
        self._binance_downloader: Optional[BinanceDataDownloader] = None
        self._funding_loader = None  # Lazy init to avoid circular imports

        # Funding config
        funding_config = self.config.get('funding', {})
        self.funding_enabled = funding_config.get('enabled', False)

        logger.info(
            f"DataScheduler initialized: hours={self.update_hours}, enabled={self.enabled}"
        )

    @property
    def pairs_updater(self) -> PairsUpdater:
        """Lazy init pairs updater"""
        if self._pairs_updater is None:
            self._pairs_updater = PairsUpdater()
        return self._pairs_updater

    @property
    def binance_downloader(self) -> BinanceDataDownloader:
        """Lazy init binance downloader"""
        if self._binance_downloader is None:
            self._binance_downloader = BinanceDataDownloader()
        return self._binance_downloader

    @property
    def funding_loader(self):
        """Lazy init funding loader"""
        if self._funding_loader is None:
            from src.data.funding_loader import FundingLoader
            self._funding_loader = FundingLoader()
        return self._funding_loader

    def update_pairs(self) -> None:
        """
        Update trading_pairs.json with top pairs by volume.

        Called at scheduled times (e.g., 02:00 UTC).
        """
        logger.info("Starting scheduled pairs update...")

        try:
            result = self.pairs_updater.update()
            n_pairs = len(result.get('pair_whitelist', []))
            logger.info(f"Pairs update complete: {n_pairs} pairs")

        except Exception as e:
            logger.error(f"Pairs update failed: {e}", exc_info=True)

    def download_data(self) -> None:
        """
        Download OHLCV data for all pairs in trading_pairs.json.

        Called 5 minutes after pairs update.
        """
        logger.info("Starting scheduled data download...")

        try:
            # Cleanup obsolete pairs first
            deleted = self.binance_downloader.cleanup_obsolete_pairs()
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} obsolete pairs")

            # Download all pairs/timeframes
            self.binance_downloader.download_for_pairs()
            logger.info("Data download complete")

            # Sync funding rates if enabled
            if self.funding_enabled:
                self.sync_funding()

        except Exception as e:
            logger.error(f"Data download failed: {e}", exc_info=True)

    def sync_funding(self) -> None:
        """
        Sync funding rates for all active coins from Hyperliquid.

        Called after OHLCV download when funding.enabled=true.
        """
        if not self.funding_enabled:
            return

        logger.info("Starting funding rates sync...")

        try:
            from src.data.coin_registry import get_active_pairs
            symbols = get_active_pairs()

            logger.info(f"Syncing funding rates for {len(symbols)} symbols")
            results = self.funding_loader.download_for_symbols(symbols)

            success = sum(1 for v in results.values() if v is not None)
            failed = len(results) - success

            logger.info(f"Funding sync complete: {success} success, {failed} failed")

        except Exception as e:
            logger.error(f"Funding sync failed: {e}", exc_info=True)

    def run_now(self) -> None:
        """
        Run update immediately (for manual trigger or testing).
        """
        logger.info("Running immediate update...")
        self.update_pairs()

        # Small delay between pairs and data download
        time.sleep(5)

        self.download_data()
        logger.info("Immediate update complete")

    def _schedule_jobs(self) -> None:
        """Setup scheduled jobs"""
        # Convert hours list to cron hour string (e.g., "4,16")
        hour_str = ','.join(str(h) for h in self.update_hours)

        # Job 1: Update pairs at configured hours
        self.scheduler.add_job(
            self.update_pairs,
            CronTrigger(hour=hour_str, minute=0),
            id='update_pairs',
            name='Update Trading Pairs',
            replace_existing=True
        )

        # Job 2: Download data 5 minutes after pairs update
        self.scheduler.add_job(
            self.download_data,
            CronTrigger(hour=hour_str, minute=5),
            id='download_data',
            name='Download OHLCV Data',
            replace_existing=True
        )

        logger.info(f"Scheduled jobs: pairs+data at {hour_str}:00 and {hour_str}:05 UTC")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, stopping scheduler...")
        self.shutdown_event.set()

    def run(self) -> None:
        """
        Main entry point - start scheduler and wait.
        """
        if not self.enabled:
            logger.warning("DataScheduler is disabled in config")
            return

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Schedule jobs
        self._schedule_jobs()

        # Start scheduler
        self.scheduler.start()
        logger.info("DataScheduler started")

        # Run initial update if pairs file is stale or missing
        if self.pairs_updater.is_config_stale(max_age_hours=12):
            logger.info("Pairs config is stale, running initial update...")
            try:
                self.run_now()
            except Exception as e:
                logger.error(f"Initial update failed: {e}")

        # Wait for shutdown
        try:
            while not self.shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.scheduler.shutdown(wait=False)
            logger.info("DataScheduler stopped")


def run_scheduler():
    """Convenience function to run scheduler"""
    scheduler = DataScheduler()
    scheduler.run()


if __name__ == "__main__":
    run_scheduler()
