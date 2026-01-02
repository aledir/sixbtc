"""
Tests for Orchestrator

Following CLAUDE.md testing requirements:
- Test dry_run mode enforcement
- Test graceful shutdown
- Test emergency stop
- Mock all external dependencies
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.orchestration.orchestrator import Orchestrator, StrategyInstance


@pytest.fixture
def config(dry_run_config):
    """Test configuration - use centralized dry_run_config"""
    return dry_run_config


@pytest.fixture
def orchestrator_dry_run(config):
    """Create orchestrator in dry-run mode"""
    with patch('src.orchestration.orchestrator.HyperliquidClient'), \
         patch('src.orchestration.orchestrator.get_session'):
        return Orchestrator(config, dry_run=True)


@pytest.fixture
def orchestrator_live(config):
    """Create orchestrator in live mode"""
    with patch('src.orchestration.orchestrator.HyperliquidClient'), \
         patch('src.orchestration.orchestrator.get_session'):
        return Orchestrator(config, dry_run=False)


class TestOrchestratorInitialization:
    """Test orchestrator initialization"""

    def test_init_dry_run(self, orchestrator_dry_run):
        """Test initialization in dry-run mode"""
        assert orchestrator_dry_run.dry_run is True
        assert orchestrator_dry_run.running is False
        assert orchestrator_dry_run.shutdown_requested is False
        assert len(orchestrator_dry_run.strategies) == 0

    def test_init_live(self, orchestrator_live):
        """Test initialization in live mode"""
        assert orchestrator_live.dry_run is False
        assert orchestrator_live.running is False

    def test_components_created(self, orchestrator_dry_run):
        """Test all components are initialized"""
        assert orchestrator_dry_run.client is not None
        assert orchestrator_dry_run.risk_manager is not None
        assert orchestrator_dry_run.position_tracker is not None
        assert orchestrator_dry_run.subaccount_manager is not None
        assert orchestrator_dry_run.scheduler is not None

    def test_statistics_initialized(self, orchestrator_dry_run):
        """Test statistics are initialized"""
        stats = orchestrator_dry_run.stats

        assert stats['start_time'] is None
        assert stats['iterations'] == 0
        assert stats['signals_generated'] == 0
        assert stats['orders_placed'] == 0
        assert stats['errors'] == 0


class TestStrategyInstance:
    """Test StrategyInstance dataclass"""

    def test_strategy_instance_creation(self):
        """Test creating strategy instance"""
        instance = StrategyInstance(
            strategy=None,
            subaccount_id=1,
            symbol='BTC',
            timeframe='15m'
        )

        assert instance.subaccount_id == 1
        assert instance.symbol == 'BTC'
        assert instance.timeframe == '15m'
        assert instance.active is True

    def test_strategy_instance_inactive(self):
        """Test creating inactive strategy instance"""
        instance = StrategyInstance(
            strategy=None,
            subaccount_id=1,
            symbol='BTC',
            timeframe='15m',
            active=False
        )

        assert instance.active is False


class TestLoadStrategies:
    """Test strategy loading from database"""

    @patch('src.orchestration.orchestrator.get_session')
    def test_load_strategies_empty(self, mock_session, config):
        """Test loading strategies when database is empty"""
        # Mock database session
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = []
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query

        with patch('src.orchestration.orchestrator.HyperliquidClient'):
            orch = Orchestrator(config, dry_run=True)
            orch.load_strategies()

        assert len(orch.strategies) == 0

    @patch('src.orchestration.orchestrator.get_session')
    def test_load_strategies_with_data(self, mock_session, config):
        """Test loading strategies from database"""
        # Mock strategy model with all required attributes
        mock_strat = MagicMock()
        mock_strat.name = 'Strategy_MOM_abc123'
        mock_strat.subaccount_id = 1
        mock_strat.symbol = 'BTC'
        mock_strat.timeframe = '15m'
        mock_strat.status = 'LIVE'
        # The orchestrator loads strategy code from DB and writes to temp file
        mock_strat.code = '''
from src.strategies.base import StrategyCore, Signal
import pandas as pd

class Strategy_MOM_abc123(StrategyCore):
    leverage = 5
    indicator_columns = []

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        return None
'''

        # Mock database session
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_strat]
        mock_session.return_value.__enter__.return_value.query.return_value = mock_query

        with patch('src.orchestration.orchestrator.HyperliquidClient'):
            orch = Orchestrator(config, dry_run=True)
            orch.load_strategies()

        assert len(orch.strategies) == 1
        assert orch.strategies[0].symbol == 'BTC'


class TestDataProvider:
    """Test data provider initialization"""

    def test_initialize_data_provider_no_strategies(self, orchestrator_dry_run):
        """Test initializing data provider with no strategies"""
        orchestrator_dry_run.initialize_data_provider()

        assert orchestrator_dry_run.data_provider is not None
        assert len(orchestrator_dry_run.data_provider.symbols) == 0

    def test_initialize_data_provider_with_strategies(self, orchestrator_dry_run):
        """Test initializing data provider with strategies"""
        # Add mock strategies
        orchestrator_dry_run.strategies = [
            StrategyInstance(None, 1, 'BTC', '15m'),
            StrategyInstance(None, 2, 'ETH', '1h'),
            StrategyInstance(None, 3, 'BTC', '1h'),  # Duplicate symbol
        ]

        orchestrator_dry_run.initialize_data_provider()

        provider = orchestrator_dry_run.data_provider
        assert provider is not None
        assert 'BTC' in provider.symbols
        assert 'ETH' in provider.symbols
        assert '15m' in provider.timeframes
        assert '1h' in provider.timeframes


class TestLifecycle:
    """Test orchestrator lifecycle"""

    def test_start_no_strategies(self, orchestrator_dry_run):
        """Test start with no strategies exits gracefully"""
        with patch.object(orchestrator_dry_run, 'load_strategies'):
            orchestrator_dry_run.load_strategies.return_value = None
            orchestrator_dry_run.strategies = []

            orchestrator_dry_run.start()

            assert not orchestrator_dry_run.running

    def test_stop_not_running(self, orchestrator_dry_run):
        """Test stop when not running"""
        orchestrator_dry_run.stop()
        # Should not raise error

    def test_emergency_stop(self, orchestrator_dry_run):
        """Test emergency stop"""
        orchestrator_dry_run.running = True

        with patch.object(orchestrator_dry_run, '_close_all_positions'), \
             patch.object(orchestrator_dry_run, '_cancel_all_orders'):

            orchestrator_dry_run.emergency_stop()

            assert not orchestrator_dry_run.running
            orchestrator_dry_run._close_all_positions.assert_called_once()
            orchestrator_dry_run._cancel_all_orders.assert_called_once()


class TestStatistics:
    """Test statistics collection"""

    def test_get_statistics_initial(self, orchestrator_dry_run):
        """Test initial statistics"""
        stats = orchestrator_dry_run.get_statistics()

        assert stats['running'] is False
        assert stats['dry_run'] is True
        assert stats['runtime_seconds'] is None
        assert stats['active_strategies'] == 0
        assert stats['total_strategies'] == 0
        assert stats['iterations'] == 0

    def test_get_statistics_with_strategies(self, orchestrator_dry_run):
        """Test statistics with active strategies"""
        orchestrator_dry_run.strategies = [
            StrategyInstance(None, 1, 'BTC', '15m', active=True),
            StrategyInstance(None, 2, 'ETH', '1h', active=True),
            StrategyInstance(None, 3, 'SOL', '15m', active=False),
        ]

        stats = orchestrator_dry_run.get_statistics()

        assert stats['active_strategies'] == 2
        assert stats['total_strategies'] == 3

    def test_get_statistics_runtime(self, orchestrator_dry_run):
        """Test runtime calculation in statistics"""
        from datetime import datetime, timedelta

        orchestrator_dry_run.stats['start_time'] = datetime.now() - timedelta(seconds=60)

        stats = orchestrator_dry_run.get_statistics()

        assert stats['runtime_seconds'] is not None
        assert stats['runtime_seconds'] >= 60


class TestDryRunSafety:
    """Test dry-run mode safety"""

    def test_dry_run_flag_set(self, orchestrator_dry_run):
        """Test dry_run flag is set"""
        assert orchestrator_dry_run.dry_run is True

    def test_dry_run_passed_to_client(self, config):
        """Test dry_run is passed to all components"""
        with patch('src.orchestration.orchestrator.HyperliquidClient') as mock_client, \
             patch('src.orchestration.orchestrator.PositionTracker') as mock_tracker, \
             patch('src.orchestration.orchestrator.SubaccountManager') as mock_manager, \
             patch('src.orchestration.orchestrator.get_session'):

            orch = Orchestrator(config, dry_run=True)

            # Verify dry_run passed to components
            mock_client.assert_called_once()
            assert mock_client.call_args[1]['dry_run'] is True

            # PositionTracker doesn't accept dry_run, just client
            mock_tracker.assert_called_once()
            assert 'client' in mock_tracker.call_args[1]

            # SubaccountManager accepts dry_run
            mock_manager.assert_called_once()
            assert mock_manager.call_args[1]['dry_run'] is True

    def test_live_mode_flag(self, orchestrator_live):
        """Test live mode flag is set"""
        assert orchestrator_live.dry_run is False


class TestSignalHandling:
    """Test signal handling for graceful shutdown"""

    def test_signal_handler_sets_shutdown(self, orchestrator_dry_run):
        """Test signal handler sets shutdown flag"""
        import signal

        orchestrator_dry_run._signal_handler(signal.SIGINT, None)

        assert orchestrator_dry_run.shutdown_requested is True

    def test_signal_handler_sigterm(self, orchestrator_dry_run):
        """Test SIGTERM signal handling"""
        import signal

        orchestrator_dry_run._signal_handler(signal.SIGTERM, None)

        assert orchestrator_dry_run.shutdown_requested is True


class TestShutdownBehavior:
    """Test shutdown behavior based on config"""

    def test_stop_cancel_orders(self, config):
        """Test stop cancels orders if configured"""
        config['deployment']['shutdown']['cancel_orders'] = True

        with patch('src.orchestration.orchestrator.HyperliquidClient'), \
             patch('src.orchestration.orchestrator.get_session'):

            orch = Orchestrator(config, dry_run=True)
            orch.running = True

            with patch.object(orch, '_cancel_all_orders') as mock_cancel:
                orch.stop()
                mock_cancel.assert_called_once()

    def test_stop_close_positions(self, config):
        """Test stop closes positions if configured"""
        config['deployment']['shutdown']['close_positions'] = True

        with patch('src.orchestration.orchestrator.HyperliquidClient'), \
             patch('src.orchestration.orchestrator.get_session'):

            orch = Orchestrator(config, dry_run=True)
            orch.running = True

            with patch.object(orch, '_close_all_positions') as mock_close:
                orch.stop()
                mock_close.assert_called_once()

    def test_stop_no_close_positions(self, config):
        """Test stop doesn't close positions if configured"""
        config['deployment']['shutdown']['close_positions'] = False

        with patch('src.orchestration.orchestrator.HyperliquidClient'), \
             patch('src.orchestration.orchestrator.get_session'):

            orch = Orchestrator(config, dry_run=True)
            orch.running = True

            with patch.object(orch, '_close_all_positions') as mock_close:
                orch.stop()
                mock_close.assert_not_called()


class TestExecutionMode:
    """Test execution mode determination"""

    def test_execution_mode_determined(self, orchestrator_dry_run):
        """Test execution mode is determined from strategy count"""
        orchestrator_dry_run.strategies = [
            StrategyInstance(None, i, 'BTC', '15m')
            for i in range(25)
        ]

        mode = orchestrator_dry_run.scheduler.determine_mode(len(orchestrator_dry_run.strategies))

        assert mode == 'sync'  # 25 strategies → sync mode
