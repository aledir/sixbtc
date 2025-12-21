"""
Test Strategy Scorer

Unit tests for multi-factor scoring system.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.classifier.scorer import StrategyScorer


class TestStrategyScorer:
    """Test strategy scoring system"""

    def test_score_calculation(self):
        """Score calculated correctly with default weights"""
        scorer = StrategyScorer()

        metrics = {
            'expectancy': 0.05,       # 5% edge
            'sharpe_ratio': 2.0,
            'consistency': 0.8,       # 80% time in profit
            'wf_stability': 0.1       # 10% variation (lower is better)
        }

        score = scorer.score(metrics)

        # Score should be between 0 and 100
        assert 0 <= score <= 100

        # With good metrics, should be > 50
        assert score > 50

    def test_better_metrics_higher_score(self):
        """Better metrics produce higher score"""
        scorer = StrategyScorer()

        good_metrics = {
            'expectancy': 0.08,
            'sharpe_ratio': 2.5,
            'consistency': 0.9,
            'wf_stability': 0.05
        }

        bad_metrics = {
            'expectancy': 0.01,
            'sharpe_ratio': 0.5,
            'consistency': 0.4,
            'wf_stability': 0.5
        }

        good_score = scorer.score(good_metrics)
        bad_score = scorer.score(bad_metrics)

        assert good_score > bad_score

    def test_zero_metrics(self):
        """Zero metrics produce low score"""
        scorer = StrategyScorer()

        zero_metrics = {
            'expectancy': 0,
            'sharpe_ratio': 0,
            'consistency': 0,
            'wf_stability': 1  # Worst stability
        }

        score = scorer.score(zero_metrics)

        # Should be very low (close to 0)
        assert score < 10

    def test_custom_weights(self):
        """Custom weights work correctly"""
        config = {
            'classification': {
                'score_weights': {
                    'edge': 0.5,
                    'sharpe': 0.3,
                    'consistency': 0.1,
                    'stability': 0.1
                }
            }
        }

        scorer = StrategyScorer(config)
        assert scorer.weights['edge'] == 0.5

    def test_rank_strategies(self):
        """Strategies ranked by score"""
        scorer = StrategyScorer()

        strategies = [
            {'name': 'A', 'metrics': {'expectancy': 0.08, 'sharpe_ratio': 2.5, 'consistency': 0.9, 'wf_stability': 0.05}},
            {'name': 'B', 'metrics': {'expectancy': 0.02, 'sharpe_ratio': 1.0, 'consistency': 0.5, 'wf_stability': 0.3}},
            {'name': 'C', 'metrics': {'expectancy': 0.05, 'sharpe_ratio': 1.8, 'consistency': 0.7, 'wf_stability': 0.15}},
        ]

        ranked = scorer.rank_strategies(strategies)

        # A should be first (best metrics)
        assert ranked[0]['name'] == 'A'
        assert ranked[0]['score'] > ranked[1]['score'] > ranked[2]['score']

    def test_missing_metrics(self):
        """Missing metrics handled gracefully"""
        scorer = StrategyScorer()

        incomplete_metrics = {
            'expectancy': 0.05,
            # Missing sharpe_ratio, consistency, wf_stability
        }

        # Should not crash
        score = scorer.score(incomplete_metrics)
        assert isinstance(score, float)
        assert 0 <= score <= 100
