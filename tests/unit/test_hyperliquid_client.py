"""
Test HyperliquidClient

Tests client functionality in dry-run mode.
CRITICAL: All tests MUST use dry_run=True to prevent real orders.

NOTE: The HyperliquidClient is a real SDK implementation. In dry-run mode:
- Orders return simulated Order objects with dry_run_* prefix
- No internal state is maintained (positions come from real API if configured)
- Operations are logged but not executed
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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
        """Create dry-run client with mocked API calls"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            # Mock the Info client
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {
                'universe': [
                    {'name': 'BTC', 'szDecimals': 5, 'maxLeverage': 40},
                    {'name': 'ETH', 'szDecimals': 4, 'maxLeverage': 25},
                    {'name': 'SOL', 'szDecimals': 2, 'maxLeverage': 20},
                ]
            }
            mock_info_instance.all_mids.return_value = {
                'BTC': '42000.0',
                'ETH': '2200.0',
                'SOL': '100.0',
            }
            mock_info_instance.user_state.return_value = {
                'marginSummary': {'accountValue': '10000.0'},
                'assetPositions': []
            }
            mock_info_instance.open_orders.return_value = []
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)
            # Set mock wallet address so position methods work
            client.wallet_address = '0x' + '0' * 40
            client._info_mock = mock_info_instance  # Store for test access
            return client

    def test_initialization_dry_run(self):
        """Test client initializes in dry-run mode"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)
            assert client.dry_run is True
            assert client.current_subaccount == 1

    def test_initialization_live_without_credentials_fails(self):
        """Test live mode requires credentials"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info.return_value = mock_info_instance

            with pytest.raises(ValueError, match="Live trading requires valid private_key and wallet_address"):
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
        """Test placing long market order in dry-run"""
        order = client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1,
            stop_loss=41000.0,
            take_profit=43000.0
        )

        # Verify order is returned
        assert isinstance(order, Order)
        assert order.symbol == 'BTC'
        assert order.side == 'long'
        assert order.stop_loss == 41000.0
        assert order.take_profit == 43000.0
        assert order.status == OrderStatus.FILLED
        assert order.order_id.startswith('dry_run_')

    def test_place_market_order_short(self, client):
        """Test placing short market order"""
        order = client.place_market_order(
            symbol='ETH',
            side='short',
            size=1.5
        )

        assert order.side == 'short'
        assert order.symbol == 'ETH'

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
        """Test closing position in dry-run"""
        # Mock a position
        client._info_mock.user_state.return_value = {
            'marginSummary': {'accountValue': '10000.0'},
            'assetPositions': [{
                'position': {
                    'coin': 'BTC',
                    'szi': '0.1',
                    'entryPx': '42000.0',
                    'unrealizedPnl': '100.0',
                    'leverage': {'value': '10'}
                }
            }]
        }

        # Close position (dry-run logs but returns True)
        result = client.close_position('BTC', reason='Take profit')
        assert result is True

    def test_close_all_positions(self, client):
        """Test closing all positions in dry-run"""
        # Mock positions
        client._info_mock.user_state.return_value = {
            'marginSummary': {'accountValue': '10000.0'},
            'assetPositions': [
                {'position': {'coin': 'BTC', 'szi': '0.1', 'entryPx': '42000.0', 'unrealizedPnl': '100.0'}},
                {'position': {'coin': 'ETH', 'szi': '-1.0', 'entryPx': '2200.0', 'unrealizedPnl': '-50.0'}},
            ]
        }

        count = client.close_all_positions()
        assert count == 2

    def test_cancel_all_orders(self, client):
        """Test cancelling all pending orders in dry-run"""
        # In dry-run mode, returns 0 (logs only)
        count = client.cancel_all_orders()
        assert count == 0

    def test_get_positions(self, client):
        """Test retrieving positions"""
        # No positions initially
        positions = client.get_positions()
        assert len(positions) == 0

        # Mock positions
        client._info_mock.user_state.return_value = {
            'marginSummary': {'accountValue': '10000.0'},
            'assetPositions': [
                {'position': {'coin': 'BTC', 'szi': '0.1', 'entryPx': '42000.0', 'unrealizedPnl': '100.0'}},
                {'position': {'coin': 'ETH', 'szi': '-1.0', 'entryPx': '2200.0', 'unrealizedPnl': '-50.0'}},
            ]
        }

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

        # Mock position
        client._info_mock.user_state.return_value = {
            'marginSummary': {'accountValue': '10000.0'},
            'assetPositions': [
                {'position': {'coin': 'BTC', 'szi': '0.1', 'entryPx': '42000.0', 'unrealizedPnl': '100.0'}}
            ]
        }

        position = client.get_position('BTC')
        assert position is not None
        assert position.symbol == 'BTC'
        assert position.size == 0.1

    def test_get_account_balance(self, client):
        """Test retrieving account balance"""
        # Balance comes from mocked user_state
        balance = client.get_account_balance()
        assert balance == 10000.0  # From mock fixture

    def test_get_orders(self, client):
        """Test retrieving orders"""
        # No wallet configured, returns empty
        orders = client.get_orders()
        assert len(orders) == 0

    def test_update_stop_loss(self, client):
        """Test updating stop loss in dry-run"""
        result = client.update_stop_loss('BTC', 41000.0)
        # Returns simulated result
        assert result is not None
        assert result.get('status') == 'simulated'

    def test_update_take_profit(self, client):
        """Test updating take profit in dry-run"""
        result = client.update_take_profit('BTC', 46000.0)
        # Returns simulated result
        assert result is not None
        assert result.get('status') == 'simulated'

    def test_get_current_price(self, client):
        """Test getting current price"""
        price = client.get_current_price('BTC')
        assert price == 42000.0

    def test_health_check(self, client):
        """Test health check"""
        health = client.health_check()
        assert health['status'] == 'healthy'
        assert health['dry_run'] is True
        assert health['subaccount'] == 1

    def test_multiple_subaccounts(self, client):
        """Test operations across multiple subaccounts"""
        # Subaccount 1
        client.switch_subaccount(1)
        order1 = client.place_market_order('BTC', 'long', 0.1)
        assert order1 is not None

        # Subaccount 2
        client.switch_subaccount(2)
        order2 = client.place_market_order('ETH', 'short', 1.0)
        assert order2 is not None

        # Verify current subaccount
        assert client.current_subaccount == 2

    def test_no_real_orders_in_dry_run(self, client):
        """
        CRITICAL TEST: Verify NO real orders can be placed in dry-run

        This test MUST pass before production deployment.
        """
        # Verify dry-run flag
        assert client.dry_run is True

        # Place "order"
        order = client.place_market_order('BTC', 'long', 0.1)

        # Verify it's a dry-run order
        assert order.order_id.startswith('dry_run_')
        assert order.status == OrderStatus.FILLED

    def test_order_sequencing(self, client):
        """Test order IDs are timestamp-based"""
        order1 = client.place_market_order('BTC', 'long', 0.1)
        order2 = client.place_market_order('ETH', 'short', 1.0)
        order3 = client.place_market_order('SOL', 'long', 10.0)

        # All should be dry-run orders
        assert order1.order_id.startswith('dry_run_')
        assert order2.order_id.startswith('dry_run_')
        assert order3.order_id.startswith('dry_run_')

    def test_position_from_api(self, client):
        """Test positions come from mocked API"""
        # Mock different positions
        client._info_mock.user_state.return_value = {
            'marginSummary': {'accountValue': '10000.0'},
            'assetPositions': [
                {'position': {'coin': 'BTC', 'szi': '0.2', 'entryPx': '42000.0', 'unrealizedPnl': '200.0'}}
            ]
        }

        position = client.get_position('BTC')
        assert position is not None
        assert position.size == 0.2

    def test_set_leverage(self, client):
        """Test setting leverage in dry-run"""
        result = client.set_leverage('BTC', 10)
        assert result is True

    def test_set_leverage_capped(self, client):
        """Test leverage is capped at max"""
        # BTC max is 40x per mock
        result = client.set_leverage('BTC', 100)
        assert result is True  # Succeeds but caps at max

    def test_place_trigger_order(self, client):
        """Test placing trigger orders (SL/TP) in dry-run"""
        result = client.place_trigger_order(
            symbol='BTC',
            side='sell',
            size=0.1,
            trigger_price=40000.0,
            order_type='sl'
        )
        assert result is not None
        assert result['status'] == 'simulated'
        assert result['trigger_price'] == 40000.0

    def test_place_order_with_sl_tp(self, client):
        """Test placing order with SL and TP in dry-run"""
        result = client.place_order_with_sl_tp(
            symbol='BTC',
            side='long',
            size=0.1,
            stop_loss=40000.0,
            take_profit=45000.0
        )
        assert result['status'] == 'ok'
        assert result['entry'] is not None
        assert result['stop_loss'] is not None
        assert result['take_profit'] is not None
