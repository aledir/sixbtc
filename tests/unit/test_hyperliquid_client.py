"""
Test HyperliquidClient

Tests all client functionality in dry-run mode.
CRITICAL: All tests MUST use dry_run=True to prevent real orders.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.executor.hyperliquid_client import (
    HyperliquidClient,
    Order,
    Position,
    OrderStatus
)


class TestHyperliquidClient:
    """Test Hyperliquid client functionality"""

    @pytest.fixture
    def client(self):
        """Create dry-run client"""
        return HyperliquidClient(dry_run=True)

    def test_initialization_dry_run(self):
        """Test client initializes in dry-run mode"""
        client = HyperliquidClient(dry_run=True)
        assert client.dry_run is True
        assert client.current_subaccount == 1
        assert len(client._mock_orders) == 0
        assert len(client._mock_positions) == 0

    def test_initialization_live_without_credentials_fails(self):
        """Test live mode requires credentials"""
        with pytest.raises(ValueError, match="Live trading not allowed in tests"):
            HyperliquidClient(dry_run=False)

    def test_switch_subaccount(self, client):
        """Test subaccount switching"""
        # Valid switch
        assert client.switch_subaccount(5) is True
        assert client.current_subaccount == 5

        # Invalid switches
        assert client.switch_subaccount(0) is False
        assert client.switch_subaccount(11) is False
        assert client.switch_subaccount(-1) is False

    def test_place_market_order_long(self, client):
        """Test placing long market order"""
        order = client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1,
            stop_loss=41000.0,
            take_profit=43000.0
        )

        # Verify order
        assert isinstance(order, Order)
        assert order.symbol == 'BTC'
        assert order.side == 'long'
        assert order.size == 0.1
        assert order.stop_loss == 41000.0
        assert order.take_profit == 43000.0
        assert order.status == OrderStatus.FILLED
        assert order.order_id.startswith('mock_order_')

        # Verify order logged
        assert len(client._mock_orders) == 1
        assert client._mock_orders[0].order_id == order.order_id

        # Verify position created
        assert 'BTC' in client._mock_positions
        position = client._mock_positions['BTC']
        assert position.symbol == 'BTC'
        assert position.side == 'long'
        assert position.size == 0.1

    def test_place_market_order_short(self, client):
        """Test placing short market order"""
        order = client.place_market_order(
            symbol='ETH',
            side='short',
            size=1.5
        )

        assert order.side == 'short'
        assert order.symbol == 'ETH'
        assert order.size == 1.5

    def test_place_market_order_invalid_side(self, client):
        """Test invalid side raises error"""
        with pytest.raises(ValueError, match="Invalid side"):
            client.place_market_order('BTC', 'invalid', 0.1)

    def test_place_market_order_invalid_size(self, client):
        """Test invalid size raises error"""
        with pytest.raises(ValueError, match="Invalid size"):
            client.place_market_order('BTC', 'long', 0.0)

        with pytest.raises(ValueError, match="Invalid size"):
            client.place_market_order('BTC', 'long', -0.5)

    def test_close_position(self, client):
        """Test closing position"""
        # Create position
        client.place_market_order('BTC', 'long', 0.1)
        assert 'BTC' in client._mock_positions

        # Close position
        result = client.close_position('BTC', reason='Take profit')
        assert result is True
        assert 'BTC' not in client._mock_positions

        # Try to close again (should fail)
        result = client.close_position('BTC')
        assert result is False

    def test_close_all_positions(self, client):
        """Test closing all positions"""
        # Create multiple positions
        client.place_market_order('BTC', 'long', 0.1)
        client.place_market_order('ETH', 'short', 1.0)
        client.place_market_order('SOL', 'long', 10.0)

        assert len(client._mock_positions) == 3

        # Close all
        count = client.close_all_positions()
        assert count == 3
        assert len(client._mock_positions) == 0

    def test_cancel_all_orders(self, client):
        """Test cancelling all pending orders"""
        # Place orders
        order1 = client.place_market_order('BTC', 'long', 0.1)
        order2 = client.place_market_order('ETH', 'short', 1.0)

        # Both should be filled in dry-run
        assert order1.status == OrderStatus.FILLED
        assert order2.status == OrderStatus.FILLED

        # Manually set one to pending for testing
        client._mock_orders[0].status = OrderStatus.PENDING

        # Cancel all
        count = client.cancel_all_orders()
        assert count == 1
        assert client._mock_orders[0].status == OrderStatus.CANCELLED

    def test_get_positions(self, client):
        """Test retrieving positions"""
        # No positions initially
        positions = client.get_positions()
        assert len(positions) == 0

        # Create positions
        client.place_market_order('BTC', 'long', 0.1)
        client.place_market_order('ETH', 'short', 1.0)

        # Get positions
        positions = client.get_positions()
        assert len(positions) == 2

        symbols = {p.symbol for p in positions}
        assert 'BTC' in symbols
        assert 'ETH' in symbols

    def test_get_position(self, client):
        """Test retrieving single position"""
        # No position
        position = client.get_position('BTC')
        assert position is None

        # Create position
        client.place_market_order('BTC', 'long', 0.1)

        # Get position
        position = client.get_position('BTC')
        assert position is not None
        assert position.symbol == 'BTC'
        assert position.size == 0.1

    def test_get_account_balance(self, client):
        """Test retrieving account balance"""
        balance = client.get_account_balance()
        assert balance == 10000.0  # Default mock balance

    def test_get_orders(self, client):
        """Test retrieving orders"""
        # No orders initially
        orders = client.get_orders()
        assert len(orders) == 0

        # Create orders
        client.place_market_order('BTC', 'long', 0.1)
        client.place_market_order('ETH', 'short', 1.0)

        # Get all orders
        orders = client.get_orders()
        assert len(orders) == 2

        # Get orders for specific symbol
        btc_orders = client.get_orders(symbol='BTC')
        assert len(btc_orders) == 1
        assert btc_orders[0].symbol == 'BTC'

    def test_update_stop_loss(self, client):
        """Test updating stop loss"""
        # Create position
        client.place_market_order('BTC', 'long', 0.1, stop_loss=40000.0)

        # Update stop loss
        result = client.update_stop_loss('BTC', 41000.0)
        assert result is True

        # Verify update
        position = client.get_position('BTC')
        assert position.stop_loss == 41000.0

        # Try to update non-existent position
        result = client.update_stop_loss('NONEXISTENT', 50000.0)
        assert result is False

    def test_update_take_profit(self, client):
        """Test updating take profit"""
        # Create position
        client.place_market_order('BTC', 'long', 0.1, take_profit=45000.0)

        # Update take profit
        result = client.update_take_profit('BTC', 46000.0)
        assert result is True

        # Verify update
        position = client.get_position('BTC')
        assert position.take_profit == 46000.0

    def test_get_current_price(self, client):
        """Test getting current price"""
        price = client.get_current_price('BTC')
        assert price == 42000.0  # Mock price

    def test_health_check(self, client):
        """Test health check"""
        # Empty state
        health = client.health_check()
        assert health['status'] == 'healthy'
        assert health['dry_run'] is True
        assert health['subaccount'] == 1
        assert health['positions'] == 0
        assert health['orders'] == 0
        assert health['balance'] == 10000.0

        # With positions
        client.place_market_order('BTC', 'long', 0.1)
        health = client.health_check()
        assert health['positions'] == 1
        assert health['orders'] == 1

    def test_multiple_subaccounts(self, client):
        """Test operations across multiple subaccounts"""
        # Subaccount 1
        client.switch_subaccount(1)
        client.place_market_order('BTC', 'long', 0.1)

        # Subaccount 2
        client.switch_subaccount(2)
        client.place_market_order('ETH', 'short', 1.0)

        # Verify current subaccount
        assert client.current_subaccount == 2

        # Positions are shared in mock implementation
        # In real implementation, would be per-subaccount
        positions = client.get_positions()
        assert len(positions) == 2

    def test_no_real_orders_in_dry_run(self, client):
        """
        CRITICAL TEST: Verify NO real orders can be placed in dry-run

        This test MUST pass before production deployment.
        """
        # Verify dry-run flag
        assert client.dry_run is True

        # Place "order"
        order = client.place_market_order('BTC', 'long', 0.1)

        # Verify it's a mock order
        assert order.order_id.startswith('mock_')
        assert order.status == OrderStatus.FILLED

        # Verify order is in mock list, not real exchange
        assert order in client._mock_orders
        assert len(client._mock_orders) > 0

        # Verify all mock orders have mock IDs
        for mock_order in client._mock_orders:
            assert mock_order.order_id.startswith('mock_')

    def test_order_sequencing(self, client):
        """Test order IDs are sequential"""
        order1 = client.place_market_order('BTC', 'long', 0.1)
        order2 = client.place_market_order('ETH', 'short', 1.0)
        order3 = client.place_market_order('SOL', 'long', 10.0)

        # Extract order numbers
        id1 = int(order1.order_id.split('_')[-1])
        id2 = int(order2.order_id.split('_')[-1])
        id3 = int(order3.order_id.split('_')[-1])

        # Verify sequential
        assert id2 == id1 + 1
        assert id3 == id2 + 1

    def test_position_overwrite(self, client):
        """Test opening new position on same symbol overwrites old one"""
        # First position
        order1 = client.place_market_order('BTC', 'long', 0.1)
        position1 = client.get_position('BTC')
        assert position1.size == 0.1

        # Second position (overwrites)
        order2 = client.place_market_order('BTC', 'long', 0.2)
        position2 = client.get_position('BTC')
        assert position2.size == 0.2

        # Only one BTC position
        positions = client.get_positions()
        btc_positions = [p for p in positions if p.symbol == 'BTC']
        assert len(btc_positions) == 1
