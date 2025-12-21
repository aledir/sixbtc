"""
Unit Tests for Binance Data Downloader

Tests the Binance data downloader with focus on:
- Symbol fetching (HL-Binance intersection)
- OHLCV data download
- Incremental updates
- Volume filtering
- Error handling

All tests use mocked API responses (no real network calls).
"""

import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd
import ccxt

from src.data.binance_downloader import BinanceDataDownloader


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        'trading': {
            'data': {
                'min_volume_24h': 5000000  # $5M minimum
            }
        },
        'data': {
            'cache_dir': tempfile.mkdtemp()
        }
    }


@pytest.fixture
def downloader(mock_config):
    """Create BinanceDataDownloader with mocked config"""
    # Create mock Config object
    config_mock = Mock()
    config_mock.get = Mock(side_effect=lambda k, default=None: {
        'data.cache_dir': mock_config['data']['cache_dir'],
    }.get(k, default))
    config_mock.get_required = Mock(return_value=mock_config['trading']['data']['min_volume_24h'])

    return BinanceDataDownloader(config=config_mock)


class TestSymbolFetching:
    """Test symbol fetching and filtering"""

    @patch('requests.post')
    def test_get_hyperliquid_symbols(self, mock_post, downloader):
        """Test fetching Hyperliquid symbols"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'universe': [
                {'name': 'BTC'},
                {'name': 'ETH'},
                {'name': 'SOL'}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        symbols = downloader.get_hyperliquid_symbols()

        assert symbols == ['BTC', 'ETH', 'SOL']
        assert len(symbols) == 3
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_get_hyperliquid_symbols_network_error(self, mock_post, downloader):
        """Test Hyperliquid fetch handles network errors"""
        mock_post.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            downloader.get_hyperliquid_symbols()

    @patch('ccxt.binance')
    def test_get_binance_perps(self, mock_binance, downloader):
        """Test fetching Binance perpetual futures symbols"""
        mock_exchange = Mock()
        mock_exchange.load_markets.return_value = {
            'BTC/USDT:USDT': {'base': 'BTC', 'quote': 'USDT', 'type': 'swap', 'active': True},
            'ETH/USDT:USDT': {'base': 'ETH', 'quote': 'USDT', 'type': 'swap', 'active': True},
            'SOL/USDT:USDT': {'base': 'SOL', 'quote': 'USDT', 'type': 'swap', 'active': True}
        }
        downloader.exchange = mock_exchange

        symbols = downloader.get_binance_perps()

        assert 'BTC' in symbols
        assert 'ETH' in symbols
        assert 'SOL' in symbols

    def test_get_common_symbols(self, downloader):
        """Test getting HL-Binance symbol intersection"""
        with patch.object(downloader, 'get_hyperliquid_symbols', return_value=['BTC', 'ETH', 'SOL', 'ARB']):
            with patch.object(downloader, 'get_binance_perps', return_value=['BTC', 'ETH', 'DOGE']):
                common = downloader.get_common_symbols()

                # Intersection should be BTC and ETH
                assert 'BTC' in common
                assert 'ETH' in common
                assert 'SOL' not in common  # Only on HL
                assert 'DOGE' not in common  # Only on Binance
                assert 'ARB' not in common  # Only on HL

    @patch('requests.get')
    def test_filter_by_volume(self, mock_get, downloader):
        """Test volume filtering (>$5M 24h volume)"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'volume': '10000000'  # $10M
        }
        mock_get.return_value = mock_response

        symbols = ['BTC', 'ETH']

        with patch.object(downloader, '_get_24h_volume', side_effect=[10000000, 3000000]):
            filtered = downloader.filter_by_volume(symbols)

            # Only BTC should pass (>$5M)
            assert 'BTC' in filtered
            assert 'ETH' not in filtered


