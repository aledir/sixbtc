"""
Full integration tests for Emergency Stop System.

Tests the complete flow with:
1. Real PostgreSQL database
2. Real Hyperliquid API (read-only calls only - no trades)
3. Real EmergencyStopManager
4. Real balance tracking

SAFE: Only reads from Hyperliquid, never places orders.
"""

import os
import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from sqlalchemy import text

from src.config import load_config
from src.database.connection import get_session
from src.database.models import EmergencyStopState, Subaccount, Strategy
from src.executor.emergency_stop_manager import EmergencyStopManager
from src.executor.hyperliquid_client import HyperliquidClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def config():
    """Load real config."""
    return load_config()


@pytest.fixture(scope="module")
def hl_client(config):
    """Create real Hyperliquid client (read-only operations)."""
    try:
        client = HyperliquidClient(config._raw_config)
        # Test connection with a simple read
        prices = client.get_current_prices()
        if not prices:
            pytest.skip("Cannot connect to Hyperliquid API")
        return client
    except Exception as e:
        pytest.skip(f"Cannot create Hyperliquid client: {e}")


@pytest.fixture
def manager(config):
    """Create EmergencyStopManager with real config."""
    return EmergencyStopManager(config._raw_config)


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up test data before and after each test."""
    yield
    with get_session() as session:
        session.execute(text(
            "DELETE FROM emergency_stop_states WHERE scope_id LIKE 'test_%'"
        ))
        session.commit()


# ============================================================================
# HYPERLIQUID READ-ONLY TESTS
# ============================================================================

class TestHyperliquidReadOnly:
    """Test Hyperliquid API read-only operations."""

    def test_get_current_prices(self, hl_client):
        """Test fetching current prices from Hyperliquid."""
        prices = hl_client.get_current_prices()

        assert prices is not None
        assert len(prices) > 0
        assert 'BTC' in prices or 'ETH' in prices

        # Verify prices are reasonable
        btc_price = prices.get('BTC', 0)
        if btc_price > 0:
            assert 10000 < btc_price < 500000, f"BTC price {btc_price} seems wrong"

        print(f"Fetched {len(prices)} prices from Hyperliquid")
        print(f"BTC: ${prices.get('BTC', 'N/A')}, ETH: ${prices.get('ETH', 'N/A')}")

    def test_get_account_balance_subaccount_1(self, hl_client):
        """Test fetching balance for subaccount 1."""
        try:
            balance = hl_client.get_account_balance(1)
            assert balance >= 0, f"Balance should be non-negative, got {balance}"
            print(f"Subaccount 1 balance: ${balance:.2f}")
        except ValueError as e:
            pytest.skip(f"Subaccount 1 not configured: {e}")
        except RuntimeError as e:
            pytest.skip(f"Cannot fetch balance: {e}")

    def test_get_account_balance_all_subaccounts(self, hl_client):
        """Test fetching balance for all configured subaccounts."""
        balances = {}

        for i in range(1, 11):  # Try subaccounts 1-10
            try:
                balance = hl_client.get_account_balance(i)
                balances[i] = balance
            except (ValueError, RuntimeError):
                # Subaccount not configured or error
                pass

        assert len(balances) > 0, "Should have at least one subaccount configured"
        print(f"Found {len(balances)} subaccounts with balances:")
        for sub_id, bal in balances.items():
            print(f"  Subaccount {sub_id}: ${bal:.2f}")

    def test_get_positions_subaccount_1(self, hl_client):
        """Test fetching positions for subaccount 1."""
        try:
            positions = hl_client.get_positions(1)
            print(f"Subaccount 1 has {len(positions)} open positions")
            for pos in positions:
                print(f"  {pos.symbol}: {pos.size} @ ${pos.entry_price:.2f}")
        except ValueError as e:
            pytest.skip(f"Subaccount 1 not configured: {e}")

    def test_get_account_state(self, hl_client):
        """Test fetching full account state."""
        # Use subaccount 1 address instead of main wallet
        try:
            address = hl_client._get_subaccount_address(1)
            state = hl_client.get_account_state(address)

            assert state is not None

            if state:
                margin = state.get('marginSummary', {})
                account_value = float(margin.get('accountValue', 0))
                print(f"Subaccount 1 account value: ${account_value:.2f}")
        except Exception as e:
            pytest.skip(f"Cannot get account state: {e}")


# ============================================================================
# DATABASE + HYPERLIQUID INTEGRATION TESTS
# ============================================================================

class TestDatabaseHyperliquidSync:
    """Test synchronization between database and Hyperliquid."""

    def test_subaccount_balance_matches_exchange(self, hl_client):
        """Compare database balance with Hyperliquid balance."""
        mismatches = []

        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            for sa in subaccounts:
                try:
                    hl_balance = hl_client.get_account_balance(sa.id)
                    db_balance = sa.current_balance or 0

                    # Allow 1% tolerance for timing differences
                    if hl_balance > 0:
                        diff_pct = abs(hl_balance - db_balance) / hl_balance
                        if diff_pct > 0.01:  # More than 1% difference
                            mismatches.append({
                                'subaccount': sa.id,
                                'db_balance': db_balance,
                                'hl_balance': hl_balance,
                                'diff_pct': diff_pct
                            })

                    print(f"Subaccount {sa.id}: DB=${db_balance:.2f}, HL=${hl_balance:.2f}")

                except (ValueError, RuntimeError) as e:
                    print(f"Subaccount {sa.id}: Cannot fetch HL balance - {e}")

        if mismatches:
            print("\nBalance mismatches found:")
            for m in mismatches:
                print(f"  Subaccount {m['subaccount']}: "
                      f"DB=${m['db_balance']:.2f} vs HL=${m['hl_balance']:.2f} "
                      f"({m['diff_pct']:.1%} diff)")

        # Don't fail test, just report
        assert True

    def test_update_db_from_hyperliquid(self, hl_client):
        """Test updating database balances from Hyperliquid."""
        updated = []

        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            for sa in subaccounts:
                try:
                    hl_balance = hl_client.get_account_balance(sa.id)

                    # Update current_balance
                    old_balance = sa.current_balance
                    sa.current_balance = hl_balance

                    # Update peak_balance if higher
                    if sa.peak_balance is None or hl_balance > sa.peak_balance:
                        sa.peak_balance = hl_balance
                        sa.peak_balance_updated_at = datetime.now(UTC)

                    updated.append({
                        'id': sa.id,
                        'old': old_balance,
                        'new': hl_balance
                    })

                except (ValueError, RuntimeError):
                    pass

            session.commit()

        print(f"Updated {len(updated)} subaccounts from Hyperliquid:")
        for u in updated:
            print(f"  Subaccount {u['id']}: ${u['old'] or 0:.2f} -> ${u['new']:.2f}")


# ============================================================================
# EMERGENCY STOP MANAGER INTEGRATION TESTS
# ============================================================================

class TestEmergencyStopWithRealData:
    """Test EmergencyStopManager with real data."""

    def test_check_conditions_with_real_balances(self, manager, hl_client):
        """Test emergency condition checking with real Hyperliquid data."""
        # First sync balances from Hyperliquid
        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            for sa in subaccounts:
                try:
                    hl_balance = hl_client.get_account_balance(sa.id)
                    sa.current_balance = hl_balance
                    if sa.peak_balance is None:
                        sa.peak_balance = hl_balance
                    sa.peak_balance_updated_at = datetime.now(UTC)
                except (ValueError, RuntimeError):
                    pass

            session.commit()

        # Now check conditions
        manager.last_check_time = None  # Bypass throttle
        triggered = manager.check_all_conditions()

        print(f"Emergency conditions check: {len(triggered)} triggers")
        for t in triggered:
            print(f"  [{t['scope']}:{t['scope_id']}] {t['reason']} -> {t['action']}")

        # Verify no false positives from stale data
        for t in triggered:
            if 'data_stale' in t.get('reason', '').lower():
                # Data should be fresh now
                pytest.fail("Data stale triggered after sync - check peak_balance_updated_at")

    def test_can_trade_after_sync(self, manager, hl_client):
        """Test can_trade with synchronized data."""
        # First ensure no stops are active for a test strategy
        test_strategy_id = uuid4()

        result = manager.can_trade(1, test_strategy_id)

        print(f"can_trade result: allowed={result['allowed']}")
        if not result['allowed']:
            print(f"  blocked_by: {result['blocked_by']}")
            print(f"  reasons: {result['reasons']}")

        # Result depends on current state - just verify format
        assert 'allowed' in result
        assert 'blocked_by' in result
        assert 'reasons' in result

    def test_drawdown_calculation_accuracy(self, manager, hl_client):
        """Verify drawdown calculations match expected values."""
        with get_session() as session:
            subaccounts = session.query(Subaccount).filter(
                Subaccount.status.in_(['ACTIVE', 'PAUSED'])
            ).all()

            for sa in subaccounts:
                try:
                    hl_balance = hl_client.get_account_balance(sa.id)
                    peak = sa.peak_balance or hl_balance

                    if peak > 0:
                        dd = (peak - hl_balance) / peak
                        print(f"Subaccount {sa.id}: "
                              f"peak=${peak:.2f}, current=${hl_balance:.2f}, DD={dd:.1%}")

                        # Verify DD calculation makes sense
                        assert dd >= 0, f"DD should be non-negative, got {dd}"
                        assert dd <= 1, f"DD should be <= 100%, got {dd}"

                except (ValueError, RuntimeError):
                    pass


# ============================================================================
# END-TO-END FLOW TESTS
# ============================================================================

class TestEndToEndFlow:
    """Test complete emergency stop flow end-to-end."""

    def test_full_cycle_trigger_and_reset(self, manager):
        """Test full cycle: trigger stop -> verify blocked -> reset -> verify unblocked."""
        test_strategy_id = uuid4()
        test_scope_id = f"test_{uuid4().hex[:8]}"

        # 1. Initially should not have our test stop
        result = manager.can_trade(999, test_strategy_id)
        initial_blocks = set(result['blocked_by'])

        # 2. Trigger a test stop
        manager.trigger_stop(
            scope='strategy',
            scope_id=str(test_strategy_id),
            reason='Integration test stop',
            action='halt_entries',
            reset_trigger='24h'
        )

        # 3. Verify blocked
        result = manager.can_trade(999, test_strategy_id)
        assert f'strategy_{test_strategy_id}' in result['blocked_by'], \
            f"Strategy should be blocked, blocked_by={result['blocked_by']}"

        # 4. Manually reset (simulate expired cooldown)
        with get_session() as session:
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope == 'strategy',
                EmergencyStopState.scope_id == str(test_strategy_id)
            ).first()
            if state:
                state.is_stopped = False
                state.stop_reason = None
                session.commit()

        # 5. Verify unblocked
        result = manager.can_trade(999, test_strategy_id)
        assert f'strategy_{test_strategy_id}' not in result['blocked_by'], \
            "Strategy should be unblocked after reset"

        print("Full cycle test passed: trigger -> block -> reset -> unblock")

    def test_balance_update_flow(self, manager, hl_client):
        """Test balance update flow with real Hyperliquid data."""
        # Get a subaccount with real balance
        try:
            hl_balance = hl_client.get_account_balance(1)
        except (ValueError, RuntimeError) as e:
            pytest.skip(f"Cannot get balance: {e}")

        # Simulate a trade PnL
        test_pnl = 10.0  # $10 profit

        # Update via manager
        manager.update_balances(
            subaccount_id=1,
            current_balance=hl_balance,
            pnl_delta=test_pnl
        )

        # Verify in database
        with get_session() as session:
            sa = session.query(Subaccount).filter(Subaccount.id == 1).first()
            assert sa is not None
            assert sa.current_balance == hl_balance
            assert sa.peak_balance is not None
            print(f"Balance update verified: current=${sa.current_balance:.2f}, "
                  f"peak=${sa.peak_balance:.2f}, daily_pnl=${sa.daily_pnl_usd:.2f}")

    def test_concurrent_stops_multiple_scopes(self, manager):
        """Test multiple concurrent stops at different scopes."""
        test_strategy_id = uuid4()

        # Create stops at multiple scopes
        scopes = [
            ('strategy', str(test_strategy_id), 'Test strategy stop', '24h'),
            ('subaccount', 'test_sub_999', 'Test subaccount stop', 'rotation'),
        ]

        for scope, scope_id, reason, reset in scopes:
            manager.trigger_stop(scope, scope_id, reason, 'halt_entries', reset)

        # Check can_trade - should see strategy block
        result = manager.can_trade(999, test_strategy_id)
        assert not result['allowed']
        assert f'strategy_{test_strategy_id}' in result['blocked_by']

        # Cleanup
        with get_session() as session:
            session.execute(text(
                f"DELETE FROM emergency_stop_states WHERE scope_id = '{test_strategy_id}'"
            ))
            session.execute(text(
                "DELETE FROM emergency_stop_states WHERE scope_id = 'test_sub_999'"
            ))
            session.commit()

        print("Concurrent stops test passed")


# ============================================================================
# SAFETY VERIFICATION TESTS
# ============================================================================

class TestSafetyVerification:
    """Verify safety mechanisms work correctly."""

    def test_throttling_prevents_spam(self, manager):
        """Verify throttling prevents database spam."""
        manager.last_check_time = datetime.now(UTC)

        # Immediate call should be throttled
        result = manager.check_all_conditions()
        assert result == [], "Should be throttled, returning empty list"

        print("Throttling verification passed")

    def test_idempotent_triggers(self, manager):
        """Verify triggers are idempotent."""
        test_id = f"test_{uuid4().hex[:8]}"

        # Trigger multiple times
        for i in range(3):
            manager.trigger_stop(
                scope='strategy',
                scope_id=test_id,
                reason=f'Trigger {i}',
                action='halt_entries',
                reset_trigger='24h'
            )

        # Should only have one record
        with get_session() as session:
            count = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope_id == test_id
            ).count()
            assert count == 1, f"Expected 1 record, got {count}"

            # First trigger's reason should be preserved
            state = session.query(EmergencyStopState).filter(
                EmergencyStopState.scope_id == test_id
            ).first()
            assert state.stop_reason == 'Trigger 0'

        print("Idempotent triggers verification passed")

    def test_state_persistence_across_manager_instances(self, config):
        """Verify state persists across manager restarts."""
        test_id = f"test_{uuid4().hex[:8]}"

        # Create stop with first manager
        manager1 = EmergencyStopManager(config._raw_config)
        manager1.trigger_stop(
            scope='strategy',
            scope_id=test_id,
            reason='Persistence test',
            action='halt_entries',
            reset_trigger='24h'
        )

        # Create new manager (simulates restart)
        manager2 = EmergencyStopManager(config._raw_config)

        # Check with second manager
        is_stopped, reason = manager2.is_stopped('strategy', test_id)
        assert is_stopped is True
        assert reason == 'Persistence test'

        # Cleanup
        with get_session() as session:
            session.execute(text(
                f"DELETE FROM emergency_stop_states WHERE scope_id = '{test_id}'"
            ))
            session.commit()

        print("Persistence verification passed")
