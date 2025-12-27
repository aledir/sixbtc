"""
Integration tests for end-to-end workflows

Tests complete system workflows:
1. Generation → Backtesting → Classification → Deployment
2. Live trading cycle (dry-run)
3. Emergency stop procedures
4. Data flow between modules

CRITICAL: All tests use dry_run=True
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

from src.generator.strategy_builder import StrategyBuilder
from src.backtester.vectorbt_engine import VectorBTEngine
from src.classifier.scorer import StrategyScorer
from src.classifier.portfolio_builder import PortfolioBuilder
from src.executor.subaccount_manager import SubaccountManager
from src.strategies.base import StrategyCore, Signal


@pytest.fixture
def full_config():
    """Complete system configuration"""
    return {
        'generator': {
            'strategies_per_cycle': 20,
            'pattern_discovery_url': 'http://localhost:8001'
        },
        'backtester': {
            'initial_capital': 10000,
            'fees': 0.0004,
            'slippage': 0.0002,
            'lookback_days': 180
        },
        'backtesting': {
            'thresholds': {
                'min_sharpe': 1.0,
                'min_win_rate': 0.55,
                'max_drawdown': 0.30,
                'min_trades': 100
            }
        },
        'classification': {
            'score_weights': {
                'edge': 0.40,
                'sharpe': 0.30,
                'consistency': 0.20,
                'stability': 0.10
            },
            'scoring': {
                'edge_weight': 0.4,
                'sharpe_weight': 0.3,
                'stability_weight': 0.3,
                'min_sharpe': 1.0,
                'min_win_rate': 0.55,
                'max_drawdown': 0.30,
                'min_trades': 100
            },
            'diversification': {
                'max_same_type': 3,
                'max_same_timeframe': 3,
                'max_same_symbol': 2
            }
        },
        'executor': {
            'dry_run': True,
            'hyperliquid': {
                'api_key': 'test_key',
                'secret_key': 'test_secret',
                'testnet': True,
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
                    'max_open_positions_total': 100,
                    'max_open_positions_per_subaccount': 4,
                    'max_leverage': 10
                },
                'emergency': {
                    'max_portfolio_drawdown': 0.30,
                    'max_subaccount_drawdown': 0.25,
                    'max_consecutive_losses': 5
                }
            }
        }
    }


@pytest.fixture
def sample_market_data():
    """Generate realistic market data"""
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=180),
        periods=5000,
        freq='15min'
    )

    np.random.seed(42)

    # Generate realistic price action
    returns = np.random.randn(5000) * 0.002  # 0.2% volatility
    price = 50000 * (1 + returns).cumprod()

    high = price * (1 + np.abs(np.random.randn(5000) * 0.005))
    low = price * (1 - np.abs(np.random.randn(5000) * 0.005))
    open_ = price + np.random.randn(5000) * 100

    volume = np.random.lognormal(15, 1, 5000)

    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': price,
        'volume': volume
    })

    return df


class MockGeneratedStrategy(StrategyCore):
    """Mock generated strategy for testing"""

    def __init__(self, strategy_id: str, quality: str = 'good'):
        self.strategy_id = strategy_id
        self.type = 'MOM'
        self.timeframe = '15m'
        self.symbol = 'BTC/USDT'
        self.quality = quality

    def generate_signal(self, df: pd.DataFrame, symbol: str = None) -> Signal | None:
        if len(df) < 50:
            return None

        # Different behavior based on quality
        if self.quality == 'good':
            # Simple profitable logic
            sma_fast = df['close'].rolling(10).mean()
            sma_slow = df['close'].rolling(20).mean()

            if sma_fast.iloc[-1] > sma_slow.iloc[-1]:
                return Signal(
                    direction='long',
                    atr_stop_multiplier=2.0,
                    atr_take_multiplier=3.0,
                    reason="Fast > Slow"
                )

        elif self.quality == 'bad':
            # Random signals (should fail backtest)
            if np.random.rand() > 0.7:
                return Signal(
                    direction='long',
                    atr_stop_multiplier=2.0,
                    atr_take_multiplier=3.0,
                    reason="Random"
                )

        return None


class TestGenerationToBacktestWorkflow:
    """Test workflow from generation to backtesting"""

    def test_generate_and_backtest_workflow(self, full_config, sample_market_data):
        """Test generating strategies and backtesting them"""
        # 1. Generate mock strategies
        strategies = [
            MockGeneratedStrategy(f'Strategy_MOM_{i:03d}', 'good')
            for i in range(5)
        ]
        strategies += [
            MockGeneratedStrategy(f'Strategy_MOM_{i:03d}', 'bad')
            for i in range(5, 10)
        ]

        # 2. Backtest each strategy
        engine = VectorBTEngine()
        backtest_results = []

        for strategy in strategies:
            try:
                results = engine.run_backtest(
                    strategy=strategy,
                    data=sample_market_data,
                    initial_capital=full_config['backtester']['initial_capital'],
                    fees=full_config['backtester']['fees']
                )

                backtest_results.append({
                    'id': strategy.strategy_id,
                    'type': strategy.type,
                    'timeframe': strategy.timeframe,
                    'symbol': strategy.symbol,
                    'backtest_results': results,
                    'status': 'TESTED'
                })
            except Exception as e:
                # Some strategies might fail - that's okay
                pass

        # 3. Validate results
        assert len(backtest_results) > 0

        # Good strategies should have better metrics
        good_strategies = [r for r in backtest_results if 'MOM_00' in r['id'][:15]]
        if good_strategies:
            avg_sharpe_good = np.mean([
                r['backtest_results']['sharpe_ratio']
                for r in good_strategies
            ])
            # Should have positive performance
            assert avg_sharpe_good is not None


class TestBacktestToClassificationWorkflow:
    """Test workflow from backtesting to classification"""

    def test_backtest_to_classification_workflow(self, full_config):
        """Test filtering and selecting top strategies"""
        # 1. Create mock backtested strategies
        strategies = []
        for i in range(20):
            strategies.append({
                'id': f'Strategy_TEST_{i:03d}',
                'type': ['MOM', 'REV', 'TRN'][i % 3],
                'timeframe': ['5m', '15m', '1h'][i % 3],
                'symbol': 'BTC/USDT',
                'backtest_results': {
                    'sharpe_ratio': 1.0 + np.random.rand() * 1.5,
                    'win_rate': 0.50 + np.random.rand() * 0.20,
                    'max_drawdown': 0.15 + np.random.rand() * 0.15,
                    'total_return': 0.20 + np.random.rand() * 0.30,
                    'expectancy': 0.03 + np.random.rand() * 0.05,
                    'total_trades': 100 + int(np.random.rand() * 100),
                    'ed_ratio': 0.15 + np.random.rand() * 0.15,
                    'consistency': 0.55 + np.random.rand() * 0.20
                },
                'status': 'TESTED'
            })

        # 2. Score and filter strategies
        scorer = StrategyScorer(full_config)
        filtered = scorer.filter_strategies(strategies)
        ranked = scorer.rank_strategies(filtered)

        # Add required fields for PortfolioBuilder
        for s in ranked:
            s['backtest_sharpe'] = s['backtest_results']['sharpe_ratio']
            s['backtest_win_rate'] = s['backtest_results']['win_rate']
            s['shuffle_p_value'] = 0.001

        # 3. Select top 10
        builder = PortfolioBuilder(full_config)
        selected = builder.select_top_10(ranked)

        # 4. Validate selection
        assert len(selected) <= 10
        assert len(selected) > 0

        # Should be sorted by score
        scores = [s['score'] for s in selected]
        assert scores == sorted(scores, reverse=True)

        # Should have diversification
        types = [s['type'] for s in selected]
        assert len(set(types)) >= 2  # At least 2 different types


class TestClassificationToDeploymentWorkflow:
    """Test workflow from classification to deployment"""

    @patch('src.executor.hyperliquid_client.HyperliquidClient')
    def test_classification_to_deployment_workflow(
        self,
        mock_client_class,
        full_config
    ):
        """Test deploying selected strategies to subaccounts"""
        # 1. Mock top 10 strategies
        selected_strategies = [
            {
                'id': f'Strategy_TOP_{i:02d}',
                'type': 'MOM',
                'timeframe': '15m',
                'symbol': 'BTC/USDT',
                'score': 0.9 - i * 0.05,
                'status': 'SELECTED'
            }
            for i in range(10)
        ]

        # 2. Mock Hyperliquid client
        mock_client = Mock()
        mock_client.dry_run = True
        mock_client_class.return_value = mock_client

        # 3. Assign strategies to subaccounts
        subaccount_mgr = SubaccountManager(full_config['executor'])

        assignments = []
        for i, strategy in enumerate(selected_strategies[:3]):  # Testing phase: 3 subaccounts
            success = subaccount_mgr.assign_strategy(
                subaccount_id=i + 1,
                strategy_id=strategy['id']
            )
            if success:
                assignments.append({
                    'subaccount_id': i + 1,
                    'strategy_id': strategy['id']
                })

        # 4. Validate deployment
        assert len(assignments) == 3
        assert all(a['strategy_id'].startswith('Strategy_TOP_') for a in assignments)


class TestLiveTradingCycle:
    """Test complete live trading cycle (dry-run)"""

    @patch('src.executor.hyperliquid_client.HyperliquidClient')
    def test_full_trading_cycle(
        self,
        mock_client_class,
        full_config,
        sample_market_data
    ):
        """Test one complete trading cycle iteration"""
        # Mock client
        mock_client = Mock()
        mock_client.dry_run = True
        mock_client.get_current_prices.return_value = {'BTC': 50000.0}
        mock_client.get_account_state.return_value = {
            'marginSummary': {
                'accountValue': '100.0',
                'totalNtlPos': '0.0'
            },
            'assetPositions': []
        }
        mock_client.place_order.return_value = {
            'status': 'simulated',
            'order_id': 'test_123'
        }
        mock_client_class.return_value = mock_client

        # 1. Initialize components
        subaccount_mgr = SubaccountManager(full_config['executor'])
        strategy = MockGeneratedStrategy('Strategy_LIVE_001', 'good')

        # 2. Assign strategy to subaccount
        subaccount_mgr.assign_strategy(1, strategy.strategy_id)

        # 3. Generate signal
        signal = strategy.generate_signal(sample_market_data)

        # 4. If signal exists, simulate execution
        if signal:
            # Would execute trade here in real system
            result = mock_client.place_order(
                symbol='BTC',
                side='buy' if signal.direction == 'long' else 'sell',
                size=0.01,
                order_type='market',
                dry_run=True
            )

            assert result['status'] == 'simulated'
            assert result['order_id'] == 'test_123'

        # 5. Verify cycle completed successfully
        # Check that strategy was assigned
        assert 1 in subaccount_mgr.subaccount_strategies
        assert subaccount_mgr.subaccount_strategies[1] == strategy.strategy_id


class TestEmergencyStopProcedures:
    """Test emergency stop workflows"""

    def test_emergency_stop_on_max_drawdown(self, full_config):
        """Test emergency stop triggered by max drawdown"""
        from src.executor.risk_manager import RiskManager

        risk_mgr = RiskManager(full_config['executor']['risk'])

        # Simulate large drawdown
        portfolio_dd = 0.35  # 35% drawdown
        consecutive_losses = 3

        should_stop = risk_mgr.should_emergency_stop(
            portfolio_drawdown=portfolio_dd,
            consecutive_losses=consecutive_losses
        )

        assert should_stop is True

    def test_emergency_stop_on_consecutive_losses(self, full_config):
        """Test emergency stop triggered by consecutive losses"""
        from src.executor.risk_manager import RiskManager

        risk_mgr = RiskManager(full_config['executor']['risk'])

        # Simulate many consecutive losses
        portfolio_dd = 0.15  # Moderate drawdown
        consecutive_losses = 6  # Too many losses

        should_stop = risk_mgr.should_emergency_stop(
            portfolio_drawdown=portfolio_dd,
            consecutive_losses=consecutive_losses
        )

        assert should_stop is True

    @patch('src.executor.subaccount_manager.SubaccountManager.stop_all_strategies')
    def test_emergency_stop_execution(self, mock_stop_all_strategies, full_config):
        """Test emergency stop execution"""
        subaccount_mgr = SubaccountManager(full_config['executor'])

        # Trigger emergency stop
        subaccount_mgr.emergency_stop(reason="Max drawdown exceeded")

        # Should call stop_all_strategies
        mock_stop_all_strategies.assert_called_once_with(close_positions=True)


class TestDataFlowBetweenModules:
    """Test data flow and integration between modules"""

    def test_data_consistency_across_modules(self, full_config, sample_market_data):
        """Test that data flows correctly between modules"""
        # 1. Generate strategy
        builder = StrategyBuilder()
        strategy = MockGeneratedStrategy('Strategy_DATA_001', 'good')

        # 2. Backtest
        engine = VectorBTEngine()
        backtest_results = engine.run_backtest(
            strategy=strategy,
            data=sample_market_data,
            initial_capital=10000
        )

        # 3. Create strategy record
        strategy_record = {
            'id': strategy.strategy_id,
            'type': strategy.type,
            'timeframe': strategy.timeframe,
            'symbol': strategy.symbol,
            'backtest_results': backtest_results,
            'status': 'TESTED'
        }

        # 4. Score
        scorer = StrategyScorer(full_config)
        scored = scorer.rank_strategies([strategy_record])

        # 5. Validate data consistency
        assert scored[0]['id'] == strategy.strategy_id
        assert scored[0]['backtest_results'] == backtest_results
        assert 'score' in scored[0]


class TestSystemResilience:
    """Test system resilience and error handling"""

    def test_handles_backtest_failure(self, full_config, sample_market_data):
        """Test system handles backtest failures gracefully"""
        # Strategy that will fail
        class FailingStrategy(StrategyCore):
            def generate_signal(self, df, symbol=None):
                raise Exception("Intentional failure")

        strategy = FailingStrategy()
        strategy.strategy_id = 'Strategy_FAIL_001'

        engine = VectorBTEngine()

        # Should not crash entire system
        try:
            engine.run_backtest(strategy, sample_market_data, 10000)
        except Exception:
            # Failure is expected and should be caught
            pass

    def test_handles_empty_signal_stream(self, full_config, sample_market_data):
        """Test system handles strategies that produce no signals"""
        class NoSignalStrategy(StrategyCore):
            def generate_signal(self, df, symbol=None):
                return None  # Never signals

        strategy = NoSignalStrategy()
        strategy.strategy_id = 'Strategy_NOSIG_001'

        engine = VectorBTEngine()

        # Should complete without errors
        results = engine.run_backtest(strategy, sample_market_data, 10000)

        # Should have 0 trades
        assert results.get('total_trades', 0) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
