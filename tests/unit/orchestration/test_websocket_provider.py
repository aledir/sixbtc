"""
Tests for MultiWebSocketDataProvider

Following CLAUDE.md testing requirements:
- Test in isolation
- Mock external dependencies
- Cover all edge cases
"""

import pytest
import threading
from datetime import datetime
import pandas as pd

from src.orchestration.websocket_provider import (
    MultiWebSocketDataProvider,
    CandleData,
    MarketCache
)


@pytest.fixture
def config(dry_run_config):
    """Test configuration - use centralized dry_run_config"""
    return dry_run_config


@pytest.fixture
def provider(config):
    """Create provider instance"""
    symbols = ['BTC', 'ETH', 'SOL']
    timeframes = ['15m', '1h']
    return MultiWebSocketDataProvider(config, symbols, timeframes)


class TestMarketCache:
    """Test MarketCache dataclass"""

    def test_cache_creation(self):
        """Test cache creation"""
        cache = MarketCache()

        assert isinstance(cache.data, dict)
        assert hasattr(cache.lock, 'acquire')  # Check if it's a lock object
        assert hasattr(cache.lock, 'release')  # Check if it's a lock object
        assert isinstance(cache.last_update, dict)
        assert len(cache.data) == 0

    def test_cache_thread_safety(self):
        """Test cache is thread-safe"""
        cache = MarketCache()
        errors = []

        def worker():
            try:
                with cache.lock:
                    cache.data['test'] = pd.DataFrame()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert 'test' in cache.data


class TestCandleData:
    """Test CandleData dataclass"""

    def test_candle_creation(self):
        """Test candle creation"""
        candle = CandleData(
            symbol='BTC',
            timeframe='15m',
            timestamp=datetime.now(),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=1000.0
        )

        assert candle.symbol == 'BTC'
        assert candle.timeframe == '15m'
        assert candle.open == 50000.0
        assert candle.high == 50100.0
        assert candle.low == 49900.0
        assert candle.close == 50050.0
        assert candle.volume == 1000.0


