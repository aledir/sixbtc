"""
Unit tests for BalanceReconciliationService.

The service ensures allocated_capital = actual_balance to prevent false DD alerts.
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
        client.get_account_balance.return_value = 100.0
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

    # =========================================================================
    # Test 1: Phantom capital is zeroed out
    # =========================================================================
    @pytest.mark.asyncio
    async def test_phantom_capital_zeroed(self, mock_client, config):
        """
        Test that phantom capital (allocated > 0 but balance = 0) is zeroed.
        """
        mock_client.get_account_balance.return_value = 0.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 500.0  # Phantom!
        mock_subaccount.current_balance = 0.0
        mock_subaccount.peak_balance = 500.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 1
            assert mock_subaccount.allocated_capital == 0
            assert mock_subaccount.peak_balance == 0

    # =========================================================================
    # Test 2: Mismatch (allocated > balance) is corrected
    # =========================================================================
    @pytest.mark.asyncio
    async def test_mismatch_corrected(self, mock_client, config):
        """
        Test that allocated > balance mismatch is corrected.
        """
        mock_client.get_account_balance.return_value = 100.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 300.0  # Wrong - should be 100
        mock_subaccount.current_balance = 100.0
        mock_subaccount.peak_balance = 300.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 1
            assert mock_subaccount.allocated_capital == 100.0
            assert mock_subaccount.current_balance == 100.0

    # =========================================================================
    # Test 3: Correct state is not changed
    # =========================================================================
    @pytest.mark.asyncio
    async def test_correct_state_unchanged(self, mock_client, config):
        """
        Test that correct state (allocated ~= balance) is not modified.
        """
        mock_client.get_account_balance.return_value = 100.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.5  # Close enough (< $1 diff)
        mock_subaccount.current_balance = 100.0
        mock_subaccount.peak_balance = 100.5

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            # Should not fix (diff < $1)
            assert fixed == 0
            assert mock_subaccount.allocated_capital == 100.5

    # =========================================================================
    # Test 4: Current balance is updated from Hyperliquid
    # =========================================================================
    @pytest.mark.asyncio
    async def test_current_balance_updated(self, mock_client, config):
        """
        Test that current_balance is always updated from Hyperliquid.
        """
        mock_client.get_account_balance.return_value = 150.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.current_balance = 90.0  # Stale
        mock_subaccount.peak_balance = 100.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # current_balance always updated
            assert mock_subaccount.current_balance == 150.0

    # =========================================================================
    # Test 5: Peak balance is updated if needed
    # =========================================================================
    @pytest.mark.asyncio
    async def test_peak_balance_updated(self, mock_client, config):
        """
        Test that peak_balance is updated when allocated increases.
        """
        mock_client.get_account_balance.return_value = 200.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0  # Will be updated to 200
        mock_subaccount.current_balance = 100.0
        mock_subaccount.peak_balance = 100.0  # Should be updated to 200
        mock_subaccount.peak_balance_updated_at = None

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            assert mock_subaccount.peak_balance == 200.0

    # =========================================================================
    # Test 6: Disabled service skips reconciliation
    # =========================================================================
    @pytest.mark.asyncio
    async def test_disabled_service_skips(self, mock_client):
        """
        Test that disabled service skips reconciliation.
        """
        config = {
            'hyperliquid': {
                'balance_reconciliation': {
                    'enabled': False,
                }
            }
        }

        service = BalanceReconciliationService(mock_client, None, config)
        fixed = await service.startup_catchup()

        assert fixed == 0
        mock_client.get_account_balance.assert_not_called()

    # =========================================================================
    # Test 7: API errors handled gracefully
    # =========================================================================
    @pytest.mark.asyncio
    async def test_api_error_handled(self, mock_client, config):
        """
        Test that API errors don't crash the service.
        """
        mock_client.get_account_balance.side_effect = RuntimeError("API error")

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            # Should not raise
            fixed = await service.startup_catchup()

            assert fixed == 0

    # =========================================================================
    # Test 8: Subaccounts without credentials skipped
    # =========================================================================
    @pytest.mark.asyncio
    async def test_unconfigured_subaccounts_skipped(self, mock_client, config):
        """
        Test that subaccounts without credentials are skipped.
        """
        mock_client._subaccount_credentials = {1: {'address': '0x123'}}
        mock_client.get_account_balance.return_value = 100.0

        mock_sub1 = Mock()
        mock_sub1.id = 1
        mock_sub1.allocated_capital = 100.0
        mock_sub1.current_balance = 100.0
        mock_sub1.peak_balance = 100.0

        mock_sub2 = Mock()
        mock_sub2.id = 2  # Not in credentials
        mock_sub2.allocated_capital = 500.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_sub1, mock_sub2]

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # Sub 2 should be skipped (no credentials)
            # Sub 1 is correct, so no changes
            assert mock_sub2.allocated_capital == 500.0  # Unchanged

    # =========================================================================
    # Test 9: Multiple subaccounts processed
    # =========================================================================
    @pytest.mark.asyncio
    async def test_multiple_subaccounts(self, mock_client, config):
        """
        Test that multiple subaccounts are processed correctly.
        """
        def get_balance(sub_id):
            return {1: 100.0, 2: 0.0}[sub_id]

        mock_client.get_account_balance.side_effect = get_balance

        mock_sub1 = Mock()
        mock_sub1.id = 1
        mock_sub1.allocated_capital = 200.0  # Mismatch
        mock_sub1.current_balance = 100.0
        mock_sub1.peak_balance = 200.0

        mock_sub2 = Mock()
        mock_sub2.id = 2
        mock_sub2.allocated_capital = 300.0  # Phantom
        mock_sub2.current_balance = 0.0
        mock_sub2.peak_balance = 300.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_sub1, mock_sub2]

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 2
            assert mock_sub1.allocated_capital == 100.0
            assert mock_sub2.allocated_capital == 0.0

    # =========================================================================
    # Test 10: Real-time callback processes update
    # =========================================================================
    def test_realtime_callback_processes_update(self, mock_client, mock_data_provider, config):
        """
        Test that WebSocket callback processes ledger updates.
        """
        from dataclasses import dataclass

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

        service = BalanceReconciliationService(mock_client, mock_data_provider, config)

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            service._on_ledger_update(update)

            # Deposit should increase allocated_capital
            assert mock_subaccount.allocated_capital == 150.0

    # =========================================================================
    # Test 11: Ledger hashes tracked for deduplication
    # =========================================================================
    @pytest.mark.asyncio
    async def test_ledger_hashes_tracked(self, mock_client, config):
        """
        Test that ledger hashes are tracked for real-time deduplication.
        """
        mock_client.get_account_balance.return_value = 100.0
        mock_client.get_ledger_updates.return_value = [
            {'hash': 'tx_001', 'type': 'deposit', 'amount': 50.0, 'direction': 'in'},
            {'hash': 'tx_002', 'type': 'deposit', 'amount': 50.0, 'direction': 'in'},
        ]

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.current_balance = 100.0
        mock_subaccount.peak_balance = 100.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # Hashes should be tracked
            assert 'tx_001' in service._processed_hashes
            assert 'tx_002' in service._processed_hashes

    # =========================================================================
    # Test 12: Get reconciliation status
    # =========================================================================
    def test_get_reconciliation_status(self, service):
        """
        Test that get_reconciliation_status returns correct data.
        """
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
