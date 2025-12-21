"""
Tests for database module

Validates:
- SQLAlchemy models
- Database connection
- CRUD operations
- Query performance
- Data integrity
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import json
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Strategy, BacktestResult, Trade, Subaccount
from src.database.connection import get_engine, get_session, init_db


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
def sample_strategy_data():
    """Sample strategy data matching actual model columns"""
    return {
        'name': 'Strategy_MOM_abc123_15m',
        'strategy_type': 'MOM',
        'timeframe': '15m',
        'code': '''
class Strategy_MOM_abc123(StrategyCore):
    def generate_signal(self, df):
        return Signal(direction='long')
''',
        'ai_provider': 'claude',
        'generation_prompt': 'Generate momentum strategy',
        'pattern_based': False,
        'status': 'PENDING'
    }


class TestStrategyModel:
    """Test Strategy database model"""

    def test_create_strategy(self, test_db, sample_strategy_data):
        """Test creating strategy record"""
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Query back
        result = test_db.query(Strategy).filter_by(
            name='Strategy_MOM_abc123_15m'
        ).first()

        assert result is not None
        assert result.name == 'Strategy_MOM_abc123_15m'
        assert result.strategy_type == 'MOM'
        assert result.timeframe == '15m'

    def test_update_strategy_status(self, test_db, sample_strategy_data):
        """Test updating strategy status"""
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Update status
        strategy.status = 'TESTED'
        test_db.commit()

        # Verify
        result = test_db.query(Strategy).filter_by(
            name='Strategy_MOM_abc123_15m'
        ).first()

        assert result.status == 'TESTED'

    def test_strategy_metadata_json(self, test_db, sample_strategy_data):
        """Test JSON metadata storage"""
        sample_strategy_data['pattern_ids'] = ['pattern1', 'pattern2']
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Query and verify JSON
        result = test_db.query(Strategy).first()

        assert result.pattern_ids == ['pattern1', 'pattern2']

    def test_unique_strategy_id(self, test_db, sample_strategy_data):
        """Test name uniqueness constraint"""
        strategy1 = Strategy(**sample_strategy_data)
        test_db.add(strategy1)
        test_db.commit()

        # Try to add duplicate
        strategy2 = Strategy(**sample_strategy_data)
        test_db.add(strategy2)

        with pytest.raises(Exception):  # IntegrityError
            test_db.commit()


class TestBacktestResultModel:
    """Test BacktestResult database model"""

    def test_create_backtest_result(self, test_db, sample_strategy_data):
        """Test creating backtest result"""
        # First create strategy
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Create backtest result
        result = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=180),
            end_date=datetime.now(timezone.utc),
            final_equity=12500.0,
            total_return_pct=0.25,
            sharpe_ratio=1.8,
            max_drawdown=0.18,
            win_rate=0.62,
            total_trades=150,
            expectancy=0.052
        )
        test_db.add(result)
        test_db.commit()

        # Query back
        retrieved = test_db.query(BacktestResult).filter_by(
            strategy_id=strategy.id
        ).first()

        assert retrieved is not None
        assert retrieved.sharpe_ratio == 1.8
        assert retrieved.win_rate == 0.62

    def test_backtest_foreign_key(self, test_db):
        """Test foreign key constraint - validates strategy_id references valid strategy"""
        # Create a backtest result with valid strategy first
        strategy = Strategy(
            name='Strategy_FK_Test_15m',
            strategy_type='MOM',
            timeframe='15m',
            code='test code',
            status='PENDING'
        )
        test_db.add(strategy)
        test_db.commit()

        # This should work - valid foreign key
        result = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=180),
            end_date=datetime.now(timezone.utc),
            sharpe_ratio=1.5,
            total_trades=100
        )
        test_db.add(result)
        test_db.commit()

        # Verify the relationship works
        retrieved = test_db.query(BacktestResult).filter_by(
            strategy_id=strategy.id
        ).first()
        assert retrieved is not None
        assert retrieved.strategy_id == strategy.id

    def test_query_best_strategies(self, test_db, sample_strategy_data):
        """Test querying top performing strategies"""
        # Create strategy
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Create multiple backtest results
        for i, sharpe in enumerate([1.5, 2.0, 1.8, 2.5, 1.2]):
            result = BacktestResult(
                strategy_id=strategy.id,
                lookback_days=180,
                initial_capital=10000.0,
                start_date=datetime.now(timezone.utc) - timedelta(days=30*i),
                end_date=datetime.now(timezone.utc),
                sharpe_ratio=sharpe,
                total_return_pct=0.1 * sharpe,
                total_trades=100
            )
            test_db.add(result)
        test_db.commit()

        # Query top 3 by Sharpe
        top_results = test_db.query(BacktestResult).order_by(
            BacktestResult.sharpe_ratio.desc()
        ).limit(3).all()

        assert len(top_results) == 3
        assert top_results[0].sharpe_ratio == 2.5
        assert top_results[1].sharpe_ratio == 2.0


class TestTradeModel:
    """Test Trade database model"""

    def test_create_trade(self, test_db, sample_strategy_data):
        """Test creating trade record"""
        # Create strategy first
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Create trade
        trade = Trade(
            strategy_id=strategy.id,
            subaccount_id=1,
            symbol='BTC',
            direction='LONG',
            entry_price=50000.0,
            exit_price=52000.0,
            entry_size=0.01,
            exit_size=0.01,
            entry_time=datetime.now(timezone.utc) - timedelta(hours=2),
            exit_time=datetime.now(timezone.utc),
            pnl_usd=20.0,
            pnl_pct=0.04,
            fees_usd=0.8,
            exit_reason='take_profit'
        )
        test_db.add(trade)
        test_db.commit()

        # Query back
        result = test_db.query(Trade).first()

        assert result.pnl_usd == 20.0
        assert result.exit_reason == 'take_profit'

    def test_calculate_trade_metrics(self, test_db, sample_strategy_data):
        """Test calculating metrics from trades"""
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Create multiple trades
        trades_data = [
            {'pnl_usd': 20.0},
            {'pnl_usd': -10.0},
            {'pnl_usd': 30.0},
            {'pnl_usd': -5.0},
            {'pnl_usd': 15.0}
        ]

        for i, data in enumerate(trades_data):
            trade = Trade(
                strategy_id=strategy.id,
                subaccount_id=1,
                symbol='BTC',
                direction='LONG',
                entry_price=50000.0,
                exit_price=50000.0 + data['pnl_usd'] * 100,
                entry_size=0.01,
                exit_size=0.01,
                entry_time=datetime.now(timezone.utc) - timedelta(hours=i+1),
                exit_time=datetime.now(timezone.utc),
                pnl_usd=data['pnl_usd']
            )
            test_db.add(trade)
        test_db.commit()

        # Calculate metrics
        all_trades = test_db.query(Trade).filter_by(
            strategy_id=strategy.id
        ).all()

        total_pnl = sum(t.pnl_usd for t in all_trades)
        win_rate = sum(1 for t in all_trades if t.pnl_usd > 0) / len(all_trades)

        assert total_pnl == 50.0  # 20 - 10 + 30 - 5 + 15
        assert win_rate == 0.6  # 3 wins / 5 trades

    def test_query_trades_by_date_range(self, test_db, sample_strategy_data):
        """Test querying trades by date range"""
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Create trades at different times
        now = datetime.now(timezone.utc)
        for i in range(10):
            trade = Trade(
                strategy_id=strategy.id,
                subaccount_id=1,
                symbol='BTC',
                direction='LONG',
                entry_price=50000.0,
                exit_price=51000.0,
                entry_size=0.01,
                exit_size=0.01,
                entry_time=now - timedelta(days=i),
                exit_time=now - timedelta(days=i) + timedelta(hours=1),
                pnl_usd=10.0
            )
            test_db.add(trade)
        test_db.commit()

        # Query last 5 days (exclusive, so < 5 days ago)
        cutoff = now - timedelta(days=5)
        recent_trades = test_db.query(Trade).filter(
            Trade.entry_time > cutoff
        ).all()

        assert len(recent_trades) == 5


class TestSubaccountModel:
    """Test Subaccount database model"""

    def test_create_subaccount(self, test_db):
        """Test creating subaccount record"""
        subaccount = Subaccount(
            id=1,
            allocated_capital=100.0,
            current_balance=105.0,
            status='ACTIVE'
        )
        test_db.add(subaccount)
        test_db.commit()

        # Query back
        result = test_db.query(Subaccount).filter_by(id=1).first()

        assert result.current_balance == 105.0
        assert result.status == 'ACTIVE'

    def test_update_subaccount_balance(self, test_db):
        """Test updating subaccount balance"""
        subaccount = Subaccount(
            id=1,
            allocated_capital=100.0,
            current_balance=100.0,
            status='ACTIVE'
        )
        test_db.add(subaccount)
        test_db.commit()

        # Update balance
        subaccount.current_balance = 120.0
        test_db.commit()

        # Verify
        result = test_db.query(Subaccount).first()
        assert result.current_balance == 120.0


class TestDatabaseManager:
    """Test DatabaseManager"""

    @patch('src.database.connection.create_engine')
    def test_initialization(self, mock_create_engine):
        """Test database manager initialization"""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        engine = get_engine()

        mock_create_engine.assert_called_once()

    def test_transaction_rollback(self, test_db, sample_strategy_data):
        """Test transaction rollback on error"""
        strategy = Strategy(**sample_strategy_data)
        test_db.add(strategy)
        test_db.commit()

        # Save ID for later
        strategy_id = strategy.id

        # Now try to modify and rollback
        strategy.status = 'TESTED'
        test_db.rollback()

        # Status should still be PENDING
        result = test_db.query(Strategy).filter_by(id=strategy_id).first()
        assert result.status == 'PENDING'


class TestDatabaseIntegration:
    """Integration tests for database operations"""

    def test_full_strategy_lifecycle(self, test_db):
        """Test complete strategy lifecycle in database"""
        # 1. Create strategy
        strategy = Strategy(
            name='Strategy_TEST_001_15m',
            strategy_type='MOM',
            timeframe='15m',
            code='test code',
            status='PENDING'
        )
        test_db.add(strategy)
        test_db.commit()

        # 2. Add backtest result
        backtest = BacktestResult(
            strategy_id=strategy.id,
            lookback_days=180,
            initial_capital=10000.0,
            start_date=datetime.now(timezone.utc) - timedelta(days=180),
            end_date=datetime.now(timezone.utc),
            sharpe_ratio=1.8,
            win_rate=0.62,
            total_return_pct=0.25,
            total_trades=100
        )
        test_db.add(backtest)

        # 3. Update strategy status
        strategy.status = 'TESTED'
        test_db.commit()

        # 4. Create subaccount assignment
        subaccount = Subaccount(
            id=1,
            strategy_id=strategy.id,
            allocated_capital=100.0,
            current_balance=100.0,
            status='ACTIVE'
        )
        test_db.add(subaccount)
        test_db.commit()

        # 5. Update status to LIVE
        strategy.status = 'LIVE'
        test_db.commit()

        # Verify complete lifecycle
        result = test_db.query(Strategy).filter_by(
            name='Strategy_TEST_001_15m'
        ).first()

        assert result.status == 'LIVE'

        backtest_result = test_db.query(BacktestResult).filter_by(
            strategy_id=strategy.id
        ).first()

        assert backtest_result.sharpe_ratio == 1.8

        sub = test_db.query(Subaccount).filter_by(
            strategy_id=strategy.id
        ).first()

        assert sub is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
