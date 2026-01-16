"""
Integration tests for BalanceReconciliationService with real PostgreSQL.

These tests verify:
1. Full deposit reconciliation cycle
2. WebSocket and HTTP consistency
3. Recovery after restart

Each test runs in a transaction that is rolled back at the end.
"""
import pytest
import uuid
from datetime import datetime, UTC
from unittest.mock import Mock, patch

from src.database.connection import get_session, get_session_factory
from src.database.models import Subaccount
from src.executor.balance_reconciliation import BalanceReconciliationService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """
    Provide a database session that rolls back after each test.

    This ensures tests don't persist data in the real database.
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_client():
    """Create mock Hyperliquid client."""
    client = Mock()
    client._subaccount_credentials = {1: {'address': '0x123abc'}}
    client.get_ledger_updates.return_value = []
    return client


@pytest.fixture
def config():
    """Create test config."""
    return {
        'hyperliquid': {
            'balance_reconciliation': {
                'enabled': True,
                'catchup_lookback_days': 7,
            }
        }
    }


# =============================================================================
# TEST 1: Full Cycle Deposit Reconciliation
# =============================================================================

class TestFullCycleDepositReconciliation:
    """Test full deposit reconciliation cycle with real DB."""

    @pytest.mark.asyncio
    async def test_full_cycle_deposit_reconciliation(self, db_session, mock_client, config):
        """
        Test complete deposit reconciliation flow:
        1. Create subaccount with allocated_capital = 0
        2. Mock ledger with deposit event
        3. Run startup_catchup
        4. Verify allocated_capital updated in DB
        """
        # Create subaccount in DB
        subaccount = Subaccount(
            id=99,  # Use high ID to avoid conflicts
            status='ACTIVE',
            allocated_capital=0,
            current_balance=0,
            peak_balance=None
        )
        db_session.add(subaccount)
        db_session.flush()

        # Mock ledger updates
        mock_client._subaccount_credentials = {99: {'address': '0xtest99'}}
        mock_client.get_ledger_updates.return_value = [
            {
                'hash': 'tx_integration_001',
                'type': 'deposit',
                'amount': 250.0,
                'direction': 'in',
                'timestamp': 1700000000000
            }
        ]

        # Patch get_session to use our test session
        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            processed = await service.startup_catchup()

            # Verify
            assert processed == 1

            # Refresh from DB
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 250.0
            assert subaccount.peak_balance == 250.0


# =============================================================================
# TEST 2: WebSocket and HTTP Consistency
# =============================================================================

class TestWebSocketHttpConsistency:
    """Test that WebSocket and HTTP produce consistent results."""

    @pytest.mark.asyncio
    async def test_websocket_and_http_consistency(self, db_session, mock_client, config):
        """
        Test that HTTP catchup and WebSocket real-time produce same result.
        """
        # Create subaccount
        subaccount = Subaccount(
            id=98,
            status='ACTIVE',
            allocated_capital=100.0,
            current_balance=100.0,
            peak_balance=100.0
        )
        db_session.add(subaccount)
        db_session.flush()

        mock_client._subaccount_credentials = {98: {'address': '0xtest98'}}

        # Same event via HTTP
        mock_client.get_ledger_updates.return_value = [
            {
                'hash': 'tx_consistency_001',
                'type': 'deposit',
                'amount': 50.0,
                'direction': 'in',
                'timestamp': 1700000000000
            }
        ]

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # HTTP result: 100 + 50 = 150
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 150.0

            # Now simulate same event via WebSocket (should be skipped as duplicate)
            from dataclasses import dataclass

            @dataclass
            class MockLedgerUpdate:
                timestamp: datetime
                update_type: str
                amount: float
                direction: str
                hash: str
                raw_data: dict

            ws_update = MockLedgerUpdate(
                timestamp=datetime.now(UTC),
                update_type='deposit',
                amount=50.0,
                direction='in',
                hash='tx_consistency_001',  # Same hash
                raw_data={'delta': {'destination': '0xtest98'}}
            )

            service._on_ledger_update(ws_update)

            # Should still be 150 (duplicate skipped)
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 150.0


# =============================================================================
# TEST 3: Recovery After Restart
# =============================================================================

class TestRecoveryAfterRestart:
    """Test recovery of missed events after system restart."""

    @pytest.mark.asyncio
    async def test_recovery_after_restart(self, db_session, mock_client, config):
        """
        Simulate events missed during downtime and recovered at startup.
        """
        # Create subaccount that was active before shutdown
        subaccount = Subaccount(
            id=97,
            status='ACTIVE',
            allocated_capital=500.0,
            current_balance=500.0,
            peak_balance=500.0
        )
        db_session.add(subaccount)
        db_session.flush()

        mock_client._subaccount_credentials = {97: {'address': '0xtest97'}}

        # Events that happened during downtime
        mock_client.get_ledger_updates.return_value = [
            {
                'hash': 'tx_recovery_001',
                'type': 'deposit',
                'amount': 100.0,
                'direction': 'in',
                'timestamp': 1700000000000
            },
            {
                'hash': 'tx_recovery_002',
                'type': 'withdraw',
                'amount': 30.0,
                'direction': 'out',
                'timestamp': 1700001000000
            },
            {
                'hash': 'tx_recovery_003',
                'type': 'deposit',
                'amount': 50.0,
                'direction': 'in',
                'timestamp': 1700002000000
            }
        ]

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            processed = await service.startup_catchup()

            # All 3 events processed
            assert processed == 3

            # Verify final balance: 500 + 100 - 30 + 50 = 620
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 620.0
            assert subaccount.peak_balance == 620.0


# =============================================================================
# TEST 4: Phantom Capital Detection Integration
# =============================================================================

class TestPhantomCapitalDetection:
    """Test phantom capital detection with real DB."""

    @pytest.mark.asyncio
    async def test_phantom_capital_zeroed(self, db_session, mock_client, config):
        """
        Test that phantom capital is detected and zeroed.
        Subaccount has allocated_capital but no deposit events.
        """
        # Create subaccount with phantom capital
        subaccount = Subaccount(
            id=96,
            status='ACTIVE',
            allocated_capital=83.33,  # Set by Deployer but never funded
            current_balance=0,
            peak_balance=83.33
        )
        db_session.add(subaccount)
        db_session.flush()

        mock_client._subaccount_credentials = {96: {'address': '0xtest96'}}

        # No deposit events found
        mock_client.get_ledger_updates.return_value = []

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            await service.startup_catchup()

            # Phantom capital should be zeroed
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 0
            assert subaccount.current_balance == 0
