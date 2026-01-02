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
        'data_scheduler.min_volume_usd': mock_config['trading']['data']['min_volume_24h'],
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
        # Use timestamps within the last 7 days so they don't get filtered
        import time
        now_ms = int(time.time() * 1000)
        hour_ms = 3600 * 1000
        mock_ohlcv = [
            [now_ms - 2 * hour_ms, 29000, 29500, 28800, 29200, 1000],  # 2 hours ago
            [now_ms - hour_ms, 29200, 30000, 29000, 29800, 1200]       # 1 hour ago
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
        """Test saving empty DataFrame returns None (not saved)"""
        empty_df = pd.DataFrame()

        # Should skip save and return None
        result = downloader.save_data('BTC', '1h', empty_df)

        assert result is None


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


class TestGapDetection:
    """Test gap detection functionality"""

    def test_detect_gaps_no_gaps(self, downloader):
        """Test detection with continuous data"""
        now = pd.Timestamp.now(tz='UTC')
        timestamps = [now - pd.Timedelta(hours=i) for i in range(10, 0, -1)]

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': [100] * 10,
            'high': [110] * 10,
            'low': [90] * 10,
            'close': [105] * 10,
            'volume': [1000] * 10
        })

        gaps = downloader.detect_gaps(df, '1h')
        assert len(gaps) == 0

    def test_detect_gaps_single_gap(self, downloader):
        """Test detection with single gap"""
        now = pd.Timestamp.now(tz='UTC')

        # Create data with 3 hour gap
        timestamps = [
            now - pd.Timedelta(hours=10),
            now - pd.Timedelta(hours=9),
            now - pd.Timedelta(hours=8),
            # Gap: hours 7, 6, 5 missing
            now - pd.Timedelta(hours=4),
            now - pd.Timedelta(hours=3),
        ]

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': [100] * 5,
            'high': [110] * 5,
            'low': [90] * 5,
            'close': [105] * 5,
            'volume': [1000] * 5
        })

        gaps = downloader.detect_gaps(df, '1h')

        assert len(gaps) == 1
        gap_start, gap_end, missing_count = gaps[0]
        assert missing_count == 3

    def test_detect_gaps_multiple_gaps(self, downloader):
        """Test detection with multiple gaps"""
        now = pd.Timestamp.now(tz='UTC')

        timestamps = [
            now - pd.Timedelta(hours=10),
            now - pd.Timedelta(hours=9),
            # Gap 1: hour 8 missing
            now - pd.Timedelta(hours=7),
            now - pd.Timedelta(hours=6),
            # Gap 2: hours 5, 4 missing
            now - pd.Timedelta(hours=3),
        ]

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': [100] * 5,
            'high': [110] * 5,
            'low': [90] * 5,
            'close': [105] * 5,
            'volume': [1000] * 5
        })

        gaps = downloader.detect_gaps(df, '1h')

        assert len(gaps) == 2

    def test_detect_gaps_empty_df(self, downloader):
        """Test detection with empty DataFrame"""
        df = pd.DataFrame()
        gaps = downloader.detect_gaps(df, '1h')
        assert len(gaps) == 0

    def test_detect_gaps_single_row(self, downloader):
        """Test detection with single row"""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'open': [100],
            'high': [110],
            'low': [90],
            'close': [105],
            'volume': [1000]
        })
        gaps = downloader.detect_gaps(df, '1h')
        assert len(gaps) == 0

    def test_verify_data_integrity_valid(self, downloader):
        """Test integrity check on valid data"""
        now = pd.Timestamp.now(tz='UTC')
        timestamps = [now - pd.Timedelta(hours=i) for i in range(5, 0, -1)]

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': [100.0] * 5,
            'high': [110.0] * 5,
            'low': [90.0] * 5,
            'close': [105.0] * 5,
            'volume': [1000.0] * 5
        })

        downloader.save_data('TEST', '1h', df)

        result = downloader.verify_data_integrity('TEST', '1h')

        assert result['valid'] is True
        assert result['gap_count'] == 0
        assert result['candle_count'] == 5

    def test_verify_data_integrity_with_gaps(self, downloader):
        """Test integrity check detects gaps"""
        now = pd.Timestamp.now(tz='UTC')
        timestamps = [
            now - pd.Timedelta(hours=5),
            now - pd.Timedelta(hours=4),
            # Gap: hour 3 missing
            now - pd.Timedelta(hours=2),
        ]

        df = pd.DataFrame({
            'timestamp': timestamps,
            'open': [100.0] * 3,
            'high': [110.0] * 3,
            'low': [90.0] * 3,
            'close': [105.0] * 3,
            'volume': [1000.0] * 3
        })

        downloader.save_data('TEST', '1h', df)

        result = downloader.verify_data_integrity('TEST', '1h')

        assert result['valid'] is False
        assert result['gap_count'] == 1

    def test_verify_data_integrity_missing_file(self, downloader):
        """Test integrity check for missing file"""
        result = downloader.verify_data_integrity('NONEXISTENT', '1h')

        assert result['valid'] is False
        assert result['candle_count'] == 0


