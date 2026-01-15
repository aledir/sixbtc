"""
Unit tests for BalanceSyncService.
"""

import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, patch, MagicMock

from src.executor.balance_sync import BalanceSyncService


class TestBalanceSyncService:
    """Tests for BalanceSyncService."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Hyperliquid client."""
        client = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create BalanceSyncService with mock client."""
        config = {}
        return BalanceSyncService(config, mock_client)

    def test_sync_initializes_allocated_capital_when_zero(self, service, mock_client):
        """Test that allocated_capital is set from HL when it's 0."""
        # Setup mock
        mock_client.get_account_balance.return_value = 100.0

        # Mock subaccount with allocated_capital = 0
        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0
        mock_subaccount.current_balance = None
        mock_subaccount.peak_balance = None

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            result = service.sync_all_subaccounts()

            # Verify allocated_capital and current_balance were set
            assert mock_subaccount.allocated_capital == 100.0
            assert mock_subaccount.current_balance == 100.0
            # Note: peak_balance is NOT set by balance_sync (set by deployer)
            # This is by design to prevent false emergency stops
            assert 1 in result
            assert result[1] == 100.0

    def test_sync_does_not_overwrite_existing_allocated_capital(self, service, mock_client):
        """Test that existing allocated_capital is preserved."""
        mock_client.get_account_balance.return_value = 150.0

        # Mock subaccount with existing allocated_capital
        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0  # Already set
        mock_subaccount.current_balance = 90.0
        mock_subaccount.peak_balance = 100.0
        mock_subaccount.peak_balance_updated_at = None

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            result = service.sync_all_subaccounts()

            # allocated_capital should NOT change
            assert mock_subaccount.allocated_capital == 100.0
            # current_balance SHOULD update
            assert mock_subaccount.current_balance == 150.0
            assert 1 in result

    def test_sync_skips_unfunded_subaccounts(self, service, mock_client):
        """Test that subaccounts with 0 balance on HL are skipped."""
        mock_client.get_account_balance.return_value = 0.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = None
        mock_subaccount.current_balance = None

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            result = service.sync_all_subaccounts()

            # Should not be in results (skipped)
            assert 1 not in result
            # allocated_capital should remain None
            assert mock_subaccount.allocated_capital is None

    def test_sync_handles_api_errors_gracefully(self, service, mock_client):
        """Test that API errors don't crash the sync."""
        mock_client.get_account_balance.side_effect = RuntimeError("API error")

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            # Should not raise
            result = service.sync_all_subaccounts()

            # Should return empty result (error handled)
            assert result == {}

    def test_sync_handles_unconfigured_subaccount(self, service, mock_client):
        """Test handling of subaccounts not configured in Hyperliquid."""
        mock_client.get_account_balance.side_effect = ValueError("Not configured")

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            result = service.sync_all_subaccounts()

            # Should return empty (subaccount not configured)
            assert result == {}

    def test_sync_does_not_initialize_peak_balance(self, service, mock_client):
        """Test that peak_balance is NOT initialized by balance_sync.

        This is intentional: peak_balance must be set by deployer (from allocated_capital)
        to prevent false emergency stops. Balance_sync only updates timestamp when
        peak_balance is already set.

        See: Root cause analysis of EmergencyStopState bug.
        """
        mock_client.get_account_balance.return_value = 100.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.current_balance = 90.0
        mock_subaccount.peak_balance = None  # Not set yet
        mock_subaccount.peak_balance_updated_at = None

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            service.sync_all_subaccounts()

            # peak_balance should NOT be initialized by balance_sync
            # It must be set by deployer when assigning strategy
            assert mock_subaccount.peak_balance is None
            assert mock_subaccount.peak_balance_updated_at is None

    def test_sync_multiple_subaccounts(self, service, mock_client):
        """Test syncing multiple subaccounts."""
        def get_balance(sub_id):
            balances = {1: 100.0, 2: 150.0, 3: 0.0}  # Sub 3 is unfunded
            return balances.get(sub_id, 0.0)

        mock_client.get_account_balance.side_effect = get_balance

        subaccounts = []
        for i in range(1, 4):
            sa = Mock()
            sa.id = i
            sa.allocated_capital = 0
            sa.current_balance = None
            sa.peak_balance = None
            subaccounts.append(sa)

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = subaccounts

            result = service.sync_all_subaccounts()

            # Sub 1 and 2 synced, sub 3 skipped (unfunded)
            assert 1 in result
            assert 2 in result
            assert 3 not in result
            assert result[1] == 100.0
            assert result[2] == 150.0

    def test_force_sync_overwrites_allocated_capital(self, service, mock_client):
        """Test that force_sync overwrites existing allocated_capital."""
        mock_client.get_account_balance.return_value = 200.0

        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0  # Will be overwritten
        mock_subaccount.current_balance = 100.0
        mock_subaccount.peak_balance = 100.0

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.filter.return_value.first.return_value = mock_subaccount

            result = service.force_sync_allocated(1)

            # allocated_capital SHOULD be overwritten
            assert mock_subaccount.allocated_capital == 200.0
            assert mock_subaccount.current_balance == 200.0
            assert result == 200.0

    def test_force_sync_fails_on_zero_balance(self, service, mock_client):
        """Test that force_sync returns None if HL balance is 0."""
        mock_client.get_account_balance.return_value = 0.0

        result = service.force_sync_allocated(1)

        assert result is None

    def test_get_sync_status(self, service):
        """Test getting sync status for all subaccounts."""
        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 100.0
        mock_subaccount.current_balance = 95.0
        mock_subaccount.peak_balance = 100.0
        mock_subaccount.peak_balance_updated_at = datetime.now(UTC)
        mock_subaccount.status = 'ACTIVE'

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            status = service.get_sync_status()

            assert 1 in status
            assert status[1]['allocated_capital'] == 100.0
            assert status[1]['current_balance'] == 95.0
            assert status[1]['needs_sync'] is False

    def test_get_sync_status_identifies_needs_sync(self, service):
        """Test that get_sync_status identifies subaccounts needing sync."""
        mock_subaccount = Mock()
        mock_subaccount.id = 1
        mock_subaccount.allocated_capital = 0  # Needs sync
        mock_subaccount.current_balance = None
        mock_subaccount.peak_balance = None
        mock_subaccount.peak_balance_updated_at = None
        mock_subaccount.status = 'PAUSED'

        with patch('src.executor.balance_sync.get_session') as mock_session:
            session_instance = MagicMock()
            mock_session.return_value.__enter__.return_value = session_instance
            session_instance.query.return_value.all.return_value = [mock_subaccount]

            status = service.get_sync_status()

            assert status[1]['needs_sync'] is True
