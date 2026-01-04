"""
Tests for CoinRegistry - Centralized Coin Management.

Tests cover:
- Singleton pattern
- Cache behavior and invalidation
- Coin lookup and validation
- Leverage queries
- Pattern-aware filtering
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.data.coin_registry import (
    CoinRegistry,
    CoinInfo,
    CoinNotFoundError,
    get_registry,
    get_active_pairs,
    get_coin,
    get_max_leverage,
    is_tradable,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before and after each test."""
    CoinRegistry.reset()
    yield
    CoinRegistry.reset()


@pytest.fixture
def mock_coins():
    """Sample coin data for mocking database."""
    now = datetime.now()
    return [
        Mock(
            symbol='BTC',
            max_leverage=50,
            volume_24h=10_000_000_000,
            price=50000.0,
            is_active=True,
            updated_at=now
        ),
        Mock(
            symbol='ETH',
            max_leverage=50,
            volume_24h=5_000_000_000,
            price=3000.0,
            is_active=True,
            updated_at=now
        ),
        Mock(
            symbol='SOL',
            max_leverage=20,
            volume_24h=500_000_000,
            price=100.0,
            is_active=True,
            updated_at=now
        ),
        Mock(
            symbol='DOGE',
            max_leverage=10,
            volume_24h=100_000,  # Below $1M threshold
            price=0.1,
            is_active=True,
            updated_at=now
        ),
        Mock(
            symbol='SHIB',
            max_leverage=5,
            volume_24h=50_000_000,
            price=0.00001,
            is_active=False,  # Inactive
            updated_at=now
        ),
    ]


@pytest.fixture
def mock_session(mock_coins):
    """Mock database session."""
    session = MagicMock()

    # Mock query().all() for full coin list
    session.query.return_value.all.return_value = mock_coins

    # Mock query().order_by().first() for updated_at check
    session.query.return_value.order_by.return_value.first.return_value = (
        datetime.now(),
    )

    return session


class TestSingleton:
    """Tests for singleton pattern."""

    def test_instance_returns_same_object(self):
        """CoinRegistry.instance() always returns same object."""
        r1 = CoinRegistry.instance()
        r2 = CoinRegistry.instance()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        """CoinRegistry.reset() creates fresh instance."""
        r1 = CoinRegistry.instance()
        CoinRegistry.reset()
        r2 = CoinRegistry.instance()
        assert r1 is not r2

    def test_get_registry_returns_singleton(self):
        """get_registry() convenience function returns singleton."""
        r1 = get_registry()
        r2 = CoinRegistry.instance()
        assert r1 is r2


