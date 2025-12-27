"""
Tests for executor module

Validates:
- Hyperliquid client operations (DRY RUN ONLY)
- Subaccount management
- Position tracking
- Risk management
- Order execution (simulated)

CRITICAL: All tests use dry_run=True - NO REAL TRADES
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.subaccount_manager import SubaccountManager
from src.executor.position_tracker import PositionTracker
from src.executor.risk_manager import RiskManager
from src.strategies.base import Signal



@pytest.fixture
def mock_config():
    """Mock configuration - DRY RUN MODE"""
    return {
        'executor': {
            'dry_run': True,  # CRITICAL: Always True in tests
            'hyperliquid': {
                'api_key': 'test_key',
                'secret_key': 'test_secret',
                'testnet': True,
                'subaccounts': {
                    'total': 10,
                    'test_mode': {
                        'enabled': True,
                        'count': 3,
                        'capital_per_account': 100
                    }
                }
            },
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
                    'max_leverage': 10
                },
                'emergency': {
                    'max_portfolio_drawdown': 0.30,
                    'max_subaccount_drawdown': 0.25,
                    'max_consecutive_losses': 5
                }
            }
        }
    }


@pytest.fixture
def mock_account_state():
    """Mock Hyperliquid account state"""
    return {
        'marginSummary': {
            'accountValue': '1000.0',
            'totalNtlPos': '500.0',
            'totalRawUsd': '1000.0',
            'withdrawable': '500.0'
        },
        'assetPositions': [
            {
                'position': {
                    'coin': 'BTC',
                    'entryPx': '50000.0',
                    'leverage': {
                        'value': 5,
                        'type': 'cross'
                    },
                    'liquidationPx': '45000.0',
                    'marginUsed': '100.0',
                    'positionValue': '500.0',
                    'returnOnEquity': '0.05',
                    'szi': '0.01',  # Size: 0.01 BTC
                    'unrealizedPnl': '25.0'
                },
                'type': 'oneWay'
            }
        ]
    }


class TestHyperliquidClient:
    """Test Hyperliquid client operations - DRY RUN ONLY"""

    # Enabled
    def test_initialization_dry_run(self, mock_config):
        """Test client initialization in dry-run mode"""
        client = HyperliquidClient(mock_config['executor'])

        assert client.dry_run is True
        assert client.testnet is True

    # Enabled
    def test_initialization_fails_without_dry_run(self, mock_config):
        """Test that live mode is blocked in tests without credentials"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info.return_value = mock_info_instance

            # Should raise error when trying live mode without credentials
            with pytest.raises(ValueError, match="Live trading requires valid private_key and wallet_address"):
                HyperliquidClient(dry_run=False)

    def test_get_account_state(self, mock_config):
        """Test fetching account state in dry-run mode"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info_instance.user_state.return_value = {
                'marginSummary': {'accountValue': '10000.0'},
                'assetPositions': []
            }
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(mock_config['executor'])
            state = client.get_account_state('0x123')

            assert state['marginSummary']['accountValue'] == '10000.0'
            assert 'assetPositions' in state
            assert isinstance(state['assetPositions'], list)

    def test_get_open_positions(self, mock_config):
        """Test getting open positions in dry-run mode"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info_instance.user_state.return_value = {
                'marginSummary': {'accountValue': '10000.0'},
                'assetPositions': [{
                    'position': {
                        'coin': 'BTC',
                        'szi': '0.01',
                        'entryPx': '50000.0',
                        'unrealizedPnl': '0.0'
                    }
                }]
            }
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(mock_config['executor'])
            client.wallet_address = '0x123'  # Set wallet for position queries

            positions = client.get_open_positions('0x123')

            assert len(positions) == 1
            assert positions[0]['coin'] == 'BTC'
            assert float(positions[0]['szi']) == 0.01

    # Enabled
    def test_place_order_dry_run(self, mock_config):
        """Test order placement in dry-run mode"""
        client = HyperliquidClient(mock_config['executor'])

        result = client.place_order(
            symbol='BTC',
            side='buy',
            size=0.01,
            order_type='market',
            dry_run=True
        )

        # In dry-run, should return simulated result
        assert result['status'] == 'simulated'
        assert result['symbol'] == 'BTC'
        assert result['size'] == 0.01
        assert 'order_id' in result

    # Enabled
    def test_place_order_blocks_live_mode(self, mock_config):
        """Test that live orders fail without exchange client"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [
                {'name': 'BTC', 'szDecimals': 5, 'maxLeverage': 40}
            ]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

            # Client in dry_run mode has no exchange_client
            client = HyperliquidClient(mock_config['executor'])
            assert client.exchange_client is None

            # Attempting live order (dry_run=False) should fail gracefully
            result = client.place_order(
                symbol='BTC',
                side='buy',
                size=0.01,
                order_type='market',
                dry_run=False  # Attempt live order without exchange client
            )

            # Should return error (not raise exception for graceful handling)
            assert result['status'] == 'error'

    def test_get_market_data(self, mock_config):
        """Test fetching market data"""
        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info_instance.all_mids.return_value = {
                'BTC': '50000.0',
                'ETH': '3000.0'
            }
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(mock_config['executor'])
            prices = client.get_current_prices()

            # Verify we get a dict with BTC and ETH prices
            assert 'BTC' in prices
            assert 'ETH' in prices
            assert prices['BTC'] == 50000.0
            assert prices['ETH'] == 3000.0


class TestSubaccountManager:
    """Test subaccount management"""

    # Enabled
    def test_initialization(self, mock_config):
        """Test subaccount manager initialization"""
        manager = SubaccountManager(mock_config['executor'])

        assert manager.total_subaccounts == 10
        assert manager.active_subaccounts == 3
        assert manager.capital_per_account == 100

    @patch.object(HyperliquidClient, 'get_account_state')
    # Enabled
    def test_get_subaccount_balance(self, mock_get_state, mock_config, mock_account_state):
        """Test getting subaccount balance"""
        mock_get_state.return_value = mock_account_state

        manager = SubaccountManager(mock_config['executor'])
        balance = manager.get_subaccount_balance(subaccount_id=1)

        assert balance == 1000.0

    @patch.object(HyperliquidClient, 'get_open_positions')
    # Enabled
    def test_get_subaccount_positions(self, mock_get_positions, mock_config):
        """Test getting subaccount positions"""
        mock_get_positions.return_value = [
            {'coin': 'BTC', 'szi': '0.01', 'entryPx': '50000.0'}
        ]

        manager = SubaccountManager(mock_config['executor'])
        positions = manager.get_subaccount_positions(subaccount_id=1)

        assert len(positions) == 1
        assert positions[0]['coin'] == 'BTC'

    # Enabled
    def test_assign_strategy_to_subaccount(self, mock_config):
        """Test assigning strategy to subaccount"""
        manager = SubaccountManager(mock_config['executor'])

        success = manager.assign_strategy(
            subaccount_id=1,
            strategy_id='Strategy_MOM_001'
        )

        assert success is True
        assert manager.subaccount_strategies[1] == 'Strategy_MOM_001'

    # Enabled
    def test_prevent_duplicate_assignment(self, mock_config):
        """Test preventing duplicate strategy assignment"""
        manager = SubaccountManager(mock_config['executor'])

        # First assignment succeeds
        manager.assign_strategy(1, 'Strategy_MOM_001')

        # Second assignment to same subaccount should fail
        success = manager.assign_strategy(1, 'Strategy_MOM_002')

        assert success is False


class TestPositionTracker:
    """Test position tracking"""

    # Enabled
    def test_open_position(self, mock_config):
        """Test opening position"""
        tracker = PositionTracker()

        position = tracker.open_position(
            strategy_id='Strategy_MOM_001',
            symbol='BTC',
            side='long',
            size=0.01,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=54000.0
        )

        assert position['symbol'] == 'BTC'
        assert position['side'] == 'long'
        assert position['size'] == 0.01
        assert position['status'] == 'open'

    # Enabled
    def test_close_position(self, mock_config):
        """Test closing position"""
        tracker = PositionTracker()

        # Open position
        position = tracker.open_position(
            strategy_id='Strategy_MOM_001',
            symbol='BTC',
            side='long',
            size=0.01,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=54000.0
        )

        # Close position
        closed = tracker.close_position(
            position_id=position['id'],
            exit_price=52000.0,
            reason='take_profit'
        )

        assert closed['status'] == 'closed'
        assert closed['pnl'] > 0  # Profit
        assert closed['exit_reason'] == 'take_profit'

    # Enabled
    def test_calculate_pnl(self, mock_config):
        """Test PnL calculation"""
        tracker = PositionTracker()

        # Long position - profit
        pnl_long = tracker.calculate_pnl(
            side='long',
            entry_price=50000.0,
            exit_price=52000.0,
            size=0.01
        )
        assert pnl_long == 20.0  # (52000 - 50000) * 0.01

        # Short position - profit
        pnl_short = tracker.calculate_pnl(
            side='short',
            entry_price=50000.0,
            exit_price=48000.0,
            size=0.01
        )
        assert pnl_short == 20.0  # (50000 - 48000) * 0.01

    # Enabled
    def test_get_open_positions_by_strategy(self, mock_config):
        """Test getting open positions by strategy"""
        tracker = PositionTracker()

        # Open multiple positions
        tracker.open_position('Strategy_MOM_001', 'BTC', 'long', 0.01, 50000, 48000, 54000)
        tracker.open_position('Strategy_MOM_001', 'ETH', 'long', 0.1, 3000, 2900, 3300)
        tracker.open_position('Strategy_REV_002', 'BTC', 'short', 0.01, 50000, 52000, 46000)

        # Get positions for Strategy_MOM_001
        positions = tracker.get_positions_by_strategy('Strategy_MOM_001')

        assert len(positions) == 2
        assert all(p['strategy_id'] == 'Strategy_MOM_001' for p in positions)


class TestRiskManager:
    """Test risk management"""

    # Enabled
    def test_calculate_position_size_atr(self, mock_config):
        """Test ATR-based position sizing"""
        risk_mgr = RiskManager(mock_config['executor']['risk'])

        size, stop, take = risk_mgr.calculate_position_size(
            signal=Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0
            ),
            account_balance=1000.0,
            current_price=50000.0,
            atr=1500.0
        )

        # Risk = 2% of $1000 = $20
        # Stop distance = 2 * $1500 = $3000
        # Size = $20 / $3000 = 0.00667 BTC
        # BUT: capped by max_position_size_pct (20% of $1000 = $200)
        # Max size = $200 / $50000 = 0.004 BTC
        assert size == 0.004
        assert stop == 50000.0 - 3000.0  # $47,000
        assert take == 50000.0 + (1500.0 * 3.0)  # $54,500

    # Enabled
    def test_calculate_position_size_fixed(self, mock_config):
        """Test fixed fractional position sizing"""
        risk_mgr = RiskManager(mock_config['executor']['risk'])

        size, stop, take = risk_mgr.calculate_position_size(
            signal=Signal(
                direction='long',
                stop_loss=48000.0,
                take_profit=54000.0
            ),
            account_balance=1000.0,
            current_price=50000.0,
            atr=None  # Force fixed mode
        )

        # Risk = 2% of $1000 = $20
        # Stop distance = $50000 - $48000 = $2000
        # Size = $20 / $2000 = 0.01 BTC
        # BUT: capped by max_position_size_pct (20% of $1000 = $200)
        # Max size = $200 / $50000 = 0.004 BTC
        assert size == 0.004
        assert stop == 48000.0
        assert take == 54000.0

    # Enabled
    def test_check_position_limits(self, mock_config):
        """Test position limit enforcement"""
        risk_mgr = RiskManager(mock_config['executor']['risk'])

        # Within limits
        assert risk_mgr.check_position_limit(
            current_positions=3,
            max_positions=4
        ) is True

        # Exceeds limits
        assert risk_mgr.check_position_limit(
            current_positions=5,
            max_positions=4
        ) is False

    # Enabled
    def test_check_drawdown_limit(self, mock_config):
        """Test drawdown limit checking"""
        risk_mgr = RiskManager(mock_config['executor']['risk'])

        # Within limit (20% DD)
        assert risk_mgr.check_drawdown(
            current_balance=800.0,
            peak_balance=1000.0,
            max_drawdown=0.25
        ) is True

        # Exceeds limit (35% DD)
        assert risk_mgr.check_drawdown(
            current_balance=650.0,
            peak_balance=1000.0,
            max_drawdown=0.25
        ) is False

    # Enabled
    def test_emergency_stop_trigger(self, mock_config):
        """Test emergency stop conditions"""
        risk_mgr = RiskManager(mock_config['executor']['risk'])

        # Normal operation
        assert risk_mgr.should_emergency_stop(
            portfolio_drawdown=0.15,
            consecutive_losses=3
        ) is False

        # Max drawdown exceeded
        assert risk_mgr.should_emergency_stop(
            portfolio_drawdown=0.35,
            consecutive_losses=2
        ) is True

        # Too many consecutive losses
        assert risk_mgr.should_emergency_stop(
            portfolio_drawdown=0.10,
            consecutive_losses=6
        ) is True


class TestExecutorIntegration:
    """Integration tests for executor workflow - DRY RUN ONLY"""

    @patch.object(HyperliquidClient, 'get_account_state')
    @patch.object(HyperliquidClient, 'place_order')
    # Enabled
    def test_full_trade_execution_workflow(
        self,
        mock_place_order,
        mock_get_state,
        mock_config,
        mock_account_state
    ):
        """Test complete trade execution workflow (dry-run)"""
        # Mock responses
        mock_get_state.return_value = mock_account_state
        mock_place_order.return_value = {
            'status': 'simulated',
            'order_id': 'test_order_123',
            'symbol': 'BTC',
            'size': 0.01
        }

        # 1. Initialize components
        client = HyperliquidClient(mock_config['executor'])
        subaccount_mgr = SubaccountManager(mock_config['executor'])
        risk_mgr = RiskManager(mock_config['executor']['risk'])
        position_tracker = PositionTracker()

        # 2. Assign strategy to subaccount
        subaccount_mgr.assign_strategy(1, 'Strategy_MOM_001')

        # 3. Calculate position size
        signal = Signal(
            direction='long',
            atr_stop_multiplier=2.0,
            atr_take_multiplier=3.0
        )

        size, stop, take = risk_mgr.calculate_position_size(
            signal=signal,
            account_balance=1000.0,
            current_price=50000.0,
            atr=1500.0
        )

        # 4. Check risk limits
        assert risk_mgr.check_position_limit(
            current_positions=0,
            max_positions=4
        ) is True

        # 5. Place order (dry-run)
        order = client.place_order(
            symbol='BTC',
            side='buy',
            size=size,
            order_type='market',
            dry_run=True
        )

        # 6. Track position
        position = position_tracker.open_position(
            strategy_id='Strategy_MOM_001',
            symbol='BTC',
            side='long',
            size=size,
            entry_price=50000.0,
            stop_loss=stop,
            take_profit=take
        )

        # Validate complete workflow
        assert order['status'] == 'simulated'
        assert position['status'] == 'open'
        assert position['size'] > 0
        mock_place_order.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
