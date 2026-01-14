"""
Unit tests for EmergencyStopManager

Tests emergency stop logic at four scopes:
- PORTFOLIO: daily_loss, drawdown
- SUBACCOUNT: drawdown
- STRATEGY: consecutive_losses
- SYSTEM: data_stale
"""

import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.executor.emergency_stop_manager import EmergencyStopManager
from src.database.models import EmergencyStopState, Subaccount, Strategy, Trade


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


class TestEmergencyStopManagerInit:
    """Tests for EmergencyStopManager initialization."""

    def test_init_loads_thresholds(self, manager):
        """Verify thresholds are loaded from config."""
        assert manager.max_portfolio_drawdown == 0.20
        assert manager.max_daily_loss == 0.10
        assert manager.max_subaccount_drawdown == 0.25
        assert manager.max_consecutive_losses == 10
        assert manager.data_stale_seconds == 120

    def test_init_loads_cooldowns(self, manager):
        """Verify cooldown periods are loaded from config."""
        assert manager.portfolio_dd_cooldown_hours == 48
        assert manager.strategy_cooldown_hours == 24


class TestCanTrade:
    """Tests for can_trade method."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_can_trade_returns_allowed_when_no_stops(self, mock_session, manager):
        """Verify can_trade returns allowed=True when no stops active."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        result = manager.can_trade(1, uuid4())

        assert result['allowed'] is True
        assert result['blocked_by'] == []
        assert result['reasons'] == []

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_can_trade_returns_blocked_when_portfolio_stopped(self, mock_session, manager):
        """Verify can_trade returns blocked when portfolio is stopped."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create mock stop state
        mock_state = MagicMock()
        mock_state.is_stopped = True
        mock_state.stop_reason = "Daily loss 10.5% >= 10%"
        mock_state.cooldown_until = datetime.now(UTC) + timedelta(hours=1)

        # First call returns portfolio stop, others return None
        mock_ctx.query.return_value.filter.return_value.first.side_effect = [
            mock_state,  # portfolio
            None,  # system
            None,  # subaccount
            None,  # strategy
        ]
        mock_session.return_value = mock_ctx

        result = manager.can_trade(1, uuid4())

        assert result['allowed'] is False
        assert 'portfolio_global' in result['blocked_by']
        assert "Daily loss 10.5% >= 10%" in result['reasons']

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_can_trade_checks_all_scopes(self, mock_session, manager):
        """Verify can_trade checks portfolio, system, subaccount, strategy."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        manager.can_trade(5, uuid4())

        # Verify 4 queries were made (one per scope)
        assert mock_ctx.query.return_value.filter.return_value.first.call_count == 4


