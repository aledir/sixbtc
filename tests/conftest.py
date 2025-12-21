"""
Global test fixtures for SixBTC

Provides reusable fixtures for all test modules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import Base
from src.strategies.base import StrategyCore, Signal


@pytest.fixture
def sample_ohlcv():
    """
    Generate sample OHLCV data for testing

    Usage:
        df = sample_ohlcv(n_candles=500, seed=42)
    """
    def _create(n_candles=500, seed=42, start_price=42000.0):
        np.random.seed(seed)

        dates = pd.date_range(
            end=datetime.now(),
            periods=n_candles,
            freq='15min'
        )

        # Random walk price
        returns = np.random.randn(n_candles) * 0.001
        close = start_price * np.cumprod(1 + returns)

        df = pd.DataFrame({
            'open': close * (1 + np.random.randn(n_candles) * 0.001),
            'high': close * (1 + np.abs(np.random.randn(n_candles)) * 0.002),
            'low': close * (1 - np.abs(np.random.randn(n_candles)) * 0.002),
            'close': close,
            'volume': np.random.randint(100, 1000, n_candles).astype(float)
        }, index=dates)

        # Ensure OHLC relationships are valid
        df['high'] = df[['open', 'high', 'close']].max(axis=1)
        df['low'] = df[['open', 'low', 'close']].min(axis=1)

        return df

    return _create


@pytest.fixture
def mock_strategy():
    """Simple test strategy for testing"""
    class MockStrategy(StrategyCore):
        def generate_signal(self, df: pd.DataFrame) -> Signal | None:
            if len(df) < 20:
                return None

            # Simple SMA crossover
            sma_fast = df['close'].rolling(10).mean().iloc[-1]
            sma_slow = df['close'].rolling(20).mean().iloc[-1]

            if sma_fast > sma_slow:
                return Signal(
                    direction='long',
                    atr_stop_multiplier=2.0,
                    atr_take_multiplier=3.0,
                    reason='SMA crossover'
                )

            return None

    return MockStrategy()


@pytest.fixture
def db_session():
    """In-memory database session for testing"""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


@pytest.fixture
def dry_run_config():
    """Configuration with dry_run=True (SAFE for testing)"""
    return {
        'system': {
            'name': 'SixBTC-Test',
            'version': '1.0.0-test'
        },
        'trading': {
            'dry_run': True,  # CRITICAL: No real orders
            'timeframes': {
                'available': ['15m', '1h'],
                'primary': '15m'
            },
            'data': {
                'lookback_bars': 1000
            }
        },
        'hyperliquid': {
            'dry_run': True,  # CRITICAL: No real orders
            'base_url': 'https://api.hyperliquid.xyz',
            'taker_fee': 0.00045,
            'expected_slippage': 0.0005,
            'websocket': {
                'max_symbols_per_connection': 100,
                'auto_reconnect': True,
                'ping_interval': 30,
                'ping_timeout': 10
            },
            'subaccounts': {
                'total': 10,
                'test_mode': {
                    'enabled': True,
                    'count': 3,
                    'capital_per_account': 100
                }
            }
        },
        'risk': {
            'sizing_mode': 'atr',
            'fixed_fractional': {
                'risk_per_trade_pct': 0.02,
                'max_position_size_pct': 0.20
            },
            'atr': {
                'period': 14,
                'stop_multiplier': 2.0,
                'take_profit_multiplier': 3.0,
                'min_risk_reward': 1.5,
                'volatility_scaling': {
                    'enabled': True,
                    'low_volatility_threshold': 0.015,
                    'high_volatility_threshold': 0.05,
                    'scaling_factor': 0.5
                }
            },
            'limits': {
                'max_open_positions_total': 10,
                'max_open_positions_per_subaccount': 4,
                'max_leverage': 10
            },
            'emergency': {
                'max_portfolio_drawdown': 0.30,
                'max_consecutive_losses': 5
            }
        },
        'deployment': {
            'shutdown': {
                'close_positions': False,
                'cancel_orders': True,
                'graceful_timeout': 30
            }
        },
        'execution': {
            'orchestrator': {
                'mode': 'adaptive'
            }
        },
        'backtesting': {
            'lookback_days': 30,  # Shorter for tests
            'initial_capital': 10000,
            'thresholds': {
                'min_sharpe': 1.0,
                'min_win_rate': 0.55,
                'min_total_trades': 10,  # Lower for tests
                'max_drawdown': 0.30
            }
        },
        'classification': {
            'score_weights': {
                'edge': 0.40,
                'sharpe': 0.30,
                'consistency': 0.20,
                'stability': 0.10
            },
            'diversification': {
                'max_same_type': 3,
                'max_same_timeframe': 3
            }
        },
        'generation': {
            'pattern_discovery': {
                'api_url': 'http://localhost:8001'
            }
        },
        'development': {
            'testing': {
                'dry_run': True
            }
        },
        'dry_run': True  # Simplified access for legacy code
    }


@pytest.fixture
def sample_signals():
    """Sample trading signals for testing"""
    return [
        Signal(
            direction='long',
            atr_stop_multiplier=2.0,
            atr_take_multiplier=3.0,
            reason='Test long signal'
        ),
        Signal(
            direction='short',
            atr_stop_multiplier=2.0,
            atr_take_multiplier=3.0,
            reason='Test short signal'
        ),
        Signal(
            direction='close',
            reason='Test close signal'
        )
    ]


@pytest.fixture
def sample_strategy_code():
    """Sample valid strategy code"""
    return '''
import pandas as pd
import numpy as np
from src.strategies.base import StrategyCore, Signal

class Strategy_MOM_test123(StrategyCore):
    """Test momentum strategy"""

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        sma_fast = df['close'].rolling(10).mean().iloc[-1]
        sma_slow = df['close'].rolling(20).mean().iloc[-1]

        if sma_fast > sma_slow:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason='SMA crossover'
            )

        return None
'''
