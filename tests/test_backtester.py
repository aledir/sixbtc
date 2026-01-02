"""
Tests for backtester module

Validates:
- Data loading from Binance
- VectorBT backtest execution
- Metrics calculation
- Lookahead bias detection
- Walk-forward validation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

from src.backtester.data_loader import BacktestDataLoader
from src.backtester.backtest_engine import BacktestEngine
from src.backtester.validator import LookaheadValidator
from src.strategies.base import StrategyCore, Signal

# Alias for backward compatibility
VectorBTBacktester = BacktestEngine


class MockStrategy(StrategyCore):
    """Mock strategy for testing"""

    indicator_columns = ['sma_fast', 'sma_slow']

    def __init__(self, **params):
        super().__init__(params)
        self.timeframe = '15m'
        self.symbol = 'BTC'

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate indicators"""
        df = df.copy()
        df['sma_fast'] = df['close'].rolling(10).mean()
        df['sma_slow'] = df['close'].rolling(20).mean()
        return df

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        """Simple momentum strategy using pre-calculated indicators"""
        if len(df) < 20:
            return None

        # Read pre-calculated indicators
        sma_fast = df['sma_fast'].iloc[-1] if 'sma_fast' in df.columns else df['close'].rolling(10).mean().iloc[-1]
        sma_slow = df['sma_slow'].iloc[-1] if 'sma_slow' in df.columns else df['close'].rolling(20).mean().iloc[-1]

        if pd.isna(sma_fast) or pd.isna(sma_slow):
            return None

        if sma_fast > sma_slow:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason="Fast SMA > Slow SMA"
            )

        return None


@pytest.fixture
def sample_ohlcv_data():
    """Generate sample OHLCV data with UTC timezone"""
    dates = pd.date_range(
        start=datetime.now(timezone.utc) - timedelta(days=100),
        periods=1000,
        freq='15min',
        tz=timezone.utc
    )

    np.random.seed(42)
    close = 50000 + np.cumsum(np.random.randn(1000) * 100)
    high = close + np.random.rand(1000) * 100
    low = close - np.random.rand(1000) * 100
    open_ = close + np.random.randn(1000) * 50
    volume = np.random.rand(1000) * 1000000

    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })

    return df


class TestBacktestDataLoader:
    """Test data loading for backtests"""

    @patch('src.data.binance_downloader.BinanceDataDownloader')
    def test_load_single_symbol(self, mock_downloader_class, sample_ohlcv_data):
        """Test single symbol data loading"""
        # Mock the downloader instance
        mock_downloader = Mock()
        mock_downloader.download_ohlcv.return_value = sample_ohlcv_data
        mock_downloader_class.return_value = mock_downloader

        # Load data
        loader = BacktestDataLoader()
        df = loader.load_single_symbol(
            symbol='BTC',
            timeframe='15m',
            days=100
        )

        # Validate
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert all(col in df.columns for col in ['open', 'high', 'low', 'close', 'volume'])
        assert df['high'].min() >= df['low'].min()
        assert df['close'].notna().all()

    @patch('src.data.binance_downloader.BinanceDataDownloader')
    def test_load_multi_symbol(self, mock_downloader_class, sample_ohlcv_data):
        """Test multi-symbol data loading"""
        # Mock the downloader instance
        mock_downloader = Mock()
        mock_downloader.download_ohlcv.return_value = sample_ohlcv_data
        mock_downloader_class.return_value = mock_downloader

        # Load data
        loader = BacktestDataLoader()
        data = loader.load_multi_symbol(
            symbols=['BTC', 'ETH'],
            timeframe='15m',
            days=100
        )

        # Validate
        assert isinstance(data, dict)
        assert len(data) == 2
        assert 'BTC' in data
        assert 'ETH' in data
        assert all(isinstance(df, pd.DataFrame) for df in data.values())


class TestVectorBTBacktester:
    """Test VectorBT backtest execution"""

    @patch('src.database.connection.get_session')
    @patch('src.config.loader.load_config')
    def test_backtest_execution(self, mock_config, mock_session, sample_ohlcv_data):
        """Test backtest execution with portfolio method"""
        # Mock config
        mock_config.return_value = Mock(
            get=lambda key, default=None: {
                'hyperliquid.fee_rate': 0.0004,
                'hyperliquid.slippage': 0.0002,
                'backtesting.initial_capital': 10000,
                'risk.limits.max_open_positions_per_subaccount': 10,
            }.get(key, default),
            _raw_config={}
        )

        # Mock database session for leverage lookup
        mock_session.return_value.__enter__ = Mock(return_value=Mock(
            query=Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None)))))
        ))
        mock_session.return_value.__exit__ = Mock(return_value=None)

        strategy = MockStrategy()
        backtester = VectorBTBacktester()

        # backtest() now requires Dict[str, pd.DataFrame]
        data = {'BTC': sample_ohlcv_data}
        results = backtester.backtest(
            strategy=strategy,
            data=data,
            max_positions=4
        )

        # Validate results structure
        assert 'sharpe_ratio' in results
        assert 'max_drawdown' in results
        assert 'win_rate' in results
        assert 'total_trades' in results
        assert 'avg_leverage' in results

        # Validate metrics ranges
        assert results['max_drawdown'] <= 1.0
        # win_rate can be NaN if no trades
        if results['total_trades'] > 0:
            assert 0 <= results['win_rate'] <= 1.0
        assert results['total_trades'] >= 0

    @patch('src.database.connection.get_session')
    @patch('src.config.loader.load_config')
    def test_backtest_multi_symbol(self, mock_config, mock_session, sample_ohlcv_data):
        """Test multi-symbol backtest"""
        # Mock config
        mock_config.return_value = Mock(
            get=lambda key, default=None: {
                'hyperliquid.fee_rate': 0.0004,
                'hyperliquid.slippage': 0.0002,
                'backtesting.initial_capital': 10000,
                'risk.limits.max_open_positions_per_subaccount': 10,
            }.get(key, default),
            _raw_config={}
        )

        # Mock database session for leverage lookup
        mock_session.return_value.__enter__ = Mock(return_value=Mock(
            query=Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None)))))
        ))
        mock_session.return_value.__exit__ = Mock(return_value=None)

        strategy = MockStrategy()
        backtester = VectorBTBacktester()

        data = {
            'BTC': sample_ohlcv_data,
            'ETH': sample_ohlcv_data.copy()
        }

        results = backtester.backtest(
            strategy=strategy,
            data=data
        )

        # Validate
        assert isinstance(results, dict)
        assert 'sharpe_ratio' in results
        assert 'total_trades' in results
        assert 'avg_leverage' in results