class TestDownloadForPairs:
    """Test download_for_pairs method"""

    def test_download_for_pairs_with_active_coins(self, downloader):
        """Test download_for_pairs with mocked database"""
        # Mock the database query
        mock_coins = [MagicMock(symbol='BTC'), MagicMock(symbol='ETH')]

        with patch('src.database.get_session') as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value.all.return_value = mock_coins
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            with patch.object(downloader, 'download_all_timeframes') as mock_download:
                mock_download.return_value = {'BTC': {'1h': MagicMock()}}

                result = downloader.download_for_pairs(days=7)

                mock_download.assert_called_once()
                call_kwargs = mock_download.call_args
                symbols = call_kwargs[1].get('symbols') or call_kwargs[0][0]
                assert 'BTC' in symbols
                assert 'ETH' in symbols

    def test_download_for_pairs_empty_db(self, downloader):
        """Test download_for_pairs with empty database"""
        with patch('src.database.get_session') as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value.all.return_value = []
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            result = downloader.download_for_pairs()

            assert result == {}

    def test_download_for_pairs_passes_days_param(self, downloader):
        """Test download_for_pairs passes days parameter correctly"""
        mock_coins = [MagicMock(symbol='BTC')]

        with patch('src.database.get_session') as mock_session:
            mock_query = MagicMock()
            mock_query.filter.return_value.all.return_value = mock_coins
            mock_session.return_value.__enter__.return_value.query.return_value = mock_query

            with patch.object(downloader, 'download_all_timeframes') as mock_download:
                mock_download.return_value = {}

                downloader.download_for_pairs(days=30, force_refresh=True)

                mock_download.assert_called_once()
                call_kwargs = mock_download.call_args[1]
                assert call_kwargs['days'] == 30
                assert call_kwargs['force_refresh'] is True


