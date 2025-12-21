"""
Tests for AdaptiveScheduler

Following CLAUDE.md testing requirements:
- Test auto-scaling behavior
- Test mode switching logic
- Test all execution modes
"""

import pytest
from src.orchestration.adaptive_scheduler import (
    AdaptiveScheduler,
    SchedulerConfig,
    ExecutionMode
)


@pytest.fixture
def config(dry_run_config):
    """Test configuration - use centralized dry_run_config"""
    return dry_run_config


@pytest.fixture
def scheduler(config):
    """Create scheduler instance"""
    return AdaptiveScheduler(config)


class TestSchedulerConfig:
    """Test SchedulerConfig dataclass"""

    def test_default_thresholds(self):
        """Test default threshold values"""
        config = SchedulerConfig()

        assert config.sync_threshold == 50
        assert config.async_threshold == 100
        assert config.multiprocess_threshold == 500


class TestAdaptiveScheduler:
    """Test AdaptiveScheduler"""

    def test_initialization(self, config):
        """Test scheduler initialization"""
        scheduler = AdaptiveScheduler(config)

        assert scheduler.current_mode == 'sync'
        assert len(scheduler.mode_history) == 0

    def test_initialization_custom_mode(self, config):
        """Test initialization with custom mode"""
        scheduler = AdaptiveScheduler(config, initial_mode='async')

        assert scheduler.current_mode == 'async'

    def test_determine_mode_sync(self, scheduler):
        """Test mode determination for small strategy count"""
        # 1-50 strategies → sync mode
        assert scheduler.determine_mode(1) == 'sync'
        assert scheduler.determine_mode(25) == 'sync'
        assert scheduler.determine_mode(50) == 'sync'

    def test_determine_mode_async(self, scheduler):
        """Test mode determination for medium strategy count"""
        # 51-100 strategies → async mode
        assert scheduler.determine_mode(51) == 'async'
        assert scheduler.determine_mode(75) == 'async'
        assert scheduler.determine_mode(100) == 'async'

    def test_determine_mode_multiprocess(self, scheduler):
        """Test mode determination for large strategy count"""
        # 101-500 strategies → multiprocess mode
        assert scheduler.determine_mode(101) == 'multiprocess'
        assert scheduler.determine_mode(250) == 'multiprocess'
        assert scheduler.determine_mode(500) == 'multiprocess'

    def test_determine_mode_hybrid(self, scheduler):
        """Test mode determination for very large strategy count"""
        # 501+ strategies → hybrid mode
        assert scheduler.determine_mode(501) == 'hybrid'
        assert scheduler.determine_mode(1000) == 'hybrid'
        assert scheduler.determine_mode(5000) == 'hybrid'

    def test_should_switch_mode_no_change(self, scheduler):
        """Test should_switch_mode returns False if mode unchanged"""
        # Current mode is 'sync', 25 strategies also needs 'sync'
        assert not scheduler.should_switch_mode(25)

    def test_should_switch_mode_needed(self, scheduler):
        """Test should_switch_mode returns True if mode should change"""
        # Current mode is 'sync', 100 strategies needs 'async'
        assert scheduler.should_switch_mode(100)

    def test_switch_mode(self, scheduler):
        """Test mode switching"""
        assert scheduler.current_mode == 'sync'

        scheduler.switch_mode('async', 75)

        assert scheduler.current_mode == 'async'
        assert len(scheduler.mode_history) == 1
        assert scheduler.mode_history[0] == ('sync', 75)

    def test_switch_mode_no_change(self, scheduler):
        """Test switch_mode does nothing if mode unchanged"""
        scheduler.switch_mode('sync', 10)

        assert scheduler.current_mode == 'sync'
        assert len(scheduler.mode_history) == 0

    def test_auto_switch_no_change(self, scheduler):
        """Test auto_switch keeps current mode if appropriate"""
        mode = scheduler.auto_switch(25)

        assert mode == 'sync'
        assert scheduler.current_mode == 'sync'
        assert len(scheduler.mode_history) == 0

    def test_auto_switch_changes_mode(self, scheduler):
        """Test auto_switch changes mode when needed"""
        mode = scheduler.auto_switch(75)

        assert mode == 'async'
        assert scheduler.current_mode == 'async'
        assert len(scheduler.mode_history) == 1

    def test_auto_switch_multiple_changes(self, scheduler):
        """Test auto_switch tracks multiple mode changes"""
        scheduler.auto_switch(25)   # sync
        scheduler.auto_switch(75)   # async
        scheduler.auto_switch(250)  # multiprocess
        scheduler.auto_switch(750)  # hybrid

        assert scheduler.current_mode == 'hybrid'
        assert len(scheduler.mode_history) == 3

    def test_get_mode_info_sync(self, scheduler):
        """Test mode info for sync mode"""
        info = scheduler.get_mode_info('sync')

        assert 'description' in info
        assert 'throughput' in info
        assert 'cpu_cores' in info
        assert 'ram' in info
        assert 'pros' in info
        assert 'cons' in info
        assert info['throughput'] == '20 strategies/sec'

    def test_get_mode_info_async(self, scheduler):
        """Test mode info for async mode"""
        info = scheduler.get_mode_info('async')

        assert info['throughput'] == '100 strategies/sec'
        assert 'Event loop' in info['description']

    def test_get_mode_info_multiprocess(self, scheduler):
        """Test mode info for multiprocess mode"""
        info = scheduler.get_mode_info('multiprocess')

        assert info['throughput'] == '200 strategies/sec'
        assert 'parallelism' in info['description']

    def test_get_mode_info_hybrid(self, scheduler):
        """Test mode info for hybrid mode"""
        info = scheduler.get_mode_info('hybrid')

        assert info['throughput'] == '500+ strategies/sec'
        assert 'best' in info['description'].lower()

    def test_get_mode_info_invalid(self, scheduler):
        """Test mode info for invalid mode"""
        info = scheduler.get_mode_info('invalid_mode')

        assert info == {}

    def test_get_statistics(self, scheduler):
        """Test statistics collection"""
        stats = scheduler.get_statistics()

        assert stats['current_mode'] == 'sync'
        assert 'thresholds' in stats
        assert stats['thresholds']['sync'] == 50
        assert stats['thresholds']['async'] == 100
        assert stats['thresholds']['multiprocess'] == 500
        assert stats['mode_switches'] == 0
        assert stats['history'] == []

    def test_get_statistics_with_history(self, scheduler):
        """Test statistics with mode change history"""
        scheduler.auto_switch(75)   # sync → async
        scheduler.auto_switch(250)  # async → multiprocess

        stats = scheduler.get_statistics()

        assert stats['current_mode'] == 'multiprocess'
        assert stats['mode_switches'] == 2
        assert len(stats['history']) == 2
        assert stats['history'][0] == ('sync', 75)
        assert stats['history'][1] == ('async', 250)

    def test_scaling_scenario_10_to_1000(self, scheduler):
        """Test realistic scaling scenario from 10 to 1000 strategies"""
        strategy_counts = [10, 50, 75, 100, 250, 500, 750, 1000]
        expected_modes = ['sync', 'sync', 'async', 'async', 'multiprocess', 'multiprocess', 'hybrid', 'hybrid']

        for count, expected in zip(strategy_counts, expected_modes):
            mode = scheduler.auto_switch(count)
            assert mode == expected, f"Failed at {count} strategies"

    def test_mode_history_limit(self, scheduler):
        """Test mode history is limited in statistics"""
        # Create many mode switches by oscillating between thresholds
        # This will force actual mode changes
        test_counts = []
        for i in range(15):
            # Oscillate to force mode changes
            if i % 4 == 0:
                test_counts.append(30)   # sync
            elif i % 4 == 1:
                test_counts.append(80)   # async
            elif i % 4 == 2:
                test_counts.append(200)  # multiprocess
            else:
                test_counts.append(600)  # hybrid

        for n in test_counts:
            scheduler.auto_switch(n)

        stats = scheduler.get_statistics()

        # History should be limited to last 10 in statistics
        # We made 15 oscillations, which creates 12 actual switches
        # (first call doesn't switch from initial mode)
        # So history should have max 10 elements
        assert len(stats['history']) <= 10

        # Verify we actually made some switches
        assert len(stats['history']) > 0

    def test_concurrent_mode_switches(self, scheduler):
        """Test scheduler is thread-safe for mode switches"""
        import threading

        errors = []

        def worker(n_strategies):
            try:
                scheduler.auto_switch(n_strategies)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=[count])
            for count in [25, 75, 250, 750]
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_mode_persistence(self, scheduler):
        """Test mode persists after determination"""
        scheduler.auto_switch(75)
        assert scheduler.current_mode == 'async'

        # Calling with same count shouldn't change mode
        scheduler.auto_switch(75)
        assert scheduler.current_mode == 'async'

        # History shouldn't grow
        assert len(scheduler.mode_history) == 1
