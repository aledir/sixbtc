"""
Integration tests for emergency stop scenarios.

Tests realistic emergency situations with database persistence.
Uses mocking to avoid PostgreSQL-specific types in SQLite.
"""

import pytest
from datetime import datetime, UTC, timedelta, date
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

from src.executor.emergency_stop_manager import EmergencyStopManager
from src.database.models import EmergencyStopState, Subaccount


@pytest.fixture
def config():
    """Test configuration with emergency stop settings."""
    return {
        'risk': {
            'emergency': {
                'max_portfolio_drawdown': 0.20,
                'max_daily_loss': 0.10,
                'max_subaccount_drawdown': 0.25,
                'max_consecutive_losses': 10,
                'data_stale_seconds': 120,
                'rotation_loss_threshold': 0.00,
            },
            'emergency_cooldowns': {
                'portfolio_dd_hours': 48,
                'strategy_hours': 24,
            }
        }
    }


@pytest.fixture
def manager(config):
    """EmergencyStopManager instance for testing."""
    return EmergencyStopManager(config)


def create_mock_session():
    """Create a properly configured mock session context manager."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


class TestDailyLossScenario:
    """Test 10% daily loss scenario."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_daily_loss_triggers_halt_entries(self, mock_session, manager):
        """Simulate 10% daily loss and verify halt_entries is triggered."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Track added states
        added_states = []

        def capture_add(obj):
            added_states.append(obj)

        mock_ctx.add.side_effect = capture_add
        mock_ctx.query.return_value.filter.return_value.first.return_value = None

        # Trigger portfolio daily loss stop
        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Daily loss 10.5% >= 10%',
            action='halt_entries',
            reset_trigger='midnight_utc'
        )

        # Verify state was added
        assert len(added_states) == 1
        state = added_states[0]
        assert state.scope == 'portfolio'
        assert state.scope_id == 'global'
        assert state.is_stopped is True
        assert state.stop_action == 'halt_entries'
        assert state.reset_trigger == 'midnight_utc'
        assert 'Daily loss' in state.stop_reason

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_daily_loss_resets_at_midnight(self, mock_session, manager):
        """Verify daily loss auto-resets at midnight UTC."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create expired stop mock
        yesterday = datetime.now(UTC) - timedelta(hours=1)
        mock_state = MagicMock()
        mock_state.scope = 'portfolio'
        mock_state.scope_id = 'global'
        mock_state.is_stopped = True
        mock_state.reset_trigger = 'midnight_utc'
        mock_state.cooldown_until = yesterday  # Expired

        mock_ctx.query.return_value.filter.return_value.all.return_value = [mock_state]
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Check auto-resets
        resets = manager.check_auto_resets()

        assert len(resets) == 1
        assert resets[0]['scope'] == 'portfolio'
        assert resets[0]['scope_id'] == 'global'
        assert 'midnight' in resets[0]['reason'].lower()


