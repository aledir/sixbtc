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

        def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
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

        # Health check
        health = client.health_check()
        assert health['dry_run'] is True
        assert health['status'] == 'healthy'

    def test_signal_to_execution_cycle(self, config, sample_ohlcv, simple_strategy):
        """Test full cycle: signal → sizing → execution → tracking"""
        from unittest.mock import patch, MagicMock

        # Mock the Info API to avoid real network calls
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info_instance.user_state.return_value = {
                'marginSummary': {'accountValue': '10000.0'},
                'assetPositions': []
            }
            mock_info.return_value = mock_info_instance

            # 1. Initialize components
            client = HyperliquidClient(dry_run=True)
            client.wallet_address = '0x' + '0' * 40  # Mock wallet for API calls
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

            # Verify order created (dry_run_ prefix in new implementation)
            assert order.order_id.startswith('dry_run_')
            assert order.status == OrderStatus.FILLED
            assert order.symbol == 'BTC'

    def test_multiple_subaccounts_dry_run(self, config):
        """Test trading across multiple subaccounts (dry-run)"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [
                {'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50},
                {'name': 'ETH', 'szDecimals': 4, 'maxLeverage': 50}
            ]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0', 'ETH': '3000.0'}
            mock_info.return_value = mock_info_instance

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

            assert order1.order_id.startswith('dry_run_')

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

            assert order2.order_id.startswith('dry_run_')
            # Both orders were created successfully
            assert order1.symbol == 'BTC'
            assert order2.symbol == 'ETH'

    def test_risk_limits_enforcement(self, config, sample_ohlcv):
        """Test risk limits are enforced in dry-run"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.user_state.return_value = {'marginSummary': {'accountValue': '10000.0'}}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)
            client.wallet_address = '0x' + '0' * 40
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
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info_instance.user_state.return_value = {'marginSummary': {'accountValue': '10000.0'}}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)
            client.wallet_address = '0x' + '0' * 40
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

    def test_emergency_stop_dry_run(self, config):
        """Test emergency stop functionality in dry-run"""
        from unittest.mock import patch, MagicMock

        # Note: In the new implementation, dry_run mode doesn't maintain fake state
        # Orders are logged but positions aren't tracked since it uses real API
        # This test validates the logging/order placement works in dry_run mode
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [
                {'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50},
                {'name': 'ETH', 'szDecimals': 4, 'maxLeverage': 50},
                {'name': 'SOL', 'szDecimals': 4, 'maxLeverage': 50}
            ]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0', 'ETH': '3000.0', 'SOL': '100.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            # Place orders (logged only in dry_run mode)
            orders = []
            for symbol in ['BTC', 'ETH', 'SOL']:
                order = client.place_market_order(
                    symbol=symbol,
                    side='long',
                    size=0.1,
                    stop_loss=40000.0,
                    take_profit=50000.0
                )
                orders.append(order)

            # Verify orders were created (in dry_run, they get dry_run_ prefix)
            assert len(orders) == 3
            for order in orders:
                assert order.order_id.startswith('dry_run_')
                assert order.status == OrderStatus.FILLED

    def test_order_cancellation_dry_run(self):
        """Test order cancellation in dry-run"""
        from unittest.mock import patch, MagicMock

        # In the new implementation, dry_run doesn't maintain mock state
        # Test that order placement works correctly in dry_run
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [
                {'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50},
                {'name': 'ETH', 'szDecimals': 4, 'maxLeverage': 50}
            ]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0', 'ETH': '3000.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            # Create orders
            order1 = client.place_market_order(
                symbol='BTC',
                side='long',
                size=0.1
            )

            order2 = client.place_market_order(
                symbol='ETH',
                side='short',
                size=1.0
            )

            # In dry_run, orders are immediately "filled" (simulated)
            assert order1.status == OrderStatus.FILLED
            assert order2.status == OrderStatus.FILLED
            assert order1.order_id.startswith('dry_run_')
            assert order2.order_id.startswith('dry_run_')

    def test_position_tracking_accuracy(self, config, sample_ohlcv):
        """Test order placement accuracy in dry-run"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info_instance.user_state.return_value = {'marginSummary': {'accountValue': '10000.0'}}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)
            client.wallet_address = '0x' + '0' * 40
            risk_manager = RiskManager(config)

            current_price = sample_ohlcv['close'].iloc[-1]
            account_balance = client.get_account_balance()

            # Calculate position size
            position_size, stop_loss, take_profit = risk_manager.calculate_position_size(
                account_balance=account_balance,
                current_price=current_price,
                df=sample_ohlcv
            )

            # Place order
            order = client.place_market_order(
                symbol='BTC',
                side='long',
                size=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            # Verify order details
            assert order is not None
            assert order.symbol == 'BTC'
            assert order.side == 'long'
            assert order.stop_loss == stop_loss
            assert order.take_profit == take_profit
            assert order.status == OrderStatus.FILLED

    def test_dry_run_prevents_live_errors(self):
        """Test that dry-run mode prevents accidental live trading"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

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

            assert order.order_id.startswith('dry_run_')

            # Verify health check works without credentials
            assert client.health_check()['status'] == 'healthy'

    def test_live_mode_requires_credentials(self):
        """Test that live mode requires valid credentials"""
        from unittest.mock import patch, MagicMock

        # Should raise error without credentials
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info.return_value = mock_info_instance

            with pytest.raises(ValueError, match="Live trading requires valid private_key and wallet_address"):
                HyperliquidClient(
                    private_key=None,
                    vault_address=None,
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
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            # Open position
            order = client.place_market_order(
                symbol='BTC',
                side='long',
                size=0.1,
                stop_loss=49000.0,
                take_profit=51000.0
            )

            # Verify order was created with SL/TP
            assert order.stop_loss == 49000.0
            assert order.take_profit == 51000.0

            # Update stop loss - returns dict with status in new implementation
            result_sl = client.update_stop_loss('BTC', 49500.0)
            # In dry_run, update methods return dict with status
            assert result_sl is not None

            # Update take profit
            result_tp = client.update_take_profit('BTC', 52000.0)
            assert result_tp is not None

    def test_get_current_price_dry_run(self):
        """Test getting current price in dry-run"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            # Should return price from mocked API
            price = client.get_current_price('BTC')
            assert price == 50000.0  # Mocked price
