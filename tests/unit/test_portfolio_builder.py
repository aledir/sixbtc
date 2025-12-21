"""
Test Portfolio Builder

Unit tests for top 10 strategy selection with diversification.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.classifier.portfolio_builder import PortfolioBuilder


def create_strategy(
    name='Test',
    score=70,
    strategy_type='MOM',
    timeframe='15m',
    sharpe=1.5,
    win_rate=0.6,
    p_value=0.01
):
    """Helper to create test strategy"""
    return {
        'name': name,
        'score': score,
        'type': strategy_type,
        'timeframe': timeframe,
        'backtest_sharpe': sharpe,
        'backtest_win_rate': win_rate,
        'shuffle_p_value': p_value
    }


class TestPortfolioBuilder:
    """Test portfolio construction"""

    def test_selects_top_10(self):
        """Selects up to 10 strategies"""
        builder = PortfolioBuilder()

        # Create 20 good strategies
        strategies = [
            create_strategy(
                name=f'Strategy_{i}',
                score=90-i,
                strategy_type=['MOM', 'REV', 'TRN', 'BRE'][i % 4],
                timeframe=['15m', '1h', '4h'][i % 3]
            )
            for i in range(20)
        ]

        selected = builder.select_top_10(strategies)

        # Should select exactly 10 (or less if diversification constraints)
        assert len(selected) <= 10
        assert len(selected) > 0

    def test_diversification_by_type(self):
        """Max 3 of the same type"""
        builder = PortfolioBuilder()

        # Create 20 MOM strategies with decreasing scores
        strategies = [
            create_strategy(
                name=f'MOM_{i}',
                score=100-i,
                strategy_type='MOM',
                timeframe=['15m', '1h', '4h'][i % 3]  # Vary timeframe
            )
            for i in range(20)
        ]

        selected = builder.select_top_10(strategies)

        # Count MOM strategies
        mom_count = sum(1 for s in selected if s['type'] == 'MOM')

        # Should be limited to 3
        assert mom_count <= 3

    def test_diversification_by_timeframe(self):
        """Max 5 of the same timeframe"""
        builder = PortfolioBuilder()

        # Create 20 strategies on 15m timeframe
        strategies = [
            create_strategy(
                name=f'Strategy_{i}',
                score=100-i,
                strategy_type=['MOM', 'REV', 'TRN', 'BRE'][i % 4],  # Vary type
                timeframe='15m'
            )
            for i in range(20)
        ]

        selected = builder.select_top_10(strategies)

        # Count 15m strategies
        tf_count = sum(1 for s in selected if s['timeframe'] == '15m')

        # Should be limited to 5
        assert tf_count <= 5

    def test_minimum_thresholds(self):
        """Filters strategies below threshold"""
        builder = PortfolioBuilder()

        strategies = [
            create_strategy(name='Good', score=60, sharpe=1.5, win_rate=0.6, p_value=0.01),
            create_strategy(name='BadScore', score=40, sharpe=1.5, win_rate=0.6, p_value=0.01),
            create_strategy(name='BadSharpe', score=60, sharpe=0.5, win_rate=0.6, p_value=0.01),
            create_strategy(name='BadWinRate', score=60, sharpe=1.5, win_rate=0.4, p_value=0.01),
            create_strategy(name='BadPValue', score=60, sharpe=1.5, win_rate=0.6, p_value=0.1),
        ]

        selected = builder.select_top_10(strategies)

        # Only 'Good' should pass
        assert len(selected) == 1
        assert selected[0]['name'] == 'Good'

    def test_empty_input(self):
        """Handles empty input"""
        builder = PortfolioBuilder()
        selected = builder.select_top_10([])
        assert selected == []

    def test_all_below_threshold(self):
        """Handles case where all strategies fail thresholds"""
        builder = PortfolioBuilder()

        strategies = [
            create_strategy(name=f'Bad_{i}', score=30, sharpe=0.5, win_rate=0.4)
            for i in range(10)
        ]

        selected = builder.select_top_10(strategies)
        assert selected == []

    def test_portfolio_stats(self):
        """Portfolio stats calculated correctly"""
        builder = PortfolioBuilder()

        portfolio = [
            create_strategy(name='A', score=80, strategy_type='MOM', timeframe='15m'),
            create_strategy(name='B', score=70, strategy_type='REV', timeframe='1h'),
            create_strategy(name='C', score=60, strategy_type='MOM', timeframe='4h'),
        ]

        stats = builder.get_portfolio_stats(portfolio)

        assert stats['count'] == 3
        assert stats['avg_score'] == 70  # (80+70+60)/3
        assert stats['type_distribution']['MOM'] == 2
        assert stats['type_distribution']['REV'] == 1
        assert stats['timeframe_distribution']['15m'] == 1

    def test_portfolio_stats_empty(self):
        """Portfolio stats for empty portfolio"""
        builder = PortfolioBuilder()
        stats = builder.get_portfolio_stats([])

        assert stats['count'] == 0
        assert stats['avg_score'] == 0