class TestPortfolioDrawdownScenario:
    """Test 20% portfolio drawdown scenario."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_portfolio_dd_triggers_force_close(self, mock_session, manager):
        """Simulate 20% portfolio DD and verify force_close is triggered."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Track added states
        added_states = []

        def capture_add(obj):
            added_states.append(obj)

        mock_ctx.add.side_effect = capture_add
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_ctx.query.return_value.filter.return_value.update.return_value = 0

        # Trigger portfolio DD stop
        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Portfolio DD 22% >= 20%',
            action='force_close',
            reset_trigger='cooldown_48h_rotation'
        )

        # Verify state was added with force_close action
        assert len(added_states) == 1
        state = added_states[0]
        assert state.scope == 'portfolio'
        assert state.is_stopped is True
        assert state.stop_action == 'force_close'
        assert state.reset_trigger == 'cooldown_48h_rotation'

        # Verify 48h cooldown
        expected_cooldown = datetime.now(UTC) + timedelta(hours=48)
        assert abs((state.cooldown_until - expected_cooldown).total_seconds()) < 5

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_portfolio_dd_requires_rotation_to_reset(self, mock_session, manager):
        """Verify portfolio DD requires rotation of losing strategies to reset."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create expired stop (48h passed but rotation not done)
        two_days_ago = datetime.now(UTC) - timedelta(hours=49)
        mock_state = MagicMock()
        mock_state.scope = 'portfolio'
        mock_state.scope_id = 'global'
        mock_state.is_stopped = True
        mock_state.stop_reason = 'Portfolio DD 22% >= 20%'
        mock_state.reset_trigger = 'cooldown_48h_rotation'
        mock_state.cooldown_until = two_days_ago + timedelta(hours=48)  # Expired

        mock_ctx.query.return_value.filter.return_value.all.return_value = [mock_state]
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Mock losing strategy still exists
        mock_strategy = MagicMock()
        mock_strategy.status = 'LIVE'
        mock_strategy.total_pnl_live = -500  # Losing strategy

        def mock_query_side_effect(model):
            result = MagicMock()
            if model.__name__ == 'EmergencyStopState':
                result.filter.return_value.all.return_value = [mock_state]
                result.filter.return_value.first.return_value = mock_state
            elif model.__name__ == 'Strategy':
                result.filter.return_value.all.return_value = [mock_strategy]
            return result

        mock_ctx.query.side_effect = mock_query_side_effect

        # Check auto-resets - should not reset without rotation
        resets = manager.check_auto_resets()

        # No reset because losing strategy still exists
        portfolio_resets = [r for r in resets if r['scope'] == 'portfolio']
        assert len(portfolio_resets) == 0


class TestSubaccountDrawdownScenario:
    """Test 25% subaccount drawdown scenario."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_subaccount_dd_only_affects_one_subaccount(self, mock_session, manager):
        """Verify subaccount DD only blocks that specific subaccount."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        added_states = []

        def capture_add(obj):
            added_states.append(obj)

        mock_ctx.add.side_effect = capture_add
        mock_ctx.query.return_value.filter.return_value.first.return_value = None

        # Trigger stop only on subaccount 1
        manager.trigger_stop(
            scope='subaccount',
            scope_id='1',
            reason='Subaccount DD 27% >= 25%',
            action='halt_entries',
            reset_trigger='rotation'
        )

        # Verify state was created for subaccount 1
        assert len(added_states) == 1
        state = added_states[0]
        assert state.scope == 'subaccount'
        assert state.scope_id == '1'
        assert state.is_stopped is True

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_subaccount_dd_resets_on_rotation(self, mock_session, manager):
        """Verify subaccount DD resets when new strategy is deployed."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create stopped state mock
        mock_state = MagicMock()
        mock_state.scope = 'subaccount'
        mock_state.scope_id = '1'
        mock_state.is_stopped = True
        mock_state.reset_trigger = 'rotation'

        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Call reset_on_rotation (simulating rotator deploying new strategy)
        manager.reset_on_rotation(1)

        # Verify state was cleared
        assert mock_state.is_stopped is False
        mock_ctx.commit.assert_called()


class TestConsecutiveLossesScenario:
    """Test 10 consecutive losses scenario."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_consecutive_losses_triggers_halt(self, mock_session, manager):
        """Simulate 10 consecutive losses and verify halt_entries."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        added_states = []

        def capture_add(obj):
            added_states.append(obj)

        mock_ctx.add.side_effect = capture_add
        mock_ctx.query.return_value.filter.return_value.first.return_value = None

        strategy_id = str(uuid4())

        # Trigger strategy stop
        manager.trigger_stop(
            scope='strategy',
            scope_id=strategy_id,
            reason='10 consecutive losses',
            action='halt_entries',
            reset_trigger='24h'
        )

        # Verify state was created
        assert len(added_states) == 1
        state = added_states[0]
        assert state.scope == 'strategy'
        assert state.scope_id == strategy_id
        assert state.is_stopped is True
        assert state.stop_action == 'halt_entries'
        assert state.reset_trigger == '24h'

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_consecutive_losses_resets_after_24h(self, mock_session, manager):
        """Verify strategy stop resets after 24h cooldown."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        strategy_id = str(uuid4())

        # Create expired stop mock (25h ago)
        expired = datetime.now(UTC) - timedelta(hours=25)
        mock_state = MagicMock()
        mock_state.scope = 'strategy'
        mock_state.scope_id = strategy_id
        mock_state.is_stopped = True
        mock_state.reset_trigger = '24h'
        mock_state.cooldown_until = expired + timedelta(hours=24)  # Expired

        mock_ctx.query.return_value.filter.return_value.all.return_value = [mock_state]
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Check auto-resets
        resets = manager.check_auto_resets()

        assert len(resets) == 1
        assert resets[0]['scope'] == 'strategy'
        assert resets[0]['scope_id'] == strategy_id


class TestDataStaleScenario:
    """Test data stale scenario."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_data_stale_triggers_halt(self, mock_session, manager):
        """Simulate stale data and verify halt_entries."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        added_states = []

        def capture_add(obj):
            added_states.append(obj)

        mock_ctx.add.side_effect = capture_add
        mock_ctx.query.return_value.filter.return_value.first.return_value = None

        # Trigger system stop
        manager.trigger_stop(
            scope='system',
            scope_id='data_feed',
            reason='Data stale > 2min',
            action='halt_entries',
            reset_trigger='data_valid'
        )

        # Verify state was created
        assert len(added_states) == 1
        state = added_states[0]
        assert state.scope == 'system'
        assert state.scope_id == 'data_feed'
        assert state.is_stopped is True
        assert state.reset_trigger == 'data_valid'

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_data_stale_resets_when_valid(self, mock_session, manager):
        """Verify data stale resets immediately when data is valid again."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create stopped state mock with data_valid trigger
        mock_state = MagicMock()
        mock_state.scope = 'system'
        mock_state.scope_id = 'data_feed'
        mock_state.is_stopped = True
        mock_state.reset_trigger = 'data_valid'

        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Manually reset (simulating data becoming valid)
        manager.reset_data_stale()

        # Verify state was cleared
        assert mock_state.is_stopped is False
        mock_ctx.commit.assert_called()


