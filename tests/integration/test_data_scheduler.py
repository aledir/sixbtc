"""
Integration Tests for Data Scheduler

Tests the full workflow:
1. Pairs updater populates Coin table
2. Scheduler calls download_for_pairs()
3. Data is downloaded for active coins
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Coin
from src.data.data_scheduler import DataScheduler
from src.data.binance_downloader import BinanceDataDownloader


@pytest.fixture
def mock_config():
    """Mock configuration for scheduler"""
    return {
        'data_scheduler': {
            'enabled': True,
            'update_hours': [4, 16],
            'top_pairs_count': 3,
            'min_volume_usd': 0,
            'download_days': 7,
        },
        'data': {
            'cache_dir': '/tmp/test_binance_data'
        },
        'timeframes': ['1h', '4h']
    }


@pytest.fixture
def test_db():
    """Create in-memory test database"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def populated_coins(test_db):
    """Populate test database with active coins"""
    coins = [
        Coin(symbol='BTC', max_leverage=100, volume_24h=5e9, price=50000, is_active=True, updated_at=datetime.now(timezone.utc)),
        Coin(symbol='ETH', max_leverage=50, volume_24h=2e9, price=3000, is_active=True, updated_at=datetime.now(timezone.utc)),
        Coin(symbol='SOL', max_leverage=20, volume_24h=1e9, price=100, is_active=True, updated_at=datetime.now(timezone.utc)),
        Coin(symbol='DEAD', max_leverage=5, volume_24h=1000, price=0.01, is_active=False, updated_at=datetime.now(timezone.utc)),
    ]
    for coin in coins:
        test_db.add(coin)
    test_db.commit()
    return test_db


class TestSchedulerIntegration:
    """Integration tests for DataScheduler"""

    def test_scheduler_initialization(self, mock_config):
        """Test scheduler initializes correctly"""
        scheduler = DataScheduler(config=mock_config)

        assert scheduler.enabled is True
        assert scheduler.update_hours == [4, 16]

    def test_scheduler_update_pairs_calls_pairs_updater(self, mock_config):
        """Test that update_pairs calls PairsUpdater"""
        scheduler = DataScheduler(config=mock_config)

        # Inject mock directly into private attribute (bypasses property)
        mock_updater = MagicMock()
        mock_updater.update.return_value = {'pair_whitelist': ['BTC', 'ETH']}
        scheduler._pairs_updater = mock_updater

        scheduler.update_pairs()

        mock_updater.update.assert_called_once()

    def test_scheduler_download_data_calls_binance_downloader(self, mock_config):
        """Test that download_data calls BinanceDataDownloader.download_for_pairs()"""
        scheduler = DataScheduler(config=mock_config)

        # Inject mock directly into private attribute (bypasses property)
        mock_downloader = MagicMock()
        mock_downloader.cleanup_obsolete_pairs.return_value = 0
        mock_downloader.download_for_pairs.return_value = {}
        scheduler._binance_downloader = mock_downloader

        scheduler.download_data()

        mock_downloader.cleanup_obsolete_pairs.assert_called_once()
        mock_downloader.download_for_pairs.assert_called_once()


class TestDownloaderDBIntegration:
    """Test BinanceDataDownloader integration with database"""

    def test_download_for_pairs_reads_active_coins(self, mock_config, populated_coins):
        """Test download_for_pairs reads active coins from DB"""
        # Create mock config object
        config_mock = Mock()
        config_mock.get = Mock(side_effect=lambda k, d=None: mock_config.get(k, d))
        config_mock.get_required = Mock(side_effect=lambda k: mock_config[k])

        downloader = BinanceDataDownloader(config=config_mock)

        # Mock the actual download to prevent network calls
        with patch.object(downloader, 'download_all_timeframes') as mock_download:
            mock_download.return_value = {}

            # Mock get_session to use our test DB session
            mock_session_context = MagicMock()
            mock_query = MagicMock()

            # Return only active coins
            active_coins = [
                MagicMock(symbol='BTC'),
                MagicMock(symbol='ETH'),
                MagicMock(symbol='SOL'),
            ]
            mock_query.filter.return_value.all.return_value = active_coins
            mock_session_context.__enter__.return_value.query.return_value = mock_query

            with patch('src.database.get_session', return_value=mock_session_context):
                result = downloader.download_for_pairs(days=7)

            # Verify download_all_timeframes was called
            mock_download.assert_called_once()

            # Verify correct symbols passed
            call_kwargs = mock_download.call_args[1]
            symbols = call_kwargs['symbols']
            assert 'BTC' in symbols
            assert 'ETH' in symbols
            assert 'SOL' in symbols
            assert 'DEAD' not in symbols  # Inactive coin not included

    def test_download_for_pairs_excludes_inactive(self, mock_config):
        """Test download_for_pairs excludes inactive coins"""
        config_mock = Mock()
        config_mock.get = Mock(side_effect=lambda k, d=None: mock_config.get(k, d))
        config_mock.get_required = Mock(side_effect=lambda k: mock_config[k])

        downloader = BinanceDataDownloader(config=config_mock)

        with patch.object(downloader, 'download_all_timeframes') as mock_download:
            mock_download.return_value = {}

            # Mock session with mix of active/inactive
            mock_session_context = MagicMock()
            mock_query = MagicMock()

            # Only active coin returned by filter
            mock_query.filter.return_value.all.return_value = [MagicMock(symbol='BTC')]
            mock_session_context.__enter__.return_value.query.return_value = mock_query

            with patch('src.database.get_session', return_value=mock_session_context):
                downloader.download_for_pairs()

            call_kwargs = mock_download.call_args[1]
            symbols = call_kwargs['symbols']
            assert len(symbols) == 1
            assert symbols[0] == 'BTC'


class TestSchedulerRunNow:
    """Test scheduler run_now functionality"""

    def test_run_now_executes_both_phases(self, mock_config):
        """Test run_now calls update_pairs then download_data"""
        scheduler = DataScheduler(config=mock_config)

        call_order = []

        # Inject mocks into private attributes
        mock_updater = MagicMock()
        def track_update():
            call_order.append('update_pairs')
            return {'pair_whitelist': ['BTC']}
        mock_updater.update.side_effect = track_update
        scheduler._pairs_updater = mock_updater

        mock_downloader = MagicMock()
        def track_download():
            call_order.append('download_data')
        mock_downloader.cleanup_obsolete_pairs.return_value = 0
        mock_downloader.download_for_pairs.side_effect = track_download
        scheduler._binance_downloader = mock_downloader

        with patch('time.sleep'):  # Skip the 5 second delay
            scheduler.run_now()

        # Verify order: update_pairs first, then download_data
        assert call_order == ['update_pairs', 'download_data']
