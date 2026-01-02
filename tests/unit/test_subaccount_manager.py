"""
Test Subaccount Manager

Unit tests for subaccount management - DRY RUN ONLY.
"""

import pytest
import sys
from pathlib import Path

# Add project root and tests to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'tests'))

from src.executor.subaccount_manager import SubaccountManager
from mocks.mock_hyperliquid import MockHyperliquidClient
from src.strategies.base import StrategyCore, Signal
import pandas as pd


class DummyStrategy(StrategyCore):
    """Dummy strategy for testing"""
    indicator_columns = []

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None


class TestSubaccountManager:
    """Test subaccount management - DRY RUN ONLY"""

    @pytest.fixture
    def mock_client(self):
        """Mock Hyperliquid client - NO REAL ORDERS"""
        return MockHyperliquidClient()

    @pytest.fixture
    def manager(self, mock_client):
        """Subaccount manager with mock client"""
        return SubaccountManager(mock_client, dry_run=True)

    def test_init_dry_run(self, manager):
        """Manager initializes in dry_run mode"""
        assert manager.dry_run is True
        assert manager.get_active_count() == 0

    def test_deploy_strategy_dry_run(self, manager):
        """Deploy strategy (dry run)"""
        strategy = DummyStrategy()
        success = manager.deploy_strategy(
            strategy_id='test_123',
            strategy_instance=strategy,
            subaccount_id=1,
            metadata={'type': 'MOM', 'timeframe': '15m'}
        )

        assert success is True
        assignment = manager.get_assignment(1)
        assert assignment is not None
        assert assignment['strategy_id'] == 'test_123'
        assert assignment['strategy'] == strategy

    def test_deploy_invalid_subaccount(self, manager):
        """Invalid subaccount ID rejected"""
        strategy = DummyStrategy()

        # Test invalid IDs
        assert manager.deploy_strategy('test', strategy, 0) is False
        assert manager.deploy_strategy('test', strategy, 11) is False
        assert manager.deploy_strategy('test', strategy, -1) is False

    def test_stop_strategy(self, manager, mock_client):
        """Stop strategy closes positions (dry run)"""
        strategy = DummyStrategy()
        manager.deploy_strategy('test_123', strategy, 1)

        # Verify deployed
        assert manager.get_assignment(1) is not None

        # Stop strategy
        success = manager.stop_strategy(1, close_positions=True)

        assert success is True
        assert manager.get_assignment(1) is None

        # In dry-run, no real close_all_positions call
        # (mock client just logs it)

    def test_stop_empty_subaccount(self, manager):
        """Stopping empty subaccount handled gracefully"""
        success = manager.stop_strategy(5, close_positions=True)
        assert success is False  # No strategy to stop

    def test_get_all_assignments(self, manager):
        """Get all subaccount assignments"""
        strategy1 = DummyStrategy()
        strategy2 = DummyStrategy()

        manager.deploy_strategy('strat_1', strategy1, 1)
        manager.deploy_strategy('strat_2', strategy2, 5)

        assignments = manager.get_all_assignments()

        assert len(assignments) == 10  # All 10 subaccounts
        assert assignments[1] is not None
        assert assignments[5] is not None
        assert assignments[2] is None  # Empty

    def test_get_active_count(self, manager):
        """Active count tracks deployed strategies"""
        assert manager.get_active_count() == 0

        manager.deploy_strategy('s1', DummyStrategy(), 1)
        assert manager.get_active_count() == 1

        manager.deploy_strategy('s2', DummyStrategy(), 3)
        assert manager.get_active_count() == 2

        manager.stop_strategy(1)
        assert manager.get_active_count() == 1

    def test_stop_all_strategies(self, manager):
        """Stop all strategies"""
        # Deploy multiple
        for i in range(1, 6):
            manager.deploy_strategy(f'strat_{i}', DummyStrategy(), i)

        assert manager.get_active_count() == 5

        # Stop all
        manager.stop_all_strategies(close_positions=True)

        assert manager.get_active_count() == 0
        assert all(a is None for a in manager.get_all_assignments().values())

    def test_deploy_batch(self, manager):
        """Deploy multiple strategies in batch"""
        strategies = [
            {
                'strategy_id': f'strat_{i}',
                'strategy': DummyStrategy(),
                'metadata': {'index': i}
            }
            for i in range(5)
        ]

        deployed = manager.deploy_batch(strategies, start_subaccount=1)

        assert deployed == 5
        assert manager.get_active_count() == 5

        # Check assignments
        for i in range(5):
            assignment = manager.get_assignment(i + 1)
            assert assignment is not None
            assert assignment['strategy_id'] == f'strat_{i}'

    def test_deploy_batch_overflow(self, manager):
        """Deploy batch stops at subaccount 10"""
        strategies = [
            {'strategy_id': f'strat_{i}', 'strategy': DummyStrategy()}
            for i in range(15)  # More than 10
        ]

        deployed = manager.deploy_batch(strategies, start_subaccount=1)

        # Should only deploy 10
        assert deployed == 10
        assert manager.get_active_count() == 10

    def test_redeploy_replaces_strategy(self, manager):
        """Deploying to occupied subaccount replaces strategy"""
        strategy1 = DummyStrategy()
        strategy2 = DummyStrategy()

        # Deploy first
        manager.deploy_strategy('old', strategy1, 1)
        assert manager.get_assignment(1)['strategy_id'] == 'old'

        # Deploy second (should replace)
        manager.deploy_strategy('new', strategy2, 1)
        assert manager.get_assignment(1)['strategy_id'] == 'new'
        assert manager.get_active_count() == 1  # Still just 1 strategy
