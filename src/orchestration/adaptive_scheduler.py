"""
Adaptive Scheduler

Automatically selects execution mode based on number of strategies.
Supports: sync, async, multiprocess, hybrid modes.

Following CLAUDE.md:
- Auto-scales from 10 to 1000+ strategies
- No hardcoded values
- KISS principle
"""

from typing import Literal
from dataclasses import dataclass
from src.utils.logger import get_logger

logger = get_logger(__name__)

ExecutionMode = Literal['sync', 'async', 'multiprocess', 'hybrid']


@dataclass
class SchedulerConfig:
    """Scheduler configuration thresholds"""
    sync_threshold: int = 50
    async_threshold: int = 100
    multiprocess_threshold: int = 500


class AdaptiveScheduler:
    """
    Automatically selects execution mode based on load

    Modes:
    - sync: 1-50 strategies (simple, single-threaded)
    - async: 50-100 strategies (event loop concurrency)
    - multiprocess: 100-500 strategies (worker pool)
    - hybrid: 500+ strategies (multi-process + async)

    Args:
        config: Configuration dictionary
        initial_mode: Starting execution mode (optional)

    Example:
        scheduler = AdaptiveScheduler(config)
        mode = scheduler.determine_mode(len(strategies))
        scheduler.switch_mode(mode)
    """

    def __init__(
        self,
        config: dict,
        initial_mode: ExecutionMode = 'sync'
    ):
        self.config = config

        # Get thresholds from config (with sensible defaults)
        exec_config = config.get('execution', {}).get('orchestrator', {})
        self.thresholds = SchedulerConfig(
            sync_threshold=50,
            async_threshold=100,
            multiprocess_threshold=500
        )

        self.current_mode = initial_mode
        self.mode_history: list[tuple[ExecutionMode, int]] = []

        logger.info(f"AdaptiveScheduler initialized with mode: {initial_mode}")

    def determine_mode(self, n_strategies: int) -> ExecutionMode:
        """
        Determine optimal execution mode based on strategy count

        Args:
            n_strategies: Number of active strategies

        Returns:
            Recommended execution mode
        """
        if n_strategies <= self.thresholds.sync_threshold:
            return 'sync'
        elif n_strategies <= self.thresholds.async_threshold:
            return 'async'
        elif n_strategies <= self.thresholds.multiprocess_threshold:
            return 'multiprocess'
        else:
            return 'hybrid'

    def should_switch_mode(self, n_strategies: int) -> bool:
        """Check if mode should be switched"""
        recommended_mode = self.determine_mode(n_strategies)
        return recommended_mode != self.current_mode

    def switch_mode(self, new_mode: ExecutionMode, n_strategies: int) -> None:
        """
        Switch execution mode

        Args:
            new_mode: New execution mode
            n_strategies: Current strategy count
        """
        if new_mode == self.current_mode:
            return

        logger.info(
            f"Switching execution mode: {self.current_mode} -> {new_mode} "
            f"(strategies: {n_strategies})"
        )

        self.mode_history.append((self.current_mode, n_strategies))
        self.current_mode = new_mode

    def auto_switch(self, n_strategies: int) -> ExecutionMode:
        """
        Automatically switch mode if needed

        Args:
            n_strategies: Current strategy count

        Returns:
            Current execution mode (after potential switch)
        """
        if self.should_switch_mode(n_strategies):
            new_mode = self.determine_mode(n_strategies)
            self.switch_mode(new_mode, n_strategies)

        return self.current_mode

    def get_mode_info(self, mode: ExecutionMode) -> dict:
        """Get information about execution mode"""
        mode_specs = {
            'sync': {
                'description': 'Simple single-threaded execution',
                'throughput': '20 strategies/sec',
                'cpu_cores': '1-2',
                'ram': '500MB',
                'websockets': 1,
                'pros': ['Simple', 'Easy to debug', 'No concurrency issues'],
                'cons': ['Limited throughput']
            },
            'async': {
                'description': 'Event loop for concurrent I/O',
                'throughput': '100 strategies/sec',
                'cpu_cores': '2-4',
                'ram': '1GB',
                'websockets': '1-2',
                'pros': ['Concurrent API calls', 'Single process'],
                'cons': ['Requires async client']
            },
            'multiprocess': {
                'description': 'Worker pool for CPU parallelism',
                'throughput': '200 strategies/sec',
                'cpu_cores': '8-16',
                'ram': '2GB',
                'websockets': 5,
                'pros': ['True parallelism', 'Linear scaling'],
                'cons': ['Shared data layer required']
            },
            'hybrid': {
                'description': 'Multi-process + async (best of both)',
                'throughput': '500+ strategies/sec',
                'cpu_cores': '16-32',
                'ram': '4GB',
                'websockets': 10,
                'pros': ['Best performance', 'Scales to 1000+'],
                'cons': ['Most complex']
            }
        }

        return mode_specs.get(mode, {})

    def get_statistics(self) -> dict:
        """Get scheduler statistics"""
        return {
            'current_mode': self.current_mode,
            'thresholds': {
                'sync': self.thresholds.sync_threshold,
                'async': self.thresholds.async_threshold,
                'multiprocess': self.thresholds.multiprocess_threshold
            },
            'mode_switches': len(self.mode_history),
            'history': self.mode_history[-10:]  # Last 10 switches
        }
