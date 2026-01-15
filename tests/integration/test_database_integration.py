"""
Integration tests for Database models with real PostgreSQL.

These tests use the actual PostgreSQL database to verify:
1. Model CRUD operations
2. Relationships and cascades
3. Constraints and indexes
4. Complex queries

Each test runs in a transaction that is rolled back at the end,
so no test data persists in the database.
"""
import pytest
import uuid
from datetime import datetime, UTC

from sqlalchemy import text

from src.database.connection import get_session, get_engine
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
# FIXTURES
# =============================================================================

@pytest.fixture
def db_session():
    """
    Provide a database session that rolls back after each test.

    This ensures tests don't persist data in the real database.
    """
    from src.database.connection import get_session_factory

    SessionFactory = get_session_factory()
    session = SessionFactory()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# STRATEGY MODEL INTEGRATION TESTS
# =============================================================================

class TestStrategyIntegration:
    """Integration tests for Strategy model."""

    def test_create_strategy(self, db_session):
        """Should create a strategy in PostgreSQL."""
        strategy = Strategy(
            id=uuid.uuid4(),
            name=f'TestStrat_INT_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            status='GENERATED',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        # Verify it's in DB
        fetched = db_session.query(Strategy).filter_by(id=strategy.id).first()
        assert fetched is not None
        assert fetched.name == strategy.name
        assert fetched.status == 'GENERATED'

    def test_strategy_with_trading_coins_json(self, db_session):
        """Should store trading_coins as JSON array."""
        strategy = Strategy(
            name=f'TestStrat_JSON_{uuid.uuid4().hex[:8]}',
            strategy_type='TRN',
            timeframe='15m',
            code='class TestStrat(StrategyCore): pass',
            trading_coins=['BTC', 'ETH', 'SOL'],
        )
        db_session.add(strategy)
        db_session.flush()

        fetched = db_session.query(Strategy).filter_by(id=strategy.id).first()
        assert fetched.trading_coins == ['BTC', 'ETH', 'SOL']

    def test_strategy_status_enum(self, db_session):
        """Should enforce status enum values."""
        strategy = Strategy(
            name=f'TestStrat_ENUM_{uuid.uuid4().hex[:8]}',
            strategy_type='VOL',
            timeframe='30m',
            status='ACTIVE',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        assert strategy.status == 'ACTIVE'

    def test_strategy_repr(self, db_session):
        """Should have readable repr."""
        strategy = Strategy(
            name=f'TestStrat_REPR_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        repr_str = repr(strategy)
        assert strategy.name in repr_str
        assert 'MOM' in repr_str


# =============================================================================
# BACKTEST RESULT INTEGRATION TESTS
# =============================================================================

class TestBacktestResultIntegration:
    """Integration tests for BacktestResult model."""

    def test_backtest_result_with_strategy(self, db_session):
        """Should link backtest result to strategy."""
        strategy = Strategy(
            name=f'TestStrat_BT_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        result = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            total_trades=150,
            win_rate=0.58,
            sharpe_ratio=1.5,
            expectancy=0.025,
            max_drawdown=0.15,
        )
        db_session.add(result)
        db_session.flush()

        # Verify relationship
        assert result.strategy_id == strategy.id
        fetched = db_session.query(BacktestResult).filter_by(id=result.id).first()
        assert fetched.sharpe_ratio == 1.5

    def test_backtest_result_repr(self, db_session):
        """Should have readable repr with metrics."""
        strategy = Strategy(
            name=f'TestStrat_BTR_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        result = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            total_trades=100,
            sharpe_ratio=1.25,
        )
        db_session.add(result)
        db_session.flush()

        repr_str = repr(result)
        assert 'sharpe=1.25' in repr_str
        assert 'trades=100' in repr_str


# =============================================================================
# TRADE INTEGRATION TESTS
# =============================================================================

class TestTradeIntegration:
    """Integration tests for Trade model."""

    def test_trade_creation(self, db_session):
        """Should create trade with entry details."""
        strategy = Strategy(
            name=f'TestStrat_TR_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        trade = Trade(
            strategy_id=strategy.id,
            symbol='BTC',
            subaccount_id=1,
            direction='LONG',
            entry_time=datetime.now(UTC),
            entry_price=50000.0,
            entry_size=0.1,
        )
        db_session.add(trade)
        db_session.flush()

        fetched = db_session.query(Trade).filter_by(id=trade.id).first()
        assert fetched.symbol == 'BTC'
        assert fetched.direction == 'LONG'

    def test_trade_with_pnl(self, db_session):
        """Should store PnL after exit."""
        strategy = Strategy(
            name=f'TestStrat_PNL_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        trade = Trade(
            strategy_id=strategy.id,
            symbol='ETH',
            subaccount_id=2,
            direction='SHORT',
            entry_time=datetime.now(UTC),
            entry_price=3000.0,
            entry_size=1.0,
            exit_time=datetime.now(UTC),
            exit_price=2900.0,
            exit_reason='take_profit',
            pnl_usd=100.0,
            pnl_pct=0.0333,
        )
        db_session.add(trade)
        db_session.flush()

        fetched = db_session.query(Trade).filter_by(id=trade.id).first()
        assert fetched.pnl_usd == 100.0
        assert fetched.exit_reason == 'take_profit'


# =============================================================================
# COIN INTEGRATION TESTS
# =============================================================================

class TestCoinIntegration:
    """Integration tests for Coin model."""

    def test_coin_upsert(self, db_session):
        """Should handle coin upsert (symbol is PK)."""
        # Use a unique test symbol
        test_symbol = f'TEST{uuid.uuid4().hex[:4].upper()}'

        coin = Coin(
            symbol=test_symbol,
            max_leverage=50,
            is_active=True,
            volume_24h=1000000.0,
        )
        db_session.add(coin)
        db_session.flush()

        fetched = db_session.query(Coin).filter_by(symbol=test_symbol).first()
        assert fetched.max_leverage == 50

    def test_coin_repr(self, db_session):
        """Should have readable repr."""
        test_symbol = f'REP{uuid.uuid4().hex[:4].upper()}'

        coin = Coin(
            symbol=test_symbol,
            max_leverage=25,
            is_active=True,
        )
        db_session.add(coin)
        db_session.flush()

        repr_str = repr(coin)
        assert test_symbol in repr_str
        assert '25' in repr_str


# =============================================================================
# VALIDATION CACHE INTEGRATION TESTS
# =============================================================================

class TestValidationCacheIntegration:
    """Integration tests for ValidationCache model."""

    def test_validation_cache_creation(self, db_session):
        """Should store validation results by hash."""
        cache = ValidationCache(
            code_hash=uuid.uuid4().hex,
            shuffle_passed=True,
            multi_window_passed=True,
        )
        db_session.add(cache)
        db_session.flush()

        fetched = db_session.query(ValidationCache).filter_by(
            code_hash=cache.code_hash
        ).first()
        assert fetched.shuffle_passed is True
        assert fetched.multi_window_passed is True

    def test_validation_cache_repr(self, db_session):
        """Should show hash prefix and status."""
        cache = ValidationCache(
            code_hash='abc123def456789ghijklmnop',
            shuffle_passed=False,
            multi_window_passed=None,
        )
        db_session.add(cache)
        db_session.flush()

        repr_str = repr(cache)
        assert 'abc123de' in repr_str
        assert 'shuffle=False' in repr_str


# =============================================================================
# STRATEGY EVENT INTEGRATION TESTS
# =============================================================================

class TestStrategyEventIntegration:
    """Integration tests for StrategyEvent model."""

    def test_event_creation(self, db_session):
        """Should record pipeline events."""
        event = StrategyEvent(
            strategy_name=f'TestStrat_EVT_{uuid.uuid4().hex[:8]}',
            event_type='syntax_passed',
            stage='validation',
            status='passed',
            duration_ms=150,
        )
        db_session.add(event)
        db_session.flush()

        fetched = db_session.query(StrategyEvent).filter_by(id=event.id).first()
        assert fetched.event_type == 'syntax_passed'
        assert fetched.stage == 'validation'

    def test_event_with_metadata(self, db_session):
        """Should store event_data JSON."""
        event = StrategyEvent(
            strategy_name=f'TestStrat_META_{uuid.uuid4().hex[:8]}',
            event_type='backtest_scored',
            stage='backtest',
            status='completed',
            event_data={'score': 72, 'sharpe': 1.4, 'win_rate': 0.58},
        )
        db_session.add(event)
        db_session.flush()

        fetched = db_session.query(StrategyEvent).filter_by(id=event.id).first()
        assert fetched.event_data['score'] == 72


# =============================================================================
# MARKET REGIME INTEGRATION TESTS
# =============================================================================

class TestMarketRegimeIntegration:
    """Integration tests for MarketRegime model."""

    def test_regime_creation(self, db_session):
        """Should store regime classification."""
        # Use unique symbol
        test_symbol = f'RGM{uuid.uuid4().hex[:4].upper()}'

        regime = MarketRegime(
            symbol=test_symbol,
            regime_type='TREND',
            strength=0.75,
            direction='BOTH',
            breakout_pnl=0.15,
            breakout_long_pnl=0.10,
            breakout_short_pnl=0.05,
            reversal_pnl=-0.08,
            reversal_long_pnl=-0.05,
            reversal_short_pnl=-0.03,
            regime_score=0.23,
            window_days=90,
        )
        db_session.add(regime)
        db_session.flush()

        fetched = db_session.query(MarketRegime).filter_by(symbol=test_symbol).first()
        assert fetched.regime_type == 'TREND'
        assert fetched.strength == 0.75

    def test_regime_repr(self, db_session):
        """Should show classification in repr."""
        test_symbol = f'RPR{uuid.uuid4().hex[:4].upper()}'

        regime = MarketRegime(
            symbol=test_symbol,
            regime_type='REVERSAL',
            strength=0.60,
            direction='LONG',
            breakout_pnl=-0.05,
            breakout_long_pnl=-0.03,
            breakout_short_pnl=-0.02,
            reversal_pnl=0.12,
            reversal_long_pnl=0.08,
            reversal_short_pnl=0.04,
            regime_score=-0.17,
            window_days=90,
        )
        db_session.add(regime)
        db_session.flush()

        repr_str = repr(regime)
        assert test_symbol in repr_str
        assert 'REVERSAL' in repr_str


# =============================================================================
# EMERGENCY STOP STATE INTEGRATION TESTS
# =============================================================================

class TestEmergencyStopStateIntegration:
    """Integration tests for EmergencyStopState model."""

    def test_stop_state_creation(self, db_session):
        """Should track stop conditions."""
        # Use unique scope_id
        scope_id = f'test_{uuid.uuid4().hex[:8]}'

        stop_state = EmergencyStopState(
            scope='subaccount',
            scope_id=scope_id,
            is_stopped=True,
            stop_reason='Max drawdown exceeded (25%)',
            stop_action='halt_entries',
        )
        db_session.add(stop_state)
        db_session.flush()

        fetched = db_session.query(EmergencyStopState).filter_by(
            scope='subaccount',
            scope_id=scope_id
        ).first()
        assert fetched.is_stopped is True
        assert fetched.stop_action == 'halt_entries'

    def test_stop_state_repr(self, db_session):
        """Should show status in repr."""
        scope_id = f'repr_{uuid.uuid4().hex[:8]}'

        stop_state = EmergencyStopState(
            scope='portfolio',
            scope_id=scope_id,
            is_stopped=False,
        )
        db_session.add(stop_state)
        db_session.flush()

        repr_str = repr(stop_state)
        assert f'portfolio:{scope_id}' in repr_str
        assert 'CLEAR' in repr_str


# =============================================================================
# RELATIONSHIP TESTS
# =============================================================================

class TestModelRelationships:
    """Integration tests for model relationships."""

    def test_strategy_backtest_results_relationship(self, db_session):
        """Strategy should have backtest_results relationship."""
        strategy = Strategy(
            name=f'TestStrat_REL_{uuid.uuid4().hex[:8]}',
            strategy_type='MOM',
            timeframe='1h',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        result1 = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 30),
            total_trades=100,
        )
        result2 = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=90,
            initial_capital=10000.0,
            start_date=datetime(2024, 4, 1),
            end_date=datetime(2024, 6, 30),
            total_trades=50,
        )
        db_session.add_all([result1, result2])
        db_session.flush()

        # Refresh to load relationships
        db_session.refresh(strategy)
        assert len(strategy.backtest_results) == 2

    def test_strategy_trades_relationship(self, db_session):
        """Strategy should have trades relationship."""
        strategy = Strategy(
            name=f'TestStrat_TRR_{uuid.uuid4().hex[:8]}',
            strategy_type='TRN',
            timeframe='15m',
            code='class TestStrat(StrategyCore): pass',
        )
        db_session.add(strategy)
        db_session.flush()

        trade = Trade(
            strategy_id=strategy.id,
            symbol='BTC',
            subaccount_id=1,
            direction='LONG',
            entry_time=datetime.now(UTC),
            entry_price=50000.0,
            entry_size=0.1,
        )
        db_session.add(trade)
        db_session.flush()

        db_session.refresh(strategy)
        assert len(strategy.trades) == 1
        assert strategy.trades[0].symbol == 'BTC'


# =============================================================================
# QUERY TESTS
# =============================================================================

class TestDatabaseQueries:
    """Integration tests for database queries."""

    def test_query_strategies_by_status(self, db_session):
        """Should query strategies by status."""
        # Create test strategies with unique names
        prefix = uuid.uuid4().hex[:8]

        s1 = Strategy(
            name=f'TestStrat_Q1_{prefix}',
            strategy_type='MOM',
            timeframe='1h',
            status='GENERATED',
            code='pass',
        )
        s2 = Strategy(
            name=f'TestStrat_Q2_{prefix}',
            strategy_type='TRN',
            timeframe='15m',
            status='ACTIVE',
            code='pass',
        )
        db_session.add_all([s1, s2])
        db_session.flush()

        generated = db_session.query(Strategy).filter(
            Strategy.status == 'GENERATED',
            Strategy.name.like(f'%{prefix}%')
        ).all()

        assert len(generated) == 1
        assert generated[0].name == s1.name

    def test_query_with_score_filter(self, db_session):
        """Should filter strategies by score."""
        prefix = uuid.uuid4().hex[:8]

        s1 = Strategy(
            name=f'TestStrat_SC1_{prefix}',
            strategy_type='MOM',
            timeframe='1h',
            status='ACTIVE',
            code='pass',
            score_backtest=75.0,
        )
        s2 = Strategy(
            name=f'TestStrat_SC2_{prefix}',
            strategy_type='TRN',
            timeframe='15m',
            status='ACTIVE',
            code='pass',
            score_backtest=45.0,
        )
        db_session.add_all([s1, s2])
        db_session.flush()

        high_score = db_session.query(Strategy).filter(
            Strategy.score_backtest >= 60,
            Strategy.name.like(f'%{prefix}%')
        ).all()

        assert len(high_score) == 1
        assert high_score[0].score_backtest == 75.0

    def test_postgresql_specific_json_query(self, db_session):
        """Should query JSON fields with PostgreSQL operators."""
        prefix = uuid.uuid4().hex[:8]

        strategy = Strategy(
            name=f'TestStrat_JS_{prefix}',
            strategy_type='MOM',
            timeframe='1h',
            code='pass',
            trading_coins=['BTC', 'ETH'],
        )
        db_session.add(strategy)
        db_session.flush()

        # Query using PostgreSQL JSON containment (cast to jsonb first)
        result = db_session.execute(
            text("""
                SELECT name FROM strategies
                WHERE trading_coins::jsonb @> '["BTC"]'::jsonb
                AND name LIKE :prefix
            """),
            {'prefix': f'%{prefix}%'}
        ).fetchall()

        assert len(result) == 1
        assert prefix in result[0][0]
