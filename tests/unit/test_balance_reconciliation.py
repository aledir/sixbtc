"""
Unit tests for BalanceReconciliationService.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, patch, MagicMock

from src.executor.balance_reconciliation import BalanceReconciliationService


class TestBalanceReconciliationService:
    """Tests for BalanceReconciliationService."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Hyperliquid client."""
        client = Mock()
        client._subaccount_credentials = {1: {'address': '0x123'}, 2: {'address': '0x456'}}
        client.get_ledger_updates.return_value = []
        return client

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock data provider."""
        dp = Mock()
        dp.set_ledger_callback = Mock()
        return dp

    @pytest.fixture
    def config(self):
        """Create test config."""
        return {
            'hyperliquid': {
                'balance_reconciliation': {
                    'enabled': True,
                    'catchup_lookback_days': 7,
                }
            }
        }

    @pytest.fixture
    def service(self, mock_client, config):
        """Create BalanceReconciliationService with mock client."""
        return BalanceReconciliationService(
            client=mock_client,
            data_provider=None,
            config=config
        )

    @pytest.fixture
    def service_with_dp(self, mock_client, mock_data_provider, config):
        """Create BalanceReconciliationService with data provider."""
        return BalanceReconciliationService(
            client=mock_client,
            data_provider=mock_data_provider,
            config=config
        )

    # =========================================================================
    # Test 1: startup_catchup processes events
    # =========================================================================
    @pytest.mark.asyncio
    async def test_startup_catchup_processes_events(self, mock_client, config):
        """Test that startup_catchup processes ledger events."""
        # Mock ledger updates
        mock_client.get_ledger_updates.return_value = [
            {
                'hash': 'tx_001',
                'type': 'deposit',
                'amount': 100.0,
                'direction': 'in',
                'timestamp': 1700000000000
            },
            {
                'hash': 'tx_002',
                'type': 'deposit',
                'amount': 50.0,
                'direction': 'in',
                'timestamp': 1700001000000
            }
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            processed = await service.startup_catchup()

            # Should process 2 events
            assert processed == 2
            # allocated_capital should be updated
            assert mock_subaccount.allocated_capital == 150.0

    # =========================================================================
    # Test 2: startup_catchup skips duplicates
    # =========================================================================
    @pytest.mark.asyncio
    async def test_startup_catchup_skips_duplicates(self, mock_client, config):
        """Test that duplicate transaction hashes are skipped."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000},
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000},
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            processed = await service.startup_catchup()

            # Only 1 event processed (duplicate skipped)
            assert processed == 1
            assert mock_subaccount.allocated_capital == 100.0

    # =========================================================================
    # Test 3: deposit increases allocated_capital
    # =========================================================================
    @pytest.mark.asyncio
    async def test_deposit_increases_allocated_capital(self, mock_client, config):
        """Test that deposit events increase allocated_capital."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 50.0  # Pre-existing
        mock_subaccount.peak_balance = 50.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # 50 + 100 = 150
            assert mock_subaccount.allocated_capital == 150.0

    # =========================================================================
    # Test 4: withdrawal decreases allocated_capital
    # =========================================================================
    @pytest.mark.asyncio
    async def test_withdrawal_decreases_allocated_capital(self, mock_client, config):
        """Test that withdrawal events decrease allocated_capital."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000},
            {'hash': 'tx_002', 'type': 'withdraw', 'amount': 30.0, 'direction': 'out', 'timestamp': 1700001000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # 0 + 100 - 30 = 70
            assert mock_subaccount.allocated_capital == 70.0

    # =========================================================================
    # Test 5: transfer IN increases capital
    # =========================================================================
    @pytest.mark.asyncio
    async def test_transfer_in_increases_capital(self, mock_client, config):
        """Test that transfer IN events increase allocated_capital."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'internalTransfer', 'amount': 200.0, 'direction': 'in', 'timestamp': 1700000000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            assert mock_subaccount.allocated_capital == 200.0

    # =========================================================================
    # Test 6: transfer OUT decreases capital
    # =========================================================================
    @pytest.mark.asyncio
    async def test_transfer_out_decreases_capital(self, mock_client, config):
        """Test that transfer OUT events decrease allocated_capital."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000},
            {'hash': 'tx_002', 'type': 'subAccountTransfer', 'amount': 40.0, 'direction': 'out', 'timestamp': 1700001000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # 100 - 40 = 60
            assert mock_subaccount.allocated_capital == 60.0

    # =========================================================================
    # Test 7: adjustment never goes negative
    # =========================================================================
    @pytest.mark.asyncio
    async def test_adjustment_never_goes_negative(self, mock_client, config):
        """Test that allocated_capital never goes below 0."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 50.0, 'direction': 'in', 'timestamp': 1700000000000},
            {'hash': 'tx_002', 'type': 'withdraw', 'amount': 100.0, 'direction': 'out', 'timestamp': 1700001000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # 50 - 100 = -50, but clamped to 0
            assert mock_subaccount.allocated_capital == 0

    # =========================================================================
    # Test 8: deposit updates peak_balance
    # =========================================================================
    @pytest.mark.asyncio
    async def test_deposit_updates_peak_balance(self, mock_client, config):
        """Test that deposit updates peak_balance if it becomes higher."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 200.0, 'direction': 'in', 'timestamp': 1700000000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.peak_balance = 100.0
        mock_subaccount.peak_balance_updated_at = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # allocated_capital = 100 + 200 = 300
            assert mock_subaccount.allocated_capital == 300.0
            # peak_balance should be updated since 300 > 100
            assert mock_subaccount.peak_balance == 300.0

    # =========================================================================
    # Test 9: real-time callback processes update
    # =========================================================================
    def test_real_time_callback_processes_update(self, service_with_dp, mock_client):
        """Test that WebSocket callback processes ledger updates."""
        # Create mock LedgerUpdate
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class MockLedgerUpdate:
            timestamp: datetime
            update_type: str
            amount: float
            direction: str
            hash: str
            raw_data: dict

        update = MockLedgerUpdate(
            timestamp=datetime.now(UTC),
            update_type='deposit',
            amount=100.0,
            direction='in',
            hash='tx_realtime_001',
            raw_data={'delta': {'destination': '0x123'}}
        )

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 50.0
        mock_subaccount.peak_balance = 50.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service_with_dp._on_ledger_update(update)

            # Should increase allocated_capital
            assert mock_subaccount.allocated_capital == 150.0

    # =========================================================================
    # Test 10: resolve subaccount from address
    # =========================================================================
    def test_resolve_subaccount_from_address(self, service, mock_client):
        """Test that subaccount is resolved from destination address."""
        from dataclasses import dataclass
        from datetime import datetime

        @dataclass
        class MockLedgerUpdate:
            timestamp: datetime
            update_type: str
            amount: float
            direction: str
            hash: str
            raw_data: dict

        # Test with address matching subaccount 2
        update = MockLedgerUpdate(
            timestamp=datetime.now(UTC),
            update_type='deposit',
            amount=100.0,
            direction='in',
            hash='tx_001',
            raw_data={'delta': {'destination': '0x456'}}  # Matches subaccount 2
        )

        sub_id = service._resolve_subaccount_id(update)
        assert sub_id == 2

    # =========================================================================
    # Test 11: handles unknown event type
    # =========================================================================
    @pytest.mark.asyncio
    async def test_handles_unknown_event_type(self, mock_client, config):
        """Test that unknown event types are handled gracefully."""
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 100.0, 'direction': 'in', 'timestamp': 1700000000000},
            {'hash': 'tx_002', 'type': 'unknown_type', 'amount': 50.0, 'direction': 'unknown', 'timestamp': 1700001000000}
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service = BalanceReconciliationService(mock_client, None, config)
            # Should not raise
            processed = await service.startup_catchup()

            # Only first event processed (unknown direction skipped)
            assert processed == 1
            assert mock_subaccount.allocated_capital == 100.0

    # =========================================================================
    # Test 12: handles API error gracefully
    # =========================================================================
    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self, mock_client, config):
        """Test that API errors don't crash the service."""
        mock_client.get_ledger_updates.side_effect = RuntimeError("API error")

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            # Should not raise
            processed = await service.startup_catchup()

            # No events processed (error caught)
            assert processed == 0

    # =========================================================================
    # Test 13: CRITICAL - zero allocated if no deposits
    # =========================================================================
    @pytest.mark.asyncio
    async def test_zero_allocated_if_no_deposits(self, mock_client, config):
        """
        CRITICAL TEST: If allocated_capital > 0 but no deposit events found,
        zero out allocated_capital (phantom capital detection).
        """
        # No deposit events in ledger
        mock_client.get_ledger_updates.return_value = []

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 83.33  # Phantom capital
        mock_subaccount.current_balance = 0  # Never actually funded

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # CRITICAL: allocated_capital should be zeroed
            assert mock_subaccount.allocated_capital == 0
            assert mock_subaccount.current_balance == 0

    # =========================================================================
    # Test 14: disabled service skips catchup
    # =========================================================================
    @pytest.mark.asyncio
    async def test_disabled_service_skips_catchup(self, mock_client):
        """Test that disabled service skips catchup."""
        config = {
            'hyperliquid': {
                'balance_reconciliation': {
                    'enabled': False,
                }
            }
        }

        service = BalanceReconciliationService(mock_client, None, config)
        processed = await service.startup_catchup()

        assert processed == 0
        mock_client.get_ledger_updates.assert_not_called()

    # =========================================================================
    # Test 15: get_reconciliation_status returns correct data
    # =========================================================================
    def test_get_reconciliation_status(self, service):
        """Test that get_reconciliation_status returns correct data."""
        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.current_balance = 95.0
        mock_subaccount.peak_balance = 100.0
        mock_subaccount.status = 'ACTIVE'

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            status = service.get_reconciliation_status()

            assert status['enabled'] is True
            assert 1 in status['subaccounts']
            assert status['subaccounts'][1]['allocated_capital'] == 100.0
            assert status['subaccounts'][1]['current_balance'] == 95.0