class TestAutoHealing:
    """Test auto-healing and resilience features"""

    def test_load_data_deletes_corrupted_file(self, downloader):
        """Corrupted parquet should be deleted and return None"""
        file_path = downloader.data_dir / "CORRUPT_1h.parquet"

        # Write garbage data
        with open(file_path, 'wb') as f:
            f.write(b'this is not valid parquet data at all!')

        # load_data should detect corruption, delete, and return None
        result = downloader.load_data('CORRUPT', '1h')

        assert result is None
        assert not file_path.exists()

    def test_load_data_deletes_empty_file(self, downloader):
        """Empty file (0 bytes) should be deleted"""
        file_path = downloader.data_dir / "EMPTY_1h.parquet"

        # Create empty file
        file_path.touch()

        result = downloader.load_data('EMPTY', '1h')

        assert result is None
        assert not file_path.exists()

    def test_load_data_deletes_too_small_file(self, downloader):
        """File smaller than MIN_PARQUET_SIZE should be deleted"""
        from src.data.binance_downloader import MIN_PARQUET_SIZE

        file_path = downloader.data_dir / "SMALL_1h.parquet"

        # Write file smaller than minimum
        with open(file_path, 'wb') as f:
            f.write(b'PAR1')  # 4 bytes, less than MIN_PARQUET_SIZE

        result = downloader.load_data('SMALL', '1h')

        assert result is None
        assert not file_path.exists()

    def test_save_data_atomic_write(self, downloader):
        """Save should use temp file + rename (no partial files)"""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'open': [100.0],
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        result = downloader.save_data('ATOMIC', '1h', df)

        assert result is not None
        assert result.exists()

        # No temp files should remain
        tmp_files = list(downloader.data_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_save_data_skips_empty_dataframe(self, downloader):
        """Empty DataFrame should not be saved"""
        empty_df = pd.DataFrame()

        result = downloader.save_data('EMPTY', '1h', empty_df)

        assert result is None
        assert not (downloader.data_dir / "EMPTY_1h.parquet").exists()

    def test_save_data_skips_none_dataframe(self, downloader):
        """None DataFrame should not be saved"""
        result = downloader.save_data('NONE', '1h', None)

        assert result is None

    def test_save_data_rejects_invalid_ohlcv(self, downloader):
        """Invalid OHLCV data should not be saved"""
        invalid_df = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'open': [-100.0],  # Invalid negative price
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        result = downloader.save_data('INVALID', '1h', invalid_df)

        assert result is None
        assert not (downloader.data_dir / "INVALID_1h.parquet").exists()

    def test_save_data_cleans_tmp_on_failure(self, downloader, monkeypatch):
        """Temp file should be cleaned if write fails"""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'open': [100.0],
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        # Monkeypatch to_parquet to raise exception
        def fail_write(*args, **kwargs):
            raise IOError("Simulated disk failure")

        monkeypatch.setattr(pd.DataFrame, 'to_parquet', fail_write)

        result = downloader.save_data('FAIL', '1h', df)

        assert result is None
        # No tmp files should remain
        tmp_files = list(downloader.data_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_cleanup_temp_files_on_init(self):
        """Orphan .tmp files should be cleaned on init"""
        import tempfile

        # Create temp directory with orphan .tmp files
        tmp_dir = tempfile.mkdtemp()
        tmp_file = Path(tmp_dir) / "orphan.parquet.tmp"
        tmp_file.touch()

        # Create mock config
        config_mock = Mock()
        config_mock.get = Mock(side_effect=lambda k, default=None: {
            'data.cache_dir': tmp_dir,
            'data_scheduler.min_volume_usd': 0,
        }.get(k, default))

        # Init should cleanup tmp files
        downloader = BinanceDataDownloader(config=config_mock)

        assert not tmp_file.exists()

    def test_sanitize_deduplicates(self, downloader):
        """Sanitize should remove duplicate timestamps"""
        now = pd.Timestamp.now(tz='UTC')
        df = pd.DataFrame({
            'timestamp': [now, now, now - pd.Timedelta(hours=1)],  # Duplicate
            'open': [100.0, 101.0, 102.0],
            'high': [110.0, 111.0, 112.0],
            'low': [90.0, 91.0, 92.0],
            'close': [105.0, 106.0, 107.0],
            'volume': [1000.0, 1001.0, 1002.0]
        })

        result = downloader._sanitize_dataframe(df)

        assert len(result) == 2  # Deduplicated
        # Should keep last for duplicates
        assert result[result['timestamp'] == now]['open'].iloc[0] == 101.0

    def test_sanitize_sorts(self, downloader):
        """Sanitize should sort by timestamp"""
        now = pd.Timestamp.now(tz='UTC')
        df = pd.DataFrame({
            'timestamp': [
                now,
                now - pd.Timedelta(hours=2),
                now - pd.Timedelta(hours=1)
            ],  # Out of order
            'open': [100.0, 102.0, 101.0],
            'high': [110.0, 112.0, 111.0],
            'low': [90.0, 92.0, 91.0],
            'close': [105.0, 107.0, 106.0],
            'volume': [1000.0, 1002.0, 1001.0]
        })

        result = downloader._sanitize_dataframe(df)

        # First row should be oldest
        assert result.iloc[0]['open'] == 102.0

    def test_sanitize_removes_nan(self, downloader):
        """Sanitize should remove rows with NaN in critical columns"""
        import numpy as np
        now = pd.Timestamp.now(tz='UTC')

        df = pd.DataFrame({
            'timestamp': [
                now - pd.Timedelta(hours=2),
                now - pd.Timedelta(hours=1),
                now
            ],
            'open': [100.0, np.nan, 102.0],  # NaN in middle row
            'high': [110.0, 111.0, 112.0],
            'low': [90.0, 91.0, 92.0],
            'close': [105.0, 106.0, 107.0],
            'volume': [1000.0, 1001.0, 1002.0]
        })

        result = downloader._sanitize_dataframe(df)

        assert len(result) == 2  # NaN row removed
        assert 101.0 not in result['high'].values

    def test_verify_data_dir_writable(self, downloader):
        """Test that init verifies directory is writable"""
        # Current downloader should have passed the check
        # Just verify the data_dir exists and we can write
        test_file = downloader.data_dir / '.test_write'
        test_file.touch()
        assert test_file.exists()
        test_file.unlink()

    def test_get_cached_data_uses_load_data(self, downloader):
        """get_cached_data should delegate to load_data for auto-repair"""
        df = pd.DataFrame({
            'timestamp': [pd.Timestamp.now(tz='UTC')],
            'open': [100.0],
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        # Save valid data
        downloader.save_data('CACHED', '1h', df)

        # get_cached_data should return same as load_data
        result = downloader.get_cached_data('CACHED', '1h')

        assert result is not None
        assert len(result) == 1
        assert result['close'].iloc[0] == 105.0


class TestCacheMetadata:
    """Test metadata-based auto-healing features"""

    def test_metadata_created_on_save(self, downloader):
        """Metadata file should be created when saving data"""
        from src.data.binance_downloader import CacheMetadata

        now = pd.Timestamp.now(tz='UTC')
        df = pd.DataFrame({
            'timestamp': [now - pd.Timedelta(hours=2), now - pd.Timedelta(hours=1), now],
            'open': [100.0, 101.0, 102.0],
            'high': [110.0, 111.0, 112.0],
            'low': [90.0, 91.0, 92.0],
            'close': [105.0, 106.0, 107.0],
            'volume': [1000.0, 1001.0, 1002.0]
        })

        # Save with metadata
        downloader._save_metadata('META', '1h', df, is_full_history=True, listing_date_ts=1500000000000)

        # Check metadata file exists
        meta_path = downloader._get_meta_path('META', '1h')
        assert meta_path.exists()

        # Load and verify
        meta = CacheMetadata.from_file(meta_path)
        assert meta is not None
        assert meta.is_full_history is True
        assert meta.candle_count == 3
        assert meta.listing_date_ts == 1500000000000

    def test_metadata_loaded_correctly(self, downloader):
        """Metadata should be loadable after save"""
        now = pd.Timestamp.now(tz='UTC')
        df = pd.DataFrame({
            'timestamp': [now],
            'open': [100.0],
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        downloader._save_metadata('LOAD', '1h', df, is_full_history=False, listing_date_ts=1600000000000)

        meta = downloader._load_metadata('LOAD', '1h')

        assert meta is not None
        assert meta.is_full_history is False
        assert meta.listing_date_ts == 1600000000000

    def test_metadata_returns_none_for_missing(self, downloader):
        """Loading missing metadata should return None"""
        meta = downloader._load_metadata('NONEXISTENT', '1h')
        assert meta is None

    def test_metadata_returns_none_for_corrupted(self, downloader):
        """Loading corrupted metadata should return None"""
        meta_path = downloader._get_meta_path('CORRUPT', '1h')
        meta_path.write_text("not valid json {{{")

        meta = downloader._load_metadata('CORRUPT', '1h')
        assert meta is None

    def test_metadata_deleted_with_cache(self, downloader):
        """Metadata should be deleted when cache is cleared"""
        now = pd.Timestamp.now(tz='UTC')
        df = pd.DataFrame({
            'timestamp': [now],
            'open': [100.0],
            'high': [110.0],
            'low': [90.0],
            'close': [105.0],
            'volume': [1000.0]
        })

        # Save data and metadata
        downloader.save_data('CLEAR', '1h', df)
        downloader._save_metadata('CLEAR', '1h', df, is_full_history=True)

        data_path = downloader.data_dir / 'CLEAR_1h.parquet'
        meta_path = downloader._get_meta_path('CLEAR', '1h')

        assert data_path.exists()
        assert meta_path.exists()

        # Clear cache
        downloader.clear_cache('CLEAR')

        assert not data_path.exists()
        assert not meta_path.exists()

    def test_get_symbol_listing_date_returns_timestamp(self, downloader):
        """get_symbol_listing_date should return timestamp in ms"""
        # Mock the exchange to return a predictable first candle
        listing_ts = 1568937600000  # 2019-09-20

        downloader.exchange.fetch_ohlcv = Mock(return_value=[
            [listing_ts, 100, 110, 90, 105, 1000]
        ])

        result = downloader.get_symbol_listing_date('BTC')

        assert result == listing_ts
        downloader.exchange.fetch_ohlcv.assert_called_once()

    def test_get_symbol_listing_date_caches_result(self, downloader):
        """Listing date should be cached after first query"""
        listing_ts = 1568937600000

        downloader.exchange.fetch_ohlcv = Mock(return_value=[
            [listing_ts, 100, 110, 90, 105, 1000]
        ])

        # First call
        result1 = downloader.get_symbol_listing_date('ETH')
        # Second call
        result2 = downloader.get_symbol_listing_date('ETH')

        assert result1 == result2
        # Should only call exchange once
        assert downloader.exchange.fetch_ohlcv.call_count == 1

    def test_get_symbol_listing_date_fallback_on_error(self, downloader):
        """Should return fallback date on error"""
        downloader.exchange.fetch_ohlcv = Mock(side_effect=Exception("API error"))

        result = downloader.get_symbol_listing_date('FAIL')

        # Should return 2020-01-01 fallback
        assert result is not None
        # Check it's a reasonable timestamp (2020)
        from datetime import datetime, timezone
        fallback = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        assert result == fallback

    def test_delete_metadata(self, downloader):
        """_delete_metadata should remove metadata file"""
        meta_path = downloader._get_meta_path('DEL', '1h')
        meta_path.write_text('{"test": true}')

        assert meta_path.exists()

        downloader._delete_metadata('DEL', '1h')

        assert not meta_path.exists()

    def test_delete_metadata_nonexistent(self, downloader):
        """_delete_metadata should not error on missing file"""
        # Should not raise
        downloader._delete_metadata('NONEXISTENT', '1h')
