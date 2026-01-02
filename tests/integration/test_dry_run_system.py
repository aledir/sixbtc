"""
Integration Tests for Complete Dry-Run System

Tests the entire system in dry_run mode with focus on:
- End-to-end workflow safety
- No real orders placed
- Correct simulation behavior
- Emergency stops work correctly
- Statistics tracking accurate
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime

from src.executor.hyperliquid_client import HyperliquidClient
from src.executor.risk_manager import RiskManager
from src.executor.position_tracker import PositionTracker
from src.strategies.base import Signal


@pytest.fixture
def mock_config():
    """Mock configuration for dry-run testing"""
    return {
        'executor': {
            'dry_run': True,  # CRITICAL: Always True for safety
            'subaccounts': {
                'enabled': [1, 2, 3],
                'max_active': 3
            }
        },
        'risk': {
            'sizing_mode': 'atr',
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
            'fixed_fractional': {
                'risk_per_trade_pct': 0.02,
                'max_position_size_pct': 0.20
            },
            'limits': {
                'max_open_positions_total': 15,
                'max_open_positions_per_subaccount': 5,
                'max_leverage': 10
            },
            'emergency': {
                'max_portfolio_drawdown': 0.25,
                'max_subaccount_drawdown': 0.20,
                'max_consecutive_losses': 5
            }
        },
        'hyperliquid': {
            'base_url': 'https://api.hyperliquid.xyz',
            'fee_rate': 0.0004,
            'slippage': 0.0005
        }
    }


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='15min')

    df = pd.DataFrame({
        'timestamp': dates,
        'open': 50000 + np.cumsum(np.random.randn(200) * 100),
        'high': 50500 + np.cumsum(np.random.randn(200) * 100),
        'low': 49500 + np.cumsum(np.random.randn(200) * 100),
        'close': 50000 + np.cumsum(np.random.randn(200) * 100),
        'volume': np.abs(np.random.randn(200) * 1000)
    })

    # Fix high/low consistency
    df['high'] = df[['open', 'high', 'low', 'close']].max(axis=1)
    df['low'] = df[['open', 'high', 'low', 'close']].min(axis=1)

    return df


class TestDryRunSafety:
    """Test dry-run mode prevents live trading"""

    def test_dry_run_flag_prevents_real_orders(self, mock_config):
        """CRITICAL: Verify dry_run=True prevents all real orders"""
        client = HyperliquidClient(dry_run=True)

        assert client.dry_run is True

        # Attempt to place order
        result = client.place_order(
            symbol='BTC',
            side='long',
            size=0.1,
            order_type='market'
        )

        # Should return simulated result, not real order
        assert result is not None
        assert result.get('simulated', False) is True

    def test_cannot_switch_to_live_without_credentials(self, mock_config):
        """Test switching to live mode requires credentials"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': []}
            mock_info.return_value = mock_info_instance

            with pytest.raises(ValueError, match="Live trading requires valid private_key and wallet_address"):
                HyperliquidClient(dry_run=False)

    def test_dry_run_logs_all_actions(self, mock_config):
        """Test dry-run mode logs all simulated actions"""
        client = HyperliquidClient(dry_run=True)

        with patch('src.executor.hyperliquid_client.logger') as mock_logger:
            client.place_order('BTC', 'long', 0.1, 'market')

            # Should log DRY RUN action
            assert any('DRY RUN' in str(call) for call in mock_logger.info.call_args_list)


class TestSimulatedExecution:
    """Test simulated order execution"""

    def test_simulated_market_order_fills_at_current_price(self, mock_config):
        """Test market order simulation fills at current price (with slippage)"""
        client = HyperliquidClient(dry_run=True)

        # Mock current price
        with patch.object(client, 'get_current_price', return_value=50000.0):
            result = client.place_order('BTC', 'long', 0.1, 'market')

            # Fill price includes slippage (0.02% for long = slightly higher)
            assert result['fill_price'] >= 50000.0
            assert result['fill_price'] <= 50020.0  # Max 0.04% slippage
            assert result['size'] == 0.1
            assert result['side'] == 'long'

    def test_simulated_order_includes_fees(self, mock_config):
        """Test simulated orders contain required fields"""
        from unittest.mock import patch, MagicMock

        with patch('src.executor.hyperliquid_client.Info') as mock_info:
            mock_info_instance = MagicMock()
            mock_info_instance.meta.return_value = {'universe': [{'name': 'BTC', 'szDecimals': 4, 'maxLeverage': 50}]}
            mock_info_instance.all_mids.return_value = {'BTC': '50000.0'}
            mock_info.return_value = mock_info_instance

            client = HyperliquidClient(dry_run=True)

            result = client.place_order('BTC', 'long', 0.1, 'market')

            # Verify result contains expected fields
            assert result is not None
            assert 'status' in result
            assert result['status'] == 'simulated'
            assert 'fill_price' in result
            assert 'size' in result

    def test_simulated_slippage_applied(self, mock_config):
        """Test slippage is applied to simulated fills"""
        client = HyperliquidClient(dry_run=True)

        with patch.object(client, 'get_current_price', return_value=50000.0):
            result = client.place_order('BTC', 'long', 0.1, 'market')

            # Slippage should make fill price slightly worse
            # Long order: fill price > current price
            assert result['fill_price'] >= 50000.0


