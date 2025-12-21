"""
Unit tests for BacktestDataLoader
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.backtester.data_loader import BacktestDataLoader


@pytest.fixture
def mock_binance_downloader():
    """Mock BinanceDataDownloader"""
    with patch('src.backtester.data_loader.BinanceDataDownloader') as mock:
        yield mock


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV DataFrame"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='15min')
    return pd.DataFrame({
        'timestamp': dates,
        'open': range(100, 200),
        'high': range(105, 205),
        'low': range(95, 195),
        'close': range(101, 201),
        'volume': range(1000, 1100)
    })


@pytest.fixture
def data_loader(tmp_path, mock_binance_downloader):
    """BacktestDataLoader with temporary cache dir"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return BacktestDataLoader(cache_dir=str(cache_dir))


class TestBacktestDataLoader:
    """Test suite for BacktestDataLoader"""

    def test_initialization(self, tmp_path):
        """Test data loader initialization"""
        cache_dir = tmp_path / "cache"
        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        assert loader.cache_dir == cache_dir
        assert loader.downloader is not None

    def test_load_single_symbol_success(self, data_loader, sample_ohlcv_data, mock_binance_downloader):
        """Test loading single symbol data"""
        # Mock downloader response
        mock_instance = mock_binance_downloader.return_value
        mock_instance.download_ohlcv.return_value = sample_ohlcv_data

        # Load data
        result = data_loader.load_single_symbol(
            symbol='BTC',
            timeframe='15m',
            days=180
        )

        # Verify
        assert len(result) == 100
        assert 'timestamp' in result.columns
        assert 'close' in result.columns
        mock_instance.download_ohlcv.assert_called_once_with(
            symbol='BTC',
            timeframe='15m',
            days=180
        )

    def test_load_single_symbol_with_end_date(self, data_loader, sample_ohlcv_data, mock_binance_downloader):
        """Test loading with end date filter"""
        mock_instance = mock_binance_downloader.return_value
        mock_instance.download_ohlcv.return_value = sample_ohlcv_data

        # Load with end date
        end_date = sample_ohlcv_data['timestamp'].iloc[50]
        result = data_loader.load_single_symbol(
            symbol='BTC',
            timeframe='1h',
            days=180,
            end_date=end_date
        )

        # Should filter data
        assert len(result) <= 51  # Up to and including index 50
        assert result['timestamp'].max() <= end_date

    def test_load_multi_symbol_success(self, data_loader, sample_ohlcv_data, mock_binance_downloader):
        """Test loading multiple symbols"""
        mock_instance = mock_binance_downloader.return_value
        mock_instance.download_ohlcv.return_value = sample_ohlcv_data

        # Load multiple symbols
        symbols = ['BTC', 'ETH', 'SOL']
        result = data_loader.load_multi_symbol(
            symbols=symbols,
            timeframe='1h',
            days=180
        )

        # Verify
        assert len(result) == 3
        assert 'BTC' in result
        assert 'ETH' in result
        assert 'SOL' in result
        assert mock_instance.download_ohlcv.call_count == 3

    def test_load_multi_symbol_partial_failure(self, data_loader, sample_ohlcv_data, mock_binance_downloader):
        """Test multi-symbol load with partial failures"""
        mock_instance = mock_binance_downloader.return_value

        # Mock: BTC succeeds, ETH fails, SOL succeeds
        def mock_download(symbol, timeframe, days):
            if symbol == 'ETH':
                raise Exception("Network error")
            return sample_ohlcv_data

        mock_instance.download_ohlcv.side_effect = mock_download

        # Load symbols
        result = data_loader.load_multi_symbol(
            symbols=['BTC', 'ETH', 'SOL'],
            timeframe='1h',
            days=180
        )

        # Should have 2 symbols (ETH failed)
        assert len(result) == 2
        assert 'BTC' in result
        assert 'SOL' in result
        assert 'ETH' not in result

    def test_prepare_vectorbt_format_success(self, data_loader):
        """Test VectorBT format conversion"""
        # Create sample multi-symbol data
        dates = pd.date_range(start='2025-01-01', periods=100, freq='1h')

        btc_data = pd.DataFrame({
            'timestamp': dates,
            'open': range(100, 200),
            'high': range(105, 205),
            'low': range(95, 195),
            'close': range(101, 201),
            'volume': range(1000, 1100)
        })

        eth_data = pd.DataFrame({
            'timestamp': dates,
            'open': range(50, 150),
            'high': range(55, 155),
            'low': range(45, 145),
            'close': range(51, 151),
            'volume': range(2000, 2100)
        })

        data = {'BTC': btc_data, 'ETH': eth_data}

        # Convert to VectorBT format
        result = data_loader.prepare_vectorbt_format(data)

        # Verify structure
        assert isinstance(result.columns, pd.MultiIndex)
        assert result.columns.names == ['symbol', 'ohlcv']
        assert len(result) == 100

        # Verify data
        assert ('BTC', 'close') in result.columns
        assert ('ETH', 'close') in result.columns
        assert result[('BTC', 'close')].iloc[0] == 101

    def test_prepare_vectorbt_format_empty_data(self, data_loader):
        """Test VectorBT conversion with empty data"""
        with pytest.raises(ValueError, match="No data provided"):
            data_loader.prepare_vectorbt_format({})

    def test_prepare_vectorbt_format_no_common_timestamps(self, data_loader):
        """Test VectorBT conversion with non-overlapping timestamps"""
        # Create data with no common timestamps
        btc_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-01-01', periods=100, freq='1h'),
            'open': range(100, 200),
            'high': range(105, 205),
            'low': range(95, 195),
            'close': range(101, 201),
            'volume': range(1000, 1100)
        })

        eth_data = pd.DataFrame({
            'timestamp': pd.date_range(start='2025-02-01', periods=100, freq='1h'),  # Different dates
            'open': range(50, 150),
            'high': range(55, 155),
            'low': range(45, 145),
            'close': range(51, 151),
            'volume': range(2000, 2100)
        })

        data = {'BTC': btc_data, 'ETH': eth_data}

        # Should raise error
        with pytest.raises(ValueError, match="No common timestamps"):
            data_loader.prepare_vectorbt_format(data)

    def test_walk_forward_split_4_windows(self, data_loader, sample_ohlcv_data):
        """Test walk-forward split with 4 windows"""
        windows = data_loader.walk_forward_split(
            df=sample_ohlcv_data,
            n_windows=4,
            train_pct=0.75
        )

        # Should have 4 windows
        assert len(windows) == 4

        # Each window should have train and test
        for train_df, test_df in windows:
            assert isinstance(train_df, pd.DataFrame)
            assert isinstance(test_df, pd.DataFrame)
            assert len(train_df) > 0
            assert len(test_df) > 0

        # Train sets should expand
        train_sizes = [len(train) for train, _ in windows]
        assert train_sizes == sorted(train_sizes)  # Increasing

    def test_walk_forward_split_custom_split(self, data_loader, sample_ohlcv_data):
        """Test walk-forward split with custom train percentage"""
        windows = data_loader.walk_forward_split(
            df=sample_ohlcv_data,
            n_windows=3,
            train_pct=0.80
        )

        assert len(windows) == 3

        # First window should have ~80% train
        train_df, test_df = windows[0]
        total_len = len(sample_ohlcv_data)
        expected_train_len = int(total_len * 0.80)

        assert abs(len(train_df) - expected_train_len) <= 1  # Allow 1 row tolerance

    def test_get_available_symbols_empty_cache(self, data_loader):
        """Test getting symbols from empty cache"""
        symbols = data_loader.get_available_symbols()
        assert symbols == []

    def test_get_available_symbols_with_files(self, data_loader):
        """Test getting symbols from cache with files"""
        # Create fake cache files
        cache_dir = data_loader.cache_dir
        (cache_dir / "BTC_15m.parquet").touch()
        (cache_dir / "BTC_1h.parquet").touch()
        (cache_dir / "ETH_15m.parquet").touch()
        (cache_dir / "SOL_4h.parquet").touch()

        symbols = data_loader.get_available_symbols()

        # Should extract unique symbols
        assert set(symbols) == {'BTC', 'ETH', 'SOL'}
        assert symbols == sorted(symbols)  # Should be sorted


