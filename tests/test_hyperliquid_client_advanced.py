"""
Test advanced HyperliquidClient features:
- Trigger orders (SL/TP)
- Cancel orders
- Update SL/TP (trailing stop support)
- Place order with SL/TP

All tests run in dry-run mode.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.executor.hyperliquid_client import HyperliquidClient, Order, OrderStatus


class TestHyperliquidClientAdvanced:
    """Test advanced trading features"""

    @pytest.fixture
    def client(self):
        """Create a dry-run client for testing"""
        return HyperliquidClient(dry_run=True)

    def test_place_trigger_order_sl(self, client):
        """Test placing a Stop Loss trigger order"""
        result = client.place_trigger_order(
            symbol="BTC",
            side="sell",
            size=0.01,
            trigger_price=95000.0,
            order_type="sl"
        )

        assert result is not None
        assert result["status"] == "simulated"
        assert result["symbol"] == "BTC"
        assert result["order_type"] == "sl"
        assert result["trigger_price"] == 95000.0
        assert result["side"] == "sell"
        assert result["size"] == 0.01

    def test_place_trigger_order_tp(self, client):
        """Test placing a Take Profit trigger order"""
        result = client.place_trigger_order(
            symbol="ETH",
            side="sell",
            size=0.5,
            trigger_price=4500.0,
            order_type="tp"
        )

        assert result is not None
        assert result["status"] == "simulated"
        assert result["symbol"] == "ETH"
        assert result["order_type"] == "tp"
        assert result["trigger_price"] == 4500.0

    def test_place_trigger_order_invalid_type(self, client):
        """Test that invalid order type is rejected"""
        result = client.place_trigger_order(
            symbol="BTC",
            side="sell",
            size=0.01,
            trigger_price=95000.0,
            order_type="invalid"  # Should fail
        )

        assert result is None

    def test_cancel_order_dry_run(self, client):
        """Test canceling an order in dry-run mode"""
        result = client.cancel_order(symbol="BTC", order_id="12345")

        assert result is True

    def test_update_stop_loss_dry_run(self, client):
        """Test updating stop loss (core of trailing stop)"""
        result = client.update_stop_loss(
            symbol="BTC",
            new_stop_loss=96000.0,
            old_order_id=None,
            size=0.01
        )

        assert result is not None
        assert result["status"] == "simulated"
        assert result["trigger_price"] == 96000.0

    def test_update_take_profit_dry_run(self, client):
        """Test updating take profit"""
        result = client.update_take_profit(
            symbol="ETH",
            new_take_profit=5000.0,
            old_order_id=None,
            size=0.5
        )

        assert result is not None
        assert result["status"] == "simulated"
        assert result["trigger_price"] == 5000.0

    def test_place_order_with_sl_tp(self, client):
        """Test placing market order with SL and TP"""
        result = client.place_order_with_sl_tp(
            symbol="BTC",
            side="long",
            size=0.01,
            stop_loss=95000.0,
            take_profit=105000.0
        )

        assert result is not None
        assert result["status"] == "ok"

        # Entry order
        assert result["entry"] is not None
        assert result["entry"]["side"] == "long"
        assert result["entry"]["size"] == 0.01

        # Stop Loss
        assert result["stop_loss"] is not None
        assert result["stop_loss"]["order_type"] == "sl"
        assert result["stop_loss"]["trigger_price"] == 95000.0

        # Take Profit
        assert result["take_profit"] is not None
        assert result["take_profit"]["order_type"] == "tp"
        assert result["take_profit"]["trigger_price"] == 105000.0

    def test_place_order_with_sl_only(self, client):
        """Test placing order with only SL (no TP)"""
        result = client.place_order_with_sl_tp(
            symbol="SOL",
            side="short",
            size=1.0,
            stop_loss=220.0,
            take_profit=None  # No TP
        )

        assert result is not None
        assert result["status"] == "ok"
        assert result["entry"] is not None
        assert result["stop_loss"] is not None
        assert result["take_profit"] is None

    def test_place_order_with_tp_only(self, client):
        """Test placing order with only TP (no SL)"""
        result = client.place_order_with_sl_tp(
            symbol="ARB",
            side="long",
            size=100.0,
            stop_loss=None,  # No SL
            take_profit=1.50
        )

        assert result is not None
        assert result["status"] == "ok"
        assert result["entry"] is not None
        assert result["stop_loss"] is None
        assert result["take_profit"] is not None

    def test_place_order_no_protection(self, client):
        """Test placing order without SL or TP"""
        result = client.place_order_with_sl_tp(
            symbol="ETH",
            side="long",
            size=0.1,
            stop_loss=None,
            take_profit=None
        )

        assert result is not None
        assert result["status"] == "ok"
        assert result["entry"] is not None
        assert result["stop_loss"] is None
        assert result["take_profit"] is None

    def test_symbol_normalization(self, client):
        """Test that various symbol formats are normalized"""
        # All should work the same
        symbols = ["BTC", "BTC-USDC", "BTC/USDC:USDC"]

        for symbol in symbols:
            result = client.place_trigger_order(
                symbol=symbol,
                side="sell",
                size=0.01,
                trigger_price=95000.0,
                order_type="sl"
            )
            assert result is not None
            assert result["symbol"] == "BTC"

    def test_side_normalization(self, client):
        """Test that various side formats are normalized"""
        # Test long/buy normalization
        result = client.place_market_order(
            symbol="BTC",
            side="buy",  # Should be converted to 'long'
            size=0.01
        )
        assert result.side == "long"

        result = client.place_market_order(
            symbol="BTC",
            side="sell",  # Should be converted to 'short'
            size=0.01
        )
        assert result.side == "short"

    def test_round_size(self, client):
        """Test size rounding based on asset decimals"""
        # BTC typically has sz_decimals=5
        rounded = client.round_size("BTC", 0.123456789)
        # Should be rounded to sz_decimals
        assert isinstance(rounded, float)

    def test_round_price(self, client):
        """Test price rounding based on price level"""
        # High price (>10000) -> 1 decimal
        assert client.round_price(50123.456) == 50123.5

        # Medium price (1000-10000) -> 2 decimals
        assert client.round_price(3456.789) == 3456.79

        # Low price (100-1000) -> 3 decimals
        assert client.round_price(234.5678) == 234.568

        # Very low price (<1) -> 6 decimals
        assert client.round_price(0.123456789) == 0.123457


class TestTrailingStopSimulation:
    """Test trailing stop logic (simulated)"""

    @pytest.fixture
    def client(self):
        """Create a dry-run client for testing"""
        return HyperliquidClient(dry_run=True)

    def test_trailing_stop_workflow(self, client):
        """Simulate a complete trailing stop workflow"""
        # 1. Open position with initial SL
        entry_result = client.place_order_with_sl_tp(
            symbol="BTC",
            side="long",
            size=0.01,
            stop_loss=95000.0,  # Initial SL at $95k
            take_profit=None
        )
        assert entry_result["status"] == "ok"
        initial_sl_id = entry_result["stop_loss"]["order_id"]

        # 2. Price moves up, trail the stop (cancel old, place new)
        # In dry-run, we simulate the workflow

        # Cancel old SL
        cancelled = client.cancel_order("BTC", initial_sl_id)
        assert cancelled is True

        # Place new higher SL
        new_sl_result = client.place_trigger_order(
            symbol="BTC",
            side="sell",
            size=0.01,
            trigger_price=97000.0,  # Trail up to $97k
            order_type="sl"
        )
        assert new_sl_result is not None
        assert new_sl_result["trigger_price"] == 97000.0

        # 3. Use update_stop_loss helper (combines cancel + place)
        final_result = client.update_stop_loss(
            symbol="BTC",
            new_stop_loss=98500.0,  # Trail to $98.5k
            old_order_id=None,  # In dry-run, already simulated
            size=0.01
        )
        assert final_result is not None
        assert final_result["trigger_price"] == 98500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