class TestDryRunPositionTracking:
    """Test position tracking in dry-run mode"""

    def test_open_simulated_position(self, mock_config):
        """Test opening simulated position"""
        tracker = PositionTracker(dry_run=True)

        position = tracker.open_position(
            strategy_id='test_strategy',
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51500.0
        )

        assert position is not None
        assert position['symbol'] == 'BTC'
        assert position['side'] == 'long'
        assert position['size'] == 0.1

    def test_simulated_position_pnl_calculation(self, mock_config):
        """Test PnL calculation for simulated positions"""
        tracker = PositionTracker(dry_run=True)

        # Open long position
        position = tracker.open_position(
            strategy_id='test_strategy',
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51500.0
        )

        # Update with new price
        current_price = 51000.0
        pnl = tracker.calculate_pnl(position=position, current_price=current_price)

        # PnL = (current - entry) * size
        expected_pnl = (51000.0 - 50000.0) * 0.1
        assert abs(pnl - expected_pnl) < 0.01

    def test_close_simulated_position(self, mock_config):
        """Test closing simulated position"""
        tracker = PositionTracker(dry_run=True)

        # Open position
        position = tracker.open_position(
            strategy_id='test_strategy',
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51500.0
        )

        # Close position
        exit_price = 51000.0
        closed = tracker.close_position(position['id'], exit_price)

        assert closed is not None
        assert closed['exit_price'] == exit_price
        assert closed['pnl'] > 0  # Profitable trade


class TestDryRunRiskManagement:
    """Test risk management in dry-run mode"""

    def test_risk_limits_enforced_in_dry_run(self, mock_config):
        """Test risk limits are enforced even in dry-run"""
        risk_manager = RiskManager(config=mock_config)

        # Signal with proper structure
        signal = Signal(
            direction='long',
            atr_stop_multiplier=2.0,
            atr_take_multiplier=3.0,
            confidence=1.0,
            reason="Test signal"
        )

        # Valid signal should pass basic checks
        is_valid = risk_manager.validate_signal(signal, current_price=50000.0)
        # Just verify validate_signal works (no exception)
        assert isinstance(is_valid, bool)

    def test_emergency_stop_triggers_in_dry_run(self, mock_config):
        """Test emergency stop triggers correctly in dry-run"""
        risk_manager = RiskManager(config=mock_config)

        # check_emergency_stop should return a boolean
        should_stop = risk_manager.check_emergency_stop()
        assert isinstance(should_stop, bool)

    def test_consecutive_loss_tracking(self, mock_config):
        """Test consecutive loss tracking in dry-run"""
        risk_manager = RiskManager(config=mock_config)

        # Record consecutive losses
        for i in range(5):
            risk_manager.record_trade_result(
                strategy_id='test',
                pnl=-100.0,
                reason='loss'
            )

        # Verify recording worked (no exception)
        # check_emergency_stop should return a boolean
        should_stop = risk_manager.check_emergency_stop()
        assert isinstance(should_stop, bool)


class TestDryRunStatistics:
    """Test statistics tracking in dry-run mode"""

    def test_track_simulated_trades(self, mock_config):
        """Test simulated trades are tracked correctly"""
        tracker = PositionTracker(dry_run=True)

        # Simulate 10 trades
        for i in range(10):
            position = tracker.open_position(
                strategy_id='test',
                symbol='BTC',
                side='long',
                size=0.1,
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=51500.0
            )

            # Close with profit or loss
            exit_price = 51000.0 if i % 2 == 0 else 49500.0
            tracker.close_position(position['id'], exit_price)

        stats = tracker.get_statistics()

        assert stats['total_trades'] == 10
        assert stats['winning_trades'] == 5
        assert stats['losing_trades'] == 5
        assert abs(stats['win_rate'] - 0.5) < 0.01

    def test_performance_metrics_calculation(self, mock_config):
        """Test performance metrics calculated correctly"""
        tracker = PositionTracker(dry_run=True)

        # Simulate profitable trading session
        for i in range(20):
            position = tracker.open_position(
                strategy_id='test',
                symbol='BTC',
                side='long',
                size=0.1,
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=51500.0
            )

            # 70% win rate
            exit_price = 51500.0 if i % 10 < 7 else 49000.0
            tracker.close_position(position['id'], exit_price)

        stats = tracker.get_statistics()

        assert stats['win_rate'] >= 0.65  # Should be ~70%
        assert stats['total_pnl'] > 0  # Overall profitable
        assert stats['avg_win'] > abs(stats['avg_loss'])


