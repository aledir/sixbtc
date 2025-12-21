"""
Tests for classifier module

Validates:
- Strategy scoring algorithm
- Market regime filtering
- Portfolio diversification
- Top-10 selection logic
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.classifier.scorer import StrategyScorer
from src.classifier.regime_filter import MarketRegimeFilter
from src.classifier.portfolio_builder import PortfolioBuilder


@pytest.fixture
def sample_strategies():
    """Sample tested strategies with backtest results"""
    return [
        {
            'id': 'Strategy_MOM_001',
            'type': 'MOM',
            'timeframe': '15m',
            'symbol': 'BTC/USDT',
            'backtest_results': {
                'sharpe_ratio': 2.1,
                'win_rate': 0.62,
                'max_drawdown': 0.18,
                'total_return': 0.45,
                'expectancy': 0.052,
                'total_trades': 150,
                'ed_ratio': 0.289,
                'consistency': 0.68
            },
            'status': 'TESTED',
            'created_at': datetime.now() - timedelta(hours=2)
        },
        {
            'id': 'Strategy_REV_002',
            'type': 'REV',
            'timeframe': '1h',
            'symbol': 'ETH/USDT',
            'backtest_results': {
                'sharpe_ratio': 1.8,
                'win_rate': 0.58,
                'max_drawdown': 0.22,
                'total_return': 0.38,
                'expectancy': 0.045,
                'total_trades': 120,
                'ed_ratio': 0.205,
                'consistency': 0.61
            },
            'status': 'TESTED',
            'created_at': datetime.now() - timedelta(hours=3)
        },
        {
            'id': 'Strategy_MOM_003',
            'type': 'MOM',
            'timeframe': '5m',
            'symbol': 'BTC/USDT',
            'backtest_results': {
                'sharpe_ratio': 1.5,
                'win_rate': 0.55,
                'max_drawdown': 0.25,
                'total_return': 0.32,
                'expectancy': 0.038,
                'total_trades': 200,
                'ed_ratio': 0.152,
                'consistency': 0.57
            },
            'status': 'TESTED',
            'created_at': datetime.now() - timedelta(hours=1)
        },
        {
            'id': 'Strategy_TRN_004',
            'type': 'TRN',
            'timeframe': '4h',
            'symbol': 'SOL/USDT',
            'backtest_results': {
                'sharpe_ratio': 1.9,
                'win_rate': 0.60,
                'max_drawdown': 0.20,
                'total_return': 0.42,
                'expectancy': 0.048,
                'total_trades': 100,
                'ed_ratio': 0.240,
                'consistency': 0.64
            },
            'status': 'TESTED',
            'created_at': datetime.now() - timedelta(hours=4)
        },
        {
            'id': 'Strategy_REV_005',
            'type': 'REV',
            'timeframe': '15m',
            'symbol': 'AVAX/USDT',
            'backtest_results': {
                'sharpe_ratio': 1.7,
                'win_rate': 0.57,
                'max_drawdown': 0.23,
                'total_return': 0.36,
                'expectancy': 0.041,
                'total_trades': 130,
                'ed_ratio': 0.178,
                'consistency': 0.59
            },
            'status': 'TESTED',
            'created_at': datetime.now() - timedelta(hours=5)
        }
    ]


@pytest.fixture
def mock_config():
    """Mock configuration"""
    return {
        'classification': {
            'score_weights': {
                'edge': 0.40,
                'sharpe': 0.30,
                'consistency': 0.20,
                'stability': 0.10
            },
            'diversification': {
                'max_same_type': 3,
                'max_same_timeframe': 3,
                'max_same_symbol': 2
            },
            'regime_filter': {
                'enabled': True,
                'lookback_days': 30
            }
        },
        'backtesting': {
            'thresholds': {
                'min_sharpe': 1.0,
                'min_win_rate': 0.55,
                'max_drawdown': 0.30,
                'min_trades': 100
            }
        }
    }


class TestStrategyScorer:
    """Test strategy scoring logic"""

    def test_calculate_score(self, mock_config):
        """Test score calculation"""
        scorer = StrategyScorer(config=mock_config)

        metrics = {
            'sharpe_ratio': 2.0,
            'expectancy': 0.05,
            'max_drawdown': 0.20,
            'consistency': 0.65
        }

        score = scorer.score(metrics)

        # Score should be between 0 and 100
        assert 0 <= score <= 100

        # Higher quality metrics should give higher score
        assert score > 50

    def test_score_weighting(self, mock_config):
        """Test that weights are applied correctly"""
        scorer = StrategyScorer(config=mock_config)

        # High edge, low Sharpe
        metrics_high_edge = {
            'expectancy': 0.10,
            'sharpe_ratio': 1.0,
            'max_drawdown': 0.20,
            'consistency': 0.60
        }

        # Low edge, high Sharpe
        metrics_high_sharpe = {
            'expectancy': 0.02,
            'sharpe_ratio': 3.0,
            'max_drawdown': 0.20,
            'consistency': 0.60
        }

        score_edge = scorer.score(metrics_high_edge)
        score_sharpe = scorer.score(metrics_high_sharpe)

        # With edge_weight=0.4, high edge should score higher
        assert score_edge > score_sharpe

    def test_rank_strategies_basic(self, mock_config, sample_strategies):
        """Test basic strategy ranking"""
        scorer = StrategyScorer(config=mock_config)

        # Add scores to strategies manually for testing
        for s in sample_strategies:
            s['score'] = scorer.score(s['backtest_results'])

        ranked = sorted(sample_strategies, key=lambda x: x['score'], reverse=True)

        # Should be sorted by score descending
        for i in range(len(ranked) - 1):
            assert ranked[i]['score'] >= ranked[i + 1]['score']

    def test_rank_strategies(self, mock_config, sample_strategies):
        """Test strategy ranking using rank_strategies method"""
        scorer = StrategyScorer(config=mock_config)

        ranked = scorer.rank_strategies(sample_strategies)

        # Should be sorted by score descending
        for i in range(len(ranked) - 1):
            assert ranked[i]['score'] >= ranked[i + 1]['score']

        # Top strategy should be Strategy_MOM_001 (best metrics)
        assert ranked[0]['id'] == 'Strategy_MOM_001'


class TestMarketRegimeFilter:
    """Test market regime filtering"""

    @patch('src.classifier.regime_filter.pd.DataFrame')
    def test_detect_regime(self, mock_df, mock_config):
        """Test regime detection"""
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta, timezone

        # Create real DataFrame for testing
        dates = pd.date_range(
            start=datetime.now(timezone.utc) - timedelta(days=30),
            periods=100,
            freq='1h'
        )

        # Trending market data
        closes = 50000 + np.cumsum(np.random.randn(100) * 100)  # Random walk with trend
        market_data = pd.DataFrame({
            'timestamp': dates,
            'close': closes,
            'high': closes + 100,
            'low': closes - 100,
            'volume': np.random.rand(100) * 1000000
        })

        filter_obj = MarketRegimeFilter(config=mock_config)
        regime = filter_obj.detect_regime(market_data)

        assert regime in ['trending', 'ranging', 'volatile', 'calm']

    def test_filter_by_regime(self, mock_config, sample_strategies):
        """Test filtering strategies by market regime"""
        filter_obj = MarketRegimeFilter(config=mock_config)

        # Filter for trending regime (should favor MOM and TRN)
        trending = filter_obj.filter_strategies(
            strategies=sample_strategies,
            current_regime='trending'
        )

        # Should return strategies
        assert isinstance(trending, list)
        assert len(trending) > 0

        # Filter for ranging regime (should favor REV)
        ranging = filter_obj.filter_strategies(
            strategies=sample_strategies,
            current_regime='ranging'
        )

        assert isinstance(ranging, list)
        assert len(ranging) > 0


class TestPortfolioBuilder:
    """Test portfolio building and diversification"""

    def test_select_top_10(self, mock_config, sample_strategies):
        """Test top-10 selection"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(config=mock_config)
        scorer = StrategyScorer(config=mock_config)

        # Create more strategies and add required fields
        all_strategies = []
        for i in range(5):
            for j, s in enumerate(sample_strategies):
                strat = s.copy()
                strat['id'] = f"{s['id']}_{i}_{j}"
                strat['backtest_results'] = s['backtest_results'].copy()
                strat['score'] = scorer.score(strat['backtest_results'])
                # Add flat fields required by PortfolioBuilder
                strat['backtest_sharpe'] = strat['backtest_results']['sharpe_ratio']
                strat['backtest_win_rate'] = strat['backtest_results']['win_rate']
                strat['shuffle_p_value'] = 0.001  # Low p-value = statistically significant
                all_strategies.append(strat)

        selected = builder.select_top_10(all_strategies)

        # Should select up to 10 (may be less if filtering is strict)
        assert len(selected) <= 10
        assert len(selected) > 0

        # Should be sorted by score if any selected
        if len(selected) > 1:
            scores = [s['score'] for s in selected]
            assert scores == sorted(scores, reverse=True)

    def test_diversification_constraints(self, mock_config, sample_strategies):
        """Test diversification constraints"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(mock_config)
        scorer = StrategyScorer(mock_config)

        # Create many similar strategies
        mom_strategies = []
        for i in range(20):
            strat = sample_strategies[0].copy()
            strat['id'] = f'Strategy_MOM_{i:03d}'
            strat['type'] = 'MOM'
            strat['backtest_results'] = strat['backtest_results'].copy()
            strat['score'] = scorer.score(strat['backtest_results'])
            strat['backtest_sharpe'] = strat['backtest_results']['sharpe_ratio']
            strat['backtest_win_rate'] = strat['backtest_results']['win_rate']
            strat['shuffle_p_value'] = 0.001
            mom_strategies.append(strat)

        selected = builder.select_top_10(mom_strategies)

        # Should not exceed max_same_type (3)
        assert len(selected) <= 3

    def test_timeframe_diversification(self, mock_config, sample_strategies):
        """Test timeframe diversification"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(mock_config)
        scorer = StrategyScorer(mock_config)

        # Create many strategies on same timeframe
        strategies = []
        for i in range(15):
            strat = sample_strategies[0].copy()
            strat['id'] = f'Strategy_TEST_{i:03d}'
            strat['timeframe'] = '15m'
            strat['backtest_results'] = strat['backtest_results'].copy()
            strat['score'] = scorer.score(strat['backtest_results'])
            strat['backtest_sharpe'] = strat['backtest_results']['sharpe_ratio']
            strat['backtest_win_rate'] = strat['backtest_results']['win_rate']
            strat['shuffle_p_value'] = 0.001
            strategies.append(strat)

        selected = builder.select_top_10(strategies)

        # Count strategies per timeframe
        timeframe_counts = {}
        for s in selected:
            tf = s['timeframe']
            timeframe_counts[tf] = timeframe_counts.get(tf, 0) + 1

        # Should not exceed max_same_timeframe (3)
        for count in timeframe_counts.values():
            assert count <= 3

    def test_symbol_diversification(self, mock_config, sample_strategies):
        """Test symbol diversification"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(mock_config)
        scorer = StrategyScorer(mock_config)

        # Add required fields to strategies
        all_strats = []
        for i, s in enumerate(sample_strategies * 3):
            strat = s.copy()
            strat['id'] = f"{s['id']}_{i}"
            strat['backtest_results'] = s['backtest_results'].copy()
            strat['score'] = scorer.score(strat['backtest_results'])
            strat['backtest_sharpe'] = strat['backtest_results']['sharpe_ratio']
            strat['backtest_win_rate'] = strat['backtest_results']['win_rate']
            strat['shuffle_p_value'] = 0.001
            all_strats.append(strat)

        selected = builder.select_top_10(all_strats)

        # Count strategies per symbol
        symbol_counts = {}
        for s in selected:
            sym = s['symbol']
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1

        # Should not exceed max_same_symbol (2)
        for count in symbol_counts.values():
            assert count <= 2

    def test_balance_strategy_types(self, mock_config, sample_strategies):
        """Test balanced strategy type distribution"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(mock_config)
        scorer = StrategyScorer(mock_config)

        # Create independent copies with required fields
        all_strategies = []
        for i in range(5):
            for s in sample_strategies:
                strat = s.copy()
                strat['id'] = f"{s['id']}_{i}"
                strat['backtest_results'] = s['backtest_results'].copy()
                strat['score'] = scorer.score(strat['backtest_results'])
                strat['backtest_sharpe'] = s['backtest_results']['sharpe_ratio']
                strat['backtest_win_rate'] = s['backtest_results']['win_rate']
                strat['shuffle_p_value'] = 0.001
                all_strategies.append(strat)

        selected = builder.select_top_10(all_strategies)

        # Count strategy types
        type_counts = {}
        for s in selected:
            stype = s['type']
            type_counts[stype] = type_counts.get(stype, 0) + 1

        # Should have multiple strategy types (diversification)
        assert len(type_counts) >= 2


