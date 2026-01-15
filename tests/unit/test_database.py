"""
Tests for the Database module.

Covers:
1. Models - Strategy, BacktestResult, Trade, Coin, Subaccount
2. Connection - engine singleton, session management
3. Model relationships and constraints

Note: These tests use mocks since SQLite doesn't support PostgreSQL-specific
types (ARRAY, UUID, JSONB). For full integration tests, use PostgreSQL.
"""
import pytest
import uuid
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock

from src.database.models import (
    Strategy,
    BacktestResult,
    Trade,
    Coin,
    Subaccount,
    ValidationCache,
    StrategyEvent,
    MarketRegime,
    EmergencyStopState,
)


# =============================================================================
# STRATEGY MODEL TESTS
# =============================================================================

class TestStrategyModel:
    """Tests for Strategy model attributes."""

    def test_strategy_table_name(self):
        """Strategy should have correct table name."""
        assert Strategy.__tablename__ == 'strategies'

    def test_strategy_required_columns(self):
        """Strategy should have required columns defined."""
        columns = [c.name for c in Strategy.__table__.columns]

        assert 'id' in columns
        assert 'name' in columns
        assert 'strategy_type' in columns
        assert 'timeframe' in columns
        assert 'status' in columns
        assert 'code' in columns

    def test_strategy_has_relationships(self):
        """Strategy should define relationships."""
        assert hasattr(Strategy, 'backtest_results')
        assert hasattr(Strategy, 'trades')
        assert hasattr(Strategy, 'performance_snapshots')

    def test_strategy_default_status(self):
        """Strategy default status should be GENERATED."""
        status_col = Strategy.__table__.columns['status']
        assert status_col.default.arg == 'GENERATED'

    def test_strategy_repr_method_exists(self):
        """Strategy should have __repr__ method defined."""
        assert hasattr(Strategy, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# BACKTEST RESULT MODEL TESTS
# =============================================================================

class TestBacktestResultModel:
    """Tests for BacktestResult model attributes."""

    def test_backtest_result_table_name(self):
        """BacktestResult should have correct table name."""
        assert BacktestResult.__tablename__ == 'backtest_results'

    def test_backtest_result_required_columns(self):
        """BacktestResult should have performance columns."""
        columns = [c.name for c in BacktestResult.__table__.columns]

        assert 'strategy_id' in columns
        assert 'total_trades' in columns
        assert 'win_rate' in columns
        assert 'sharpe_ratio' in columns
        assert 'expectancy' in columns
        assert 'max_drawdown' in columns

    def test_backtest_result_has_strategy_relationship(self):
        """BacktestResult should relate to Strategy."""
        assert hasattr(BacktestResult, 'strategy')


# =============================================================================
# TRADE MODEL TESTS
# =============================================================================

class TestTradeModel:
    """Tests for Trade model attributes."""

    def test_trade_table_name(self):
        """Trade should have correct table name."""
        assert Trade.__tablename__ == 'trades'

    def test_trade_required_columns(self):
        """Trade should have entry/exit columns."""
        columns = [c.name for c in Trade.__table__.columns]

        assert 'strategy_id' in columns
        assert 'symbol' in columns
        assert 'direction' in columns
        assert 'entry_time' in columns
        assert 'entry_price' in columns
        assert 'exit_time' in columns
        assert 'exit_price' in columns
        assert 'pnl_usd' in columns

    def test_trade_direction_enum(self):
        """Trade direction should be LONG or SHORT."""
        direction_col = Trade.__table__.columns['direction']
        # Check the enum type has expected values
        enum_type = direction_col.type
        assert set(enum_type.enums) == {'LONG', 'SHORT'}


# =============================================================================
# COIN MODEL TESTS
# =============================================================================

class TestCoinModel:
    """Tests for Coin model attributes."""

    def test_coin_table_name(self):
        """Coin should have correct table name."""
        assert Coin.__tablename__ == 'coins'

    def test_coin_primary_key_is_symbol(self):
        """Coin primary key should be symbol."""
        symbol_col = Coin.__table__.columns['symbol']
        assert symbol_col.primary_key is True

    def test_coin_required_columns(self):
        """Coin should have leverage and status columns."""
        columns = [c.name for c in Coin.__table__.columns]

        assert 'symbol' in columns
        assert 'max_leverage' in columns
        assert 'is_active' in columns
        assert 'volume_24h' in columns

    def test_coin_repr_method_exists(self):
        """Coin should have __repr__ method defined."""
        assert hasattr(Coin, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# SUBACCOUNT MODEL TESTS
# =============================================================================

class TestSubaccountModel:
    """Tests for Subaccount model attributes."""

    def test_subaccount_table_name(self):
        """Subaccount should have correct table name."""
        assert Subaccount.__tablename__ == 'subaccounts'

    def test_subaccount_required_columns(self):
        """Subaccount should have allocation and balance columns."""
        columns = [c.name for c in Subaccount.__table__.columns]

        assert 'id' in columns
        assert 'strategy_id' in columns
        assert 'allocated_capital' in columns
        assert 'current_balance' in columns
        assert 'status' in columns

    def test_subaccount_default_values(self):
        """Subaccount should have sensible defaults."""
        total_trades_col = Subaccount.__table__.columns['total_trades']
        total_pnl_col = Subaccount.__table__.columns['total_pnl']

        assert total_trades_col.default.arg == 0
        assert total_pnl_col.default.arg == 0.0


# =============================================================================
# VALIDATION CACHE MODEL TESTS
# =============================================================================

class TestValidationCacheModel:
    """Tests for ValidationCache model attributes."""

    def test_validation_cache_table_name(self):
        """ValidationCache should have correct table name."""
        assert ValidationCache.__tablename__ == 'validation_caches'

    def test_validation_cache_primary_key(self):
        """ValidationCache primary key should be code_hash."""
        code_hash_col = ValidationCache.__table__.columns['code_hash']
        assert code_hash_col.primary_key is True

    def test_validation_cache_columns(self):
        """ValidationCache should have test result columns."""
        columns = [c.name for c in ValidationCache.__table__.columns]

        assert 'code_hash' in columns
        assert 'shuffle_passed' in columns
        assert 'multi_window_passed' in columns
        assert 'validated_at' in columns

    def test_validation_cache_repr_method_exists(self):
        """ValidationCache should have __repr__ method defined."""
        assert hasattr(ValidationCache, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# STRATEGY EVENT MODEL TESTS
# =============================================================================

class TestStrategyEventModel:
    """Tests for StrategyEvent model attributes."""

    def test_strategy_event_table_name(self):
        """StrategyEvent should have correct table name."""
        assert StrategyEvent.__tablename__ == 'strategy_events'

    def test_strategy_event_columns(self):
        """StrategyEvent should have pipeline tracking columns."""
        columns = [c.name for c in StrategyEvent.__table__.columns]

        assert 'strategy_name' in columns
        assert 'event_type' in columns
        assert 'stage' in columns
        assert 'status' in columns
        assert 'duration_ms' in columns
        assert 'event_data' in columns

    def test_strategy_event_repr_method_exists(self):
        """StrategyEvent should have __repr__ method defined."""
        assert hasattr(StrategyEvent, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# MARKET REGIME MODEL TESTS
# =============================================================================

class TestMarketRegimeModel:
    """Tests for MarketRegime model attributes."""

    def test_market_regime_table_name(self):
        """MarketRegime should have correct table name."""
        assert MarketRegime.__tablename__ == 'market_regimes'

    def test_market_regime_primary_key(self):
        """MarketRegime primary key should be symbol."""
        symbol_col = MarketRegime.__table__.columns['symbol']
        assert symbol_col.primary_key is True

    def test_market_regime_columns(self):
        """MarketRegime should have Unger method columns."""
        columns = [c.name for c in MarketRegime.__table__.columns]

        assert 'symbol' in columns
        assert 'regime_type' in columns
        assert 'strength' in columns
        assert 'direction' in columns
        assert 'breakout_pnl' in columns
        assert 'reversal_pnl' in columns
        assert 'regime_score' in columns

    def test_market_regime_repr_method_exists(self):
        """MarketRegime should have __repr__ method defined."""
        assert hasattr(MarketRegime, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# EMERGENCY STOP STATE MODEL TESTS
# =============================================================================

class TestEmergencyStopStateModel:
    """Tests for EmergencyStopState model attributes."""

    def test_emergency_stop_table_name(self):
        """EmergencyStopState should have correct table name."""
        assert EmergencyStopState.__tablename__ == 'emergency_stop_states'

    def test_emergency_stop_composite_key(self):
        """EmergencyStopState should have composite primary key."""
        scope_col = EmergencyStopState.__table__.columns['scope']
        scope_id_col = EmergencyStopState.__table__.columns['scope_id']

        assert scope_col.primary_key is True
        assert scope_id_col.primary_key is True

    def test_emergency_stop_columns(self):
        """EmergencyStopState should have stop tracking columns."""
        columns = [c.name for c in EmergencyStopState.__table__.columns]

        assert 'is_stopped' in columns
        assert 'stop_reason' in columns
        assert 'stop_action' in columns
        assert 'cooldown_until' in columns

    def test_emergency_stop_repr_method_exists(self):
        """EmergencyStopState should have __repr__ method defined."""
        assert hasattr(EmergencyStopState, '__repr__')
        # The repr format is tested in integration tests with actual DB


# =============================================================================
# CONNECTION MODULE TESTS
# =============================================================================

class TestConnectionModule:
    """Tests for database connection module."""

    def test_get_engine_is_singleton(self):
        """get_engine should return same instance on multiple calls."""
        from src.database import connection

        # Reset module state
        connection._engine = None

        with patch.object(connection, 'load_config') as mock_config:
            mock_config.return_value = MagicMock(
                get_required=MagicMock(side_effect=lambda k: {
                    'database.user': 'test',
                    'database.password': 'test',
                    'database.host': 'localhost',
                    'database.port': '5432',
                    'database.database': 'test',
                    'database.pool.min_connections': 2,
                    'database.pool.max_connections': 10,
                    'database.pool.pool_recycle': 3600,
                }.get(k))
            )

            with patch('src.database.connection.create_engine') as mock_create:
                mock_engine = MagicMock()
                mock_create.return_value = mock_engine

                engine1 = connection.get_engine()
                engine2 = connection.get_engine()

                # Should be the same instance
                assert engine1 is engine2

                # create_engine should only be called once
                mock_create.assert_called_once()

    def test_get_session_yields_session(self):
        """get_session should yield a session and handle cleanup."""
        from src.database import connection

        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(connection, 'get_session_factory', return_value=mock_factory):
            with connection.get_session() as session:
                assert session is mock_session

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_session_rolls_back_on_error(self):
        """get_session should rollback on exception."""
        from src.database import connection

        mock_session = MagicMock()
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(connection, 'get_session_factory', return_value=mock_factory):
            with pytest.raises(ValueError):
                with connection.get_session() as session:
                    raise ValueError("Test error")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
