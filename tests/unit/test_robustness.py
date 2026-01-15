"""
Unit tests for Robustness Calculation

Tests the robustness score formula:
robustness = 0.50 * oos_ratio + 0.35 * trade_score + 0.15 * simplicity

Components:
- oos_ratio = min(1.0, OOS_Sharpe / IS_Sharpe)
- trade_score = min(1.0, total_trades / 150)
- simplicity = 1.0 / num_indicators
"""

import pytest
from unittest.mock import MagicMock


def calculate_robustness(
    is_sharpe: float,
    oos_sharpe: float,
    is_trades: int,
    oos_trades: int,
    num_indicators: int,
    weights: dict = None,
    trade_target: int = 150,
) -> float:
    """
    Calculate robustness score (0-1).

    This is a standalone version of the robustness calculation for testing.
    The actual implementation is in ContinuousBacktester._calculate_robustness()
    """
    if weights is None:
        weights = {
            'oos_ratio': 0.50,
            'trade_significance': 0.35,
            'simplicity': 0.15,
        }

    # 1. OOS/IS ratio (closer to 1 = less overfit)
    if is_sharpe > 0:
        oos_ratio = min(1.0, max(0, oos_sharpe / is_sharpe))
    else:
        oos_ratio = 0.0

    # 2. Trade significance (more trades = more reliable)
    total_trades = is_trades + oos_trades
    trade_score = min(1.0, total_trades / trade_target)

    # 3. Simplicity (fewer indicators = less overfit)
    simplicity = 1.0 / num_indicators if num_indicators > 0 else 0.5

    # Weighted robustness score
    return (
        weights['oos_ratio'] * oos_ratio +
        weights['trade_significance'] * trade_score +
        weights['simplicity'] * simplicity
    )