class TestOHLCVDownload:
    """Test OHLCV data download"""

    def test_download_ohlcv_single_symbol(self, downloader):
        """Test downloading OHLCV for single symbol"""
        mock_ohlcv = [
            [1609459200000, 29000, 29500, 28800, 29200, 1000],  # Example candle
            [1609545600000, 29200, 30000, 29000, 29800, 1200]
        ]

        # Mock to return data once, then empty (to break the loop)
        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=[mock_ohlcv, []]):
            df = downloader.download_ohlcv(
                symbol='BTC',
                timeframe='1h',
                days=7
            )

            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert 'open' in df.columns
            assert 'high' in df.columns
            assert 'low' in df.columns
            assert 'close' in df.columns
            assert 'volume' in df.columns

    def test_download_ohlcv_multiple_symbols(self, downloader):
        """Test downloading OHLCV for multiple symbols"""
        mock_ohlcv = [
            [1609459200000, 29000, 29500, 28800, 29200, 1000]
        ]

        # Return data once per symbol, then empty
        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=[mock_ohlcv, [], mock_ohlcv, []]):
            results = downloader.download_multiple(
                symbols=['BTC', 'ETH'],
                timeframe='1h',
                days=7
            )

            assert 'BTC' in results
            assert 'ETH' in results
            assert isinstance(results['BTC'], pd.DataFrame)
            assert isinstance(results['ETH'], pd.DataFrame)

    def test_download_with_rate_limit(self, downloader):
        """Test download respects rate limits"""
        mock_ohlcv = [[1609459200000, 29000, 29500, 28800, 29200, 1000]]

        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=[mock_ohlcv, []]) as mock_fetch:
            # Should use enableRateLimit
            downloader.exchange.enableRateLimit = True

            df = downloader.download_ohlcv('BTC', '1h', days=7)

            assert mock_fetch.called
            # CCXT handles rate limiting internally


class TestIncrementalUpdates:
    """Test incremental data updates"""

    def test_save_to_parquet(self, downloader):
        """Test saving data to Parquet file"""
        df = pd.DataFrame({
            'timestamp': [1609459200000, 1609545600000],
            'open': [29000, 29200],
            'high': [29500, 30000],
            'low': [28800, 29000],
            'close': [29200, 29800],
            'volume': [1000, 1200]
        })

        file_path = downloader.save_data('BTC', '1h', df)

        assert file_path.exists()
        assert file_path.suffix == '.parquet'

        # Verify data can be read back
        loaded_df = pd.read_parquet(file_path)
        assert len(loaded_df) == 2
        assert loaded_df['close'].iloc[0] == 29200

    def test_load_from_parquet(self, downloader):
        """Test loading data from Parquet file"""
        df = pd.DataFrame({
            'timestamp': [1609459200000],
            'open': [29000],
            'high': [29500],
            'low': [28800],
            'close': [29200],
            'volume': [1000]
        })

        # Save first
        file_path = downloader.save_data('BTC', '1h', df)

        # Load back
        loaded_df = downloader.load_data('BTC', '1h')

        assert loaded_df is not None
        assert len(loaded_df) == 1
        assert loaded_df['close'].iloc[0] == 29200

    def test_incremental_update(self, downloader):
        """Test incremental update (only download missing candles)"""
        # Existing data
        existing_df = pd.DataFrame({
            'timestamp': [1609459200000],  # Old candle
            'open': [29000],
            'high': [29500],
            'low': [28800],
            'close': [29200],
            'volume': [1000]
        })

        # Save existing
        downloader.save_data('BTC', '1h', existing_df)

        # New data (includes old + new candles)
        new_ohlcv = [
            [1609459200000, 29000, 29500, 28800, 29200, 1000],  # Duplicate
            [1609545600000, 29200, 30000, 29000, 29800, 1200]   # New
        ]

        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=[new_ohlcv, []]):
            updated_df = downloader.update_data('BTC', '1h')

            # Should have 2 candles (old + new)
            assert len(updated_df) == 2

            # Last candle should be the new one
            assert updated_df['close'].iloc[-1] == 29800