class TestLookaheadValidator:
    """Test lookahead bias detection"""

    def test_validate_clean_strategy(self, sample_ohlcv_data):
        """Test validation of clean strategy (no lookahead)"""
        clean_code = '''
def generate_signal(df):
    sma = df['close'].rolling(20).mean()
    if df['close'].iloc[-1] > sma.iloc[-1]:
        return Signal(direction='long')
    return None
'''
        validator = LookaheadValidator()
        strategy = MockStrategy()

        results = validator.validate(
            strategy=strategy,
            strategy_code=clean_code,
            backtest_data=sample_ohlcv_data,
            shuffle_iterations=10  # Fewer for speed
        )

        # AST check should pass (no lookahead patterns)
        assert results['ast_check_passed'] is True
        assert len(results['ast_violations']) == 0

        # Shuffle test may pass or fail (zero variance is OK for simple strategies)
        # Just verify the structure is correct
        assert 'shuffle_test_passed' in results
        assert 'shuffle_p_value' in results
        assert 'passed' in results

    def test_detect_lookahead_bias(self, sample_ohlcv_data):
        """Test detection of lookahead bias"""
        lookahead_code = '''
def generate_signal(df):
    # Using center=True - lookahead!
    sma = df['close'].rolling(20, center=True).mean()

    # Negative shift - lookahead!
    future_price = df['close'].shift(-1)

    return Signal(direction='long')
'''
        validator = LookaheadValidator()
        strategy = MockStrategy()

        results = validator.validate(
            strategy=strategy,
            strategy_code=lookahead_code,
            backtest_data=sample_ohlcv_data,
            shuffle_iterations=10
        )

        assert results['ast_check_passed'] is False
        assert len(results['ast_violations']) > 0
        assert results['passed'] is False


class TestBacktesterIntegration:
    """Integration tests for full backtest workflow"""

    @patch('src.database.connection.get_session')
    @patch('src.data.binance_downloader.BinanceDataDownloader')
    @patch('src.config.loader.load_config')
    def test_full_backtest_workflow(
        self,
        mock_config,
        mock_downloader_class,
        mock_session,
        sample_ohlcv_data
    ):
        """Test complete backtest workflow"""
        # Mock config
        mock_config.return_value = Mock(
            get=lambda key, default=None: {
                'hyperliquid.fee_rate': 0.0004,
                'hyperliquid.slippage': 0.0002,
                'backtesting.initial_capital': 10000,
                'risk.limits.max_open_positions_per_subaccount': 10,
                'data.cache_dir': 'data/binance',
            }.get(key, default),
            get_required=lambda key: {
                'trading.data.min_volume_24h': 1000000,
            }.get(key),
            _raw_config={}
        )

        # Mock downloader
        mock_downloader = Mock()
        mock_downloader.download_ohlcv.return_value = sample_ohlcv_data
        mock_downloader_class.return_value = mock_downloader

        # Mock database session for leverage lookup
        mock_session.return_value.__enter__ = Mock(return_value=Mock(
            query=Mock(return_value=Mock(filter=Mock(return_value=Mock(first=Mock(return_value=None)))))
        ))
        mock_session.return_value.__exit__ = Mock(return_value=None)

        # 1. Load data
        loader = BacktestDataLoader()
        data = loader.load_single_symbol('BTC', '15m', days=100)

        # 2. Run backtest (now uses Dict format)
        strategy = MockStrategy()
        backtester = VectorBTBacktester()
        results = backtester.backtest(strategy, {'BTC': data})

        # 3. Validate
        assert 'sharpe_ratio' in results
        assert 'total_trades' in results
        assert 'win_rate' in results
        assert 'avg_leverage' in results

        # 4. Check lookahead
        validator = LookaheadValidator()
        clean_code = '''
def generate_signal(df):
    return None
'''
        validation = validator.validate(
            strategy,
            clean_code,
            data,
            shuffle_iterations=5
        )

        assert 'passed' in validation