class TestClassifierIntegration:
    """Integration tests for complete classification workflow"""

    def test_full_classification_workflow(self, mock_config, sample_strategies):
        """Test complete classification workflow"""
        # 1. Score strategies
        scorer = StrategyScorer(mock_config)
        filtered = scorer.filter_strategies(sample_strategies)
        ranked = scorer.rank_strategies(filtered)

        # 2. Apply regime filter
        regime_filter = MarketRegimeFilter(mock_config)
        market_data = {'volatility': 0.03, 'trend': 0.10, 'volume_trend': 1.1}
        regime = regime_filter.detect_regime(market_data)
        regime_filtered = regime_filter.filter_for_regime(ranked, regime)

        # 3. Build portfolio - add required fields
        for s in regime_filtered:
            s['backtest_sharpe'] = s['backtest_results']['sharpe_ratio']
            s['backtest_win_rate'] = s['backtest_results']['win_rate']
            s['shuffle_p_value'] = 0.001

        builder = PortfolioBuilder(mock_config)
        selected = builder.select_top_10(regime_filtered)

        # Validate complete workflow
        assert len(filtered) > 0
        assert len(ranked) > 0
        assert regime in ['trending', 'ranging', 'volatile', 'calm']
        assert len(selected) <= 10

        # All selected should have scores
        for strategy in selected:
            assert 'score' in strategy
            assert strategy['score'] > 0

    def test_handles_empty_input(self, mock_config):
        """Test handling of empty strategy list"""
        builder = PortfolioBuilder(mock_config)

        selected = builder.select_top_10([])

        assert selected == []

    def test_handles_insufficient_strategies(self, mock_config, sample_strategies):
        """Test when fewer than 10 strategies available"""
        from src.classifier.scorer import StrategyScorer

        builder = PortfolioBuilder(mock_config)
        scorer = StrategyScorer(mock_config)

        # Only 5 strategies - add required fields and make them diverse
        strategies_5 = []
        symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'AVAX/USDT', 'ARB/USDT']
        timeframes = ['5m', '15m', '1h', '4h', '1d']
        types = ['MOM', 'REV', 'TRN', 'BRE', 'VOL']

        for i, s in enumerate(sample_strategies[:5]):
            strat = s.copy()
            strat['backtest_results'] = s['backtest_results'].copy()
            strat['score'] = scorer.score(strat['backtest_results'])
            strat['backtest_sharpe'] = s['backtest_results']['sharpe_ratio']
            strat['backtest_win_rate'] = s['backtest_results']['win_rate']
            strat['shuffle_p_value'] = 0.001
            # Make them all different to avoid diversification filtering
            strat['symbol'] = symbols[i]
            strat['timeframe'] = timeframes[i]
            strat['type'] = types[i]
            strategies_5.append(strat)

        selected = builder.select_top_10(strategies_5)

        # Should return strategies that pass minimum thresholds
        # (Note: Only 2 of the 5 sample strategies have score >= 50)
        assert len(selected) > 0
        assert len(selected) <= 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
