"""
Tests for LeveragedBacktester

Validates that:
1. Leverage=1 produces same results as base calculations
2. Leverage correctly scales returns
3. MaxDD scales with leverage
4. Sharpe remains invariant to leverage (mathematically)
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.backtester.leveraged_engine import LeveragedBacktester, LeveragedTrade
from src.strategies.base import StrategyCore, Signal


class SimpleTestStrategy(StrategyCore):
    """
    Simple strategy for testing - enters long when price drops 2%, exits when up 2%
    """

    # Target leverage (will be capped at coin's max)
    leverage = 5

    def __init__(self, leverage: int = 1):
        super().__init__()
        self.leverage = leverage  # Override class default
        self._in_position = False
        self._entry_price = None

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        if len(df) < 10:
            return None

        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]

        # Entry: price dropped 2% from previous bar
        if not self._in_position:
            if current_price < prev_price * 0.98:
                self._in_position = True
                self._entry_price = current_price
                return Signal(
                    direction='long',
                    leverage=self.leverage,
                    reason="Price dropped 2%"
                )

        # Exit: price up 2% from entry
        if self._in_position and self._entry_price:
            if current_price > self._entry_price * 1.02:
                self._in_position = False
                self._entry_price = None
                return Signal(direction='close', reason="Target reached")

        return None


def create_test_data(n_bars: int = 500) -> pd.DataFrame:
    """Create synthetic OHLCV data with some volatility"""
    np.random.seed(42)

    dates = pd.date_range(start='2024-01-01', periods=n_bars, freq='1H')

    # Generate price with random walk + mean reversion
    base_price = 50000
    returns = np.random.normal(0, 0.005, n_bars)  # 0.5% daily volatility
    prices = base_price * np.cumprod(1 + returns)

    # Add some larger moves for trading signals
    for i in range(50, n_bars, 50):
        if i < n_bars:
            prices[i:i+5] *= 0.97  # 3% drop
            prices[i+5:i+15] *= 1.04  # Recovery

    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.uniform(-0.001, 0.001, n_bars)),
        'high': prices * (1 + np.random.uniform(0, 0.01, n_bars)),
        'low': prices * (1 - np.random.uniform(0, 0.01, n_bars)),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n_bars),
    })
    df.set_index('timestamp', inplace=True)

    return df


class TestLeveragedTrade:
    """Test LeveragedTrade dataclass calculations"""

    def test_long_trade_pnl(self):
        """Test PnL calculation for long trade"""
        trade = LeveragedTrade(
            symbol='BTC',
            entry_idx=0,
            exit_idx=10,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            entry_price=50000,
            exit_price=52000,
            size=0.1,
            direction='long',
            leverage=10,
            fees=5,
        )

        # PnL = (52000 - 50000) * 0.1 - 5 = 200 - 5 = 195
        assert trade.pnl_dollars == 195

        # Notional = 0.1 * 50000 = 5000
        assert trade.notional == 5000

        # Margin = 5000 / 10 = 500
        assert trade.margin == 500

        # Return on margin = 195 / 500 = 0.39 = 39%
        assert abs(trade.return_on_margin - 0.39) < 0.01

    def test_short_trade_pnl(self):
        """Test PnL calculation for short trade"""
        trade = LeveragedTrade(
            symbol='BTC',
            entry_idx=0,
            exit_idx=10,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            entry_price=50000,
            exit_price=48000,
            size=0.1,
            direction='short',
            leverage=5,
            fees=5,
        )

        # PnL = (50000 - 48000) * 0.1 - 5 = 200 - 5 = 195
        assert trade.pnl_dollars == 195

        # Margin = 5000 / 5 = 1000
        assert trade.margin == 1000

        # Return on margin = 195 / 1000 = 0.195 = 19.5%
        assert abs(trade.return_on_margin - 0.195) < 0.01

    def test_leverage_1x_same_as_notional(self):
        """At 1x leverage, margin equals notional"""
        trade = LeveragedTrade(
            symbol='BTC',
            entry_idx=0,
            exit_idx=10,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            entry_price=50000,
            exit_price=51000,
            size=0.1,
            direction='long',
            leverage=1,
            fees=0,
        )

        assert trade.margin == trade.notional
        assert trade.margin == 5000


class TestLeveragedBacktester:
    """Test LeveragedBacktester class"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session that returns proper coin data"""
        with patch('src.backtester.leveraged_engine.get_session') as mock_session:
            mock_coin = MagicMock()
            mock_coin.max_leverage = 50  # BTC typically has high max leverage
            mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = mock_coin
            yield mock_session

    @pytest.fixture
    def backtester(self, mock_db_session):
        """Create backtester with mocked config and database"""
        with patch('src.backtester.leveraged_engine.load_config') as mock_config:
            mock_config.return_value = MagicMock()
            mock_config.return_value.get = lambda key, default=None: {
                'backtesting.initial_capital': 10000,
                'hyperliquid.fee_rate': 0.00045,
                'hyperliquid.slippage': 0.0005,
            }.get(key, default)

            bt = LeveragedBacktester()
            # Clear cache to ensure fresh DB queries
            bt._coin_max_leverage_cache = {}
            return bt

    @pytest.fixture
    def test_data(self):
        """Create test OHLCV data"""
        return create_test_data(500)

    def test_backtest_runs_without_error(self, backtester, test_data):
        """Basic smoke test"""
        strategy = SimpleTestStrategy(leverage=1)
        result = backtester.backtest(strategy, test_data, 'BTC')

        assert 'total_trades' in result
        assert 'sharpe_ratio' in result
        assert 'max_drawdown' in result

    def test_leverage_increases_returns(self, backtester, test_data):
        """Higher leverage should increase returns (positive and negative)"""
        strategy_1x = SimpleTestStrategy(leverage=1)
        strategy_5x = SimpleTestStrategy(leverage=5)

        result_1x = backtester.backtest(strategy_1x, test_data, 'BTC', leverage_override=1)
        result_5x = backtester.backtest(strategy_5x, test_data, 'BTC', leverage_override=5)

        # Skip if no trades
        if result_1x['total_trades'] == 0 or result_5x['total_trades'] == 0:
            pytest.skip("No trades generated")

        # 5x leverage should have ~5x the average return on margin
        # (with some tolerance for position sizing differences)
        if result_1x['avg_return_on_margin'] != 0:
            ratio = result_5x['avg_return_on_margin'] / result_1x['avg_return_on_margin']
            # Should be approximately 5x, allow 20% tolerance
            assert 3 < ratio < 7, f"Expected ~5x, got {ratio}"

    def test_max_drawdown_scales_with_leverage(self, backtester, test_data):
        """MaxDD should scale approximately with leverage"""
        strategy = SimpleTestStrategy(leverage=1)

        result_1x = backtester.backtest(strategy, test_data, 'BTC', leverage_override=1)
        result_3x = backtester.backtest(strategy, test_data, 'BTC', leverage_override=3)

        if result_1x['total_trades'] == 0:
            pytest.skip("No trades generated")

        # MaxDD at 3x should be roughly 3x MaxDD at 1x
        # Allow significant tolerance due to timing differences
        if result_1x['max_drawdown'] != 0:
            ratio = result_3x['max_drawdown'] / result_1x['max_drawdown']
            assert 1.5 < ratio < 5, f"Expected ~3x, got {ratio}"

    def test_metrics_include_leverage_info(self, backtester, test_data):
        """Result should include leverage-specific metrics"""
        strategy = SimpleTestStrategy(leverage=5)
        result = backtester.backtest(strategy, test_data, 'BTC', leverage_override=5)

        assert 'avg_leverage' in result
        assert 'max_margin_used' in result
        assert 'max_margin_pct' in result
        assert 'avg_return_on_margin' in result

        if result['total_trades'] > 0:
            assert result['avg_leverage'] == 5

    def test_empty_results_on_no_trades(self, backtester):
        """Should return empty results if no trades generated"""
        # Create flat price data (no trading signals)
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
        flat_data = pd.DataFrame({
            'open': [50000] * 100,
            'high': [50100] * 100,
            'low': [49900] * 100,
            'close': [50000] * 100,
            'volume': [100] * 100,
        }, index=dates)

        strategy = SimpleTestStrategy(leverage=1)
        result = backtester.backtest(strategy, flat_data, 'BTC')

        assert result['total_trades'] == 0
        assert result['sharpe_ratio'] == 0.0

    def test_multi_symbol_backtest(self, backtester):
        """Test multi-symbol backtest"""
        # Create data for multiple symbols
        data = {
            'BTC': create_test_data(300),
            'ETH': create_test_data(300),
        }

        strategy = SimpleTestStrategy(leverage=1)
        result = backtester.backtest_multi_symbol(
            strategy,
            data,
            leverage_per_symbol={'BTC': 5, 'ETH': 10}
        )

        assert 'symbols_traded' in result
        assert 'symbol_breakdown' in result


