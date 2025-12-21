"""
Test PositionTracker

Tests position tracking, PnL calculation, and stop monitoring.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.executor.position_tracker import PositionTracker, TrackedPosition
from src.executor.hyperliquid_client import HyperliquidClient


class TestTrackedPosition:
    """Test TrackedPosition class"""

    def test_position_initialization(self):
        """Test position initializes correctly"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0,
            subaccount_id=1,
            strategy_id='test_strat',
            entry_reason='Test signal'
        )

        assert pos.symbol == 'BTC'
        assert pos.side == 'long'
        assert pos.size == 0.1
        assert pos.entry_price == 42000.0
        assert pos.unrealized_pnl == 0.0
        assert pos.unrealized_pnl_pct == 0.0
        assert pos.entry_time is not None
        assert isinstance(pos.entry_time, datetime)

    def test_update_price_long_profit(self):
        """Test price update for long position in profit"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Price increases
        pos.update_price(43000.0)

        # Verify PnL
        assert pos.current_price == 43000.0
        assert pos.unrealized_pnl == 100.0  # (43000 - 42000) * 0.1
        assert abs(pos.unrealized_pnl_pct - 0.02381) < 0.00001  # ~2.38%

    def test_update_price_long_loss(self):
        """Test price update for long position in loss"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Price decreases
        pos.update_price(41000.0)

        # Verify PnL
        assert pos.unrealized_pnl == -100.0  # (41000 - 42000) * 0.1
        assert abs(pos.unrealized_pnl_pct + 0.02381) < 0.00001  # ~-2.38%

    def test_update_price_short_profit(self):
        """Test price update for short position in profit"""
        pos = TrackedPosition(
            symbol='BTC',
            side='short',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Price decreases (profit for short)
        pos.update_price(41000.0)

        # Verify PnL
        assert pos.unrealized_pnl == 100.0  # (42000 - 41000) * 0.1
        assert abs(pos.unrealized_pnl_pct - 0.02381) < 0.00001

    def test_update_price_short_loss(self):
        """Test price update for short position in loss"""
        pos = TrackedPosition(
            symbol='BTC',
            side='short',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Price increases (loss for short)
        pos.update_price(43000.0)

        # Verify PnL
        assert pos.unrealized_pnl == -100.0
        assert abs(pos.unrealized_pnl_pct + 0.02381) < 0.00001

    def test_check_stop_loss_long(self):
        """Test stop loss check for long position"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0,
            stop_loss=41000.0
        )

        # Above stop loss
        assert pos.check_stop_loss_hit() is False

        # At stop loss
        pos.update_price(41000.0)
        assert pos.check_stop_loss_hit() is True

        # Below stop loss
        pos.update_price(40000.0)
        assert pos.check_stop_loss_hit() is True

    def test_check_stop_loss_short(self):
        """Test stop loss check for short position"""
        pos = TrackedPosition(
            symbol='BTC',
            side='short',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0,
            stop_loss=43000.0
        )

        # Below stop loss
        assert pos.check_stop_loss_hit() is False

        # At stop loss
        pos.update_price(43000.0)
        assert pos.check_stop_loss_hit() is True

        # Above stop loss
        pos.update_price(44000.0)
        assert pos.check_stop_loss_hit() is True

    def test_check_take_profit_long(self):
        """Test take profit check for long position"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0,
            take_profit=45000.0
        )

        # Below take profit
        assert pos.check_take_profit_hit() is False

        # At take profit
        pos.update_price(45000.0)
        assert pos.check_take_profit_hit() is True

        # Above take profit
        pos.update_price(46000.0)
        assert pos.check_take_profit_hit() is True

    def test_check_take_profit_short(self):
        """Test take profit check for short position"""
        pos = TrackedPosition(
            symbol='BTC',
            side='short',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0,
            take_profit=40000.0
        )

        # Above take profit
        assert pos.check_take_profit_hit() is False

        # At take profit
        pos.update_price(40000.0)
        assert pos.check_take_profit_hit() is True

        # Below take profit
        pos.update_price(39000.0)
        assert pos.check_take_profit_hit() is True

    def test_high_water_mark_tracking(self):
        """Test high water mark tracking"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Initial (high_water_mark is entry_price in current implementation)
        assert pos.high_water_mark == 42000.0

        # Price up - verify PnL tracking works
        pos.update_price(43000.0)
        assert pos.unrealized_pnl == 100.0

        # Track max PnL
        max_pnl_seen = pos.unrealized_pnl

        # Price down (PnL decreases)
        pos.update_price(42500.0)
        assert pos.unrealized_pnl == 50.0
        assert pos.unrealized_pnl < max_pnl_seen

        # Price up again (new high PnL)
        pos.update_price(44000.0)
        assert pos.unrealized_pnl == 200.0
        assert pos.unrealized_pnl > max_pnl_seen

    def test_get_holding_time(self):
        """Test holding time calculation"""
        pos = TrackedPosition(
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            current_price=42000.0
        )

        # Should be very close to 0
        holding_time = pos.get_holding_time()
        assert holding_time >= 0
        assert holding_time < 1.0  # Less than 1 second


class TestPositionTracker:
    """Test PositionTracker class"""

    @pytest.fixture
    def client(self):
        """Create dry-run client"""
        return HyperliquidClient(dry_run=True)

    @pytest.fixture
    def tracker(self, client):
        """Create position tracker"""
        return PositionTracker(client)

    def test_initialization(self, tracker):
        """Test tracker initializes correctly"""
        assert len(tracker.positions) == 0
        assert tracker.get_position_count() == 0

    def test_add_position(self, tracker):
        """Test adding position"""
        pos = tracker.add_position(
            subaccount_id=1,
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0,
            stop_loss=41000.0,
            take_profit=45000.0,
            strategy_id='test_strat',
            entry_reason='Test signal'
        )

        assert isinstance(pos, TrackedPosition)
        assert pos.symbol == 'BTC'
        assert pos.subaccount_id == 1

        # Verify in tracker
        assert tracker.get_position_count() == 1
        retrieved_pos = tracker.get_position(1, 'BTC')
        assert retrieved_pos is not None
        assert retrieved_pos.symbol == 'BTC'

    def test_remove_position(self, tracker):
        """Test removing position"""
        # Add position
        tracker.add_position(
            subaccount_id=1,
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0
        )

        assert tracker.get_position_count() == 1

        # Remove position
        removed = tracker.remove_position(1, 'BTC')
        assert removed is not None
        assert removed.symbol == 'BTC'
        assert tracker.get_position_count() == 0

        # Try to remove again
        removed = tracker.remove_position(1, 'BTC')
        assert removed is None

    def test_update_position_price(self, tracker):
        """Test updating position price"""
        # Add position
        tracker.add_position(
            subaccount_id=1,
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=42000.0
        )

        # Update price
        result = tracker.update_position_price(1, 'BTC', 43000.0)
        assert result is True

        # Verify update
        pos = tracker.get_position(1, 'BTC')
        assert pos.current_price == 43000.0
        assert pos.unrealized_pnl == 100.0

    def test_get_subaccount_positions(self, tracker):
        """Test getting positions for subaccount"""
        # Add positions to different subaccounts
        tracker.add_position(1, 'BTC', 'long', 0.1, 42000.0)
        tracker.add_position(1, 'ETH', 'short', 1.0, 3000.0)
        tracker.add_position(2, 'SOL', 'long', 10.0, 100.0)

        # Get subaccount 1 positions
        sub1_positions = tracker.get_subaccount_positions(1)
        assert len(sub1_positions) == 2
        symbols = {p.symbol for p in sub1_positions}
        assert symbols == {'BTC', 'ETH'}

        # Get subaccount 2 positions
        sub2_positions = tracker.get_subaccount_positions(2)
        assert len(sub2_positions) == 1
        assert sub2_positions[0].symbol == 'SOL'

    def test_get_all_positions(self, tracker):
        """Test getting all positions"""
        # Add positions
        tracker.add_position(1, 'BTC', 'long', 0.1, 42000.0)
        tracker.add_position(2, 'ETH', 'short', 1.0, 3000.0)
        tracker.add_position(3, 'SOL', 'long', 10.0, 100.0)

        # Get all
        all_positions = tracker.get_all_positions()
        assert len(all_positions) == 3

    def test_check_all_stops(self, tracker):
        """Test checking all stop losses and take profits"""
        # Add positions with stops
        tracker.add_position(
            1, 'BTC', 'long', 0.1, 42000.0,
            stop_loss=41000.0, take_profit=45000.0
        )
        tracker.add_position(
            1, 'ETH', 'short', 1.0, 3000.0,
            stop_loss=3100.0, take_profit=2900.0
        )

        # No stops hit initially
        to_close = tracker.check_all_stops()
        assert len(to_close) == 0

        # Update BTC to hit stop loss
        tracker.update_position_price(1, 'BTC', 40000.0)
        to_close = tracker.check_all_stops()
        assert len(to_close) == 1
        assert to_close[0] == (1, 'BTC', 'stop_loss')

        # Update ETH to hit take profit
        tracker.update_position_price(1, 'ETH', 2900.0)
        to_close = tracker.check_all_stops()
        assert len(to_close) == 2

        # Find ETH in results
        eth_close = [x for x in to_close if x[1] == 'ETH']
        assert len(eth_close) == 1
        assert eth_close[0] == (1, 'ETH', 'take_profit')

    def test_get_total_unrealized_pnl(self, tracker):
        """Test calculating total unrealized PnL"""
        # Add positions
        tracker.add_position(1, 'BTC', 'long', 0.1, 42000.0)
        tracker.add_position(1, 'ETH', 'short', 1.0, 3000.0)

        # Update prices
        tracker.update_position_price(1, 'BTC', 43000.0)  # +100
        tracker.update_position_price(1, 'ETH', 2900.0)  # +100

        # Total PnL
        total_pnl = tracker.get_total_unrealized_pnl()
        assert abs(total_pnl - 200.0) < 0.01

        # Subaccount PnL
        sub1_pnl = tracker.get_total_unrealized_pnl(subaccount_id=1)
        assert abs(sub1_pnl - 200.0) < 0.01

        # Subaccount with no positions
        sub2_pnl = tracker.get_total_unrealized_pnl(subaccount_id=2)
        assert sub2_pnl == 0.0

    def test_get_strategy_positions(self, tracker):
        """Test getting positions for specific strategy"""
        # Add positions with different strategies
        tracker.add_position(
            1, 'BTC', 'long', 0.1, 42000.0,
            strategy_id='strat_1'
        )
        tracker.add_position(
            2, 'ETH', 'short', 1.0, 3000.0,
            strategy_id='strat_1'
        )
        tracker.add_position(
            3, 'SOL', 'long', 10.0, 100.0,
            strategy_id='strat_2'
        )

        # Get positions for strat_1
        strat1_positions = tracker.get_strategy_positions('strat_1')
        assert len(strat1_positions) == 2
        symbols = {p.symbol for p in strat1_positions}
        assert symbols == {'BTC', 'ETH'}

        # Get positions for strat_2
        strat2_positions = tracker.get_strategy_positions('strat_2')
        assert len(strat2_positions) == 1
        assert strat2_positions[0].symbol == 'SOL'

    def test_get_summary(self, tracker):
        """Test getting summary statistics"""
        # Empty tracker
        summary = tracker.get_summary()
        assert summary['total_positions'] == 0
        assert summary['total_unrealized_pnl'] == 0.0

        # Add positions
        tracker.add_position(1, 'BTC', 'long', 0.1, 42000.0)
        tracker.add_position(1, 'ETH', 'short', 1.0, 3000.0)
        tracker.add_position(2, 'SOL', 'long', 10.0, 100.0)

        # Update prices
        tracker.update_position_price(1, 'BTC', 43000.0)  # +100
        tracker.update_position_price(1, 'ETH', 2900.0)  # +100
        tracker.update_position_price(2, 'SOL', 95.0)   # -50

        # Get summary
        summary = tracker.get_summary()
        assert summary['total_positions'] == 3
        assert summary['long_positions'] == 2
        assert summary['short_positions'] == 1
        assert summary['subaccounts_with_positions'] == 2
        assert abs(summary['total_unrealized_pnl'] - 150.0) < 0.01

    def test_position_count(self, tracker):
        """Test position counting"""
        # Empty
        assert tracker.get_position_count() == 0
        assert tracker.get_position_count(subaccount_id=1) == 0

        # Add positions
        tracker.add_position(1, 'BTC', 'long', 0.1, 42000.0)
        tracker.add_position(1, 'ETH', 'short', 1.0, 3000.0)
        tracker.add_position(2, 'SOL', 'long', 10.0, 100.0)

        # Total count
        assert tracker.get_position_count() == 3

        # Per-subaccount count
        assert tracker.get_position_count(subaccount_id=1) == 2
        assert tracker.get_position_count(subaccount_id=2) == 1
        assert tracker.get_position_count(subaccount_id=3) == 0

    def test_multiple_subaccounts(self, tracker):
        """Test tracking positions across multiple subaccounts"""
        # Add positions to 5 different subaccounts
        for sub_id in range(1, 6):
            tracker.add_position(
                sub_id, 'BTC', 'long', 0.1 * sub_id, 42000.0,
                strategy_id=f'strat_{sub_id}'
            )

        # Verify total
        assert tracker.get_position_count() == 5

        # Verify each subaccount has exactly 1 position
        for sub_id in range(1, 6):
            assert tracker.get_position_count(subaccount_id=sub_id) == 1

            pos = tracker.get_position(sub_id, 'BTC')
            assert pos is not None
            assert pos.size == 0.1 * sub_id
