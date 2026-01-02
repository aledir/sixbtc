"""
Unit tests for BacktestDataLoader

Tests cache-based data loading for backtesting.
BacktestDataLoader reads ONLY from parquet cache files (no downloads).
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.backtester.data_loader import BacktestDataLoader
from src.backtester.cache_reader import CacheNotFoundError


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV DataFrame"""
    dates = pd.date_range(start='2025-01-01', periods=100, freq='15min', tz='UTC')
    return pd.DataFrame({
        'timestamp': dates,
        'open': range(100, 200),
        'high': range(105, 205),
        'low': range(95, 195),
        'close': range(101, 201),
        'volume': range(1000, 1100)
    })


@pytest.fixture
def cache_dir(tmp_path):
    """Create temporary cache directory"""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache


@pytest.fixture
def populated_cache(cache_dir, sample_ohlcv_data):
    """Create cache with sample parquet files"""
    # Save BTC 15m data
    btc_path = cache_dir / "BTC_15m.parquet"
    sample_ohlcv_data.to_parquet(btc_path)

    # Save ETH 15m data with different dates
    eth_dates = pd.date_range(start='2025-01-01', periods=100, freq='15min', tz='UTC')
    eth_data = pd.DataFrame({
        'timestamp': eth_dates,
        'open': range(50, 150),
        'high': range(55, 155),
        'low': range(45, 145),
        'close': range(51, 151),
        'volume': range(2000, 2100)
    })
    eth_path = cache_dir / "ETH_15m.parquet"
    eth_data.to_parquet(eth_path)

    # Save BTC 1h data
    btc_1h_dates = pd.date_range(start='2025-01-01', periods=100, freq='1h', tz='UTC')
    btc_1h_data = pd.DataFrame({
        'timestamp': btc_1h_dates,
        'open': range(100, 200),
        'high': range(105, 205),
        'low': range(95, 195),
        'close': range(101, 201),
        'volume': range(1000, 1100)
    })
    btc_1h_path = cache_dir / "BTC_1h.parquet"
    btc_1h_data.to_parquet(btc_1h_path)

    return cache_dir


class TestBacktestDataLoader:
    """Test suite for BacktestDataLoader"""

    def test_initialization(self, cache_dir):
        """Test data loader initialization with existing cache"""
        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        assert loader.cache_dir == cache_dir
        assert loader.cache_reader is not None

    def test_initialization_missing_cache(self, tmp_path):
        """Test that initialization fails when cache doesn't exist"""
        non_existent = tmp_path / "non_existent"

        with pytest.raises(CacheNotFoundError, match="Cache directory does not exist"):
            BacktestDataLoader(cache_dir=str(non_existent))

    def test_load_single_symbol_success(self, populated_cache, sample_ohlcv_data):
        """Test loading single symbol data from cache"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        result = loader.load_single_symbol(
            symbol='BTC',
            timeframe='15m',
            days=180
        )

        assert len(result) == 100
        assert 'timestamp' in result.columns
        assert 'close' in result.columns

    def test_load_single_symbol_not_found(self, populated_cache):
        """Test loading non-existent symbol raises error"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        with pytest.raises(CacheNotFoundError, match="Cache not found"):
            loader.load_single_symbol(
                symbol='XYZ',
                timeframe='15m',
                days=180
            )

    def test_load_single_symbol_with_end_date(self, populated_cache, sample_ohlcv_data):
        """Test loading with end date filter"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        # End date in the middle of the data
        end_date = sample_ohlcv_data['timestamp'].iloc[50]
        result = loader.load_single_symbol(
            symbol='BTC',
            timeframe='15m',
            days=180,
            end_date=end_date
        )

        # Should filter data
        assert len(result) <= 51  # Up to and including index 50
        assert result['timestamp'].max() <= end_date

    def test_load_multi_symbol_success(self, populated_cache):
        """Test loading multiple symbols"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        # Use days=1 and low coverage threshold since test data is only ~100 candles
        result = loader.load_multi_symbol(
            symbols=['BTC', 'ETH'],
            timeframe='15m',
            days=1,
            min_coverage_pct=0.5
        )

        assert len(result) == 2
        assert 'BTC' in result
        assert 'ETH' in result

    def test_load_multi_symbol_partial_data(self, populated_cache):
        """Test multi-symbol load with some missing symbols"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        # Request BTC, ETH (exist) and XYZ (doesn't exist)
        # Use days=1 and low coverage threshold since test data is only ~100 candles
        result = loader.load_multi_symbol(
            symbols=['BTC', 'ETH', 'XYZ'],
            timeframe='15m',
            days=1,
            min_coverage_pct=0.5
        )

        # Should have 2 symbols (XYZ not cached)
        assert len(result) == 2
        assert 'BTC' in result
        assert 'ETH' in result
        assert 'XYZ' not in result

    def test_prepare_vectorbt_format_success(self, populated_cache):
        """Test VectorBT format conversion"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        # Load multi-symbol data
        # Use days=1 and low coverage threshold since test data is only ~100 candles
        data = loader.load_multi_symbol(
            symbols=['BTC', 'ETH'],
            timeframe='15m',
            days=1,
            min_coverage_pct=0.5
        )

        # Convert to VectorBT format
        result = loader.prepare_vectorbt_format(data)

        # Verify structure
        assert isinstance(result.columns, pd.MultiIndex)
        assert result.columns.names == ['symbol', 'ohlcv']
        assert len(result) > 0  # Some common timestamps should exist

        # Verify data
        assert ('BTC', 'close') in result.columns
        assert ('ETH', 'close') in result.columns

    def test_prepare_vectorbt_format_empty_data(self, populated_cache):
        """Test VectorBT conversion with empty data"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        with pytest.raises(ValueError, match="No data provided"):
            loader.prepare_vectorbt_format({})

    def test_prepare_vectorbt_format_no_common_timestamps(self, cache_dir):
        """Test VectorBT conversion with non-overlapping timestamps"""
        # Create data with no common timestamps
        btc_dates = pd.date_range(start='2025-01-01', periods=100, freq='1h', tz='UTC')
        btc_data = pd.DataFrame({
            'timestamp': btc_dates,
            'open': range(100, 200),
            'high': range(105, 205),
            'low': range(95, 195),
            'close': range(101, 201),
            'volume': range(1000, 1100)
        })
        (cache_dir / "BTC_4h.parquet").write_bytes(btc_data.to_parquet())

        # ETH with completely different dates
        eth_dates = pd.date_range(start='2025-03-01', periods=100, freq='1h', tz='UTC')
        eth_data = pd.DataFrame({
            'timestamp': eth_dates,
            'open': range(50, 150),
            'high': range(55, 155),
            'low': range(45, 145),
            'close': range(51, 151),
            'volume': range(2000, 2100)
        })
        (cache_dir / "ETH_4h.parquet").write_bytes(eth_data.to_parquet())

        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        data = {
            'BTC': btc_data,
            'ETH': eth_data
        }

        with pytest.raises(ValueError, match="No common timestamps"):
            loader.prepare_vectorbt_format(data)

    def test_walk_forward_split_4_windows(self, populated_cache, sample_ohlcv_data):
        """Test walk-forward split with 4 windows"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        windows = loader.walk_forward_split(
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

    def test_walk_forward_split_custom_split(self, populated_cache, sample_ohlcv_data):
        """Test walk-forward split with custom train percentage"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        windows = loader.walk_forward_split(
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

    def test_get_available_symbols_empty_cache(self, cache_dir):
        """Test getting symbols from empty cache"""
        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        symbols = loader.get_available_symbols()
        assert symbols == []

    def test_get_available_symbols_with_files(self, populated_cache):
        """Test getting symbols from cache with files"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        symbols = loader.get_available_symbols()

        # Should extract unique symbols
        assert set(symbols) == {'BTC', 'ETH'}
        assert symbols == sorted(symbols)  # Should be sorted

    def test_get_available_timeframes(self, populated_cache):
        """Test getting available timeframes for a symbol"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        timeframes = loader.get_available_timeframes('BTC')

        # BTC should have 15m and 1h
        assert '15m' in timeframes
        assert '1h' in timeframes


class TestDataLoaderTrainingHoldout:
    """Test training/holdout data loading"""

    def test_load_training_holdout(self, tmp_path):
        """Test loading training and holdout splits"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        # Create 40 days of data
        dates = pd.date_range(
            start='2025-01-01',
            periods=40 * 24,  # 40 days, hourly
            freq='1h',
            tz='UTC'
        )
        data = pd.DataFrame({
            'timestamp': dates,
            'open': range(len(dates)),
            'high': range(len(dates)),
            'low': range(len(dates)),
            'close': range(len(dates)),
            'volume': range(len(dates))
        })
        data.to_parquet(cache_dir / "BTC_1h.parquet")

        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        training_df, holdout_df = loader.load_training_holdout(
            symbol='BTC',
            timeframe='1h',
            training_days=30,
            holdout_days=10
        )

        # Should have non-empty splits
        assert len(training_df) > 0
        assert len(holdout_df) > 0

        # Training should be older than holdout
        assert training_df['timestamp'].max() < holdout_df['timestamp'].min()