class TestRobustnessCalculation:
    """Tests for robustness score calculation."""

    def test_perfect_robustness(self):
        """Perfect strategy: OOS=IS, 200 trades, 1 indicator -> robustness = 1.0."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,  # OOS = IS -> ratio = 1.0
            is_trades=100,
            oos_trades=100,  # 200 trades > 150 -> trade_score = 1.0
            num_indicators=1,  # 1 indicator -> simplicity = 1.0
        )
        # 0.50 * 1.0 + 0.35 * 1.0 + 0.15 * 1.0 = 1.0
        assert robustness == 1.0

    def test_overfit_strategy_fails(self):
        """Overfit strategy: OOS << IS -> low robustness."""
        robustness = calculate_robustness(
            is_sharpe=5.0,
            oos_sharpe=1.0,  # 80% degradation -> ratio = 0.2
            is_trades=50,
            oos_trades=20,  # 70 trades -> trade_score = 0.47
            num_indicators=3,  # simplicity = 0.33
        )
        # 0.50 * 0.2 + 0.35 * 0.47 + 0.15 * 0.33 = 0.10 + 0.16 + 0.05 = 0.31
        assert robustness < 0.50  # Should definitely fail threshold

    def test_low_trades_reduces_robustness(self):
        """Low trade count = low confidence."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,  # Perfect ratio = 1.0
            is_trades=10,
            oos_trades=5,  # Only 15 trades -> trade_score = 0.1
            num_indicators=1,  # simplicity = 1.0
        )
        # 0.50 * 1.0 + 0.35 * 0.1 + 0.15 * 1.0 = 0.50 + 0.035 + 0.15 = 0.685
        assert robustness < 0.80  # Below threshold due to low trades

    def test_many_indicators_reduces_robustness(self):
        """Many indicators = higher overfitting risk."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,  # Perfect ratio = 1.0
            is_trades=100,
            oos_trades=100,  # trade_score = 1.0
            num_indicators=5,  # simplicity = 0.2
        )
        # 0.50 * 1.0 + 0.35 * 1.0 + 0.15 * 0.2 = 0.50 + 0.35 + 0.03 = 0.88
        assert robustness >= 0.80  # Still passes, but lower

    def test_negative_is_sharpe_zero_oos_ratio(self):
        """Negative IS Sharpe -> OOS ratio = 0."""
        robustness = calculate_robustness(
            is_sharpe=-1.0,  # Negative
            oos_sharpe=2.0,
            is_trades=100,
            oos_trades=100,
            num_indicators=1,
        )
        # oos_ratio = 0, so 0.50 * 0 + 0.35 * 1.0 + 0.15 * 1.0 = 0.50
        assert robustness == 0.50

    def test_oos_better_than_is_capped(self):
        """OOS > IS should be capped at 1.0 (not rewarded for luck)."""
        robustness = calculate_robustness(
            is_sharpe=1.0,
            oos_sharpe=3.0,  # OOS > IS -> ratio capped at 1.0
            is_trades=100,
            oos_trades=100,
            num_indicators=1,
        )
        # Should still be 1.0, not higher
        assert robustness == 1.0

    def test_zero_trades(self):
        """Zero trades = zero trade score contribution."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,
            is_trades=0,
            oos_trades=0,
            num_indicators=1,
        )
        # 0.50 * 1.0 + 0.35 * 0.0 + 0.15 * 1.0 = 0.65
        assert robustness == 0.65

    def test_threshold_boundary_pass(self):
        """Strategy exactly at threshold should pass."""
        # Need: robustness = 0.80
        # With 1 indicator (simplicity=1.0): 0.15 * 1.0 = 0.15
        # Need remaining 0.65 from oos_ratio + trade_score
        # If trade_score = 1.0: 0.35 * 1.0 = 0.35
        # Need oos_ratio to give 0.30: 0.50 * X = 0.30 -> X = 0.60
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=1.2,  # ratio = 0.6
            is_trades=100,
            oos_trades=50,  # trade_score = 1.0
            num_indicators=1,
        )
        # 0.50 * 0.6 + 0.35 * 1.0 + 0.15 * 1.0 = 0.30 + 0.35 + 0.15 = 0.80
        assert robustness >= 0.80 or robustness == pytest.approx(0.80)

    def test_threshold_boundary_fail(self):
        """Strategy just below threshold should fail."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=1.1,  # ratio = 0.55 (just under 0.6)
            is_trades=100,
            oos_trades=50,
            num_indicators=1,
        )
        # 0.50 * 0.55 + 0.35 * 1.0 + 0.15 * 1.0 = 0.275 + 0.35 + 0.15 = 0.775
        assert robustness < 0.80

    def test_real_world_good_strategy(self):
        """Realistic good strategy parameters."""
        robustness = calculate_robustness(
            is_sharpe=2.5,
            oos_sharpe=2.2,  # 12% degradation -> ratio = 0.88
            is_trades=120,
            oos_trades=40,  # 160 trades -> trade_score = 1.0
            num_indicators=2,  # simplicity = 0.5
        )
        # 0.50 * 0.88 + 0.35 * 1.0 + 0.15 * 0.5 = 0.44 + 0.35 + 0.075 = 0.865
        assert robustness >= 0.80

    def test_real_world_overfit_strategy(self):
        """Realistic overfit strategy parameters."""
        robustness = calculate_robustness(
            is_sharpe=4.5,  # Very high IS Sharpe
            oos_sharpe=1.5,  # 67% degradation -> ratio = 0.33
            is_trades=80,
            oos_trades=25,  # 105 trades -> trade_score = 0.7
            num_indicators=3,  # simplicity = 0.33
        )
        # 0.50 * 0.33 + 0.35 * 0.7 + 0.15 * 0.33 = 0.165 + 0.245 + 0.05 = 0.46
        assert robustness < 0.50


class TestRobustnessWeights:
    """Tests for custom weight configurations."""

    def test_custom_weights(self):
        """Verify custom weights are applied correctly."""
        custom_weights = {
            'oos_ratio': 0.60,
            'trade_significance': 0.30,
            'simplicity': 0.10,
        }
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,
            is_trades=100,
            oos_trades=100,
            num_indicators=1,
            weights=custom_weights,
        )
        # Still 1.0 because all components are maxed
        assert robustness == pytest.approx(1.0)

    def test_custom_trade_target(self):
        """Verify custom trade target is used."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,
            is_trades=50,
            oos_trades=50,  # 100 trades
            num_indicators=1,
            trade_target=100,  # Custom target = 100
        )
        # trade_score = 100/100 = 1.0 (instead of 100/150 = 0.67)
        assert robustness == 1.0


class TestRobustnessEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_is_sharpe(self):
        """IS Sharpe = 0 should result in oos_ratio = 0."""
        robustness = calculate_robustness(
            is_sharpe=0.0,
            oos_sharpe=2.0,
            is_trades=100,
            oos_trades=100,
            num_indicators=1,
        )
        assert robustness == 0.50  # Only trade_score (0.35) + simplicity (0.15)

    def test_negative_oos_sharpe(self):
        """Negative OOS Sharpe should be capped at 0."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=-1.0,  # Negative OOS
            is_trades=100,
            oos_trades=100,
            num_indicators=1,
        )
        # oos_ratio = max(0, -0.5) = 0
        assert robustness == 0.50

    def test_very_high_trades(self):
        """Very high trade count should still cap at 1.0."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,
            is_trades=500,
            oos_trades=500,  # 1000 trades
            num_indicators=1,
        )
        # trade_score capped at 1.0
        assert robustness == 1.0

    def test_zero_indicators_default(self):
        """Zero indicators should use default simplicity of 0.5."""
        robustness = calculate_robustness(
            is_sharpe=2.0,
            oos_sharpe=2.0,
            is_trades=100,
            oos_trades=100,
            num_indicators=0,  # Edge case
        )
        # simplicity = 0.5 (default for 0 indicators)
        # 0.50 * 1.0 + 0.35 * 1.0 + 0.15 * 0.5 = 0.925
        assert robustness == pytest.approx(0.925)