class TestMultiWebSocketDataProvider:
    """Test MultiWebSocketDataProvider"""

    def test_initialization(self, config):
        """Test provider initialization"""
        symbols = ['BTC', 'ETH', 'SOL', 'ARB', 'AVAX']
        timeframes = ['15m', '30m', '1h']

        provider = MultiWebSocketDataProvider(config, symbols, timeframes)

        assert provider.symbols == symbols
        assert provider.timeframes == timeframes
        assert provider.max_symbols_per_ws == 100
        assert provider.auto_reconnect is True
        assert not provider.running
        assert len(provider.websockets) == 0

    def test_initialization_fast_fail_missing_config(self):
        """Test fast fail if config missing"""
        bad_config = {'hyperliquid': {}}  # Missing websocket key

        with pytest.raises(KeyError):
            MultiWebSocketDataProvider(bad_config, ['BTC'], ['15m'])

    def test_chunk_symbols(self, provider):
        """Test symbol chunking"""
        chunks = provider._chunk_symbols()

        # 3 symbols, max 100 per chunk → should be 1 chunk
        assert len(chunks) == 1
        assert chunks[0] == ['BTC', 'ETH', 'SOL']

    def test_chunk_symbols_large(self, config):
        """Test symbol chunking with many symbols"""
        # Create 250 symbols
        symbols = [f"SYM{i}" for i in range(250)]
        provider = MultiWebSocketDataProvider(config, symbols, ['15m'])

        chunks = provider._chunk_symbols()

        # 250 symbols, max 100 per chunk → should be 3 chunks
        assert len(chunks) == 3
        assert len(chunks[0]) == 100
        assert len(chunks[1]) == 100
        assert len(chunks[2]) == 50

    def test_start_stop(self, provider):
        """Test start/stop lifecycle"""
        assert not provider.running

        provider.start()
        assert provider.running
        assert len(provider.websockets) > 0
        assert len(provider.threads) > 0

        provider.stop()
        assert not provider.running
        assert len(provider.websockets) == 0
        assert len(provider.threads) == 0

    def test_start_already_running(self, provider):
        """Test error if starting already running provider"""
        provider.start()

        with pytest.raises(RuntimeError, match="already running"):
            provider.start()

        provider.stop()

    def test_get_data_empty(self, provider):
        """Test get_data returns None if no data"""
        result = provider.get_data('BTC', '15m')
        assert result is None

    def test_get_data_with_cache(self, provider):
        """Test get_data returns cached data"""
        # Add data to cache
        df = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [50000.0],
            'high': [50100.0],
            'low': [49900.0],
            'close': [50050.0],
            'volume': [1000.0]
        })

        with provider.cache.lock:
            provider.cache.data['BTC_15m'] = df

        result = provider.get_data('BTC', '15m')
        assert result is not None
        assert len(result) == 1
        assert result['close'].iloc[0] == 50050.0

    def test_get_data_lookback(self, provider):
        """Test get_data respects lookback parameter"""
        # Create large dataframe
        df = pd.DataFrame({
            'timestamp': [datetime.now()] * 2000,
            'open': range(2000),
            'high': range(2000),
            'low': range(2000),
            'close': range(2000),
            'volume': range(2000)
        })

        with provider.cache.lock:
            provider.cache.data['BTC_15m'] = df

        # Request last 500 bars
        result = provider.get_data('BTC', '15m', lookback=500)
        assert len(result) == 500

    def test_get_last_update_empty(self, provider):
        """Test get_last_update returns None if no data"""
        result = provider.get_last_update('BTC', '15m')
        assert result is None

    def test_get_last_update_with_data(self, provider):
        """Test get_last_update returns timestamp"""
        now = datetime.now()

        with provider.cache.lock:
            provider.cache.last_update['BTC_15m'] = now

        result = provider.get_last_update('BTC', '15m')
        assert result == now

    def test_is_data_fresh_no_data(self, provider):
        """Test is_data_fresh returns False if no data"""
        assert not provider.is_data_fresh('BTC', '15m')

    def test_is_data_fresh_old_data(self, provider):
        """Test is_data_fresh returns False if data is old"""
        from datetime import timedelta

        old_time = datetime.now() - timedelta(seconds=120)

        with provider.cache.lock:
            provider.cache.last_update['BTC_15m'] = old_time

        assert not provider.is_data_fresh('BTC', '15m', max_age_seconds=60)

    def test_is_data_fresh_recent_data(self, provider):
        """Test is_data_fresh returns True if data is recent"""
        now = datetime.now()

        with provider.cache.lock:
            provider.cache.last_update['BTC_15m'] = now

        assert provider.is_data_fresh('BTC', '15m', max_age_seconds=60)

    def test_update_cache(self, provider):
        """Test _update_cache adds new candle"""
        candle = CandleData(
            symbol='BTC',
            timeframe='15m',
            timestamp=datetime.now(),
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=1000.0
        )

        provider._update_cache(candle)

        df = provider.get_data('BTC', '15m')
        assert df is not None
        assert len(df) == 1
        assert df['close'].iloc[0] == 50050.0

    def test_update_cache_limits_size(self, config):
        """Test _update_cache respects max bars limit"""
        config['trading']['data']['lookback_bars'] = 10  # Small limit

        provider = MultiWebSocketDataProvider(config, ['BTC'], ['15m'])

        # Add 20 candles
        for i in range(20):
            candle = CandleData(
                symbol='BTC',
                timeframe='15m',
                timestamp=datetime.now(),
                open=50000.0 + i,
                high=50100.0,
                low=49900.0,
                close=50050.0,
                volume=1000.0
            )
            provider._update_cache(candle)

        df = provider.get_data('BTC', '15m')
        assert len(df) <= 10  # Should be limited to 10

    def test_get_statistics(self, provider):
        """Test get_statistics returns correct info"""
        stats = provider.get_statistics()

        assert stats['running'] is False
        assert stats['websockets'] == 0
        assert stats['connected'] == 0
        assert stats['symbols'] == 3
        assert stats['timeframes'] == 2
        assert stats['cached_pairs'] == 0

    def test_get_statistics_running(self, provider):
        """Test statistics when running"""
        provider.start()

        stats = provider.get_statistics()
        assert stats['running'] is True
        assert stats['websockets'] > 0

        provider.stop()

    def test_multiple_symbols_timeframes(self, config):
        """Test provider with many symbols/timeframes"""
        symbols = [f"SYM{i}" for i in range(50)]
        timeframes = ['15m', '30m', '1h', '4h']

        provider = MultiWebSocketDataProvider(config, symbols, timeframes)

        assert len(provider.symbols) == 50
        assert len(provider.timeframes) == 4

        chunks = provider._chunk_symbols()
        assert len(chunks) == 1  # 50 symbols < 100 max

    def test_websocket_count_scaling(self, config):
        """Test WebSocket count scales with symbols"""
        # 100 symbols → 1 WS
        provider1 = MultiWebSocketDataProvider(config, [f"S{i}" for i in range(100)], ['15m'])
        provider1.start()
        assert len(provider1.websockets) == 1
        provider1.stop()

        # 250 symbols → 3 WS
        provider2 = MultiWebSocketDataProvider(config, [f"S{i}" for i in range(250)], ['15m'])
        provider2.start()
        assert len(provider2.websockets) == 3
        provider2.stop()