class TestDataLoaderEdgeCases:
    """Test edge cases and error conditions"""

    def test_walk_forward_split_single_window(self, populated_cache, sample_ohlcv_data):
        """Test walk-forward with n_windows=1"""
        loader = BacktestDataLoader(cache_dir=str(populated_cache))

        windows = loader.walk_forward_split(
            df=sample_ohlcv_data,
            n_windows=1,
            train_pct=0.75
        )

        assert len(windows) == 1
        train_df, test_df = windows[0]

        # Should split at 75%
        total_len = len(sample_ohlcv_data)
        assert len(train_df) == int(total_len * 0.75)

    def test_prepare_vectorbt_partial_overlap(self, cache_dir):
        """Test VectorBT conversion with partial timestamp overlap"""
        # BTC: 100 candles starting Jan 1
        btc_dates = pd.date_range(start='2025-01-01', periods=100, freq='1h', tz='UTC')
        btc_data = pd.DataFrame({
            'timestamp': btc_dates,
            'open': range(100, 200),
            'high': range(105, 205),
            'low': range(95, 195),
            'close': range(101, 201),
            'volume': range(1000, 1100)
        })
        btc_data.to_parquet(cache_dir / "BTC_1h.parquet")

        # ETH: 120 candles starting Jan 1 (overlap: first 100)
        eth_dates = pd.date_range(start='2025-01-01', periods=120, freq='1h', tz='UTC')
        eth_data = pd.DataFrame({
            'timestamp': eth_dates,
            'open': range(50, 170),
            'high': range(55, 175),
            'low': range(45, 165),
            'close': range(51, 171),
            'volume': range(2000, 2120)
        })
        eth_data.to_parquet(cache_dir / "ETH_1h.parquet")

        loader = BacktestDataLoader(cache_dir=str(cache_dir))

        # Load data
        data = {
            'BTC': btc_data,
            'ETH': eth_data
        }

        # Should use common timestamps (first 100)
        result = loader.prepare_vectorbt_format(data)

        assert len(result) == 100
        assert ('BTC', 'close') in result.columns
        assert ('ETH', 'close') in result.columns
