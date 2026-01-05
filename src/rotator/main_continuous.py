"""
Continuous Rotator Process

Rotates strategies from ACTIVE pool to LIVE deployment:
- Checks for free LIVE slots every N minutes
- Selects top candidates from ACTIVE pool
- Deploys to subaccounts

Single Responsibility: Rotation only (no monitoring, no scoring).
"""

import asyncio
import os
import signal
import threading
from datetime import datetime, UTC
from typing import Optional

from src.config import load_config
from src.rotator.selector import StrategySelector
from src.rotator.deployer import StrategyDeployer
from src.utils import get_logger, setup_logging

# Initialize logging at module load
_config = load_config()
setup_logging(
    log_file='logs/rotator.log',
    log_level=_config.get_required('logging.level'),
)

logger = get_logger(__name__)


class ContinuousRotatorProcess:
    """
    Continuous strategy rotation process.

    Checks for deployment opportunities at regular intervals.
    """

    def __init__(
        self,
        selector: Optional[StrategySelector] = None,
        deployer: Optional[StrategyDeployer] = None
    ):
        """
        Initialize rotator process with dependency injection.

        Args:
            selector: StrategySelector instance (created if not provided)
            deployer: StrategyDeployer instance (created if not provided)
        """
        self.config = load_config()
        self.shutdown_event = threading.Event()
        self.force_exit = False

        # Process configuration
        rotator_config = self.config.get_required('rotator')
        self.check_interval_minutes = rotator_config['check_interval_minutes']

        # Components (dependency injection)
        self.selector = selector or StrategySelector(self.config._raw_config)
        self.deployer = deployer or StrategyDeployer(self.config._raw_config)

        logger.info(
            f"ContinuousRotatorProcess initialized: "
            f"check_interval={self.check_interval_minutes}min"
        )

    async def run_continuous(self):
        """Main continuous rotation loop."""
        logger.info("Starting continuous rotation loop")

        while not self.shutdown_event.is_set() and not self.force_exit:
            try:
                await self._rotation_cycle()
            except Exception as e:
                logger.error(f"Rotation cycle error: {e}", exc_info=True)

            # Wait for next check
            await self._wait_interval()

        logger.info("Rotation loop ended")

    async def _rotation_cycle(self):
        """Single rotation cycle."""
        # Get selection stats
        stats = self.selector.get_selection_stats()
        free_slots = stats['free_slots']

        logger.info(
            f"Rotation check: ACTIVE={stats['active_count']}, "
            f"LIVE={stats['live_count']}/{stats['max_live']}, "
            f"free_slots={free_slots}"
        )

        if free_slots <= 0:
            logger.debug("No free slots available")
            return

        # Get candidates
        candidates = self.selector.get_candidates(free_slots)

        if not candidates:
            logger.debug("No candidates meet selection criteria")
            return

        # Get free subaccounts
        free_subaccounts = self.deployer.get_free_subaccounts()

        if not free_subaccounts:
            logger.warning("No free subaccounts available")
            return

        # Deploy candidates to subaccounts
        deployed_count = 0
        for candidate, subaccount in zip(candidates, free_subaccounts):
            success = await self.deployer.deploy(candidate, subaccount['id'])
            if success:
                deployed_count += 1
                logger.info(
                    f"Deployed {candidate['name']} (score={candidate['score']:.1f}) "
                    f"to subaccount {subaccount['id']}"
                )

        if deployed_count > 0:
            logger.info(f"Rotation complete: {deployed_count} strategies deployed")

    async def _wait_interval(self):
        """Wait for next rotation check."""
        wait_seconds = self.check_interval_minutes * 60

        logger.debug(f"Next rotation check in {self.check_interval_minutes} minutes")

        while wait_seconds > 0 and not self.shutdown_event.is_set():
            sleep_time = min(60, wait_seconds)
            await asyncio.sleep(sleep_time)
            wait_seconds -= sleep_time

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Shutdown requested (signal {signum})")
        self.shutdown_event.set()
        self.force_exit = True
        os._exit(0)

    def run(self):
        """Main entry point."""
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

        try:
            asyncio.run(self.run_continuous())
        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Rotator process terminated")


def main():
    """Entry point for supervisor."""
    process = ContinuousRotatorProcess()
    process.run()


if __name__ == "__main__":
    main()