class TestTriggerStop:
    """Tests for trigger_stop method."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_trigger_stop_creates_state(self, mock_session, manager):
        """Verify trigger_stop creates EmergencyStopState in DB."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Test stop',
            action='halt_entries',
            reset_trigger='midnight_utc'
        )

        # Verify state was added
        mock_ctx.add.assert_called_once()
        mock_ctx.commit.assert_called_once()

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_trigger_stop_is_idempotent(self, mock_session, manager):
        """Verify trigger_stop is idempotent (no double trigger)."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Simulate existing stop
        existing_state = MagicMock()
        existing_state.is_stopped = True
        mock_ctx.query.return_value.filter.return_value.first.return_value = existing_state
        mock_session.return_value = mock_ctx

        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Test stop',
            action='halt_entries',
            reset_trigger='midnight_utc'
        )

        # Verify no commit was made (already stopped)
        mock_ctx.commit.assert_not_called()

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_trigger_stop_calculates_cooldown_midnight(self, mock_session, manager):
        """Verify midnight_utc reset trigger calculates correct cooldown."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        added_state = None

        def capture_add(state):
            nonlocal added_state
            added_state = state

        mock_ctx.add.side_effect = capture_add

        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Daily loss',
            action='halt_entries',
            reset_trigger='midnight_utc'
        )

        # Verify cooldown is set to next midnight UTC
        assert added_state is not None
        assert added_state.cooldown_until is not None
        assert added_state.cooldown_until.hour == 0
        assert added_state.cooldown_until.minute == 0

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_trigger_stop_calculates_cooldown_48h(self, mock_session, manager):
        """Verify cooldown_48h_rotation calculates 48h cooldown."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        added_state = None

        def capture_add(state):
            nonlocal added_state
            added_state = state

        mock_ctx.add.side_effect = capture_add

        now = datetime.now(UTC)
        manager.trigger_stop(
            scope='portfolio',
            scope_id='global',
            reason='Portfolio DD',
            action='force_close',
            reset_trigger='cooldown_48h_rotation'
        )

        # Verify cooldown is ~48h from now
        assert added_state is not None
        expected_cooldown = now + timedelta(hours=48)
        assert abs((added_state.cooldown_until - expected_cooldown).total_seconds()) < 5


class TestAutoResets:
    """Tests for auto-reset logic."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_auto_reset_midnight_utc(self, mock_session, manager):
        """Verify daily loss resets at midnight UTC."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create expired stop
        expired_stop = MagicMock()
        expired_stop.scope = 'portfolio'
        expired_stop.scope_id = 'global'
        expired_stop.is_stopped = True
        expired_stop.reset_trigger = 'midnight_utc'
        expired_stop.cooldown_until = datetime.now(UTC) - timedelta(hours=1)

        mock_ctx.query.return_value.filter.return_value.all.return_value = [expired_stop]
        mock_ctx.query.return_value.filter.return_value.first.return_value = expired_stop
        mock_session.return_value = mock_ctx

        resets = manager.check_auto_resets()

        assert len(resets) == 1
        assert resets[0]['scope'] == 'portfolio'
        assert 'midnight' in resets[0]['reason'].lower()

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_auto_reset_24h_strategy(self, mock_session, manager):
        """Verify strategy consecutive losses resets after 24h."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        strategy_id = str(uuid4())

        # Create expired stop
        expired_stop = MagicMock()
        expired_stop.scope = 'strategy'
        expired_stop.scope_id = strategy_id
        expired_stop.is_stopped = True
        expired_stop.reset_trigger = '24h'
        expired_stop.cooldown_until = datetime.now(UTC) - timedelta(hours=1)

        mock_ctx.query.return_value.filter.return_value.all.return_value = [expired_stop]
        mock_ctx.query.return_value.filter.return_value.first.return_value = expired_stop
        mock_session.return_value = mock_ctx

        resets = manager.check_auto_resets()

        assert len(resets) == 1
        assert resets[0]['scope'] == 'strategy'

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_no_reset_before_cooldown(self, mock_session, manager):
        """Verify no reset before cooldown expires."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create non-expired stop
        active_stop = MagicMock()
        active_stop.scope = 'portfolio'
        active_stop.scope_id = 'global'
        active_stop.is_stopped = True
        active_stop.reset_trigger = 'midnight_utc'
        active_stop.cooldown_until = datetime.now(UTC) + timedelta(hours=5)

        mock_ctx.query.return_value.filter.return_value.all.return_value = [active_stop]
        mock_session.return_value = mock_ctx

        resets = manager.check_auto_resets()

        assert len(resets) == 0


class TestBalanceTracking:
    """Tests for balance tracking methods."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_update_balances_tracks_peak(self, mock_session, manager):
        """Verify peak balance is only updated when balance increases."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create mock subaccount
        mock_subaccount = MagicMock()
        mock_subaccount.peak_balance = 1000.0
        mock_subaccount.daily_pnl_usd = 0.0
        mock_subaccount.daily_pnl_reset_date = None
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_subaccount
        mock_session.return_value = mock_ctx

        # Update with lower balance
        manager.update_balances(1, current_balance=950.0, pnl_delta=-50.0)

        # Peak should NOT be updated
        assert mock_subaccount.peak_balance == 1000.0

        # Update with higher balance
        manager.update_balances(1, current_balance=1100.0, pnl_delta=100.0)

        # Peak SHOULD be updated
        assert mock_subaccount.peak_balance == 1100.0

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_update_balances_resets_daily_pnl(self, mock_session, manager):
        """Verify daily PnL resets at midnight UTC."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create mock subaccount with yesterday's date
        mock_subaccount = MagicMock()
        mock_subaccount.peak_balance = 1000.0
        mock_subaccount.daily_pnl_usd = 50.0  # Previous day's PnL
        mock_subaccount.daily_pnl_reset_date = datetime.now(UTC) - timedelta(days=1)
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_subaccount
        mock_session.return_value = mock_ctx

        manager.update_balances(1, current_balance=1000.0, pnl_delta=10.0)

        # Daily PnL should be reset to just this trade's PnL
        assert mock_subaccount.daily_pnl_usd == 10.0

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_update_balances_accumulates_daily_pnl(self, mock_session, manager):
        """Verify daily PnL accumulates within same day."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create mock subaccount with today's date
        mock_subaccount = MagicMock()
        mock_subaccount.peak_balance = 1000.0
        mock_subaccount.daily_pnl_usd = 50.0
        mock_subaccount.daily_pnl_reset_date = datetime.now(UTC)
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_subaccount
        mock_session.return_value = mock_ctx

        manager.update_balances(1, current_balance=1000.0, pnl_delta=20.0)

        # Daily PnL should accumulate
        assert mock_subaccount.daily_pnl_usd == 70.0


class TestThrottling:
    """Tests for check throttling."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_throttling_skips_frequent_checks(self, mock_session, manager):
        """Verify check_all_conditions is throttled."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.all.return_value = []
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        # First call should execute
        manager.last_check_time = None
        result1 = manager.check_all_conditions()

        # Second immediate call should be throttled
        result2 = manager.check_all_conditions()

        assert result2 == []  # Throttled, returns empty

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_throttling_allows_after_interval(self, mock_session, manager):
        """Verify checks are allowed after throttle interval."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.query.return_value.filter.return_value.all.return_value = []
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        # Set last check to 61 seconds ago
        manager.last_check_time = datetime.now(UTC) - timedelta(seconds=61)

        # This call should execute (not throttled)
        result = manager.check_all_conditions()

        # Verify last_check_time was updated
        assert manager.last_check_time is not None
        assert (datetime.now(UTC) - manager.last_check_time).total_seconds() < 2