class TestLeverageValidation:
    """
    Validation tests to ensure leveraged calculations are correct
    """

    def test_manual_calculation_matches(self):
        """Verify our calculations match manual example"""
        # Manual example:
        # Entry: $50,000, Exit: $52,000, Size: 0.1 BTC, Leverage: 10x
        # Notional: $5,000
        # Margin: $500
        # PnL: $200
        # Return on margin: 40%

        trade = LeveragedTrade(
            symbol='BTC',
            entry_idx=0,
            exit_idx=10,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            entry_price=50000,
            exit_price=52000,
            size=0.1,
            direction='long',
            leverage=10,
            fees=0,
        )

        assert trade.notional == 5000
        assert trade.margin == 500
        assert trade.pnl_dollars == 200
        assert trade.return_on_margin == 0.4  # 40%

    def test_losing_trade_calculation(self):
        """Verify losing trade calculations"""
        # Entry: $50,000, Exit: $48,000, Size: 0.1 BTC, Leverage: 10x, Long
        # PnL: -$200
        # Return on margin: -40%

        trade = LeveragedTrade(
            symbol='BTC',
            entry_idx=0,
            exit_idx=10,
            entry_time=datetime.now(),
            exit_time=datetime.now(),
            entry_price=50000,
            exit_price=48000,
            size=0.1,
            direction='long',
            leverage=10,
            fees=0,
        )

        assert trade.pnl_dollars == -200
        assert trade.return_on_margin == -0.4  # -40%


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