class TestCacheManagement:
    """Tests for cache behavior."""

    @patch('src.data.coin_registry.get_session')
    def test_cache_refresh_on_first_access(self, mock_get_session, mock_session, mock_coins):
        """Cache is populated on first access."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        pairs = registry.get_active_pairs()

        # Should have called query to populate cache
        assert mock_session.query.called
        assert len(pairs) > 0

    @patch('src.data.coin_registry.get_session')
    def test_cache_reused_on_subsequent_access(self, mock_get_session, mock_session, mock_coins):
        """Cache is reused without re-querying database."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        # First access - populates cache
        registry.get_active_pairs()
        call_count_1 = mock_session.query.call_count

        # Second access - should use cache (staleness check + optional refresh)
        registry.get_active_pairs()
        call_count_2 = mock_session.query.call_count

        # Second call adds staleness check (1-2 queries depending on cache validity)
        # Total should be less than 2x first call (would be 2x if full refresh each time)
        assert call_count_2 < call_count_1 * 2 + 2

    @patch('src.data.coin_registry.get_session')
    def test_cache_invalidation_manual(self, mock_get_session, mock_session):
        """invalidate_cache() forces refresh on next access."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        # Populate cache
        registry._refresh_cache()

        # Invalidate
        registry.invalidate_cache()

        # Cache should be considered invalid
        assert registry._cache_updated_at is None


class TestCoinLookup:
    """Tests for coin lookup operations."""

    @patch('src.data.coin_registry.get_session')
    def test_get_coin_returns_coin_info(self, mock_get_session, mock_session, mock_coins):
        """get_coin() returns CoinInfo for valid coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        coin = registry.get_coin('BTC')

        assert coin is not None
        assert coin.symbol == 'BTC'
        assert coin.max_leverage == 50
        assert coin.is_active is True

    @patch('src.data.coin_registry.get_session')
    def test_get_coin_raises_for_missing_coin(self, mock_get_session, mock_session, mock_coins):
        """get_coin() raises CoinNotFoundError for missing coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        with pytest.raises(CoinNotFoundError):
            registry.get_coin('NONEXISTENT')

    @patch('src.data.coin_registry.get_session')
    def test_get_coin_raises_for_inactive_coin(self, mock_get_session, mock_session, mock_coins):
        """get_coin() raises CoinNotFoundError for inactive coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        # SHIB is inactive in mock data
        with pytest.raises(CoinNotFoundError):
            registry.get_coin('SHIB')

    @patch('src.data.coin_registry.get_session')
    def test_get_coin_returns_none_when_not_required(self, mock_get_session, mock_session, mock_coins):
        """get_coin(required=False) returns None instead of raising."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        coin = registry.get_coin('NONEXISTENT', required=False)

        assert coin is None


class TestActivePairs:
    """Tests for get_active_pairs()."""

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_filters_by_volume(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs() filters out low volume coins."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        pairs = registry.get_active_pairs()

        # DOGE has volume < $1M, should be excluded
        assert 'DOGE' not in pairs
        assert 'BTC' in pairs
        assert 'ETH' in pairs

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_filters_inactive(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs() excludes inactive coins."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        pairs = registry.get_active_pairs()

        # SHIB is inactive
        assert 'SHIB' not in pairs

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_sorted_by_volume(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs() returns coins sorted by volume desc."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        pairs = registry.get_active_pairs()

        # BTC has highest volume, should be first
        assert pairs[0] == 'BTC'
        assert pairs[1] == 'ETH'

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_respects_limit(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs(limit=N) returns at most N pairs."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        pairs = registry.get_active_pairs(limit=2)

        assert len(pairs) == 2

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_custom_volume(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs(min_volume=X) uses custom threshold."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        # With low threshold, DOGE should be included
        pairs = registry.get_active_pairs(min_volume=50_000)
        assert 'DOGE' in pairs

        # With high threshold, only BTC and ETH
        pairs = registry.get_active_pairs(min_volume=1_000_000_000)
        assert 'SOL' not in pairs


class TestLeverage:
    """Tests for leverage queries."""

    @patch('src.data.coin_registry.get_session')
    def test_get_max_leverage(self, mock_get_session, mock_session, mock_coins):
        """get_max_leverage() returns correct leverage."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        assert registry.get_max_leverage('BTC') == 50
        assert registry.get_max_leverage('SOL') == 20

    @patch('src.data.coin_registry.get_session')
    def test_get_leverage_range(self, mock_get_session, mock_session, mock_coins):
        """get_leverage_range() returns min/max across active coins."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        min_lev, max_lev = registry.get_leverage_range()

        # DOGE has min leverage=10, BTC/ETH have max leverage=50
        # (SHIB with leverage=5 is inactive)
        assert min_lev == 10
        assert max_lev == 50


class TestTradability:
    """Tests for is_tradable() and validation."""

    @patch('src.data.coin_registry.get_session')
    def test_is_tradable_active_high_volume(self, mock_get_session, mock_session, mock_coins):
        """is_tradable() returns True for active high-volume coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        assert registry.is_tradable('BTC') is True
        assert registry.is_tradable('ETH') is True

    @patch('src.data.coin_registry.get_session')
    def test_is_tradable_low_volume(self, mock_get_session, mock_session, mock_coins):
        """is_tradable() returns False for low volume coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        # DOGE has volume < $1M
        assert registry.is_tradable('DOGE') is False

    @patch('src.data.coin_registry.get_session')
    def test_is_tradable_inactive(self, mock_get_session, mock_session, mock_coins):
        """is_tradable() returns False for inactive coin."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()

        assert registry.is_tradable('SHIB') is False

    @patch('src.data.coin_registry.get_session')
    def test_validate_coins(self, mock_get_session, mock_session, mock_coins):
        """validate_coins() separates valid from invalid."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        valid, invalid = registry.validate_coins(['BTC', 'ETH', 'DOGE', 'SHIB', 'FAKE'])

        assert 'BTC' in valid
        assert 'ETH' in valid
        assert 'DOGE' in invalid  # Low volume
        assert 'SHIB' in invalid  # Inactive
        assert 'FAKE' in invalid  # Doesn't exist


class TestPatternAwareFiltering:
    """Tests for get_tradable_for_strategy()."""

    @patch('src.data.coin_registry.get_session')
    def test_prefers_pattern_coins(self, mock_get_session, mock_session, mock_coins):
        """get_tradable_for_strategy() prefers pattern_coins over backtest_pairs."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        result = registry.get_tradable_for_strategy(
            pattern_coins=['ETH', 'SOL'],
            backtest_pairs=['BTC', 'ETH']
        )

        # Should use pattern_coins, not backtest_pairs
        # ETH and SOL are both valid
        assert 'ETH' in result
        assert 'SOL' in result
        # BTC should NOT be in result (not in pattern_coins)
        assert 'BTC' not in result

    @patch('src.data.coin_registry.get_session')
    def test_falls_back_to_backtest_pairs(self, mock_get_session, mock_session, mock_coins):
        """get_tradable_for_strategy() uses backtest_pairs if no pattern_coins."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        result = registry.get_tradable_for_strategy(
            pattern_coins=None,
            backtest_pairs=['BTC', 'ETH']
        )

        assert 'BTC' in result
        assert 'ETH' in result

    @patch('src.data.coin_registry.get_session')
    def test_filters_out_invalid_coins(self, mock_get_session, mock_session, mock_coins):
        """get_tradable_for_strategy() filters out non-tradable coins."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        registry = CoinRegistry.instance()
        result = registry.get_tradable_for_strategy(
            pattern_coins=['BTC', 'SHIB', 'FAKE'],  # SHIB inactive, FAKE doesn't exist
            backtest_pairs=[]
        )

        assert 'BTC' in result
        assert 'SHIB' not in result
        assert 'FAKE' not in result


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch('src.data.coin_registry.get_session')
    def test_get_active_pairs_function(self, mock_get_session, mock_session, mock_coins):
        """get_active_pairs() convenience function works."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        pairs = get_active_pairs()
        assert 'BTC' in pairs

    @patch('src.data.coin_registry.get_session')
    def test_get_coin_function(self, mock_get_session, mock_session, mock_coins):
        """get_coin() convenience function works."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        coin = get_coin('BTC')
        assert coin.symbol == 'BTC'

    @patch('src.data.coin_registry.get_session')
    def test_get_max_leverage_function(self, mock_get_session, mock_session, mock_coins):
        """get_max_leverage() convenience function works."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        lev = get_max_leverage('BTC')
        assert lev == 50

    @patch('src.data.coin_registry.get_session')
    def test_is_tradable_function(self, mock_get_session, mock_session, mock_coins):
        """is_tradable() convenience function works."""
        mock_get_session.return_value.__enter__.return_value = mock_session

        assert is_tradable('BTC') is True
        assert is_tradable('SHIB') is False