class TestResetOnRotation:
    """Tests for rotation-triggered resets."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_reset_on_rotation_clears_subaccount_stop(self, mock_session, manager):
        """Verify reset_on_rotation clears subaccount stop."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Create mock stop state
        mock_state = MagicMock()
        mock_state.scope = 'subaccount'
        mock_state.scope_id = '1'
        mock_state.is_stopped = True
        mock_state.reset_trigger = 'rotation'

        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_state
        mock_session.return_value = mock_ctx

        manager.reset_on_rotation(1)

        # Verify state was cleared
        assert mock_state.is_stopped is False
        mock_ctx.commit.assert_called_once()

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_reset_on_rotation_ignores_non_rotation_stops(self, mock_session, manager):
        """Verify reset_on_rotation only affects rotation trigger stops."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        # Return None (no stop with rotation trigger)
        mock_ctx.query.return_value.filter.return_value.first.return_value = None
        mock_session.return_value = mock_ctx

        manager.reset_on_rotation(1)

        # No commit should happen
        mock_ctx.commit.assert_not_called()


class TestActions:
    """Tests for stop actions."""

    @patch('src.executor.emergency_stop_manager.get_session')
    def test_halt_entries_updates_subaccount_status(self, mock_session, manager):
        """Verify halt_entries updates subaccount status to PAUSED."""
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        mock_subaccount = MagicMock()
        mock_subaccount.status = 'ACTIVE'
        mock_ctx.query.return_value.filter.return_value.first.return_value = mock_subaccount
        mock_session.return_value = mock_ctx

        manager._execute_halt_entries('subaccount', '1')

        assert mock_subaccount.status == 'PAUSED'
        mock_ctx.commit.assert_called_once()

    def test_force_close_without_client_logs_error(self, manager, caplog):
        """Verify force_close logs error when no client available."""
        manager.client = None

        manager._execute_force_close("Test reason")

        assert "Cannot force close" in caplog.text