class TestDataLoaderEdgeCases:
    """Test edge cases and error conditions"""

    def test_load_single_symbol_downloader_exception(self, data_loader, mock_binance_downloader):
        """Test handling of downloader exceptions"""
        mock_instance = mock_binance_downloader.return_value
        mock_instance.download_ohlcv.side_effect = Exception("API error")

        with pytest.raises(Exception, match="API error"):
            data_loader.load_single_symbol(
                symbol='BTC',
                timeframe='1h',
                days=180
            )

    def test_walk_forward_split_single_window(self, data_loader, sample_ohlcv_data):
        """Test walk-forward with n_windows=1"""
        windows = data_loader.walk_forward_split(
            df=sample_ohlcv_data,
            n_windows=1,
            train_pct=0.75
        )

        assert len(windows) == 1
        train_df, test_df = windows[0]

        # Should split at 75%
        total_len = len(sample_ohlcv_data)
        assert len(train_df) == int(total_len * 0.75)

    def test_prepare_vectorbt_partial_overlap(self, data_loader):
        """Test VectorBT conversion with partial timestamp overlap"""
        # BTC: 100 candles
        btc_dates = pd.date_range(start='2025-01-01', periods=100, freq='1h')
        btc_data = pd.DataFrame({
            'timestamp': btc_dates,
            'open': range(100, 200),
            'high': range(105, 205),
            'low': range(95, 195),
            'close': range(101, 201),
            'volume': range(1000, 1100)
        })

        # ETH: 120 candles (overlap: first 100)
        eth_dates = pd.date_range(start='2025-01-01', periods=120, freq='1h')
        eth_data = pd.DataFrame({
            'timestamp': eth_dates,
            'open': range(50, 170),
            'high': range(55, 175),
            'low': range(45, 165),
            'close': range(51, 171),
            'volume': range(2000, 2120)
        })

        data = {'BTC': btc_data, 'ETH': eth_data}

        # Should use common timestamps (first 100)
        result = data_loader.prepare_vectorbt_format(data)

        assert len(result) == 100
        assert ('BTC', 'close') in result.columns
        assert ('ETH', 'close') in result.columns
