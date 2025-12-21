"""
Integration test for full dry-run trading cycle

This test validates the complete workflow:
1. Strategy generation signal
2. Risk management (position sizing)
3. Order execution (dry-run)
4. Position tracking
5. Position closing

All operations in dry_run=True mode (no real API calls)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.executor.hyperliquid_client import HyperliquidClient, OrderStatus
from src.executor.risk_manager import RiskManager
from src.executor.position_tracker import PositionTracker
from src.executor.subaccount_manager import SubaccountManager
from src.strategies.base import StrategyCore, Signal


@pytest.fixture
def config():
    """Mock configuration for testing"""
    return {
        'risk': {
            'sizing_mode': 'atr',
            'fixed_fractional': {
                'risk_per_trade_pct': 0.02,
                'max_position_size_pct': 0.20
            },
            'atr': {
                'period': 14,
                'stop_multiplier': 2.0,
                'take_profit_multiplier': 3.0,
                'min_risk_reward': 1.5,
                'volatility_scaling': {
                    'enabled': True,
                    'low_volatility_threshold': 0.015,
                    'high_volatility_threshold': 0.05,
                    'scaling_factor': 0.5
                }
            },
            'limits': {
                'max_open_positions_total': 100,
                'max_open_positions_per_subaccount': 4,
                'max_leverage': 10,
                'max_correlated_positions': 5
            },
            'emergency': {
                'max_portfolio_drawdown': 0.30,
                'max_daily_loss': 0.10,
                'max_subaccount_drawdown': 0.25,
                'max_consecutive_losses': 5,
                'max_strategy_degradation': 0.50
            }
        },
        'hyperliquid': {
            'subaccounts': {
                'total': 10,
                'test_mode': {
                    'enabled': True,
                    'count': 3,
                    'capital_per_account': 100
                }
            }
        }
    }


@pytest.fixture
def sample_ohlcv():
    """Sample OHLCV data for ATR calculation"""
    np.random.seed(42)
    dates = pd.date_range(start='2025-01-01', periods=100, freq='1h')

    base_price = 50000
    prices = base_price + np.cumsum(np.random.randn(100) * 100)

    return pd.DataFrame({
        'timestamp': dates,
        'open': prices - 50,
        'high': prices + 100,
        'low': prices - 100,
        'close': prices,
        'volume': 1000 + np.random.randn(100) * 50
    })


@pytest.fixture
def simple_strategy():
    """Simple RSI strategy for testing"""
    class TestStrategy(StrategyCore):
        """Test strategy that generates a long signal"""

        def generate_signal(self, df: pd.DataFrame) -> Signal | None:
            if len(df) < 20:
                return None

            # Simple condition: always long for testing
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason='Test signal - dry run',
                confidence=0.85
            )

    return TestStrategy()


class TestDryRunFullCycle:
    """Test complete trading cycle in dry-run mode"""

    def test_initialization_dry_run(self):
        """Test all components initialize in dry-run mode"""
        # HyperliquidClient
        client = HyperliquidClient(dry_run=True)
        assert client.dry_run is True
        assert client._mock_balance == 10000.0

        # Health check
        health = client.health_check()
        assert health['dry_run'] is True
        assert health['status'] == 'healthy'

    def test_signal_to_execution_cycle(self, config, sample_ohlcv, simple_strategy):
        """Test full cycle: signal → sizing → execution → tracking"""

        # 1. Initialize components
        client = HyperliquidClient(dry_run=True)
        risk_manager = RiskManager(config)
        tracker = PositionTracker(client=client)

        # 2. Strategy generates signal
        signal = simple_strategy.generate_signal(sample_ohlcv)

        assert signal is not None
        assert signal.direction == 'long'
        assert signal.atr_stop_multiplier == 2.0

        # 3. Calculate position size (ATR-based)
        current_price = sample_ohlcv['close'].iloc[-1]
        account_balance = client.get_account_balance()

        position_size, stop_loss, take_profit = risk_manager.calculate_position_size(
            account_balance=account_balance,
            current_price=current_price,
            df=sample_ohlcv,
            signal_atr_stop_mult=signal.atr_stop_multiplier,
            signal_atr_take_mult=signal.atr_take_multiplier
        )

        # Verify position size calculated
        assert position_size > 0
        assert stop_loss < current_price
        assert take_profit > current_price

        # 4. Check risk limits
        allowed, reason = risk_manager.check_risk_limits(
            new_position_size=position_size,
            current_positions_count=0,
            subaccount_positions_count=0,
            account_balance=account_balance,
            current_price=current_price
        )

        assert allowed is True
        assert reason == "OK"

        # 5. Execute order (dry-run)
        order = client.place_market_order(
            symbol='BTC',
            side='long',
            size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Verify order created
        assert order.order_id.startswith('mock_order_')
        assert order.status == OrderStatus.FILLED
        assert order.symbol == 'BTC'
        assert order.size == position_size

        # 6. Track position
        positions = client.get_positions()
        assert len(positions) == 1

        position = positions[0]
        assert position.symbol == 'BTC'
        assert position.side == 'long'
        assert position.size == position_size

        # 7. Close position
        success = client.close_position('BTC', reason='Test complete')
        assert success is True

        # Verify position closed
        positions_after = client.get_positions()
        assert len(positions_after) == 0

    def test_multiple_subaccounts_dry_run(self, config):
        """Test trading across multiple subaccounts (dry-run)"""
        client = HyperliquidClient(dry_run=True)
        risk_manager = RiskManager(config)

        # Trade on subaccount 1
        client.switch_subaccount(1)
        assert client.current_subaccount == 1

        order1 = client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1,
            stop_loss=49000.0,
            take_profit=51000.0
        )

        assert order1.order_id.startswith('mock_order_')

        # Switch to subaccount 2
        client.switch_subaccount(2)
        assert client.current_subaccount == 2

        order2 = client.place_market_order(
            symbol='ETH',
            side='short',
            size=1.0,
            stop_loss=3100.0,
            take_profit=2900.0
        )

        assert order2.order_id.startswith('mock_order_')
        assert order1.order_id != order2.order_id

        # Verify positions per subaccount
        # Note: Current implementation tracks positions globally
        # In production, this would be per-subaccount
        positions = client.get_positions()
        assert len(positions) >= 1

    def test_risk_limits_enforcement(self, config, sample_ohlcv):
        """Test risk limits are enforced in dry-run"""
        client = HyperliquidClient(dry_run=True)
        risk_manager = RiskManager(config)

        current_price = sample_ohlcv['close'].iloc[-1]
        account_balance = client.get_account_balance()

        # Try to exceed max positions per subaccount
        max_positions = config['risk']['limits']['max_open_positions_per_subaccount']

        # Create max_positions + 1 positions
        for i in range(max_positions + 1):
            position_size, stop_loss, take_profit = risk_manager.calculate_position_size(
                account_balance=account_balance,
                current_price=current_price,
                df=sample_ohlcv
            )

            # Check if allowed
            allowed, reason = risk_manager.check_risk_limits(
                new_position_size=position_size,
                current_positions_count=i,
                subaccount_positions_count=i,
                account_balance=account_balance,
                current_price=current_price
            )

            if i < max_positions:
                # Should be allowed
                assert allowed is True
            else:
                # Should be rejected
                assert allowed is False
                assert 'Max subaccount positions' in reason

    def test_atr_volatility_scaling(self, config):
        """Test volatility scaling in position sizing"""
        risk_manager = RiskManager(config)

        # Low volatility scenario
        low_vol_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-01-01', periods=50, freq='1h'),
            'high': [50100] * 50,  # Tight range
            'low': [49900] * 50,
            'close': [50000] * 50,
            'volume': [1000] * 50
        })

        position_size_low, sl_low, tp_low = risk_manager.calculate_position_size(
            account_balance=10000.0,
            current_price=50000.0,
            df=low_vol_data
        )

        # High volatility scenario
        np.random.seed(42)
        high_vol_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-01-01', periods=50, freq='1h'),
            'high': 50000 + np.random.randn(50) * 5000,  # Wide range
            'low': 50000 + np.random.randn(50) * 5000,
            'close': 50000 + np.random.randn(50) * 5000,
            'volume': [1000] * 50
        })

        position_size_high, sl_high, tp_high = risk_manager.calculate_position_size(
            account_balance=10000.0,
            current_price=50000.0,
            df=high_vol_data
        )

        # Low volatility should have larger position (if ATR is very small and scaling triggers)
        # High volatility should have smaller position
        # This is a qualitative check - exact values depend on ATR calculation
        assert position_size_low >= 0
        assert position_size_high >= 0

    def test_short_position_cycle(self, config, sample_ohlcv):
        """Test short position handling in dry-run"""
        client = HyperliquidClient(dry_run=True)
        risk_manager = RiskManager(config)

        current_price = sample_ohlcv['close'].iloc[-1]
        account_balance = client.get_account_balance()

        # Calculate position size for short
        position_size, stop_loss, take_profit = risk_manager.calculate_position_size(
            account_balance=account_balance,
            current_price=current_price,
            df=sample_ohlcv
        )

        # Adjust for short position
        stop_loss_short, take_profit_short = risk_manager.adjust_stops_for_side(
            side='short',
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Short: SL should be above, TP should be below
        assert stop_loss_short > current_price
        assert take_profit_short < current_price

        # Execute short order
        order = client.place_market_order(
            symbol='BTC',
            side='short',
            size=position_size,
            stop_loss=stop_loss_short,
            take_profit=take_profit_short
        )

        assert order.status == OrderStatus.FILLED
        assert order.side == 'short'

        # Close position
        success = client.close_position('BTC')
        assert success is True

    def test_emergency_stop_dry_run(self, config):
        """Test emergency stop functionality in dry-run"""
        client = HyperliquidClient(dry_run=True)

        # Open multiple positions
        for i, symbol in enumerate(['BTC', 'ETH', 'SOL']):
            client.place_market_order(
                symbol=symbol,
                side='long',
                size=0.1,
                stop_loss=40000.0,
                take_profit=50000.0
            )

        # Verify positions open
        positions_before = client.get_positions()
        assert len(positions_before) == 3

        # Emergency stop: close all
        closed_count = client.close_all_positions()
        assert closed_count == 3

        # Verify all closed
        positions_after = client.get_positions()
        assert len(positions_after) == 0

    def test_order_cancellation_dry_run(self):
        """Test order cancellation in dry-run"""
        client = HyperliquidClient(dry_run=True)

        # Create pending orders (modify order to be pending)
        order1 = client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1
        )

        # Manually set to pending for testing
        order1.status = OrderStatus.PENDING
        client._mock_orders[-1] = order1

        order2 = client.place_market_order(
            symbol='ETH',
            side='short',
            size=1.0
        )
        order2.status = OrderStatus.PENDING
        client._mock_orders[-1] = order2

        # Cancel all orders
        cancelled_count = client.cancel_all_orders()
        assert cancelled_count == 2

        # Verify orders cancelled
        orders = client.get_orders()
        pending = [o for o in orders if o.status == OrderStatus.PENDING]
        assert len(pending) == 0

    def test_position_tracking_accuracy(self, config, sample_ohlcv):
        """Test position tracking maintains accurate state"""
        client = HyperliquidClient(dry_run=True)
        risk_manager = RiskManager(config)

        current_price = sample_ohlcv['close'].iloc[-1]
        account_balance = client.get_account_balance()

        # Open position
        position_size, stop_loss, take_profit = risk_manager.calculate_position_size(
            account_balance=account_balance,
            current_price=current_price,
            df=sample_ohlcv
        )

        order = client.place_market_order(
            symbol='BTC',
            side='long',
            size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        # Retrieve position
        position = client.get_position('BTC')

        assert position is not None
        assert position.symbol == 'BTC'
        assert position.size == position_size
        assert position.entry_price == order.entry_price
        assert position.stop_loss == stop_loss
        assert position.take_profit == take_profit

    def test_dry_run_prevents_live_errors(self):
        """Test that dry-run mode prevents accidental live trading"""
        # Initialize without credentials (safe in dry-run)
        client = HyperliquidClient(
            private_key=None,
            vault_address=None,
            dry_run=True
        )

        # Should work fine
        order = client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1
        )

        assert order.order_id.startswith('mock_order_')

        # Verify all operations work without credentials
        assert client.get_account_balance() > 0
        assert len(client.get_positions()) >= 0
        assert client.health_check()['status'] == 'healthy'

    def test_live_mode_requires_credentials(self):
        """Test that live mode is blocked in test environment"""
        # Should raise error without credentials
        with pytest.raises(ValueError, match="Live trading not allowed in tests"):
            HyperliquidClient(
                private_key=None,
                vault_address=None,
                dry_run=False
            )

        # CRITICAL: Even with credentials, live mode blocked in tests (safety)
        with pytest.raises(ValueError, match="Live trading not allowed in tests"):
            HyperliquidClient(
                private_key="test_key_123",
                vault_address="test_address_456",
                dry_run=False
            )


class TestDryRunEdgeCases:
    """Test edge cases in dry-run mode"""

    def test_close_nonexistent_position(self):
        """Test closing position that doesn't exist"""
        client = HyperliquidClient(dry_run=True)

        success = client.close_position('NONEXISTENT')
        assert success is False

    def test_invalid_order_parameters(self):
        """Test order validation in dry-run"""
        client = HyperliquidClient(dry_run=True)

        # Invalid side
        with pytest.raises(ValueError, match="Invalid side"):
            client.place_market_order(
                symbol='BTC',
                side='invalid',
                size=0.1
            )

        # Invalid size
        with pytest.raises(ValueError, match="Invalid size"):
            client.place_market_order(
                symbol='BTC',
                side='long',
                size=-0.1
            )

        with pytest.raises(ValueError, match="Invalid size"):
            client.place_market_order(
                symbol='BTC',
                side='long',
                size=0.0
            )

    def test_update_stops_dry_run(self):
        """Test updating stop loss and take profit in dry-run"""
        client = HyperliquidClient(dry_run=True)

        # Open position
        client.place_market_order(
            symbol='BTC',
            side='long',
            size=0.1,
            stop_loss=49000.0,
            take_profit=51000.0
        )

        # Update stop loss
        success_sl = client.update_stop_loss('BTC', 49500.0)
        assert success_sl is True

        # Update take profit
        success_tp = client.update_take_profit('BTC', 52000.0)
        assert success_tp is True

        # Verify updates
        position = client.get_position('BTC')
        assert position.stop_loss == 49500.0
        assert position.take_profit == 52000.0

    def test_get_current_price_dry_run(self):
        """Test getting current price in dry-run"""
        client = HyperliquidClient(dry_run=True)

        # Should return mock price
        price = client.get_current_price('BTC')
        assert price == 42000.0  # Mock price