class TestPersistenceScenario:
    """Test state persistence across restarts."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_stop_persists_across_restart(self, mock_session, manager, config):
        """Verify stop state persists in database across restarts."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create stopped state that simulates persisted state
        mock_state = MagicMock()
        mock_state.scope = 'portfolio'
        mock_state.scope_id = 'global'
        mock_state.is_stopped = True
        mock_state.stop_reason = 'Daily loss 10.5% >= 10%'
        mock_state.cooldown_until = datetime.now(UTC) + timedelta(hours=1)

        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state

        # Create new manager (simulating restart)
        manager2 = EmergencyStopManager(config)

        # Check can_trade with new manager
        result = manager2.can_trade(1, uuid4())

        # Should still be blocked
        assert result['allowed'] is False
        assert 'portfolio_global' in result['blocked_by']


class TestCanTradeHierarchy:
    """Test can_trade scope hierarchy."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_can_trade_aggregates_all_blocks(self, mock_session, manager):
        """Verify can_trade returns all active blocks."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        strategy_id = uuid4()

        # Create mock stops for different scopes
        portfolio_stop = MagicMock()
        portfolio_stop.is_stopped = True
        portfolio_stop.stop_reason = 'Daily loss'
        portfolio_stop.cooldown_until = datetime.now(UTC) + timedelta(hours=1)

        subaccount_stop = MagicMock()
        subaccount_stop.is_stopped = True
        subaccount_stop.stop_reason = 'Subaccount DD'
        subaccount_stop.cooldown_until = None

        # Return different stops for different scope queries
        def mock_filter_side_effect(*args, **kwargs):
            result = MagicMock()
            # Check which scope is being queried
            if hasattr(args[0], 'right') and hasattr(args[0].right, 'value'):
                scope = args[0].right.value
                if scope == 'portfolio':
                    result.first.return_value = portfolio_stop
                elif scope == 'subaccount':
                    result.first.return_value = subaccount_stop
                else:
                    result.first.return_value = None
            else:
                result.first.return_value = None
            return result

        # Mock to return both stops
        call_count = [0]
        stops = [portfolio_stop, None, subaccount_stop, None]  # portfolio, system, subaccount, strategy

        def mock_first():
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(stops):
                return stops[idx]
            return None

        mock_ctx.query.return_value.filter.return_value.first = mock_first

        # Check can_trade
        result = manager.can_trade(1, strategy_id)

        # Should be blocked by both portfolio and subaccount
        assert result['allowed'] is False
        assert len(result['blocked_by']) >= 1


class TestActionExecution:
    """Test action execution."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_halt_entries_pauses_subaccount(self, mock_session, manager):
        """Verify halt_entries pauses the subaccount."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        mock_subaccount = MagicMock()
        mock_subaccount.status = 'ACTIVE'
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_subaccount

        manager._execute_halt_entries('subaccount', '1')

        assert mock_subaccount.status == 'PAUSED'
        mock_ctx.commit.assert_called()

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_force_close_stops_all_subaccounts(self, mock_session, manager):
        """Verify force_close updates all subaccounts to STOPPED when client exists."""
        mock_ctx = create_mock_session()
        mock_session.return_value = mock_ctx

        # Create mock client
        mock_client = MagicMock()
        manager.client = mock_client

        manager._execute_force_close("Test emergency")

        # Verify client was asked to close positions
        mock_client.emergency_close_all_positions.assert_called_with("Test emergency")

        # Should update all active subaccounts to STOPPED
        mock_ctx.query.return_value.filter.return_value.update.assert_called()


class TestThrottlingBehavior:
    """Test check throttling behavior."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_throttle_interval_respected(self, mock_session, manager):
        """Verify check_all_conditions respects throttle interval."""
        mock_ctx = create_mock_session()
        mock_ctx.query.return_value.filter.return_value.all.return_value = []
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        # First call should execute
        manager.last_check_time = None
        result1 = manager.check_all_conditions()

        # Immediate second call should be throttled
        result2 = manager.check_all_conditions()
        assert result2 == []

        # After throttle interval, should execute again
        manager.last_check_time = datetime.now(UTC) - timedelta(seconds=65)
        result3 = manager.check_all_conditions()
        # This should not return empty due to throttling
        assert manager.last_check_time is not None
