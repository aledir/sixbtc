"""
Unit Tests for Coin Database Model

Tests:
- Coin CRUD operations
- Active/inactive filtering
- Volume-based queries
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Coin


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
def sample_coins():
    """Sample coin data for testing"""
    return [
        {'symbol': 'BTC', 'max_leverage': 100, 'volume_24h': 5000000000.0, 'price': 50000.0, 'is_active': True},
        {'symbol': 'ETH', 'max_leverage': 50, 'volume_24h': 1000000000.0, 'price': 3000.0, 'is_active': True},
        {'symbol': 'DOGE', 'max_leverage': 20, 'volume_24h': 100000.0, 'price': 0.1, 'is_active': False},
    ]


@pytest.fixture
def populated_db(test_db, sample_coins):
    """Populate test database with sample coins"""
    for coin_data in sample_coins:
        coin = Coin(
            symbol=coin_data['symbol'],
            max_leverage=coin_data['max_leverage'],
            volume_24h=coin_data['volume_24h'],
            price=coin_data['price'],
            is_active=coin_data['is_active'],
            updated_at=datetime.now(timezone.utc)
        )
        test_db.add(coin)
    test_db.commit()
    return test_db


class TestCoinModel:
    """Test Coin database model"""

    def test_create_coin(self, test_db):
        """Test creating a new coin"""
        coin = Coin(
            symbol='SOL',
            max_leverage=50,
            volume_24h=500000000.0,
            price=100.0,
            is_active=True,
            updated_at=datetime.now(timezone.utc)
        )
        test_db.add(coin)
        test_db.commit()

        # Verify creation
        saved = test_db.query(Coin).filter(Coin.symbol == 'SOL').first()
        assert saved is not None
        assert saved.max_leverage == 50
        assert saved.is_active is True
        assert saved.volume_24h == 500000000.0

    def test_query_active_coins(self, populated_db):
        """Test querying only active coins"""
        active = populated_db.query(Coin).filter(Coin.is_active == True).all()

        assert len(active) == 2
        symbols = [c.symbol for c in active]
        assert 'BTC' in symbols
        assert 'ETH' in symbols
        assert 'DOGE' not in symbols

    def test_query_coins_by_volume(self, populated_db):
        """Test querying coins by minimum volume"""
        high_volume = populated_db.query(Coin).filter(
            Coin.volume_24h >= 1_000_000_000
        ).all()

        assert len(high_volume) == 2
        symbols = [c.symbol for c in high_volume]
        assert 'BTC' in symbols
        assert 'ETH' in symbols

    def test_update_coin(self, populated_db):
        """Test updating coin data"""
        coin = populated_db.query(Coin).filter(Coin.symbol == 'BTC').first()
        coin.price = 60000.0
        coin.volume_24h = 6000000000.0
        populated_db.commit()

        updated = populated_db.query(Coin).filter(Coin.symbol == 'BTC').first()
        assert updated.price == 60000.0
        assert updated.volume_24h == 6000000000.0

    def test_deactivate_coin(self, populated_db):
        """Test deactivating a coin"""
        coin = populated_db.query(Coin).filter(Coin.symbol == 'BTC').first()
        coin.is_active = False
        populated_db.commit()

        active = populated_db.query(Coin).filter(Coin.is_active == True).all()
        assert len(active) == 1
        assert active[0].symbol == 'ETH'

    def test_coin_repr(self, test_db):
        """Test Coin string representation"""
        coin = Coin(
            symbol='TEST',
            max_leverage=10,
            is_active=True
        )
        test_db.add(coin)
        test_db.commit()

        repr_str = repr(coin)
        assert 'TEST' in repr_str
        assert '10' in repr_str

    def test_coin_primary_key(self, test_db):
        """Test that symbol is the primary key"""
        coin1 = Coin(symbol='UNIQUE', max_leverage=10)
        test_db.add(coin1)
        test_db.commit()

        # Trying to add duplicate should fail
        coin2 = Coin(symbol='UNIQUE', max_leverage=20)
        test_db.add(coin2)

        with pytest.raises(Exception):  # IntegrityError wrapped
            test_db.commit()

    def test_query_combined_filters(self, populated_db):
        """Test querying with multiple filters"""
        # Active coins with high volume
        result = populated_db.query(Coin).filter(
            Coin.is_active == True,
            Coin.volume_24h >= 1_000_000_000
        ).order_by(Coin.volume_24h.desc()).all()

        assert len(result) == 2
        # BTC should be first (higher volume)
        assert result[0].symbol == 'BTC'
        assert result[1].symbol == 'ETH'