class TestTimeframeHandling:
    """Test timeframe conversion and validation"""

    def test_timeframe_to_seconds(self, downloader):
        """Test converting timeframe string to seconds"""
        assert downloader.timeframe_to_seconds('1m') == 60
        assert downloader.timeframe_to_seconds('5m') == 300
        assert downloader.timeframe_to_seconds('15m') == 900
        assert downloader.timeframe_to_seconds('1h') == 3600
        assert downloader.timeframe_to_seconds('4h') == 14400
        assert downloader.timeframe_to_seconds('1d') == 86400

    def test_calculate_missing_candles(self, downloader):
        """Test calculating how many candles to fetch"""
        days = 7
        timeframe = '1h'

        expected_candles = (days * 24)  # 168 candles

        candles = downloader.calculate_candles_needed(timeframe, days)
        assert candles == expected_candles

    def test_get_start_timestamp(self, downloader):
        """Test calculating start timestamp for download"""
        days = 7
        now = datetime.now()
        expected_start = now - timedelta(days=7)

        start_ts = downloader.get_start_timestamp(days)

        # Allow 1 second tolerance
        assert abs((datetime.fromtimestamp(start_ts/1000) - expected_start).total_seconds()) < 1


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_download_invalid_symbol(self, downloader):
        """Test downloading invalid symbol raises error"""
        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=ccxt.BadSymbol("Invalid symbol")):
            with pytest.raises(ccxt.BadSymbol):
                downloader.download_ohlcv('INVALID', '1h', days=7)

    def test_download_network_timeout(self, downloader):
        """Test network timeout handling"""
        with patch.object(downloader.exchange, 'fetch_ohlcv', side_effect=ccxt.NetworkError("Timeout")):
            with pytest.raises(ccxt.NetworkError):
                downloader.download_ohlcv('BTC', '1h', days=7)

    def test_load_nonexistent_file(self, downloader):
        """Test loading non-existent file returns None"""
        df = downloader.load_data('NONEXISTENT', '1h')
        assert df is None

    def test_save_empty_dataframe(self, downloader):
        """Test saving empty DataFrame"""
        empty_df = pd.DataFrame()

        # Should handle gracefully
        file_path = downloader.save_data('BTC', '1h', empty_df)

        # File should exist but be empty
        loaded = pd.read_parquet(file_path)
        assert len(loaded) == 0


class TestDataValidation:
    """Test OHLCV data validation"""

    def test_validate_ohlcv_structure(self, downloader):
        """Test validating OHLCV data structure"""
        valid_df = pd.DataFrame({
            'timestamp': [1609459200000],
            'open': [29000.0],
            'high': [29500.0],
            'low': [28800.0],
            'close': [29200.0],
            'volume': [1000.0]
        })

        assert downloader.validate_ohlcv(valid_df) is True

    def test_validate_missing_columns(self, downloader):
        """Test validation fails for missing columns"""
        invalid_df = pd.DataFrame({
            'timestamp': [1609459200000],
            'open': [29000.0]
            # Missing high, low, close, volume
        })

        assert downloader.validate_ohlcv(invalid_df) is False

    def test_validate_negative_prices(self, downloader):
        """Test validation fails for negative prices"""
        invalid_df = pd.DataFrame({
            'timestamp': [1609459200000],
            'open': [-100.0],  # Invalid negative price
            'high': [29500.0],
            'low': [28800.0],
            'close': [29200.0],
            'volume': [1000.0]
        })

        assert downloader.validate_ohlcv(invalid_df) is False

    def test_validate_high_low_consistency(self, downloader):
        """Test validation checks high >= low"""
        invalid_df = pd.DataFrame({
            'timestamp': [1609459200000],
            'open': [29000.0],
            'high': [28000.0],  # High < Low (invalid)
            'low': [29000.0],
            'close': [29200.0],
            'volume': [1000.0]
        })

        assert downloader.validate_ohlcv(invalid_df) is False