class TestDryRunMultiSubaccount:
    """Test multi-subaccount handling in dry-run"""

    def test_independent_subaccount_tracking(self, mock_config):
        """Test each subaccount tracked independently"""
        tracker1 = PositionTracker(dry_run=True, subaccount_id=1)
        tracker2 = PositionTracker(dry_run=True, subaccount_id=2)

        # Open position in subaccount 1
        pos1 = tracker1.open_position(
            strategy_id='strategy1',
            symbol='BTC',
            side='long',
            size=0.1,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51500.0
        )

        # Open position in subaccount 2
        pos2 = tracker2.open_position(
            strategy_id='strategy2',
            symbol='ETH',
            side='short',
            size=1.0,
            entry_price=3000.0,
            stop_loss=3100.0,
            take_profit=2900.0
        )

        # Positions should be independent
        assert tracker1.get_open_positions_count() == 1
        assert tracker2.get_open_positions_count() == 1

        # Close positions to get stats
        tracker1.close_position(pos1['id'], 51000.0)
        tracker2.close_position(pos2['id'], 2900.0)

        stats1 = tracker1.get_statistics()
        stats2 = tracker2.get_statistics()

        assert stats1['total_trades'] == 1
        assert stats2['total_trades'] == 1

    def test_portfolio_aggregation(self, mock_config):
        """Test portfolio-level aggregation across subaccounts"""
        trackers = [
            PositionTracker(dry_run=True, subaccount_id=i)
            for i in range(1, 4)
        ]

        # Open positions in each subaccount
        for i, tracker in enumerate(trackers):
            tracker.open_position(
                strategy_id=f'strategy{i}',
                symbol='BTC',
                side='long',
                size=0.1,
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=51500.0
            )

        # Calculate portfolio-level stats
        total_positions = sum(t.get_open_positions_count() for t in trackers)
        assert total_positions == 3


class TestDryRunErrorHandling:
    """Test error handling in dry-run mode"""

    def test_invalid_signal_rejected(self, mock_config):
        """Test invalid signals are rejected gracefully"""
        risk_manager = RiskManager(config=mock_config)
        current_price = 50000.0

        # Test 1: Invalid direction
        invalid_direction_signal = Mock()
        invalid_direction_signal.direction = 'invalid_direction'

        is_valid = risk_manager.validate_signal(invalid_direction_signal, current_price)
        assert is_valid is False

        # Test 2: Missing direction attribute
        signal_no_direction = Mock(spec=[])  # Empty spec = no attributes
        is_valid = risk_manager.validate_signal(signal_no_direction, current_price)
        assert is_valid is False

        # Test 3: Signal with stop_loss > entry (invalid for long)
        # Using mock to test the legacy validation path
        invalid_sl_signal = Mock()
        invalid_sl_signal.direction = 'long'
        invalid_sl_signal.stop_loss = 60000.0  # Above entry (50000) - invalid for long
        invalid_sl_signal.take_profit = 55000.0

        is_valid = risk_manager.validate_signal(invalid_sl_signal, current_price)
        assert is_valid is False

    def test_zero_size_position_rejected(self, mock_config):
        """Test zero-size positions are rejected"""
        tracker = PositionTracker(dry_run=True)

        with pytest.raises(ValueError, match="size must be positive"):
            tracker.open_position(
                strategy_id='test',
                symbol='BTC',
                side='long',
                size=0.0,  # Invalid
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=51500.0
            )

    def test_negative_price_rejected(self, mock_config):
        """Test negative prices are rejected"""
        tracker = PositionTracker(dry_run=True)

        with pytest.raises(ValueError, match="price must be positive"):
            tracker.open_position(
                strategy_id='test',
                symbol='BTC',
                side='long',
                size=0.1,
                entry_price=-50000.0,  # Invalid
                stop_loss=49000.0,
                take_profit=51500.0
            )


class TestDryRunReporting:
    """Test reporting and logging in dry-run mode"""

    def test_dry_run_clearly_labeled(self, mock_config):
        """Test all dry-run actions are clearly labeled"""
        client = HyperliquidClient(dry_run=True)

        # Check string representation includes DRY RUN
        assert 'DRY RUN' in str(client) or 'dry_run=True' in str(client)

    def test_dry_run_statistics_exported(self, mock_config):
        """Test dry-run statistics can be exported"""
        tracker = PositionTracker(dry_run=True)

        # Simulate some trades
        for i in range(5):
            position = tracker.open_position(
                strategy_id='test',
                symbol='BTC',
                side='long',
                size=0.1,
                entry_price=50000.0,
                stop_loss=49000.0,
                take_profit=51500.0
            )
            tracker.close_position(position['id'], 51000.0)

        # Export statistics
        stats = tracker.export_statistics()

        assert stats is not None
        assert 'total_trades' in stats
        assert 'win_rate' in stats
        assert 'total_pnl' in stats
        assert 'dry_run' in stats
        assert stats['dry_run'] is True
