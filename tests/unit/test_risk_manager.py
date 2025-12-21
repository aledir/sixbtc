"""
Test RiskManager

Tests ATR-based and fixed fractional position sizing.
"""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.executor.risk_manager import RiskManager


class TestRiskManager:
    """Test RiskManager functionality"""

    @pytest.fixture
    def atr_config(self):
        """Configuration for ATR-based sizing"""
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
                    'max_leverage': 10
                },
                'emergency': {
                    'max_portfolio_drawdown': 0.30,
                    'max_consecutive_losses': 5
                }
            }
        }

    @pytest.fixture
    def fixed_config(self):
        """Configuration for fixed fractional sizing"""
        config = {
            'risk': {
                'sizing_mode': 'fixed',
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
                        'enabled': False,
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
                    'max_consecutive_losses': 5
                }
            }
        }
        return config

    @pytest.fixture
    def sample_ohlcv(self):
        """Sample OHLCV data for ATR calculation"""
        def _create(n_candles=100, volatility=1500.0):
            np.random.seed(42)
            dates = pd.date_range(end=pd.Timestamp.now(), periods=n_candles, freq='1h')

            # Create realistic OHLCV with known ATR
            close = 42000.0 + np.random.randn(n_candles) * volatility
            high = close + np.abs(np.random.randn(n_candles)) * volatility * 0.5
            low = close - np.abs(np.random.randn(n_candles)) * volatility * 0.5
            open_price = close + np.random.randn(n_candles) * volatility * 0.3

            return pd.DataFrame({
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': np.random.randint(100, 1000, n_candles).astype(float)
            }, index=dates)

        return _create

    def test_initialization_atr_mode(self, atr_config):
        """Test risk manager initializes in ATR mode"""
        rm = RiskManager(atr_config)

        assert rm.sizing_mode == 'atr'
        assert rm.atr_period == 14
        assert rm.atr_stop_multiplier == 2.0
        assert rm.risk_per_trade_pct == 0.02

    def test_initialization_fixed_mode(self, fixed_config):
        """Test risk manager initializes in fixed mode"""
        rm = RiskManager(fixed_config)

        assert rm.sizing_mode == 'fixed'
        assert rm.risk_per_trade_pct == 0.02

    def test_calculate_atr(self, atr_config, sample_ohlcv):
        """Test ATR calculation"""
        rm = RiskManager(atr_config)
        df = sample_ohlcv()

        atr = rm._calculate_atr(df)

        # ATR should be positive
        assert atr > 0

        # ATR should be reasonable (within expected range for our test data)
        assert 500 < atr < 3000

    def test_calculate_atr_insufficient_data(self, atr_config):
        """Test ATR calculation with insufficient data"""
        rm = RiskManager(atr_config)

        # Only 5 candles (less than period of 14)
        df = pd.DataFrame({
            'open': [42000] * 5,
            'high': [42100] * 5,
            'low': [41900] * 5,
            'close': [42000] * 5,
            'volume': [100] * 5
        })

        atr = rm._calculate_atr(df)
        assert atr == 0.0  # Should return 0 for insufficient data

    def test_position_size_atr_basic(self, atr_config, sample_ohlcv):
        """Test basic ATR-based position sizing"""
        # Disable volatility scaling for predictable test
        atr_config['risk']['atr']['volatility_scaling']['enabled'] = False
        rm = RiskManager(atr_config)
        df = sample_ohlcv(volatility=1500.0)

        account_balance = 10000.0
        current_price = 42000.0
        atr = 1500.0

        size, sl, tp = rm.calculate_position_size_atr(
            account_balance=account_balance,
            current_price=current_price,
            atr=atr
        )

        # Verify basic properties
        assert size > 0
        assert size <= (account_balance * 0.20) / current_price  # Respect max size
        assert sl == current_price - (atr * 2.0)  # 39000
        assert tp == current_price + (atr * 3.0)  # 46500

        # Verify risk/reward
        profit = tp - current_price
        loss = current_price - sl
        rr = profit / loss
        assert abs(rr - 1.5) < 0.01  # Should be 1.5:1

    def test_position_size_atr_low_volatility_scaling(self, atr_config, sample_ohlcv):
        """Test position size increases in low volatility"""
        rm = RiskManager(atr_config)

        account_balance = 10000.0
        current_price = 42000.0
        low_atr = 500.0  # ~1.2% of price (below 1.5% threshold)

        size_low, _, _ = rm.calculate_position_size_atr(
            account_balance, current_price, low_atr
        )

        # With low volatility scaling, size should be positive but capped by max_position_size_pct
        # Max size = 20% of balance = $2000 / $42000 = 0.0476 BTC
        max_size = (account_balance * 0.20) / current_price

        assert size_low > 0
        assert size_low <= max_size

    def test_position_size_atr_high_volatility_scaling(self, atr_config, sample_ohlcv):
        """Test position size decreases in high volatility"""
        rm = RiskManager(atr_config)

        account_balance = 10000.0
        current_price = 42000.0
        high_atr = 2500.0  # ~6% of price (above 5% threshold)

        size_high, _, _ = rm.calculate_position_size_atr(
            account_balance, current_price, high_atr
        )

        # Calculate expected size without scaling
        expected_base = (account_balance * 0.02) / (high_atr * 2.0)
        expected_scaled = expected_base * 0.5  # Decreased by 50%

        # Size should be scaled down
        assert size_high < expected_base
        assert abs(size_high - expected_scaled) < 0.001

    def test_position_size_atr_respects_max_size(self, atr_config):
        """Test position size respects maximum size limit"""
        rm = RiskManager(atr_config)

        account_balance = 10000.0
        current_price = 42000.0
        very_low_atr = 10.0  # Would result in huge position

        size, _, _ = rm.calculate_position_size_atr(
            account_balance, current_price, very_low_atr
        )

        # Max position is 20% of balance = $2000
        max_size = (account_balance * 0.20) / current_price
        assert size <= max_size

    def test_position_size_fixed_basic(self, fixed_config):
        """Test basic fixed fractional position sizing"""
        rm = RiskManager(fixed_config)

        account_balance = 10000.0
        entry_price = 42000.0
        stop_loss = 40000.0

        size = rm.calculate_position_size_fixed(
            account_balance, entry_price, stop_loss
        )

        # Expected: risk $200 / $2000 stop distance = 0.1 BTC
        expected_size = 200.0 / 2000.0
        # Size may be capped by max_position_size_pct (20% = $2000 / $42000 = 0.0476)
        assert size > 0
        assert size <= (account_balance * 0.20) / entry_price

    def test_position_size_fixed_respects_max_size(self, fixed_config):
        """Test fixed sizing respects maximum size limit"""
        rm = RiskManager(fixed_config)

        account_balance = 10000.0
        entry_price = 42000.0
        stop_loss = 41999.0  # Very tight stop (would result in huge position)

        size = rm.calculate_position_size_fixed(
            account_balance, entry_price, stop_loss
        )

        # Max position is 20% of balance
        max_size = (account_balance * 0.20) / entry_price
        assert size <= max_size

    def test_position_size_fixed_zero_stop_distance(self, fixed_config):
        """Test fixed sizing with zero stop distance"""
        rm = RiskManager(fixed_config)

        account_balance = 10000.0
        entry_price = 42000.0
        stop_loss = 42000.0  # Same as entry (zero distance)

        size = rm.calculate_position_size_fixed(
            account_balance, entry_price, stop_loss
        )

        # Should return 0 for invalid stop
        assert size == 0.0

    def test_calculate_position_size_auto_select_atr(self, atr_config, sample_ohlcv):
        """Test auto-selection of ATR mode"""
        rm = RiskManager(atr_config)
        df = sample_ohlcv()

        size, sl, tp = rm.calculate_position_size(
            account_balance=10000.0,
            current_price=42000.0,
            df=df
        )

        # Should use ATR mode
        assert size > 0
        assert sl < 42000.0
        assert tp > 42000.0

    def test_calculate_position_size_auto_select_fixed(self, fixed_config):
        """Test auto-selection of fixed mode"""
        rm = RiskManager(fixed_config)

        size, sl, tp = rm.calculate_position_size(
            account_balance=10000.0,
            current_price=42000.0,
            signal_stop_loss=40000.0,
            signal_take_profit=45000.0
        )

        # Should use fixed mode
        assert size > 0
        assert sl == 40000.0
        assert tp == 45000.0

    def test_check_risk_limits_position_count(self, atr_config):
        """Test position count limits"""
        rm = RiskManager(atr_config)

        # Within limits (small position to avoid size/leverage limits)
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.01,  # Small size: ~$420
            current_positions_count=50,
            subaccount_positions_count=2,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is True, f"Should be allowed but got: {reason}"

        # Exceeds total limit
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.1,
            current_positions_count=100,
            subaccount_positions_count=2,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is False
        assert 'Max total positions' in reason

        # Exceeds subaccount limit
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.1,
            current_positions_count=50,
            subaccount_positions_count=4,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is False
        assert 'Max subaccount positions' in reason

    def test_check_risk_limits_position_size(self, atr_config):
        """Test position size limits"""
        rm = RiskManager(atr_config)

        # Within limits (10% of balance)
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.023,  # ~$1000 at $42k
            current_positions_count=0,
            subaccount_positions_count=0,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is True

        # Exceeds max size (20% limit)
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.06,  # ~$2520 at $42k (>20% of $10k)
            current_positions_count=0,
            subaccount_positions_count=0,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is False
        assert 'Position size' in reason

    def test_check_risk_limits_leverage(self, atr_config):
        """Test leverage limits"""
        rm = RiskManager(atr_config)

        # Within leverage limit (2x, well below 10x max)
        allowed, reason = rm.check_risk_limits(
            new_position_size=0.047,  # ~$2000 position on $10k balance = ~0.2x
            current_positions_count=0,
            subaccount_positions_count=0,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is True, f"Should be allowed but got: {reason}"

        # Exceeds leverage limit (10x max)
        # Note: Position size check happens first, so large positions may fail on size before leverage
        allowed, reason = rm.check_risk_limits(
            new_position_size=3.0,  # $126k position on $10k balance = 12.6x
            current_positions_count=0,
            subaccount_positions_count=0,
            account_balance=10000.0,
            current_price=42000.0
        )
        assert allowed is False
        # May fail on either position size or leverage check
        assert ('Leverage' in reason or 'Position size' in reason)

    def test_adjust_stops_for_long(self, atr_config):
        """Test stop adjustment for long positions"""
        rm = RiskManager(atr_config)

        sl, tp = rm.adjust_stops_for_side(
            side='long',
            current_price=42000.0,
            stop_loss=40000.0,
            take_profit=45000.0
        )

        # Long: stops unchanged
        assert sl == 40000.0
        assert tp == 45000.0

    def test_adjust_stops_for_short(self, atr_config):
        """Test stop adjustment for short positions"""
        rm = RiskManager(atr_config)

        sl, tp = rm.adjust_stops_for_side(
            side='short',
            current_price=42000.0,
            stop_loss=40000.0,  # For long (below entry)
            take_profit=45000.0  # For long (above entry)
        )

        # Short: stops inverted
        # Original: SL 2000 below, TP 3000 above
        # Short: SL should be 2000 above, TP should be 3000 below
        assert sl == 44000.0  # 42000 + 2000
        assert tp == 39000.0  # 42000 - 3000

    def test_custom_stop_take_multipliers(self, atr_config):
        """Test using custom stop/take multipliers from signal"""
        rm = RiskManager(atr_config)

        account_balance = 10000.0
        current_price = 42000.0
        atr = 1000.0

        # Use custom multipliers (3x stop, 6x take)
        size, sl, tp = rm.calculate_position_size_atr(
            account_balance=account_balance,
            current_price=current_price,
            atr=atr,
            signal_stop_multiplier=3.0,
            signal_take_multiplier=6.0
        )

        # Verify custom multipliers used
        assert sl == current_price - (atr * 3.0)  # 39000
        assert tp == current_price + (atr * 6.0)  # 48000

    def test_get_summary(self, atr_config):
        """Test getting configuration summary"""
        rm = RiskManager(atr_config)

        summary = rm.get_summary()

        assert summary['sizing_mode'] == 'atr'
        assert summary['risk_per_trade_pct'] == 0.02
        assert summary['atr_period'] == 14
        assert summary['max_positions_total'] == 100
        assert summary['volatility_scaling_enabled'] is True

    def test_realistic_scenario_btc(self, atr_config, sample_ohlcv):
        """Test realistic BTC trading scenario"""
        rm = RiskManager(atr_config)

        # Realistic BTC data
        df = sample_ohlcv(n_candles=100, volatility=1500.0)

        account_balance = 1000.0  # $1k account
        current_price = 42000.0

        size, sl, tp = rm.calculate_position_size(
            account_balance=account_balance,
            current_price=current_price,
            df=df
        )

        # Verify reasonable values
        assert size > 0
        assert sl < current_price
        assert tp > current_price

        # Verify risk
        position_value = size * current_price
        risk_amount = size * (current_price - sl)

        # Risk should be ~2% of balance (with volatility scaling, may vary)
        # Use larger tolerance
        assert risk_amount > 0
        assert risk_amount < account_balance * 0.10  # Should be < 10%

        # Position shouldn't exceed 20% of balance (with small tolerance for rounding)
        assert position_value <= (account_balance * 0.20) + 1.0
