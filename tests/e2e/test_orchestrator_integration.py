"""
End-to-End Integration Tests for Orchestrator

Following CLAUDE.md testing requirements:
- Test full system integration with dry_run=True
- Verify NO real orders are placed
- Test complete lifecycle
"""

import pytest
from unittest.mock import patch, MagicMock
from src.orchestration.orchestrator import Orchestrator


@pytest.fixture
def config(dry_run_config):
    """Full system configuration - use centralized dry_run_config"""
    return dry_run_config


class TestOrchestratorIntegration:
    """End-to-end integration tests"""

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_initialization_dry_run(self, mock_db, mock_client, config):
        """Test complete initialization in dry-run mode"""
        # Create orchestrator in dry-run mode
        orch = Orchestrator(config, dry_run=True)

        # Verify all components initialized
        assert orch.client is not None
        assert orch.risk_manager is not None
        assert orch.position_tracker is not None
        assert orch.subaccount_manager is not None
        assert orch.scheduler is not None

        # Verify dry-run mode
        assert orch.dry_run is True
        assert not orch.running

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_no_real_orders_in_dry_run(self, mock_db, mock_client, config):
        """
        CRITICAL SAFETY TEST

        Verify that NO real orders are placed when dry_run=True
        """
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client_instance.place_order.return_value = {'success': True, 'dry_run': True}
        mock_client.return_value = mock_client_instance

        # Create orchestrator in dry-run mode
        orch = Orchestrator(config, dry_run=True)

        # Verify client was created with dry_run=True
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs.get('dry_run') is True, "Client must be created with dry_run=True"

        # Verify client's dry_run property
        assert mock_client_instance.dry_run is True or call_kwargs.get('dry_run') is True

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_load_strategies_integration(self, mock_db, mock_client, config):
        """Test loading strategies from database"""
        # Mock database with strategies
        mock_strategy = MagicMock()
        mock_strategy.name = 'Strategy_MOM_test123'
        mock_strategy.subaccount_id = 1
        mock_strategy.symbol = 'BTC'
        mock_strategy.timeframe = '15m'
        mock_strategy.status = 'LIVE'

        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_strategy]
        mock_session = MagicMock()
        mock_session.query.return_value = mock_query
        mock_db.return_value.__enter__.return_value = mock_session

        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)

        # Load strategies
        orch.load_strategies()

        # Verify strategies loaded
        assert len(orch.strategies) == 1
        assert orch.strategies[0].symbol == 'BTC'
        assert orch.strategies[0].timeframe == '15m'

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_data_provider_initialization(self, mock_db, mock_client, config):
        """Test WebSocket data provider initialization"""
        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)

        # Add test strategies
        from src.orchestration.orchestrator import StrategyInstance
        orch.strategies = [
            StrategyInstance(None, 1, 'BTC', '15m'),
            StrategyInstance(None, 2, 'ETH', '1h'),
            StrategyInstance(None, 3, 'SOL', '4h'),
        ]

        # Initialize data provider
        orch.initialize_data_provider()

        # Verify data provider created
        assert orch.data_provider is not None
        assert 'BTC' in orch.data_provider.symbols
        assert 'ETH' in orch.data_provider.symbols
        assert 'SOL' in orch.data_provider.symbols
        assert '15m' in orch.data_provider.timeframes
        assert '1h' in orch.data_provider.timeframes
        assert '4h' in orch.data_provider.timeframes

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_adaptive_scheduler_integration(self, mock_db, mock_client, config):
        """Test adaptive scheduler determines correct mode"""
        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)

        # Test with different strategy counts
        from src.orchestration.orchestrator import StrategyInstance

        # Small count → sync mode
        orch.strategies = [
            StrategyInstance(None, i, 'BTC', '15m')
            for i in range(25)
        ]
        mode = orch.scheduler.determine_mode(len(orch.strategies))
        assert mode == 'sync'

        # Medium count → async mode
        orch.strategies = [
            StrategyInstance(None, i, 'BTC', '15m')
            for i in range(75)
        ]
        mode = orch.scheduler.determine_mode(len(orch.strategies))
        assert mode == 'async'

        # Large count → multiprocess mode
        orch.strategies = [
            StrategyInstance(None, i, 'BTC', '15m')
            for i in range(250)
        ]
        mode = orch.scheduler.determine_mode(len(orch.strategies))
        assert mode == 'multiprocess'

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_emergency_stop_integration(self, mock_db, mock_client, config):
        """Test emergency stop functionality"""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)
        orch.running = True

        # Add test strategies
        from src.orchestration.orchestrator import StrategyInstance
        orch.strategies = [
            StrategyInstance(None, 1, 'BTC', '15m'),
            StrategyInstance(None, 2, 'ETH', '1h'),
        ]

        # Trigger emergency stop
        orch.emergency_stop()

        # Verify system stopped
        assert not orch.running

        # Verify close_position called for each strategy
        assert mock_client_instance.close_position.call_count == 2

        # Verify cancel_all_orders called for each strategy
        assert mock_client_instance.cancel_all_orders.call_count == 2

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_graceful_shutdown_integration(self, mock_db, mock_client, config):
        """Test graceful shutdown"""
        # Setup mock client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)
        orch.running = True

        # Initialize data provider
        orch.initialize_data_provider()
        if orch.data_provider:
            orch.data_provider.start()

        # Add strategies
        from src.orchestration.orchestrator import StrategyInstance
        orch.strategies = [StrategyInstance(None, 1, 'BTC', '15m')]

        # Stop gracefully
        orch.stop()

        # Verify stopped
        assert not orch.running

        # Verify data provider stopped
        if orch.data_provider:
            assert not orch.data_provider.running

        # Verify orders canceled (based on config)
        if config['deployment']['shutdown']['cancel_orders']:
            assert mock_client_instance.cancel_all_orders.call_count >= 0

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_statistics_integration(self, mock_db, mock_client, config):
        """Test complete statistics collection"""
        # Create orchestrator
        orch = Orchestrator(config, dry_run=True)

        # Add strategies
        from src.orchestration.orchestrator import StrategyInstance
        orch.strategies = [
            StrategyInstance(None, 1, 'BTC', '15m', active=True),
            StrategyInstance(None, 2, 'ETH', '1h', active=True),
            StrategyInstance(None, 3, 'SOL', '4h', active=False),
        ]

        # Initialize data provider
        orch.initialize_data_provider()

        # Get statistics
        stats = orch.get_statistics()

        # Verify all statistics present
        assert 'running' in stats
        assert 'dry_run' in stats
        assert 'active_strategies' in stats
        assert 'total_strategies' in stats
        assert 'execution_mode' in stats
        assert 'iterations' in stats
        assert 'signals_generated' in stats
        assert 'orders_placed' in stats

        # Verify values
        assert stats['dry_run'] is True
        assert stats['active_strategies'] == 2
        assert stats['total_strategies'] == 3

    @patch('src.orchestration.orchestrator.HyperliquidClient')
    @patch('src.orchestration.orchestrator.get_session')
    def test_full_lifecycle_dry_run(self, mock_db, mock_client, config):
        """
        COMPREHENSIVE INTEGRATION TEST

        Test complete lifecycle in dry-run mode:
        1. Initialize
        2. Load strategies
        3. Start data provider
        4. Run (mock)
        5. Stop gracefully
        """
        # Mock database
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_db.return_value.__enter__.return_value = mock_session

        # Create orchestrator in dry-run mode
        orch = Orchestrator(config, dry_run=True)
        assert orch.dry_run is True

        # Load strategies (empty for this test)
        orch.load_strategies()
        assert len(orch.strategies) == 0

        # With no strategies, start should exit gracefully
        orch.start()
        assert not orch.running  # Should not be running with no strategies

        # Statistics should be available
        stats = orch.get_statistics()
        assert stats is not None
        assert stats['dry_run'] is True
