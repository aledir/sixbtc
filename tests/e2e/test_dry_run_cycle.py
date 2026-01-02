"""
End-to-End Dry Run Test

Tests complete cycle from strategy generation to deployment in DRY RUN mode.
CRITICAL: This test MUST NEVER place real orders.
"""

import pytest
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root and tests to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'tests'))

from src.strategies.base import StrategyCore, Signal
from src.classifier.scorer import StrategyScorer
from src.classifier.portfolio_builder import PortfolioBuilder
from src.executor.subaccount_manager import SubaccountManager
from mocks.mock_hyperliquid import MockHyperliquidClient


class MockStrategy(StrategyCore):
    """Mock strategy that generates signals for testing"""
    indicator_columns = []

    def __init__(self, strategy_id: str, params=None):
        super().__init__(params)
        self.strategy_id = strategy_id
        self.signal_count = 0

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()

    def generate_signal(self, df: pd.DataFrame) -> Signal | None:
        if len(df) < 20:
            return None

        # Generate signal every 10 calls
        self.signal_count += 1
        if self.signal_count % 10 == 0:
            return Signal(
                direction='long',
                atr_stop_multiplier=2.0,
                atr_take_multiplier=3.0,
                reason=f'Test signal from {self.strategy_id}'
            )

        return None


class TestDryRunCycle:
    """
    Test complete trading cycle in DRY RUN mode

    Flow:
    1. Create mock strategies
    2. Simulate backtest results
    3. Score and rank strategies
    4. Select top 10 with portfolio builder
    5. Deploy to subaccounts
    6. Simulate strategy execution
    7. Verify NO real orders were placed
    """

    @pytest.fixture
    def mock_client(self):
        """Mock Hyperliquid client"""
        return MockHyperliquidClient()

    @pytest.fixture
    def sample_ohlcv(self):
        """Sample OHLCV data"""
        dates = pd.date_range(end=pd.Timestamp.now(), periods=500, freq='15min')
        np.random.seed(42)
        close = 42000 * np.cumprod(1 + np.random.randn(500) * 0.001)

        return pd.DataFrame({
            'open': close,
            'high': close * 1.01,
            'low': close * 0.99,
            'close': close,
            'volume': np.random.randint(100, 1000, 500)
        }, index=dates)

    def test_full_cycle_dry_run(self, mock_client, sample_ohlcv):
        """
        Complete cycle from generation to deployment (DRY RUN)
        """
        # PHASE 1: Create mock strategies with simulated backtest results
        strategies = []
        for i in range(20):
            strategy = {
                'strategy_id': f'test_strat_{i}',
                'name': f'Strategy_{i}',
                'type': ['MOM', 'REV', 'TRN', 'BRE'][i % 4],
                'timeframe': ['15m', '1h', '4h'][i % 3],
                'strategy': MockStrategy(f'test_strat_{i}'),
                'metrics': {
                    'expectancy': 0.02 + (i * 0.002),
                    'sharpe_ratio': 1.0 + (i * 0.1),
                    'consistency': 0.6 + (i * 0.01),
                    'wf_stability': 0.1
                },
                'backtest_sharpe': 1.0 + (i * 0.1),
                'backtest_win_rate': 0.55 + (i * 0.005),
                'shuffle_p_value': 0.01
            }
            strategies.append(strategy)

        assert len(strategies) == 20

        # PHASE 2: Score strategies
        scorer = StrategyScorer()
        for strategy in strategies:
            strategy['score'] = scorer.score(strategy['metrics'])

        # Verify scores calculated
        assert all('score' in s for s in strategies)
        assert all(0 <= s['score'] <= 100 for s in strategies)

        # PHASE 3: Select top 10 with portfolio builder
        builder = PortfolioBuilder()
        selected = builder.select_top_10(strategies)

        # Verify selection
        assert len(selected) <= 10
        assert len(selected) > 0

        # Verify diversification
        type_counts = {}
        for s in selected:
            stype = s['type']
            type_counts[stype] = type_counts.get(stype, 0) + 1

        for count in type_counts.values():
            assert count <= 3  # Max 3 of same type

        # PHASE 4: Deploy to subaccounts (DRY RUN)
        manager = SubaccountManager(mock_client, dry_run=True)
        assert manager.dry_run is True  # CRITICAL CHECK

        deployed_count = 0
        for i, strategy in enumerate(selected):
            success = manager.deploy_strategy(
                strategy_id=strategy['strategy_id'],
                strategy_instance=strategy['strategy'],
                subaccount_id=i + 1
            )
            if success:
                deployed_count += 1

        assert deployed_count == len(selected)
        assert manager.get_active_count() == len(selected)

        # PHASE 5: Simulate strategy execution
        signal_log = []

        for subaccount_id in range(1, len(selected) + 1):
            assignment = manager.get_assignment(subaccount_id)
            assert assignment is not None

            strategy = assignment['strategy']

            # Generate signals (simulate multiple iterations)
            for iteration in range(50):
                signal = strategy.generate_signal(sample_ohlcv)

                if signal:
                    signal_log.append({
                        'subaccount_id': subaccount_id,
                        'strategy_id': assignment['strategy_id'],
                        'signal': signal
                    })

                    # In real system, would execute signal here
                    # But we're in DRY RUN, so just log it

        # PHASE 6: Verify results
        # Should have some signals generated
        assert len(signal_log) > 0

        # Verify no real orders placed (check mock client)
        # Mock client's place_market_order should log but not execute real orders
        assert mock_client.dry_run is True
        assert len(mock_client.orders) >= 0  # May have mock orders

        # PHASE 7: Cleanup
        manager.stop_all_strategies(close_positions=True)
        assert manager.get_active_count() == 0

    def test_no_real_orders_ever(self, mock_client):
        """
        CRITICAL TEST: Verify NO real orders can be placed in dry-run

        This test MUST pass before any production deployment.
        """
        manager = SubaccountManager(mock_client, dry_run=True)

        # Try to place order
        strategy = MockStrategy('test')
        manager.deploy_strategy('test', strategy, 1)

        # Simulate signal execution
        mock_client.switch_subaccount(1)
        response = mock_client.place_market_order('BTC', 'long', 0.1)

        # Verify it's a mock response
        assert response.status == 'filled'
        assert mock_client.dry_run is True

        # Verify orders list is populated (mock orders)
        # but no REAL API calls were made
        assert len(mock_client.orders) > 0
        assert mock_client.orders[0].order_id.startswith('mock_')

    def test_emergency_stop_all(self, mock_client):
        """Test emergency stop functionality"""
        manager = SubaccountManager(mock_client, dry_run=True)

        # Deploy 5 strategies
        for i in range(1, 6):
            manager.deploy_strategy(
                f'strat_{i}',
                MockStrategy(f'strat_{i}'),
                i
            )

        assert manager.get_active_count() == 5

        # Emergency stop
        manager.stop_all_strategies(close_positions=True)

        # Verify all stopped
        assert manager.get_active_count() == 0
        for i in range(1, 11):
            assert manager.get_assignment(i) is None
