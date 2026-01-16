"""
Integration tests for BalanceReconciliationService with real PostgreSQL.

These tests verify:
1. Phantom capital detection and zeroing
2. Mismatch correction (allocated != balance)
3. Multiple subaccounts processed correctly
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, patch

from src.database.connection import get_session_factory
from src.database.models import Subaccount
from src.executor.balance_reconciliation import BalanceReconciliationService


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """
    Provide a database session that rolls back after each test.
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
    client._subaccount_credentials = {}
    client.get_ledger_updates.return_value = []
    client.get_account_balance.return_value = 0.0
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
# TEST 1: Phantom Capital Detection
# =============================================================================

class TestPhantomCapitalDetection:
    """Test phantom capital detection and zeroing."""

    @pytest.mark.asyncio
    async def test_phantom_capital_zeroed(self, db_session, mock_client, config):
        """
        Test that phantom capital is detected and zeroed.
        """
        # Create subaccount with phantom capital
        subaccount = Subaccount(
            id=96,
            status='ACTIVE',
            allocated_capital=500.0,  # Phantom!
            current_balance=0.0,
            peak_balance=500.0
        )
        db_session.add(subaccount)
        db_session.flush()

        # Mock: no balance on Hyperliquid
        mock_client._subaccount_credentials = {96: {'address': '0xtest96'}}
        mock_client.get_account_balance.return_value = 0.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 1
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 0
            assert subaccount.peak_balance == 0


# =============================================================================
# TEST 2: Mismatch Correction
# =============================================================================

class TestMismatchCorrection:
    """Test mismatch correction (allocated != balance)."""

    @pytest.mark.asyncio
    async def test_mismatch_corrected(self, db_session, mock_client, config):
        """
        Test that allocated > balance mismatch is corrected.
        """
        subaccount = Subaccount(
            id=97,
            status='ACTIVE',
            allocated_capital=300.0,  # Too high
            current_balance=100.0,
            peak_balance=300.0
        )
        db_session.add(subaccount)
        db_session.flush()

        mock_client._subaccount_credentials = {97: {'address': '0xtest97'}}
        mock_client.get_account_balance.return_value = 100.0  # Actual balance

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 1
            db_session.refresh(subaccount)
            assert subaccount.allocated_capital == 100.0
            assert subaccount.current_balance == 100.0


# =============================================================================
# TEST 3: Multiple Subaccounts
# =============================================================================

class TestMultipleSubaccounts:
    """Test processing multiple subaccounts."""

    @pytest.mark.asyncio
    async def test_multiple_subaccounts_fixed(self, db_session, mock_client, config):
        """
        Test that multiple subaccounts are processed correctly.
        """
        # Phantom capital
        sub1 = Subaccount(
            id=94,
            status='ACTIVE',
            allocated_capital=200.0,
            current_balance=0.0,
            peak_balance=200.0
        )
        # Mismatch
        sub2 = Subaccount(
            id=95,
            status='ACTIVE',
            allocated_capital=300.0,
            current_balance=150.0,
            peak_balance=300.0
        )

        db_session.add_all([sub1, sub2])
        db_session.flush()

        mock_client._subaccount_credentials = {
            94: {'address': '0xtest94'},
            95: {'address': '0xtest95'}
        }

        def get_balance(sub_id):
            return {94: 0.0, 95: 150.0}[sub_id]

        mock_client.get_account_balance.side_effect = get_balance

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            assert fixed == 2

            db_session.refresh(sub1)
            db_session.refresh(sub2)

            assert sub1.allocated_capital == 0  # Phantom zeroed
            assert sub2.allocated_capital == 150.0  # Mismatch corrected


# =============================================================================
# TEST 4: Correct State Not Changed
# =============================================================================

class TestCorrectStatePreserved:
    """Test that correct state is not changed."""

    @pytest.mark.asyncio
    async def test_correct_state_unchanged(self, db_session, mock_client, config):
        """
        Test that subaccounts with correct state are not modified.
        """
        subaccount = Subaccount(
            id=93,
            status='ACTIVE',
            allocated_capital=100.0,
            current_balance=100.0,
            peak_balance=100.0
        )
        db_session.add(subaccount)
        db_session.flush()

        mock_client._subaccount_credentials = {93: {'address': '0xtest93'}}
        mock_client.get_account_balance.return_value = 100.0

        with patch('src.executor.balance_reconciliation.get_session') as mock_get_session:
            mock_get_session.return_value.__enter__ = Mock(return_value=db_session)
            mock_get_session.return_value.__exit__ = Mock(return_value=None)

            service = BalanceReconciliationService(mock_client, None, config)
            fixed = await service.startup_catchup()

            # No fix needed (diff < $1)
            assert fixed == 0
